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
import tempfile
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

    # --junit: write JUnit XML for enterprise CI dashboards (WP-145).
    if getattr(args, "junit", None):
        from fettle.junit import findings_to_junit
        Path(args.junit).write_text(findings_to_junit(findings))
        if not args.json:
            print(f"JUnit report written to {args.junit}")

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
    """Reproduce CI locally, scaffold the workflow, or verify the remote verdict."""
    from fettle import ci as ci_mod
    action = getattr(args, "ci_action", None)
    if action == "init":
        out = ci_mod.init_ci(args.root, dry_run=getattr(args, "dry_run", False))
        if getattr(args, "dry_run", False):
            print(out)
        else:
            print("Wrote .github/workflows/fettle.yml and seeded .fettle.toml [boundary].")
        return
    if action in ("status", "wait"):
        from fettle.ci_gate import run_ci_status
        from fettle.config import load_config
        from fettle.paths import find_repo_root
        root = find_repo_root()
        if root is None:
            print("✗ not inside a git repository", file=sys.stderr)
            sys.exit(2)
        stamp = run_ci_status(
            str(root), load_config(str(root)),
            wait=(action == "wait"), sha=getattr(args, "sha", None),
            progress=(
                None if getattr(args, "json", False)
                else lambda line: print(line, file=sys.stderr, flush=True)
            ),
        )
        if getattr(args, "json", False):
            print(json.dumps(stamp, indent=2))
        else:
            mark = "✓" if stamp["ok"] else "✗"
            print(f"{mark} CI {stamp['overall']} — {stamp['sha'][:12]}")
            for r in stamp["runs"]:
                print(f"  {r['name']}: {r['conclusion'] or r['status']}")
            if stamp.get("error"):
                print(f"  {stamp['error']}")
            if stamp.get("reproduce"):
                print(f"  Reproduce locally: {stamp['reproduce']}")
        if stamp["ok"]:
            sys.exit(0)
        sys.exit(2 if stamp["overall"] in ("error", "no-runs") else 1)
    result = ci_mod.run_ci(args.root)
    rc = ci_mod._print_result(result)
    sys.exit(rc)


def cmd_config(args: argparse.Namespace) -> None:
    """Show or validate configuration."""
    from fettle.config import resolve_with_provenance
    from fettle.paths import find_repo_root

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

    # WP-20: one resolver for inspection and runtime — this output is
    # exactly what gates load (org/team/remote/repo/env/capsule included;
    # directory overrides apply per-file only).
    config, layers = resolve_with_provenance(str(project_root))

    if args.print_effective:
        print("── Effective Fettle Configuration ──\n")
        print(f"  Repo root: {repo_root or '(not found)'}")
        sources = [f"{lyr.name} ({lyr.source})" for lyr in layers if lyr.name != "defaults"]
        print(f"  Sources: {'; '.join(sources) if sources else '(defaults only)'}")
        print()
        print(json.dumps(config, indent=2, default=str))
    elif args.explain:
        from fettle.policy_layers import _print_explain, discover_directory_layers
        _print_explain(layers)
        dir_layers = discover_directory_layers(project_root)
        if dir_layers:
            print("\npath-scoped layers (apply to files under their directory only):")
            for lyr in dir_layers:
                print(f"  {lyr.name}: {lyr.source}")
    else:
        print("Use --print-effective, --explain, or --validate to inspect config.")


def cmd_explain(args: argparse.Namespace) -> None:
    """Explain the last hook decision."""
    from fettle.explain import explain_entry
    from fettle.trace import get_recent_decisions

    entries = get_recent_decisions(limit=args.last)
    if not entries:
        print("No Fettle decisions recorded yet.")
        return
    if not args.json:
        print(f"── Last {len(entries)} Fettle Decision(s) ──\n")
    for entry in reversed(entries):
        print(explain_entry(entry, detailed=args.detailed, json_output=args.json))


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


def _mutation_exit(report: dict) -> int:
    if report.get("status") in {"tool_error", "unknown", "not_configured", "stale"}:
        return 2
    return 0 if report.get("passed", False) or report.get("status") == "not_applicable" else 1


