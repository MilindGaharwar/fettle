import tomllib
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_default_install_has_no_runtime_dependencies():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    assert project["dependencies"] == []


def test_all_extra_composes_every_optional_capability():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        extras = tomllib.load(stream)["project"]["optional-dependencies"]

    assert extras["mutation"] == ["mutmut==2.5.1"]
    assert extras["evals"] == ["pyyaml>=6.0"]
    assert extras["uat"] == ["playwright>=1.40"]
    assert {dependency.removeprefix("finefettle[").removesuffix("]") for dependency in extras["all"]} == {
        "dev", "mutation", "semgrep", "evals", "uat",
    }


def test_wheel_build_declares_every_owned_resource_family():
    setup = (ROOT / "setup.py").read_text()
    manifest = (ROOT / "MANIFEST.in").read_text()

    for resource in ("_rules", "_templates", "_commands", "_bridge", "PROVENANCE.md"):
        assert f'"{resource}"' in setup
    assert 'src_rules.rglob("*")' in setup
    assert "recursive-include rules *.yaml" in manifest
