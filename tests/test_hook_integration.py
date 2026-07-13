"""Tests for scripts/hook_integration.py — WP-76: Hook integration for tiered checks."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from hook_integration import (
    determine_tier_for_event,
    format_hook_output,
)
from finding import CheckFinding, FindingSeverity, CheckResult


def test_post_edit_triggers_fast_check():
    tier = determine_tier_for_event("PostToolUse", tool="Edit", command=None)
    assert tier == "fast"


def test_git_commit_triggers_changed_check():
    tier = determine_tier_for_event("PostToolUse", tool="Bash", command="git commit -m 'fix'")
    assert tier == "changed"


def test_git_push_triggers_changed_check():
    tier = determine_tier_for_event("PostToolUse", tool="Bash", command="git push origin main")
    assert tier == "changed"


def test_stop_hook_reports_deferred_results():
    tier = determine_tier_for_event("Stop", tool=None, command=None)
    assert tier == "deferred"


def test_fast_check_within_15s_budget():
    tier = determine_tier_for_event("PostToolUse", tool="Write", command=None)
    assert tier == "fast"


def test_blocking_finding_blocks_commit():
    findings = [CheckFinding(
        checker="ruff", severity=FindingSeverity.ERROR,
        file="x.py", line=1, message="error", blocking=True,
    )]
    result = CheckResult(findings=findings)
    output = format_hook_output(result, tier="changed", hook_event="PostToolUse")
    assert output.get("decision") == "block"


def test_advisory_finding_does_not_block():
    findings = [CheckFinding(
        checker="ruff", severity=FindingSeverity.WARNING,
        file="x.py", line=1, message="warning",
    )]
    result = CheckResult(findings=findings)
    output = format_hook_output(result, tier="fast", hook_event="PostToolUse")
    assert output.get("decision") != "block"


def test_secret_finding_always_blocks():
    findings = [CheckFinding(
        checker="gitleaks", severity=FindingSeverity.ERROR,
        file="config.py", line=1, message="secret detected", blocking=True,
    )]
    result = CheckResult(findings=findings)
    output = format_hook_output(result, tier="fast", hook_event="PostToolUse")
    assert output.get("decision") == "block"
