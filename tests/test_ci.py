"""`fettle ci` — composed gate + generated workflow (CI enforcement WP-2)."""

import os
import subprocess
import sys
import tempfile
import json
from pathlib import Path

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR))

from fettle import ci  # noqa: E402
from fettle.quality_scan import ToolScanResult  # noqa: E402
from fettle.result import ResultStatus  # noqa: E402

SYNTH_AWS = "AKIAZ7Q3M5N8P2K4R6T9"


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
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
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
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qam", "base"],
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
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base"],
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
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "audited"],
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

    assert "timeout-minutes: 12" in workflow
    assert "prepare:" in workflow
    assert "fromJSON(needs.prepare.outputs.matrix)" in workflow
    assert "--manifest" in workflow
    assert "shard: [0, 1," not in workflow
    assert "--paths fettle/" not in workflow
    assert "--shard-count 240" not in workflow
    assert "if: always()" in workflow


def test_changed_mutation_workflow_transports_non_authoritative_native_cache():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "actions/cache/restore@" in workflow
    assert "actions/cache/save@" in workflow
    assert "path: .fettle/mutation-cache" in workflow
    assert "restore-keys:" in workflow
    assert "fettle mutation run --changed" in workflow
    assert workflow.index("actions/cache/restore@") < workflow.index("fettle mutation run --changed")
    assert workflow.index("fettle mutation run --changed") < workflow.index("actions/cache/save@")


def test_changed_mutation_workflow_preseeds_timeout_evidence_and_truthful_summary():
    workflow = (Path(PLUGIN_DIR) / ".github/workflows/mutation.yml").read_text()

    assert "--initialize-timeout-report mutation-report.json" in workflow
    assert "--initialize-timeout-report mutation-report.json --timeout 600" in workflow
    assert "name: Changed-scope mutation evidence\n        timeout-minutes: 10" in workflow
    assert workflow.index("--initialize-timeout-report") < workflow.index("fettle mutation run --changed")
    assert "--github-summary mutation-report.json" in workflow
    assert "mutation-evidence-${{ github.run_id }}" in workflow
    assert "if-no-files-found: error" in workflow


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
