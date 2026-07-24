#!/usr/bin/env python3
"""Fettle CLI — quality enforcement from the command line.

Commands:
    fettle check [--all] [--changed] [--json] [--fix] [--baseline]
    fettle config [--print-effective]
    fettle explain [--last]
    fettle baseline create|update
    fettle doctor
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root (clone mode)
def _version() -> str:
    """Fettle version — pyproject.toml in clone mode, package metadata when installed."""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib
            with open(pyproject, "rb") as fh:
                return tomllib.load(fh)["project"]["version"]
        except (OSError, KeyError, ValueError):
            pass
    try:
        from importlib.metadata import version
        return version("finefettle")
    except Exception:  # noqa: BLE001 — version display must never crash the CLI
        return "unknown"


def _finding_key(f: dict) -> str:
    """Stable identity for a finding across scan and baseline formats."""
    return f"{f.get('file', '')}:{f.get('line', 0)}:{f.get('code') or f.get('rule', '')}"


def _baseline_keys(path: Path) -> set[str]:
    """Load finding keys from a baseline file (wrapper dict or bare list)."""
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    items = data.get("findings", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return set()
    return {_finding_key(f) for f in items if isinstance(f, dict)}


def cmd_check(args: argparse.Namespace) -> None:
    """Run quality checks (CI-friendly, no hook context needed).

    Exit codes: 0 = clean (no error-severity findings), 1 = errors found,
    2 = usage or environment error. Identical for text and --json output.
    """
    from fettle.config import load_config
    from fettle.paths import find_repo_root

    if args.all and args.changed:
        print("Error: --all and --changed are mutually exclusive", file=sys.stderr)
        sys.exit(2)

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)

    config = load_config(str(repo_root))
    scan_root = Path(args.root).resolve() if args.root else repo_root

    if getattr(args, "boundaries", False):
        from fettle.boundary_scan import scan_repo
        findings = scan_repo(str(repo_root), config)
        if args.json:
            print(json.dumps([f.to_dict() for f in findings], indent=2))
        else:
            for f in findings:
                print(f"  [{f.severity.value.upper()}] {f.path}:{f.line} {f.code} — {f.message}")
            print(f"\n{len(findings)} boundary finding(s)." if findings else "✓ No boundary issues found.")
        sys.exit(1 if findings else 0)

    # --changed: restrict the scan to Python files changed in git.
    changed_files: list[str] | None = None
    if args.changed:
        from fettle.changeset import get_changed_files
        scan_root = repo_root  # changed paths are repo-root-relative
        changed_files = [
            str(repo_root / c.path)
            for c in get_changed_files(str(repo_root))
            if c.path.endswith(".py") and (repo_root / c.path).is_file()
        ]
        if not changed_files:
            if args.json:
                print(json.dumps({"findings": [], "file_count": 0}, indent=2))
            else:
                print("✓ No changed Python files to check.")
            sys.exit(0)

    # --fix: apply safe ruff autofixes before scanning.
    if args.fix:
        from fettle.autofix import fix_file
        if changed_files is not None:
            fix_targets = changed_files
        else:
            fix_targets = [
                str(p) for p in scan_root.rglob("*.py")
                if "__pycache__" not in str(p) and ".venv" not in str(p)
            ]
        fix_results = [fix_file(t, config) for t in fix_targets]
        fix_errors = [r for r in fix_results if r.get("status") == "error"]
        if not args.json:
            print(f"Autofix ran on {len(fix_targets)} file(s)"
                  + (f", {len(fix_errors)} error(s)." if fix_errors else "."))

    from fettle.quality_scan import scan_project
    results = scan_project(str(scan_root), config, json_output=args.json,
                           files=changed_files)
    findings = results.get("findings", [])

    # --baseline: report only findings absent from the committed baseline.
    if args.baseline:
        baseline_path = repo_root / ".fettle-baseline.json"
        if not baseline_path.exists():
            print("Error: no .fettle-baseline.json found — run `fettle baseline create` first.",
                  file=sys.stderr)
            sys.exit(2)
        known = _baseline_keys(baseline_path)
        findings = [f for f in findings if _finding_key(f) not in known]
        results["findings"] = findings

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not findings:
            print("✓ No issues found.")
        else:
            for f in findings:
                sev = f.get("severity", "info").upper()
                loc = f"{f.get('file', '')}:{f.get('line', '')}" if f.get("file") else ""
                print(f"  [{sev}] {loc} {f.get('code', '')} — {f.get('message', '')}")
            print(f"\n{len(findings)} finding(s).")
    sys.exit(1 if any(f.get("severity") == "error" for f in findings) else 0)


def cmd_ci(args: argparse.Namespace) -> None:
    """Reproduce CI locally, or scaffold the workflow with `ci init`."""
    from fettle import ci as ci_mod
    if getattr(args, "ci_action", None) == "init":
        out = ci_mod.init_ci(args.root, dry_run=getattr(args, "dry_run", False))
        if getattr(args, "dry_run", False):
            print(out)
        else:
            print("Wrote .github/workflows/fettle.yml and seeded .fettle.toml [boundary].")
        return
    result = ci_mod.run_ci(args.root)
    rc = ci_mod._print_result(result)
    sys.exit(rc)


def cmd_config(args: argparse.Namespace) -> None:
    """Show or validate configuration."""
    from fettle.paths import find_repo_root
    from fettle.policy_layers import discover_layers, load_config_layered

    repo_root = find_repo_root()
    project_root = repo_root or __import__("pathlib").Path.cwd()

    if getattr(args, "validate", False):
        import tomllib
        from fettle.config_schema import validate_config
        config_path = project_root / ".fettle.toml"
        if not config_path.is_file():
            print("No .fettle.toml found — defaults apply, nothing to validate.")
            sys.exit(0)
        try:
            with open(config_path, "rb") as fh:
                user_cfg = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f"✗ {config_path}: not parseable TOML — {exc}", file=sys.stderr)
            sys.exit(1)
        errors, warnings = validate_config(user_cfg)
        for w in warnings:
            print(f"  [WARN] {w}")
        for e in errors:
            print(f"  [ERROR] {e}")
        if errors:
            print(f"\n✗ {config_path}: {len(errors)} error(s), {len(warnings)} warning(s)")
            sys.exit(1)
        print(f"\n✓ {config_path}: valid"
              + (f" ({len(warnings)} warning(s))" if warnings else ""))
        sys.exit(0)

    layers = discover_layers(project_root)
    config = load_config_layered(str(project_root))

    if args.print_effective:
        print("── Effective Fettle Configuration ──\n")
        print(f"  Repo root: {repo_root or '(not found)'}")
        print(f"  Config file: {repo_root / '.fettle.toml' if repo_root and (repo_root / '.fettle.toml').exists() else '(defaults only)'}")
        print()
        print(json.dumps(config, indent=2, default=str))
    elif args.explain:
        from fettle.policy_layers import _print_explain
        _print_explain(layers)
    else:
        print("Use --print-effective, --explain, or --validate to inspect config.")


def cmd_explain(args: argparse.Namespace) -> None:
    """Explain the last hook decision."""

    state_dir = os.environ.get(
        "XDG_STATE_HOME", os.path.expanduser("~/.local/state")
    )
    trace_dir = os.path.join(state_dir, "fettle")

    if not os.path.isdir(trace_dir):
        print("No Fettle state found. Run a hook first.")
        return

    trace_file = os.path.join(trace_dir, "trace.jsonl")
    if not os.path.isfile(trace_file):
        print("No trace file found.")
        return

    with open(trace_file) as f:
        lines = f.readlines()

    if not lines:
        print("Trace is empty.")
        return

    last_entries = []
    for line in reversed(lines[-20:]):
        try:
            entry = json.loads(line.strip())
            last_entries.append(entry)
        except json.JSONDecodeError:
            continue

    if not last_entries:
        print("No parseable trace entries.")
        return

    print("── Last Fettle Decision(s) ──\n")
    for entry in last_entries[:5]:
        hook = entry.get("hook", "?")
        status = entry.get("status", "?")
        tool = entry.get("tool", "?")
        file_path = entry.get("file", "")
        findings = entry.get("findings", [])
        ts = entry.get("timestamp", "")

        print(f"  [{ts}] {hook} → {status}")
        if file_path:
            print(f"    File: {file_path}")
        if tool:
            print(f"    Tool: {tool}")
        if findings:
            for f in findings[:3]:
                print(f"    • {f.get('code', '')} {f.get('message', '')}")
        print()


def cmd_baseline(args: argparse.Namespace) -> None:
    """Manage violation baselines."""
    from fettle.config import load_config
    from fettle.paths import find_repo_root

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    baseline_path = repo_root / ".fettle-baseline.json"

    if args.action == "create":
        config = load_config(str(repo_root))
        from fettle.quality_scan import scan_project
        results = scan_project(str(repo_root), config, json_output=True)
        findings = results.get("findings", [])

        baseline = {
            "version": 1,
            "created": __import__("datetime").datetime.now().isoformat(),
            "findings_count": len(findings),
            "findings": findings,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2))
        print(f"✓ Baseline created: {len(findings)} finding(s) at {baseline_path}")

    elif args.action == "update":
        if not baseline_path.exists():
            print("No baseline found. Run `fettle baseline create` first.")
            sys.exit(1)
        config = load_config(str(repo_root))
        from fettle.quality_scan import scan_project
        results = scan_project(str(repo_root), config, json_output=True)
        findings = results.get("findings", [])

        baseline = {
            "version": 1,
            "updated": __import__("datetime").datetime.now().isoformat(),
            "findings_count": len(findings),
            "findings": findings,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2))
        print(f"✓ Baseline updated: {len(findings)} finding(s)")


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run environment self-check."""
    import subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run([sys.executable, os.path.join(script_dir, "doctor.py")], check=False)


