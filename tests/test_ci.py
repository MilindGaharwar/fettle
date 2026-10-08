"""`fettle ci` — composed gate + generated workflow (CI enforcement WP-2)."""

import os
import subprocess
import sys
import tempfile
import json
import re
from pathlib import Path

import yaml

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR))

from fettle import ci  # noqa: E402
from fettle.quality_scan import ToolScanResult  # noqa: E402
from fettle.result import ResultStatus  # noqa: E402

SYNTH_AWS = "AKIAZ7Q3M5N8P2K4R6T9"


def _workflow_step(workflow: dict, job_name: str, step_name: str) -> dict:
    return next(
        step for step in workflow["jobs"][job_name]["steps"]
        if step.get("name") == step_name
    )


def _embedded_python_blocks(script: str) -> list[str]:
    heredocs = re.findall(r"(?:^|\n)\s*(?:\S+/)?python - <<'PY'\n(.*?)\n\s*PY(?:\n|$)", script, re.DOTALL)
    one_liners = re.findall(r"python -c '([^']*)'", script)
    return [*heredocs, *one_liners]


def _git_repo(files: dict) -> str:
    d = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    for name, content in files.items():
        path = os.path.join(d, name)
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(name) else None
        with open(path, "w") as f:
            f.write(content)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    return d


def test_run_ci_clean_repo_passes():
    d = _git_repo({"a.py": "x = 1\n"})
    result = ci.run_ci(d)
    assert result["ok"] is True
    assert any(g["name"] == "boundary" and g["ok"] for g in result["gates"])


def test_run_ci_planted_secret_fails():
    d = _git_repo({"leak.py": f'k = "{SYNTH_AWS}"\n'})
    result = ci.run_ci(d)
    assert result["ok"] is False
    boundary = next(g for g in result["gates"] if g["name"] == "boundary")
    assert boundary["ok"] is False
    assert boundary["findings"]  # the secret is surfaced


def test_run_ci_changed_spec_without_audit_fails():
    d = _git_repo({
        ".fettle.toml": "[gates.spec_audit]\nenabled = true\n",
        "docs/PRODUCT-STRATEGY.md": "# Strategy\n",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qm", "base"],
        cwd=d,
        check=True,
    )
    with open(os.path.join(d, "docs", "PRODUCT-STRATEGY.md"), "a") as f:
        f.write("Changed.\n")

    result = ci.run_ci(d)
    quality = next(g for g in result["gates"] if g["name"] == "quality")
    assert quality["ok"] is False
    assert any("SPEC_AUDIT" in finding for finding in quality["findings"])


def test_run_ci_baseline_cannot_suppress_spec_audit():
    d = _git_repo({
        ".fettle.toml": "[gates.spec_audit]\nenabled = true\n",
        ".fettle-baseline.json": (
            '{"fingerprints":["spec_audit:docs/spec-audit.md:1:"]}'
        ),
        "docs/PRODUCT-STRATEGY.md": "# Strategy\n",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qam", "base"],
        cwd=d,
        check=True,
    )
    with open(os.path.join(d, "docs", "PRODUCT-STRATEGY.md"), "a") as f:
        f.write("Changed.\n")

    quality = next(g for g in ci.run_ci(d)["gates"] if g["name"] == "quality")
    assert quality["ok"] is False
    assert any("SPEC_AUDIT" in finding for finding in quality["findings"])


def test_run_ci_committed_spec_and_audit_pass_on_clean_branch():
    sections = (
        "Requirements Matrix",
        "Fixture And Live Separation",
        "Adversarial Pass Review",
        "Non-Goals And Failure Paths",
        "Residual Risks",
    )
    d = _git_repo({
        ".fettle.toml": "[gates.spec_audit]\nenabled = true\n",
        "docs/PRODUCT-STRATEGY.md": "# Strategy\n",
    })
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qm", "base"],
        cwd=d,
        check=True,
    )
    subprocess.run(["git", "branch", "-M", "main"], cwd=d, check=True)
    subprocess.run(["git", "switch", "-qc", "feature"], cwd=d, check=True)
    with open(os.path.join(d, "docs", "PRODUCT-STRATEGY.md"), "a") as f:
        f.write("Changed.\n")
    with open(os.path.join(d, "docs", "spec-audit.md"), "w") as f:
        f.write("# Audit\n" + "".join(f"\n## {section}\nChecked.\n" for section in sections))
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@fettle.invalid", "commit", "-qm", "audited"],
        cwd=d,
        check=True,
    )

    assert ci.run_ci(d)["ok"] is True


