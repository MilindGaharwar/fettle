#!/usr/bin/env python3
"""Fettle Unified Quality Gate.

Single entry point for ALL quality dimensions:
- UX: spec existence for frontend files (BLOCKING)
- UI: design token compliance (WARNING)
- PLANNING: plan artifact for multi-file changes (BLOCKING at 3+ files)
- TESTS: per-file tracking + freshness check (BLOCKING at Stop)

Runs as PreToolUse, PostToolUse, and Stop hook. Determines which checks
to run based on context (tool name, file path, hook event).

Exit 0 = allow/warn. Exit 2 = BLOCK.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config, state_dir  # noqa: E402

# ─── Configuration ────────────────────────────────────────────────────────────

FRONTEND_PATHS = ["frontend/src/pages/", "frontend/src/components/", "src/pages/", "src/components/"]
FRONTEND_EXEMPT = ["components/ui/", "utils/", "hooks/", "stores/", "api/", "test", ".test.", ".spec."]

# From plan_gate.py — comprehensive extension/path exemptions
IMPL_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".sh"}
EXEMPT_EXTS = {".md", ".toml", ".json", ".yml", ".yaml", ".txt", ".cfg", ".ini", ".env", ".lock"}
EXEMPT_PATH_PREFIXES = ("/tmp/", "/var/tmp/")
EXEMPT_PATH_CONTAINS = ("/tests/", "/test/", "/.fettle/", "/memory/", "/__pycache__/", "/node_modules/", "/.venv/", "/alembic/versions/")

# Session-scoped state paths — set by _init_state(session_id) in main().
TRACKING_FILE = ""
EDIT_TRACKING_FILE = ""
BOOTSTRAP_WARNED_MARKER = ""

# From post_bash_test_detect.py — comprehensive test pattern detection
TEST_PATTERNS = [
    r"\bpytest\b",
    r"\bpython3?\s+-[cm]\b",
    r"\bcargo\s+test\b",
    r"\bnpm\s+test\b",
    r"\bpnpm\s+test\b",
    r"\bnpx\s+(jest|vitest|mocha)\b",
    r"\bvitest\b",
    r"\bgo\s+test\b",
    r"\bpy_compile\.compile\b",
    r"\bimport\s+unittest\b",
    r"\bassert\s+",
    r"\bprint\(['\"]PASS",
    r"\bprint\(['\"]ALL PASS",
    r"\bplaywright\s+test\b",
    r"\bscreenshot\b",
    r"page\.\w+",
]

BROWSER_TEST_MARKER = ""  # set by _init_state()
FRONTEND_EXTENSIONS = {".tsx", ".ts", ".jsx", ".js", ".css"}
_TEST_RE = re.compile("|".join(TEST_PATTERNS), re.IGNORECASE)

ALLOWED_HEX: set[str] = set()  # repo-specific brand palette; configurable via .fettle.toml in v0.3.0 (WP-7)

HARDCODED_PATTERNS = [
    (r"#[0-9a-fA-F]{6}\b", "Hardcoded hex color — use var(--color-*) token"),
    (r"(?:rgb|rgba|hsl|hsla)\(", "Hardcoded color function — use token"),
]


# ─── File Classification (from plan_gate.py) ─────────────────────────────────


def _is_test_file(path: str) -> bool:
    """Detect test files by basename convention."""
    basename = os.path.basename(path)
    return (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or basename.endswith(".test.ts")
        or basename.endswith(".test.tsx")
        or basename.endswith(".spec.ts")
        or basename.endswith(".spec.tsx")
        or basename == "conftest.py"
    )


def _is_implementation_file(path: str, cwd: str = "") -> bool:
    """Determine if a file is implementation code that requires a plan.

    Files outside the project root (scratch files, /tmp experiments) are
    exempt — "is it under cwd" generalizes the old hardcoded /tmp prefixes,
    which wrongly exempted whole projects on systems where tmp IS /tmp.
    """
    if not path:
        return False
    _, ext = os.path.splitext(path)
    if ext in EXEMPT_EXTS:
        return False
    if ext not in IMPL_EXTENSIONS:
        return False
    if cwd and os.path.isabs(path):
        root = os.path.abspath(cwd)
        if not os.path.abspath(path).startswith(root + os.sep):
            return False
    elif any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
        return False
    if any(s in path for s in EXEMPT_PATH_CONTAINS):
        return False
    return not _is_test_file(path)


# ─── Scanners ─────────────────────────────────────────────────────────────────


def scan_ux(file_path: str, cwd: str) -> list[str]:
    """BLOCKING: Check if UX spec exists for frontend page/component edits."""
    is_frontend = any(p in file_path for p in FRONTEND_PATHS)
    if not is_frontend:
        return []
    if any(p in file_path for p in FRONTEND_EXEMPT):
        return []

    docs_dir = Path(cwd) / "docs"
    if not docs_dir.exists():
        return [f"UX: No docs/ directory. Create a UX spec before editing {Path(file_path).name} (disable via [gates.ux_spec] enabled=false)"]

    specs = list(docs_dir.glob("*.ux-spec.md")) + list(docs_dir.glob("UX-*.md"))
    if not specs:
        return ["UX: No .ux-spec.md found. Create docs/[feature].ux-spec.md before frontend work (disable via [gates.ux_spec] enabled=false)"]

    return []


def scan_ui(file_path: str, content: str, ui_cfg: dict | None = None) -> list[str]:
    """WARNING: Check for hardcoded colors in frontend files."""
    allowed_hex = {h.lower() for h in (ui_cfg or {}).get("allowed_hex", [])} or ALLOWED_HEX
    is_frontend = any(p in file_path for p in FRONTEND_PATHS)
    if not is_frontend:
        return []
    if any(p in file_path for p in FRONTEND_EXEMPT):
        return []
    if not content:
        return []

    findings = []
    for i, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("import") or stripped.startswith("*"):
            continue
        for pattern, message in HARDCODED_PATTERNS:
            for match in re.findall(pattern, line):
                if match.lower() in allowed_hex:
                    continue
                if "var(--" in line:
                    continue
                findings.append(f"UI: Line {i}: {match} — {message}")

    return findings[:5]


def scan_planning(file_path: str, cwd: str, plan_cfg: dict | None = None) -> list[str]:
    """BLOCKING (threshold+ files): Enforce plan for multi-file changes."""
    cfg = plan_cfg or {}
    threshold = int(cfg.get("threshold", 3))
    plan_dir_name = str(cfg.get("plan_dir", "docs"))
    max_age_s = float(cfg.get("max_age_hours", 1)) * 3600

    if not _is_implementation_file(file_path, cwd):
        return []

    session = _load_tracking()
    if file_path not in session:
        session.append(file_path)
    _save_tracking(session)

    if len(session) < threshold:
        return []

    docs_dir = Path(cwd) / plan_dir_name
    if docs_dir.is_dir():
        for f in docs_dir.iterdir():
            if "plan" in f.name.lower() and f.suffix == ".md" and time.time() - f.stat().st_mtime < max_age_s:
                return []

    return [
        f"PLANNING: {len(session)} implementation files edited without a recent plan in {plan_dir_name}/ "
        f"(disable via [gates.plan] enabled=false in .fettle.toml)"
    ]


def scan_bootstrap(file_path: str, cwd: str) -> list[str]:
    """CI must be set up before development: fire on an impl-file edit in a
    repo with no Fettle CI workflow. The caller decides block vs warn by mode."""
    if not _is_implementation_file(file_path, cwd):
        return []
    workflow = Path(cwd) / ".github" / "workflows" / "fettle.yml"
    if workflow.is_file():
        return []
    return [
        "CI-BOOTSTRAP: this package has no Fettle CI workflow — run `fettle ci init` "
        "to set up boundary/secret + quality enforcement before developing "
        "(strict-block via [gates.ci_bootstrap] mode=strict; disable via enabled=false)"
    ]


def scan_tests_before_commit(command: str) -> list[str]:
    """WARNING: Check test freshness before git commit/push."""
    if "git commit" not in command and "git push" not in command:
        return []

    entries = _load_edit_tracking()
    if not entries:
        return []

    untested = [e for e in entries if not e.get("tested", False)]
    if not untested:
        return []

    files = [os.path.basename(str(e.get("file", ""))) for e in untested[:5]]
    return [f"TESTS: {len(untested)} file(s) untested before commit: {', '.join(files)}"]


def scan_stop_untested(data: dict) -> list[str]:
    """BLOCKING (Stop): Block response if implementation files edited but not tested."""
    cwd = data.get("cwd", "")
    entries = _load_edit_tracking()
    if not entries:
        return []

    findings = []

    untested = []
    for entry in entries:
        fpath = str(entry.get("file", ""))
        if _is_implementation_file(fpath, cwd) and not entry.get("tested", False):
            untested.append(fpath)

    if untested:
        file_list = ", ".join(os.path.basename(f) for f in untested[:10])
        findings.append(f"TESTS: {len(untested)} implementation file(s) edited but not tested: {file_list}")

    # Check if frontend files were edited but no browser test ran
    frontend_edited = any(
        os.path.splitext(str(e.get("file", "")))[1] in FRONTEND_EXTENSIONS
        for e in entries
    )
    if frontend_edited:
        browser_tested = (
            os.path.isfile(BROWSER_TEST_MARKER)
            and time.time() - os.path.getmtime(BROWSER_TEST_MARKER) < 1800
        )
        if not browser_tested:
            findings.append("BROWSER: Frontend files edited but no browser test (Playwright/screenshot) detected. Test the LIVE UI before shipping.")

    return findings


def stamp_tests(command: str):
    """Record test runs — marks ALL tracked files as tested (from post_bash_test_detect.py)."""
    if not _TEST_RE.search(command):
        return

    # Detect browser testing (Playwright with screenshots)
    if "playwright" in command or "screenshot" in command or "chromium.launch" in command:
        Path(BROWSER_TEST_MARKER).touch()

    entries = _load_edit_tracking()
    if not entries:
        return

    changed = False
    for entry in entries:
        if not entry.get("tested", False):
            entry["tested"] = True
            entry["tested_ts"] = time.time()
            changed = True

    if changed:
        _save_edit_tracking(entries)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _load_tracking() -> list[str]:
    """Load session edit list (for planning gate)."""
    try:
        if os.path.isfile(TRACKING_FILE):
            if time.time() - os.path.getmtime(TRACKING_FILE) > 3600:
                return []
            with open(TRACKING_FILE) as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_tracking(files: list[str]):
    """Save session edit list (for planning gate)."""
    try:
        with open(TRACKING_FILE, "w") as f:
            json.dump(files, f)
    except OSError:
        pass


def _load_edit_tracking() -> list[dict]:
    """Load per-file edit tracking JSONL (for test gate)."""
    entries = []
    try:
        if os.path.isfile(EDIT_TRACKING_FILE):
            with open(EDIT_TRACKING_FILE) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return entries


def _save_edit_tracking(entries: list[dict]):
    """Save per-file edit tracking JSONL (atomic write)."""
    try:
        tmp = EDIT_TRACKING_FILE + ".tmp"
        with open(tmp, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        os.replace(tmp, EDIT_TRACKING_FILE)
    except OSError:
        pass


def _init_state(session_id: str) -> None:
    """Bind tracking files to this session's state directory (no /tmp bleed)."""
    global TRACKING_FILE, EDIT_TRACKING_FILE, BROWSER_TEST_MARKER, BOOTSTRAP_WARNED_MARKER
    sdir = state_dir(session_id)
    TRACKING_FILE = str(sdir / "session-edits.json")
    EDIT_TRACKING_FILE = str(sdir / "edits.jsonl")
    BROWSER_TEST_MARKER = str(sdir / "browser-tested.timestamp")
    BOOTSTRAP_WARNED_MARKER = str(sdir / "ci-bootstrap-warned.json")


