"""WP-109 — Config Protection Gate contract tests.

PreToolUse(Write|Edit) hook that warns/blocks when agent modifies linter configs.
"""

import contextlib
import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)


def _run_hook(
    file_path: str,
    cwd: str | None = None,
    tool_name: str = "Edit",
    env_overrides: dict | None = None,
) -> tuple[int, dict | None, str]:
    """Run config_protect.py, return (rc, parsed_json, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    input_data = {
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": file_path},
        "cwd": cwd or "/tmp/test-project",
        "session_id": "test-session",
    }
    proc = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "config_protect.py")],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    output = None
    if proc.stdout.strip():
        with contextlib.suppress(json.JSONDecodeError):
            output = json.loads(proc.stdout.strip())
    return proc.returncode, output, proc.stderr


class TestBlocksConfigModification:
    def test_blocks_eslintrc_modification(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".eslintrc.json").write_text("{}")
        rc, out, _ = _run_hook(str(proj / ".eslintrc.json"), cwd=str(proj))
        assert rc == 0  # advisory default
        assert out is not None
        assert "Fix the code" in out["hookSpecificOutput"]["additionalContext"]

    def test_blocks_ruff_toml_modification(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "ruff.toml").write_text("[lint]\nselect = ['ALL']\n")
        rc, out, _ = _run_hook(str(proj / "ruff.toml"), cwd=str(proj))
        assert rc == 0
        assert out is not None

    def test_blocks_prettierrc(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".prettierrc").write_text("{}")
        rc, out, _ = _run_hook(str(proj / ".prettierrc"), cwd=str(proj))
        assert rc == 0
        assert out is not None

    def test_blocks_biome_json(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "biome.json").write_text("{}")
        rc, out, _ = _run_hook(str(proj / "biome.json"), cwd=str(proj))
        assert rc == 0
        assert out is not None

    def test_blocks_editorconfig(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / ".editorconfig").write_text("[*]\nindent_style = space\n")
        rc, out, _ = _run_hook(str(proj / ".editorconfig"), cwd=str(proj))
        assert rc == 0
        assert out is not None


class TestAllowsCreation:
    def test_allows_eslintrc_creation(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        # File does NOT exist yet
        rc, out, _ = _run_hook(str(proj / ".eslintrc.json"), cwd=str(proj))
        assert rc == 0
        assert out is None

    def test_allows_ruff_toml_creation(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        rc, out, _ = _run_hook(str(proj / "ruff.toml"), cwd=str(proj))
        assert rc == 0
        assert out is None


class TestPyprojectToml:
    def test_pyproject_only_triggers_on_tool_sections(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[tool.ruff]\nselect = ['ALL']\n")
        rc, out, _ = _run_hook(str(proj / "pyproject.toml"), cwd=str(proj))
        assert rc == 0
        assert out is not None

    def test_pyproject_allows_metadata_changes(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        # pyproject without tool.ruff/mypy/pyright sections
        (proj / "pyproject.toml").write_text("[project]\nname = 'foo'\nversion = '1.0'\n")
        rc, out, _ = _run_hook(str(proj / "pyproject.toml"), cwd=str(proj))
        assert rc == 0
        assert out is None


class TestAdvisoryMode:
    def test_advisory_mode_warns_not_blocks(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text('[gates.config_protect]\nenabled = true\nmode = "advisory"\n')
        (proj / ".eslintrc.json").write_text("{}")
        rc, out, _ = _run_hook(str(proj / ".eslintrc.json"), cwd=str(proj))
        assert rc == 0
        assert out is not None


class TestEnforceMode:
    def test_enforce_mode_blocks(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text('[gates.config_protect]\nenabled = true\nmode = "enforce"\n')
        (proj / ".eslintrc.json").write_text("{}")
        rc, out, _ = _run_hook(str(proj / ".eslintrc.json"), cwd=str(proj))
        assert rc == 2
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestAllowPatterns:
    def test_allow_patterns_override(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text('[gates.config_protect]\nenabled = true\nallow_patterns = [".eslintrc*"]\n')
        (proj / ".eslintrc.json").write_text("{}")
        rc, out, _ = _run_hook(str(proj / ".eslintrc.json"), cwd=str(proj))
        assert rc == 0
        assert out is None


class TestDisabled:
    def test_disabled_allows_all(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.config_protect]\nenabled = false\n")
        (proj / ".eslintrc.json").write_text("{}")
        rc, out, _ = _run_hook(str(proj / ".eslintrc.json"), cwd=str(proj))
        assert rc == 0
        assert out is None


class TestMalformedInput:
    def test_malformed_stdin_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, "config_protect.py")],
            input="not json",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0

    def test_non_config_file_ignored(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / "main.py").write_text("x = 1")
        rc, out, _ = _run_hook(str(proj / "main.py"), cwd=str(proj))
        assert rc == 0
        assert out is None
