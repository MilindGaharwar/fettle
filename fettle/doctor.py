#!/usr/bin/env python3
"""Fettle doctor — environment self-check.

Verifies the interpreter and every external tool Fettle's gates rely on, so a
misconfigured environment is diagnosed in one command instead of silently
degrading gate coverage.

Usage:
    scripts/run.sh doctor.py [--json]
"""

import argparse
import json
import shutil
import subprocess
import sys


def _version_of(binary: str, args: list[str] | None = None) -> str | None:
    try:
        out = subprocess.run(
            [binary] + (args or ["--version"]),
            capture_output=True,
            text=True,
            timeout=15,
        )
        first = (out.stdout or out.stderr).strip().splitlines()
        return first[0] if first else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _which(name: str) -> str | None:
    """Find a tool on PATH, including ~/.local/bin (uv tool install location)."""
    import os
    path = shutil.which(name)
    if path:
        return path
    local_bin = os.path.expanduser(f"~/.local/bin/{name}")
    if os.path.isfile(local_bin) and os.access(local_bin, os.X_OK):
        return local_bin
    return None


def check_environment() -> list[dict]:
    checks: list[dict] = []

    py_ok = sys.version_info >= (3, 11)
    checks.append({
        "name": "python",
        "required": True,
        "ok": py_ok,
        "detail": f"{sys.version.split()[0]} at {sys.executable}"
                  + ("" if py_ok else " — need >= 3.11 (set FETTLE_PYTHON)"),
    })

    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fettle.supply_chain import SYSTEM_TOOLS, system_install_hint

    tools = [
        ("ruff", True, "lint layer disabled without it"),
        ("semgrep", False, "LLM-antipattern layer skipped without it"),
        ("cargo", False, "Rust checks skipped without it"),
        ("shellcheck", False, "shell checks skipped without it"),
        ("claude", False, "cross-review/learn providers unavailable without it (v0.4.0)"),
    ]
    for name, required, consequence in tools:
        path = _which(name)
        version = _version_of(path) if path else None
        detail = f"{version} at {path}" if path else f"not on PATH — {consequence}"
        if not path and name in SYSTEM_TOOLS:
            # WP-16: the warn line carries the exact per-OS install command
            detail += f" — install: {system_install_hint(name)}"
        checks.append({
            "name": name,
            "required": required,
            "ok": bool(path),
            "detail": detail,
        })

    return checks


def check_mutation_readiness() -> list[dict]:
    """Report whether the pinned Python mutation engine is ready to preflight."""
    from fettle.config import load_config

    try:
        mutation = load_config(".").get("mutation", {})
    except (KeyError, OSError, TypeError, ValueError) as exc:
        return [{
            "name": "mutation", "required": False, "ok": False,
            "status": "unavailable",
            "detail": f"configuration unavailable ({exc}) — run: fettle config --validate",
        }]

    if not mutation.get("enabled", False):
        return [{
            "name": "mutation", "required": False, "ok": True,
            "status": "disabled",
            "detail": "disabled — enable [mutation] before running mutation preflight",
        }]

    path = _which("mutmut")
    if not path:
        return [{
            "name": "mutation", "required": False, "ok": False,
            "status": "unavailable",
            "detail": "mutmut==2.5.1 not on PATH — install: "
                      "python -m pip install -r requirements-mutation.txt",
        }]

    version = _version_of(path, ["version"])
    if version != "mutmut version 2.5.1":
        return [{
            "name": "mutation", "required": False, "ok": False,
            "status": "unsupported",
            "detail": f"{version or 'unknown version'} at {path}; expected 2.5.1 — install: "
                      "python -m pip install -r requirements-mutation.txt",
        }]

    return [{
        "name": "mutation", "required": False, "ok": True,
        "status": "ready",
        "detail": f"mutmut 2.5.1 at {path} — run: fettle mutation preflight",
    }]


