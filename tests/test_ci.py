"""`fettle ci` — composed gate + generated workflow (CI enforcement WP-2)."""

import os
import hashlib
import shutil
import subprocess
import sys
import tempfile
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR))

from fettle import ci  # noqa: E402
from fettle.quality_scan import ToolScanResult  # noqa: E402
from fettle.result import ResultStatus  # noqa: E402
from scripts.staged_preflight import combine_accounting  # noqa: E402

SYNTH_AWS = "AKIAZ7Q3M5N8P2K4R6T9"


def _run_actions_bash(script, *, cwd, env):
    return subprocess.run(
        ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", script],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def _python_heredoc(script):
    marker = "python - <<'PY'\n"
    return script.split(marker, 1)[1].split("\nPY", 1)[0]


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
    assert "name: mutation-calibration-stage-${{ github.event.inputs.stage_1_run_id }}" in workflow
    assert "name: mutation-calibration-stage-${{ github.event.inputs.stage_2_run_id }}" in workflow
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
    assert "fail-fast: false" in workflow
    readback = workflow.split("\n  evidence-readback:", 1)[1]
    assert "github.event.inputs.calibration_stage != '3'" in readback


def test_finalization_rejects_non_allowlisted_or_mode_changes():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    finalization = workflow.split("Prove evidence-only finalization head", 1)[1].split(
        "Download stage 1 mutation evidence", 1,
    )[0]

    assert '"docs/completion/audit-hardening.json"' in finalization
    assert '"docs/final-candidate-readiness.md"' in finalization
    assert '"docs/completion/evidence/external/audit-hardening/run-05-locator.json"' in finalization
    assert '"docs/completion/evidence/external/audit-hardening"' not in finalization
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
    assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in staged
    assert "if: always()\n        uses: actions/upload-artifact@" in staged
    assert "monitor-final-status.txt" in staged
    assert "cancellation-attempt.json" in staged
    assert "gh workflow run staged-preflight-continuation.yml" in staged
    assert '--repo "$GITHUB_REPOSITORY" --ref "$GITHUB_REF_NAME"' in staged
    assert "source_plan_sha256" in staged
    assert "merge-multiple: true" not in staged


def test_staged_handoff_commands_bind_repo_ref_and_unified_successor(tmp_path):
    mutation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    continuation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    sender_steps = mutation["jobs"]["staged-dispatch-continuation"]["steps"]
    dispatch = next(
        step["run"] for step in sender_steps
        if step.get("name") == "Dispatch immutable continuation"
    )
    receiver_steps = continuation["jobs"]["prepare"]["steps"]
    bind = next(
        step["run"] for step in receiver_steps
        if step.get("name") == "Bind unified candidate and orchestration identity"
    )

    workspace = tmp_path / "workspace"
    control = workspace / "control"
    control.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=control, check=True)
    (control / "identity.txt").write_text("successor")
    subprocess.run(["git", "add", "identity.txt"], cwd=control, check=True)
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
         "commit", "-qm", "successor"], cwd=control, check=True,
    )
    candidate = workspace / "candidate"
    subprocess.run(["git", "clone", "-q", str(control), str(candidate)], check=True)
    control_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=control, text=True,
    ).strip()
    candidate_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=candidate, text=True,
    ).strip()
    assert control_sha == candidate_sha

    (workspace / "source-plan").mkdir()
    (workspace / "source-plan/staged-preflight-plan.json").write_text("{}\n")
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    capture = workspace / "gh-args.txt"
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$GH_CAPTURE\"\n")
    gh.chmod(0o755)
    (bin_dir / "python").symlink_to(sys.executable)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_CAPTURE": str(capture),
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_REF_NAME": "repair-branch",
        "GITHUB_SHA": candidate_sha,
        "GITHUB_RUN_ID": "37",
        "GITHUB_WORKFLOW_REF": "owner/repo/.github/workflows/mutation.yml@refs/heads/repair-branch",
    }

    subprocess.run(dispatch, cwd=workspace, env=env, shell=True, check=True)

    args = capture.read_text().splitlines()
    assert args[:7] == [
        "workflow", "run", "staged-preflight-continuation.yml",
        "--repo", "owner/repo", "--ref", "repair-branch",
    ]
    fields = {
        key: value
        for flag, assignment in zip(args[7::2], args[8::2])
        for key, value in [assignment.split("=", 1)]
        if flag == "-f"
    }
    assert fields == {
        "candidate_sha": candidate_sha,
        "source_run_id": "37",
        "source_orchestration_sha": candidate_sha,
        "source_plan_sha256": __import__("hashlib").sha256(b"{}\n").hexdigest(),
        "source_workflow_ref": env["GITHUB_WORKFLOW_REF"],
    }

    expanded_bind = bind.replace(
        '${{ github.event.inputs.candidate_sha }}', candidate_sha
    )
    subprocess.run(
        expanded_bind, cwd=workspace,
        env={**env, "GITHUB_SHA": control_sha, "CANDIDATE_SHA": candidate_sha},
        shell=True, check=True,
    )

    rejected = subprocess.run(
        expanded_bind, cwd=workspace,
        env={**env, "GITHUB_SHA": "f" * 40, "CANDIDATE_SHA": candidate_sha},
        shell=True,
    )
    assert rejected.returncode != 0


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

    batches = [f"wave-3-batch-{index}" for index in range(1, 8)]
    admissions = [f"wave-3-admission-{index}" for index in range(1, 7)]
    assert set(jobs) == {
        "prepare", "launch-gate", *batches, *admissions, "monitor", "validate",
        "aggregate", "readback", "terminal-accounting",
    }
    assert sum("strategy" in job for job in jobs.values()) == 7
    assert len(jobs) == 20
    assert workflow.count("strategy:") == 7
    assert workflow.count("max-parallel: 8") == 7
    assert jobs["wave-3-batch-1"]["needs"] == ["prepare", "launch-gate"]
    for index in range(1, 7):
        assert jobs[f"wave-3-admission-{index}"]["needs"] == [
            "prepare", "launch-gate" if index == 1 else f"wave-3-admission-{index - 1}",
        ]
        assert jobs[f"wave-3-batch-{index + 1}"]["needs"] == [
            "prepare", f"wave-3-admission-{index}",
        ]
        matrix = jobs[f"wave-3-batch-{index + 1}"]["strategy"]["matrix"]
        assert matrix == f"${{{{ fromJSON(needs.wave-3-admission-{index}.outputs.matrix) }}}}"
    assert jobs["validate"]["needs"] == ["prepare", "wave-3-batch-7", "monitor"]
    assert jobs["monitor"]["needs"] == "wave-3-admission-6"
    monitor_steps = jobs["monitor"]["steps"]
    prior = next(
        step for step in monitor_steps
        if step.get("name") == "Download preceding admission accounting"
    )
    assert prior["with"]["name"] == (
        "mutation-continuation-admission-6-${{ github.run_id }}-${{ github.run_attempt }}"
    )
    monitor = next(
        step["run"] for step in monitor_steps
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    assert "historical_args=(--historical-accounting prior-admission/admission-budget.json)" in monitor
    for index in range(1, 7):
        steps = jobs[f"wave-3-admission-{index}"]["steps"]
        names = [step.get("name") for step in steps]
        assert names.index("Observe batch and enforce cumulative global budget") < names.index(
            "Wait for admitted artifact inventory"
        ) < names.index("Download admitted reports") < names.index(
            "Validate terminal evidence and emit next matrix"
        )
        observe = next(
            step["run"] for step in steps
            if step.get("name") == "Observe batch and enforce cumulative global budget"
        )
        assert "admission-budget-non-pass" in observe
        assert "admission-shard-failure" in observe
        assert "admission-observer-error" in observe
        assert "admission-observer-deadline" in observe
        assert "observer_deadline=" in observe
        assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' not in observe
        assert names[0] == "Arm fail-closed admission containment"
        arm = steps[0]["run"]
        assert "armed-through-diagnostics-retention" in arm
        assert "admission-containment-armed.txt" in arm
        assert "admission-observer-started-at.txt" in arm
        disarm_index = names.index("Disarm admission containment after retained success")
        retain_index = names.index("Retain admission evidence")
        assert disarm_index > names.index("Validate terminal evidence and emit next matrix")
        assert disarm_index > retain_index
        cancel_index = names.index("Request cancellation after retaining admission diagnostics")
        assert cancel_index > retain_index
        cancel = steps[cancel_index]
        assert cancel["if"] == "always()"
        assert "admission-containment-armed.txt" in cancel["run"]
        assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in cancel["run"]
    assert "workflow_dispatch:" in workflow
    assert "candidate_sha:" in workflow
    assert "source_plan_sha256:" in workflow
    assert "fresh-continuation-plan" in workflow
    assert "--prior-run-id ${{ github.event.inputs.source_run_id }}" in workflow
    assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in workflow
    assert "if: always()\n        uses: actions/upload-artifact@" in workflow
    assert "monitor-final-status.txt" in workflow
    assert "cancellation-attempt.json" in workflow
    assert 'source_uncertainty=api' in workflow
    assert 'source_uncertainty=accounting' in workflow
    assert 'reason="persistent-source-${source_uncertainty}-uncertainty"' in workflow
    assert '"status == \\"completed\\"' not in workflow
    assert '.status == "completed" and .conclusion == "success"' in workflow
    assert "--aggregate-preflight staged-reports --shard-count 256" in workflow
    assert "staged-wave-1" not in workflow
    assert "staged-wave-2" not in workflow


def test_staged_admission_production_shell_fragments_parse():
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )

    for index in range(1, 7):
        steps = workflow["jobs"][f"wave-3-admission-{index}"]["steps"]
        for step in steps:
            if "run" not in step:
                continue
            result = subprocess.run(
                ["bash", "-n"], input=step["run"], text=True,
                capture_output=True,
            )
            assert result.returncode == 0, f"batch {index} {step.get('name')}: {result.stderr}"


