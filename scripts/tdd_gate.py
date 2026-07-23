"""WP-I — TDD Phase Enforcement.

PreToolUse + PostToolUse check that detects whether test files are
edited before corresponding implementation files. Advisory only in v0.9.

Known limitations (by design):
- Checks ORDERING only (test file edited before implementation file).
- Does NOT verify the red phase (test failing before implementation).
- Does NOT verify the green phase (test passing after implementation).
- Red/green verification would require parsing test runner output,
  which is unreliable across frameworks. The ordering check is the
  enforceable proxy; true red-green-refactor discipline is process
  guidance (see discipline-testing skill).
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_EXEMPT_PATTERNS_DEFAULT = [
    "docs/**", "**/*.md", "**/*.toml", "**/*.yaml", "**/*.yml",
    "**/*.json", "**/*.cfg", "**/*.ini", "**/*.txt",
    "tests/fixtures/**", "**/__pycache__/**", "**/node_modules/**",
    "**/.venv/**", "**/dist/**",
]


def _is_exempt(rel_path: str, exempt_patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_path, pat) for pat in exempt_patterns)


def _is_test_file(rel_path: str, test_patterns: list[str]) -> bool:
    basename = os.path.basename(rel_path)
    if basename.startswith("test_") or basename.endswith("_test.py"):
        return True
    if ".test." in basename or ".spec." in basename:
        return True
    if "/tests/" in rel_path or "/test/" in rel_path or rel_path.startswith("tests/"):
        return True
    return any(fnmatch.fnmatch(rel_path, pat) for pat in test_patterns)


def _derive_module_key(rel_path: str, impl_roots: list[str]) -> str:
    """Derive a module key from a file path for matching test↔impl."""
    parts = rel_path.replace("\\", "/").split("/")
    basename = os.path.splitext(parts[-1])[0]
    basename = re.sub(r"^test_", "", basename)
    basename = re.sub(r"_test$", "", basename)

    for root in impl_roots:
        if parts[0] == root and len(parts) > 1:
            return "/".join(parts[1:-1] + [basename])

    if parts[0] in ("tests", "test") and len(parts) > 1:
        return "/".join(parts[1:-1] + [basename])

    return "/".join(parts[:-1] + [basename]) if len(parts) > 1 else basename


def _get_state_path(session_id: str) -> Path:
    from config import state_dir
    return state_dir(session_id) / "tdd_events.jsonl"


def _load_evidence(state_path: Path) -> set[str]:
    """Load module keys that have test-first evidence."""
    evidence: set[str] = set()
    try:
        if state_path.is_file():
            for line in state_path.read_text().splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("event") == "test_edit":
                        module = entry.get("module", "")
                        if module:
                            evidence.add(module)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return evidence


def _record_event(state_path: Path, event_type: str, path: str, module: str) -> None:
    record = json.dumps({
        "ts": time.time(),
        "event": event_type,
        "path": path,
        "module": module,
    }, separators=(",", ":"))
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(state_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (record + "\n").encode())
        finally:
            os.close(fd)
    except OSError:
        logger.debug("fettle: tdd_gate write failed", exc_info=True)


def _check_preexisting_test(module_key: str, cwd: str, test_patterns: list[str]) -> bool:
    """Check if a test file exists on disk for this module."""
    candidates = [
        f"tests/test_{module_key.split('/')[-1]}.py",
        f"tests/{'/'.join(module_key.split('/')[:-1])}/test_{module_key.split('/')[-1]}.py",
    ]
    return any(os.path.isfile(os.path.join(cwd, candidate)) for candidate in candidates)


def run_check(ctx):
    """Dispatcher-compatible entry point for TDD enforcement."""
    from dispatcher_types import CheckResult

    cfg = ctx.config.get("gates", {}).get("tdd", {})
    if not cfg.get("enabled", False):
        return CheckResult.allow()

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path:
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    session_id = ctx.session_id or "unknown"
    event = ctx.input.hook_event_name

    exempt_paths = cfg.get("exempt_paths", _EXEMPT_PATTERNS_DEFAULT)
    test_patterns = cfg.get("test_patterns", ["tests/test_*.py", "tests/**/test_*.py"])
    impl_roots = cfg.get("implementation_roots", ["src/"])
    accept_preexisting = cfg.get("accept_preexisting_tests", True)

    rel_path = os.path.relpath(file_path, cwd) if os.path.isabs(file_path) else file_path

    if _is_exempt(rel_path, exempt_paths):
        return CheckResult.allow()

    module_key = _derive_module_key(rel_path, [r.rstrip("/") for r in impl_roots])
    state_path = _get_state_path(session_id)
    is_test = _is_test_file(rel_path, test_patterns)

    # PostToolUse: record successful edits
    if event == "PostToolUse":
        if is_test:
            _record_event(state_path, "test_edit", rel_path, module_key)
        else:
            _record_event(state_path, "impl_edit", rel_path, module_key)
        return CheckResult.allow()

    # PreToolUse: check for test-first evidence
    if event == "PreToolUse" and not is_test:
        evidence = _load_evidence(state_path)
        if module_key in evidence:
            return CheckResult.allow()

        if accept_preexisting and _check_preexisting_test(module_key, cwd, test_patterns):
            return CheckResult.allow()

        # Check path_mappings
        path_mappings = cfg.get("path_mappings", {})
        if rel_path in path_mappings:
            mapped_test = path_mappings[rel_path]
            if os.path.isfile(os.path.join(cwd, mapped_test)):
                return CheckResult.allow()

        mode = cfg.get("mode", "advisory")
        expected_test = f"tests/test_{module_key.split('/')[-1]}.py"
        msg = (
            f"TDD: editing {os.path.basename(file_path)} without test-first evidence. "
            f"Expected: edit {expected_test} before implementation."
        )

        if mode == "strict":
            return CheckResult.block(msg, hook_specific_output={
                "hookEventName": event,
                "additionalContext": msg,
            })
        return CheckResult.advisory(msg, hook_specific_output={
            "hookEventName": event,
            "additionalContext": msg,
        })

    return CheckResult.allow()
