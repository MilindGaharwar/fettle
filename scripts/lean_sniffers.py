#!/usr/bin/env python3
"""WP-106 — Tier 1 Lean Sniffers.

PostToolUse(Write|Edit) hook that silently detects over-engineering patterns
and appends candidates to session state JSONL. No stdout, always exits 0.
"""

import ast
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402

# ─── Constants ────────────────────────────────────────────────────────────────

IMPL_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go"}
MANIFEST_FILES = {
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "Pipfile", "package.json", "Cargo.toml", "go.mod",
}
MANIFEST_PATTERNS = {re.compile(r"requirements.*\.txt")}

IGNORE_PATTERNS = [
    "/__pycache__/", "/.venv/", "/venv/", "/node_modules/",
    "/dist/", "/build/", "/migrations/", "/.pytest_cache/",
    "/.mypy_cache/", "/.ruff_cache/",
]

MAX_FILE_BYTES = 262144  # 256 KiB

ABSTRACTION_NAMES = re.compile(
    r"\b(Factory|Manager|Provider|Registry|Strategy|Adapter|Builder|"
    r"Resolver|Coordinator|Orchestrator|Service|Base|Abstract|Interface)\b"
)

ABSTRACTION_CLASS_RE = re.compile(
    r"^class\s+\w*(?:Factory|Manager|Provider|Registry|Strategy|Adapter|Builder|"
    r"Resolver|Coordinator|Orchestrator|Service|Base|Abstract|Interface)\w*",
    re.MULTILINE,
)
ABSTRACTION_FUNC_RE = re.compile(
    r"^(?:def|function|const)\s+\w*(?:factory|manager|provider|registry|strategy|"
    r"adapter|builder|resolver|coordinator|orchestrator|service)\w*",
    re.MULTILINE | re.IGNORECASE,
)

