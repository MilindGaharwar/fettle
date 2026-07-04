#!/usr/bin/env python3
"""Fettle full-project quality scanner.

Runs ruff + semgrep across a project tree, merges and deduplicates findings,
and reports them sorted by severity.  Supports baseline diffing for
incremental adoption.

Usage:
    python3 quality_scan.py [--root DIR] [--baseline FILE] [--update-baseline] [--json]
"""

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

# Populated from [severity] config in main(); defaults match config.DEFAULTS.
ERROR_RULES = {"BLE001", "S110", "S608", "S701"}
WARNING_PREFIXES = {"SIM", "UP"}

# Directories that are never part of the project's own code.
_SKIP_DIRS = {"node_modules", "__pycache__", "venv", "build", "dist"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_tool(name: str) -> str | None:
    """Return absolute path to *name* or None."""
    local = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    found = shutil.which(name)
    return found


def _load_ignore(root: str) -> list[str]:
    ignore_file = os.path.join(root, ".fettle-ignore")
    if not os.path.isfile(ignore_file):
        return []
    patterns: list[str] = []
    with open(ignore_file) as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def _collect_py_files(root: str, ignore_patterns: list[str]) -> list[str]:
    results: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            if _is_ignored(rel, ignore_patterns):
                continue
            results.append(os.path.join(dirpath, fn))
    return results


def _is_ignored(rel_path: str, ignore_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_path, pat) for pat in ignore_patterns)


def _classify(rule_id: str, tool_severity: str = "") -> str:
    if rule_id in ERROR_RULES:
        return "ERROR"
    if tool_severity in ("error", "ERROR"):
        return "ERROR"
    for prefix in WARNING_PREFIXES:
        if rule_id.startswith(prefix):
            return "WARNING"
    if tool_severity in ("warning", "WARNING"):
        return "WARNING"
    return "INFO"


def _finding_key(f: dict) -> str:
    raw = f"{f['file']}:{f['line']}:{f['rule']}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _severity_order(sev: str) -> int:
    return {"ERROR": 0, "WARNING": 1, "INFO": 2}.get(sev, 3)


# ---------------------------------------------------------------------------
# Tool runners
# ---------------------------------------------------------------------------

def run_ruff(root: str) -> list[dict]:
    ruff = _resolve_tool("ruff")
    if not ruff:
        print("WARNING: ruff not found — skipping ruff checks", file=sys.stderr)
        return []

    ruff_toml = os.path.join(PLUGIN_ROOT, "rules", ".ruff.toml")
    cmd = [ruff, "check", "--output-format=json"]
    if os.path.isfile(ruff_toml):
        cmd.extend(["--config", ruff_toml])
    cmd.append(root)

    result = subprocess.run(cmd, capture_output=True, text=True)
    # ruff exits 1 when findings exist — that is expected
    if result.returncode not in (0, 1):
        print(f"WARNING: ruff exited {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
        return []

    try:
        entries = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        print("WARNING: could not parse ruff JSON output", file=sys.stderr)
        return []

    findings: list[dict] = []
    for e in entries:
        findings.append({
            "file": e.get("filename", ""),
            "line": e.get("location", {}).get("row", 0),
            "rule": e.get("code", "UNKNOWN"),
            "message": e.get("message", ""),
            "severity": _classify(e.get("code", ""), ""),
            "tool": "ruff",
        })
    return findings


def run_semgrep(root: str) -> list[dict]:
    semgrep = _resolve_tool("semgrep")
    if not semgrep:
        print("WARNING: semgrep not found — skipping semgrep checks", file=sys.stderr)
        return []

    rules_file = os.path.join(PLUGIN_ROOT, "rules", "llm-antipatterns.yml")
    if not os.path.isfile(rules_file):
        print("WARNING: semgrep rules file not found — skipping semgrep checks", file=sys.stderr)
        return []

    cmd = [semgrep, "--config", rules_file, "--json", root]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):
        print(f"WARNING: semgrep exited {result.returncode}: {result.stderr.strip()[:200]}", file=sys.stderr)
        return []

    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        print("WARNING: could not parse semgrep JSON output", file=sys.stderr)
        return []

    findings: list[dict] = []
    for r in data.get("results", []):
        sev = r.get("extra", {}).get("severity", "warning").upper()
        findings.append({
            "file": r.get("path", ""),
            "line": r.get("start", {}).get("line", 0),
            "rule": r.get("check_id", "UNKNOWN").rsplit(".", 1)[-1],
            "message": r.get("extra", {}).get("message", ""),
            "severity": _classify(r.get("check_id", "").rsplit(".", 1)[-1], sev),
            "tool": "semgrep",
        })
    return findings


