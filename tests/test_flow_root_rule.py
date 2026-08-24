"""Contract tests for the test-flow-root-cwd semgrep rule (llm-antipatterns).

Shard-201 lesson: a mutated configuration default made a test invoke
run_mutation_test(".") against the repository root, deleting the live
mutmut cache mid-run. The rule forbids cwd-relative roots in mutation-flow
calls inside test functions while leaving production entry points alone.
"""

import json
import os
import subprocess

import pytest

RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules"
)
RULE_FILE = os.path.join(RULES_DIR, "llm-antipatterns.yml")
RULE_ID = "test-flow-root-cwd"


def _has_semgrep() -> bool:
    try:
        probe = subprocess.run(
            ["semgrep", "--version"], capture_output=True, timeout=5
        )
        return probe.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")


def _findings(target_file: str) -> list[dict]:
    result = subprocess.run(
        ["semgrep", "--config", RULE_FILE, "--json", "--quiet", target_file],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode in (0, 1), result.stderr
    data = json.loads(result.stdout)
    return [
        finding for finding in data.get("results", [])
        if finding.get("check_id", "").endswith(RULE_ID)
    ]


def test_flags_cwd_root_in_test_function(tmp_path):
    target = tmp_path / "test_bad.py"
    target.write_text(
        "def test_uses_dot_root(tmp_path):\n"
        "    result = run_mutation_test('.', {'paths': ['src/']})\n"
    )

    findings = _findings(str(target))

    assert len(findings) == 1


def test_all_guarded_flow_entry_points_fire(tmp_path):
    body = "".join([
        "def test_each_flow(dot=None):\n",
        "    aggregate_shards('.', [])\n"
        "    write_timeout_evidence('.', 60)\n"
        "    save_mutation_native_cache('.', {})\n"
        "    restore_mutation_native_cache('.', {})\n"
        "    prepare_shard_replay_matrix('.', 4)\n"
        "    run_resumable_mutation_shard('.', {}, '.', '.', 'id', '.')\n",
    ])
    target = tmp_path / "test_many.py"
    target.write_text(body)

    assert len(_findings(str(target))) == 6


def test_isolated_tmp_path_root_is_clean(tmp_path):
    target = tmp_path / "test_good.py"
    target.write_text(
        "def test_isolated(tmp_path):\n"
        "    result = run_mutation_test(str(tmp_path), {'paths': ['src/']})\n"
    )

    assert _findings(str(target)) == []


def test_production_caller_outside_test_function_is_clean(tmp_path):
    target = tmp_path / "cli_like.py"
    target.write_text(
        "def cmd_mutation(args):\n"
        "    return run_mutation_test('.', {'paths': args.paths})\n"
    )

    assert _findings(str(target)) == []
