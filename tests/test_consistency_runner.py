"""P55/SC3 bounded state-consistency execution kernel contracts."""

from __future__ import annotations

import json
import sys
from dataclasses import replace

from fettle.consistency_runner import execute_contract
from fettle.state_consistency import parse_contract


def _contract(
    tmp_path,
    *,
    mutation="mutation",
    canonical="canonical",
    observer="observer",
    model="immediate",
):
    script = tmp_path / "adapter.py"
    script.write_text("""\
import json, sys, time
phase = sys.argv[1]
if phase == "timeout":
    time.sleep(5)
if phase == "fail":
    raise SystemExit(3)
if phase == "malformed":
    print("not-json")
elif phase == "eventual":
    path = "eventual-count.txt"
    try:
        count = int(open(path).read())
    except FileNotFoundError:
        count = 0
    open(path, "w").write(str(count + 1))
    print(json.dumps({"fettle-observation": "v1", "value": "new" if count else "old"}))
elif phase in {"canonical", "observer", "stale"}:
    value = "new" if phase != "stale" else "old"
    print(json.dumps({"fettle-observation": "v1", "value": value}))
else:
    print(json.dumps({"fettle-operation": "v1"}))
""", encoding="utf-8")
    text = f"""\
fettle-consistency: v1
id: account-sync
scope: ["src/**"]
fact: account.name
owner: accounts
consistency: {{model: {model}}}
setup: {{adapter: setup}}
mutation: {{adapter: mutation, retry_safe: false}}
canonical_read: {{adapter: canonical}}
observers: [{{id: api, surface: api, adapter: observer}}]
comparator: {{kind: exact}}
cleanup: {{adapter: cleanup}}
adapters:
  setup: {{kind: command, argv: [{json.dumps(sys.executable)}, adapter.py, setup], timeout_s: 2, output: json-v1}}
  mutation: {{kind: command, argv: [{json.dumps(sys.executable)}, adapter.py, {mutation}], timeout_s: 2, output: json-v1}}
  canonical: {{kind: command, argv: [{json.dumps(sys.executable)}, adapter.py, {canonical}], timeout_s: 2, output: json-v1}}
  observer: {{kind: command, argv: [{json.dumps(sys.executable)}, adapter.py, {observer}], timeout_s: 2, output: json-v1}}
  cleanup: {{kind: command, argv: [{json.dumps(sys.executable)}, adapter.py, cleanup], timeout_s: 2, output: json-v1}}
"""
    contract, findings = parse_contract(text)
    assert contract is not None, [finding.message for finding in findings]
    return contract


def test_executes_phases_in_order_and_records_redacted_observations(tmp_path):
    result = execute_contract(tmp_path, _contract(tmp_path), policy={})

    assert result["outcome"] == "converged"
    assert [operation["phase"] for operation in result["operations"]] == [
        "setup", "mutation", "canonical_read", "observer:api", "cleanup",
    ]
    assert result["canonical_observation"]["fingerprint"]
    assert result["observer_observations"][0]["fingerprint"]
    assert result["observer_observations"][0]["state"] == "converged"
    assert result["observer_observations"][0]["attempts"] == 1
    assert "value" not in result["canonical_observation"]
    assert result["cleanup"]["state"] == "pass"
    assert result["source_revision"]
    assert result["contract_digest"]
    assert result["adapter_digest"]
    assert result["rerun"] == "fettle consistency run account-sync"


def test_mutation_failure_skips_reads_but_still_cleans_up(tmp_path):
    result = execute_contract(tmp_path, _contract(tmp_path, mutation="fail"), policy={})

    assert result["outcome"] == "tool_error"
    assert [operation["phase"] for operation in result["operations"]] == [
        "setup", "mutation", "cleanup",
    ]
    assert result["canonical_observation"] is None
    assert result["observer_observations"] == []
    assert result["cleanup"]["state"] == "pass"


def test_malformed_canonical_output_is_unknown_and_skips_observers(tmp_path):
    result = execute_contract(tmp_path, _contract(tmp_path, canonical="malformed"), policy={})

    assert result["outcome"] == "unknown"
    assert result["primary_error"]["phase"] == "canonical_read"
    assert not any(operation["phase"].startswith("observer:")
                   for operation in result["operations"])
    assert result["cleanup"]["state"] == "pass"