def test_regression_fails_closed_when_scanner_raises(monkeypatch):
    """Regression — CI must fail closed, never silently skip a gate: if the
    boundary scanner raises, run_ci reports failure, not pass."""
    d = _git_repo({"a.py": "x = 1\n"})

    def boom(root, cfg):
        raise RuntimeError("scanner crashed")

    monkeypatch.setattr(ci, "scan_repo", boom)
    result = ci.run_ci(d)
    assert result["ok"] is False
    boundary = next(g for g in result["gates"] if g["name"] == "boundary")
    assert boundary["ok"] is False
    assert "error" in boundary


def test_quality_gate_fails_closed_when_required_scanner_fails(monkeypatch):
    d = _git_repo({"a.py": "x = 1\n"})

    monkeypatch.setattr(
        "fettle.quality_scan.execute_ruff",
        lambda targets: ToolScanResult(
            tool="ruff",
            status=ResultStatus.TOOL_ERROR,
            message="ruff timed out",
        ),
    )

    result = ci.run_ci(d)

    quality = next(g for g in result["gates"] if g["name"] == "quality")
    assert result["ok"] is False
    assert quality["ok"] is False
    assert quality["status"] == ResultStatus.TOOL_ERROR.value
    assert "timed out" in quality["error"]


def test_quality_gate_preserves_scanner_config_error(monkeypatch):
    d = _git_repo({"a.py": "x = 1\n"})
    monkeypatch.setattr(
        "fettle.quality_scan.execute_semgrep",
        lambda targets: ToolScanResult(
            tool="semgrep",
            status=ResultStatus.CONFIG_ERROR,
            message="rules file not found",
        ),
    )

    quality = next(g for g in ci.run_ci(d)["gates"] if g["name"] == "quality")

    assert quality["ok"] is False
    assert quality["status"] == ResultStatus.CONFIG_ERROR.value


def test_plan_gate_honors_explicit_exclusions_without_hiding_other_plans():
    d = _git_repo({
        ".fettle.toml": (
            "[gates.plan]\n"
            'exclude = ["docs/activity-plan.md"]\n'
        ),
        "docs/activity-plan.md": "# Activity Plan\n\nNo WP task format.\n",
        "docs/invalid-plan.md": "# Invalid Plan\n\nNo work packages.\n",
    })

    plans = next(g for g in ci.run_ci(d)["gates"] if g["name"] == "plans")

    assert plans["ok"] is False
    assert plans["findings"] == ["docs/invalid-plan.md"]


def test_generated_workflow_parses_and_runs_fettle_ci():
    yaml_text = ci.generate_workflow()
    import yaml
    doc = yaml.safe_load(yaml_text)
    assert "jobs" in doc
    flat = yaml_text.lower()
    assert "fettle ci" in flat or "cli.py ci" in flat


def test_regression_generated_workflow_always_has_boundary_step():
    """Regression — a generated CI must never omit the boundary scan (the
    root cause: a hand-rolled CI missing the scrub audit let a leak ship)."""
    yaml_text = ci.generate_workflow()
    assert "boundar" in yaml_text.lower()


def test_init_seeds_config_and_workflow():
    d = _git_repo({"a.py": "x = 1\n"})
    ci.init_ci(d, dry_run=False)
    assert os.path.isfile(os.path.join(d, ".github", "workflows", "fettle.yml"))
    toml = os.path.join(d, ".fettle.toml")
    assert os.path.isfile(toml)
    with open(toml) as f:
        assert "boundary" in f.read()


def test_init_dry_run_writes_nothing():
    d = _git_repo({"a.py": "x = 1\n"})
    out = ci.init_ci(d, dry_run=True)
    assert not os.path.exists(os.path.join(d, ".github"))
    assert "boundar" in out.lower()


def test_integration_run_ci_end_to_end():
    clean = _git_repo({"ok.py": "y = 2\n"})
    assert ci.run_ci(clean)["ok"] is True
    leaky = _git_repo({"bad.py": f'p = "/Users/someone/other/x.py"\nk = "{SYNTH_AWS}"\n'})
    assert ci.run_ci(leaky)["ok"] is False


def test_mutation_workflow_uses_dynamic_blocking_evidence_authority():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "timeout-minutes: 35" in workflow
    assert "prepare:" in workflow
    assert "fromJSON(needs.prepare.outputs.matrix)" in workflow
    assert "--resume-manifest" in workflow
    assert "shard: [0, 1," not in workflow
    assert "--paths fettle/" not in workflow
    assert "--shard-count 240" not in workflow
    assert "if: always()" in workflow


def test_pr_containment_is_separate_from_authoritative_check_producer():
    authoritative = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    containment = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert "pull_request:" not in authoritative
    assert "pull_request:" in containment
    assert "name: mutation evidence" not in containment
    assert containment.count("name: mutation qualification pending") == 1