DEFAULT_THRESHOLDS = {
    "large_added_lines": 120,
    "large_function_lines": 60,
    "large_class_lines": 80,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _is_test_path(path: str) -> bool:
    return "/tests/" in path or "/test/" in path or "test_" in os.path.basename(path)


def _is_ignored(path: str) -> bool:
    return any(pat in path for pat in IGNORE_PATTERNS)


def _is_manifest(path: str) -> bool:
    basename = os.path.basename(path)
    if basename in MANIFEST_FILES:
        return True
    return any(p.match(basename) for p in MANIFEST_PATTERNS)


def _get_changed_lines(file_path: str, cwd: str) -> set[int] | None:
    """Return set of added line numbers via git diff, or None for whole-file fallback."""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "diff", "--no-ext-diff", "--unified=0", "--", file_path],
            capture_output=True, text=True, timeout=0.5,
        )
        if result.returncode != 0:
            return None
        lines: set[int] = set()
        for match in re.finditer(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", result.stdout):
            start = int(match.group(1))
            count = int(match.group(2)) if match.group(2) else 1
            for i in range(start, start + count):
                lines.add(i)
        if not lines:
            # Try untracked
            ls_result = subprocess.run(
                ["git", "-C", cwd, "ls-files", "--others", "--exclude-standard", "--", file_path],
                capture_output=True, text=True, timeout=0.5,
            )
            if ls_result.returncode == 0 and ls_result.stdout.strip():
                return None  # untracked → whole file
            # Tracked file with no diff → empty set (nothing changed)
            return lines
        return lines
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def _make_candidate(
    sniffer_id: str,
    ladder_step: str,
    file_path: str,
    cwd: str,
    line_start: int,
    line_end: int,
    evidence: str,
    message: str,
    severity_hint: str,
    session_id: str,
) -> dict:
    relative = os.path.relpath(file_path, cwd) if cwd else file_path
    evidence_hash = hashlib.sha256(evidence.encode()).hexdigest()[:16]
    cand_id = hashlib.sha256(
        f"{session_id}:{sniffer_id}:{relative}:{line_start}:{evidence_hash}".encode()
    ).hexdigest()[:24]
    return {
        "id": cand_id,
        "sniffer_id": sniffer_id,
        "ladder_step": ladder_step,
        "file_path": file_path,
        "relative_path": relative,
        "line_start": line_start,
        "line_end": line_end,
        "evidence": evidence[:200],
        "message": message,
        "severity_hint": severity_hint,
        "dedupe_key": f"{sniffer_id}:{relative}:{evidence_hash}",
    }


def _append_candidates(state_dir: str, session_id: str, candidates: list[dict]) -> None:
    if not candidates:
        return
    sessions_dir = os.path.join(state_dir, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_.\-]", "_", session_id)
    path = os.path.join(sessions_dir, f"{safe_id}.lean.jsonl")
    with open(path, "a") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")


LEAN_MARKER_RE = re.compile(r"fettle:lean:")


def _suppress_near_lean_markers(candidates: list[dict], content: str) -> list[dict]:
    """Remove candidates whose flagged lines are near a fettle:lean: marker."""
    lines = content.splitlines()
    marker_lines: set[int] = set()
    for i, line in enumerate(lines, 1):
        if LEAN_MARKER_RE.search(line):
            marker_lines.add(i)
    if not marker_lines:
        return candidates
    filtered = []
    for c in candidates:
        start = c.get("line_start", 0)
        end = c.get("line_end", start)
        suppressed = any(
            abs(m - start) <= 3 or abs(m - end) <= 3
            for m in marker_lines
        )
        if not suppressed:
            filtered.append(c)
    return filtered


# ─── Sniffers ─────────────────────────────────────────────────────────────────


def sniff_lr001(file_path: str, content: str, changed_lines: set[int] | None,
                cwd: str, session_id: str) -> list[dict]:
    """LR001: New dependency added to manifest."""
    if not _is_manifest(file_path):
        return []
    candidates = []
    dep_patterns = [
        re.compile(r"^\+?\s*[\w\-]+==[^\s]+", re.MULTILINE),  # pip: pkg==ver
        re.compile(r"^\+?\s*[\w\-]+\s*[><=~!]+", re.MULTILINE),  # pip constraints
        re.compile(r'^\+?\s*"[\w\-@/]+"\s*:\s*"[^"]+"', re.MULTILINE),  # npm
        re.compile(r"^\+?\s*[\w\-]+\s*=\s*\{?\s*version", re.MULTILINE),  # Cargo
        re.compile(r"^\+?\s*[\w\-]+\s*=\s*\"[^\"]+\"", re.MULTILINE),  # pyproject
    ]
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if changed_lines is not None and i not in changed_lines:
            continue
        for pat in dep_patterns:
            if pat.match(line.strip()):
                candidates.append(_make_candidate(
                    "LR001_DEPENDENCY_ADDED", "existing_dep",
                    file_path, cwd, i, i,
                    line.strip(), "A new dependency was added.",
                    "high", session_id,
                ))
                break
    return candidates


def sniff_lr002(file_path: str, content: str, changed_lines: set[int] | None,
                cwd: str, session_id: str) -> list[dict]:
    """LR002: New abstraction-heavy class/function names."""
    if _is_test_path(file_path):
        return []
    candidates = []
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        if changed_lines is not None and i not in changed_lines:
            continue
        if ABSTRACTION_CLASS_RE.match(line.strip()) or ABSTRACTION_FUNC_RE.match(line.strip()):
            candidates.append(_make_candidate(
                "LR002_NEW_ABSTRACTION_NAME", "YAGNI",
                file_path, cwd, i, i,
                line.strip(), "Name suggests speculative abstraction.",
                "medium", session_id,
            ))
    return candidates


def sniff_lr003(file_path: str, tree: ast.Module | None, changed_lines: set[int] | None,
                cwd: str, session_id: str) -> list[dict]:
    """LR003: Pass-through wrapper (Python AST only)."""
    if tree is None:
        return []
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if changed_lines is not None and node.lineno not in changed_lines:
            continue
        real_stmts = [s for s in node.body if not isinstance(s, ast.Pass)]
        if len(real_stmts) != 1:
            continue
        stmt = real_stmts[0]
        is_return_call = isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call)
        is_expr_call = isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)
        if not (is_return_call or is_expr_call):
            continue
        candidates.append(_make_candidate(
            "LR003_PASS_THROUGH_WRAPPER", "one-liner",
            file_path, cwd, node.lineno, node.end_lineno or node.lineno,
            f"def {node.name}(...): single delegation",
            "Function only delegates to another call.",
            "medium", session_id,
        ))
    return candidates