def test_timeout_is_tool_error_and_cleanup_remains_separate(tmp_path):
    contract = _contract(tmp_path, mutation="timeout")
    contract = replace(contract, adapters={
        **contract.adapters,
        "mutation": replace(contract.adapters["mutation"], timeout_s=1),
        "cleanup": replace(contract.adapters["cleanup"], argv=(
            sys.executable, "adapter.py", "fail",
        )),
    })

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "tool_error"
    assert result["primary_error"]["kind"] == "timeout"
    assert result["cleanup"]["state"] == "tool_error"
    assert result["primary_error"]["phase"] == "mutation"


def test_cleanup_only_failure_makes_run_non_pass_without_primary_error(tmp_path):
    contract = _contract(tmp_path)
    contract = replace(contract, adapters={
        **contract.adapters,
        "cleanup": replace(contract.adapters["cleanup"], argv=(
            sys.executable, "adapter.py", "fail",
        )),
    })

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "tool_error"
    assert result["primary_error"] is None
    assert result["cleanup"]["state"] == "tool_error"


def test_cleanup_failure_overrides_divergence_without_becoming_primary_error(tmp_path):
    contract = _contract(tmp_path, observer="stale")
    contract = replace(contract, adapters={
        **contract.adapters,
        "cleanup": replace(contract.adapters["cleanup"], argv=(
            sys.executable, "adapter.py", "fail",
        )),
    })

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "tool_error"
    assert result["observer_observations"][0]["state"] == "divergent"
    assert result["primary_error"] is None
    assert result["cleanup"]["error"]["phase"] == "cleanup"


def test_stale_fixture_retains_distinct_fingerprints_for_p56(tmp_path):
    result = execute_contract(tmp_path, _contract(tmp_path, observer="stale"), policy={})

    assert result["outcome"] == "divergent"
    assert (result["canonical_observation"]["fingerprint"]
            != result["observer_observations"][0]["fingerprint"])


def test_oversized_output_is_bounded_and_non_pass(tmp_path):
    contract = _contract(tmp_path)
    script = tmp_path / "adapter.py"
    script.write_text("import sys; sys.stdout.write('x' * 100000)\n", encoding="utf-8")
    contract = replace(contract, adapters={
        **contract.adapters,
        "mutation": replace(contract.adapters["mutation"], argv=(
            sys.executable, "adapter.py",
        )),
    })

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "tool_error"
    assert result["primary_error"]["kind"] == "oversized_output"
    assert result["cleanup"]["state"] == "tool_error"


def test_path_escape_and_missing_environment_fail_before_mutation(tmp_path):
    contract = _contract(tmp_path)
    escaped = replace(contract, adapters={
        **contract.adapters,
        "mutation": replace(contract.adapters["mutation"], cwd="../outside"),
    })
    missing_env = replace(contract, adapters={
        **contract.adapters,
        "mutation": replace(contract.adapters["mutation"], env=("MISSING_SECRET",)),
    })

    escaped_result = execute_contract(tmp_path, escaped, policy={})
    env_result = execute_contract(tmp_path, missing_env, policy={}, environment={})

    assert escaped_result["outcome"] == "config_error"
    assert env_result["outcome"] == "config_error"
    assert escaped_result["operations"] == []
    assert env_result["operations"] == []


def test_symlinked_working_directory_escape_fails_before_mutation(tmp_path):
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    contract = _contract(tmp_path)
    escaped = replace(contract, adapters={
        **contract.adapters,
        "mutation": replace(contract.adapters["mutation"], cwd="escape"),
    })

    result = execute_contract(tmp_path, escaped, policy={})

    assert result["outcome"] == "config_error"
    assert result["operations"] == []