def test_changed_mutation_workflow_prepares_scope_without_pr_execution_fanout():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert "--prepare-changed-manifests mutation-changed-manifests" in workflow
    assert "fromJSON(needs.changed-prepare.outputs.matrix)" not in workflow
    assert "mutmut run" not in workflow
    assert "needs: changed-prepare" in workflow
    assert "Mutation execution requires explicit maintainer dispatch" in workflow
    assert '\"status\":\"unknown\"' in workflow
    assert '\"passed\":false' in workflow
    assert "if: needs.changed-prepare.result != 'success'" in workflow
    assert "needs.changed-prepare.outputs.shard_count != '0'" in workflow


def test_changed_mutation_workflow_retains_truthful_nonpass_summary():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert '\"qualification_executed\":false' in workflow
    assert '\"status\":\"not_applicable\"' in workflow
    assert '\"status\":\"unknown\"' in workflow
    assert "--github-summary mutation-report.json" in workflow
    assert "mutation-pr-containment-${{ github.run_id }}" in workflow
    assert "if-no-files-found: error" in workflow


def test_changed_mutation_workflow_keeps_replay_behind_explicit_dispatch():
    containment = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "changed-replay" not in containment
    assert "--resume-manifest" not in containment
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "--resume-manifest" in workflow
    assert "--timeout 1740" in workflow


def test_mutation_workflows_have_one_authoritative_check_producer():
    workflows = [
        yaml.safe_load(path.read_text())
        for path in (Path(PLUGIN_DIR) / ".github/workflows").glob("*.yml")
    ]

    assert sum(
        job.get("name") == "mutation evidence"
        for workflow in workflows
        for job in workflow.get("jobs", {}).values()
    ) == 1


def test_mutation_workflows_pin_supported_node24_setup_uv():
    workflows = [
        Path(PLUGIN_DIR) / ".github/workflows/mutation.yml",
        Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml",
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml",
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-aggregation-recovery.yml",
    ]
    pin = "astral-sh/setup-uv@eb1897b8dc4b5d5bfe39a428a8f2304605e0983c # v7.0.0"

    assert all(pin in path.read_text() for path in workflows)
    assert all("setup-uv@d0cc045d" not in path.read_text() for path in workflows)


def test_final_candidate_mutation_path_uses_exact_runtime_and_stages():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert 'python-version: "3.12"' not in workflow
    assert 'python-version: "3.12.13"' in workflow
    assert 'platform.python_version()=="3.12.13"' in workflow
    assert 'report.get("shard_count")==256' in workflow
    assert "- finalize" in workflow
    assert 'WAVES["wave-"+stage]' in workflow
    assert '"1":8,"2":16,"3":32' in workflow
    assert "pattern: mutation-shard-${{ github.event.inputs.stage_1_run_id }}-*" in workflow
    assert "pattern: mutation-shard-${{ github.event.inputs.stage_2_run_id }}-*" in workflow
    assert "Validate prior calibration stages before fan-out" in workflow
    assert "len(identities) != 1" in workflow
    assert "identity != prior_identity" in workflow
    assert 'report.get("calibration_id") != os.environ["CALIBRATION_ID"]' in workflow
    assert "Download prior calibration accounting" in workflow
    assert 'accounting.get("ceiling") != int(os.environ["RUNNER_MINUTE_CEILING"])' in workflow
    assert "name: mutation (assemble evidence)" in workflow
    assert "name: mutation evidence" in workflow
    assert "Independently read back authoritative evidence" in workflow
    assert "name: mutation (read back detail corpus)" in workflow
    assert "name: mutation (calibration accounting)" in workflow
    assert "runner_minute_ceiling:" in workflow
    assert "int(value)<=12000" in workflow
    assert "fail-fast: ${{ github.event.inputs.mode == 'calibration' }}" in workflow
    readback = workflow.split("\n  evidence-readback:", 1)[1]
    assert "github.event.inputs.calibration_stage != '3'" in readback


def test_finalization_rejects_non_allowlisted_or_mode_changes():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    finalization = workflow.split("Prove evidence-only finalization head", 1)[1].split(
        "Download stage 1 mutation evidence", 1,
    )[0]

    assert '"docs/completion/audit-hardening.json"' in finalization
    assert '"docs/final-candidate-readiness.md"' in finalization
    assert '["git", "diff", "--raw", "--no-abbrev", executable, head]' in finalization
    assert 'fields[0] != ":100644" or fields[1] != "100644"' in finalization
    assert "set(changed) - allowed" in finalization
    aggregate = workflow.split("\n  aggregate:", 1)[1].split("\n  evidence-readback:", 1)[0]
    assert "fetch-depth: 0" in aggregate
    assert 'report.get("calibration_id")==os.environ["CALIBRATION_ID"]' in workflow
    assert 'hashlib.sha256(path.read_bytes()).hexdigest()==checksum' in workflow
    assert 'accounting.get("stage")=="3" and accounting.get("passed") is True' in workflow