def sniff_lr004(file_path: str, tree: ast.Module | None, changed_lines: set[int] | None,
                cwd: str, session_id: str) -> list[dict]:
    """LR004: Single-method class (Python AST only)."""
    if tree is None:
        return []
    candidates = []
    dunder_ok = {"__init__", "__repr__", "__str__", "__enter__", "__exit__",
                 "__del__", "__hash__", "__eq__", "__ne__", "__lt__", "__gt__"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if changed_lines is not None and node.lineno not in changed_lines:
            continue
        # Skip exception classes
        if any(
            (isinstance(b, ast.Name) and "Error" in b.id)
            or (isinstance(b, ast.Name) and "Exception" in b.id)
            or (isinstance(b, ast.Attribute) and ("Error" in b.attr or "Exception" in b.attr))
            for b in node.bases
        ):
            continue
        methods = [
            n for n in node.body
            if isinstance(n, ast.FunctionDef) and n.name not in dunder_ok
        ]
        if len(methods) == 1:
            candidates.append(_make_candidate(
                "LR004_SINGLE_METHOD_CLASS", "minimum_code",
                file_path, cwd, node.lineno, node.end_lineno or node.lineno,
                f"class {node.name}: single method '{methods[0].name}'",
                "Class has only one real method — consider a function instead.",
                "medium", session_id,
            ))
    return candidates


def sniff_lr008(file_path: str, content: str, changed_lines: set[int] | None,
                tree: ast.Module | None, cwd: str, session_id: str,
                thresholds: dict) -> list[dict]:
    """LR008: Large addition."""
    candidates = []
    large_added = thresholds.get("large_added_lines", 120)
    large_func = thresholds.get("large_function_lines", 60)
    large_class = thresholds.get("large_class_lines", 80)

    # Check total added lines
    if changed_lines is not None:
        if len(changed_lines) >= large_added:
            candidates.append(_make_candidate(
                "LR008_LARGE_ADDITION", "minimum_code",
                file_path, cwd, min(changed_lines), max(changed_lines),
                f"{len(changed_lines)} lines added",
                f"Large addition ({len(changed_lines)} lines). Consider breaking down.",
                "low", session_id,
            ))
    else:
        # Whole file fallback — count non-empty lines
        line_count = sum(1 for line in content.splitlines() if line.strip())
        if line_count >= large_added:
            candidates.append(_make_candidate(
                "LR008_LARGE_ADDITION", "minimum_code",
                file_path, cwd, 1, line_count,
                f"{line_count} lines in new/untracked file",
                f"Large addition ({line_count} lines). Consider breaking down.",
                "low", session_id,
            ))

    # Check individual functions/classes (Python only)
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                length = (node.end_lineno or node.lineno) - node.lineno + 1
                if length >= large_func and (changed_lines is None or node.lineno in changed_lines):
                    candidates.append(_make_candidate(
                        "LR008_LARGE_ADDITION", "minimum_code",
                        file_path, cwd, node.lineno, node.end_lineno or node.lineno,
                        f"def {node.name}: {length} lines",
                        f"Function '{node.name}' is {length} lines.",
                        "low", session_id,
                    ))
            elif isinstance(node, ast.ClassDef):
                length = (node.end_lineno or node.lineno) - node.lineno + 1
                if length >= large_class and (changed_lines is None or node.lineno in changed_lines):
                    candidates.append(_make_candidate(
                        "LR008_LARGE_ADDITION", "minimum_code",
                        file_path, cwd, node.lineno, node.end_lineno or node.lineno,
                        f"class {node.name}: {length} lines",
                        f"Class '{node.name}' is {length} lines.",
                        "low", session_id,
                    ))
    return candidates


def sniff_lr012(file_path: str, tree: ast.Module | None, cwd: str,
                session_id: str) -> list[dict]:
    """LR012: Duplicate helper name found elsewhere in repo."""
    if tree is None:
        return []
    candidates = []
    func_names = [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    ]
    for func in func_names:
        name = func.name
        if name.startswith("_") or name.startswith("test_"):
            continue
        try:
            result = subprocess.run(
                ["git", "-C", cwd, "grep", "-l", f"def {name}(", "--", "*.py"],
                capture_output=True, text=True, timeout=0.04,
            )
            if result.returncode == 0:
                matches = [
                    m for m in result.stdout.strip().splitlines()
                    if os.path.join(cwd, m) != file_path
                    and os.path.abspath(os.path.join(cwd, m)) != os.path.abspath(file_path)
                ]
                if matches:
                    candidates.append(_make_candidate(
                        "LR012_DUPLICATE_LOCAL_HELPER_NAME", "reuse",
                        file_path, cwd, func.lineno, func.end_lineno or func.lineno,
                        f"def {name}() also in: {matches[0]}",
                        f"Function '{name}' already exists in {matches[0]}. Consider reuse.",
                        "high", session_id,
                    ))
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    return candidates


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    start_time = time.monotonic()

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    file_path: str = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    cwd: str = data.get("cwd", ".")
    session_id: str = data.get("session_id", "unknown")

    # Extension guard
    ext = os.path.splitext(file_path)[1].lower()
    is_manifest = _is_manifest(file_path)
    if ext not in IMPL_EXTENSIONS and not is_manifest:
        sys.exit(0)

    # Ignore patterns
    if _is_ignored(file_path):
        sys.exit(0)

    # File existence and size
    if not os.path.isfile(file_path):
        sys.exit(0)
    if os.path.getsize(file_path) > MAX_FILE_BYTES:
        sys.exit(0)

    # Config
    cfg = load_config(cwd)
    lean_cfg = cfg.get("gates", {}).get("lean_review", {})
    if not lean_cfg.get("enabled", True):
        sys.exit(0)
    tier1_cfg = lean_cfg.get("tier1", {})
    if not tier1_cfg.get("enabled", True):
        sys.exit(0)
    thresholds = {**DEFAULT_THRESHOLDS, **tier1_cfg.get("thresholds", {})}
    max_runtime_ms = tier1_cfg.get("max_runtime_ms", 200)

    # Read content
    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        sys.exit(0)

    # Changed lines
    changed_lines = _get_changed_lines(file_path, cwd)

    # AST (Python only)
    tree: ast.Module | None = None
    if ext == ".py":
        with contextlib.suppress(SyntaxError):
            tree = ast.parse(content)

    # State dir
    state_dir = os.environ.get(
        "FETTLE_LEAN_STATE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state"),
    )

    # Run sniffers
    candidates: list[dict] = []

    def _budget_ok() -> bool:
        return (time.monotonic() - start_time) * 1000 < max_runtime_ms

    # LR001 — dependency manifest
    if _budget_ok() and is_manifest:
        candidates.extend(sniff_lr001(file_path, content, changed_lines, cwd, session_id))

    # LR002 — abstraction names (regex, all languages)
    if _budget_ok() and ext in IMPL_EXTENSIONS:
        candidates.extend(sniff_lr002(file_path, content, changed_lines, cwd, session_id))

    # LR003 — pass-through wrapper (Python AST)
    if _budget_ok() and tree is not None:
        candidates.extend(sniff_lr003(file_path, tree, changed_lines, cwd, session_id))

    # LR004 — single-method class (Python AST)
    if _budget_ok() and tree is not None:
        candidates.extend(sniff_lr004(file_path, tree, changed_lines, cwd, session_id))

    # LR008 — large addition
    if _budget_ok():
        candidates.extend(sniff_lr008(file_path, content, changed_lines, tree, cwd, session_id, thresholds))

    # LR012 — duplicate helper name (Python AST + git grep)
    if _budget_ok() and tree is not None:
        candidates.extend(sniff_lr012(file_path, tree, cwd, session_id))

    # Suppress candidates near fettle:lean: markers
    if candidates:
        candidates = _suppress_near_lean_markers(candidates, content)

    # Write state
    if candidates:
        with contextlib.suppress(OSError):
            _append_candidates(state_dir, session_id, candidates)

    sys.exit(0)