# ---------------------------------------------------------------------------
# Baseline
# ---------------------------------------------------------------------------

def _load_baseline(path: str, root: str) -> dict[str, dict]:
    if not os.path.isfile(path):
        return {}
    with open(path) as fh:
        items = json.load(fh)
    # Legacy baselines stored absolute paths; normalize so they keep matching.
    for f in items:
        if os.path.isabs(f.get("file", "")):
            f["file"] = os.path.relpath(f["file"], root)
    return {_finding_key(f): f for f in items}


def _save_baseline(path: str, findings: list[dict]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(findings, fh, indent=2)
    os.rename(tmp, path)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_human(root: str, findings: list[dict], file_count: int) -> None:
    errors = [f for f in findings if f["severity"] == "ERROR"]
    warnings = [f for f in findings if f["severity"] == "WARNING"]
    infos = [f for f in findings if f["severity"] == "INFO"]

    print("=== Fettle Quality Report ===")
    print(f"Root: {root}")
    print(f"Files scanned: {file_count}")
    print()

    for label, group in [("ERRORS", errors), ("WARNINGS", warnings), ("INFO", infos)]:
        print(f"{label} ({len(group)}):")
        if not group:
            print("  (none)")
        for f in group:
            print(f"  {f['file']}:{f['line']}  {f['rule']}  {f['message']}")
        print()

    print(f"Summary: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")


def _print_json(findings: list[dict], file_count: int) -> None:
    print(json.dumps({
        "file_count": file_count,
        "findings": findings,
        "summary": {
            "errors": sum(1 for f in findings if f["severity"] == "ERROR"),
            "warnings": sum(1 for f in findings if f["severity"] == "WARNING"),
            "info": sum(1 for f in findings if f["severity"] == "INFO"),
        },
    }, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle full-project quality scan")
    parser.add_argument("--root", default=os.getcwd(), help="Project root (default: cwd)")
    parser.add_argument("--baseline", default=None, help="Baseline JSON for incremental reporting")
    parser.add_argument("--update-baseline", action="store_true", help="Save current findings as baseline")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    root = os.path.abspath(args.root)

    # [severity] config is the single source; constants are the fallback defaults.
    cfg = load_config(root)
    global ERROR_RULES, WARNING_PREFIXES
    ERROR_RULES = set(cfg["severity"]["error_rules"])
    WARNING_PREFIXES = set(cfg["severity"]["warning_prefixes"])

    ignore_patterns = _load_ignore(root)
    py_files = _collect_py_files(root, ignore_patterns)
    file_count = len(py_files)

    # Run tools on the whole directory (they handle file discovery internally)
    findings = run_ruff(root) + run_semgrep(root)

    # Root-relative paths: keeps committed baselines portable across machines
    # and checkout locations.
    for f in findings:
        if os.path.isabs(f["file"]):
            f["file"] = os.path.relpath(f["file"], root)
    findings = [f for f in findings if not _is_ignored(f["file"], ignore_patterns)]

    # Deduplicate (same file+line+rule)
    seen: dict[str, dict] = {}
    for f in findings:
        key = _finding_key(f)
        if key not in seen:
            seen[key] = f
    findings = list(seen.values())

    # Sort: severity (errors first), then file path, then line
    findings.sort(key=lambda f: (_severity_order(f["severity"]), f["file"], f["line"]))

    # Baseline diff
    if args.baseline and not args.update_baseline:
        baseline = _load_baseline(args.baseline, root)
        findings = [f for f in findings if _finding_key(f) not in baseline]

    # Save baseline
    if args.update_baseline:
        bl_path = args.baseline or os.path.join(root, ".fettle", "baseline.json")
        bl_dir = os.path.dirname(bl_path)
        if bl_dir:
            os.makedirs(bl_dir, exist_ok=True)
        _save_baseline(bl_path, findings)
        print(f"Baseline saved: {bl_path} ({len(findings)} findings)", file=sys.stderr)

    # Output
    if args.json_output:
        _print_json(findings, file_count)
    else:
        _print_human(root, findings, file_count)

    # Exit code
    error_count = sum(1 for f in findings if f["severity"] == "ERROR")
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