def test_full_mutation_workflow_gates_fanout_on_retained_preflight():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "preflight:" in workflow
    assert "--preflight-manifest" in workflow
    assert "name: mutation-preflight-${{ github.run_id }}-${{ matrix.shard }}" in workflow
    assert "needs: [prepare, preflight]" in workflow
    assert workflow.index("Prepare digest-bound partitions") < workflow.index("Bounded mutation-detail preflight")
    assert "type: choice" in workflow
    assert "- preflight" in workflow and "- replay" in workflow and "- calibration" in workflow


def test_mutation_workflow_has_bounded_non_qualifying_diagnostic_canary():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    prepare_job = workflow.split("\n  prepare:", 1)[1].split("\n  preflight:", 1)[0]
    preflight_job = workflow.split("\n  preflight:", 1)[1].split("\n  diagnostic-canary:", 1)[0]
    canary_job = workflow.split("\n  diagnostic-canary:", 1)[1].split(
        "\n  preflight-aggregate:", 1,
    )[0]
    preflight_aggregate_job = workflow.split("\n  preflight-aggregate:", 1)[1].split(
        "\n  full-shard:", 1,
    )[0]
    full_shard_job = workflow.split("\n  full-shard:", 1)[1].split("\n  aggregate:", 1)[0]
    aggregate_job = workflow.split("\n  aggregate:", 1)[1]

    assert "- diagnostic-canary" in workflow
    assert "diagnostic_shard:" in workflow
    assert "Bind dispatch to exact candidate" in prepare_job
    assert "Validate diagnostic canary scope" in prepare_job
    assert "name: mutation (diagnostic preflight shard)" in canary_job
    assert "matrix:" not in canary_job
    assert '--preflight-manifest "mutation-manifests/partition-${DIAGNOSTIC_SHARD}.json"' in canary_job
    assert "if: always()" in canary_job
    assert "name: mutation-preflight-diagnostic-${{ github.run_id }}" in canary_job
    assert "github.event.inputs.mode == 'preflight'" in preflight_job
    assert "github.event.inputs.mode == 'preflight'" in preflight_aggregate_job
    assert "github.event.inputs.mode != 'diagnostic-canary'" in full_shard_job
    assert "github.event.inputs.mode != 'calibration'" in aggregate_job
    assert '"qualification_executed":False' in aggregate_job
    assert "report.get('passed') is True" in aggregate_job
    assert "[46,62,63,239]" not in workflow
    assert 'archived=(("fettle/mutation_test.py",121,180)' in workflow
    assert 'item["start"] <= end and item["end"] >= start' in workflow
    assert "python -m pip install" not in workflow
    assert "uv run --no-sync" in workflow
    assert "merge-multiple: true" not in workflow


def test_staged_preflight_first_run_is_frozen_bounded_and_fail_closed():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    staged = workflow.split("\n  staged-prepare:", 1)[1].split("\n  full-shard:", 1)[0]

    assert "- staged-preflight" in workflow
    assert 'run: test "$RUN_ATTEMPT" = "1"' in staged
    assert staged.count("ref: ${{ github.event.inputs.candidate_sha }}") >= 3
    assert "max-parallel: 2" in staged
    assert "max-parallel: 4" in staged
    assert "max-parallel: 8" not in staged
    assert staged.count("fail-fast: true") == 2
    assert "needs: [staged-prepare, staged-wave-1-gate]" in staged
    assert staged.count("validate-wave") == 2
    assert "mutation (monitor staged preflight budget)" in staged
    assert "gh run cancel \"$GITHUB_RUN_ID\"" in staged
    assert "gh workflow run staged-preflight-continuation.yml --ref \"$GITHUB_REF_NAME\"" in staged
    assert "source_plan_sha256" in staged
    assert "merge-multiple: true" not in staged


def test_staged_preflight_keeps_authoritative_check_non_qualifying():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    aggregate = workflow.split("\n  aggregate:", 1)[1]

    assert "name: mutation staged preflight evidence" not in workflow
    assert "name: mutation (dispatch staged preflight continuation)" in workflow
    assert "github.event.inputs.mode != 'staged-preflight'" in aggregate
    assert 'candidate == os.environ["GITHUB_SHA"]' in aggregate