def run_check(ctx):
    """Dispatcher-compatible entry point. Surfaces findings when mode != 'silent'."""
    from dispatcher_types import CheckResult

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path:
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    session_id = ctx.session_id or "unknown"

    ext = os.path.splitext(file_path)[1].lower()
    is_manifest = _is_manifest(file_path)
    if ext not in IMPL_EXTENSIONS and not is_manifest:
        return CheckResult.allow()
    if _is_ignored(file_path):
        return CheckResult.allow()
    if not os.path.isfile(file_path):
        return CheckResult.allow()
    if os.path.getsize(file_path) > MAX_FILE_BYTES:
        return CheckResult.allow()

    lean_cfg = ctx.config.get("gates", {}).get("lean_review", {})
    if not lean_cfg.get("enabled", True):
        return CheckResult.allow()
    tier1_cfg = lean_cfg.get("tier1", {})
    if not tier1_cfg.get("enabled", True):
        return CheckResult.allow()
    thresholds = {**DEFAULT_THRESHOLDS, **tier1_cfg.get("thresholds", {})}
    max_runtime_ms = tier1_cfg.get("max_runtime_ms", 200)

    start_time = time.monotonic()

    try:
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError:
        return CheckResult.allow()

    changed_lines = _get_changed_lines(file_path, cwd)

    tree: ast.Module | None = None
    if ext == ".py":
        with contextlib.suppress(SyntaxError):
            tree = ast.parse(content)

    state_dir = os.environ.get(
        "FETTLE_LEAN_STATE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".state"),
    )

    candidates: list[dict] = []

    def _budget_ok() -> bool:
        return (time.monotonic() - start_time) * 1000 < max_runtime_ms

    if _budget_ok() and is_manifest:
        candidates.extend(sniff_lr001(file_path, content, changed_lines, cwd, session_id))
    if _budget_ok() and ext in IMPL_EXTENSIONS:
        candidates.extend(sniff_lr002(file_path, content, changed_lines, cwd, session_id))
    if _budget_ok() and tree is not None:
        candidates.extend(sniff_lr003(file_path, tree, changed_lines, cwd, session_id))
    if _budget_ok() and tree is not None:
        candidates.extend(sniff_lr004(file_path, tree, changed_lines, cwd, session_id))
    if _budget_ok():
        candidates.extend(sniff_lr008(file_path, content, changed_lines, tree, cwd, session_id, thresholds))
    if _budget_ok() and tree is not None:
        candidates.extend(sniff_lr012(file_path, tree, cwd, session_id))

    if candidates:
        candidates = _suppress_near_lean_markers(candidates, content)

    if candidates:
        with contextlib.suppress(OSError):
            _append_candidates(state_dir, session_id, candidates)

    # WP-A+B2: Surface findings when mode != "silent", dedup via AdvisoryDeduplicator
    mode = lean_cfg.get("mode", "silent")
    if mode == "silent" or not candidates:
        return CheckResult.allow()

    from advisory import Advisory, AdvisoryDeduplicator, Severity, format_advisories
    from config import state_dir as _state_dir

    advisory_cfg = ctx.config.get("gates", {}).get("advisory", {})
    dedup = AdvisoryDeduplicator(
        _state_dir(session_id),
        session_id,
        cooldown_s=float(advisory_cfg.get("cooldown_seconds", 300)),
        window_s=float(advisory_cfg.get("dedup_window_seconds", 900)),
    )

    MAX_FINDINGS = 3
    emitted: list[Advisory] = []
    for c in candidates:
        if len(emitted) >= MAX_FINDINGS:
            break
        adv = Advisory(
            rule_id=c.get("sniffer_id", "lean"),
            category="lean",
            severity=Severity.INFO,
            confidence=0.7,
            summary=c.get("message", "")[:120],
            recommended_action=f"{c.get('relative_path', '?')}:{c.get('line_start', '?')}",
            dedupe_key=c.get("dedupe_key", ""),
            provenance="lean_sniffers@0.7.0",
        )
        if dedup.should_emit(adv):
            dedup.record(adv)
            emitted.append(adv)

    if not emitted:
        return CheckResult.allow()

    text = format_advisories(emitted, max_total_bytes=int(advisory_cfg.get("max_total_bytes", 2048)))
    if len(candidates) > MAX_FINDINGS:
        text += f"\n  ... and {len(candidates) - MAX_FINDINGS} more (run /fettle:lean-debt)"

    return CheckResult.advisory(text, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": text,
    })


if __name__ == "__main__":
    main()