def test_staged_preflight_budget_gates_are_cumulative_across_both_runs():
    first = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    continuation = (
        Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml"
    ).read_text()

    assert "--next-wave wave-2 --output wave-1-budget.json" in first
    assert "--next-wave wave-3 --output wave-2-budget.json" in first
    assert '--next-wave complete --output "$budget_snapshot"' in first
    assert '--observed-at "$observed_at" --job-timeout-minutes 35' in first
    assert 'historical_args+=(--historical-accounting "$prior_budget")' in first
    assert "--prior-jobs source-jobs.json" in continuation
    assert "--prior-run-id ${{ github.event.inputs.source_run_id }}" in continuation
    assert continuation.count("--next-wave complete") == 9
    assert continuation.count('cp "$budget" admission-budget.json') == 6
    assert continuation.count("--job-timeout-minutes 35") == 7
    assert '--observed-at "$observed_at" --job-timeout-minutes 35' in continuation
    assert 'historical_args+=(--historical-accounting "$prior_budget")' in continuation
    assert first.count("--historical-accounting monitor-accounting/monitor-budget.json") == 1
    assert continuation.count("--historical-accounting monitor-accounting/monitor-budget.json") == 2
    assert 'assert result["billing_authority"] is False' in first
    assert "Operational ceiling, not a guaranteed provider billing cap." not in first


