#!/usr/bin/env python3
"""Fettle post-edit check for Go — semgrep antipatterns + golangci-lint.

Dispatcher-routed (extensions={".go"}). Semgrep runs the built-in
rules/go-antipatterns.yml plus any project rules from .fettle/rules/
(see project_rules.py). golangci-lint runs only when the anchor root
contains a go.mod — single files outside a module cannot compile.
"""

import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
from fettle.project_rules import extra_rule_configs
from fettle.result import Finding, Severity
from fettle.semgrep_util import anchored_semgrep_args

_GOLANGCI_LINE = re.compile(r"^(?P<path>.+?\.go):(?P<line>\d+)(?::\d+)?:\s*(?P<msg>.+)$")


def _resolve_tool(name: str) -> str | None:
    local = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which(name)


def _semgrep_findings(file_path: str, cfg: dict, plugin_root: str, cwd: str) -> list[Finding]:
    semgrep_bin = _resolve_tool("semgrep")
    rules_file = os.path.join(plugin_root, "rules", "go-antipatterns.yml")
    if not semgrep_bin or not os.path.isfile(rules_file):
        return []
    anchor_args, anchor_cwd = anchored_semgrep_args(file_path, cwd=cwd)
    config_args = ["--config", rules_file]
    for extra in extra_rule_configs(cfg, anchor_cwd):
        config_args.extend(["--config", extra])
    try:
        proc = subprocess.run(
            [semgrep_bin, *config_args, "--json", *anchor_args],
            capture_output=True, text=True, timeout=15, cwd=anchor_cwd,
        )
        raw = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return []
    findings = []
    for item in raw.get("results", []):
        if not isinstance(item, dict):
            continue
        start_loc = item.get("start", {})
        line_no = start_loc.get("line", 0) if isinstance(start_loc, dict) else 0
        extra = item.get("extra", {})
        msg = extra.get("message", "") if isinstance(extra, dict) else ""
        sev = Severity.ERROR if "error" in str(extra.get("severity", "")).lower() else Severity.WARNING
        findings.append(Finding(
            tool="semgrep", severity=sev, path=file_path,
            line=line_no, code=item.get("check_id", ""), message=msg,
        ))
    return findings


def _golangci_findings(file_path: str, cwd: str) -> list[Finding]:
    golangci_bin = _resolve_tool("golangci-lint")
    if not golangci_bin:
        return []
    anchor_args, anchor_cwd = anchored_semgrep_args(file_path, cwd=cwd)
    if not os.path.isfile(os.path.join(anchor_cwd, "go.mod")):
        return []
    target = anchor_args[-1]
    try:
        proc = subprocess.run(
            [golangci_bin, "run", "--out-format=line-number", target],
            capture_output=True, text=True, timeout=30, cwd=anchor_cwd,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    findings = []
    for line in proc.stdout.splitlines():
        m = _GOLANGCI_LINE.match(line.strip())
        if m:
            findings.append(Finding(
                tool="golangci-lint", severity=Severity.WARNING,
                path=m.group("path"), line=int(m.group("line")),
                code="golangci-lint", message=m.group("msg"),
            ))
    return findings


def run_check(ctx):
    """Dispatcher entry point for .go edits. Returns CheckResult."""
    from fettle.dispatcher_types import CheckResult

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path.endswith(".go"):
        return CheckResult.allow()
    if not os.path.isfile(file_path):
        return CheckResult.allow()
    lint_cfg = ctx.config.get("gates", {}).get("lint", {})
    if not lint_cfg.get("enabled", True):
        return CheckResult.allow()

    cwd = str(ctx.cwd)
    plugin_root = str(ctx.plugin_root)
    findings = _semgrep_findings(file_path, ctx.config, plugin_root, cwd)
    findings += _golangci_findings(file_path, cwd)
    if not findings:
        return CheckResult.allow()

    text = "\n".join(
        f"[{f.severity.value.upper()}] {f.path}:{f.line} {f.code} — {f.message}"
        for f in findings
    )
    output = {"hookEventName": "PostToolUse", "additionalContext": text}
    mode = str(lint_cfg.get("mode", "advisory"))
    if mode == "enforce" and any(f.severity == Severity.ERROR for f in findings):
        return CheckResult.block(text, hook_specific_output=output)
    return CheckResult.advisory(text, hook_specific_output=output)