def _read_mutation_report(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read mutation report {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"mutation report {path} must be a JSON object")
    return value


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _render_mutation(report: dict) -> str:
    status = report.get("status", "unknown")
    lines = [f"Mutation status: {status}"]
    if report.get("message"):
        lines.append(str(report["message"]))
    if report.get("score") is not None:
        lines.append(f"Score: {report['score']}%")
    records = report.get("records", report.get("survivor_preview", []))
    for record in records[:20] if isinstance(records, list) else []:
        lines.append(
            f"{record.get('file', '?')}:{record.get('line', '?')} "
            f"{record.get('before', '?')} -> {record.get('after', '?')} "
            f"[{record.get('disposition', record.get('state', 'unknown'))}]"
        )
        if record.get("rerun_command"):
            lines.append(f"  Rerun: {record['rerun_command']}")
    return "\n".join(lines) + "\n"


def cmd_mutation(args: argparse.Namespace) -> None:
    """Run, inspect, and establish strict mutation evidence."""
    from fettle.config import load_config
    from fettle.mutation_baseline import (
        baseline_digest,
        compare_report,
        establish_baseline,
        load_baseline,
        load_classifications,
        save_baseline,
    )
    from fettle.paths import find_repo_root

    root = find_repo_root()
    if root is None:
        result = {"status": "not_configured", "passed": False, "message": "not inside a Fettle repository"}
        print(json.dumps(result, indent=2) if args.json else _render_mutation(result), end="\n" if args.json else "")
        sys.exit(2)
    root = Path(root)
    action = args.mutation_action
    try:
        if action == "show":
            report = _read_mutation_report(Path(args.report))
            record = next(
                (item for item in report.get("non_killed", []) if item.get("fingerprint") == args.fingerprint),
                None,
            )
            if record is None:
                raise ValueError(f"mutation fingerprint {args.fingerprint} was not found")
            result = {"status": "completed", "passed": True, "records": [record]}
        elif action == "baseline":
            reports = [_read_mutation_report(Path(path)) for path in args.reports]
            mutation = load_config(str(root))["mutation"]
            previous = load_baseline(root / ".fettle" / "mutation-baseline.json")
            baseline = establish_baseline(
                reports, args.run_id, floor=args.floor,
                target=mutation.get("score_target", args.floor),
                previous=previous,
            )
            result = {"status": "completed", "passed": True, "baseline": baseline}
            if args.baseline_action == "establish":
                digest = save_baseline(
                    root / ".fettle" / "mutation-baseline.json", baseline,
                    expected_digest=baseline_digest(previous) if previous is not None else None,
                )
                result["baseline_digest"] = digest
        else:
            report_path = Path(args.report) if getattr(args, "report", None) else None
            if action == "run":
                mutation = load_config(str(root))["mutation"]
                if not mutation.get("enabled", False):
                    result = {
                        "status": "not_configured", "passed": False,
                        "message": "Mutation testing is disabled; set [mutation] enabled = true",
                    }
                else:
                    from fettle.mutation_test import run_mutation_test
                    result = run_mutation_test(str(root), {
                        **mutation, "all": args.all,
                        "base": args.base or mutation.get("base", "origin/main"),
                        "shard_index": args.shard_index, "shard_count": args.shard_count,
                        "manifest": args.manifest,
                        "timeout_s": mutation.get("full_timeout_s") if args.all else mutation.get("timeout_s"),
                    })
            else:
                if report_path is None:
                    raise ValueError("mutation status requires --report")
                result = _read_mutation_report(report_path)
            baseline = load_baseline(root / ".fettle" / "mutation-baseline.json")
            if baseline is not None and result.get("status") == "completed" and result.get("schema_version") == "2":
                from fettle.overrides import load_override_ledger
                ledger = load_override_ledger(root)
                if ledger.invalid:
                    raise ValueError("mutation override ledger is invalid: " + "; ".join(ledger.invalid))
                classifications = load_classifications(
                    root / ".fettle" / "mutation-classifications.json", root=root,
                )
                comparison = compare_report(
                    result, baseline, overrides=ledger.records, classifications=classifications,
                )
                enforce_survivors = load_config(str(root))["mutation"].get("mode") == "enforce"
                result = {
                    **result,
                    "comparison": comparison,
                    "passed": result.get("passed", False) and (comparison["passed"] or not enforce_survivors),
                }
        if getattr(args, "output", None):
            _write_json_atomic(Path(args.output), result)
    except ValueError as exc:
        result = {"status": "unknown", "passed": False, "message": str(exc)}

    print(json.dumps(result, indent=2) if args.json else _render_mutation(result), end="\n" if args.json else "")
    sys.exit(_mutation_exit(result))


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run environment self-check."""
    import subprocess
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = [sys.executable, os.path.join(script_dir, "doctor.py")]
    if getattr(args, "verify_hashes", False):
        cmd.append("--verify-hashes")
    if getattr(args, "fix", False):
        cmd.append("--fix")
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:  # WP-10 (audit M-06): propagate failure to CI
        sys.exit(proc.returncode)


# WP-14b: integration adapters wired to the CLI (audit C14).
_INTEGRATIONS = {
    "sonarqube": ("fettle.sonar_adapter", "SonarQube"),
    "blackduck": ("fettle.blackduck_adapter", "Black Duck"),
    "pact": ("fettle.pact_adapter", "Pact"),
}


def cmd_integrations(args: argparse.Namespace) -> None:
    """Run external tool adapters: named one, or all enabled ones.

    Exit contract (matches `fettle check`): 0 pass, 1 findings/failure,
    2 misconfigured or unavailable environment.
    """
    from importlib import import_module

    from fettle.config import load_config
    from fettle.integration_base import IntegrationStatus, format_integration_report

    cwd = os.getcwd()
    cfg = load_config(cwd)
    names = [args.name] if args.name else list(_INTEGRATIONS)

    results = []  # (name, label, IntegrationReport)
    for name in names:
        module_name, label = _INTEGRATIONS[name]
        report = import_module(module_name).run_command(cfg, cwd)
        if args.name is None and report.status == IntegrationStatus.NOT_ENABLED:
            continue  # "run all" means all *enabled*
        results.append((name, label, report))

    exit_code = 0
    for _, _, report in results:
        if report.status in (IntegrationStatus.MISCONFIGURED,
                             IntegrationStatus.UNAVAILABLE,
                             IntegrationStatus.NOT_ENABLED):
            exit_code = 2
        elif report.status == IntegrationStatus.FAIL:
            exit_code = max(exit_code, 1)

    if args.json:
        payload = {
            "integrations": [
                {
                    "name": name,
                    "status": report.status.value,
                    "summary": report.summary,
                    "findings": [
                        {"severity": f.severity, "message": f.message,
                         "file": f.file, "line": f.line, "code": f.code}
                        for f in report.findings
                    ],
                }
                for name, _, report in results
            ],
        }
        print(json.dumps(payload, indent=2))
    elif not results:
        print("No integrations enabled — set [integrations.<name>].enabled "
              "in .fettle.toml (sonarqube, blackduck, pact).")
    else:
        for _, label, report in results:
            print(format_integration_report(report, label))

    sys.exit(exit_code)


def cmd_workflows(args: argparse.Namespace) -> None:
    """Install/list the guided workflows in each agent's native command
    format (WP-18). Exit 0 unless a write failed; action/skipped steps are
    informational, matching `fettle init`.
    """
    from fettle.paths import find_repo_root
    from fettle.workflows import AGENTS, install, list_rows

    action = getattr(args, "workflows_action", "list") or "list"
    if action == "list":
        rows = list_rows()
        if getattr(args, "json", False):
            print(json.dumps({"workflows": rows}, indent=2))
        else:
            print("── fettle workflows ──\n")
            for row in rows:
                print(f"  {row['name']:<16} {row['description']}")
            print("\nInvocation: Claude/Gemini /fettle:<name> · VS Code/OpenCode "
                  "/fettle-<name> · Codex /prompts:fettle-<name>")
            print("Install:    fettle workflows install [--agent …] [--project|--user]")
        sys.exit(0)

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    scope = "user" if getattr(args, "user", False) else "project"
    agent = getattr(args, "agent", "all")
    agents = list(AGENTS) if agent == "all" else [agent]
    steps = install(agents, scope, Path(repo_root),
                    dry_run=getattr(args, "dry_run", False),
                    detect=(agent == "all"))
    if getattr(args, "json", False):
        print(json.dumps({"steps": [s.to_dict() for s in steps]}, indent=2))
    else:
        from fettle.init_cmd import print_steps
        print_steps(steps)
    sys.exit(1 if any(s.status == "error" for s in steps) else 0)


def cmd_init(args: argparse.Namespace) -> None:
    """One-command setup: repo config, agent hooks, commit-time guards (WP-141).

    --interactive / --profile (v1.6 slice B) generate an annotated
    .fettle.toml from your answers before the wiring steps run.
    """
    from fettle.paths import find_repo_root
    from fettle.init_cmd import print_steps, run_init

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)

    profile = getattr(args, "profile", None)
    interactive = getattr(args, "interactive", False)
    if interactive or profile:
        from fettle.init_interview import (
            PROFILES, detect_stack, render_config, run_interview, write_config,
        )
        root = Path(repo_root)
        if interactive:
            if not sys.stdin.isatty():
                print("Error: --interactive needs a terminal; use --profile "
                      f"{{{'|'.join(PROFILES)}}} instead", file=sys.stderr)
                sys.exit(2)
            answers = run_interview(root)
        else:
            answers = dict(PROFILES[profile])
        content = render_config(answers, detect_stack(root))
        ok, msg = write_config(root, content, force=getattr(args, "force", False))
        if not ok:
            print(f"Error: {msg}", file=sys.stderr)
            sys.exit(2)
        print(f"✓ wrote {msg}")

    steps, exit_code = run_init(repo_root, tools=args.install_tools, dry_run=args.dry_run)
    if args.json:
        print(json.dumps([s.to_dict() for s in steps], indent=2))
    else:
        print_steps(steps)
    sys.exit(exit_code)


def cmd_report(args: argparse.Namespace) -> None:
    """Effectiveness metrics from the audit trail; --org rolls up per repo (WP-145)."""
    from fettle.report import compute_effectiveness, compute_org_report

    if getattr(args, "lineage", False):
        from fettle.lineage_report import compute_lineage, render_lineage_tree
        data = compute_lineage(args.days)
        print(json.dumps(data, indent=2) if args.json else render_lineage_tree(data))
        sys.exit(1 if "error" in data else 0)
    if getattr(args, "compliance", False):
        from fettle.compliance import compute_compliance_report, render_compliance_table
        data = compute_compliance_report(args.days)
        print(json.dumps(data, indent=2) if args.json else render_compliance_table(data))
        return
    data = compute_org_report(args.days) if args.org else compute_effectiveness(args.days)
    if not args.org and "error" not in data:
        from fettle.paths import find_repo_root
        from fettle.report import compute_override_inventory
        repo_root = find_repo_root()
        if repo_root:
            data["override_inventory"] = compute_override_inventory(repo_root)
    if args.json:
        print(json.dumps(data, indent=2))
        sys.exit(1 if "error" in data else 0)
    if "error" in data:
        print(data["error"])
        sys.exit(1)
    if args.org:
        print(f"── Fettle Org Report ({data['period_days']}d, "
              f"{data['total_repos']} repo(s), {data['total_decisions']} decisions) ──\n")
        for repo, s in data["repos"].items():
            print(f"  {repo}")
            print(f"    decisions: {s['decisions']}  violations: {s['violations']} "
                  f"({s['violation_rate_pct']}%)  blocked: {s['blocked']}  "
                  f"tool errors: {s['tool_errors']}")
            for code, count in s["top_codes"]:
                print(f"      {code}: {count}")
    else:
        print(f"── Fettle Effectiveness ({data['period_days']}d) ──\n")
        print(f"  decisions: {data['total_decisions']}  "
              f"pass: {data['pass_rate_pct']}%  violations: {data['violation_rate_pct']}%  "
              f"tool errors: {data['tool_error_rate_pct']}%")
        for code, count in data["top_violations"]:
            print(f"    {code}: {count}")
    sys.exit(0)


def cmd_telemetry(args: argparse.Namespace) -> None:
    """Opt-in anonymous counters (WP-148): status / show / send."""
    from fettle.telemetry import compute_payload, send_payload, telemetry_settings

    action = getattr(args, "telemetry_action", "status") or "status"
    settings = telemetry_settings()

    if action == "status":
        state = "ENABLED (org policy)" if settings["enabled"] else "off (default)"
        print(f"telemetry: {state}")
        if settings["endpoint"]:
            print(f"endpoint:  {settings['endpoint']}")
        if settings["note"]:
            print(f"note:      {settings['note']}")
        print("payload:   anonymous counters only — inspect with `fettle telemetry show`")
        sys.exit(0)

    if action == "show":
        print(json.dumps(compute_payload(args.days), indent=2))
        sys.exit(0)

    # send
    if not settings["enabled"]:
        print("telemetry is off — only the org's digest-pinned central policy "
              "([extends]) can enable it; nothing was sent", file=sys.stderr)
        if settings["note"]:
            print(f"note: {settings['note']}", file=sys.stderr)
        sys.exit(1)
    payload = compute_payload(args.days)
    if send_payload(payload, settings["endpoint"]):
        print(f"sent {payload['counters']['decisions']} decision counters "
              f"({args.days}d) to {settings['endpoint']}")
        sys.exit(0)
    print(f"send failed ({settings['endpoint']}) — telemetry never blocks; "
          "try again later", file=sys.stderr)
    sys.exit(1)


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


def cmd_overrides(args: argparse.Namespace) -> None:
    """Inspect and validate revision-bound override records."""
    from fettle.overrides import load_override_ledger, summarize_ledger
    from fettle.paths import find_repo_root

    project_root = find_repo_root()
    if not project_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(2)
    summary = summarize_ledger(load_override_ledger(project_root))
    if args.json:
        print(json.dumps(summary, indent=2))
    elif not any(
        summary[key] for key in ("active_count", "pending_count", "expired_count", "invalid_count")
    ):
        print("No recorded overrides. Enforcing decisions remain unchanged.")
    else:
        print("── Recorded Overrides ──")
        for label in ("active", "pending", "expired"):
            for record in summary[label]:
                print(
                    f"  {label.upper():<7} {record['override_id']}  {record['check_id']}  "
                    f"{record['scope']}  expires {record['expiry']}"
                )
        for error in summary["invalid"]:
            print(f"  INVALID {error}")
    if args.overrides_action == "validate" and (
        summary["pending_count"] or summary["expired_count"] or summary["invalid_count"]
    ):
        sys.exit(1)
    sys.exit(0)


def cmd_verification(args: argparse.Namespace) -> None:
    """Run committed seeded-defect conformance manifests."""
    from fettle.verification_fixtures import BUILTIN_RUNNERS, evaluate_manifest, load_manifests

    root = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "verification"
    promoted = {"ci.verdict"}
    loaded = load_manifests(root, promoted_check_ids=promoted)
    selected = [
        manifest for manifest in loaded.manifests
        if not args.check_id or manifest.check_id == args.check_id
    ]
    errors = list(loaded.errors)
    if args.check_id and not selected:
        errors.append(f"check '{args.check_id}' has no seeded-defect manifest")
    results = [
        {
            "check_id": manifest.check_id,
            "status": result.status,
            "errors": list(result.errors),
            "rerun_command": manifest.rerun_command,
        }
        for manifest in selected
        for result in (evaluate_manifest(manifest, BUILTIN_RUNNERS),)
    ]
    payload = {"schema_version": "1", "results": results, "errors": errors}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for result in results:
            mark = "PASS" if result["status"] == "pass" else result["status"].upper()
            print(f"  {mark:<10} {result['check_id']}")
            for error in result["errors"]:
                print(f"    {error}")
        for error in errors:
            print(f"  INVALID    {error}")
    failed = errors or any(result["status"] != "pass" for result in results)
    sys.exit(1 if failed else 0)


def cmd_lsp(args: argparse.Namespace) -> None:
    """Start the LSP server (WP-125)."""
    from fettle.lsp_server import main as lsp_main
    lsp_main()


def cmd_spec(args: argparse.Namespace) -> None:
    """Living specifications: lint and list (Stage 3, Pillar 1).

    Exit codes: 0 = clean, 1 = error findings, 2 = usage/environment error.
    """
    from fettle.paths import find_repo_root
    from fettle.spec_model import discover_specs, lint_specs, scenario_coverage

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    root = str(repo_root)

    if args.spec_action == "coverage":
        report = scenario_coverage(root)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for s in report["specs"]:
                print(f"  {s['id']} ({s['status']}): {s['covered']}/{s['total']} scenarios covered")
                for row in s["scenarios"]:
                    mark = "\u2713" if row["covered"] else "\u2717"
                    by = f" \u2190 {', '.join(row['covered_by'])}" if row["covered_by"] else ""
                    print(f"    {mark} {row['id']}. {row['title']}{by}")
            for u in report["unknown_traces"]:
                print(f"  [WARNING] {u['test']}: marker '{u['marker']}' \u2014 {u['reason']}")
            t = report["totals"]
            print(f"\n{t['covered']}/{t['scenarios']} scenarios covered ({t['coverage_percent']}%).")
        sys.exit(0)

    if args.spec_action == "list":
        rows = []
        for spec, findings in discover_specs(root):
            if spec is None:
                continue
            errors = sum(1 for f in findings if f["severity"] == "ERROR")
            rows.append({
                "id": spec.spec_id, "path": spec.path, "status": spec.status,
                "requirements": len(spec.requirements),
                "scenarios": len(spec.scenarios), "lint_errors": errors,
            })
        if args.json:
            print(json.dumps(rows, indent=2))
        elif not rows:
            print("No specs found (markdown files with 'fettle-spec' frontmatter).")
        else:
            for r in rows:
                print(f"  {r['id']:<24} {r['status']:<11} "
                      f"{r['requirements']}R/{r['scenarios']}S  {r['path']}"
                      + (f"  ({r['lint_errors']} lint error(s))" if r["lint_errors"] else ""))
        sys.exit(0)

    # default action: lint
    findings = lint_specs(root)
    errors = [f for f in findings if f["severity"] == "ERROR"]
    if args.json:
        print(json.dumps({"findings": findings, "error_count": len(errors)}, indent=2))
    else:
        for f in findings:
            print(f"  [{f['severity']}] {f['file']}:{f['line']} — {f['message']}")
            print(f"      fix: {f['fix']}")
        print(f"\n{len(findings)} finding(s)." if findings else "\u2713 All specs valid.")
    sys.exit(1 if errors else 0)


def cmd_spawn(args: argparse.Namespace) -> None:
    """Launch a child agent under the current effective policy (WP-157).

    Exit codes: 0 = child ran and exited 0, 1 = child failed or spawn
    refused, 2 = usage/environment error.
    """
    from fettle.spawn import spawn_agent

    result = spawn_agent(
        args.runner, args.task, os.getcwd(),
        worktree_item=args.worktree, timeout_s=args.timeout,
        role=getattr(args, "role", "") or "",
    )
    if result.error:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(2 if "not inside a repository" in result.error else 1)
    print(f"✓ capsule {result.capsule_digest} → {result.runner} in {result.child_cwd}")
    if result.lineage:
        print(f"  lineage: {' → '.join(result.lineage)} → {result.capsule_digest}")
    run = result.run
    if run.error:
        print(f"Child agent failed: {run.error}", file=sys.stderr)
        sys.exit(1)
    if run.transcript.strip():
        print(run.transcript.strip())
    print(f"✓ child exited {run.exit_code} in {run.duration_s:.1f}s")
    sys.exit(0 if run.exit_code == 0 else 1)


def cmd_topology(args: argparse.Namespace) -> None:
    """Multi-agent topology intelligence (WP-159..161)."""
    action = getattr(args, "topology_action", "advise") or "advise"
    root = os.getcwd()
    if action == "advise":
        from fettle.topology import advise, render_advice
        data = advise(root, days=args.days)
        print(json.dumps(data, indent=2) if args.json else render_advice(data))
        sys.exit(0)
    if action == "apply":
        from fettle.topology_apply import apply_topology, render_apply
        manifest = apply_topology(root, runner_name=args.runner, days=args.days)
        print(json.dumps(manifest, indent=2) if args.json else render_apply(manifest))
        sys.exit(1 if manifest["errors"] else 0)
    if action == "status":
        from fettle.topology_apply import render_status, topology_status
        data = topology_status(root, max_blocks=args.max_blocks)
        print(json.dumps(data, indent=2) if args.json else render_status(data))
        sys.exit(1 if "error" in data else 0)
    if action == "revoke":
        from fettle.topology_apply import revoke_item
        err = revoke_item(root, args.item_id)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        print(f"✓ revoked {args.item_id}")
        sys.exit(0)
    if action == "report":
        from fettle.topology_apply import render_topology_report, topology_report
        data = topology_report(root)
        print(json.dumps(data, indent=2) if args.json else render_topology_report(data))
        sys.exit(1 if "error" in data else 0)
    print(f"unknown topology action: {action}", file=sys.stderr)
    sys.exit(2)


def cmd_brief(args: argparse.Namespace) -> None:
    """One poll for orchestrators (v1.6 slice C). Read-only, offline."""
    from fettle.brief import compute_brief, render_brief
    from fettle.paths import find_repo_root

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)",
              file=sys.stderr)
        sys.exit(2)
    data = compute_brief(Path(repo_root), days=args.days)
    print(json.dumps(data, indent=2) if args.json else render_brief(data))
    sys.exit(0)


def cmd_learn(args: argparse.Namespace) -> None:
    """Delegate to the learn module — docs promise `fettle learn` (WP-163)."""
    from fettle import learn
    argv = ["fettle learn"]
    if args.incident:
        argv += ["--incident", args.incident]
    if args.file:
        argv += ["--file", args.file]
    if args.list:
        argv.append("--list")
    if args.auto_save:
        argv.append("--auto-save")
    if args.from_trace:
        argv.append("--from-trace")
    argv += ["--days", str(args.days)]
    sys.argv = argv
    learn.main()
    sys.exit(0)


def cmd_plan(args: argparse.Namespace) -> None:
    """Session plans — checklist created before work starts (v1.6 slice A)."""
    from fettle.paths import find_repo_root
    from fettle.session_plan import (
        active_plan, check_item, create_plan, find_plans, parse_plan,
        render_status,
    )

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)",
              file=sys.stderr)
        sys.exit(2)
    root = Path(repo_root)
    action = getattr(args, "plan_action", "status") or "status"
    if action == "start":
        try:
            path = create_plan(root, args.title, args.item,
                               session_id=os.environ.get("CLAUDE_SESSION_ID"))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)
        print(f"✓ session plan: {path} ({len(args.item)} steps)")
        sys.exit(0)
    if action == "status":
        plan = active_plan(root)
        if plan is None:
            plans = find_plans(root)
            plan = parse_plan(plans[0]) if plans else None
        if args.json:
            print(json.dumps(plan, indent=2))
        else:
            print(render_status(plan))
        sys.exit(0)
    if action == "check":
        ok, msg = check_item(root, args.text)
        print(("✓ done: " if ok else "Refused: ") + msg,
              file=sys.stdout if ok else sys.stderr)
        sys.exit(0 if ok else 1)
    print(f"unknown plan action: {action}", file=sys.stderr)
    sys.exit(2)


def cmd_insights(args: argparse.Namespace) -> None:
    """Read-only evidence digest (WP-163, C4)."""
    from fettle.insights import compute_insights, render_insights
    from fettle.paths import find_repo_root

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)",
              file=sys.stderr)
        sys.exit(2)
    data = compute_insights(Path(repo_root), days=args.days)
    print(json.dumps(data, indent=2) if args.json else render_insights(data))
    sys.exit(0)


def cmd_rules(args: argparse.Namespace) -> None:
    """Machine-drafted rule file lifecycle (WP-163, C3)."""
    from fettle.paths import find_repo_root

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)",
              file=sys.stderr)
        sys.exit(2)
    root = Path(repo_root)
    action = getattr(args, "rules_action", "list") or "list"
    if action == "list":
        from fettle.rules_cmd import list_rules, render_rules_table
        rows = list_rules(root)
        print(json.dumps(rows, indent=2) if args.json else render_rules_table(rows))
        sys.exit(0)
    if action == "promote":
        if getattr(args, "candidates", False):
            from fettle.rules_cmd import promotion_candidates, render_candidates
            data = promotion_candidates(root)
            print(json.dumps(data, indent=2) if args.json else render_candidates(data))
            sys.exit(0)
        if not args.rule_id:
            print("Error: provide a rule id or --candidates", file=sys.stderr)
            sys.exit(2)
        from fettle.rules_cmd import promote_rule_file
        ok, msg = promote_rule_file(root, args.rule_id)
        print(("✓ " if ok else "Refused: ") + msg,
              file=sys.stdout if ok else sys.stderr)
        sys.exit(0 if ok else 1)
    if action == "demote":
        from fettle.rules_cmd import demote_rule_file
        ok, msg = demote_rule_file(root, args.rule_id, args.reason)
        print(("✓ " if ok else "Refused: ") + msg,
              file=sys.stdout if ok else sys.stderr)
        sys.exit(0 if ok else 1)
    print(f"unknown rules action: {action}", file=sys.stderr)
    sys.exit(2)


def cmd_worktree(args: argparse.Namespace) -> None:
    """Per-work-item git worktrees (WP7, Stage 4).

    Exit codes: 0 = ok, 1 = git-level failure, 2 = usage/environment error.
    """
    from fettle.config import load_config
    from fettle.paths import find_repo_root
    from fettle.worktrees import create_worktree, list_worktrees, remove_worktree

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    root = str(repo_root)
    config = load_config(root)

    if args.wt_action == "create":
        path, err = create_worktree(root, args.item_id, config)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(2 if "invalid item id" in err else 1)
        print(f"✓ worktree ready: {path} (branch fettle/{args.item_id})")
        sys.exit(0)

    if args.wt_action == "remove":
        err = remove_worktree(root, args.item_id, config, force=args.force)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        print(f"✓ worktree {args.item_id} removed (branch fettle/{args.item_id} kept)")
        sys.exit(0)

    # default action: list
    rows, err = list_worktrees(root, config)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for r in rows:
            tag = f"[{r['item']}]" if r.get("managed") else "(main)" if not r.get("bare") else "(bare)"
            dirty = " — DIRTY" if r.get("dirty") else ""
            print(f"  {tag:<20} {r.get('branch', '?'):<28} {r['path']}{dirty}")
    sys.exit(0)


def cmd_links(args: argparse.Namespace) -> None:
    """Semantic layer query surface (Stage 6).

    Exit codes: 0 = ok, 1 = orphans found, 2 = usage error / unknown id.
    """
    from fettle.config import load_config
    from fettle.paths import find_repo_root
    from fettle.semantic import (build_graph, closest_ids, find_orphans,
                                 format_links, format_orphans, links_for)

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    root = str(repo_root)
    g = build_graph(root, load_config(root))

    if args.orphans:
        orphans = find_orphans(g)
        if args.json:
            print(json.dumps({"orphans": orphans}, indent=2))
        else:
            print(format_orphans(orphans))
        sys.exit(1 if orphans else 0)

    if not args.id:
        print("Error: give an id to look up, or --orphans", file=sys.stderr)
        sys.exit(2)
    info = links_for(g, args.id)
    if info is None:
        suggestions = closest_ids(g, args.id)
        hint = f" Closest known ids: {', '.join(suggestions)}" if suggestions else ""
        print(f"Error: unknown id '{args.id}'.{hint}", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(format_links(info))
    sys.exit(0)


def cmd_work(args: argparse.Namespace) -> None:
    """Work items + claims (WP5, Stage 4).

    Exit codes: 0 = ok, 1 = error findings / refused claim, 2 = usage/env error.
    """
    from fettle.paths import find_repo_root
    from fettle.work_items import (
        claim_item, discover_work_items, lint_work_items, load_claims, release_item,
    )

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    root = str(repo_root)

    if args.work_action == "claim":
        session = os.environ.get("CLAUDE_SESSION_ID", "") or f"cli-{os.getpid()}"
        err = claim_item(root, args.item_id, session, root)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        print(f"✓ claimed {args.item_id}")
        sys.exit(0)

    if args.work_action == "release":
        err = release_item(root, args.item_id)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        print(f"✓ released {args.item_id}")
        sys.exit(0)

    # default action: list (items + lint findings + claim state)
    claims = load_claims(root)
    items = [i for i, _ in discover_work_items(root) if i is not None]
    findings = lint_work_items(root)
    if args.json:
        print(json.dumps({
            "items": [{
                "id": i.item_id, "status": i.status, "path": i.path,
                "spec": i.spec, "claimed_by": claims.get(i.item_id, {}).get("session_id", ""),
            } for i in items],
            "findings": findings,
        }, indent=2))
    else:
        if not items:
            print("No work items found (markdown files with 'fettle-work-item' frontmatter).")
        for i in items:
            claim = claims.get(i.item_id, {})
            claimed = f"  ← claimed by {claim['session_id']}" if claim else ""
            spec = f"  spec:{i.spec}" if i.spec else ""
            print(f"  {i.item_id:<28} {i.status:<8} {i.path}{spec}{claimed}")
        for f in findings:
            print(f"  [{f['severity']}] {f['file']}:{f['line']} — {f['message']}")
            print(f"      fix: {f['fix']}")
    sys.exit(1 if any(f["severity"] == "ERROR" for f in findings) else 0)


def cmd_verify(args: argparse.Namespace) -> None:
    """Run the project's test suite and record the verification stamp.

    Exit codes: 0 = suite green, 1 = red/timeout, 2 = no test command found.
    """
    from fettle.config import load_config
    from fettle.paths import find_repo_root
    from fettle.verify_gate import run_verify

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    root = str(repo_root)
    config = load_config(root)
    session_id = os.environ.get("CLAUDE_SESSION_ID")
    stamp = run_verify(root, config, full=args.full, session_id=session_id)

    if args.json:
        print(json.dumps(stamp, indent=2))
    else:
        if not stamp["command"]:
            print(f"Error: {stamp['error']}", file=sys.stderr)
        else:
            state = "green" if stamp["ok"] else "RED"
            print(f"verify: {state} — {stamp['command']} "
                  f"({stamp['scope']}, {stamp['duration_s']}s)")
            if stamp["error"]:
                print(stamp["error"], file=sys.stderr)
    if not stamp["command"]:
        sys.exit(2)
    sys.exit(0 if stamp["ok"] else 1)


def cmd_uat(args: argparse.Namespace) -> None:
    """Agentic UAT (WP3, Stage 5).

    Exit codes: 0 = ok/ready, 1 = capability gaps, 2 = usage/environment error.
    """
    from fettle.config import load_config
    from fettle.paths import find_repo_root
    from fettle.uat.doctor import format_report, probe
    from fettle.uat.surfaces import resolve_surfaces

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: not inside a repository (no .git or .fettle.toml found)", file=sys.stderr)
        sys.exit(2)
    root = str(repo_root)
    config = load_config(root)

    if getattr(args, "uat_action", "doctor") == "run":
        from fettle.uat.reconcile import format_verdicts, reconcile_session
        from fettle.uat.session import run_session
        result = run_session(root, config, args.surface, consent=args.yes)
        verdicts = []
        if result.status == "completed":
            verdicts, _cp, rec_err = reconcile_session(root, result.worktree)
            if rec_err:
                result.error = rec_err
        if args.json:
            print(json.dumps({
                "session_id": result.session_id, "surface": result.surface,
                "worktree": result.worktree, "transcript": result.transcript_path,
                "scenarios": result.scenario_ids, "status": result.status,
                "error": result.error,
                "verdicts": [{"scenario_id": v.scenario_id, "verdict": v.verdict,
                              "observed": v.observed, "note": v.note}
                             for v in verdicts],
            }, indent=2))
        else:
            print(f"UAT session {result.session_id} on '{result.surface}': {result.status}")
            if result.worktree:
                print(f"  worktree:   {result.worktree}")
            if result.transcript_path:
                print(f"  transcript: {result.transcript_path}")
            if verdicts:
                print(format_verdicts(verdicts))
            if result.error:
                print(f"  error: {result.error}", file=sys.stderr)
        ok = result.status == "completed" and not result.error and all(
            v.verdict == "CONFIRMED" for v in verdicts)
        sys.exit(0 if ok else 1)

    if getattr(args, "uat_action", "doctor") == "report":
        from fettle.uat.reconcile import format_verdicts, reconcile_session
        verdicts, cp, err = reconcile_session(root, args.worktree)
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(2)
        if args.json:
            print(json.dumps({
                "session_id": cp.get("session_id", ""),
                "verdicts": [{"scenario_id": v.scenario_id, "verdict": v.verdict,
                              "observed": v.observed, "note": v.note}
                             for v in verdicts],
            }, indent=2))
        else:
            print(format_verdicts(verdicts))
        sys.exit(0 if all(v.verdict == "CONFIRMED" for v in verdicts) else 1)

    if getattr(args, "uat_action", "doctor") == "manual":
        from fettle.uat.manual import format_manual_guide
        from fettle.uat.session import collect_scenarios
        print(format_manual_guide(collect_scenarios(root)))
        sys.exit(0)

    if getattr(args, "uat_action", "doctor") == "attest":
        import os
        from fettle.uat.manual import record_attestation
        entry, err = record_attestation(
            root, args.scenario_id, args.outcome, args.observed,
            operator=os.environ.get("USER", ""))
        if err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(2)
        print(f"Recorded operator attestation for {entry['scenario_id']}: "
              f"{entry['outcome']} (source: operator)")
        sys.exit(0)

    # default action: doctor
    surfaces, err = resolve_surfaces(root, config)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(2)
    caps, err = probe(root, config)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps({
            "surfaces": surfaces,
            "capabilities": [{
                "surface": c.surface, "ready": c.ready, "detail": c.detail,
                "why": c.why, "fix": c.fix, "manual": c.manual,
            } for c in caps],
        }, indent=2))
    else:
        print(format_report(surfaces, caps))
    sys.exit(0 if all(c.ready for c in caps) else 1)


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
    p_check.add_argument("--junit", metavar="FILE", help="Write findings as JUnit XML (CI dashboards)")

    p_config = subparsers.add_parser("config", help="Show configuration")
    p_config.add_argument("--print-effective", action="store_true", help="Show merged effective config")
    p_config.add_argument("--explain", action="store_true", help="Show the source of each effective value")
    p_config.add_argument("--validate", action="store_true", help="Validate .fettle.toml against the config schema")

    p_explain = subparsers.add_parser("explain", help="Explain last hook decision")
    p_explain.add_argument("--last", type=int, default=1, help="Show last N decisions")
    p_explain.add_argument("--detailed", action="store_true", help="Show actions and evidence")
    p_explain.add_argument("--json", action="store_true", help="JSON Lines output")

    p_baseline = subparsers.add_parser("baseline", help="Manage violation baselines")
    p_baseline.add_argument("action", choices=["create", "update"], help="Baseline action")

    p_mutation = subparsers.add_parser("mutation", help="Run and inspect Python mutation evidence")
    mutation_sub = p_mutation.add_subparsers(dest="mutation_action", required=True)
    p_mutation_run = mutation_sub.add_parser("run", help="Run changed or full mutation evidence")
    mutation_scope = p_mutation_run.add_mutually_exclusive_group(required=True)
    mutation_scope.add_argument("--changed", action="store_true", help="Mutate changed implementation files")
    mutation_scope.add_argument("--all", action="store_true", help="Mutate all configured implementation files")
    p_mutation_run.add_argument("--base", help="Changed-scope comparison base")
    p_mutation_run.add_argument("--shard-index", type=int, help=argparse.SUPPRESS)
    p_mutation_run.add_argument("--shard-count", type=int, help=argparse.SUPPRESS)
    p_mutation_run.add_argument("--manifest", help=argparse.SUPPRESS)
    p_mutation_run.add_argument("--json", action="store_true", help="JSON output")
    p_mutation_run.add_argument("--output", help="Atomically retain JSON evidence at this path")
    p_mutation_status = mutation_sub.add_parser("status", help="Evaluate a retained mutation report")
    p_mutation_status.add_argument("--report", required=True, help="Retained schema-v2 report")
    p_mutation_status.add_argument("--json", action="store_true", help="JSON output")
    p_mutation_status.add_argument("--output", help="Atomically retain the evaluated report")
    p_mutation_show = mutation_sub.add_parser("show", help="Show one canonical mutant")
    p_mutation_show.add_argument("fingerprint", help="Canonical mutant fingerprint")
    p_mutation_show.add_argument("--report", required=True, help="Retained schema-v2 report")
    p_mutation_show.add_argument("--json", action="store_true", help="JSON output")
    p_mutation_baseline = mutation_sub.add_parser("baseline", help="Check or establish an accepted baseline")
    mutation_baseline_sub = p_mutation_baseline.add_subparsers(dest="baseline_action", required=True)
    for action, help_text in (
        ("check", "Validate that reports can establish one baseline"),
        ("establish", "Validate reports and atomically save the accepted baseline"),
    ):
        command = mutation_baseline_sub.add_parser(action, help=help_text)
        command.add_argument("reports", nargs=2, help="Two independent full schema-v2 reports")
        command.add_argument("--run-id", action="append", required=True, help="Independent CI run ID (twice)")
        command.add_argument("--floor", type=float, required=True, help="Accepted repository score floor")
        command.add_argument("--json", action="store_true", help="JSON output")

    p_doctor = subparsers.add_parser("doctor", help="Environment self-check")
    p_doctor.add_argument("--fix", action="store_true",
                          help="Apply mechanical fixes only (wire declared pre-commit hooks)")
    p_doctor.add_argument("--verify-hashes", dest="verify_hashes", action="store_true",
                          help="Verify pinned tools against wheel RECORD hashes (WP-147)")

    p_integrations = subparsers.add_parser(
        "integrations",
        help="Run external tool adapters (SonarQube, Black Duck, Pact)")
    p_integrations.add_argument("name", nargs="?", default=None,
                                choices=sorted(_INTEGRATIONS),
                                help="One adapter; omit to run all enabled ones")
    p_integrations.add_argument("--json", action="store_true", help="JSON output")

    p_init = subparsers.add_parser("init", help="One-command setup: repo config, agent hooks, commit-time guards")
    p_init.add_argument("--install-tools", action="store_true",
                        help="Install pinned ruff/semgrep/pre-commit via uv")
    p_init.add_argument("--dry-run", action="store_true", help="Show what would be done")
    p_init.add_argument("--json", action="store_true", help="JSON output")
    p_init.add_argument("--interactive", action="store_true",
                        help="Five questions to fit .fettle.toml to this project (TTY)")
    p_init.add_argument("--profile", choices=["solo", "team", "enterprise"],
                        help="Generate .fettle.toml from a preset (non-interactive)")
    p_init.add_argument("--force", action="store_true",
                        help="Overwrite an existing .fettle.toml (with --interactive/--profile)")

    p_workflows = subparsers.add_parser(
        "workflows", help="Guided workflows in every agent's slash-command format (WP-18)")
    workflows_sub = p_workflows.add_subparsers(dest="workflows_action")
    p_wf_list = workflows_sub.add_parser("list", help="Canonical workflows + per-host invocation")
    p_wf_list.add_argument("--json", action="store_true", help="JSON output")
    p_wf_install = workflows_sub.add_parser(
        "install", help="Render commands/*.md into each host's native format")
    p_wf_install.add_argument("--agent", default="all",
                              choices=["all", "claude", "vscode", "codex", "gemini", "opencode"],
                              help="One host, or all detected ones (default)")
    scope_group = p_wf_install.add_mutually_exclusive_group()
    scope_group.add_argument("--project", action="store_true",
                             help="Install into this repository (default)")
    scope_group.add_argument("--user", action="store_true",
                             help="Install into your home-directory agent config")
    p_wf_install.add_argument("--dry-run", dest="dry_run", action="store_true",
                              help="Show what would be written")
    p_wf_install.add_argument("--json", action="store_true", help="JSON output")
    p_workflows.set_defaults(workflows_action="list", json=False)

    p_policy = subparsers.add_parser("policy", help="Sync or inspect the digest-pinned org policy ([extends])")
    policy_sub = p_policy.add_subparsers(dest="policy_action")
    policy_sub.add_parser("sync", help="Fetch, digest-verify, and cache the org policy")
    policy_sub.add_parser("status", help="Show pin and cache state")
    p_policy.set_defaults(policy_action="sync")

    p_tel = subparsers.add_parser("telemetry",
                                  help="Opt-in anonymous counters (org policy only, default off)")
    tel_sub = p_tel.add_subparsers(dest="telemetry_action")
    tel_sub.add_parser("status", help="Enabled? By whom? Where would it go?")
    p_tel_show = tel_sub.add_parser("show", help="Print the exact payload that would be sent")
    p_tel_show.add_argument("--days", type=int, default=30, help="Aggregation window (default 30)")
    p_tel_send = tel_sub.add_parser("send", help="Send counters to the org endpoint (refused unless org-enabled)")
    p_tel_send.add_argument("--days", type=int, default=30, help="Aggregation window (default 30)")
    p_tel.set_defaults(telemetry_action="status")

    p_report = subparsers.add_parser("report", help="Effectiveness metrics from the audit trail")
    p_report.add_argument("--org", action="store_true", help="Aggregate per repo (cross-repo rollup)")
    p_report.add_argument("--compliance", action="store_true",
                          help="Evidence table: rules mapped to CWE / OWASP ASVS / SOC 2 (WP-146)")
    p_report.add_argument("--lineage", action="store_true",
                          help="Delegation-chain forest: who spawned whom, under which capsule (WP-158)")
    p_report.add_argument("--days", type=int, default=30, help="Reporting window (default 30)")
    p_report.add_argument("--json", action="store_true", help="JSON output")

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
    for _action, _help in (("status", "One-shot remote CI verdict for a commit"),
                           ("wait", "Poll remote CI to completion, then report")):
        p_ci_a = ci_sub.add_parser(_action, help=_help)
        p_ci_a.add_argument("--sha", default=None, help="Commit to check (default: HEAD)")
        p_ci_a.add_argument("--json", action="store_true")
        p_ci_a.add_argument("--root", default=".")

    # WP-119: Ratchet workflow
    p_ratchet = subparsers.add_parser("ratchet", help="Evidence-based rule promotion/demotion")
    ratchet_sub = p_ratchet.add_subparsers(dest="ratchet_action")
    ratchet_sub.add_parser("status", help="Show per-rule mode and evidence")
    p_ratchet_promote = ratchet_sub.add_parser("promote", help="Promote rule advisory -> enforce")
    p_ratchet_promote.add_argument("rule_id", help="Rule ID to promote")
    p_ratchet_demote = ratchet_sub.add_parser("demote", help="Demote rule enforce -> advisory")
    p_ratchet_demote.add_argument("rule_id", help="Rule ID to demote")
    p_ratchet_demote.add_argument(
        "--override", required=True,
        help="Active canonical override ID authorizing this rule demotion",
    )
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

    p_overrides = subparsers.add_parser(
        "overrides", help="Inspect revision-bound enforcing-decision overrides")
    overrides_sub = p_overrides.add_subparsers(dest="overrides_action")
    for action, help_text in (
        ("list", "Show active, expired, and invalid override records"),
        ("validate", "Fail if the override ledger contains expired or invalid records"),
    ):
        command = overrides_sub.add_parser(action, help=help_text)
        command.add_argument("--json", action="store_true", help="JSON output")
    p_overrides.set_defaults(overrides_action="list", json=False)

    p_verification = subparsers.add_parser(
        "verification", help="Run seeded-defect conformance evidence")
    verification_sub = p_verification.add_subparsers(dest="verification_action")
    p_verification_check = verification_sub.add_parser(
        "check", help="Validate and execute committed verification manifests")
    p_verification_check.add_argument("--check", dest="check_id", default="")
    p_verification_check.add_argument("--json", action="store_true", help="JSON output")
    p_verification.set_defaults(verification_action="check", check_id="", json=False)

    subparsers.add_parser("lsp", help="Start the LSP server for editor integration (WP-125)")

    p_spec = subparsers.add_parser("spec", help="Living specifications: lint and list")
    p_spec.add_argument("--json", action="store_true", help="JSON output")
    spec_sub = p_spec.add_subparsers(dest="spec_action")
    p_spec_lint = spec_sub.add_parser("lint", help="Validate all discovered specs")
    p_spec_lint.add_argument("--json", action="store_true", help="JSON output")
    p_spec_list = spec_sub.add_parser("list", help="List discovered specs")
    p_spec_list.add_argument("--json", action="store_true", help="JSON output")
    p_spec_cov = spec_sub.add_parser("coverage", help="Scenario\u2192test trace coverage report")
    p_spec_cov.add_argument("--json", action="store_true", help="JSON evidence artifact")
    p_spec.set_defaults(spec_action="lint")

    p_topo = subparsers.add_parser(
        "topology", help="Multi-agent topology: advise, apply, status, revoke (WP-159..161)")
    topo_sub = p_topo.add_subparsers(dest="topology_action")
    p_topo_adv = topo_sub.add_parser(
        "advise", help="Recommend a topology for open work items, with rationale")
    p_topo_adv.add_argument("--days", type=int, default=30,
                            help="Trace window for risk heuristics (default 30)")
    p_topo_adv.add_argument("--json", action="store_true", help="JSON output")
    p_topo_app = topo_sub.add_parser(
        "apply", help="Provision the advised topology: worktrees, claims, manifest")
    p_topo_app.add_argument("--runner", default="claude",
                            choices=["claude", "codex", "gemini", "opencode"])
    p_topo_app.add_argument("--days", type=int, default=30)
    p_topo_app.add_argument("--json", action="store_true", help="JSON output")
    p_topo_st = topo_sub.add_parser(
        "status", help="Live worker table: claims × trace × stop-loss")
    p_topo_st.add_argument("--max-blocks", type=int, default=10,
                           help="Stop-loss: blocks per session before flagging (default 10)")
    p_topo_st.add_argument("--json", action="store_true", help="JSON output")
    p_topo_rev = topo_sub.add_parser("revoke", help="Release an item's claim and drop it")
    p_topo_rev.add_argument("item_id")
    p_topo_rep = topo_sub.add_parser(
        "report", help="Outcome join: predicted vs actual footprints, overlaps, stamps (v1.6)")
    p_topo_rep.add_argument("--json", action="store_true", help="JSON output")
    p_topo.set_defaults(topology_action="advise", days=30, json=False)

    p_spawn = subparsers.add_parser(
        "spawn", help="Launch a child agent governed by the current policy (WP-157)")
    p_spawn.add_argument("runner", choices=["claude", "codex", "gemini", "opencode"],
                         help="Registered agent runner")
    p_spawn.add_argument("--task", required=True, help="Prompt for the child agent")
    p_spawn.add_argument("--worktree", default="", metavar="ITEM_ID",
                         help="Provision + claim a per-item worktree as the child's cwd")
    p_spawn.add_argument("--timeout", type=int, default=600,
                         help="Child run timeout in seconds (default 600)")
    p_spawn.add_argument("--role", default="", choices=["implementer", "tester", "reviewer"],
                         help="Narrow child's file authority (P52)")

    p_rules = subparsers.add_parser(
        "rules", help="Machine-drafted rule lifecycle: proposed → learned (WP-163)")
    rules_sub = p_rules.add_subparsers(dest="rules_action")
    p_rules_list = rules_sub.add_parser(
        "list", help="Proposed + learned rules with fire/FP evidence")
    p_rules_list.add_argument("--json", action="store_true", help="JSON output")
    p_rules_prom = rules_sub.add_parser(
        "promote", help="Approve a proposal into rules/learned/ (human gate)")
    p_rules_prom.add_argument("rule_id", nargs="?", default="",
                              help="Proposal id (filename stem)")
    p_rules_prom.add_argument("--candidates", action="store_true",
                              help="List computed promote/demote candidates only")
    p_rules_prom.add_argument("--json", action="store_true", help="JSON output")
    p_rules_dem = rules_sub.add_parser(
        "demote", help="Return a learned rule to the proposal quarantine")
    p_rules_dem.add_argument("rule_id")
    p_rules_dem.add_argument("--reason", required=True,
                             help="Why the rule is being demoted")
    p_rules.set_defaults(rules_action="list", json=False)

    p_insights = subparsers.add_parser(
        "insights", help="Read-only digest: friction, signatures, rule pipeline, lineage (WP-163)")
    p_insights.add_argument("--days", type=int, default=7,
                            help="Evidence window in days (default 7)")
    p_insights.add_argument("--json", action="store_true", help="JSON output")

    p_plan = subparsers.add_parser(
        "plan", help="Session plans: checklist before work, ticked as you go (v1.6)")
    plan_sub = p_plan.add_subparsers(dest="plan_action")
    p_plan_start = plan_sub.add_parser(
        "start", help="Create a session plan in .fettle/plans/")
    p_plan_start.add_argument("--title", required=True, help="Plan title")
    p_plan_start.add_argument("--item", action="append", default=[],
                              help="A step (repeatable; at least one required)")
    p_plan_status = plan_sub.add_parser("status", help="Show the active plan")
    p_plan_status.add_argument("--json", action="store_true", help="JSON output")
    p_plan_check = plan_sub.add_parser("check", help="Tick the first unchecked item matching TEXT")
    p_plan_check.add_argument("text", help="Substring of the item to tick")
    p_plan.set_defaults(plan_action="status", json=False)

    p_brief = subparsers.add_parser(
        "brief", help="One poll for orchestrators: plan, claims, topology, CI, proposals (v1.6)")
    p_brief.add_argument("--days", type=int, default=7,
                         help="Friction window in days (default 7)")
    p_brief.add_argument("--json", action="store_true", help="JSON output")

    p_learn = subparsers.add_parser(
        "learn", help="Draft rule proposals from incidents or trace failure signatures (WP-163)")
    p_learn.add_argument("--incident", default="", help="Incident description text")
    p_learn.add_argument("--file", default="", help="Path to incident brief file")
    p_learn.add_argument("--list", action="store_true", help="List learned rules")
    p_learn.add_argument("--auto-save", dest="auto_save", action="store_true",
                         help="Save without confirmation prompt")
    p_learn.add_argument("--from-trace", dest="from_trace", action="store_true",
                         help="Draft proposals from detected failure signatures")
    p_learn.add_argument("--days", type=int, default=30,
                         help="Signature window for --from-trace (default 30)")

    p_wt = subparsers.add_parser("worktree", help="Per-work-item git worktrees (WP7)")
    wt_sub = p_wt.add_subparsers(dest="wt_action")
    p_wt_create = wt_sub.add_parser("create", help="Create worktree + branch fettle/<item-id>")
    p_wt_create.add_argument("item_id", help="kebab-case work item id")
    p_wt_list = wt_sub.add_parser("list", help="List worktrees (managed ones annotated)")
    p_wt_list.add_argument("--json", action="store_true", help="JSON output")
    p_wt_remove = wt_sub.add_parser("remove", help="Remove a managed worktree (refuses when dirty)")
    p_wt_remove.add_argument("item_id", help="work item id")
    p_wt_remove.add_argument("--force", action="store_true",
                             help="discard uncommitted changes (destructive)")
    p_wt.set_defaults(wt_action="list", json=False)

    p_work = subparsers.add_parser("work", help="Work items + claims (WP5)")
    work_sub = p_work.add_subparsers(dest="work_action")
    p_work_list = work_sub.add_parser("list", help="List work items with claim state")
    p_work_list.add_argument("--json", action="store_true", help="JSON output")
    p_work_claim = work_sub.add_parser("claim", help="Claim a work item for this checkout")
    p_work_claim.add_argument("item_id")
    p_work_release = work_sub.add_parser("release", help="Release a claimed work item")
    p_work_release.add_argument("item_id")
    p_work.set_defaults(work_action="list", json=False)

    p_links = subparsers.add_parser("links", help="Semantic layer: links for an id, or orphans")
    p_links.add_argument("id", nargs="?", help="Any known id (spec, scenario, test path, work item)")
    p_links.add_argument("--orphans", action="store_true",
                         help="Report broken evidence chains")
    p_links.add_argument("--json", action="store_true", help="JSON output")

    p_verify = subparsers.add_parser(
        "verify", help="Run the test suite and record a verification stamp")
    p_verify.add_argument("--full", action="store_true",
                          help="Run the full suite (ignore impacted-test scoping)")
    p_verify.add_argument("--json", action="store_true", help="JSON output")

    p_uat = subparsers.add_parser("uat", help="Agentic UAT (WP3)")
    uat_sub = p_uat.add_subparsers(dest="uat_action")
    p_uat_doc = uat_sub.add_parser("doctor", help="Surface detection + capability probe")
    p_uat_doc.add_argument("--json", action="store_true", help="JSON output")
    p_uat_run = uat_sub.add_parser("run", help="Run a UAT session on one surface")
    p_uat_run.add_argument("--surface", default="cli",
                           help="Surface to test (default: cli)")
    p_uat_run.add_argument("--yes", action="store_true",
                           help="Consent: the session runs an autonomous agent "
                                "with permission checks disabled in an isolated worktree")
    p_uat_run.add_argument("--json", action="store_true", help="JSON output")
    p_uat_rep = uat_sub.add_parser("report", help="Reconcile a session's transcript into verdicts")
    p_uat_rep.add_argument("--worktree", required=True, help="Session worktree path")
    p_uat_rep.add_argument("--json", action="store_true", help="JSON output")
    uat_sub.add_parser("manual", help="Print a manual UAT walkthrough from spec scenarios")
    p_uat_att = uat_sub.add_parser("attest", help="Record an operator-observed scenario outcome")
    p_uat_att.add_argument("scenario_id", help="e.g. my-spec/S1")
    p_uat_att.add_argument("--outcome", required=True,
                           choices=["matches", "differs", "could-not-attempt"])
    p_uat_att.add_argument("--observed", required=True,
                           help="What you actually saw (verbatim where possible)")
    p_uat.set_defaults(uat_action="doctor", json=False)

    args = parser.parse_args()

    if args.command is None:
        # v1.6 slice D: bare `fettle` inside a repo is a dashboard, not a
        # manpage — offline, cached CI only (D-D1). Outside a repo, help.
        from fettle.paths import find_repo_root
        repo_root = find_repo_root()
        if repo_root:
            from fettle.brief import compute_brief, render_brief
            print(render_brief(compute_brief(Path(repo_root))))
            print("\n  fettle -h — commands · fettle doctor — environment health")
            sys.exit(0)
        parser.print_help()
        sys.exit(0)

    commands = {
        "check": cmd_check,
        "config": cmd_config,
        "explain": cmd_explain,
        "baseline": cmd_baseline,
        "mutation": cmd_mutation,
        "doctor": cmd_doctor,
        "integrations": cmd_integrations,
        "init": cmd_init,
        "workflows": cmd_workflows,
        "policy": cmd_policy,
        "telemetry": cmd_telemetry,
        "report": cmd_report,
        "bench": cmd_bench,
        "ci": cmd_ci,
        "ratchet": cmd_ratchet,
        "suppressions": cmd_suppressions,
        "overrides": cmd_overrides,
        "verification": cmd_verification,
        "lsp": cmd_lsp,
        "spec": cmd_spec,
        "spawn": cmd_spawn,
        "topology": cmd_topology,
        "rules": cmd_rules,
        "insights": cmd_insights,
        "plan": cmd_plan,
        "brief": cmd_brief,
        "learn": cmd_learn,
        "worktree": cmd_worktree,
        "work": cmd_work,
        "links": cmd_links,
        "uat": cmd_uat,
        "verify": cmd_verify,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