def test_staged_monitor_cancellation_is_repo_bound_from_workspace_root(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    steps = workflow["jobs"]["staged-monitor"]["steps"]
    cancel = next(
        step["run"] for step in steps
        if step.get("name") == "Request cancellation after retaining diagnostics"
    )
    workspace = tmp_path / "workspace"
    (workspace / "control").mkdir(parents=True)
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    capture = workspace / "gh-args.txt"
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$GH_CAPTURE\"\n")
    gh.chmod(0o755)
    (workspace / "cancellation-requested.txt").write_text("operational-cutoff\n")
    result = _run_actions_bash(
        cancel, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GH_CAPTURE": str(capture),
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "37",
        },
    )

    assert result.returncode == 2
    assert capture.read_text().splitlines() == [
        "api", "--method", "POST", "repos/owner/repo/actions/runs/37/cancel",
    ]
    assert (workspace / "cancellation-final-status.txt").read_text() == "accepted\n"


def test_staged_monitor_surfaces_cancellation_api_failure(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    steps = workflow["jobs"]["monitor"]["steps"]
    cancel = next(
        step["run"] for step in steps
        if step.get("name") == "Request cancellation after retaining diagnostics"
    )
    workspace = tmp_path / "workspace"
    (workspace / "control").mkdir(parents=True)
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nexit 23\n")
    gh.chmod(0o755)
    (workspace / "cancellation-requested.txt").write_text("persistent-accounting-uncertainty\n")
    result = _run_actions_bash(
        cancel, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "37",
        },
    )

    assert result.returncode == 23
    assert (workspace / "cancellation-final-status.txt").read_text() == "api-failure-23\n"


