"""Fettle policy engine — central decision point for what runs, blocks, or warns.

The policy engine answers:
- Should this hook run checks on this file?
- Which checkers should run?
- Are failures blocking or warnings?
- Should autofix be attempted?

Configuration in .fettle.toml:
    [policy]
    pre_tool_use = "protect"         # protect | check | skip
    post_tool_use = "check_changed"  # check_changed | check_all | skip
    stop = "cross_file"              # cross_file | skip

    [policy.failures]
    ruff = "block"          # block | warn | skip
    semgrep = "block"       # block | warn | skip
    missing_tool = "warn"   # block | warn | skip
    config_error = "block"  # block | warn | skip
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paths import is_excluded, is_test_file


@dataclass
class PolicyDecision:
    """Result of a policy evaluation."""
    should_check: bool = True
    checkers: list[str] = field(default_factory=lambda: ["ruff", "semgrep"])
    block_on_error: bool = False
    autofix: bool = False
    reason: str = ""


def evaluate_policy(
    hook_event: str,
    file_path: str,
    config: dict[str, Any],
) -> PolicyDecision:
    """Evaluate policy for a given hook event and file.

    Returns a PolicyDecision indicating what to do.
    """
    gates = config.get("gates", {})
    lint_gate = gates.get("lint", {})
    policy_cfg = config.get("policy", {})

    if not lint_gate.get("enabled", True):
        return PolicyDecision(should_check=False, reason="lint gate disabled")

    mode = str(lint_gate.get("mode", "advisory"))

    exclude_patterns = config.get("paths", {}).get("exclude", [])
    if is_excluded(file_path, exclude_patterns):
        return PolicyDecision(should_check=False, reason="file excluded by pattern")

    if is_test_file(file_path) and not policy_cfg.get("check_tests", False):
        return PolicyDecision(should_check=False, reason="test file (policy.check_tests=false)")

    checkers = []
    ext = Path(file_path).suffix

    if ext in {".py", ".pyi"}:
        checkers = ["ruff", "semgrep"]
    elif ext in {".ts", ".tsx", ".js", ".jsx"}:
        checkers = ["semgrep"]
    elif ext in {".rs"}:
        checkers = ["cargo"]
    elif ext in {".sh"}:
        checkers = ["shellcheck"]
    else:
        return PolicyDecision(should_check=False, reason=f"no checkers for {ext}")

    block_on_error = mode in ("soft", "enforce")

    autofix = policy_cfg.get("autofix", False) and mode != "enforce"

    return PolicyDecision(
        should_check=True,
        checkers=checkers,
        block_on_error=block_on_error,
        autofix=autofix,
        reason=f"mode={mode}, checkers={checkers}",
    )


def should_block(finding_severity: str, config: dict[str, Any]) -> bool:
    """Determine if a finding at the given severity should block."""
    mode = config.get("gates", {}).get("lint", {}).get("mode", "advisory")
    return mode in ("soft", "enforce") and finding_severity == "error"