def check_commit_guards() -> list[dict]:
    """Warn when the repo declares pre-commit hooks but they aren't wired (WP-141).

    A .pre-commit-config.yaml without `pre-commit install` means commit-time
    guards silently don't run — the exact gap behind the 2026-07-24 CI scrub
    failure. Non-required: repos without pre-commit config are untouched.
    """
    import os
    checks: list[dict] = []
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from fettle.paths import find_repo_root
        repo_root = find_repo_root()
    except Exception:  # noqa: BLE001 — doctor must never crash
        return checks
    if not repo_root or not (repo_root / ".pre-commit-config.yaml").is_file():
        return checks
    config_text = ""
    try:
        config_text = (repo_root / ".pre-commit-config.yaml").read_text()
    except OSError:
        pass
    for stage, hook_name in (("commit", "pre-commit"), ("push", "pre-push")):
        if stage == "push" and "pre-push" not in config_text:
            continue  # repo doesn't declare push-stage hooks
        # hooks live in the shared git dir — in a linked worktree .git is a file
        from fettle.worktrees import git_common_dir
        git_dir = git_common_dir(str(repo_root)) or (repo_root / ".git")
        hook = git_dir / "hooks" / hook_name
        try:
            wired = hook.is_file() and "pre-commit" in hook.read_text()
        except OSError:
            wired = False
        checks.append({
            "name": f"{stage}-guards",
            "required": False,
            "ok": wired,
            "detail": f"{hook_name} hooks wired" if wired
                      else f"declared but not installed — run: pre-commit install --hook-type {hook_name}",
        })
    return checks


def check_org_policy() -> list[dict]:
    """Warn when [extends] is configured but the org policy isn't cached (WP-144).

    Hooks resolve org policy cache-only (no network in the hook path), so a
    configured-but-unsynced policy silently doesn't apply until someone runs
    `fettle policy sync` — exactly the kind of gap doctor exists to surface.
    """
    import os
    import tomllib
    checks: list[dict] = []
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fettle.paths import find_repo_root
    from fettle.policy_remote import PolicyError, load_cached, parse_extends
    try:
        repo_root = find_repo_root()
        if not repo_root or not (repo_root / ".fettle.toml").is_file():
            return checks
        with open(repo_root / ".fettle.toml", "rb") as fh:
            raw_cfg = tomllib.load(fh)
        extends = parse_extends(raw_cfg)
        if extends is None:
            return checks
        cached = load_cached(extends) is not None
        checks.append({
            "name": "org-policy",
            "required": False,
            "ok": cached,
            "detail": "org policy cached (digest verified)" if cached
                      else "[extends] configured but policy not cached — run: fettle policy sync",
        })
    except (PolicyError, OSError, ValueError) as exc:  # ValueError covers TOMLDecodeError
        checks.append({
            "name": "org-policy", "required": False, "ok": False,
            "detail": f"[extends] invalid: {exc}",
        })
    return checks


def check_dispatch_health(days: int = 7) -> list[dict]:
    """Surface dispatcher fail-open events and audit-trace writability (Stage 0).

    Check crashes and budget kills are fail-open in-session by design; doctor
    is where that accumulated debt becomes visible and actionable.
    """
    import os
    import time
    from collections import Counter
    checks: list[dict] = []
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fettle.trace import _ROTATE_BYTES, _get_trace_path, probe_writable, read_tail

    ok, detail = probe_writable()
    checks.append({
        "name": "audit-trace",
        "required": False,
        "ok": ok,
        "detail": f"writable at {detail}" if ok
                  else f"NOT writable ({detail}) — hook decisions are not being recorded",
    })

    # Trace size (WP-6): rotation is opportunistic from log_decision; a file
    # far past the threshold means rotation is failing.
    try:
        size = os.path.getsize(_get_trace_path())
    except OSError:
        size = 0
    if size:
        size_ok = size <= 4 * _ROTATE_BYTES
        checks.append({
            "name": "trace-size",
            "required": False,
            "ok": size_ok,
            "detail": f"{size / (1024 * 1024):.1f} MB"
                      + ("" if size_ok else " — rotation appears broken; "
                         "run: python -c 'from fettle.trace import rotate_trace; rotate_trace()'"),
        })

    cutoff = time.time() - days * 86400
    by_status: Counter = Counter()
    failing: Counter = Counter()
    for entry in read_tail(max_bytes=262144):
        if entry.get("hook") != "dispatcher":
            continue
        if float(entry.get("ts", 0)) < cutoff:
            continue
        status = entry.get("status", "")
        by_status[status] += 1
        if status == "check_error":
            for finding in entry.get("findings", []):
                name = finding.get("check", "")
                if name:
                    failing[name] += 1

    if not by_status:
        checks.append({
            "name": "dispatch", "required": False, "ok": True,
            "detail": f"no fail-open events in the last {days} days",
        })
    else:
        parts = [f"{status}×{count}" for status, count in by_status.most_common()]
        if failing:
            worst = ", ".join(f"{name} ({count}×)" for name, count in failing.most_common(3))
            parts.append(f"failing checks: {worst}")
        checks.append({
            "name": "dispatch", "required": False, "ok": False,
            "detail": f"fail-open events in the last {days} days — " + "; ".join(parts),
        })
    return checks


