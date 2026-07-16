#!/usr/bin/env python3
"""Fettle PostToolUse hook — runs semgrep TS/JS antipattern rules on edited frontend files."""

import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config
from project_rules import extra_rule_configs
from result import Finding, Severity, make_pass, make_tool_error, make_violation
from semgrep_util import anchored_semgrep_args
from trace import log_decision

TS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx"}


def _resolve_tool(name: str) -> str | None:
    local = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local
    return shutil.which(name)


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, EOFError):
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd = data.get("cwd", ".")
    session_id = data.get("session_id", "unknown")

    if not any(file_path.endswith(ext) for ext in TS_EXTENSIONS):
        sys.exit(0)

    if not os.path.isfile(file_path):
        sys.exit(0)

    cfg = load_config(cwd)
    if not cfg["gates"]["lint"]["enabled"]:
        sys.exit(0)

    PLUGIN_ROOT = os.environ.get(
        "CLAUDE_PLUGIN_ROOT",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    semgrep_bin = _resolve_tool("semgrep")
    if not semgrep_bin:
        result = make_tool_error("semgrep", "not found — TS/JS antipattern checks skipped")
        log_decision(hook="PostToolUse", status="tool_error", tool="semgrep", file=file_path, session_id=session_id)
        result.emit_and_exit(hook_event="PostToolUse")

    rules_file = os.path.join(PLUGIN_ROOT, "rules", "ts-antipatterns.yml")
    if not os.path.isfile(rules_file):
        sys.exit(0)

    start = time.monotonic_ns()
    findings: list[Finding] = []

    try:
        anchor_args, anchor_cwd = anchored_semgrep_args(file_path, cwd=cwd)
        config_args = ["--config", rules_file]
        for extra in extra_rule_configs(cfg, anchor_cwd):
            config_args.extend(["--config", extra])
        proc = subprocess.run(
            [semgrep_bin, *config_args, "--json", *anchor_args],
            capture_output=True, text=True, timeout=15, cwd=anchor_cwd,
        )
        if proc.stdout.strip():
            raw = json.loads(proc.stdout)
            for item in raw.get("results", []):
                if not isinstance(item, dict):
                    continue
                start_loc = item.get("start", {})
                line_no = start_loc.get("line", 0) if isinstance(start_loc, dict) else 0
                extra = item.get("extra", {})
                msg = extra.get("message", "") if isinstance(extra, dict) else ""
                rule_id = item.get("check_id", "")

                sev = Severity.ERROR if "error" in str(extra.get("severity", "")).lower() else Severity.WARNING
                findings.append(Finding(
                    tool="semgrep",
                    severity=sev,
                    path=file_path,
                    line=line_no,
                    code=rule_id,
                    message=msg,
                ))
    except subprocess.TimeoutExpired:
        result = make_tool_error("semgrep", "timed out (15s)")
        result.emit_and_exit(hook_event="PostToolUse")
    except (json.JSONDecodeError, OSError) as e:
        result = make_tool_error("semgrep", str(e))
        result.emit_and_exit(hook_event="PostToolUse")

    duration_ms = (time.monotonic_ns() - start) / 1_000_000

    if findings:
        result = make_violation(findings, tool_name="semgrep")
        log_decision(
            hook="PostToolUse", status="violation", tool="semgrep",
            file=file_path, findings=[f.to_dict() for f in findings],
            duration_ms=duration_ms, session_id=session_id,
        )
    else:
        result = make_pass()
        log_decision(hook="PostToolUse", status="pass", tool="semgrep", file=file_path, duration_ms=duration_ms, session_id=session_id)

    mode = str(cfg["gates"]["lint"]["mode"])
    result.emit_and_exit(hook_event="PostToolUse", block=(mode == "enforce"))


def run_check(ctx):
    """Dispatcher-compatible entry point. Returns CheckResult."""
    from dispatcher_types import CheckResult

    file_path = ctx.tool_input.get("file_path", "")
    if not any(file_path.endswith(ext) for ext in TS_EXTENSIONS):
        return CheckResult.allow()
    if not os.path.isfile(file_path):
        return CheckResult.allow()
    if not ctx.config.get("gates", {}).get("lint", {}).get("enabled", True):
        return CheckResult.allow()

    plugin_root = str(ctx.plugin_root)
    semgrep_bin = _resolve_tool("semgrep")
    if not semgrep_bin:
        return CheckResult.allow()

    rules_file = os.path.join(plugin_root, "rules", "ts-antipatterns.yml")
    if not os.path.isfile(rules_file):
        return CheckResult.allow()

    findings: list[Finding] = []
    try:
        anchor_args, anchor_cwd = anchored_semgrep_args(file_path, cwd=str(ctx.cwd))
        config_args = ["--config", rules_file]
        for extra in extra_rule_configs(ctx.config, anchor_cwd):
            config_args.extend(["--config", extra])
        proc = subprocess.run(
            [semgrep_bin, *config_args, "--json", *anchor_args],
            capture_output=True, text=True, timeout=15, cwd=anchor_cwd,
        )
        if proc.stdout.strip():
            raw = json.loads(proc.stdout)
            for item in raw.get("results", []):
                if not isinstance(item, dict):
                    continue
                start_loc = item.get("start", {})
                line_no = start_loc.get("line", 0) if isinstance(start_loc, dict) else 0
                extra = item.get("extra", {})
                msg = extra.get("message", "") if isinstance(extra, dict) else ""
                rule_id = item.get("check_id", "")
                sev = Severity.ERROR if "error" in str(extra.get("severity", "")).lower() else Severity.WARNING
                findings.append(Finding(tool="semgrep", severity=sev, path=file_path, line=line_no, code=rule_id, message=msg))
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return CheckResult.allow()

    if not findings:
        return CheckResult.allow()

    lines = []
    for f in findings:
        lines.append(f"[{f.severity.value.upper()}] {f.path}:{f.line} {f.code} — {f.message}")
    text = "\n".join(lines)

    mode = str(ctx.config.get("gates", {}).get("lint", {}).get("mode", "advisory"))
    if mode == "enforce" and any(f.severity == Severity.ERROR for f in findings):
        return CheckResult.block(text, hook_specific_output={"hookEventName": "PostToolUse", "additionalContext": text})

    return CheckResult.advisory(text, hook_specific_output={"hookEventName": "PostToolUse", "additionalContext": text})


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError):
        sys.exit(0)