def cmd_init(args: argparse.Namespace) -> None:
    """One-command setup: repo config, agent hooks, commit-time guards (WP-141)."""
    from fettle.paths import find_repo_root
    from fettle.init_cmd import print_steps, run_init

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    steps, exit_code = run_init(repo_root, tools=args.install_tools, dry_run=args.dry_run)
    if args.json:
        print(json.dumps([s.to_dict() for s in steps], indent=2))
    else:
        print_steps(steps)
    sys.exit(exit_code)


def cmd_policy(args: argparse.Namespace) -> None:
    """Sync or inspect the digest-pinned org policy (WP-144)."""
    import tomllib
    from fettle.paths import find_repo_root
    from fettle.policy_remote import (
        PolicyError, fetch_and_cache, load_cached, parse_extends,
    )

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(2)
    config_path = repo_root / ".fettle.toml"
    raw_cfg = {}
    if config_path.is_file():
        with open(config_path, "rb") as fh:
            raw_cfg = tomllib.load(fh)
    try:
        extends = parse_extends(raw_cfg)
    except PolicyError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        sys.exit(1)
    if extends is None:
        print("No [extends] in .fettle.toml — this repo uses local policy only.")
        sys.exit(0)

    if args.policy_action == "status":
        cached = load_cached(extends)
        print(f"  url:    {extends['url']}")
        print(f"  sha256: {extends['sha256']}")
        print(f"  cache:  {'✓ present (digest verified)' if cached is not None else '✗ not cached — run: fettle policy sync'}")
        sys.exit(0 if cached is not None else 1)

    # sync (default)
    try:
        policy = fetch_and_cache(extends)
    except PolicyError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        sys.exit(1)
    top_keys = ", ".join(sorted(policy.keys())) or "(empty)"
    print(f"✓ org policy synced and digest-verified ({extends['sha256'][:16]}…)")
    print(f"  sections: {top_keys}")
    sys.exit(0)