def test_adapter_receives_only_allowlisted_parent_environment(tmp_path, monkeypatch):
    contract = _contract(tmp_path)
    script = tmp_path / "adapter.py"
    script.write_text("""\
import json, os, sys
if sys.argv[1] == "mutation" and "UNDECLARED_SECRET" in os.environ:
    raise SystemExit(9)
marker = "fettle-observation" if sys.argv[1] in {"canonical", "observer"} else "fettle-operation"
payload = {marker: "v1"}
if marker == "fettle-observation":
    payload["value"] = "safe"
print(json.dumps(payload))
""", encoding="utf-8")
    monkeypatch.setenv("UNDECLARED_SECRET", "must-not-leak")

    result = execute_contract(tmp_path, contract, policy={})

    assert result["primary_error"] is None
    assert result["cleanup"]["state"] == "pass"


def test_eventual_observer_is_polled_until_it_converges(tmp_path):
    contract = replace(
        _contract(tmp_path, observer="eventual", model="eventual"),
        deadline_ms=500,
        poll_interval_ms=10,
    )

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "converged"
    assert result["observer_observations"] == [
        {
            **result["observer_observations"][0],
            "state": "converged",
            "attempts": 2,
        }
    ]
    assert [operation["phase"] for operation in result["operations"]].count(
        "observer:api"
    ) == 2


def test_eventual_polling_reruns_only_mismatching_observers(tmp_path):
    contract = _contract(tmp_path, observer="eventual", model="eventual")
    contract = replace(
        contract,
        deadline_ms=500,
        poll_interval_ms=10,
        observers=(
            {"id": "stable", "surface": "api", "adapter": "stable"},
            {"id": "lagging", "surface": "api", "adapter": "observer"},
        ),
        adapters={
            **contract.adapters,
            "stable": replace(
                contract.adapters["observer"],
                argv=(sys.executable, "adapter.py", "observer"),
            ),
        },
    )

    result = execute_contract(tmp_path, contract, policy={})

    phases = [operation["phase"] for operation in result["operations"]]
    assert result["outcome"] == "converged"
    assert phases.count("observer:stable") == 1
    assert phases.count("observer:lagging") == 2


def test_eventual_observer_that_misses_deadline_is_stale(tmp_path):
    contract = replace(
        _contract(tmp_path, observer="stale", model="eventual"),
        deadline_ms=300,
        poll_interval_ms=100,
    )

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "stale"
    assert result["observer_observations"][0]["state"] == "stale"
    assert result["observer_observations"][0]["attempts"] >= 1
    assert result["observer_observations"][0]["duration_ms"] >= 0


def test_eventual_deadline_during_later_poll_preserves_last_stale_observation(
    tmp_path,
):
    contract = _contract(tmp_path, observer="stale", model="eventual")
    script = tmp_path / "adapter.py"
    script.write_text("""\
import json, pathlib, sys, time
phase = sys.argv[1]
if phase == "stale":
    marker = pathlib.Path("observed-once")
    if marker.exists():
        time.sleep(2)
    marker.write_text("yes")
    print(json.dumps({"fettle-observation": "v1", "value": "old"}))
elif phase in {"canonical", "observer"}:
    print(json.dumps({"fettle-observation": "v1", "value": "new"}))
else:
    print(json.dumps({"fettle-operation": "v1"}))
""", encoding="utf-8")
    contract = replace(contract, deadline_ms=300, poll_interval_ms=10)

    result = execute_contract(tmp_path, contract, policy={})

    assert result["outcome"] == "stale"
    assert result["primary_error"] is None
    assert result["observer_observations"][0]["attempts"] == 1
    assert any(
        operation["state"] == "deadline" for operation in result["operations"]
    )


def test_committed_stale_read_fixture_is_reproducible():
    fixture = (
        __import__("pathlib").Path(__file__).parent
        / "fixtures" / "state_consistency" / "apps"
    )
    contract, findings = parse_contract(
        (fixture / "stale-read.md").read_text(encoding="utf-8")
    )
    assert contract is not None, [finding.message for finding in findings]

    result = execute_contract(fixture, contract, policy={})

    assert result["outcome"] == "divergent"
    assert (result["canonical_observation"]["fingerprint"]
            != result["observer_observations"][0]["fingerprint"])
    assert not (fixture / "state.json").exists()