def check_runner_governance() -> list[dict]:
    """Per-runner hook-parity probe (WP-157, E2 visibility).

    An installed agent CLI whose runtime carries no fettle hooks means any
    child spawned there runs ungoverned. Claude wires hooks via
    `fettle init`; the other runners have no hook surface yet, so their
    presence alone is worth a warning when [gates.agent_spawn] is on.
    """
    import os
    checks: list[dict] = []
    probes = {
        "claude": os.path.expanduser("~/.claude/settings.json"),
        "codex": None,
        "gemini": None,
        "opencode": None,
    }
    for name in sorted(probes):
        if not _which(name):
            continue
        settings = probes[name]
        if settings:
            wired = False
            try:
                with open(settings) as fh:
                    wired = "fettle" in fh.read()
            except OSError:
                wired = False
            detail = ("fettle hooks wired" if wired else
                      "installed but no fettle hooks — children spawned here "
                      "run ungoverned; run: fettle init")
        else:
            wired = False
            detail = ("installed; runtime has no hook surface — govern "
                      "children via `fettle spawn` (policy capsule)")
        checks.append({
            "name": f"runner:{name}",
            "required": False,
            "ok": wired,
            "detail": detail,
        })
    return checks


def check_config_valid() -> list[dict]:
    """Validate the project's .fettle.toml against the WP4 dependency model.

    A config that would misbehave (invalid per-gate mode, out-of-range value,
    broken cross-field dependency) must be surfaced — not silently act as
    something else.
    """
    import os
    import tomllib
    checks: list[dict] = []
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fettle.config_schema import validate_config
    from fettle.paths import find_repo_root
    try:
        repo_root = find_repo_root()
        if not repo_root or not (repo_root / ".fettle.toml").is_file():
            return checks
        with open(repo_root / ".fettle.toml", "rb") as fh:
            raw_cfg = tomllib.load(fh)
    except (OSError, ValueError) as exc:  # ValueError covers TOMLDecodeError
        checks.append({
            "name": "config", "required": False, "ok": False,
            "detail": f".fettle.toml unreadable: {exc}",
        })
        return checks
    errors, warnings = validate_config(raw_cfg)
    ok = not errors
    if ok and not warnings:
        detail = ".fettle.toml valid"
    else:
        parts = [f"{len(errors)} error(s)"] if errors else []
        if warnings:
            parts.append(f"{len(warnings)} warning(s)")
        first = (errors or warnings)[0]
        detail = (", ".join(parts)
                  + f" — first: {first} — run: fettle config --validate")
    checks.append({
        "name": "config", "required": False, "ok": ok, "detail": detail,
    })
    return checks


def check_mcp_trust() -> list[dict]:
    """Surface an active MCP_ALLOWLIST_PATH env override (WP-4c).

    An env-writable redirect of the trust root is invisible otherwise. When
    policy pins [gates.mcp_trust].allowlist_path the env var is inert; when
    it does not and the gate is enabled, an env override is a warning.
    """
    import os
    checks: list[dict] = []
    env_path = os.environ.get("MCP_ALLOWLIST_PATH")
    if not env_path:
        return checks
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from fettle.config import load_config
        mcp = load_config(".")["gates"]["mcp_trust"]
    except Exception:  # noqa: BLE001 — doctor must never crash
        return checks
    pinned = mcp.get("allowlist_path") or ""
    if pinned:
        ok, detail = True, (
            f"env MCP_ALLOWLIST_PATH={env_path} is inert — policy pins "
            f"allowlist_path={pinned}"
        )
    else:
        ok = not mcp.get("enabled", False)
        detail = (
            f"env MCP_ALLOWLIST_PATH={env_path} redirects the trust allowlist — "
            "pin [gates.mcp_trust].allowlist_path in policy to make it inert"
        )
    checks.append({"name": "mcp-allowlist", "required": False, "ok": ok, "detail": detail})
    return checks


def check_integrations() -> list[dict]:
    """Readiness probe for enabled integration adapters (WP-14b).

    Only enabled adapters are checked; an enabled-but-misconfigured adapter
    would otherwise fail silently at `fettle integrations` time.
    """
    import os
    checks: list[dict] = []
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from fettle.config import load_config
        from fettle.integration_base import IntegrationStatus
        from fettle.blackduck_adapter import BlackDuckAdapter
        from fettle.pact_adapter import PactAdapter
        from fettle.sonar_adapter import SonarQubeAdapter
        cfg = load_config(".")
    except Exception:  # noqa: BLE001 — doctor must never crash
        return checks
    adapters = {"sonarqube": SonarQubeAdapter(), "blackduck": BlackDuckAdapter(),
                "pact": PactAdapter()}
    for name, adapter in adapters.items():
        if not cfg.get("integrations", {}).get(name, {}).get("enabled"):
            continue
        status = adapter.is_available(cfg)
        checks.append({
            "name": f"integration-{name}",
            "required": False,
            "ok": status not in (IntegrationStatus.MISCONFIGURED,
                                 IntegrationStatus.UNAVAILABLE),
            "detail": f"{name} enabled — readiness: {status.value}",
        })
    return checks