def test_staged_monitor_lifecycle_resamples_and_retains_each_snapshot(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    steps = workflow["jobs"]["staged-monitor"]["steps"]
    monitor = next(
        step["run"] for step in steps
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    fixtures = workspace / "fixtures"
    fixtures.mkdir()
    fixture = json.loads(
        (Path(PLUGIN_DIR) / "tests/fixtures/staged_preflight_runner_acquisition.json").read_text()
    )
    assert fixture["provenance"]["kind"] == "reconstructed_runner_acquisition_sequence"
    assert "precise original trigger is uncertain" in fixture["provenance"]["limitation"]
    states = fixture["states"]
    started = datetime.now(UTC) - timedelta(seconds=2)
    completed = started + timedelta(seconds=1)
    for state in states:
        if state["started_at"] is not None:
            state["started_at"] = started.isoformat().replace("+00:00", "Z")
        if state["completed_at"] is not None:
            state["completed_at"] = completed.isoformat().replace("+00:00", "Z")
    for sample, state in enumerate(states, 1):
        jobs = [
            {
                "id": index, "run_id": 37, "run_attempt": 1,
                "name": f"mutation (staged preflight wave 2 shard {index})",
                **state,
            }
            for index in range(32)
        ]
        (fixtures / f"{sample}.json").write_text(json.dumps([{
            "total_count": len(jobs), "jobs": jobs,
        }]))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "n=$(cat \"$GH_COUNTER\" 2>/dev/null || echo 0)\n"
        "n=$((n + 1)); [ \"$n\" -gt 5 ] && n=5\n"
        "printf '%s' \"$n\" > \"$GH_COUNTER\"\n"
        "cat \"$GH_FIXTURES/$n.json\"\n"
    )
    gh.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GH_COUNTER": str(workspace / "counter"),
            "GH_FIXTURES": str(fixtures),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert (workspace / "monitor-final-status.txt").read_text() == "completed\n"
    assert not (workspace / "cancellation-requested.txt").exists()
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 5
    assert json.loads((workspace / "monitor-budget.json").read_text())["passed"] is True
    assert len(list((workspace / "monitor-snapshots").glob("budget-*.json"))) == 4
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json.observed-at"))) == 5


def test_staged_monitor_replays_exact_retained_timestamp_revision_lifecycle(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["staged-monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    source = Path(PLUGIN_DIR) / "tests/fixtures/staged_preflight_accounting_revision"
    fixtures = workspace / "fixtures"
    fixtures.mkdir()
    for index in range(1, 4):
        shutil.copy2(source / f"jobs-{index}.json", fixtures / f"{index}.json")
    shutil.copy2(source / "jobs-terminal.json", fixtures / "4.json")
    observations = [
        item["observed_at"] for item in json.loads(
            (Path(PLUGIN_DIR) / "tests/fixtures/staged_preflight_accounting_revision.json").read_text()
        )["observations"]
    ] + ["2026-10-08T15:13:16.532084+00:00"]
    (workspace / "observations.txt").write_text("\n".join(observations) + "\n")
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "n=$(cat \"$GH_COUNTER\" 2>/dev/null || echo 0)\n"
        "n=$((n + 1)); [ \"$n\" -gt 4 ] && n=4\n"
        "printf '%s' \"$n\" > \"$GH_COUNTER\"\n"
        "cat \"$GH_FIXTURES/$n.json\"\n"
    )
    gh.chmod(0o755)
    python = bin_dir / "python"
    python.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = -c ] && printf '%s' \"$2\" | grep -q 'datetime.now'; then\n"
        "  sed -n \"$(cat \"$GH_COUNTER\")p\" \"$OBSERVATIONS\"\n"
        "else\n"
        f"  exec {sys.executable} \"$@\"\n"
        "fi\n"
    )
    python.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "GH_COUNTER": str(workspace / "counter"),
            "GH_FIXTURES": str(fixtures),
            "OBSERVATIONS": str(workspace / "observations.txt"),
            "GITHUB_REPOSITORY": "MilindGaharwar/fettle",
            "GITHUB_RUN_ID": "37795579761", "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert (workspace / "monitor-final-status.txt").read_text() == "completed\n"
    budgets = [
        json.loads(path.read_text())
        for path in sorted((workspace / "monitor-snapshots").glob("budget-*.json"))
    ]
    assert len(budgets) == 4
    assert [
        next(job for job in report.get("included_jobs", []) if job["id"] == 113377920861)["minutes"]
        for report in budgets[:3]
    ] == [0.12, 0.38, 0.65]
    assert all(report["passed"] is True for report in budgets)
    assert budgets[-1]["estimated_runner_minutes"] >= max(
        report["estimated_runner_minutes"] for report in budgets[:-1]
    )
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 4
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json.observed-at"))) == 4
    assert not (workspace / "cancellation-requested.txt").exists()


