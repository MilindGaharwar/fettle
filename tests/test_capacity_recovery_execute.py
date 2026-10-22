import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


SCRIPT = Path(__file__).parents[1] / ".github/scripts/capacity_recovery_execute.py"
SPEC = importlib.util.spec_from_file_location("capacity_recovery_execute", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_ordered_membership_retains_source_order():
    assert MODULE._ordered_membership(["tests/b.py", "tests/a.py"], ["tests/a.py", "tests/b.py"]) == [
        "tests/a.py", "tests/b.py",
    ]


@pytest.mark.parametrize(
    ("recorded", "actual"),
    [
        (["tests/a.py", "tests/a.py"], ["tests/a.py"]),
        (["tests/a.py"], ["tests/b.py"]),
        ([], ["tests/a.py"]),
        (["tests/a.py"], [""]),
    ],
)
def test_ordered_membership_rejects_duplicates_or_substitution(recorded, actual):
    with pytest.raises(ValueError, match="membership"):
        MODULE._ordered_membership(recorded, actual)


def test_adapter_reorders_temporary_corpus_and_rebinds_source_result(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    plan_path = tmp_path / "plan.json"
    corpus_path = tmp_path / "corpus.json"
    result_path = tmp_path / "result.json"
    checkpoint_path = tmp_path / "checkpoint.json"
    environment_path = tmp_path / "environment.json"
    original_plan = {
        "digest": "a" * 64,
        "units": [{
            "file": "fettle/a.py", "fingerprints": ["f" * 64],
            "mapped_tests": ["tests/a.py", "tests/b.py"],
            "environment_digest": "e" * 64,
        }],
    }
    original_corpus = {
        "corpus": [{
            "fingerprint": "f" * 64,
            "mapped_tests": ["tests/b.py", "tests/a.py"],
        }],
    }
    plan_path.write_text(json.dumps(original_plan))
    corpus_path.write_text(json.dumps(original_corpus))

    def frozen_runner(root, cfg, adapted_plan_path, adapted_corpus_path, unit, timeout, checkpoint):
        adapted_plan = json.loads(adapted_plan_path.read_text())
        adapted_corpus = json.loads(adapted_corpus_path.read_text())
        assert adapted_corpus["corpus"][0]["mapped_tests"] == ["tests/a.py", "tests/b.py"]
        assert adapted_plan["digest"] != original_plan["digest"]
        return {
            "plan_digest": adapted_plan["digest"], "unit": original_plan["units"][0],
            "status": "completed", "digest": "temporary",
        }

    argv = [
        "capacity_recovery_execute.py", "--source-root", str(source),
        "--plan", str(plan_path), "--corpus", str(corpus_path), "--unit", "0",
        "--timeout", "720", "--result", str(result_path),
        "--checkpoint", str(checkpoint_path),
        "--environment-evidence", str(environment_path),
    ]
    with (
        patch.object(sys, "argv", argv),
        patch.object(MODULE, "load_config", return_value={"mutation": {"test_mappings": {}}}),
        patch.object(MODULE, "_mapped_tests", return_value={
            "fettle/a.py": ["tests/a.py", "tests/b.py"],
        }),
        patch.object(MODULE, "run_capacity_validation_unit", side_effect=frozen_runner),
        patch("fettle.mutation_test._runtime_cache_identity", return_value={
            "inputs": {
                "engine": {"name": "mutmut", "version": "2.5.1"},
                "environment": {"python": "3.12.13", "platform": "Linux-x86_64"},
                "dependencies": [{"name": "example", "version": "1"}],
            },
        }),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        assert MODULE.main() == 0

    result = json.loads(result_path.read_text())
    assert result["plan_digest"] == original_plan["digest"]
    assert result["digest"] == MODULE._canonical_digest({
        key: value for key, value in result.items() if key != "digest"
    })
    assert json.loads(corpus_path.read_text()) == original_corpus
    evidence = json.loads(environment_path.read_text())
    assert evidence["captured_before_mutation"] is True
    assert evidence["digest"] == "e" * 64
