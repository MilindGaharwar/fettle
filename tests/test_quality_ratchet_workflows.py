from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]


def _workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text())


def _scripts(workflow: dict) -> str:
    return "\n".join(
        step.get("run", "")
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    )


def test_ci_and_release_use_the_same_quality_ratchet_policy_and_verifier():
    ci_workflow = _workflow("ci.yml")
    ci = _scripts(ci_workflow)
    release = _scripts(_workflow("release.yml"))
    command = "python -m fettle.quality_ratchet"
    policy = ".github/quality-ratchet.json"

    assert f"{command} types --policy {policy}" in ci
    assert f"{command} coverage --policy {policy}" in ci
    assert f"{command} types --policy {policy}" in release
    assert f"{command} coverage --policy {policy}" in release
    assert "mypy fettle --ignore-missing-imports || true" not in ci
    advisory = ci_workflow["jobs"]["typecheck"]
    assert advisory["continue-on-error"] is True
    assert command in _scripts({"jobs": {"typecheck": advisory}})


def test_coverage_collection_enables_existing_subprocess_instrumentation():
    ci = _scripts(_workflow("ci.yml"))
    release = _scripts(_workflow("release.yml"))

    for scripts in (ci, release):
        assert "mv .coverage .coverage.main" in scripts
        assert "coverage run --rcfile=.github/coverage-subprocess.toml" in scripts
        assert "tests/test_quality_ratchet_subprocess.py" in scripts
        assert "coverage combine" in scripts
        assert "coverage json" in scripts

    subprocess_config = (ROOT / ".github" / "coverage-subprocess.toml").read_text()
    assert 'patch = ["subprocess"]' in subprocess_config
    assert "parallel = true" in subprocess_config