def test_staged_monitor_persistent_malformed_metadata_requests_cancellation(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    steps = workflow["jobs"]["staged-monitor"]["steps"]
    monitor = next(
        step["run"] for step in steps
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    malformed = workspace / "malformed.json"
    malformed.write_text(json.dumps([{"total_count": 1, "jobs": [{
        "id": 1, "run_id": 37, "run_attempt": 1,
        "name": "mutation (staged preflight wave 2 shard 0)",
        "status": "queued", "conclusion": None,
        "started_at": None, "completed_at": None,
        "runner_id": 10, "runner_name": None,
        "runner_group_id": None, "runner_group_name": None, "steps": [],
    }]}]))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\ncat \"$GH_FIXTURE\"\n")
    gh.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GH_FIXTURE": str(malformed),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0
    assert (workspace / "monitor-final-status.txt").read_text() == (
        "persistent-accounting-uncertainty\n"
    )
    assert (workspace / "cancellation-requested.txt").is_file()
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 3
    assert not list((workspace / "monitor-snapshots").glob("budget-*.json"))
    attempt = json.loads((workspace / "cancellation-attempt.json").read_text())
    assert attempt == {
        "repository": "owner/repo", "run_id": "37",
        "reason": "persistent-accounting-uncertainty", "status": "pending",
    }


def test_staged_monitor_malformed_json_is_resampled_then_requests_cancellation(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["staged-monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\nprintf '%s\\n' '{not-json'\n")
    gh.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0
    assert (workspace / "monitor-final-status.txt").read_text() == (
        "persistent-accounting-uncertainty\n"
    )
    assert len(list((workspace / "monitor-snapshots").glob("jobs-*.json"))) == 3


def test_staged_monitor_budget_crossing_requests_cancellation(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["staged-monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    started = (datetime.now(UTC) - timedelta(minutes=36)).isoformat().replace("+00:00", "Z")
    jobs = [{
        "id": index, "run_id": 37, "run_attempt": 1,
        "name": f"mutation (staged preflight wave 2 shard {index})",
        "status": "in_progress", "conclusion": None,
        "started_at": started, "completed_at": None,
        "runner_id": index + 1, "runner_name": f"runner-{index}",
        "runner_group_id": 0, "runner_group_name": "GitHub Actions",
        "steps": [{"name": "work", "status": "in_progress", "conclusion": None}],
    } for index in range(32)]
    fixture = workspace / "jobs.json"
    fixture.write_text(json.dumps([{"total_count": 32, "jobs": jobs}]))
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text("#!/bin/sh\ncat \"$GH_FIXTURE\"\n")
    gh.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "GH_FIXTURE": str(fixture),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
            "GITHUB_RUN_ATTEMPT": "1",
        },
    )

    assert result.returncode == 0
    assert (workspace / "monitor-final-status.txt").read_text() == "operational-cutoff\n"
    budget = json.loads((workspace / "monitor-budget.json").read_text())
    assert budget["launch_ceiling"] == 1120
    assert budget["passed"] is False
    assert (workspace / "cancellation-requested.txt").is_file()


def test_continuation_monitor_reuses_validated_source_snapshot(tmp_path):
    workflow = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    monitor = next(
        step["run"] for step in workflow["jobs"]["monitor"]["steps"]
        if step.get("name") == "Stop on failure or exhausted execution budget"
    ).replace("${{ github.event.inputs.source_run_id }}", "36")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "control").symlink_to(PLUGIN_DIR, target_is_directory=True)
    completed = datetime.now(UTC)
    started = completed - timedelta(seconds=1)

    def job(index, run_id, name):
        return {
            "id": index, "run_id": run_id, "run_attempt": 1, "name": name,
            "status": "completed", "conclusion": "success",
            "started_at": started.isoformat().replace("+00:00", "Z"),
            "completed_at": completed.isoformat().replace("+00:00", "Z"),
            "runner_id": index + 1, "runner_name": f"runner-{index}",
            "runner_group_id": 0, "runner_group_name": "GitHub Actions",
            "steps": [{"name": "work", "status": "completed", "conclusion": "success"}],
        }

    source = workspace / "source.json"
    source.write_text(json.dumps([{"total_count": 1, "jobs": [job(1, 36, "source support")]}]))
    current_jobs = [
        job(index + 100, 37, f"mutation (continuation shard {index})")
        for index in range(216)
    ]
    current = workspace / "current.json"
    current.write_text(json.dumps([{"total_count": 216, "jobs": current_jobs}]))
    (workspace / "prior-admission").mkdir()
    prior_accounting = {
        **combine_accounting(
            source, current,
            expected_prior_run_id="36", expected_prior_run_attempt="1",
            expected_current_run_id="37", expected_current_run_attempt="1",
        ),
        "launch_ceiling": 1120,
        "next_wave": "complete",
        "passed": True,
    }
    (workspace / "prior-admission/admission-budget.json").write_text(
        json.dumps(prior_accounting)
    )
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        "case \"$*\" in\n"
        "  */runs/36/*) printf x >> \"$SOURCE_CALLS\"; cat \"$SOURCE_FIXTURE\" ;;\n"
        "  *) cat \"$CURRENT_FIXTURE\" ;;\n"
        "esac\n"
    )
    gh.chmod(0o755)

    result = _run_actions_bash(
        monitor, cwd=workspace,
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{Path(sys.executable).parent}:{os.environ['PATH']}",
            "SOURCE_CALLS": str(workspace / "source-calls"),
            "SOURCE_FIXTURE": str(source), "CURRENT_FIXTURE": str(current),
            "GITHUB_REPOSITORY": "owner/repo", "GITHUB_RUN_ID": "37",
        },
    )

    assert result.returncode == 0, result.stderr
    assert (workspace / "source-calls").read_text() == "x"
    assert (workspace / "source-jobs.json").read_bytes() == source.read_bytes()
    assert (workspace / "monitor-final-status.txt").read_text() == "completed\n"
    assert not (workspace / "cancellation-requested.txt").exists()
    assert len(list((workspace / "monitor-snapshots").glob("current-budget-*.json"))) == 1
    assert len(list((workspace / "monitor-snapshots").glob("current-jobs-*.json.observed-at"))) == 1


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
        " && github.event.inputs.mode != 'finalize'"
        " && !(github.event.inputs.mode == 'calibration' && github.event.inputs.calibration_stage == '3')"
        "\n    needs: [prepare, calibration-launch-gate]"
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


