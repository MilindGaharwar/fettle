"""`fettle ci` — composed gate + generated workflow (CI enforcement WP-2)."""

import os
import subprocess
import sys
import tempfile

PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))

import ci  # noqa: E402

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
