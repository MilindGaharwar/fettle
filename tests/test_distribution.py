import tomllib
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_default_install_declares_complete_python_runtime():
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]

    names = {dependency.split("[", 1)[0].split("=", 1)[0].split(">", 1)[0] for dependency in project["dependencies"]}

    assert {
        "deptry", "mutmut", "playwright", "pre-commit", "pyright",
        "pytest", "pyyaml", "ruff", "semgrep",
    } <= names


def test_wheel_build_declares_every_owned_resource_family():
    setup = (ROOT / "setup.py").read_text()

    for resource in ("_rules", "_templates", "_commands", "_bridge"):
        assert f'"{resource}"' in setup