def _bootstrap_already_warned(cwd: str) -> bool:
    """True if this repo was already nudged this session — advisory warns once."""
    if not BOOTSTRAP_WARNED_MARKER:
        return False
    key = os.path.abspath(cwd)
    warned: list[str] = []
    try:
        if os.path.isfile(BOOTSTRAP_WARNED_MARKER):
            with open(BOOTSTRAP_WARNED_MARKER) as f:
                warned = json.load(f)
    except (OSError, json.JSONDecodeError):
        warned = []
    if key in warned:
        return True
    warned.append(key)
    try:
        with open(BOOTSTRAP_WARNED_MARKER, "w") as f:
            json.dump(warned, f)
    except OSError:
        pass
    return False


# ─── Main Entry Point ─────────────────────────────────────────────────────────


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    cwd = data.get("cwd", ".")
    hook_event = data.get("hook_event", "")

    _init_state(data.get("session_id", "unknown"))
    cfg = load_config(cwd)
    gates = cfg["gates"]

    blocking_findings = []
    warning_findings = []

    # ─── Stop Hook: test enforcement ─────────────────────────────────────
    if hook_event == "Stop" or data.get("stop_hook_active") is not None:
        if gates["tests"]["enabled"]:
            blocking_findings.extend(scan_stop_untested(data))

    # ─── Write/Edit: UX (block) + UI (warn) + Planning (block at 3+) ────
    elif tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("new_string", "") or tool_input.get("content", "")

        # UX and Planning only BLOCK on PreToolUse (edit hasn't happened yet).
        # On PostToolUse the edit already occurred — inform only.
        is_pre = hook_event == "PreToolUse"

        # UX spec check — BLOCKING on Pre, WARNING on Post
        ux_findings = scan_ux(file_path, cwd) if gates["ux_spec"]["enabled"] else []
        if is_pre:
            blocking_findings.extend(ux_findings)
        else:
            warning_findings.extend(ux_findings)

        # UI token check — always WARNING
        ui_findings = scan_ui(file_path, content, gates["ui_colors"]) if gates["ui_colors"]["enabled"] else []
        warning_findings.extend(ui_findings)

        # Planning check — BLOCKING on Pre (3+ files), WARNING on Post
        plan_findings = scan_planning(file_path, cwd, gates["plan"]) if gates["plan"]["enabled"] else []
        if is_pre:
            blocking_findings.extend(plan_findings)
        else:
            warning_findings.extend(plan_findings)

        # CI bootstrap — strict BLOCKS on Pre; advisory warns once per session.
        boot_cfg = gates.get("ci_bootstrap", {})
        if boot_cfg.get("enabled"):
            boot_findings = scan_bootstrap(file_path, cwd)
            if boot_findings and is_pre and boot_cfg.get("mode") == "strict":
                blocking_findings.extend(boot_findings)
            elif boot_findings and not _bootstrap_already_warned(cwd):
                warning_findings.extend(boot_findings)

    # ─── Bash: test stamping + commit warning ────────────────────────────
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        stamp_tests(command)
        if gates["tests"]["enabled"]:
            warning_findings.extend(scan_tests_before_commit(command))

    # ─── Output warnings (never block) ──────────────────────────────────
    if warning_findings:
        print(
            f"\n{'─' * 50}\n"
            f"⚠️  FETTLE WARNING ({len(warning_findings)} finding{'s' if len(warning_findings) != 1 else ''})\n"
            f"{'─' * 50}",
            file=sys.stderr,
        )
        for f in warning_findings:
            print(f"  • {f}", file=sys.stderr)
        print(f"{'─' * 50}\n", file=sys.stderr)

    # ─── Output blockers (exit 2) ────────────────────────────────────────
    if blocking_findings:
        reason = "\n".join(f"  • {f}" for f in blocking_findings)
        output = {
            "decision": "block",
            "reason": f"Fettle quality gate BLOCKED ({len(blocking_findings)} issue{'s' if len(blocking_findings) != 1 else ''}):\n{reason}",
            "hookSpecificOutput": {
                "hookEventName": hook_event or "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Fettle: {blocking_findings[0]}",
            },
        }
        print(json.dumps(output))
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except (json.JSONDecodeError, OSError, ValueError):
        sys.exit(0)