def check_workflows() -> list[dict]:
    """Rendered workflows present and current per detected host (WP-18)."""
    import os
    checks: list[dict] = []
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from fettle.workflows import check_workflows as probe
        checks = probe()
    except Exception:  # noqa: BLE001 — doctor must never crash
        return []
    return checks


def apply_mechanical_fixes(checks: list[dict], *, run=None, which=None) -> list[str]:
    """Apply fixes that are purely mechanical — no judgement calls (v1.6 slice D).

    Currently: install declared-but-unwired pre-commit hooks, and install
    missing SYSTEM_TOOLS via brew/apt when one is available (WP-16).
    Anything needing a decision (config errors, org policy) is reported,
    never auto-fixed. Returns human-readable log lines.
    """
    import os
    import shutil
    import subprocess
    run = run or subprocess.run
    which = which or shutil.which
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fettle.supply_chain import SYSTEM_TOOLS, system_install_argv, system_install_hint

    log: list[str] = []
    unwired = [c for c in checks
               if c["name"] in ("commit-guards", "push-guards") and not c["ok"]]
    if unwired and not which("pre-commit"):
        log.append("cannot fix guard wiring: pre-commit binary not found "
                   "(pip install pre-commit)")
        unwired = []
    for c in unwired:
        hook_type = "pre-commit" if c["name"] == "commit-guards" else "pre-push"
        proc = run(["pre-commit", "install", "--hook-type", hook_type],
                   capture_output=True, text=True)
        if proc.returncode == 0:
            log.append(f"fixed: installed {hook_type} hooks")
        else:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            log.append(f"fix failed for {hook_type}: {err[0] if err else 'unknown error'}")

    # SYSTEM_TOOLS tier (WP-16): best-effort brew/apt install, re-probed
    # after — the check dict is only flipped when the tool actually appears.
    for c in (c for c in checks if c["name"] in SYSTEM_TOOLS and not c["ok"]):
        tool = c["name"]
        argv = system_install_argv(tool, which=which)
        if argv is None:
            log.append(f"cannot fix {tool}: {system_install_hint(tool, which=which)}")
            continue
        proc = run(argv, capture_output=True, text=True, timeout=600)
        path = which(tool)
        if proc.returncode == 0 and path:
            c["ok"] = True
            c["detail"] = f"installed at {path} via {' '.join(a for a in argv if a != '-n')}"
            log.append(f"fixed: installed {tool}")
        else:
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            log.append(f"fix failed for {tool}: {err[0] if err else 'unknown error'}")
    return log


def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle environment self-check")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fix", action="store_true",
                        help="Apply mechanical fixes only (wire declared pre-commit hooks; "
                             "install missing system tools via brew/apt)")
    parser.add_argument("--verify-hashes", action="store_true",
                        help="Verify pinned tools' installed files against wheel RECORD hashes (WP-147)")
    args = parser.parse_args()

    checks = (check_environment() + check_mutation_readiness()
              + check_commit_guards() + check_org_policy()
              + check_config_valid() + check_dispatch_health()
              + check_runner_governance() + check_mcp_trust()
              + check_integrations() + check_workflows())
    if args.verify_hashes:
        from fettle.supply_chain import verify_tool_hashes
        checks += verify_tool_hashes()

    fix_log: list[str] = []
    if args.fix:
        fix_log = apply_mechanical_fixes(checks)
        if any(line.startswith("fixed:") for line in fix_log):
            # re-verify what we touched instead of claiming success
            others = [c for c in checks
                      if c["name"] not in ("commit-guards", "push-guards")]
            checks = others + check_commit_guards()
    required_failures = [c for c in checks if c["required"] and not c["ok"]]

    if args.json:
        print(json.dumps({"checks": checks, "healthy": not required_failures,
                          "fixes": fix_log}, indent=2))
    else:
        for line in fix_log:
            print(f"[fix ] {line}")
        for c in checks:
            mark = "ok " if c["ok"] else ("FAIL" if c["required"] else "warn")
            print(f"[{mark}] {c['name']:<10} {c['detail']}")
        print()
        print("healthy" if not required_failures else "UNHEALTHY — required tools missing")

    return 1 if required_failures else 0


if __name__ == "__main__":
    sys.exit(main())
