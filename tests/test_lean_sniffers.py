"""WP-106 — Tiered Lean Review: Tier 1 Deterministic Sniffers.

PostToolUse(Write|Edit) hook that silently detects over-engineering patterns
and records candidates to session state JSONL. No output, always exits 0.
"""

import contextlib
import json
import os
import subprocess
import sys
import textwrap
import time

SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)
HOOK_SCRIPT = os.path.join(SCRIPTS_DIR, "lean_sniffers.py")


def _run_hook(
    file_path: str,
    cwd: str | None = None,
    session_id: str = "test-session",
    env_overrides: dict | None = None,
) -> tuple[int, str, str]:
    """Run lean_sniffers.py, return (rc, stdout, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    input_data = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path},
        "cwd": cwd or "/tmp/test-project",
        "session_id": session_id,
    }
    proc = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _read_state(state_dir: str, session_id: str = "test-session") -> list[dict]:
    """Read all candidates from session JSONL state file."""
    path = os.path.join(state_dir, "sessions", f"{session_id}.lean.jsonl")
    if not os.path.exists(path):
        return []
    candidates = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                with contextlib.suppress(json.JSONDecodeError):
                    candidates.append(json.loads(line))
    return candidates


class TestLR001DependencyAdded:
    """LR001: Detects new dependencies added to manifest files."""

    def test_lr001_detects_new_pip_dependency(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        req = proj / "requirements.txt"
        req.write_text("flask==3.0.0\n")
        _git_add_commit(proj, "initial")
        # Add a new dependency
        req.write_text("flask==3.0.0\nhttpx==0.27.0\n")
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "sessions").mkdir()

        rc, stdout, _ = _run_hook(
            str(req),
            cwd=str(proj),
            env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)},
        )
        assert rc == 0
        assert stdout == ""
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR001_DEPENDENCY_ADDED" for c in candidates)

    def test_lr001_detects_new_npm_dependency(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        pkg = proj / "package.json"
        pkg.write_text('{\n  "dependencies": {\n    "react": "^18.0.0"\n  }\n}\n')
        _git_add_commit(proj, "initial")
        pkg.write_text('{\n  "dependencies": {\n    "react": "^18.0.0",\n    "lodash": "^4.17.21"\n  }\n}\n')
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "sessions").mkdir()

        rc, stdout, _ = _run_hook(
            str(pkg),
            cwd=str(proj),
            env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)},
        )
        assert rc == 0
        assert stdout == ""
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR001_DEPENDENCY_ADDED" for c in candidates)

    def test_lr001_ignores_existing_unchanged_deps(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        req = proj / "requirements.txt"
        req.write_text("flask==3.0.0\nhttpx==0.27.0\n")
        _git_add_commit(proj, "initial")
        # No change — just re-write same content
        req.write_text("flask==3.0.0\nhttpx==0.27.0\n")
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "sessions").mkdir()

        _run_hook(
            str(req),
            cwd=str(proj),
            env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)},
        )
        candidates = _read_state(str(state_dir))
        assert not any(c["sniffer_id"] == "LR001_DEPENDENCY_ADDED" for c in candidates)


class TestLR002NewAbstractionName:
    """LR002: Detects classes/functions with abstraction-heavy names."""

    def test_lr002_detects_factory_class(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "src.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        f.write_text("class PaymentStrategyFactory:\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR002_NEW_ABSTRACTION_NAME" for c in candidates)

    def test_lr002_detects_manager_function(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "utils.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        f.write_text("def create_session_manager():\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR002_NEW_ABSTRACTION_NAME" for c in candidates)

    def test_lr002_ignores_test_files(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        tests = proj / "tests"
        tests.mkdir()
        f = tests / "test_factory.py"
        f.write_text("class TestPaymentFactory:\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert not any(c["sniffer_id"] == "LR002_NEW_ABSTRACTION_NAME" for c in candidates)


class TestLR003PassThroughWrapper:
    """LR003: Detects functions that only delegate to one call."""

    def test_lr003_detects_passthrough_wrapper(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "service.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        f.write_text(textwrap.dedent("""\
            def get_user(user_id):
                return client.get_user(user_id)
        """))
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR003_PASS_THROUGH_WRAPPER" for c in candidates)

    def test_lr003_skips_function_with_validation(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "service.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        f.write_text(textwrap.dedent("""\
            def get_user(user_id):
                if not user_id:
                    raise ValueError("missing")
                return client.get_user(user_id)
        """))
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert not any(c["sniffer_id"] == "LR003_PASS_THROUGH_WRAPPER" for c in candidates)


class TestLR004SingleMethodClass:
    """LR004: Detects classes with only one real method."""

    def test_lr004_detects_single_method_class(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "validator.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        f.write_text(textwrap.dedent("""\
            class TokenValidator:
                def validate(self, token):
                    return token == "ok"
        """))
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR004_SINGLE_METHOD_CLASS" for c in candidates)

    def test_lr004_skips_exception_classes(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "errors.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        f.write_text(textwrap.dedent("""\
            class ValidationError(Exception):
                pass
        """))
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert not any(c["sniffer_id"] == "LR004_SINGLE_METHOD_CLASS" for c in candidates)


class TestLR008LargeAddition:
    """LR008: Detects unusually large additions."""

    def test_lr008_detects_large_addition(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "big.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        # 130 lines of code
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(130)) + "\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR008_LARGE_ADDITION" for c in candidates)

    def test_lr008_respects_configurable_threshold(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.lean_review.tier1.thresholds]\nlarge_added_lines = 200\n")
        f = proj / "medium.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        # 150 lines — below custom threshold of 200
        f.write_text("\n".join(f"x_{i} = {i}" for i in range(150)) + "\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert not any(c["sniffer_id"] == "LR008_LARGE_ADDITION" for c in candidates)


class TestLR012DuplicateHelperName:
    """LR012: Detects new function names that already exist elsewhere in repo."""

    def test_lr012_detects_duplicate_helper_name(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        existing = proj / "utils.py"
        existing.write_text("def parse_bool(value):\n    return value == 'true'\n")
        _git_add_commit(proj, "initial")
        new_file = proj / "config.py"
        new_file.write_text("def parse_bool(value):\n    return value.lower() in ('1', 'true')\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(new_file), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert any(c["sniffer_id"] == "LR012_DUPLICATE_LOCAL_HELPER_NAME" for c in candidates)

    def test_lr012_skips_on_git_grep_timeout(self, tmp_path) -> None:
        """If git grep is unavailable or times out, sniffer skips gracefully."""
        proj = tmp_path / "proj"
        proj.mkdir()
        # No git init — git grep will fail
        f = proj / "helpers.py"
        f.write_text("def parse_bool(v):\n    return v == 'yes'\n")
        state_dir = _make_state_dir(tmp_path)

        rc, stdout, _ = _run_hook(
            str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)}
        )
        assert rc == 0
        # Should not crash, may or may not produce LR012 (no git = skip)
        candidates = _read_state(str(state_dir))
        assert not any(c["sniffer_id"] == "LR012_DUPLICATE_LOCAL_HELPER_NAME" for c in candidates)


class TestHookBehavior:
    """Hook-level contracts: silent, exit 0, state recording."""

    def test_silent_no_stdout_no_stderr(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "x.py"
        f.write_text("class BigFactory:\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        rc, stdout, stderr = _run_hook(
            str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)}
        )
        assert rc == 0
        assert stdout == ""
        assert stderr == ""

    def test_exits_zero_always(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        f = proj / "bad.py"
        f.write_text("class MegaOrchestratorFactory:\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        rc, _, _ = _run_hook(
            str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)}
        )
        assert rc == 0

    def test_skips_non_implementation_files(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "readme.md"
        f.write_text("# Big Factory Pattern\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert candidates == []

    def test_skips_ignored_paths(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        nm = proj / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        f = nm / "index.js"
        f.write_text("class BigFactory {}\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert candidates == []

    def test_skips_large_files(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "huge.py"
        f.write_text("x = 1\n" * 100000)  # ~600KB
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert candidates == []

    def test_respects_disabled_config(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        cfg = proj / ".fettle.toml"
        cfg.write_text("[gates.lean_review]\nenabled = false\n")
        f = proj / "factory.py"
        f.write_text("class MegaFactory:\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        assert candidates == []

    def test_appends_to_session_state(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "a.py"
        f.write_text("")
        _git_add_commit(proj, "initial")
        state_dir = _make_state_dir(tmp_path)

        # First edit
        f.write_text("class FooFactory:\n    pass\n")
        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        # Second edit — different file
        g = proj / "b.py"
        g.write_text("class BarManager:\n    pass\n")
        _run_hook(str(g), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})

        candidates = _read_state(str(state_dir))
        assert len(candidates) >= 2


class TestRobustness:
    """Edge cases: malformed input, missing files, no git."""

    def test_malformed_stdin_exits_zero(self) -> None:
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input="not json at all",
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 0
        assert proc.stdout == ""

    def test_missing_file_exits_zero(self, tmp_path) -> None:
        state_dir = _make_state_dir(tmp_path)
        rc, stdout, _ = _run_hook(
            "/nonexistent/path/foo.py",
            cwd=str(tmp_path),
            env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)},
        )
        assert rc == 0
        assert stdout == ""

    def test_no_git_falls_back_to_whole_file(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        # No git init
        f = proj / "factory.py"
        f.write_text("class MegaFactory:\n    pass\n")
        state_dir = _make_state_dir(tmp_path)

        _run_hook(str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)})
        candidates = _read_state(str(state_dir))
        # Should still detect via whole-file fallback
        assert any(c["sniffer_id"] == "LR002_NEW_ABSTRACTION_NAME" for c in candidates)

    def test_ast_parse_failure_skips_ast_sniffers(self, tmp_path) -> None:
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "broken.py"
        f.write_text("def foo(\n")  # invalid syntax
        state_dir = _make_state_dir(tmp_path)

        rc, _, _ = _run_hook(
            str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)}
        )
        assert rc == 0

    def test_self_aborts_on_timeout(self, tmp_path) -> None:
        """Hook should complete within budget even on moderately large files."""
        proj = tmp_path / "proj"
        proj.mkdir()
        _init_git(proj)
        f = proj / "big.py"
        # 50 functions — enough to exercise sniffers without git grep per function
        lines = [f"def _func_{i}():\n    return {i}\n" for i in range(50)]
        f.write_text("\n".join(lines))
        _git_add_commit(proj, "initial")
        # Make a change to trigger sniffers
        f.write_text("\n".join(lines) + "\ndef new_thing():\n    return 1\n")
        state_dir = _make_state_dir(tmp_path)

        start = time.monotonic()
        rc, _, _ = _run_hook(
            str(f), cwd=str(proj), env_overrides={"FETTLE_LEAN_STATE_DIR": str(state_dir)}
        )
        elapsed = time.monotonic() - start
        assert rc == 0
        assert elapsed < 3.0  # generous; includes Python startup + git


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _init_git(path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(path), check=True)


def _git_add_commit(path, msg: str = "commit") -> None:
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg, "--allow-empty"], cwd=str(path), check=True)


def _make_state_dir(tmp_path) -> str:
    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "sessions").mkdir(exist_ok=True)
    return str(state_dir)