def cmd_bench(args: argparse.Namespace) -> None:
    """Run the noise benchmark over pinned corpora (WP-118)."""
    from fettle.bench import load_budgets, run_bench

    corpora = {}
    for spec in args.corpus:
        name, _, root = spec.partition("=")
        if not root:
            print(f"Error: --corpus must be name=path, got '{spec}'", file=sys.stderr)
            sys.exit(2)
        corpora[name] = root
    budgets = load_budgets(args.budgets)
    result = run_bench(
        corpora, budgets,
        update_budgets_path=args.budgets if args.update_budgets else None,
    )
    for name, m in result.measurements.items():
        print(f"{name}: {m.kloc:.2f} KLOC")
        for rule, count in sorted(m.findings_per_rule.items()):
            marker = " (unbudgeted)" if rule in result.unbudgeted.get(name, []) else ""
            print(f"  {rule}: {count} findings, {m.rate_per_kloc(rule):.2f}/KLOC{marker}")
    for v in result.violations:
        print(f"BUDGET EXCEEDED: {v}", file=sys.stderr)
    if args.update_budgets:
        print(f"\u2713 Budgets written to {args.budgets}")
    sys.exit(0 if result.passed else 1)


def cmd_ratchet(args: argparse.Namespace) -> None:
    """Evidence-based rule promotion/demotion (WP-119)."""
    from fettle.ratchet import cmd_ratchet as _cmd_ratchet
    _cmd_ratchet(args)


