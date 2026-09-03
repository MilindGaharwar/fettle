import tomllib
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_default_install_includes_every_python_runtime_capability():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    assert set(project["dependencies"]) == {
        "mutmut==2.5.1",
        "playwright>=1.40",
        "pytest>=7.0",
        "pyyaml>=6.0",
        "ruff>=0.4.0",
        "semgrep>=1.168",
    }


def test_capability_extras_remain_compatible():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        extras = tomllib.load(stream)["project"]["optional-dependencies"]

    assert extras["mutation"] == ["mutmut==2.5.1"]
    assert extras["evals"] == ["pyyaml>=6.0"]
    assert extras["uat"] == ["playwright>=1.40"]
    assert extras["semgrep"] == ["semgrep>=1.168"]
    assert extras["all"] == ["finefettle[dev]"]


def test_wheel_build_declares_every_owned_resource_family():
    setup = (ROOT / "setup.py").read_text()
    manifest = (ROOT / "MANIFEST.in").read_text()

    for resource in ("_rules", "_templates", "_commands", "_bridge", "PROVENANCE.md"):
        assert f'"{resource}"' in setup
    assert 'src_rules.rglob("*")' in setup
    assert "recursive-include rules *.yaml" in manifest