def test_staged_continuation_has_only_remaining_matrix_and_bounded_topology():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    workflow = workflow_path.read_text()
    jobs = yaml.safe_load(workflow)["jobs"]

    assert set(jobs) == {"prepare", "launch-gate", "canary", "canary-readback", "remaining-launch-gate", "remaining-shards", "monitor", "validate", "aggregate", "readback", "terminal-accounting"}
    assert all(job.get("if") == "github.run_attempt == 1" for job in jobs.values())
    assert sum("strategy" in job for job in jobs.values()) == 1
    assert len(jobs) - 2 == 9
    assert workflow.count("strategy:") == 1
    assert workflow.count("matrix:") == 3  # strategy plus two prepare output keys
    assert "max-parallel: 8" in workflow
    assert "workflow_dispatch:" in workflow
    assert "recovery_id:" in workflow
    assert "candidate_sha:" not in workflow
    assert "source_plan_sha256:" not in workflow
    assert "fresh-continuation-plan" in workflow
    assert "--prepare-manifests" not in workflow
    assert "--manifests source-plan/mutation-manifests" in workflow
    assert "--source source-jobs.json 37573662156 1" in workflow
    assert "--source setup-jobs.json 37580393007 1" in workflow
    assert "--source layout-jobs.json 37589782905 1" in workflow
    assert "--source api-retry-jobs.json 37602471821 1" in workflow
    assert "--source identity-jobs.json 37605831970 1" in workflow
    assert "gh run cancel \"$GITHUB_RUN_ID\"" in workflow
    assert '"status == \\"completed\\"' not in workflow
    assert 'operator_authorized_dispatch_recovery' not in workflow
    assert "e2_preflight_recovery.py" in workflow
    assert '"permanently failed; dispatch handoff only"' in workflow
    assert 'set(record["origins"]) == {str(index) for index in range(256)}' in workflow
    assert 'recovery-authorization.json' in workflow
    assert "--aggregate-preflight staged-reports --shard-count 256" in workflow
    assert "staged-plan/source-plan/mutation-manifests/partition-${{ matrix.shard }}.json" in workflow
    assert "Validate producer manifest layout before matrix expansion" in workflow
    assert "Validate downloaded manifest handoff before execution" in workflow
    assert "Validate downloaded canary through final consumer contract" in workflow
    assert "Recalculate completion reserve from observed canary" in workflow
    assert "--remaining-shards 216" in workflow
    assert "--remaining-shards 215" in workflow
    assert '--canary-minutes "$(cat canary-minutes.txt)"' in workflow
    assert "cp staged-plan/layout-jobs.json layout-jobs.json" in workflow
    assert "cp staged-plan/api-retry-jobs.json api-retry-jobs.json" in workflow
    assert "for delay in 0 5 15" in workflow
    assert 'mv "$output.tmp" "$output"' in workflow
    assert jobs["remaining-shards"]["needs"] == [
        "prepare", "canary-readback", "remaining-launch-gate",
    ]
    assert "max-parallel: 8" in workflow
    assert "matrix:" not in workflow.split("\n  canary:", 1)[1].split("\n  canary-readback:", 1)[0]
    assert "staged-wave-1" not in workflow
    assert "staged-wave-2" not in workflow


def test_recovery_workflow_embedded_python_compiles_from_actual_yaml():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    blocks = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            script = step.get("run")
            if isinstance(script, str):
                blocks.extend(_embedded_python_blocks(script))

    assert len(blocks) == 9
    for index, source in enumerate(blocks):
        compile(source, f"workflow-python-{index}", "exec")


def test_recovery_identity_entry_point_executes_actual_workflow_script(tmp_path):
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    script = _workflow_step(
        workflow, "prepare", "Bind candidate and recovery orchestration identities",
    )["run"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python").symlink_to(sys.executable)
    git = bin_dir / "git"
    git.write_text(
        "#!/bin/sh\n"
        "case \"$2\" in\n"
        "candidate) echo f5560685d1f9eaea05107947fb0ecab791ad9478 ;;\n"
        "control) echo \"$GITHUB_SHA\" ;;\n"
        "*) exit 3 ;;\n"
        "esac\n",
    )
    git.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GITHUB_SHA": "a" * 40,
        "RECOVERY_ID": "E2-37573662156-1-handoff",
    }

    accepted = subprocess.run(["bash", "-eu", "-c", script], cwd=tmp_path, env=env)
    rejected = subprocess.run(
        ["bash", "-eu", "-c", script], cwd=tmp_path,
        env={**env, "RECOVERY_ID": "wrong"},
    )

    assert accepted.returncode == 0
    assert rejected.returncode == 2