def test_calibration_has_sparse_provenance_budget_monitor_and_terminal_accounting():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "plan-calibration-continuation" in workflow
    assert "calibration-source-provenance.json" in workflow
    assert "calibration-resume-bundle-${{ github.run_id }}" in workflow
    assert "name: mutation (calibration launch gate)" in workflow
    assert "name: mutation (monitor calibration budget)" in workflow
    assert "--cancellation-reserve 1200" in workflow
    assert 'gh api --method POST "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/cancel"' in workflow
    assert "needs: [prepare, calibration-launch-gate]" in workflow
    assert "EXPECTED_SHARDS: ${{ needs.prepare.outputs.execution_matrix }}" in workflow
    assert '[[ "$terminal" -eq "$expected" ]] && break' in workflow
    assert "Retain monitor accounting before cancellation" in workflow
    assert "steps.monitor.outcome" in workflow
    assert "steps.retain-monitor.outcome" in workflow
    assert "job_timeout_minutes=35" in workflow
    assert '"calibration_id":os.environ["CALIBRATION_ID"]' in workflow
    assert "cp prior-accounting/calibration-monitor-budget.json prior-accounting/calibration-accounting.json" in workflow
    assert 'print(report["charged_runner_minutes"])' in workflow
    assert 'retained["charged_runner_minutes"]' in workflow
    assert 'sources[-1].get("expected_run_id")==os.environ["BASE_RUN_ID"]' in workflow
    assert 'accounting.get("calibration_id")==os.environ["CALIBRATION_ID"]' in workflow
    assert "needs: [prepare, calibration-launch-gate]" in workflow
    assert "fail-fast: false" in workflow
    accounting = workflow.split("\n  calibration-accounting:", 1)[1].split("\n  aggregate:", 1)[0]
    assert "if: always()" in accounting
    assert "billing_authority" in accounting
    assert "from datetime import datetime, timezone" in accounting
    assert "job_timeout_minutes=35" in accounting
    assert "Download stage 3 admission accounting floors" in accounting
    assert "retain_historical_accounting_floor(current, admission_floors)" in accounting