def cmd_suppressions(args: argparse.Namespace) -> None:
    """Manage suppressions with expiry and owner (WP-120)."""
    from fettle.suppressions_v3 import cmd_suppressions as _cmd_suppressions
    _cmd_suppressions(args)


def cmd_lsp(args: argparse.Namespace) -> None:
    """Start the LSP server (WP-125)."""
    from fettle.lsp_server import main as lsp_main
    lsp_main()


def main() -> None:
    parser = argparse.ArgumentParser(prog="fettle", description="Quality enforcement CLI")
    parser.add_argument("--version", action="version", version=f"fettle {_version()}")
    subparsers = parser.add_subparsers(dest="command")

    p_check = subparsers.add_parser("check", help="Run quality checks")
    p_check.add_argument("--all", action="store_true", help="Check all files")
    p_check.add_argument("--changed", action="store_true", help="Check only changed files")
    p_check.add_argument("--json", action="store_true", help="JSON output")
    p_check.add_argument("--fix", action="store_true", help="Apply safe autofixes")
    p_check.add_argument("--baseline", action="store_true", help="Only report new violations")
    p_check.add_argument("--boundaries", action="store_true", help="Scan for secrets, out-of-project paths, and repo-forbidden strings")
    p_check.add_argument("--root", help="File or directory to scan (default: repository root)")

    p_config = subparsers.add_parser("config", help="Show configuration")
    p_config.add_argument("--print-effective", action="store_true", help="Show merged effective config")
    p_config.add_argument("--explain", action="store_true", help="Show the source of each effective value")
    p_config.add_argument("--validate", action="store_true", help="Validate .fettle.toml against the config schema")

    p_explain = subparsers.add_parser("explain", help="Explain last hook decision")
    p_explain.add_argument("--last", action="store_true", default=True)

    p_baseline = subparsers.add_parser("baseline", help="Manage violation baselines")
    p_baseline.add_argument("action", choices=["create", "update"], help="Baseline action")

    subparsers.add_parser("doctor", help="Environment self-check")

    p_init = subparsers.add_parser("init", help="One-command setup: repo config, agent hooks, commit-time guards")
    p_init.add_argument("--install-tools", action="store_true",
                        help="Install pinned ruff/semgrep/pre-commit via uv")
    p_init.add_argument("--dry-run", action="store_true", help="Show what would be done")
    p_init.add_argument("--json", action="store_true", help="JSON output")

    p_policy = subparsers.add_parser("policy", help="Sync or inspect the digest-pinned org policy ([extends])")
    policy_sub = p_policy.add_subparsers(dest="policy_action")
    policy_sub.add_parser("sync", help="Fetch, digest-verify, and cache the org policy")
    policy_sub.add_parser("status", help="Show pin and cache state")
    p_policy.set_defaults(policy_action="sync")

    p_bench = subparsers.add_parser("bench", help="Noise benchmark: findings-per-KLOC vs committed budgets")
    p_bench.add_argument("--corpus", action="append", required=True, metavar="NAME=PATH",
                         help="Named corpus directory (repeatable)")
    p_bench.add_argument("--budgets", default="benchmarks/budgets.json",
                         help="Budget file (default: benchmarks/budgets.json)")
    p_bench.add_argument("--update-budgets", action="store_true",
                         help="Write measured rates as the new budgets")

    p_ci = subparsers.add_parser("ci", help="Run the enforced gate sequence (boundary + quality + plans)")
    p_ci.add_argument("--root", default=".")
    ci_sub = p_ci.add_subparsers(dest="ci_action")
    p_ci_init = ci_sub.add_parser("init", help="Write .github/workflows/fettle.yml")
    p_ci_init.add_argument("--dry-run", action="store_true")
    p_ci_init.add_argument("--root", default=".")

    # WP-119: Ratchet workflow
    p_ratchet = subparsers.add_parser("ratchet", help="Evidence-based rule promotion/demotion")
    ratchet_sub = p_ratchet.add_subparsers(dest="ratchet_action")
    ratchet_sub.add_parser("status", help="Show per-rule mode and evidence")
    p_ratchet_promote = ratchet_sub.add_parser("promote", help="Promote rule advisory -> enforce")
    p_ratchet_promote.add_argument("rule_id", help="Rule ID to promote")
    p_ratchet_demote = ratchet_sub.add_parser("demote", help="Demote rule enforce -> advisory")
    p_ratchet_demote.add_argument("rule_id", help="Rule ID to demote")
    p_ratchet_demote.add_argument("--reason", required=True, help="Reason for demotion")
    ratchet_sub.add_parser("sync", help="Re-aggregate evidence from trace")

    # WP-120: Suppressions with expiry and owner
    p_supp = subparsers.add_parser("suppressions", help="Manage suppressions with expiry and owner")
    supp_sub = p_supp.add_subparsers(dest="supp_action")
    supp_sub.add_parser("list", help="Show all suppressions")
    p_supp_add = supp_sub.add_parser("add", help="Add a suppression")
    p_supp_add.add_argument("--rule", required=True, help="Rule ID")
    p_supp_add.add_argument("--path", default="", help="File path pattern")
    p_supp_add.add_argument("--reason", required=True, help="Suppression reason")
    p_supp_add.add_argument("--owner", default="", help="Owner handle (@user)")
    p_supp_add.add_argument("--until", default="", help="Expiry date (YYYY-MM-DD)")
    p_supp_rm = supp_sub.add_parser("remove", help="Remove a suppression by index")
    p_supp_rm.add_argument("index", type=int, help="0-based suppression index")
    supp_sub.add_parser("report", help="Suppressions report (expired, ownerless)")
    supp_sub.add_parser("expired", help="Show expired suppressions (now findings)")

    subparsers.add_parser("lsp", help="Start the LSP server for editor integration (WP-125)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "check": cmd_check,
        "config": cmd_config,
        "explain": cmd_explain,
        "baseline": cmd_baseline,
        "doctor": cmd_doctor,
        "init": cmd_init,
        "policy": cmd_policy,
        "bench": cmd_bench,
        "ci": cmd_ci,
        "ratchet": cmd_ratchet,
        "suppressions": cmd_suppressions,
        "lsp": cmd_lsp,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
