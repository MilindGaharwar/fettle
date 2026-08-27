import tomllib
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_default_install_contains_complete_python_toolkit():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    names = {dependency.split("[", 1)[0].split("=", 1)[0].split(">", 1)[0] for dependency in project["dependencies"]}
    assert names == {
        "deptry", "mutmut", "playwright", "pre-commit", "pyright",
        "pytest", "pyyaml", "ruff", "semgrep",
    }


def test_legacy_capability_extras_are_compatible_aliases():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        extras = tomllib.load(stream)["project"]["optional-dependencies"]

    assert extras == {
        "dev": [], "mutation": [], "semgrep": [], "evals": [],
        "uat": [], "all": [],
    }


def test_wheel_build_declares_every_owned_resource_family():
    setup = (ROOT / "setup.py").read_text()
    manifest = (ROOT / "MANIFEST.in").read_text()

    for resource in ("_rules", "_templates", "_commands", "_bridge", "PROVENANCE.md"):
        assert f'"{resource}"' in setup
    assert 'src_rules.rglob("*")' in setup
    assert "recursive-include rules *.yaml" in manifest