def test_stage_3_calibration_uses_seven_output_gated_fixed_batches():
    workflow = yaml.safe_load((Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text())
    jobs = workflow["jobs"]

    batch_names = [f"calibration-stage-3-batch-{number}" for number in range(1, 8)]
    admission_names = [f"calibration-stage-3-admit-{number}" for number in range(2, 8)]
    assert all(name in jobs for name in batch_names + admission_names)
    assert jobs[batch_names[0]]["needs"] == ["prepare", "calibration-launch-gate"]
    for number in range(2, 8):
        batch = jobs[f"calibration-stage-3-batch-{number}"]
        admission = jobs[f"calibration-stage-3-admit-{number}"]
        assert admission["if"].startswith("always()")
        assert admission["needs"] == ["prepare", f"calibration-stage-3-batch-{number - 1}"]
        assert batch["needs"] == ["prepare", f"calibration-stage-3-admit-{number}"]
        assert batch["strategy"]["max-parallel"] == 32
    assert "calibration_stage == '3'" in jobs["full-shard"]["if"]
    assert jobs["calibration-stage-3-batch-7"] in [jobs[name] for name in batch_names]


def test_calibration_reusable_workflows_preserve_worker_and_containment_contracts():
    shard = (Path(PLUGIN_DIR) / ".github/workflows/mutation-calibration-shard.yml").read_text()
    admission = (Path(PLUGIN_DIR) / ".github/workflows/mutation-calibration-admission.yml").read_text()

    assert 'python-version: "3.12.13"' in shard
    assert "--timeout 1740 --json" in shard
    assert "retention-days: 90" in shard
    assert 'if [[ -n "${{ inputs.resume_run_id }}" ]]' in shard
    assert '--resume-checkpoints "calibration-resume/resume-checkpoints/' in shard
    assert "select_shard_subset_attempts" in admission
    assert "if report.get(\"shard_index\") in completed_prefix" in admission
    assert "retain_historical_accounting_floor" in admission
    assert "--paginate --slurp" in admission
    assert "completed_prefix = [index for batch in fixed[:completed_batches] for index in batch]" in admission
    assert "a later batch report exists before admission" in admission
    assert "select_shard_subset_attempts(reports, 256, completed_prefix)" in admission
    assert "steps.validate.outcome != 'success' || steps.retain.outcome != 'success'" in admission
    assert 'cancel" || true' in admission


def test_staged_preflight_publishes_consumer_aliases_with_provenance():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()

    assert "preflight-publication.json" in workflow
    assert "mutation-manifests-${{ github.run_id }}" in workflow
    assert "mutation-preflight-${{ github.run_id }}" in workflow
    assert '"candidate_sha": "${{ github.event.inputs.candidate_sha }}"' in workflow
    assert '"source_run_id": "${{ github.event.inputs.source_run_id }}"' in workflow
    assert "Download published consumer aliases" in workflow
    assert 'published_aggregate.read_bytes() == Path("retained/mutation-preflight.json").read_bytes()' in workflow
    assert 'preflight_completion.read_bytes() == Path("retained/staged-preflight-continuation.json").read_bytes()' in workflow
    assert 'publication["manifest_count"] == len(manifests) == 256' in workflow

    consumer = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    assert "assert preflight_attestation.is_file() and manifest_attestation.is_file()" in consumer
    assert 'publication.get("manifest_count") == len(manifests) == 256' in consumer
    assert 'publication.get("manifest_topology_sha256") == topology' in consumer
    assert 'publication.get("publication_run_attempt") == "1"' in consumer
    assert 'completion.get("source", {}).get("run_id") == publication["source_run_id"]' in consumer


def test_staged_publication_readback_and_calibration_consumer_delivery_path(tmp_path):
    continuation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/staged-preflight-continuation.yml").read_text()
    )
    mutation = yaml.safe_load(
        (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()
    )
    candidate = "a" * 40
    source_run = "37"
    publication_run = "38"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    manifests = workspace / "staged-plan/mutation-manifests"
    manifests.mkdir(parents=True)
    for index in range(256):
        (manifests / f"partition-{index}.json").write_text(
            json.dumps({"shard_index": index}) + "\n"
        )
    (workspace / "mutation-preflight.json").write_text(json.dumps({
        "status": "completed", "passed": True, "revision": candidate,
        "shard_count": 256, "generated": 256, "canonicalized": 256,
        "collisions": 0,
    }) + "\n")
    (workspace / "staged-preflight-continuation.json").write_text(json.dumps({
        "status": "completed", "passed": True, "kind": "fresh_staged_preflight",
        "candidate_sha": candidate, "source": {"run_id": source_run},
        "origins": {str(index): {"run_id": publication_run} for index in range(256)},
    }) + "\n")

    aggregate_steps = continuation["jobs"]["aggregate"]["steps"]
    publish = next(
        step["run"] for step in aggregate_steps
        if step.get("name") == "Build provenance-bound consumer publication"
    )
    publish = (
        publish.replace("${{ github.event.inputs.candidate_sha }}", candidate)
        .replace("${{ github.event.inputs.source_run_id }}", source_run)
        .replace("${{ github.run_id }}", publication_run)
        .replace("${{ github.run_attempt }}", "1")
    )
    bin_dir = workspace / "bin"
    bin_dir.mkdir()
    python = bin_dir / "python"
    python.symlink_to(sys.executable)
    subprocess.run(
        ["/bin/bash", "-e", "-c", publish], cwd=workspace,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}, check=True,
    )

    retained = workspace / "retained"
    retained.mkdir()
    for name in ("mutation-preflight.json", "staged-preflight-continuation.json"):
        shutil.copy2(workspace / name, retained / name)
    published = workspace / "published"
    manifest_alias = published / f"mutation-manifests-{publication_run}"
    preflight_alias = published / f"mutation-preflight-{publication_run}"
    shutil.copytree(workspace / "published-manifests", manifest_alias)
    preflight_alias.mkdir(parents=True)
    for name in (
        "mutation-preflight.json", "preflight-publication.json",
        "staged-preflight-continuation.json",
    ):
        shutil.copy2(workspace / name, preflight_alias / name)

    readback_steps = continuation["jobs"]["readback"]["steps"]
    readback = next(
        step["run"] for step in readback_steps
        if step.get("name") == "Verify downloaded aggregate and origin record"
    )
    readback = (
        readback.replace("${{ github.event.inputs.candidate_sha }}", candidate)
        .replace("${{ github.event.inputs.source_run_id }}", source_run)
        .replace("${{ github.run_id }}", publication_run)
    )
    subprocess.run([sys.executable, "-c", _python_heredoc(readback)], cwd=workspace, check=True)
    assert json.loads((workspace / "readback-checksums.json").read_text())

    altered_completion = b"{}\n"
    for alias in (manifest_alias, preflight_alias):
        (alias / "staged-preflight-continuation.json").write_bytes(altered_completion)
        attestation = alias / "preflight-publication.json"
        payload = json.loads(attestation.read_text())
        payload["completion_sha256"] = hashlib.sha256(altered_completion).hexdigest()
        attestation.write_text(json.dumps(payload, indent=2) + "\n")
    rejected = subprocess.run(
        [sys.executable, "-c", _python_heredoc(readback)], cwd=workspace,
        capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    for alias in (manifest_alias, preflight_alias):
        shutil.copy2(workspace / "staged-preflight-continuation.json", alias)
        shutil.copy2(workspace / "preflight-publication.json", alias)

    shutil.copytree(manifest_alias, workspace / "mutation-manifests")
    shutil.copytree(preflight_alias, workspace / "retained-preflight")
    prepare_steps = mutation["jobs"]["prepare"]["steps"]
    consume = next(
        step["run"] for step in prepare_steps
        if step.get("name") == "Verify retained SHA-bound preflight"
    )
    subprocess.run(
        [sys.executable, "-c", _python_heredoc(consume)], cwd=workspace,
        env={**os.environ, "GITHUB_SHA": candidate, "PREFLIGHT_RUN_ID": publication_run},
        check=True,
    )


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