def test_recovery_workflow_shell_handoffs_parse_after_expression_rendering():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    workflow = yaml.safe_load(workflow_path.read_text())
    scripts = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            script = step.get("run")
            if isinstance(script, str):
                scripts.append(re.sub(r"\$\{\{[^}]+\}\}", "rendered", script))

    for script in scripts:
        result = subprocess.run(["bash", "-n"], input=script, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr


def test_staged_preflight_budget_gates_are_cumulative_across_both_runs():
    first = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    continuation = (
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    ).read_text()

    assert "--next-wave wave-2 --output wave-1-budget.json" in first
    assert "--next-wave wave-3 --output wave-2-budget.json" in first
    assert "--next-wave complete --output monitor-budget.json" in first
    assert "--source source-jobs.json 37573662156 1" in continuation
    assert "--source setup-jobs.json 37580393007 1" in continuation
    assert "--source layout-jobs.json 37589782905 1" in continuation
    assert continuation.count("--source api-retry-jobs.json 37602471821 1") == 5
    assert continuation.count("--source identity-jobs.json 37605831970 1") == 5
    assert "--next-wave wave-3 --output launch-budget.json" in continuation
    budget_source = (Path(PLUGIN_DIR) / "fettle/staged_preflight.py").read_text()
    assert '"execution_cutoff": 700' in budget_source
    assert '"wave-3": 281.2' in budget_source
    assert '"retained_successful_shard_p95_minutes": 1.8' in budget_source
    assert '"support_completion_reserve_minutes": 30' in budget_source
    assert continuation.count("--next-wave complete") == 3
    assert "billing_authority" not in first
    assert "Operational ceiling, not a guaranteed provider billing cap." not in first


def test_aggregation_recovery_cannot_execute_mutations_and_retains_failure_evidence():
    workflow_path = Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-aggregation-recovery.yml"
    workflow = workflow_path.read_text()
    jobs = yaml.safe_load(workflow)["jobs"]

    assert set(jobs) == {"aggregate", "readback", "terminal-accounting"}
    assert all("strategy" not in job for job in jobs.values())
    assert "matrix:" not in workflow
    assert "--preflight-manifest" not in workflow
    assert "--prepare-manifests" not in workflow
    assert "mutation run" not in workflow
    assert "--aggregate-preflight corpus --shard-count 256" in workflow
    assert "github.event.head_commit.message == 'Execute preflight aggregation recovery'" in workflow
    assert workflow.count("run-id: 37464324954") == 1
    assert workflow.count("run-id: 37476889333") == 1
    assert workflow.count("run-id: 37550308775") == 2
    assert "if: always()\n    needs: aggregate" in workflow
    assert "if: always()\n    needs: [aggregate, readback]" in workflow
    assert "--source jobs-37550308775.json 37550308775 1" in workflow
    assert "generated\"] == aggregate[\"canonicalized\"] == 45432" in workflow
    assert "155a02b863d6b440211e09eef8daf189098554ca5871c5a484e7b65a3b005be2" in workflow


def test_continuation_support_jobs_install_every_invoked_tool():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    validation = workflow.split("\n  validate:", 1)[1].split("\n  aggregate:", 1)[0]
    aggregate = workflow.split("\n  aggregate:", 1)[1].split("\n  readback:", 1)[0]

    assert "astral-sh/setup-uv@" in validation
    assert "uv venv --python 3.12.13" in validation
    assert "astral-sh/setup-uv@" in aggregate
    assert "uv venv --python 3.12.13" in aggregate


def test_continuation_keeps_control_scripts_and_candidate_execution_separate():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()

    assert workflow.count("control/scripts/staged_preflight.py") == 13
    assert "candidate/.venv/bin/python control/scripts/e2_preflight_recovery.py" in workflow
    assert "candidate/.venv/bin/python control/scripts/staged_preflight.py" in workflow
    assert workflow.count("ref: f5560685d1f9eaea05107947fb0ecab791ad9478") == 7
    assert workflow.count("uv run --no-sync python -m fettle.mutation_test --root .") == 2
    assert "cp control/" not in workflow
    assert "rsync" not in workflow
    assert "--root control" not in workflow
    assert '"control_sha": os.environ["RECOVERY_ORCHESTRATION_SHA"]' in workflow
    assert '"candidate_sha": "f5560685d1f9eaea05107947fb0ecab791ad9478"' in workflow
    assert 'for name in ("staged_preflight.py", "e2_preflight_recovery.py")' in workflow
    assert '"candidate/fettle.staged_preflight"' in workflow
    assert workflow.count('"candidate/fettle.mutation_test"') == 7
    assert '"canary": ["candidate/fettle.mutation_test"]' in workflow
    assert '"readback": []' in workflow


def test_canary_readback_binds_terminal_evidence_and_uploads_no_stand_ins():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    canary = workflow.split("\n  canary:", 1)[1].split("\n  canary-readback:", 1)[0]
    readback = workflow.split("\n  canary-readback:", 1)[1].split("\n  remaining-launch-gate:", 1)[0]

    assert "report_sha256" in canary
    assert "mutation-preflight.json\n            canary-terminal.json" in canary
    assert "--terminal canary-report/canary-terminal.json" in readback
    assert "stand-in" not in workflow.lower()
    assert "non_authoritative" not in workflow


def test_mutation_execution_reuses_explicit_sha_bound_preflight():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "preflight_run_id:" in workflow
    assert workflow.count("run-id: ${{ github.event.inputs.preflight_run_id }}") == 4
    assert workflow.count("github-token: ${{ secrets.GITHUB_TOKEN }}") == 12
    assert "permissions:\n  actions: read\n  contents: read" in workflow
    assert "candidate_sha:" in workflow
    assert 'candidate == os.environ["GITHUB_SHA"]' in workflow
    assert 'aggregate["revision"]==os.environ["GITHUB_SHA"]' in workflow
    assert 'item["revision"]==os.environ["GITHUB_SHA"]' in workflow
    assert 'aggregate["shard_count"]==shard_count' in workflow
    assert 'aggregate["generated"]==aggregate["canonicalized"]' in workflow
    assert 'aggregate["collisions"]==0' in workflow
    assert "--aggregate-scope mutation-manifests" in workflow
    assert "--aggregate-preflight-evidence retained-preflight/mutation-preflight.json" in workflow
    assert '--calibration-id "$CALIBRATION_ID"' in workflow


def test_authoritative_check_binds_candidate_and_probe_cannot_qualify():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    prepare_job = workflow.split("\n  prepare:", 1)[1].split("\n  preflight:", 1)[0]
    aggregate_job = workflow.split("\n  aggregate:", 1)[1]

    assert "github.event.inputs.mode != 'binding-probe'" in prepare_job
    assert "Bind authoritative check to exact candidate" in aggregate_job
    assert 'candidate == os.environ["GITHUB_SHA"]' in aggregate_job
    assert "github.event.inputs.mode != 'calibration'" in aggregate_job
    assert '"passed":False' in aggregate_job
    assert "report.get('passed') is True" in aggregate_job


def test_mutation_execution_skips_redundant_preflight_and_schedule_is_preflight_only():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "github.event.inputs.mode == 'preflight'" in workflow
    assert "github.event_name == 'schedule' || github.event.inputs.mode != 'preflight'" not in workflow
    assert "needs: [prepare, preflight-aggregate]" not in workflow
    assert (
        "full-shard:\n    if: github.event_name == 'workflow_dispatch'"
        " && github.event.inputs.mode != 'preflight'"
            " && github.event.inputs.mode != 'diagnostic-canary'"
            " && github.event.inputs.mode != 'staged-preflight'"
            " && github.event.inputs.mode != 'finalize'\n    needs: prepare"
    ) in workflow
    assert workflow.index("Verify retained SHA-bound preflight") < workflow.index("full-shard:")
    assert "MODE='${{ github.event.inputs.mode || 'preflight' }}'" in workflow
    assert "github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'calibration'" in workflow


def test_mutation_hotspot_chunks_preserve_authoritative_worker_bound():
    config = (Path(PLUGIN_DIR) / ".fettle.toml").read_text()

    assert "full_timeout_s = 1800" in config
    assert "full_shards = 256" in config
    assert '"fettle/ci.py" = 20' in config
    assert '"fettle/coverage_gate.py" = 20' in config
    assert '"fettle/doctor.py" = 20' in config
    assert '"fettle/init_cmd.py" = 20' in config
    assert '"fettle/mutation_test.py" = 5' in config
    assert '"fettle/post_edit.py" = 20' in config
    assert '"fettle/project_rules.py" = 10' in config
    assert '"fettle/quality_scan.py" = 2' in config
    assert '"fettle/ratchet.py" = 20' in config
    assert '"fettle/result.py" = 20' in config
    assert '"fettle/security_review.py" = 20' in config
    assert '"fettle/semgrep_util.py" = 1' in config
    assert '"fettle/tool_runner.py" = 10' in config


def test_pr_mutation_runs_cancel_stale_work_but_authoritative_runs_remain_durable():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    containment = (Path(PLUGIN_DIR) / ".github/workflows/mutation-pr.yml").read_text()

    assert "concurrency:" in workflow
    assert "mutation-authoritative" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "cancel-in-progress: true" in containment


def test_mutation_calibration_checkpoints_are_explicit_and_isolated():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "calibration_id:" in workflow
    assert "resume_run_id:" in workflow
    assert 'CALIBRATION_ID: ${{ github.event.inputs.calibration_id }}' in workflow
    assert '--calibration-id "$CALIBRATION_ID"' in workflow
    assert 're.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value)' in workflow
    assert "--checkpoint-output mutation-checkpoint.json" in workflow
    assert "github.event.inputs.mode == 'replay'" in workflow
    assert "|| github.event.inputs.calibration_id }}-${{ matrix.shard }}" in workflow
    assert "if: always()" in workflow
    assert "github.event.inputs.resume_run_id != ''" in workflow
    assert "if: github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'calibration'" in workflow


def test_explicit_calibration_uses_required_pr_check_name_and_enforces_result():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    aggregate_job = workflow.split("\n  aggregate:", 1)[1]

    assert "name: mutation evidence" in aggregate_job
    assert "report.get('passed') is True" in aggregate_job
    assert "mutation (full aggregate, advisory)" not in aggregate_job
    assert "github.event.inputs.mode != 'calibration'" in aggregate_job
    assert '"qualification_executed":False' in aggregate_job


def test_mutation_replay_uses_retained_canonical_corpus():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "fettle mutation run --all" not in workflow
    assert "--resume-manifest mutation-manifests/partition-${{ matrix.shard }}.json" in workflow
    assert "--retained-preflight retained-preflight/mutation-preflight.json" in workflow
    # resume_run_id is free-text dispatch input: it must be validated and must
    # reach the shell only via env indirection, never direct interpolation.
    assert '--calibration-id "replay-${RESUME_RUN_ID:-${{ github.run_id }}}"' in workflow
    assert 'RESUME_RUN_ID: ${{ github.event.inputs.resume_run_id }}' in workflow
    assert 'test "$RESUME_RUN_ID" -eq "$RESUME_RUN_ID"' in workflow
    assert '"replay-${{ github.event.inputs.resume_run_id' not in workflow
    assert "github.event.inputs.mode == 'replay' && format('replay-{0}', github.event.inputs.resume_run_id)" in workflow
    assert "${{ github.event.inputs.resume_run_id != '' && '--resume-checkpoints resume-checkpoints' || '' }}" in workflow
    assert "if: always()\n        uses: actions/upload-artifact@" in workflow


def test_partition_manifest_rejects_tampering(tmp_path, monkeypatch):
    from fettle.mutation_test import load_partition_manifest, write_partition_manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import src.a\n")
    monkeypatch.setattr("fettle.mutation_test._revision", lambda root: "a" * 40)
    paths = write_partition_manifests(
        str(tmp_path), {"paths": ["src/"], "full_shards": 1, "default_chunk_lines": 60},
        tmp_path / "manifests",
    )
    manifest = load_partition_manifest(paths[0])
    assert manifest["ranges"] == [{"file": "src/a.py", "start": 1, "end": 1}]

    value = json.loads(paths[0].read_text())
    value["ranges"][0]["end"] = 2
    paths[0].write_text(json.dumps(value))
    try:
        load_partition_manifest(paths[0])
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("tampered manifest was accepted")


def test_partition_manifest_must_match_configured_shard_count(tmp_path, monkeypatch):
    from fettle.mutation_test import run_mutation_test, write_partition_manifests

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src/a.py").write_text("x = 1\n")
    (tmp_path / "tests/test_a.py").write_text("import src.a\n")
    monkeypatch.setattr("fettle.mutation_test._revision", lambda root: "a" * 40)
    manifest = write_partition_manifests(
        str(tmp_path), {"paths": ["src/"], "full_shards": 1}, tmp_path / "manifests",
    )[0]

    result = run_mutation_test(str(tmp_path), {
        "paths": ["src/"], "all": True, "full_shards": 2, "manifest": str(manifest),
    })

    assert result["status"] == "unknown"
    assert "shard count" in result["message"]


def test_partition_manifest_files_must_match_ranges(tmp_path):
    from fettle.mutation_test import load_partition_manifest

    payload = {
        "schema_version": "1", "revision": "a" * 40, "shard_index": 0,
        "shard_count": 1, "files": ["src/a.py"],
        "ranges": [{"file": "src/b.py", "start": 1, "end": 1}],
    }
    from fettle.mutation_test import _canonical_digest
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({**payload, "digest": _canonical_digest(payload)}))

    try:
        load_partition_manifest(path)
    except ValueError as exc:
        assert "files" in str(exc)
    else:
        raise AssertionError("inconsistent manifest was accepted")
