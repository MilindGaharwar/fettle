import json
import hashlib
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fettle.mutation_test import (
    aggregate_preflight_shards,
    build_calibration_representation_inventory,
    load_mutation_report_candidates,
    read_calibration_representation_inventory,
)
from scripts.staged_preflight import (
    ARTIFACT_RETENTION_DAYS,
    BUDGET,
    CALIBRATION_SUPPORT_BOUNDS,
    CAPACITY_PREPARATION_BUDGET,
    FROZEN_CANDIDATE,
    RECOVERY_ORCHESTRATION_SHA,
    RECOVERY_RUN_ID,
    SOURCE_ORCHESTRATION_SHA,
    SOURCE_REPORT_SHA256,
    SOURCE_RUN_ID,
    SOURCE_WORKFLOW_REF,
    WAVES,
    WAVE_3_BATCHES,
    calibration_observer_contract,
    build_calibration_observer_readiness,
    calibration_stage_3_admitted_shards,
    calibration_stage_3_completed_admissions,
    calibration_stage_3_initial_admission_status,
    calibration_stage_3_observer_contract,
    evaluate_calibration_observer,
    load_api_jobs_pages,
    load_api_workflow_run_pages,
    validate_calibration_observer_readiness,
    validate_readback_probe_admission,
    calibration_stage_3_batches,
    account_runner_minutes,
    combine_accounting,
    build_plan,
    build_continuation_plan,
    build_fresh_continuation_plan,
    build_fresh_completion_record,
    build_recovery_plan,
    build_recovery_record,
    combine_accounting_sources,
    build_calibration_launch_accounting,
    bind_calibration_observer_evidence,
    build_calibration_terminal_accounting,
    combine_calibration_monitor_accounting,
    observed_runner_minutes,
    plan_calibration_continuation,
    evaluate_calibration_budget,
    evaluate_capacity_preparation_admission,
    retain_historical_accounting_floor,
    reserve_bounded_support_minutes,
    validate_wave,
    validate_continuation_topology,
    validate_continuation_artifacts,
    validate_continuation_dispatches,
    validate_continuation_batch,
    validate_source_handoff,
)
from fettle.staged_preflight import (
    build_calibration_accounting_log_envelope,
    calibration_accounting_log_records,
    recover_calibration_accounting_log_envelope,
)

INCIDENT_ROOT = Path(__file__).parent / "fixtures/calibration-terminal-incident"


def _log_envelope_payload():
    return json.dumps({
        "schema_version": "1", "kind": "calibration_budget_decision",
        "passed": False, "billing_authority": False, "stage": "3",
        "calibration_id": "cal-test", "expected_run_id": "700",
        "expected_run_attempt": "1",
        "source_lineage": [{"run_id": "600", "run_attempt": "1"}],
        "terminal_accounting_status": "indeterminate",
    }, indent=2).encode()


def _log_envelope(**overrides):
    values = {
        "repository": "example/fettle", "candidate_sha": "a" * 40,
        "workflow_ref": "example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        "workflow_sha": "a" * 40, "run_id": "700", "run_attempt": "1",
        "calibration_id": "cal-test", "stage": "3",
        "primary_upload_outcome": "failure",
    }
    values.update(overrides)
    return build_calibration_accounting_log_envelope(_log_envelope_payload(), **values)


def _recover_log(text):
    return recover_calibration_accounting_log_envelope(
        text.encode(), repository="example/fettle", candidate_sha="a" * 40,
        workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        workflow_sha="a" * 40, run_id="700", run_attempt="1",
        calibration_id="cal-test", stage="3",
    )


def _log_records(envelope):
    return "\n".join(calibration_accounting_log_records(envelope)) + "\n"


def test_accounting_log_envelope_recovers_exact_bytes_and_identical_retry():
    envelope = _log_envelope()
    records = _log_records(envelope)

    recovered = _recover_log(records + records)

    assert recovered == _log_envelope_payload()


@pytest.mark.parametrize("mutation", ["truncate", "alter", "foreign", "missing"])
def test_accounting_log_envelope_rejects_unavailable_or_inapplicable_records(mutation):
    envelope = _log_envelope()
    records = calibration_accounting_log_records(envelope)
    if mutation == "truncate":
        text = "\n".join(records[:-1]) + "\n"
    elif mutation == "alter":
        record = json.loads(records[0].split(" ", 1)[1])
        record["chunk"] = "x" + record["chunk"][1:]
        text = "FETTLE_CALIBRATION_ACCOUNTING_LOG_V1 " + json.dumps(record) + "\n"
        text += "\n".join(records[1:]) + "\n"
    elif mutation == "foreign":
        record = json.loads(envelope)
        record["repository"] = "other/fettle"
        text = _log_records(json.dumps(record, sort_keys=True, separators=(",", ":")))
    else:
        text = "ordinary log output\n"

    with pytest.raises(ValueError, match="unavailable|malformed|differs|digest"):
        _recover_log(text)


def test_accounting_log_envelope_rejects_conflicting_duplicates():
    records = calibration_accounting_log_records(_log_envelope())
    conflict = json.loads(records[0].split(" ", 1)[1])
    conflict["chunk"] = "x" + conflict["chunk"][1:]
    text = "\n".join(records + [
        "FETTLE_CALIBRATION_ACCOUNTING_LOG_V1 " + json.dumps(conflict),
    ])

    with pytest.raises(ValueError, match="conflicting|malformed"):
        _recover_log(text)


def test_accounting_log_records_bound_each_line_for_maximum_payload():
    payload = json.loads(_log_envelope_payload())
    payload["padding"] = "x" * (250 * 1024)
    envelope = build_calibration_accounting_log_envelope(
        json.dumps(payload).encode(), repository="example/fettle",
        candidate_sha="a" * 40,
        workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
        workflow_sha="a" * 40, run_id="700", run_attempt="1",
        calibration_id="cal-test", stage="3", primary_upload_outcome="failure",
    )

    records = calibration_accounting_log_records(envelope)

    assert len(records) <= 32
    assert max(map(len, records)) < 13 * 1024
    assert _recover_log("\n".join(records) + "\n") == json.dumps(payload).encode()


def test_accounting_log_envelope_rejects_oversized_payload():
    with pytest.raises(ValueError, match="256 KiB"):
        build_calibration_accounting_log_envelope(
            b"x" * (256 * 1024 + 1), repository="example/fettle",
            candidate_sha="a" * 40,
            workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
            workflow_sha="a" * 40, run_id="700", run_attempt="1",
            calibration_id="cal-test", stage="3", primary_upload_outcome="failure",
        )


@pytest.mark.parametrize("lineage", [
    [{"run_id": "1"}],
    [{"run_id": "1", "run_attempt": "1", "extra": "x"}],
    [{"run_id": "1", "run_attempt": "1"}] * 17,
])
def test_accounting_log_envelope_rejects_malformed_or_unbounded_lineage(lineage):
    payload = json.loads(_log_envelope_payload())
    payload["source_lineage"] = lineage

    with pytest.raises(ValueError, match="identity"):
        build_calibration_accounting_log_envelope(
            json.dumps(payload).encode(), repository="example/fettle",
            candidate_sha="a" * 40,
            workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
            workflow_sha="a" * 40, run_id="700", run_attempt="1",
            calibration_id="cal-test", stage="3", primary_upload_outcome="failure",
        )


@pytest.mark.parametrize(("field", "value"), [
    ("expected_run_id", None),
    ("expected_run_id", "701"),
    ("expected_run_attempt", None),
    ("expected_run_attempt", "2"),
])
def test_accounting_log_envelope_requires_explicit_exact_attempt_identity(field, value):
    payload = json.loads(_log_envelope_payload())
    if value is None:
        payload.pop(field)
    else:
        payload[field] = value

    with pytest.raises(ValueError, match="identity"):
        build_calibration_accounting_log_envelope(
            json.dumps(payload).encode(), repository="example/fettle",
            candidate_sha="a" * 40,
            workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
            workflow_sha="a" * 40, run_id="700", run_attempt="1",
            calibration_id="cal-test", stage="3", primary_upload_outcome="failure",
        )


def test_accounting_log_recovery_rejects_whole_log_over_four_mibibytes():
    with pytest.raises(ValueError, match="oversized"):
        recover_calibration_accounting_log_envelope(
            b"x" * (4 * 1024 * 1024 + 1), repository="example/fettle",
            candidate_sha="a" * 40,
            workflow_ref="example/fettle/.github/workflows/mutation.yml@refs/heads/audit",
            workflow_sha="a" * 40, run_id="700", run_attempt="1",
            calibration_id="cal-test", stage="3",
        )


def test_stage_2_observer_contract_covers_two_worker_waves_and_shutdown():
    contract = calibration_observer_contract(32, 16)

    assert contract["worker_waves"] == 2
    assert contract["components"] == {
        "worker_waves_minutes": 70,
        "scheduling_minutes": 5,
        "polling_minutes": 1,
        "publication_minutes": 5,
        "cancellation_minutes": 5,
        "reconciliation_minutes": 5,
        "shutdown_minutes": 9,
    }
    assert contract["observer_deadline_seconds"] == 5460
    assert contract["job_timeout_minutes"] == 100
    assert contract["completion_guaranteed"] is False


@pytest.mark.parametrize(
    ("shards", "parallelism", "waves"),
    [(8, 8, 1), (32, 16, 2), (216, 32, 7), (15, 16, 1)],
)
def test_observer_contract_characterizes_supported_layouts(shards, parallelism, waves):
    assert calibration_observer_contract(shards, parallelism)["worker_waves"] == waves


def test_observer_controlled_clock_completes_successful_multi_wave_layout():
    contract = calibration_observer_contract(32, 16)
    first_wave = [
        {"name": f"mutation (full shard {index}, advisory)", "status": "completed"}
        for index in range(16)
    ]
    second_wave = [
        {"name": f"mutation (full shard {index}, advisory)", "status": "in_progress"}
        for index in range(16, 32)
    ]

    active = evaluate_calibration_observer(
        contract, first_wave + second_wave, elapsed_seconds=2_100, budget_passed=True,
    )
    terminal = evaluate_calibration_observer(
        contract,
        first_wave + [{**job, "status": "completed"} for job in second_wave],
        elapsed_seconds=4_200,
        budget_passed=True,
    )

    assert active["action"] == "continue"
    assert active["terminal_workers"] == 16
    assert terminal["action"] == "complete"
    assert terminal["terminal_workers"] == 32
    assert terminal["completion_guaranteed"] is False


def test_observer_controlled_clock_expires_with_partial_evidence_retained():
    contract = calibration_observer_contract(32, 16)
    jobs = [
        {"name": f"mutation (full shard {index}, advisory)", "status": "completed"}
        for index in range(17)
    ]

    result = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=5_460, budget_passed=True,
    )

    assert result["action"] == "cancel"
    assert result["passed"] is False
    assert result["terminal_workers"] == 17
    assert result["reason"] == (
        "observer deadline expired before all admitted workers became terminal"
    )


def test_stage_3_observer_covers_seven_batches_and_six_admissions():
    contract = calibration_stage_3_observer_contract(WAVES["wave-3"])

    assert contract["worker_waves"] == 7
    assert contract["admission_dependencies"] == 6
    assert contract["components"]["worker_waves_minutes"] == 245
    assert contract["components"]["admission_dependencies_minutes"] == 60
    assert contract["observer_deadline_seconds"] == 326 * 60
    assert contract["job_timeout_minutes"] == 335
    assert contract["completion_guaranteed"] is False


def test_sparse_stage_3_observer_uses_occupied_batches_and_required_admissions():
    selected = [WAVE_3_BATCHES[0][0], WAVE_3_BATCHES[3][0], WAVE_3_BATCHES[6][0]]

    contract = calibration_stage_3_observer_contract(selected)

    assert contract["worker_waves"] == 3
    assert contract["admission_dependencies"] == 6
    assert contract["observer_deadline_seconds"] == (105 + 60 + 21) * 60
    assert contract["job_timeout_minutes"] == 195


def test_sparse_early_stage_3_route_retains_all_actual_admission_dependencies():
    selected = [WAVE_3_BATCHES[0][0]]

    contract = calibration_stage_3_observer_contract(selected)

    assert contract["worker_waves"] == 1
    assert contract["admission_dependencies"] == 6
    assert contract["observer_deadline_seconds"] == (35 + 60 + 21) * 60


def test_stage_3_admission_distinguishes_future_from_missing_terminal_workers():
    selected = [WAVE_3_BATCHES[0][0], WAVE_3_BATCHES[1][0]]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = [{
        "name": f"calibration-stage-3-batch-1 / mutation (full shard {selected[0]}, advisory)",
        "status": "completed",
    }]
    admitted = calibration_stage_3_admitted_shards(selected, jobs)

    result = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=60, budget_passed=True,
        admitted_shards=admitted, completed_admissions=0,
    )

    assert result["missing_terminal_shards"] == []
    assert result["pending_admission_shards"] == [selected[1]]
    assert result["action"] == "continue"


def test_stage_3_observer_ignores_uninstantiated_skipped_matrix_placeholder():
    selected = [WAVE_3_BATCHES[0][0]]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = [{
        "name": "mutation (full shard ${{ matrix.shard }}, advisory)",
        "status": "completed", "conclusion": "skipped", "runner_id": None, "steps": [],
    }]

    result = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=1, budget_passed=True,
        admitted_shards=selected,
    )

    assert result["action"] == "continue"
    assert result["observed_worker_jobs"] == 0
    assert result["missing_terminal_shards"] == selected


def test_stage_3_observer_still_rejects_executed_malformed_worker_identity():
    selected = [WAVE_3_BATCHES[0][0]]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = [{
        "name": "mutation (full shard ${{ matrix.shard }}, advisory)",
        "status": "in_progress", "conclusion": None, "runner_id": 7,
        "steps": [{"name": "worker", "status": "in_progress", "conclusion": None}],
    }]

    with pytest.raises(ValueError, match="malformed worker identity"):
        evaluate_calibration_observer(
            contract, jobs, elapsed_seconds=1, budget_passed=True,
            admitted_shards=selected,
        )


def test_stage_3_successful_admission_extends_exact_observer_identity_set():
    selected = [WAVE_3_BATCHES[0][0], WAVE_3_BATCHES[1][0]]
    jobs = [{
        "name": "calibration-stage-3-admit-2 / mutation (validate calibration batch 1)",
        "status": "completed", "conclusion": "success",
    }]

    assert calibration_stage_3_admitted_shards(selected, jobs) == selected
    assert calibration_stage_3_completed_admissions(jobs) == 1


def test_sparse_stage_3_observer_waits_for_all_actual_admission_handoffs():
    selected = [WAVE_3_BATCHES[0][0]]
    contract = calibration_stage_3_observer_contract(selected)
    worker = {
        "name": f"caller / mutation (full shard {selected[0]}, advisory)",
        "status": "completed",
    }
    waiting = evaluate_calibration_observer(
        contract, [worker], elapsed_seconds=60, budget_passed=True,
        admitted_shards=selected, completed_admissions=1,
    )
    complete = evaluate_calibration_observer(
        contract, [worker], elapsed_seconds=120, budget_passed=True,
        admitted_shards=selected, completed_admissions=6, route_complete=True,
    )

    assert waiting["action"] == "continue"
    assert waiting["pending_admission_shards"] == []
    assert complete["action"] == "complete"


def test_sparse_stage_3_observer_waits_for_terminal_empty_final_batch_node():
    selected = [WAVE_3_BATCHES[0][0]]
    contract = calibration_stage_3_observer_contract(selected)
    worker = {
        "name": f"batch-1 / mutation (full shard {selected[0]}, advisory)",
        "status": "completed",
    }

    waiting = evaluate_calibration_observer(
        contract, [worker], elapsed_seconds=120, budget_passed=True,
        admitted_shards=selected, completed_admissions=6, route_complete=False,
    )
    complete = evaluate_calibration_observer(
        contract, [worker], elapsed_seconds=180, budget_passed=True,
        admitted_shards=selected, completed_admissions=6, route_complete=True,
    )

    assert waiting["action"] == "continue"
    assert waiting["route_complete"] is False
    assert complete["action"] == "complete"


def test_stage_3_observer_rejects_impossible_admission_count():
    contract = calibration_stage_3_observer_contract([WAVE_3_BATCHES[0][0]])

    with pytest.raises(ValueError, match="sample is malformed"):
        evaluate_calibration_observer(
            contract, [], elapsed_seconds=1, budget_passed=True,
            completed_admissions=7,
        )


def test_stage_3_initial_admission_failure_stops_zero_worker_observer_promptly():
    selected = [WAVE_3_BATCHES[0][0]]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = [
        {
            "name": "mutation (publish stage 3 observer readiness)",
            "status": "completed", "conclusion": "success",
        },
        {
            "name": "mutation (require stage 3 observer readiness)",
            "status": "completed", "conclusion": "failure",
        },
    ]

    status = calibration_stage_3_initial_admission_status(jobs)
    result = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=90, budget_passed=True,
        admitted_shards=selected, initial_admission_status=status,
    )

    assert status == "failure"
    assert result["action"] == "cancel"
    assert result["observed_worker_jobs"] == 0
    assert result["reason"] == "initial stage 3 admission failed"


def test_stage_3_initial_admission_remains_pending_until_exact_job_is_terminal():
    producer = {
        "name": "mutation (publish stage 3 observer readiness)",
        "status": "in_progress", "conclusion": None,
    }
    for jobs in ([], [producer], [producer, {
        "name": "mutation (require stage 3 observer readiness)",
        "status": "queued", "conclusion": None,
    }]):
        assert calibration_stage_3_initial_admission_status(jobs) == "pending"


def test_stage_3_missing_initial_admission_fails_after_producer_is_terminal():
    for conclusion in ("success", "failure", "cancelled", "timed_out", "skipped"):
        jobs = [{
            "name": "mutation (publish stage 3 observer readiness)",
            "status": "completed", "conclusion": conclusion,
        }]

        assert calibration_stage_3_initial_admission_status(jobs) == "failure"


def test_stage_3_missing_initial_admission_waits_while_producer_can_progress():
    jobs = [{
        "name": "mutation (publish stage 3 observer readiness)",
        "status": "in_progress", "conclusion": None,
    }]

    assert calibration_stage_3_initial_admission_status(jobs) == "pending"


def test_stage_3_missing_initial_admission_rejects_bad_producer_evidence():
    producer = {
        "name": "mutation (publish stage 3 observer readiness)",
        "status": "completed", "conclusion": "success",
    }
    with pytest.raises(ValueError, match="producer identity is duplicate"):
        calibration_stage_3_initial_admission_status([producer, producer])
    with pytest.raises(ValueError, match="producer state is malformed"):
        calibration_stage_3_initial_admission_status([
            {**producer, "status": "mystery", "conclusion": None},
        ])


def test_stage_3_successful_initial_admission_requires_successful_producer():
    admission = {
        "name": "mutation (require stage 3 observer readiness)",
        "status": "completed", "conclusion": "success",
    }
    with pytest.raises(ValueError, match="producer identity is missing"):
        calibration_stage_3_initial_admission_status([admission])
    for producer in (
        {
            "name": "mutation (publish stage 3 observer readiness)",
            "status": "completed", "conclusion": "failure",
        },
        {
            "name": "mutation (publish stage 3 observer readiness)",
            "status": "in_progress", "conclusion": None,
        },
    ):
        with pytest.raises(ValueError, match="conflicts with readiness producer"):
            calibration_stage_3_initial_admission_status([producer, admission])


def test_stage_3_successful_initial_admission_accepts_exact_successful_producer():
    jobs = [
        {
            "name": "mutation (publish stage 3 observer readiness)",
            "status": "completed", "conclusion": "success",
        },
        {
            "name": "mutation (require stage 3 observer readiness)",
            "status": "completed", "conclusion": "success",
        },
    ]

    assert calibration_stage_3_initial_admission_status(jobs) == "success"


def test_stage_3_initial_admission_rejects_conflicting_or_unknown_job_state():
    producer = {
        "name": "mutation (publish stage 3 observer readiness)",
        "status": "completed", "conclusion": "success",
    }
    job = {
        "name": "mutation (require stage 3 observer readiness)",
        "status": "completed", "conclusion": "success",
    }
    with pytest.raises(ValueError, match="duplicate"):
        calibration_stage_3_initial_admission_status([producer, job, job])
    with pytest.raises(ValueError, match="state is malformed"):
        calibration_stage_3_initial_admission_status([
            producer, {**job, "status": "mystery"},
        ])


def test_observer_readiness_binds_exact_current_attempt_and_monitor_identity():
    produced_at = "2026-10-14T10:00:00Z"
    expected = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "2",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "cal-readback", "stage": "3",
        "artifact_name": "mutation-calibration-observer-ready-700-2",
        "monitor_job_id": 91,
    }
    record = {
        "schema_version": "1", "kind": "calibration_observer_readiness",
        **expected, "ready": True, "produced_at": produced_at,
    }

    validated = validate_calibration_observer_readiness(
        record, **expected, observed_at="2026-10-14T10:01:00Z",
    )

    assert validated == record


def test_observer_readiness_constructor_emits_production_shape():
    record = build_calibration_observer_readiness(
        repository="example/fettle", run_id="700", run_attempt="2",
        candidate_sha="a" * 40, workflow_sha="a" * 40,
        calibration_id="cal-readback",
        artifact_name="mutation-calibration-observer-ready-700-2",
        monitor_job_id=91, produced_at="2026-10-14T10:00:00Z",
    )

    assert record["kind"] == "calibration_observer_readiness"
    assert record["monitor_job_id"] == 91
    assert record["ready"] is True
    assert "probe_only" not in record


def test_observer_readiness_probe_profile_is_explicit_and_exact():
    record = build_calibration_observer_readiness(
        repository="example/fettle", run_id="700", run_attempt="2",
        candidate_sha="a" * 40, workflow_sha="a" * 40,
        calibration_id="probe-readback",
        artifact_name="calibration-readback-probe-ready-700-2",
        monitor_job_id=91, produced_at="2026-10-14T10:00:00Z",
        probe_only=True,
    )

    assert record["probe_only"] is True
    assert record["billing_authority"] is False
    assert record["passed"] is False
    assert record["authoritative_predecessor"] is False
    assert record["qualification_eligible"] is False
    assert validate_calibration_observer_readiness(
        record, repository="example/fettle", run_id="700", run_attempt="2",
        candidate_sha="a" * 40, workflow_sha="a" * 40,
        calibration_id="probe-readback", stage="3",
        artifact_name="calibration-readback-probe-ready-700-2",
        monitor_job_id=91, observed_at="2026-10-14T10:01:00Z",
        probe_only=True,
    ) == record


@pytest.mark.parametrize(
    ("extra_key", "extra_value"),
    [("billing_authority", True), ("passed", True), ("unknown", "value")],
)
def test_observer_readiness_rejects_unknown_or_contradictory_fields(
    extra_key, extra_value,
):
    expected = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "2",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "cal-readback", "stage": "3",
        "artifact_name": "mutation-calibration-observer-ready-700-2",
        "monitor_job_id": 91,
    }
    record = {
        "schema_version": "1", "kind": "calibration_observer_readiness",
        **expected, "ready": True, "produced_at": "2026-10-14T10:00:00Z",
        extra_key: extra_value,
    }

    with pytest.raises(ValueError, match="schema differs"):
        validate_calibration_observer_readiness(
            record, **expected, observed_at="2026-10-14T10:01:00Z",
        )


def test_readback_probe_admission_requires_exact_non_authoritative_schema():
    record = {
        "schema_version": "1", "kind": "calibration_readback_probe_admission",
        "repository": "example/fettle", "run_id": "700", "run_attempt": "1",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "probe-readback", "stage": "3",
        "artifact_name": "mutation-readback-probe-ready-700-1",
        "monitor_job_id": 91, "observed_at": "2026-10-14T10:00:00Z",
        "provider_error_class": "none", "artifact_download_attempt": 1,
        "provider_attempts": [{
            "attempt": 1, "attempted_at": "2026-10-14T10:00:00Z", "outcome": "success",
        }],
        "passed": False, "billing_authority": False, "probe_only": True,
        "authoritative_predecessor": False, "qualification_eligible": False,
        "provider_validation_passed": True,
    }
    arguments = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "1",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "probe_id": "probe-readback", "scenario": "success",
        "artifact_name": "mutation-readback-probe-ready-700-1", "monitor_job_id": 91,
    }

    assert validate_readback_probe_admission(record, **arguments) == record
    for malformed in (
        {**record, "passed": True},
        {**record, "monitor_job_id": 91.0},
        {**record, "unknown": "field"},
        {**record, "provider_attempts": []},
    ):
        with pytest.raises(ValueError):
            validate_readback_probe_admission(malformed, **arguments)


def test_readback_failed_probe_admission_requires_exact_containment():
    record = {
        "schema_version": "1", "kind": "calibration_readback_probe_admission",
        "repository": "example/fettle", "run_id": "700", "run_attempt": "1",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "probe-readback", "stage": "3",
        "artifact_name": "mutation-readback-probe-ready-700-1",
        "monitor_job_id": 91, "observed_at": "2026-10-14T10:00:00Z",
        "provider_error_class": "none", "artifact_download_attempt": 1,
        "provider_attempts": [{
            "attempt": 1, "attempted_at": "2026-10-14T10:00:00Z", "outcome": "success",
        }],
        "passed": False, "billing_authority": False, "probe_only": True,
        "authoritative_predecessor": False, "qualification_eligible": False,
        "provider_validation_passed": True,
        "failure_code": "forced_calibration_identity_mismatch", "failure_class": "ValueError",
    }
    arguments = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "1",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "probe_id": "probe-readback", "scenario": "failed-initial-admission",
        "artifact_name": "mutation-readback-probe-ready-700-1", "monitor_job_id": 91,
    }

    assert validate_readback_probe_admission(record, **arguments) == record
    with pytest.raises(ValueError, match="expected containment"):
        validate_readback_probe_admission(
            {**record, "failure_code": "other"}, **arguments,
        )


@pytest.mark.parametrize("monitor_job_id", [91.0, True, 0, -1])
def test_observer_readiness_constructor_rejects_non_positive_integer_monitor_id(
    monitor_job_id,
):
    with pytest.raises(ValueError, match="monitor job identity is malformed"):
        build_calibration_observer_readiness(
            repository="example/fettle", run_id="700", run_attempt="2",
            candidate_sha="a" * 40, workflow_sha="a" * 40,
            calibration_id="cal-readback",
            artifact_name="mutation-calibration-observer-ready-700-2",
            monitor_job_id=monitor_job_id,
            produced_at="2026-10-14T10:00:00Z",
        )


@pytest.mark.parametrize("monitor_job_id", [91.0, True, 0, -1])
def test_observer_readiness_validator_rejects_malformed_record_monitor_id(
    monitor_job_id,
):
    expected = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "2",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "cal-readback", "stage": "3",
        "artifact_name": "mutation-calibration-observer-ready-700-2",
        "monitor_job_id": 91,
    }
    record = {
        "schema_version": "1", "kind": "calibration_observer_readiness",
        **expected, "monitor_job_id": monitor_job_id,
        "ready": True, "produced_at": "2026-10-14T10:00:00Z",
    }

    with pytest.raises(ValueError, match="monitor job identity is malformed"):
        validate_calibration_observer_readiness(
            record, **expected, observed_at="2026-10-14T10:01:00Z",
        )


def test_jobs_api_pages_require_complete_well_formed_pagination(tmp_path):
    path = tmp_path / "jobs.json"
    jobs = [{"id": 1, "name": "job", "status": "in_progress"}]
    path.write_text(json.dumps([{"total_count": 1, "jobs": jobs}]))

    assert load_api_jobs_pages(path) == jobs

    for malformed in (
        [{"total_count": 2, "jobs": jobs}],
        [{"total_count": True, "jobs": jobs}],
        [{"total_count": 1}],
        [{"total_count": 1, "jobs": ["not-an-object"]}],
        [{"total_count": 1, "jobs": [{"id": True}]}],
        [{"total_count": 1, "jobs": [{"id": 0}]}],
        [],
    ):
        path.write_text(json.dumps(malformed))
        with pytest.raises(ValueError, match="jobs response"):
            load_api_jobs_pages(path)


def test_jobs_api_pages_reject_duplicate_ids_masking_an_omitted_job(tmp_path):
    path = tmp_path / "jobs.json"
    duplicated = {"id": 11, "name": "monitor", "status": "in_progress"}
    path.write_text(json.dumps([
        {"total_count": 2, "jobs": [duplicated]},
        {"total_count": 2, "jobs": [duplicated]},
    ]))

    with pytest.raises(ValueError, match="duplicate job identities"):
        load_api_jobs_pages(path)


@pytest.mark.parametrize(
    "payload",
    [
        '[{"total_count":1,"total_count":1,"jobs":[{"id":1}]}]',
        '[{"total_count":1,"jobs":[],"jobs":[{"id":1}]}]',
        '[{"total_count":1,"jobs":[{"id":1,"id":2}]}]',
    ],
)
def test_jobs_api_pages_reject_duplicate_json_keys(tmp_path, payload):
    path = tmp_path / "jobs.json"
    path.write_text(payload)

    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_api_jobs_pages(path)


def test_workflow_run_pages_require_unique_positive_integer_run_ids(tmp_path):
    path = tmp_path / "runs.json"
    run = {"id": 700, "display_title": "Calibration readback probe probe-one"}
    path.write_text(json.dumps([{"total_count": 1, "workflow_runs": [run]}]))

    assert load_api_workflow_run_pages(path) == [run]

    for malformed in (
        [{"total_count": 1, "workflow_runs": [{"id": True}]}],
        [{"total_count": 1, "workflow_runs": [{"id": 0}]}],
        [{"total_count": 2, "workflow_runs": [run, run]}],
    ):
        path.write_text(json.dumps(malformed))
        with pytest.raises(ValueError, match="workflow_runs response"):
            load_api_workflow_run_pages(path)


@pytest.mark.parametrize(
    ("field", "foreign"),
    [
        ("repository", "foreign/fettle"), ("run_id", "701"),
        ("run_attempt", "1"), ("candidate_sha", "b" * 40),
        ("workflow_sha", "b" * 40), ("calibration_id", "cal-foreign"),
        ("stage", "2"), ("artifact_name", "foreign-artifact"),
        ("monitor_job_id", 92),
    ],
)
def test_observer_readiness_rejects_foreign_identity(field, foreign):
    expected = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "2",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "cal-readback", "stage": "3",
        "artifact_name": "mutation-calibration-observer-ready-700-2",
        "monitor_job_id": 91,
    }
    record = {
        "schema_version": "1", "kind": "calibration_observer_readiness",
        **expected, "ready": True, "produced_at": "2026-10-14T10:00:00Z",
    }
    record[field] = foreign

    with pytest.raises(ValueError, match="identity differs"):
        validate_calibration_observer_readiness(
            record, **expected, observed_at="2026-10-14T10:01:00Z",
        )


@pytest.mark.parametrize(
    "produced_at",
    ["2026-10-14T09:49:59Z", "2026-10-14T10:02:01Z", "not-a-time"],
)
def test_observer_readiness_rejects_stale_future_or_malformed_time(produced_at):
    expected = {
        "repository": "example/fettle", "run_id": "700", "run_attempt": "2",
        "candidate_sha": "a" * 40, "workflow_sha": "a" * 40,
        "calibration_id": "cal-readback", "stage": "3",
        "artifact_name": "mutation-calibration-observer-ready-700-2",
        "monitor_job_id": 91,
    }
    record = {
        "schema_version": "1", "kind": "calibration_observer_readiness",
        **expected, "ready": True, "produced_at": produced_at,
    }

    with pytest.raises(ValueError, match="timestamp"):
        validate_calibration_observer_readiness(
            record, **expected, observed_at="2026-10-14T10:01:00Z",
        )


def test_stage_3_controlled_path_stays_observed_through_all_batches():
    selected = [batch[0] for batch in WAVE_3_BATCHES]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = []

    for batch_number, shard in enumerate(selected, 1):
        admitted = calibration_stage_3_admitted_shards(selected, jobs)
        assert shard in admitted
        active = jobs + [{
            "name": f"batch-{batch_number} / mutation (full shard {shard}, advisory)",
            "status": "in_progress",
        }]
        sample = evaluate_calibration_observer(
            contract, active, elapsed_seconds=batch_number * 2_000,
            budget_passed=True, admitted_shards=admitted,
            completed_admissions=batch_number - 1,
        )
        assert sample["action"] == "continue"
        jobs.append({
            "name": f"batch-{batch_number} / mutation (full shard {shard}, advisory)",
            "status": "completed",
        })
        if batch_number < 7:
            before_admission = evaluate_calibration_observer(
                contract, jobs, elapsed_seconds=batch_number * 2_000 + 60,
                budget_passed=True, admitted_shards=admitted,
                completed_admissions=batch_number - 1,
            )
            assert before_admission["action"] == "continue"
            jobs.append({
                "name": (
                    f"admit-{batch_number + 1} / "
                    f"mutation (validate calibration batch {batch_number})"
                ),
                "status": "completed", "conclusion": "success",
            })

    terminal = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=14_000, budget_passed=True,
        admitted_shards=calibration_stage_3_admitted_shards(selected, jobs),
        completed_admissions=calibration_stage_3_completed_admissions(jobs),
        route_complete=True,
    )
    assert terminal["action"] == "complete"
    assert terminal["terminal_shards"] == sorted(selected)


def test_stage_3_active_batch_budget_failure_and_expiry_cancel():
    selected = [WAVE_3_BATCHES[0][0]]
    contract = calibration_stage_3_observer_contract(selected)
    jobs = [{
        "name": f"batch-1 / mutation (full shard {selected[0]}, advisory)",
        "status": "in_progress",
    }]

    budget = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=60, budget_passed=False,
        admitted_shards=selected,
    )
    expired = evaluate_calibration_observer(
        contract, jobs, elapsed_seconds=contract["observer_deadline_seconds"],
        budget_passed=True, admitted_shards=selected,
    )

    assert budget["action"] == "cancel"
    assert budget["reason"] == "budget cutoff or accounting validation did not pass"
    assert expired["action"] == "cancel"
    assert expired["reason"] == "observer deadline expired before all admitted workers became terminal"


def test_accounting_includes_observer_admission_support_and_reconciliation_cost(tmp_path):
    names = [
        "mutation (monitor calibration budget)",
        "mutation (validate calibration batch 1)",
        "mutation (watch stage 3 observer)",
        "mutation (calibration accounting)",
    ]
    jobs = []
    for job_id, name in enumerate(names, 1):
        job = _job(job_id)
        job["name"] = name
        jobs.append(job)
    path = _jobs_file(tmp_path, [{"total_count": len(jobs), "jobs": jobs}])

    result = account_runner_minutes(
        path, expected_run_id="7", expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 8
    assert [item["name"] for item in result["included_jobs"]] == names


def test_terminal_accounting_reserves_unobserved_bounded_support_costs():
    accounting = {
        "estimated_runner_minutes": 100.0,
        "included_jobs": [
            {"name": "mutation (calibration accounting)", "status": "in_progress", "minutes": 2.0},
        ],
    }

    result = reserve_bounded_support_minutes(accounting, {
        "mutation (calibration accounting)": 15,
        "mutation (assemble evidence)": 30,
        "mutation evidence": 10,
    })

    assert result["bounded_support_reserve_minutes"] == 53
    assert result["estimated_runner_minutes"] == 153
    assert [item["reserved_minutes"] for item in result["bounded_support_reservations"]] == [
        13, 30, 10,
    ]


def test_terminal_accounting_does_not_reserve_completed_support_job_again():
    accounting = {
        "estimated_runner_minutes": 4.0,
        "included_jobs": [
            {"name": "mutation evidence", "status": "completed", "minutes": 4.0},
        ],
    }

    result = reserve_bounded_support_minutes(accounting, {"mutation evidence": 10})

    assert result["bounded_support_reserve_minutes"] == 0
    assert result["estimated_runner_minutes"] == 4


def test_terminal_accounting_rejects_duplicate_bounded_support_identity():
    accounting = {
        "estimated_runner_minutes": 1.0,
        "included_jobs": [
            {"name": "mutation evidence", "status": "queued", "minutes": 0.0},
            {"name": "mutation evidence", "status": "queued", "minutes": 0.0},
        ],
    }

    with pytest.raises(ValueError, match="duplicated"):
        reserve_bounded_support_minutes(accounting, {"mutation evidence": 10})


@pytest.mark.parametrize("name", [
    "mutation (full shard 999, advisory)",
    "mutation (full shard broken, advisory)",
])
def test_observer_rejects_unexpected_or_malformed_worker_identity(name):
    contract = calibration_observer_contract(1, 1, expected_shards=[7])

    with pytest.raises(ValueError, match="unexpected|malformed"):
        evaluate_calibration_observer(
            contract, [{"name": name, "status": "in_progress"}],
            elapsed_seconds=1, budget_passed=True,
        )


def test_observer_rejects_duplicate_and_early_workers_without_matching_support_jobs():
    selected = [WAVE_3_BATCHES[0][0], WAVE_3_BATCHES[1][0]]
    contract = calibration_stage_3_observer_contract(selected)
    direct = {"name": f"mutation (full shard {selected[0]}, advisory)", "status": "completed"}
    prefixed = {"name": f"caller / mutation (full shard {selected[0]}, advisory)", "status": "completed"}
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_calibration_observer(
            contract, [direct, prefixed, {"name": "mutation evidence", "status": "in_progress"}],
            elapsed_seconds=1, budget_passed=True, admitted_shards=[selected[0]],
        )
    with pytest.raises(ValueError, match="before admission"):
        evaluate_calibration_observer(
            contract,
            [{"name": f"caller / mutation (full shard {selected[1]}, advisory)", "status": "queued"}],
            elapsed_seconds=1, budget_passed=True, admitted_shards=[selected[0]],
        )


def test_observer_ignores_nonexecuted_sparse_batch_placeholder():
    contract = calibration_observer_contract(1, 1, expected_shards=[7])
    placeholder = {
        "name": "caller / mutation (full shard 0, advisory)",
        "status": "completed", "conclusion": "skipped", "runner_id": None, "steps": [],
    }

    result = evaluate_calibration_observer(
        contract, [placeholder], elapsed_seconds=1, budget_passed=True,
    )

    assert result["observed_worker_jobs"] == 0
    assert result["missing_terminal_shards"] == [7]


def test_fixed_waves_cover_every_shard_once_and_reconcile_budget():
    members = [index for shards in WAVES.values() for index in shards]

    assert [len(WAVES[name]) for name in ("wave-1", "wave-2", "wave-3")] == [8, 32, 216]
    assert 27 in WAVES["wave-1"]
    assert len(members) == len(set(members)) == 256
    assert sorted(members) == list(range(256))
    assert BUDGET == {
        "operational_ceiling_runner_minutes": 1220,
        "wave_allowances": {"wave-1": 32, "wave-2": 120, "wave-3": 800},
        "orchestration_and_aggregation": 168,
        "cancellation_headroom": 100,
        "launch_ceiling": {
            "wave-2": 32,
            "wave-3": 152,
            "aggregate": 952,
            "complete": 1120,
        },
    }
    assert sum(BUDGET["wave_allowances"].values()) + BUDGET["orchestration_and_aggregation"] + BUDGET["cancellation_headroom"] == 1220
    assert BUDGET["launch_ceiling"] == {
        "wave-2": 32,
        "wave-3": 152,
        "aggregate": 952,
        "complete": 1120,
    }
    assert ARTIFACT_RETENTION_DAYS == 90
    assert validate_continuation_topology() == {
        "matrix_jobs": 216,
        "matrix_batches": WAVE_3_BATCHES,
        "matrix_batch_sizes": [32, 32, 32, 32, 32, 32, 24],
        "support_jobs": 13,
        "expanded_jobs": 229,
        "per_matrix_platform_limit": 256,
        "project_expanded_job_limit": 256,
    }
    assert [index for batch in WAVE_3_BATCHES for index in batch] == WAVES["wave-3"]


def _fixture(monkeypatch, tmp_path):
    root = tmp_path / "root"
    manifests = tmp_path / "manifests"
    reports = tmp_path / "reports"
    root.mkdir()
    manifests.mkdir()
    reports.mkdir()
    (root / "requirements-mutation.txt").write_text("mutmut==2.5.1\n")
    (root / ".fettle.toml").write_text("[mutation]\n")
    items = []
    for index in range(256):
        item = {"revision": FROZEN_CANDIDATE, "shard_index": index, "shard_count": 256,
                "files": ["fettle/a.py"], "ranges": [{"file": "fettle/a.py", "start": index + 1, "end": index + 1}],
                "digest": f"{index:064x}"}
        items.append(item)
        (manifests / f"partition-{index}.json").write_text(json.dumps(item))
    monkeypatch.setattr("scripts.staged_preflight._load_manifests", lambda *_: items)
    identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": "owner/repo/.github/workflows/mutation.yml@refs/heads/test",
        "run_id": "1", "run_attempt": "1",
    }
    plan = build_plan(root, manifests, "a" * 40, identity)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    return root, manifests, reports, items, identity, plan_path


def _write_wave(reports: Path, manifests: list[dict], wave="wave-1"):
    for index in WAVES[wave]:
        path = reports / str(index)
        path.mkdir()
        fingerprint = f"{index + 1:064x}"
        (path / "mutation-preflight.json").write_text(json.dumps({
            "status": "completed", "passed": True, "engine_version": "2.5.1",
            "shard_index": index, "shard_count": 256, "manifest_digest": manifests[index]["digest"],
            "line_ranges": manifests[index]["ranges"], "files": manifests[index]["files"],
            "generated": 1, "canonicalized": 1, "collisions": 0,
            "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
        }))


def _batch_fixture(monkeypatch, tmp_path, batch=1):
    root, manifests_dir, reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "owner/repo/.github/workflows/staged-preflight-continuation.yml@refs/heads/test",
        "run_id": "39", "run_attempt": "1",
    }
    candidate = "c" * 40
    for manifest in manifests:
        manifest["revision"] = candidate
    plan = build_plan(root, manifests_dir, candidate, identity, candidate_sha=candidate)
    plan.update({
        "mode": "fresh-staged-preflight-continuation",
        "topology": validate_continuation_topology(),
    })
    plan_path = tmp_path / "continuation-plan.json"
    plan_path.write_text(json.dumps(plan))
    completed = [index for members in WAVE_3_BATCHES[:batch] for index in members]
    for index in completed:
        path = reports / str(index)
        path.mkdir()
        fingerprint = f"{index + 1:064x}"
        (path / "mutation-preflight.json").write_text(json.dumps({
            "status": "completed", "passed": True, "engine_version": "2.5.1",
            "shard_index": index, "shard_count": 256,
            "manifest_digest": manifests[index]["digest"],
            "line_ranges": manifests[index]["ranges"], "files": manifests[index]["files"],
            "generated": 1, "canonicalized": 1, "collisions": 0,
            "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
        }))
    jobs = []
    for index in completed:
        jobs.append({
            "id": 1000 + index, "run_id": 39, "run_attempt": 1,
            "name": f"mutation (continuation shard {index})", "status": "completed",
            "conclusion": "success", "steps": [{"name": "run", "conclusion": "success"}],
        })
    jobs_path = tmp_path / "jobs.json"
    jobs_path.write_text(json.dumps({"total_count": len(jobs), "jobs": jobs}))
    artifacts = [{
        "id": 2000 + index,
        "name": f"mutation-preflight-wave-3-39-1-{index}",
        "size_in_bytes": 100, "digest": f"sha256:{index:064x}", "expired": False,
        "workflow_run": {"id": 39, "head_sha": candidate},
    } for index in completed]
    artifacts_path = tmp_path / "artifacts.json"
    artifacts_path.write_text(json.dumps({"total_count": len(artifacts), "artifacts": artifacts}))
    return root, manifests_dir, reports, plan_path, jobs_path, artifacts_path, identity, candidate


def test_batch_admission_validates_exact_evidence_and_emits_only_next_matrix(monkeypatch, tmp_path):
    fixture = _batch_fixture(monkeypatch, tmp_path)

    result = validate_continuation_batch(
        fixture[0], fixture[3], fixture[1], fixture[2], fixture[4], fixture[5],
        batch=1, orchestration_sha=fixture[7], identity=fixture[6],
    )

    assert result["validated_shards"] == WAVE_3_BATCHES[0]
    assert result["cumulative_shards"] == WAVE_3_BATCHES[0]
    assert result["next_matrix"] == {"shard": WAVE_3_BATCHES[1]}


@pytest.mark.parametrize("batch", range(1, 7))
def test_batch_admission_validates_each_cumulative_boundary(monkeypatch, tmp_path, batch):
    fixture = _batch_fixture(monkeypatch, tmp_path, batch=batch)

    result = validate_continuation_batch(
        fixture[0], fixture[3], fixture[1], fixture[2], fixture[4], fixture[5],
        batch=batch, orchestration_sha=fixture[7], identity=fixture[6],
    )

    expected = [index for members in WAVE_3_BATCHES[:batch] for index in members]
    assert result["validated_shards"] == WAVE_3_BATCHES[batch - 1]
    assert result["cumulative_shards"] == expected
    assert result["next_matrix"] == {"shard": WAVE_3_BATCHES[batch]}


@pytest.mark.parametrize(
    "fault", ["failed", "cancelled", "missing-job", "duplicate-job", "missing-artifact",
              "duplicate-artifact", "incompatible-artifact", "missing-report",
              "duplicate-report", "malformed-report", "later-job", "identity"],
)
def test_batch_admission_rejects_non_pass_evidence(monkeypatch, tmp_path, fault):
    fixture = list(_batch_fixture(monkeypatch, tmp_path))
    jobs_path, artifacts_path, reports, identity = fixture[4], fixture[5], fixture[2], fixture[6]
    jobs_payload = json.loads(jobs_path.read_text())
    artifacts_payload = json.loads(artifacts_path.read_text())
    if fault in {"failed", "cancelled"}:
        jobs_payload["jobs"][0]["conclusion"] = fault
    elif fault == "missing-job":
        jobs_payload["jobs"].pop()
    elif fault == "duplicate-job":
        jobs_payload["jobs"].append(deepcopy(jobs_payload["jobs"][0]))
        jobs_payload["jobs"][-1]["id"] += 9000
    elif fault == "later-job":
        later = deepcopy(jobs_payload["jobs"][0])
        later["id"] += 9000
        later["name"] = f"mutation (continuation shard {WAVE_3_BATCHES[1][0]})"
        jobs_payload["jobs"].append(later)
    elif fault == "missing-artifact":
        artifacts_payload["artifacts"].pop()
    elif fault == "duplicate-artifact":
        artifacts_payload["artifacts"].append(deepcopy(artifacts_payload["artifacts"][0]))
        artifacts_payload["artifacts"][-1]["id"] += 9000
    elif fault == "incompatible-artifact":
        artifacts_payload["artifacts"][0]["workflow_run"]["head_sha"] = "d" * 40
    elif fault in {"missing-report", "malformed-report", "duplicate-report"}:
        target = next(reports.rglob("mutation-preflight.json"))
        if fault == "missing-report":
            target.unlink()
        elif fault == "malformed-report":
            target.write_text("[]")
        else:
            duplicate = reports / "duplicate"
            duplicate.mkdir()
            (duplicate / target.name).write_bytes(target.read_bytes())
    else:
        identity = {**identity, "run_id": "40"}
    jobs_payload["total_count"] = len(jobs_payload["jobs"])
    artifacts_payload["total_count"] = len(artifacts_payload["artifacts"])
    jobs_path.write_text(json.dumps(jobs_payload))
    artifacts_path.write_text(json.dumps(artifacts_payload))

    with pytest.raises(ValueError):
        validate_continuation_batch(
            fixture[0], fixture[3], fixture[1], fixture[2], fixture[4], fixture[5],
            batch=1, orchestration_sha=fixture[7], identity=identity,
        )


def test_wave_validation_accepts_exact_complete_membership(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, identity, plan = _fixture(monkeypatch, tmp_path)
    _write_wave(reports, manifests)

    result = validate_wave(root, plan, manifests_dir, reports, "wave-1", "a" * 40, identity)

    assert result["passed"] is True
    assert result["shards"] == WAVES["wave-1"]
    assert len(result["report_digests"]) == 8


@pytest.mark.parametrize("fault", ["missing", "duplicate", "failed", "malformed", "substituted", "identity"])
def test_wave_validation_rejects_invalid_evidence(monkeypatch, tmp_path, fault):
    root, manifests_dir, reports, manifests, identity, plan = _fixture(monkeypatch, tmp_path)
    _write_wave(reports, manifests)
    target = reports / str(WAVES["wave-1"][0]) / "mutation-preflight.json"
    if fault == "missing":
        target.unlink()
    elif fault == "duplicate":
        duplicate = reports / "duplicate"
        duplicate.mkdir()
        (duplicate / target.name).write_bytes(target.read_bytes())
    elif fault == "malformed":
        target.write_text("[]")
    elif fault == "identity":
        changed = deepcopy(identity)
        changed["run_attempt"] = "2"
        identity = changed
    else:
        payload = json.loads(target.read_text())
        if fault == "failed":
            payload["passed"] = False
        if fault == "substituted":
            payload["manifest_digest"] = "f" * 64
        target.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        validate_wave(root, plan, manifests_dir, reports, "wave-1", "a" * 40, identity)


def test_all_fixed_waves_feed_authoritative_complete_corpus_aggregation(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.py").write_text("\n".join(f"line_{index} = 1" for index in range(256)) + "\n")
    reports = []
    for shards in WAVES.values():
        for index in shards:
            fingerprint = f"{index + 1:064x}"
            reports.append({
                "status": "completed", "passed": True, "engine_version": "2.5.1",
                "shard_index": index, "shard_count": 256, "manifest_digest": f"{index:064x}",
                "line_ranges": [{"file": "src/app.py", "start": index + 1, "end": index + 1}],
                "files": ["src/app.py"], "generated": 1, "canonicalized": 1, "collisions": 0,
                "fingerprints": [fingerprint], "corpus": [{"fingerprint": fingerprint}],
            })

    monkeypatch.setattr("fettle.mutation_test._revision", lambda _root: FROZEN_CANDIDATE)

    result = aggregate_preflight_shards(str(tmp_path), reports, ["src/"], [], 256)

    assert result["status"] == "completed"
    assert result["generated"] == result["canonicalized"] == 256
    assert result["collisions"] == 0


def test_mixed_origin_recovery_record_reconciles_all_256_reports(monkeypatch, tmp_path):
    root, manifests_dir, reports_dir, manifests, identity, _ = _fixture(monkeypatch, tmp_path)
    identity["run_id"] = "38"
    plan = build_plan(root, manifests_dir, "b" * 40, identity)
    plan.update({
        "mode": "staged-preflight-recovery",
        "source": {"run_id": SOURCE_RUN_ID, "verdict": "original run remains permanently non-pass"},
        "origin_assignment": {
            str(index): {
                "run_id": SOURCE_RUN_ID if index in WAVES["wave-1"] else "38",
                "run_attempt": "1",
                "wave": next(name for name, shards in WAVES.items() if index in shards),
            }
            for index in range(256)
        },
    })
    for wave in WAVES:
        _write_wave(reports_dir, manifests, wave)
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {
            index: _file_sha(reports_dir / str(index) / "mutation-preflight.json")
            for index in WAVES["wave-1"]
        },
    )
    plan_path = tmp_path / "recovery-plan.json"
    plan_path.write_text(json.dumps(plan))
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps({
        "status": "completed", "passed": True, "revision": FROZEN_CANDIDATE,
        "shard_count": 256, "manifest_digests": plan["manifest_digests"],
        "generated": 256, "canonicalized": 256, "collisions": 0,
    }))

    result = build_recovery_record(plan_path, reports_dir, aggregate_path)

    assert result["passed"] is True
    assert len(result["origins"]) == 256
    assert result["origins"]["8"]["run_id"] == SOURCE_RUN_ID
    assert result["origins"]["0"]["run_id"] == "38"
    assert all(item["artifact_sha256"] for item in result["origins"].values())


@pytest.mark.parametrize(
    "fault", ["missing", "duplicate", "boolean-index", "source-hash", "origin", "aggregate"],
)
def test_recovery_record_rejects_incomplete_or_conflicting_origins(monkeypatch, tmp_path, fault):
    root, manifests_dir, reports_dir, manifests, identity, _ = _fixture(monkeypatch, tmp_path)
    identity["run_id"] = "38"
    plan = build_plan(root, manifests_dir, "b" * 40, identity)
    plan.update({
        "mode": "staged-preflight-recovery", "source": {"run_id": SOURCE_RUN_ID},
        "origin_assignment": {
            str(index): {"run_id": SOURCE_RUN_ID if index in WAVES["wave-1"] else "38",
                         "run_attempt": "1", "wave": next(name for name, shards in WAVES.items() if index in shards)}
            for index in range(256)
        },
    })
    for wave in WAVES:
        _write_wave(reports_dir, manifests, wave)
    expected = {
        index: _file_sha(reports_dir / str(index) / "mutation-preflight.json")
        for index in WAVES["wave-1"]
    }
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_REPORT_SHA256", expected)
    if fault == "missing":
        (reports_dir / "0" / "mutation-preflight.json").unlink()
    elif fault == "duplicate":
        duplicate = reports_dir / "duplicate"
        duplicate.mkdir()
        (duplicate / "mutation-preflight.json").write_bytes(
            (reports_dir / "0" / "mutation-preflight.json").read_bytes(),
        )
    elif fault == "boolean-index":
        path = reports_dir / "1" / "mutation-preflight.json"
        report = json.loads(path.read_text())
        report["shard_index"] = True
        path.write_text(json.dumps(report))
    elif fault == "source-hash":
        expected[WAVES["wave-1"][0]] = "0" * 64
    elif fault == "origin":
        plan["origin_assignment"]["0"]["run_id"] = SOURCE_RUN_ID
    plan_path = tmp_path / "recovery-plan.json"
    plan_path.write_text(json.dumps(plan))
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps({
        "status": "completed", "passed": True, "revision": FROZEN_CANDIDATE,
        "shard_count": 256, "manifest_digests": plan["manifest_digests"],
        "generated": 255 if fault == "aggregate" else 256,
        "canonicalized": 256, "collisions": 0,
    }))

    with pytest.raises(ValueError):
        build_recovery_record(plan_path, reports_dir, aggregate_path)


def test_wave_validation_rejects_different_orchestration_commit(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, identity, plan = _fixture(monkeypatch, tmp_path)
    _write_wave(reports, manifests)

    with pytest.raises(ValueError, match="identity"):
        validate_wave(root, plan, manifests_dir, reports, "wave-1", "b" * 40, identity)


@pytest.mark.parametrize(
    "payload",
    [[], [{"jobs": []}], [{"jobs": [{"started_at": None, "completed_at": "2026-10-06T01:00:00Z"}]}]],
)
def test_budget_usage_rejects_missing_or_partial_job_evidence(tmp_path, payload):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        observed_runner_minutes(path)


def test_budget_usage_sums_completed_runner_time(tmp_path):
    path = tmp_path / "jobs.json"
    path.write_text(json.dumps([{"total_count": 3, "jobs": [
        {"id": 1, "status": "completed", "conclusion": "success", "runner_id": 1,
         "runner_name": "runner", "runner_group_id": None, "runner_group_name": None,
         "steps": [{}], "started_at": "2026-10-06T01:00:00Z", "completed_at": "2026-10-06T01:02:30Z"},
        {"id": 2, "status": "in_progress", "conclusion": None, "runner_id": 2,
         "runner_name": "runner", "runner_group_id": None, "runner_group_name": None,
         "steps": [{}], "started_at": "2026-10-06T01:00:00Z", "completed_at": None},
        {"id": 3, "started_at": None, "completed_at": None, "status": "completed",
         "conclusion": "skipped", "runner_id": None, "runner_name": None,
         "runner_group_id": None, "runner_group_name": None, "steps": []},
    ]}]))

    now = datetime(2026, 10, 6, 1, 3, tzinfo=UTC)

    assert observed_runner_minutes(path, now) == 5.5


def _job(job_id, *, status="completed", conclusion="success", start="2026-10-06T01:00:00Z",
         end="2026-10-06T01:02:00Z", runner_id=10, steps=None, run_id=7, run_attempt=1):
    return {
        "id": job_id, "run_id": run_id, "run_attempt": run_attempt,
        "created_at": start,
        "status": status, "conclusion": conclusion, "started_at": start,
        "completed_at": end, "runner_id": runner_id, "runner_name": "runner" if runner_id else None,
        "runner_group_id": None, "runner_group_name": None,
        "steps": [{"name": "work"}] if steps is None and runner_id else (steps or []),
    }


def _jobs_file(tmp_path, pages, name="jobs.json"):
    path = tmp_path / name
    path.write_text(json.dumps(pages))
    return path


def _checkpoint_artifacts_file(
    tmp_path, indexes, *, calibration_id="calibration-a", run_id="37",
    revision="f" * 40,
):
    artifacts = [{
        "id": index + 1,
        "name": f"mutation-checkpoint-{calibration_id}-{index}",
        "size_in_bytes": 100,
        "digest": f"sha256:{index + 1:064x}",
        "expired": False,
        "workflow_run": {"id": int(run_id), "head_sha": revision},
    } for index in indexes]
    path = tmp_path / "artifacts.json"
    path.write_text(json.dumps([{"total_count": len(artifacts), "artifacts": artifacts}]))
    return path


def _source_workflow_run_file(
    tmp_path, *, run_id="37", run_attempt="1", revision="f" * 40,
):
    path = tmp_path / "source-workflow-run.json"
    path.write_text(json.dumps({
        "id": int(run_id), "run_attempt": int(run_attempt), "status": "completed",
        "head_sha": revision,
    }))
    return path


def _failed_checkpoint_steps():
    return [
        {"name": "Resumable calibration shard evidence", "status": "completed",
         "conclusion": "failure"},
        {"name": "Retain resumable execution checkpoint", "status": "completed",
         "conclusion": "success"},
        {"name": "Retain mutation shard", "status": "completed", "conclusion": "failure"},
    ]


def test_accounting_preserves_observed_acquisition_exposure_and_terminal_revision(tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/staged_preflight_accounting_revision.json").read_text())
    responses = Path(__file__).parent / "fixtures/staged_preflight_accounting_revision"
    charges = []
    for index, observation in enumerate(fixture["observations"], 1):
        path = responses / f"jobs-{index}.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture["provenance"]["snapshot_sha256"][index - 1]

        result = account_runner_minutes(
            path, datetime.fromisoformat(observation["observed_at"].replace("Z", "+00:00")),
            expected_run_id="37795579761", expected_run_attempt="1", job_timeout_minutes=35,
        )

        anomalous = next(job for job in result["included_jobs"] if job["id"] == fixture["provenance"]["job_id"])
        charges.append(anomalous["minutes"])
        assert anomalous["execution_evidence"] == "absent"
        anomaly = next(item for item in result["anomalies"] if item["id"] == anomalous["id"])
        assert anomaly["resource_usage_basis"].startswith("bounded exposure")
    assert charges == [0.12, 0.38, 0.65]

    path = responses / "jobs-terminal.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == fixture["provenance"]["terminal_jobs_sha256"]
    result = account_runner_minutes(path, expected_run_id="37795579761", expected_run_attempt="1")
    corrected = next(job for job in result["included_jobs"] if job["id"] == fixture["provenance"]["job_id"])
    assert corrected["minutes"] == 1.17
    assert corrected["started_at"] == fixture["terminal"]["started_at"]
    assert corrected["execution_evidence"] == "confirmed"


def test_accounting_does_not_use_execution_timeout_to_erase_queue_exposure(tmp_path):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
               end=None, runner_id=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 2, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 60
    assert result["anomalies"][0]["timeout_bound_applied"] is False
    assert "cannot safely truncate" in result["anomalies"][0]["timeout_note"]


def test_accounting_does_not_trust_later_reported_start_to_reduce_exposure(tmp_path):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:30:00Z",
               end=None, runner_id=None, steps=[])
    job["created_at"] = "2026-10-06T01:00:00Z"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 3, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 120
    assert result["anomalies"][0]["timeout_bound_applied"] is False


def test_accounting_uses_dispatch_when_reported_start_precedes_it(tmp_path):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
               end=None, runner_id=None, steps=[])
    job["created_at"] = "2026-10-06T01:30:00Z"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 2, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 30


@pytest.mark.parametrize("now, timeout", [(None, 35), (datetime(2026, 10, 6, 1, 1, tzinfo=UTC), None)])
def test_accounting_rejects_acquisition_exposure_without_explicit_bound(tmp_path, now, timeout):
    job = _job(1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
               end=None, runner_id=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="explicit observation bound"):
        account_runner_minutes(path, now, expected_run_id="7", expected_run_attempt="1",
                               job_timeout_minutes=timeout)


def test_accounting_rejects_acquisition_exposure_without_dispatch_time(tmp_path):
    job = _job(1, status="queued", conclusion=None, end=None, runner_id=None, steps=[])
    job.pop("created_at")
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="created_at"):
        account_runner_minutes(
            path, datetime(2026, 10, 6, 1, 1, tzinfo=UTC), expected_run_id="7",
            expected_run_attempt="1", job_timeout_minutes=35,
        )


def test_accounting_acquisition_exposure_can_cross_budget_gate(tmp_path):
    jobs = [
        _job(index, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
             end=None, runner_id=None, steps=[])
        for index in range(1, 33)
    ]
    path = _jobs_file(tmp_path, [{"total_count": len(jobs), "jobs": jobs}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 36, tzinfo=UTC), expected_run_id="7",
        expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 1152
    assert result["estimated_runner_minutes"] > BUDGET["launch_ceiling"]["complete"]


def test_accounting_rejects_naive_explicit_observation_time(tmp_path):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1)]}])

    with pytest.raises(ValueError, match="timezone-aware"):
        account_runner_minutes(path, datetime(2026, 10, 6, 1, 1),
                               expected_run_id="7", expected_run_attempt="1")


def _source_handoff_fixture(tmp_path):
    repository = "owner/repo"
    source_run_id = "37"
    candidate_sha = "f" * 40
    orchestration_sha = "e" * 40
    branch = "candidate"
    workflow_ref = f"{repository}/.github/workflows/mutation.yml@refs/heads/{branch}"
    run = {
        "id": 37, "run_attempt": 1, "status": "completed", "conclusion": "failure",
        "event": "workflow_dispatch", "head_sha": orchestration_sha, "head_branch": branch,
        "path": ".github/workflows/mutation.yml",
        "head_repository": {"full_name": repository},
    }
    jobs = []
    names = {
        "mutation (freeze staged preflight)",
        "mutation (validate staged preflight wave 1)",
        "mutation (validate staged preflight wave 2)",
        "mutation (monitor staged preflight budget)",
    }
    names.update(f"mutation (staged preflight wave 1 shard {index})" for index in WAVES["wave-1"])
    names.update(f"mutation (staged preflight wave 2 shard {index})" for index in WAVES["wave-2"])
    for job_id, name in enumerate(sorted(names), 1):
        jobs.append({
            **_job(job_id, run_id=37, steps=[{"name": "work", "conclusion": "success"}]),
            "name": name,
        })
    dispatch = {
        **_job(len(jobs) + 1, run_id=37, conclusion="failure", steps=[
            {"name": "Set up job", "conclusion": "success"},
            {"name": "Dispatch immutable continuation", "conclusion": "failure"},
            {"name": "Retain handoff evidence", "conclusion": "skipped"},
        ]),
        "name": "mutation (dispatch staged preflight continuation)",
    }
    jobs.append(dispatch)
    artifact_names = {
        f"mutation-staged-plan-{source_run_id}-1",
        f"mutation-preflight-wave-1-validation-{source_run_id}-1",
        f"mutation-preflight-wave-2-validation-{source_run_id}-1",
        f"mutation-preflight-monitor-{source_run_id}-1",
    }
    artifact_names.update(
        f"mutation-preflight-{wave}-{source_run_id}-1-{index}"
        for wave in ("wave-1", "wave-2") for index in WAVES[wave]
    )
    artifacts = [{
        "id": index, "name": name, "expired": False,
        "workflow_run": {"id": 37, "head_sha": orchestration_sha},
    } for index, name in enumerate(sorted(artifact_names), 1)]
    run_path = tmp_path / "source-run.json"
    jobs_path = tmp_path / "source-jobs.json"
    artifacts_path = tmp_path / "source-artifacts.json"
    run_path.write_text(json.dumps(run))
    jobs_path.write_text(json.dumps([{"total_count": len(jobs), "jobs": jobs}]))
    artifacts_path.write_text(json.dumps([{
        "total_count": len(artifacts), "artifacts": artifacts,
    }]))
    return {
        "run": run, "jobs": jobs, "artifacts": artifacts,
        "run_path": run_path, "jobs_path": jobs_path, "artifacts_path": artifacts_path,
        "repository": repository, "source_run_id": source_run_id,
        "candidate_sha": candidate_sha, "source_orchestration_sha": orchestration_sha,
        "source_workflow_ref": workflow_ref,
    }


def _validate_source_fixture(fixture):
    return validate_source_handoff(
        fixture["run_path"], fixture["jobs_path"], fixture["artifacts_path"],
        repository=fixture["repository"], source_run_id=fixture["source_run_id"],
        candidate_sha=fixture["candidate_sha"],
        source_orchestration_sha=fixture["source_orchestration_sha"],
        source_workflow_ref=fixture["source_workflow_ref"],
    )


def test_source_handoff_accepts_failure_confined_to_dispatch(tmp_path):
    fixture = _source_handoff_fixture(tmp_path)

    result = _validate_source_fixture(fixture)

    assert result["handoff_only_failure"] is True
    assert result["prerequisite_job_count"] == 44
    assert result["prerequisite_artifact_count"] == 44


@pytest.mark.parametrize(
    "fault",
    ["shard", "gate", "identity", "artifact", "expired", "artifact-origin", "ambiguous"],
)
def test_source_handoff_rejects_substantive_or_ambiguous_failures(tmp_path, fault):
    fixture = _source_handoff_fixture(tmp_path)
    if fault == "shard":
        fixture["jobs"][0]["conclusion"] = "failure"
    elif fault == "gate":
        next(job for job in fixture["jobs"] if job["name"] == "mutation (validate staged preflight wave 2)")["conclusion"] = "failure"
    elif fault == "identity":
        fixture["run"]["head_sha"] = "d" * 40
    elif fault == "artifact":
        fixture["artifacts"].pop()
    elif fault == "expired":
        fixture["artifacts"][0]["expired"] = True
    elif fault == "artifact-origin":
        fixture["artifacts"][0]["workflow_run"]["head_sha"] = "d" * 40
    else:
        dispatch = fixture["jobs"][-1]
        dispatch["steps"].insert(1, {"name": "Unknown failed step", "conclusion": "failure"})
    fixture["run_path"].write_text(json.dumps(fixture["run"]))
    fixture["jobs_path"].write_text(json.dumps([{
        "total_count": len(fixture["jobs"]), "jobs": fixture["jobs"],
    }]))
    fixture["artifacts_path"].write_text(json.dumps([{
        "total_count": len(fixture["artifacts"]), "artifacts": fixture["artifacts"],
    }]))

    with pytest.raises(ValueError):
        _validate_source_fixture(fixture)


def test_continuation_dispatch_validation_rejects_duplicates(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps([{"total_count": 0, "workflow_runs": []}]))
    current = tmp_path / "current.json"
    current.write_text(json.dumps([{"total_count": 1, "workflow_runs": [{
        "id": 41, "display_title": "Staged preflight continuation for source 37/1",
    }]}]))

    assert validate_continuation_dispatches(empty, "37")["passed"] is True
    assert validate_continuation_dispatches(current, "37", "41")["passed"] is True
    with pytest.raises(ValueError, match="already has"):
        validate_continuation_dispatches(current, "37")


def _calibration_run_file(tmp_path, name="run.json", **changes):
    run = {
        "schema_version": "1", "kind": "calibration_source",
        "run_id": "37", "run_attempt": "1", "revision": "f" * 40,
        "mode": "calibration", "calibration_id": "calibration-a",
        "calibration_stage": "1",
        **changes,
    }
    path = tmp_path / name
    path.write_text(json.dumps(run))
    return path


def test_accounting_excludes_proven_skipped_job_but_records_reversed_timestamp(tmp_path):
    skipped = _job(
        1, conclusion="skipped", start="2026-10-06T01:00:01Z",
        end="2026-10-06T01:00:00Z", runner_id=None, steps=[],
    )
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [skipped]}])

    result = account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")

    assert result["estimated_runner_minutes"] == 0
    assert result["excluded_jobs"][0]["reason"] == "completed skipped job did not acquire a runner"
    assert result["excluded_jobs"][0]["excluded_fields"] == ["started_at", "completed_at"]
    assert result["anomalies"][0]["reason"] == "skipped job timestamps are reversed"


@pytest.mark.parametrize("field", ["runner_id", "runner_name", "runner_group_id", "runner_group_name"])
def test_accounting_rejects_skipped_job_with_any_runner_identity(tmp_path, field):
    job = _job(
        1,
        status="completed",
        conclusion="skipped",
        end="2026-10-06T01:00:00Z",
        runner_id=None,
        steps=[],
    )
    job.update({
        "runner_id": None, "runner_name": None,
        "runner_group_id": None, "runner_group_name": None,
    })
    job[field] = 9 if field.endswith("_id") else "runner"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("field", ["runner_id", "runner_name", "runner_group_id", "runner_group_name"])
def test_accounting_rejects_missing_runner_identity_field(tmp_path, field):
    job = _job(1, conclusion="skipped", runner_id=None, steps=[])
    job.pop(field)
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="runner identity is incomplete"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("conclusion", ["success", "failure", "cancelled", "timed_out"])
def test_accounting_charges_every_completed_executed_job(tmp_path, conclusion):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, conclusion=conclusion)]}])

    result = account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")

    assert result["estimated_runner_minutes"] == 2
    assert result["included_jobs"][0]["conclusion"] == conclusion


def test_accounting_conservatively_charges_ambiguous_cancelled_job(tmp_path):
    job = _job(
        1, conclusion="cancelled", start="2026-10-06T01:00:01Z",
        end="2026-10-06T01:00:00Z", runner_id=None, steps=[],
    )
    job["name"] = "mutation (full shard 0, advisory)"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, expected_run_id="7", expected_run_attempt="1", job_timeout_minutes=35,
    )

    assert result["estimated_runner_minutes"] == 35
    assert result["included_jobs"][0]["execution_evidence"] == "ambiguous"
    assert result["included_jobs"][0]["started_at"] == "2026-10-06T01:00:01Z"
    assert result["included_jobs"][0]["completed_at"] == "2026-10-06T01:00:00Z"
    assert result["anomalies"][0]["reason"] == (
        "cancelled job has no affirmative execution disposition"
    )


def test_accounting_rejects_unbounded_ambiguous_cancelled_job(tmp_path):
    job = _job(1, conclusion="cancelled", runner_id=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="indeterminate"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_does_not_apply_worker_timeout_to_ambiguous_support_job(tmp_path):
    job = _job(
        1, conclusion="cancelled", start="2026-10-06T01:00:01Z",
        end="2026-10-06T01:00:00Z", runner_id=None, steps=[],
    )
    job["name"] = "mutation evidence"
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="indeterminate"):
        account_runner_minutes(
            path, expected_run_id="7", expected_run_attempt="1",
            job_timeout_minutes=35,
        )


def test_accounting_charges_in_progress_job_to_observation_time(tmp_path):
    job = _job(1, status="in_progress", conclusion=None, end=None)
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 3
    assert result["included_jobs"][0]["basis"] == "elapsed through observation time"


@pytest.mark.parametrize("status", ["queued", "requested", "pending", "waiting"])
def test_accounting_charges_runner_acquisition_transition(tmp_path, status):
    job = _job(1, status=status, conclusion=None, end=None, steps=[])
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 3
    assert result["included_jobs"][0]["basis"] == (
        "runner-acquisition transition elapsed through observation time"
    )


def test_accounting_rejects_transition_with_unbounded_metadata(tmp_path):
    missing_start = _job(1, status="queued", conclusion=None, start=None, end=None)

    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [missing_start]}])
    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_charges_and_flags_partial_identity_during_acquisition(tmp_path):
    partial_runner = _job(2, status="queued", conclusion=None, end=None)
    partial_runner["runner_name"] = None
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [partial_runner]}])

    result = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 3
    assert result["anomalies"][0]["reason"] == (
        "active job runner identity is partial during acquisition"
    )


def test_accounting_rejects_partial_identity_after_completion(tmp_path):
    completed = _job(2)
    completed["runner_name"] = None
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [completed]}])

    with pytest.raises(ValueError, match="partial"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_does_not_exclude_started_job_with_missing_execution_metadata(tmp_path):
    job = _job(
        1, status="queued", conclusion=None, end=None, runner_id=None, steps=[],
    )
    job.update({"runner_name": None, "runner_group_id": None, "runner_group_name": None})
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="explicit observation bound"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_treats_provider_unassigned_runner_sentinels_as_acquisition(tmp_path):
    job = _job(
        1, status="queued", conclusion=None, start="2026-10-06T01:00:00Z",
        end=None, runner_id=0, steps=[],
    )
    job.update({"runner_name": "", "runner_group_id": 0, "runner_group_name": ""})
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    accounting = account_runner_minutes(
        path, datetime(2026, 10, 6, 1, 0, 36, tzinfo=UTC),
        expected_run_id="7", expected_run_attempt="1", job_timeout_minutes=35,
    )
    result = evaluate_calibration_budget(
        accounting, ceiling=3600, cancellation_reserve=1200,
    )

    assert accounting["estimated_runner_minutes"] == 0.6
    assert accounting["included_jobs"][0]["runner_id"] is None
    assert accounting["included_jobs"][0]["execution_evidence"] == "absent"
    assert accounting["included_jobs"][0]["basis"] == (
        "queued acquisition exposure bounded from dispatch through observation"
    )
    assert result["passed"] is True


@pytest.mark.parametrize(
    "identity",
    [
        {"runner_id": False, "runner_name": "", "runner_group_id": False,
         "runner_group_name": ""},
        {"runner_id": 0.0, "runner_name": "", "runner_group_id": 0.0,
         "runner_group_name": ""},
        {"runner_id": 0, "runner_name": "runner", "runner_group_id": 0,
         "runner_group_name": "GitHub Actions"},
        {"runner_id": 10, "runner_name": "", "runner_group_id": 0,
         "runner_group_name": "GitHub Actions"},
        {"runner_id": "10", "runner_name": "runner", "runner_group_id": 0,
         "runner_group_name": "GitHub Actions"},
        {"runner_id": 10, "runner_name": "runner", "runner_group_id": True,
         "runner_group_name": "GitHub Actions"},
        {"runner_id": 10, "runner_name": "runner", "runner_group_id": -1,
         "runner_group_name": "GitHub Actions"},
        {"runner_id": 10, "runner_name": "runner", "runner_group_id": 0,
         "runner_group_name": ""},
    ],
)
def test_accounting_rejects_malformed_runner_sentinel_variants(tmp_path, identity):
    job = _job(1, status="queued", conclusion=None, end=None, steps=[])
    job.update(identity)
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="runner identity is malformed"):
        account_runner_minutes(
            path, datetime(2026, 10, 6, 1, 3, tzinfo=UTC),
            expected_run_id="7", expected_run_attempt="1",
        )


@pytest.mark.parametrize(
    "job",
    [
        _job(1, start=None, end="2026-10-06T01:02:00Z"),
        _job(1, status="completed", conclusion="cancelled", start=None, end=None, runner_id=None),
        _job(1, start="2026-10-06T01:02:00Z", end="2026-10-06T01:00:00Z"),
    ],
)
def test_accounting_rejects_unknown_usage_for_potentially_executed_job(tmp_path, job):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_accepts_complete_pagination_and_rejects_duplicate_jobs(tmp_path):
    pages = [
        {"total_count": 2, "jobs": [_job(1)]},
        {"total_count": 2, "jobs": [_job(2)]},
    ]
    path = _jobs_file(tmp_path, pages)

    result = account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")
    assert result["page_count"] == 2
    assert result["job_count"] == 2
    assert result["estimated_runner_minutes"] == 4

    pages[1]["jobs"][0]["id"] = 1
    path.write_text(json.dumps(pages))
    with pytest.raises(ValueError, match="duplicate"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


def test_accounting_rejects_wrong_run_or_attempt(tmp_path):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_attempt=2)]}])

    with pytest.raises(ValueError, match="origin"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("field", ["total_count", "id"])
def test_accounting_rejects_boolean_integer_fields(tmp_path, field):
    job = _job(1)
    page = {"total_count": 1, "jobs": [job]}
    if field == "total_count":
        page[field] = True
    else:
        job[field] = True
    path = _jobs_file(tmp_path, [page])

    with pytest.raises(ValueError):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize("job_id", [0, -1])
def test_accounting_rejects_nonpositive_provider_job_ids(tmp_path, job_id):
    path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(job_id)]}])

    with pytest.raises(ValueError, match="malformed job ID"):
        account_runner_minutes(path, expected_run_id="7", expected_run_attempt="1")


@pytest.mark.parametrize(
    ("used", "next_wave", "passed"),
    [(32, "wave-2", True), (32.01, "wave-2", False),
     (100.77, "wave-3", True), (152, "wave-3", True), (152.01, "wave-3", False),
     (952, "aggregate", True), (952.01, "aggregate", False),
     (1120, "complete", True), (1120.01, "complete", False)],
)
def test_budget_transition_boundaries(used, next_wave, passed):
    assert (used <= BUDGET["launch_ceiling"][next_wave]) is passed


def _capacity_accounting(jobs):
    return {
        "schema_version": "1", "kind": "operational_runner_time_estimate",
        "billing_authority": False,
        "estimated_runner_minutes": round(sum(job["minutes"] for job in jobs), 2),
        "included_jobs": jobs,
    }


def _capacity_worker(index, minutes=1.5, status="completed", conclusion="success"):
    return {
        "name": f"capacity validation (enumerate {index})", "status": status,
        "conclusion": conclusion, "minutes": minutes,
    }


def test_capacity_preparation_admission_reserves_next_batch_and_all_categories():
    admitted = list(range(16))
    next_shards = list(range(16, 32))
    result = evaluate_capacity_preparation_admission(
        _capacity_accounting([_capacity_worker(index) for index in admitted]),
        admitted_shards=admitted, next_shards=next_shards,
    )

    assert result["passed"] is True
    assert result["worker"]["observed_minutes"] == 24
    assert result["worker"]["next_batch_reservation_minutes"] == 560
    assert result["worker"]["reserved_total_minutes"] == 584
    assert result["support"]["reserved_total_minutes"] == 168
    assert result["cancellation_uncertainty"]["reserved_total_minutes"] == 100
    assert result["operational_ceiling_minutes"] == 1220
    assert result["completion_guaranteed"] is False


def test_capacity_preparation_admission_reserves_active_remaining_without_double_counting():
    result = evaluate_capacity_preparation_admission(
        _capacity_accounting([
            _capacity_worker(0, minutes=10, status="in_progress", conclusion=None),
        ]),
        admitted_shards=[0, 1], next_shards=[], require_admitted_terminal=False,
    )

    assert result["passed"] is True
    assert result["worker"]["observed_minutes"] == 10
    assert result["worker"]["active_remaining_reservation_minutes"] == 60
    assert result["worker"]["reserved_total_minutes"] == 70
    assert result["worker"]["double_counted_elapsed_minutes"] == 0
    assert result["not_yet_observed_shards"] == [1]


def test_capacity_preparation_admission_refuses_unsafe_or_uncertain_snapshots():
    completed = [_capacity_worker(index, minutes=25) for index in range(16)]
    refused = evaluate_capacity_preparation_admission(
        _capacity_accounting(completed), admitted_shards=list(range(16)),
        next_shards=list(range(16, 32)),
    )
    assert refused["passed"] is False
    assert refused["worker"]["reserved_total_minutes"] == 960

    with pytest.raises(ValueError, match="fixed size"):
        evaluate_capacity_preparation_admission(
            _capacity_accounting([]), admitted_shards=[], next_shards=list(range(17)),
        )
    with pytest.raises(ValueError, match="did not succeed"):
        evaluate_capacity_preparation_admission(
            _capacity_accounting([_capacity_worker(0, conclusion="failure")]),
            admitted_shards=[0], next_shards=[],
        )
    with pytest.raises(ValueError, match="duplicated"):
        evaluate_capacity_preparation_admission(
            _capacity_accounting([_capacity_worker(0), _capacity_worker(0)]),
            admitted_shards=[0], next_shards=[],
        )


def test_capacity_preparation_policy_categories_are_exact_and_nontransferable():
    assert CAPACITY_PREPARATION_BUDGET == {
        "worker_ceiling_minutes": 952,
        "support_ceiling_minutes": 168,
        "cancellation_uncertainty_headroom_minutes": 100,
        "operational_ceiling_minutes": 1220,
        "worker_timeout_minutes": 35,
        "batch_size": 16,
    }


def test_calibration_budget_reserves_cancellation_lag_and_rejects_unknown_usage():
    accounting = {"estimated_runner_minutes": 10799.5, "included_jobs": []}
    accepted = evaluate_calibration_budget(accounting, ceiling=12000, cancellation_reserve=1200)
    exhausted = evaluate_calibration_budget(
        {**accounting, "estimated_runner_minutes": 10800.01},
        ceiling=12000, cancellation_reserve=1200,
    )

    assert accepted["passed"] is True
    assert accepted["launch_cutoff"] == 10800
    assert accepted["cancellation_lag_charge"] == 0
    assert accepted["billing_authority"] is False
    assert exhausted["passed"] is False
    with pytest.raises(ValueError, match="usage"):
        evaluate_calibration_budget({}, ceiling=12000, cancellation_reserve=1200)
    with pytest.raises(ValueError, match="included job"):
        evaluate_calibration_budget(
            {"estimated_runner_minutes": 1}, ceiling=12000, cancellation_reserve=1200,
        )


def _launch_current(minutes=10):
    return {
        "schema_version": "1", "kind": "operational_runner_time_estimate",
        "billing_authority": False, "estimated_runner_minutes": minutes,
        "included_jobs": [],
    }


def _complete_lifecycle(stage, expected_shards):
    contract = (
        calibration_stage_3_observer_contract(expected_shards)
        if stage == "3"
        else calibration_observer_contract(
            len(expected_shards), 8 if stage == "1" else 16,
            expected_shards=expected_shards,
        )
    )
    return {
        "schema_version": "1", "kind": "calibration_observer_sample",
        "passed": True, "billing_authority": False, "completion_guaranteed": False,
        "elapsed_seconds": 1, "expected_workers": len(expected_shards),
        "expected_shards": list(expected_shards), "admitted_shards": list(expected_shards),
        "observed_worker_jobs": len(expected_shards),
        "terminal_workers": len(expected_shards), "terminal_shards": list(expected_shards),
        "missing_terminal_shards": [], "pending_admission_shards": [],
        "completed_admissions": contract["admission_dependencies"],
        "expected_admissions": contract["admission_dependencies"],
        "route_complete": True, "action": "complete",
        "reason": "all admitted workers are terminal", "contract": contract,
    }


def _launch_predecessor(*, stage, run_ids, estimated, charged):
    assert len(run_ids) == 1
    active_jobs = int((charged - estimated) / 5)
    included_jobs = [
        {"name": name, "status": "completed", "minutes": bound}
        for name, bound in CALIBRATION_SUPPORT_BOUNDS.items()
    ] + [
        {
            "name": f"active-{index}", "status": "in_progress", "minutes": 1,
            "basis": "elapsed through observation time", "execution_evidence": "confirmed",
        }
        for index in range(active_jobs)
    ]
    current = {
        **_launch_current(estimated),
        "included_jobs": included_jobs, "expected_run_id": run_ids[0],
        "expected_run_attempt": "1",
    }
    monitor = {
        **current, "stage": stage, "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": estimated, "passed": True,
    }
    expected_shards = [WAVES[f"wave-{stage}"][0]]
    lifecycle = _complete_lifecycle(stage, expected_shards)
    result = build_calibration_terminal_accounting(
        current, monitor, lifecycle, stage=stage, calibration_id="cal-test", ceiling=3600,
        support_bounds=CALIBRATION_SUPPORT_BOUNDS,
    )
    return bind_calibration_observer_evidence(result, lifecycle)


def test_launch_contract_allows_zero_only_for_explicit_fresh_stage_1():
    launch = build_calibration_launch_accounting(
        _launch_current(), stage="1", calibration_id="cal-test", ceiling=3600,
        resume_run_id="", prior_stage_run_id="", predecessor=None,
    )
    assert launch["prior_runner_minutes"] == 0
    assert launch["estimated_runner_minutes"] == 10

    with pytest.raises(ValueError, match="missing prior-stage identity"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="", predecessor=None,
        )


def test_launch_contract_uses_effective_predecessor_charge_and_monitor_adds_it_once():
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    launch = build_calibration_launch_accounting(
        _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
        resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
    )
    monitored = combine_calibration_monitor_accounting(
        _launch_current(8), launch, stage="2", calibration_id="cal-test", ceiling=3600,
    )

    assert launch["prior_runner_minutes"] == 125
    assert monitored["estimated_runner_minutes"] == 133


def test_incident_terminal_files_admit_exact_sparse_continuation_without_enrichment(tmp_path):
    assert INCIDENT_ROOT.is_dir()
    legacy = json.loads((INCIDENT_ROOT / "accounting/calibration-accounting.json").read_text())
    current = legacy["sources"][0]
    monitor = json.loads((INCIDENT_ROOT / "monitor/calibration-monitor-budget.json").read_text())
    lifecycle = json.loads((INCIDENT_ROOT / "monitor/calibration-monitor-lifecycle.json").read_text())

    terminal = build_calibration_terminal_accounting(
        current, monitor, lifecycle, stage="1",
        calibration_id="cal-1d5bb2cd-s1-20261011-fresh", ceiling=3600,
        support_bounds={
            "mutation (calibration accounting)": 15,
            "mutation (assemble evidence)": 30,
            "mutation evidence": 10,
        },
    )
    terminal = bind_calibration_observer_evidence(
        terminal, lifecycle, budget_sha256=legacy["observer_evidence"]["budget_sha256"],
    )
    accounting = tmp_path / "calibration-accounting.json"
    accounting.write_text(json.dumps(terminal))
    manifests = [
        json.loads((INCIDENT_ROOT / f"manifests/partition-{index}.json").read_text())
        for index in WAVES["wave-1"]
    ]

    result = plan_calibration_continuation(
        INCIDENT_ROOT / "manifests/calibration-source-provenance.json",
        INCIDENT_ROOT / "jobs.json", INCIDENT_ROOT / "checkpoints",
        INCIDENT_ROOT / "reports", manifests, WAVES["wave-1"],
        "cal-1d5bb2cd-s1-20261011-fresh", "38148783107", "1",
        "1d5bb2cd122d7207f4464ff03d060e5a6ad6b286", "1", [accounting],
        INCIDENT_ROOT / "artifacts.json",
        INCIDENT_ROOT / "run.json",
    )

    assert terminal["estimated_runner_minutes"] == 286.99
    assert terminal["charged_runner_minutes"] == 291.99
    assert result["matrix"] == {"shard": [27, 28, 51, 53]}
    assert [result["shards"][str(index)]["pending"] for index in [27, 28, 51, 53]] == [
        12, 1, 4, 4,
    ]
    assert sum(
        len(json.loads(path.read_text())["outcomes"])
        for path in (INCIDENT_ROOT / "checkpoints").rglob("mutation-checkpoint.json")
    ) == 651


def test_launch_contract_rejects_predecessor_that_did_not_pass():
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    predecessor["passed"] = False

    with pytest.raises(ValueError, match="calibration (?:launch|predecessor accounting)"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize(
    "fault", ["kind", "lineage", "lifecycle", "reservation", "reservation-entry"],
)
def test_launch_contract_rejects_malformed_terminal_contract(fault):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    if fault == "kind":
        predecessor["kind"] = "combined_operational_runner_time_estimate"
    elif fault == "lineage":
        predecessor["source_lineage"][0]["run_id"] = "999"
    elif fault == "lifecycle":
        predecessor["observer_evidence"].pop("lifecycle")
    elif fault == "reservation-entry":
        predecessor["bounded_support_reservations"].append(None)
    else:
        predecessor["bounded_support_reservations"][0]["reserved_minutes"] = 4

    with pytest.raises(ValueError, match="calibration predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize(
    "fault", ["missing-shards", "empty-shards", "substituted-shard", "contract-shards"],
)
def test_launch_contract_rejects_incomplete_or_substituted_lifecycle(fault):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    lifecycle = predecessor["observer_evidence"]["lifecycle"]
    if fault == "missing-shards":
        lifecycle.pop("terminal_shards")
    elif fault == "empty-shards":
        lifecycle["terminal_shards"] = []
        lifecycle["expected_shards"] = []
        lifecycle["admitted_shards"] = []
    elif fault == "substituted-shard":
        lifecycle["terminal_shards"] = [0]
        lifecycle["expected_shards"] = [0]
        lifecycle["admitted_shards"] = [0]
        lifecycle["contract"]["expected_shards"] = [0]
    else:
        lifecycle["contract"]["expected_shards"] = [0]

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize(
    "field", [
        "max_parallel", "worker_timeout_minutes", "worker_waves",
        "admission_dependencies", "components", "observer_deadline_seconds",
    ],
)
def test_launch_contract_rejects_forged_observer_contract(field):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    contract = predecessor["observer_evidence"]["lifecycle"]["contract"]
    if field == "components":
        contract[field]["polling_minutes"] += 1
    else:
        contract[field] += 1

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize(
    "field", [
        "schema_version", "billing_authority", "completion_guaranteed",
        "expected_workers", "observed_worker_jobs", "terminal_workers",
        "missing_terminal_shards", "pending_admission_shards",
        "completed_admissions", "expected_admissions", "route_complete", "reason",
    ],
)
def test_launch_contract_rejects_incomplete_or_forged_lifecycle_metadata(field):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    lifecycle = predecessor["observer_evidence"]["lifecycle"]
    lifecycle.pop(field)

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


def test_terminal_contract_rejects_noncanonical_support_policy():
    current = {
        **_launch_current(8), "expected_run_id": "482", "expected_run_attempt": "1",
    }
    monitor = {
        **current, "stage": "2", "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": 8, "passed": True,
    }

    with pytest.raises(ValueError, match="support bounds differ"):
        build_calibration_terminal_accounting(
            current, monitor, _complete_lifecycle("2", [2]), stage="2",
            calibration_id="cal-test", ceiling=3600, support_bounds={"support": 5},
        )


@pytest.mark.parametrize("ceiling", [3599, 3601, 12000])
def test_terminal_contract_rejects_noncanonical_calibration_ceiling(ceiling):
    current = {
        **_launch_current(8), "expected_run_id": "482", "expected_run_attempt": "1",
    }
    monitor = {
        **current, "stage": "2", "calibration_id": "cal-test", "ceiling": ceiling,
        "charged_runner_minutes": 8, "passed": True,
    }

    with pytest.raises(ValueError, match="terminal observer evidence"):
        build_calibration_terminal_accounting(
            current, monitor, _complete_lifecycle("2", [2]), stage="2",
            calibration_id="cal-test", ceiling=ceiling,
            support_bounds=CALIBRATION_SUPPORT_BOUNDS,
        )


@pytest.mark.parametrize("field", ["terminal_shards", "admitted_shards"])
def test_launch_contract_rejects_reordered_lifecycle_shards(field):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    lifecycle = predecessor["observer_evidence"]["lifecycle"]
    extra = WAVES["wave-1"][1]
    lifecycle["expected_shards"].append(extra)
    lifecycle["terminal_shards"].append(extra)
    lifecycle["admitted_shards"].append(extra)
    lifecycle["contract"] = calibration_observer_contract(
        2, 8, expected_shards=lifecycle["expected_shards"],
    )
    lifecycle["expected_workers"] = 2
    lifecycle["observed_worker_jobs"] = 2
    lifecycle["terminal_workers"] = 2
    lifecycle[field] = list(reversed(lifecycle[field]))

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize("attempt", ["", "0", "2", "x"])
def test_launch_contract_rejects_malformed_or_wrong_predecessor_attempt(attempt):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    predecessor["sources"][0]["expected_run_attempt"] = attempt
    predecessor["source_lineage"][0]["run_attempt"] = attempt

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


def test_launch_contract_rejects_wrong_attempt_in_earlier_cumulative_origin():
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=100, charged=105,
    )
    current = {
        **_launch_current(8), "expected_run_id": "482", "expected_run_attempt": "1",
    }
    lifecycle = _complete_lifecycle("2", [2])
    monitor = {
        **current, "stage": "2", "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": 8, "passed": True,
    }
    cumulative = build_calibration_terminal_accounting(
        current, monitor, lifecycle, stage="2", calibration_id="cal-test", ceiling=3600,
        support_bounds=CALIBRATION_SUPPORT_BOUNDS, predecessor=predecessor,
        predecessor_run_id="381", predecessor_stage="1",
    )
    cumulative = bind_calibration_observer_evidence(cumulative, lifecycle)
    cumulative["sources"][0]["sources"][0]["expected_run_attempt"] = "2"
    cumulative["sources"][0]["source_lineage"][0]["run_attempt"] = "2"
    cumulative["source_lineage"][0]["run_attempt"] = "2"

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="3", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="482", predecessor=cumulative,
        )


def test_terminal_contract_imports_cumulative_predecessor_charge_once():
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    current = {
        **_launch_current(8), "expected_run_id": "482", "expected_run_attempt": "1",
    }
    monitor = {
        **current, "stage": "2", "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": 8, "passed": True,
    }
    lifecycle = _complete_lifecycle("2", [2])

    result = build_calibration_terminal_accounting(
        current, monitor, lifecycle, stage="2", calibration_id="cal-test", ceiling=3600,
        support_bounds=CALIBRATION_SUPPORT_BOUNDS, predecessor=predecessor,
        predecessor_run_id="381", predecessor_stage="1",
    )
    result = bind_calibration_observer_evidence(result, lifecycle)

    assert result["source_lineage"] == [
        {"run_id": "381", "run_attempt": "1"},
        {"run_id": "482", "run_attempt": "1"},
    ]
    assert result["estimated_runner_minutes"] == 188
    assert result["charged_runner_minutes"] == 188


def test_launch_and_terminal_reject_monitor_snapshot_as_cumulative_predecessor():
    monitor_snapshot = {
        **_launch_current(125), "expected_run_id": "381", "expected_run_attempt": "1",
        "stage": "1", "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": 125, "passed": True,
    }
    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=monitor_snapshot,
        )

    current = {
        **_launch_current(8), "expected_run_id": "482", "expected_run_attempt": "1",
    }
    lifecycle = _complete_lifecycle("2", [2])
    current_monitor = {
        **current, "stage": "2", "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": 8, "passed": True,
    }
    with pytest.raises(ValueError, match="prior cumulative accounting is incompatible"):
        build_calibration_terminal_accounting(
            current, current_monitor, lifecycle, stage="2", calibration_id="cal-test",
            ceiling=3600, support_bounds=CALIBRATION_SUPPORT_BOUNDS,
            predecessor=monitor_snapshot,
            predecessor_run_id="381", predecessor_stage="1",
        )


def test_terminal_decision_rejects_forged_budget_pass():
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    predecessor["ceiling"] = 10
    predecessor["launch_cutoff"] = 5

    with pytest.raises(ValueError, match="calibration launch identity is malformed"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=10,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


def test_terminal_decision_rejects_coordinated_reservation_and_lag_forgery():
    for fault in ("reservation", "lag"):
        predecessor = _launch_predecessor(
            stage="1", run_ids=("381",), estimated=120, charged=125,
        )
        if fault == "reservation":
            predecessor["bounded_support_reservations"][0]["reserved_minutes"] = 4
            predecessor["bounded_support_reserve_minutes"] = 4
            predecessor["estimated_runner_minutes"] = 124
            predecessor["charged_runner_minutes"] = 129
        else:
            predecessor["cancellation_lag_charge"] = 10
            predecessor["charged_runner_minutes"] = predecessor["estimated_runner_minutes"] + 10

        with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
            build_calibration_launch_accounting(
                _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
                resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
            )


@pytest.mark.parametrize("fault", ["active-jobs", "reservation-observed", "included-jobs"])
def test_terminal_decision_recomputes_lag_and_reservations_from_source_jobs(fault):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    if fault == "active-jobs":
        predecessor["active_jobs"] = 1
        predecessor["cancellation_lag_charge"] = 5
        predecessor["charged_runner_minutes"] += 5
    elif fault == "reservation-observed":
        reservation = predecessor["bounded_support_reservations"][0]
        reservation["already_observed_minutes"] = reservation["bound_minutes"]
        reservation["reserved_minutes"] = 0
        predecessor["bounded_support_reserve_minutes"] = 0
        predecessor["estimated_runner_minutes"] -= 5
        predecessor["charged_runner_minutes"] -= 5
    else:
        predecessor["included_jobs"] = [{"name": "forged", "status": "completed"}]

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize("field", ["terminal_shards", "admitted_shards"])
def test_launch_contract_rejects_numeric_alias_lifecycle_shards(field):
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=120, charged=125,
    )
    predecessor["observer_evidence"]["lifecycle"][field] = [8.0]

    with pytest.raises(ValueError, match="predecessor accounting is incompatible"):
        build_calibration_launch_accounting(
            _launch_current(), stage="2", calibration_id="cal-test", ceiling=3600,
            resume_run_id="", prior_stage_run_id="381", predecessor=predecessor,
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.pop("prior_runner_minutes"),
        lambda value: value.update(prior_runner_minutes=-1),
        lambda value: value.update(stage="3"),
        lambda value: value["calibration_predecessor"].update(mode="prior-stage"),
        lambda value: value["calibration_predecessor"].update(
            mode="same-stage-resume", resume_run_id="381", accounting_run_id="999",
        ),
    ],
)
def test_monitor_contract_rejects_missing_malformed_or_conflicting_launch_accounting(mutation):
    launch = build_calibration_launch_accounting(
        _launch_current(), stage="1", calibration_id="cal-test", ceiling=3600,
        resume_run_id="", prior_stage_run_id="", predecessor=None,
    )
    mutation(launch)

    with pytest.raises(ValueError, match="launch accounting contract"):
        combine_calibration_monitor_accounting(
            _launch_current(), launch, stage="1", calibration_id="cal-test", ceiling=3600,
        )


def test_monitor_contract_preserves_lower_later_observation_floor_and_support_reservation(tmp_path):
    usage = _launch_current(80)
    history = tmp_path / "history.json"
    history.write_text(json.dumps({
        **usage, "expected_run_id": "700", "expected_run_attempt": "1",
        "estimated_runner_minutes": 100, "charged_runner_minutes": 105,
    }))
    usage.update(expected_run_id="700", expected_run_attempt="1")
    retained = retain_historical_accounting_floor(usage, [history])
    reserved = reserve_bounded_support_minutes(retained, {"support": 10})
    launch = build_calibration_launch_accounting(
        _launch_current(), stage="1", calibration_id="cal-test", ceiling=3600,
        resume_run_id="", prior_stage_run_id="", predecessor=None,
    )
    monitored = combine_calibration_monitor_accounting(
        reserved, launch, stage="1", calibration_id="cal-test", ceiling=3600,
    )

    assert retained["estimated_runner_minutes"] == 105
    assert monitored["estimated_runner_minutes"] == 115
    assert monitored["bounded_support_reserve_minutes"] == 10


def test_historical_floor_accepts_cumulative_lineage_ending_in_current_origin(tmp_path):
    current = {
        **_launch_current(8), "expected_run_id": "482", "expected_run_attempt": "1",
    }
    lifecycle = _complete_lifecycle("2", [2])
    monitor = {
        **current, "stage": "2", "calibration_id": "cal-test", "ceiling": 3600,
        "charged_runner_minutes": 8, "passed": True,
    }
    predecessor = _launch_predecessor(
        stage="1", run_ids=("381",), estimated=100, charged=105,
    )
    cumulative = build_calibration_terminal_accounting(
        current, monitor, lifecycle, stage="2", calibration_id="cal-test", ceiling=3600,
        support_bounds=CALIBRATION_SUPPORT_BOUNDS, predecessor=predecessor,
        predecessor_run_id="381", predecessor_stage="1",
    )
    cumulative = bind_calibration_observer_evidence(cumulative, lifecycle)
    historical = tmp_path / "cumulative.json"
    historical.write_text(json.dumps(cumulative))

    retained = retain_historical_accounting_floor(current, [historical])

    assert retained["estimated_runner_minutes"] == cumulative["charged_runner_minutes"]
    assert retained["historical_floor_applied"] is True


@pytest.mark.parametrize("status", [None, True, 2, "queued", "unknown"])
def test_calibration_budget_rejects_malformed_included_job_status(status):
    with pytest.raises(ValueError, match="included job"):
        evaluate_calibration_budget(
            {"estimated_runner_minutes": 1, "included_jobs": [{"status": status}]},
            ceiling=12000, cancellation_reserve=1200,
        )


def test_calibration_budget_charges_active_jobs_for_cancellation_lag():
    accounting = {
        "estimated_runner_minutes": 10791,
        "included_jobs": [
            {"status": "in_progress", "minutes": 1, "basis": "elapsed through observation time", "execution_evidence": "confirmed"},
            {"status": "in_progress", "minutes": 1, "basis": "elapsed through observation time", "execution_evidence": "confirmed"},
            {"status": "completed"},
        ],
    }

    result = evaluate_calibration_budget(accounting, ceiling=12000, cancellation_reserve=1200)

    assert result["cancellation_lag_charge"] == 10
    assert result["charged_runner_minutes"] == 10801
    assert result["passed"] is False


def test_calibration_budget_accepts_conservatively_bounded_queued_acquisition():
    accounting = {
        "estimated_runner_minutes": 100,
        "included_jobs": [{
            "status": "queued", "minutes": 100,
            "basis": "queued acquisition exposure bounded from dispatch through observation",
            "execution_evidence": "absent",
        }],
    }

    result = evaluate_calibration_budget(accounting, ceiling=1500, cancellation_reserve=1200)

    assert result["active_jobs"] == 1
    assert result["cancellation_lag_charge"] == 5
    assert result["charged_runner_minutes"] == 105
    assert result["passed"] is True


@pytest.mark.parametrize(
    "job",
    [
        {"status": "queued", "minutes": 1, "basis": "unknown", "execution_evidence": "absent"},
        {"status": "queued", "minutes": 1, "basis": "queued acquisition exposure bounded from dispatch through observation", "execution_evidence": "confirmed"},
        {"status": "queued", "minutes": -1, "basis": "queued acquisition exposure bounded from dispatch through observation", "execution_evidence": "absent"},
    ],
)
def test_calibration_budget_rejects_malformed_acquisition(job):
    with pytest.raises(ValueError, match="acquisition|active"):
        evaluate_calibration_budget(
            {"estimated_runner_minutes": 1, "included_jobs": [job]},
            ceiling=1500, cancellation_reserve=1200,
        )


def test_calibration_stage_3_batches_are_exact_and_fixed():
    batches = calibration_stage_3_batches(WAVES["wave-3"])

    assert [len(batch) for batch in batches] == [32, 32, 32, 32, 32, 32, 24]
    assert len(WAVES["wave-3"]) == 216
    assert [shard for batch in batches for shard in batch] == WAVES["wave-3"]
    assert len(set(shard for batch in batches for shard in batch)) == 216
    assert set(WAVES["wave-1"]) | set(WAVES["wave-2"]) | set(WAVES["wave-3"]) == set(range(256))

    with pytest.raises(ValueError, match="exact frozen shard membership"):
        calibration_stage_3_batches(WAVES["wave-3"][:-1])


def test_sparse_continuation_requires_job_provenance_for_missing_checkpoints(tmp_path):
    manifests = [
        {"shard_index": 0, "digest": "a" * 64},
        {"shard_index": 1, "digest": "b" * 64},
        {"shard_index": 2, "digest": "c" * 64},
    ]
    jobs = [
        _job(1, run_id=37),
        _job(2, run_id=37, conclusion="cancelled"),
        _job(3, run_id=37, conclusion="skipped", runner_id=None, steps=[]),
    ]
    for index, job in enumerate(jobs):
        job["name"] = f"execute / mutation (full shard {index}, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 3, "jobs": jobs}])
    checkpoints = tmp_path / "checkpoints"
    checkpoint_dir = checkpoints / "mutation-checkpoint-calibration-a-0"
    checkpoint_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        }, "outcomes": {"x": {}},
        "attempts": [], "status": "completed", "pending": 0,
    }))
    reports = tmp_path / "reports" / "0"
    reports.mkdir(parents=True)
    reports.joinpath("mutation-report.json").write_text(json.dumps({
        "status": "completed", "shard_index": 0, "calibration_id": "calibration-a",
        "revision": "f" * 40, "preflight_digest": "e" * 64,
        "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
        "environment_digest": "c" * 64,
    }))

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, checkpoints, tmp_path / "reports",
        manifests, [0, 1, 2], "calibration-a", "37", "1", "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [1, 2]}
    assert result["shards"]["0"]["state"] == "completed"
    assert result["shards"]["1"]["state"] == "started_interrupted"
    assert result["shards"]["2"]["state"] == "never_started"


def test_sparse_continuation_never_infers_missing_checkpoint(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [
        {**_job(1, run_id=37), "name": "mutation (full shard 0, advisory)"},
    ]}])

    with pytest.raises(ValueError, match="successful shard 0 has no checkpoint"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


def test_sparse_continuation_rejects_duplicate_provider_job_identity_across_shards(tmp_path):
    manifests = [
        {"shard_index": 0, "digest": "a" * 64},
        {"shard_index": 1, "digest": "b" * 64},
    ]
    jobs = [
        {**_job(1, run_id=37, conclusion="skipped", runner_id=None, steps=[]),
         "name": f"mutation (full shard {index}, advisory)"}
        for index in range(2)
    ]
    jobs_path = _jobs_file(tmp_path, [{"total_count": 2, "jobs": jobs}])

    with pytest.raises(ValueError, match="duplicate job IDs|job identity is malformed or duplicated"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
            tmp_path / "reports", manifests, [0, 1], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


def test_sparse_continuation_proves_skipped_shard_never_acquired_runner(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="skipped", runner_id=None, steps=[])
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "never_started"


def test_sparse_continuation_treats_exact_provider_sentinel_as_never_started(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="skipped", runner_id=0, steps=[])
    job.update({
        "name": "mutation (full shard 0, advisory)",
        "runner_name": "", "runner_group_id": 0, "runner_group_name": "",
    })
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["shards"]["0"]["state"] == "never_started"


def test_sparse_continuation_rejects_cancelled_no_runner_as_indeterminate(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="cancelled", runner_id=None, steps=[])
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="indeterminate provenance"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


def test_sparse_continuation_rejects_cancelled_provider_sentinel_as_indeterminate(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="cancelled", runner_id=0, steps=[])
    job.update({
        "name": "mutation (full shard 0, advisory)",
        "runner_name": "", "runner_group_id": 0, "runner_group_name": "",
    })
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="indeterminate provenance"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


def test_sparse_continuation_rejects_sentinel_as_checkpoint_only_authority(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="cancelled", runner_id=0, steps=[])
    job.update({
        "name": "mutation (full shard 0, advisory)",
        "runner_name": "", "runner_group_id": 0, "runner_group_name": "",
    })
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint_dir = tmp_path / "checkpoints" / "artifact"
    report_dir = tmp_path / "reports" / "artifact"
    checkpoint_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        }, "outcomes": {}, "attempts": [], "status": "incomplete", "pending": 1,
    }))
    report_dir.joinpath("mutation-report.json").write_bytes(b"")

    with pytest.raises(ValueError, match="matching retained report"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


@pytest.mark.parametrize(
    "identity",
    [
        {"runner_id": False, "runner_name": "", "runner_group_id": False,
         "runner_group_name": ""},
        {"runner_id": 10, "runner_name": "runner", "runner_group_id": -1,
         "runner_group_name": "GitHub Actions"},
        {"runner_id": 10, "runner_name": "runner", "runner_group_id": 0,
         "runner_group_name": ""},
    ],
)
def test_sparse_continuation_rejects_malformed_runner_identity(tmp_path, identity):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="skipped", runner_id=None, steps=[])
    job.update({"name": "mutation (full shard 0, advisory)", **identity})
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError, match="runner identity is malformed"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "missing",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


@pytest.mark.parametrize("fault", ["calibration", "candidate", "manifest", "duplicate"])
def test_sparse_continuation_rejects_incompatible_or_conflicting_checkpoints(tmp_path, fault):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [
        {**_job(1, run_id=37), "name": "mutation (full shard 0, advisory)"},
    ]}])
    checkpoints = tmp_path / "checkpoints"
    first = checkpoints / "one"
    first.mkdir(parents=True)
    payload = {
        "schema_version": "1", "calibration_id": "other" if fault == "calibration" else "calibration-a",
        "identity": {
            "revision": ("0" if fault == "candidate" else "f") * 40,
            "preflight_digest": "e" * 64,
            "manifest_digest": "b" * 64 if fault == "manifest" else "a" * 64,
            "corpus_digest": "d" * 64, "environment_digest": "c" * 64,
        },
        "outcomes": {}, "attempts": [], "status": "completed", "pending": 0,
    }
    first.joinpath("mutation-checkpoint.json").write_text(json.dumps(payload))
    if fault == "duplicate":
        second = checkpoints / "two"
        second.mkdir()
        second.joinpath("mutation-checkpoint.json").write_text(json.dumps(payload))

    with pytest.raises(ValueError):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, checkpoints, tmp_path / "reports",
            manifests, [0], "calibration-a", "37", "1", "f" * 40, "1",
        )


def test_sparse_continuation_rejects_conflicting_shared_checkpoint_identity(tmp_path):
    manifests = [
        {"shard_index": 0, "digest": "a" * 64},
        {"shard_index": 1, "digest": "b" * 64},
    ]
    jobs = []
    checkpoints = tmp_path / "checkpoints"
    for index, manifest in enumerate(manifests):
        job = _job(index + 1, run_id=37)
        job["name"] = f"mutation (full shard {index}, advisory)"
        jobs.append(job)
        directory = checkpoints / str(index)
        directory.mkdir(parents=True)
        directory.joinpath("mutation-checkpoint.json").write_text(json.dumps({
            "schema_version": "1", "calibration_id": "calibration-a",
            "identity": {
                "revision": "f" * 40,
                "preflight_digest": ("e" if index == 0 else "9") * 64,
                "manifest_digest": manifest["digest"], "corpus_digest": "d" * 64,
                "environment_digest": "c" * 64,
            },
            "outcomes": {}, "attempts": [], "status": "completed", "pending": 0,
        }))
    jobs_path = _jobs_file(tmp_path, [{"total_count": 2, "jobs": jobs}])

    with pytest.raises(ValueError, match="conflicting shared identity"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, checkpoints, tmp_path / "reports",
            manifests, [0, 1], "calibration-a", "37", "1", "f" * 40, "1",
        )


def test_sparse_continuation_associates_cancelled_partial_report_by_exact_identity(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="cancelled")
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint = {
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {"1" * 64: {"state": "killed", "duration_ms": 1}},
        "attempts": [{"fingerprint": "2" * 64, "status": "execution_error"}],
        "status": "incomplete", "pending": 1,
    }
    checkpoint_dir = tmp_path / "checkpoints" / "downloaded-artifact"
    report_dir = tmp_path / "reports" / "downloaded-artifact"
    checkpoint_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    report_dir.joinpath("mutation-report.json").write_text(json.dumps(checkpoint))

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "started_partial"
    assert result["shards"]["0"]["pending"] == 1


@pytest.mark.parametrize("fault", ["missing", "incorrect", "duplicate"])
@pytest.mark.parametrize("conclusion", ["failure", "timed_out"])
def test_sparse_continuation_rejects_failed_partial_report_without_exact_steps(
    tmp_path, fault, conclusion,
):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    steps = _failed_checkpoint_steps()
    if fault == "missing":
        steps = steps[1:]
    elif fault == "incorrect":
        steps[0]["conclusion"] = "success"
    else:
        steps.append(dict(steps[0]))
    job = _job(1, run_id=37, conclusion=conclusion, steps=steps)
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint = {
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {"1" * 64: {"state": "killed", "duration_ms": 1}},
        "attempts": [{"fingerprint": "2" * 64, "status": "execution_error"}],
        "status": "incomplete", "pending": 1,
    }
    artifact_name = "mutation-checkpoint-calibration-a-0"
    checkpoint_dir = tmp_path / "checkpoints" / artifact_name
    report_dir = tmp_path / "reports" / artifact_name
    checkpoint_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    report_dir.joinpath("mutation-report.json").write_text(json.dumps(checkpoint))

    with pytest.raises(ValueError, match="step evidence"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1", artifact_inventory_path=_checkpoint_artifacts_file(tmp_path, [0]),
            source_run_path=_source_workflow_run_file(tmp_path),
        )


def test_sparse_continuation_accepts_cancelled_checkpoint_and_quarantines_zero_byte_report(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="cancelled")
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint = {
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {"1" * 64: {"state": "killed", "duration_ms": 1}},
        "attempts": [{
            "fingerprint": "2" * 64, "status": "execution_error", "message": "failed",
        }],
        "status": "incomplete", "pending": 1,
    }
    checkpoint_dir = tmp_path / "checkpoints" / "artifact"
    report_dir = tmp_path / "reports" / "artifact"
    checkpoint_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    report_dir.joinpath("mutation-report.json").write_bytes(b"")

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "started_partial_checkpoint_only"
    assert result["shards"]["0"]["pending"] == 1
    assert result["validated_representations"]["0"]["kind"] == "checkpoint"
    assert result["quarantined_reports"][0]["size"] == 0
    assert result["shards"]["0"]["representation"]["sha256"] == _file_sha(
        checkpoint_dir / "mutation-checkpoint.json"
    )


def test_sparse_continuation_rejects_checkpoint_only_for_uncancelled_producer(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="success")
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint_dir = tmp_path / "checkpoints" / "artifact"
    checkpoint_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        }, "outcomes": {}, "attempts": [], "status": "incomplete", "pending": 1,
    }))

    with pytest.raises(ValueError, match="successful shard"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


@pytest.mark.parametrize("conclusion", ["failure", "timed_out"])
def test_sparse_continuation_accepts_provenance_bound_failed_checkpoint_only(
    tmp_path, conclusion,
):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion=conclusion, steps=_failed_checkpoint_steps())
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint_dir = tmp_path / "checkpoints" / "mutation-checkpoint-calibration-a-0"
    checkpoint_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        }, "outcomes": {}, "attempts": [], "status": "incomplete", "pending": 1,
    }))

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1", artifact_inventory_path=_checkpoint_artifacts_file(tmp_path, [0]),
        source_run_path=_source_workflow_run_file(tmp_path),
    )

    assert result["matrix"] == {"shard": [0]}
    representation = result["shards"]["0"]["representation"]
    assert representation["kind"] == "checkpoint"
    assert representation["source_artifact"]["producer_job_id"] == 1
    assert representation["source_artifact"]["source_run_attempt"] == "1"


@pytest.mark.parametrize(
    "fault", [
        "status", "conclusion", "producer", "checkpoint-upload", "report-upload",
        "duplicate-step", "missing-artifacts", "artifact-name", "artifact-run",
        "artifact-revision", "artifact-expired", "artifact-size", "artifact-digest",
        "source-run-id", "source-run-attempt", "source-run-status", "source-run-revision",
        "completed-checkpoint", "zero-pending", "completed-report",
    ],
)
def test_sparse_continuation_rejects_failed_checkpoint_outside_amendment(tmp_path, fault):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="failure", steps=_failed_checkpoint_steps())
    job["name"] = "mutation (full shard 0, advisory)"
    checkpoint = {
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        }, "outcomes": {}, "attempts": [], "status": "incomplete", "pending": 1,
    }
    checkpoint_dir = tmp_path / "checkpoints" / "mutation-checkpoint-calibration-a-0"
    checkpoint_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    artifacts_path = _checkpoint_artifacts_file(tmp_path, [0])
    source_run_path = _source_workflow_run_file(tmp_path)
    artifacts = json.loads(artifacts_path.read_text())
    source_run = json.loads(source_run_path.read_text())
    if fault == "status":
        job["status"] = "in_progress"
    elif fault == "conclusion":
        job["conclusion"] = "action_required"
    elif fault in {"producer", "checkpoint-upload", "report-upload"}:
        name = {
            "producer": "Resumable calibration shard evidence",
            "checkpoint-upload": "Retain resumable execution checkpoint",
            "report-upload": "Retain mutation shard",
        }[fault]
        step = next(step for step in job["steps"] if step["name"] == name)
        step["conclusion"] = "failure" if fault == "checkpoint-upload" else "success"
    elif fault == "duplicate-step":
        job["steps"].append(dict(job["steps"][0]))
    elif fault == "missing-artifacts":
        artifacts_path = None
    elif fault == "artifact-name":
        artifacts[0]["artifacts"][0]["name"] = "mutation-checkpoint-calibration-a-1"
    elif fault == "artifact-run":
        artifacts[0]["artifacts"][0]["workflow_run"]["id"] = 38
    elif fault == "artifact-revision":
        artifacts[0]["artifacts"][0]["workflow_run"]["head_sha"] = "0" * 40
    elif fault == "artifact-expired":
        artifacts[0]["artifacts"][0]["expired"] = True
    elif fault == "artifact-size":
        artifacts[0]["artifacts"][0]["size_in_bytes"] = 0
    elif fault == "artifact-digest":
        artifacts[0]["artifacts"][0]["digest"] = None
    elif fault == "source-run-id":
        source_run["id"] = 38
    elif fault == "source-run-attempt":
        source_run["run_attempt"] = 2
    elif fault == "source-run-status":
        source_run["status"] = "in_progress"
    elif fault == "source-run-revision":
        source_run["head_sha"] = "0" * 40
    elif fault in {"completed-checkpoint", "zero-pending"}:
        checkpoint["status"] = "completed" if fault == "completed-checkpoint" else "incomplete"
        checkpoint["pending"] = 0
        checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    else:
        report_dir = tmp_path / "reports" / "artifact"
        report_dir.mkdir(parents=True)
        report_dir.joinpath("mutation-report.json").write_text(json.dumps({
            "status": "completed", "shard_index": 0,
        }))
    if artifacts_path is not None:
        artifacts_path.write_text(json.dumps(artifacts))
    source_run_path.write_text(json.dumps(source_run))
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])

    with pytest.raises(ValueError):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1", artifact_inventory_path=artifacts_path,
            source_run_path=source_run_path,
        )


def test_sparse_continuation_rejects_successful_job_with_partial_evidence(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37)
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint = {
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {}, "attempts": [], "status": "incomplete", "pending": 1,
    }
    checkpoint_dir = tmp_path / "checkpoints" / "artifact"
    report_dir = tmp_path / "reports" / "artifact"
    checkpoint_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    report_dir.joinpath("mutation-report.json").write_text(json.dumps(checkpoint))

    with pytest.raises(ValueError, match="successful shard 0 has an incomplete checkpoint"):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


@pytest.mark.parametrize(
    "fault", [
        "missing", "contradictory", "duplicate", "forged-index", "empty-partial",
        "preflight", "environment", "corpus",
    ],
)
def test_sparse_continuation_rejects_unbound_partial_report(tmp_path, fault):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="failure")
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoint = {
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {}, "attempts": [], "status": "incomplete", "pending": 1,
    }
    checkpoint_dir = tmp_path / "checkpoints" / "artifact"
    report_dir = tmp_path / "reports" / "artifact"
    checkpoint_dir.mkdir(parents=True)
    report_dir.mkdir(parents=True)
    checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    report = json.loads(json.dumps(checkpoint))
    if fault == "missing":
        report.pop("identity")
    elif fault == "contradictory":
        report["pending"] = 2
    elif fault == "forged-index":
        report["shard_index"] = 0
    elif fault == "empty-partial":
        report["pending"] = 0
        checkpoint["pending"] = 0
        checkpoint_dir.joinpath("mutation-checkpoint.json").write_text(json.dumps(checkpoint))
    elif fault in {"preflight", "environment", "corpus"}:
        report["identity"][f"{fault}_digest"] = "0" * 64
    report_dir.joinpath("mutation-report.json").write_text(json.dumps(report))
    if fault == "duplicate":
        duplicate = tmp_path / "reports" / "second-artifact"
        duplicate.mkdir()
        duplicate.joinpath("mutation-report.json").write_text(json.dumps(checkpoint))

    with pytest.raises(ValueError):
        plan_calibration_continuation(
            _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
            tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
            "f" * 40, "1",
        )


def test_sparse_continuation_regenerates_report_from_complete_checkpoint(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37)
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    checkpoints = tmp_path / "checkpoints" / "0"
    checkpoints.mkdir(parents=True)
    checkpoints.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a",
        "identity": {
            "revision": "f" * 40, "preflight_digest": "e" * 64,
            "manifest_digest": "a" * 64, "corpus_digest": "d" * 64,
            "environment_digest": "c" * 64,
        },
        "outcomes": {}, "attempts": [], "status": "completed", "pending": 0,
    }))

    result = plan_calibration_continuation(
        _calibration_run_file(tmp_path), jobs_path, tmp_path / "checkpoints",
        tmp_path / "reports", manifests, [0], "calibration-a", "37", "1",
        "f" * 40, "1",
    )

    assert result["matrix"] == {"shard": [0]}
    assert result["shards"]["0"]["state"] == "completed_checkpoint_missing_report"


def test_sparse_continuation_rejects_wrong_source_run_inputs(tmp_path):
    manifests = [{"shard_index": 0, "digest": "a" * 64}]
    job = _job(1, run_id=37, conclusion="skipped", runner_id=None, steps=[])
    job["name"] = "mutation (full shard 0, advisory)"
    jobs_path = _jobs_file(tmp_path, [{"total_count": 1, "jobs": [job]}])
    run_path = _calibration_run_file(tmp_path)
    run = json.loads(run_path.read_text())
    run["calibration_id"] = "other"
    run_path.write_text(json.dumps(run))

    with pytest.raises(ValueError, match="source run provenance"):
        plan_calibration_continuation(
            run_path, jobs_path, tmp_path / "checkpoints", tmp_path / "reports",
            manifests, [0], "calibration-a", "37", "1", "f" * 40, "1",
        )


def test_calibration_continuation_and_budget_cli_delivery_path(tmp_path):
    manifests = tmp_path / "manifests"
    completed = WAVES["wave-1"][0]
    checkpoints = (
        tmp_path / "checkpoints" / f"mutation-checkpoint-calibration-a-{completed}"
    )
    reports = tmp_path / "reports" / "completed"
    manifests.mkdir()
    checkpoints.mkdir(parents=True)
    reports.mkdir(parents=True)
    for index in range(256):
        (manifests / f"partition-{index}.json").write_text(json.dumps({
            "shard_index": index, "digest": f"{index + 1:064x}",
        }))
    identity = {
        "revision": "f" * 40, "preflight_digest": "e" * 64,
        "manifest_digest": f"{completed + 1:064x}", "corpus_digest": "d" * 64,
        "environment_digest": "c" * 64,
    }
    checkpoints.joinpath("mutation-checkpoint.json").write_text(json.dumps({
        "schema_version": "1", "calibration_id": "calibration-a", "identity": identity,
        "outcomes": {"a" * 64: {"state": "killed", "duration_ms": 1}},
        "attempts": [], "status": "completed", "pending": 0,
    }))
    reports.joinpath("mutation-report.json").write_text(json.dumps({
        "status": "completed", "shard_index": completed,
        "calibration_id": "calibration-a", **identity,
    }))
    jobs = []
    for position, index in enumerate(WAVES["wave-1"]):
        if index == completed:
            job = _job(position + 1, run_id=37)
        else:
            job = _job(
                position + 1, run_id=37, conclusion="skipped", runner_id=None, steps=[],
            )
        job["name"] = f"mutation (full shard {index}, advisory)"
        jobs.append(job)
    jobs_path = _jobs_file(tmp_path, [{"total_count": len(jobs), "jobs": jobs}])
    artifacts_path = _checkpoint_artifacts_file(tmp_path, [completed])
    source_run_path = _source_workflow_run_file(tmp_path)
    run_path = _calibration_run_file(tmp_path)
    continuation = tmp_path / "continuation.json"
    script = Path(__file__).parents[1] / "scripts" / "staged_preflight.py"

    subprocess.run([
        sys.executable, str(script), "plan-calibration-continuation",
        "--provenance", str(run_path), "--jobs", str(jobs_path),
        "--artifacts", str(artifacts_path),
        "--source-run", str(source_run_path),
        "--checkpoints", str(tmp_path / "checkpoints"),
        "--reports", str(tmp_path / "reports"), "--manifests", str(manifests),
        "--stage", "1", "--calibration-id", "calibration-a",
        "--run-id", "37", "--run-attempt", "1", "--revision", "f" * 40,
        "--output", str(continuation),
    ], check=True)
    plan = json.loads(continuation.read_text())
    assert plan["matrix"]["shard"] == WAVES["wave-1"][1:]
    accounting = tmp_path / "accounting.json"
    accounting.write_text(json.dumps(plan["accounting"]))
    budget = tmp_path / "budget.json"
    subprocess.run([
        sys.executable, str(script), "calibration-budget",
        "--accounting", str(accounting), "--ceiling", "12000",
        "--cancellation-reserve", "1200", "--output", str(budget),
    ], check=True)
    retained = json.loads(budget.read_text())
    assert retained["passed"] is True
    assert retained["billing_authority"] is False
    assert retained["cancellation_lag_charge"] == 0


def test_combined_accounting_charges_original_and_recovery_attempts(tmp_path):
    prior = _jobs_file(
        tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json",
    )
    current = _jobs_file(
        tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=38)]}], "current.json",
    )

    result = combine_accounting(
        prior, current, expected_prior_run_id="37", expected_current_run_id="38",
        expected_prior_run_attempt="1", expected_current_run_attempt="1",
    )

    assert result["estimated_runner_minutes"] == 4
    assert [item["expected_run_id"] for item in result["sources"]] == ["37", "38"]


def test_three_run_accounting_preserves_every_explicit_origin(tmp_path):
    sources = [
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(index, run_id=run_id)]}],
                    f"{run_id}.json"), str(run_id), "1")
        for index, run_id in enumerate((37, 38, 39), 1)
    ]

    result = combine_accounting_sources(sources)

    assert result["estimated_runner_minutes"] == 6
    assert [item["expected_run_id"] for item in result["sources"]] == ["37", "38", "39"]


def test_terminal_reconciliation_preserves_higher_historical_accounting_floor(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps({
        **terminal, "estimated_runner_minutes": 3.5,
    }))

    result = retain_historical_accounting_floor(terminal, [historical_path])

    assert result["terminal_reconciled_runner_minutes"] == 2
    assert result["historical_observed_runner_minutes_floor"] == 3.5
    assert result["estimated_runner_minutes"] == 3.5
    assert result["historical_floor_applied"] is True
    assert result["historical_accounting"][0]["sha256"] == _file_sha(historical_path)


def test_accounting_floor_cannot_regress_from_919_51_to_854_38(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    paths = []
    for name, amount in (("earlier", 854.38), ("maximum", 919.51)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({**terminal, "estimated_runner_minutes": amount}))
        paths.append(path)

    result = retain_historical_accounting_floor(terminal, paths)

    assert result["historical_observed_runner_minutes_floor"] == 919.51
    assert result["estimated_runner_minutes"] == 919.51
    assert [item["estimated_runner_minutes"] for item in result["historical_accounting"]] == [
        854.38, 919.51,
    ]


def test_accounting_floor_uses_conservative_charged_amount(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "monitor.json"
    historical_path.write_text(json.dumps({
        **terminal,
        "estimated_runner_minutes": 844.51,
        "charged_runner_minutes": 919.51,
    }))

    result = retain_historical_accounting_floor(terminal, [historical_path])

    assert result["historical_observed_runner_minutes_floor"] == 919.51
    assert result["estimated_runner_minutes"] == 919.51


def test_explicit_representation_inventory_excludes_quarantine_and_detects_tampering(tmp_path):
    reports = tmp_path / "reports"
    valid = reports / "valid" / "mutation-report.json"
    empty = reports / "historical" / "mutation-report.json"
    valid.parent.mkdir(parents=True)
    empty.parent.mkdir(parents=True)
    valid.write_text(json.dumps({"status": "completed", "shard_index": 0}) + "\n")
    empty.write_bytes(b"")
    candidates, quarantine = load_mutation_report_candidates(reports)
    inventory = build_calibration_representation_inventory(reports, candidates, [0], quarantine)
    inventory_path = reports / "inventory.json"
    inventory_path.write_text(json.dumps(inventory))

    selected = read_calibration_representation_inventory(inventory_path)

    assert selected == [{"status": "completed", "shard_index": 0}]
    assert inventory["representations"][0]["path"] == "valid/mutation-report.json"
    assert inventory["quarantined"][0]["path"] == empty.as_posix()
    valid.write_text(json.dumps({"status": "completed", "shard_index": 1}))
    with pytest.raises(ValueError, match="digest differs"):
        read_calibration_representation_inventory(inventory_path)


def test_terminal_reconciliation_keeps_later_higher_terminal_total(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps({
        **terminal, "estimated_runner_minutes": 1.5,
    }))

    result = retain_historical_accounting_floor(terminal, [historical_path])

    assert result["terminal_reconciled_runner_minutes"] == 2
    assert result["estimated_runner_minutes"] == 2
    assert result["historical_floor_applied"] is False


def test_terminal_reconciliation_accepts_prior_floored_combined_report(tmp_path):
    prior = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json"),
        expected_run_id="37", expected_run_attempt="1",
    )
    current = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=38)]}], "current.json"),
        expected_run_id="38", expected_run_attempt="1",
    )
    terminal = {
        "schema_version": "1", "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False, "estimated_runner_minutes": 4, "sources": [prior, current],
    }
    first_path = tmp_path / "first.json"
    first_path.write_text(json.dumps({
        **terminal, "estimated_runner_minutes": 5,
        "sources": [{**prior, "estimated_runner_minutes": 3}, current],
    }))
    first = retain_historical_accounting_floor(terminal, [first_path])
    retained_path = tmp_path / "retained.json"
    retained_path.write_text(json.dumps(first))

    result = retain_historical_accounting_floor(terminal, [retained_path])

    assert result["terminal_reconciled_runner_minutes"] == 4
    assert result["estimated_runner_minutes"] == 5
    assert result["historical_floor_applied"] is True


def test_terminal_reconciliation_validates_current_accounting_without_history(tmp_path):
    malformed = {
        "schema_version": "999", "kind": "operational_runner_time_estimate",
        "billing_authority": False, "expected_run_id": "37", "expected_run_attempt": "1",
        "estimated_runner_minutes": 2,
    }

    with pytest.raises(ValueError, match="malformed"):
        retain_historical_accounting_floor(malformed, [])


def test_terminal_reconciliation_rejects_historical_origin_drift(tmp_path):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps({
        **terminal, "expected_run_id": "99",
    }))

    with pytest.raises(ValueError, match="incompatible origin"):
        retain_historical_accounting_floor(terminal, [historical_path])


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "999"), ("billing_authority", True),
     ("estimated_runner_minutes", float("nan")),
     ("estimated_runner_minutes", float("inf"))],
)
def test_terminal_reconciliation_rejects_malformed_current_accounting(tmp_path, field, value):
    terminal = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}]),
        expected_run_id="37", expected_run_attempt="1",
    )
    terminal[field] = value
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps(account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=37)]}], "prior.json"),
        expected_run_id="37", expected_run_attempt="1",
    )))

    with pytest.raises(ValueError, match="malformed"):
        retain_historical_accounting_floor(terminal, [historical_path])


@pytest.mark.parametrize("field", ["schema_version", "billing_authority"])
def test_terminal_reconciliation_rejects_malformed_nested_historical_source(tmp_path, field):
    prior = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json"),
        expected_run_id="37", expected_run_attempt="1",
    )
    current = account_runner_minutes(
        _jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=38)]}], "current.json"),
        expected_run_id="38", expected_run_attempt="1",
    )
    combined = {
        "schema_version": "1", "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False, "estimated_runner_minutes": 4, "sources": [prior, current],
    }
    historical = json.loads(json.dumps(combined))
    historical["sources"][0][field] = "999" if field == "schema_version" else True
    historical_path = tmp_path / "historical.json"
    historical_path.write_text(json.dumps(historical))

    with pytest.raises(ValueError, match="malformed"):
        retain_historical_accounting_floor(combined, [historical_path])


def test_four_run_accounting_adds_aggregation_overhead_once(tmp_path):
    sources = [
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(index, run_id=run_id)]}],
                    f"{run_id}.json"), str(run_id), "1")
        for index, run_id in enumerate((37, 38, 39, 40), 1)
    ]

    result = combine_accounting_sources(sources)

    assert result["estimated_runner_minutes"] == 8
    assert [item["expected_run_id"] for item in result["sources"]] == ["37", "38", "39", "40"]


def test_three_run_accounting_rejects_wrong_middle_origin(tmp_path):
    sources = [
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "37.json"), "37", "1"),
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(2, run_id=99)]}], "38.json"), "38", "1"),
        (_jobs_file(tmp_path, [{"total_count": 1, "jobs": [_job(3, run_id=39)]}], "39.json"), "39", "1"),
    ]

    with pytest.raises(ValueError, match="origin"):
        combine_accounting_sources(sources)


def test_continuation_artifact_inventory_is_exact_and_digest_bound(monkeypatch, tmp_path):
    artifacts = [
        {"id": index + 1, "name": f"mutation-preflight-wave-3-37550308775-1-{index}",
         "size_in_bytes": 1, "digest": f"sha256:{index:064x}", "expired": False}
        for index in WAVES["wave-3"]
    ]
    path = tmp_path / "artifacts.json"
    path.write_text(json.dumps([{"artifacts": artifacts}]))
    artifacts = sorted(artifacts, key=lambda artifact: artifact["name"])
    digest = __import__("hashlib").sha256(
        json.dumps(artifacts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    monkeypatch.setattr("scripts.staged_preflight.CONTINUATION_ARTIFACT_INVENTORY_SHA256", digest)

    result = validate_continuation_artifacts(path)

    assert result["reports"] == 216
    assert result["inventory_sha256"] == digest


@pytest.mark.parametrize("fault", ["missing", "expired", "digest", "inventory"])
def test_continuation_artifact_inventory_rejects_conflicts(monkeypatch, tmp_path, fault):
    artifacts = [
        {"id": index + 1, "name": f"mutation-preflight-wave-3-37550308775-1-{index}",
         "size_in_bytes": 1, "digest": f"sha256:{index:064x}", "expired": False}
        for index in WAVES["wave-3"]
    ]
    if fault == "missing":
        artifacts.pop()
    elif fault == "expired":
        artifacts[0]["expired"] = True
    elif fault == "digest":
        artifacts[0]["digest"] = "unknown"
    path = tmp_path / "artifacts.json"
    path.write_text(json.dumps([{"artifacts": artifacts}]))
    monkeypatch.setattr(
        "scripts.staged_preflight.CONTINUATION_ARTIFACT_INVENTORY_SHA256", "0" * 64,
    )

    with pytest.raises(ValueError):
        validate_continuation_artifacts(path)


def test_combined_accounting_rejects_recovery_attempt_two(tmp_path):
    prior = _jobs_file(
        tmp_path, [{"total_count": 1, "jobs": [_job(1, run_id=37)]}], "prior.json",
    )
    current = _jobs_file(
        tmp_path,
        [{"total_count": 1, "jobs": [_job(2, run_id=38, run_attempt=2)]}],
        "current.json",
    )

    with pytest.raises(ValueError, match="origin"):
        combine_accounting(
            prior, current, expected_prior_run_id="37", expected_current_run_id="38",
            expected_prior_run_attempt="1", expected_current_run_attempt="1",
        )


def test_recovery_plan_reuses_only_exact_compatible_wave_one(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    source_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF,
        "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_plan = build_plan(root, manifests_dir, SOURCE_ORCHESTRATION_SHA, source_identity)
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(reports, manifests)
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", _file_sha(source_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {
            index: _file_sha(reports / str(index) / "mutation-preflight.json")
            for index in WAVES["wave-1"]
        },
    )
    recovery_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": "owner/repo/.github/workflows/mutation.yml@refs/heads/recovery",
        "run_id": "38", "run_attempt": "1",
    }

    result = build_recovery_plan(
        root, source_plan_path, manifests_dir, reports, "b" * 40, recovery_identity,
    )

    assert result["source"]["run_id"] == SOURCE_RUN_ID
    assert set(result["execution_waves"]) == {"wave-2", "wave-3"}
    assert result["origin_assignment"]["8"]["run_id"] == SOURCE_RUN_ID
    assert result["origin_assignment"]["0"]["run_id"] == "38"


def test_continuation_plan_revalidates_both_runs_and_schedules_only_wave_three(
    monkeypatch, tmp_path,
):
    root, manifests_dir, source_reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    source_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_plan = build_plan(root, manifests_dir, SOURCE_ORCHESTRATION_SHA, source_identity)
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(source_reports, manifests, "wave-1")
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", _file_sha(source_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {index: _file_sha(source_reports / str(index) / "mutation-preflight.json")
         for index in WAVES["wave-1"]},
    )
    recovery_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": RECOVERY_RUN_ID, "run_attempt": "1",
    }
    recovery_plan = build_recovery_plan(
        root, source_plan_path, manifests_dir, source_reports,
        RECOVERY_ORCHESTRATION_SHA, recovery_identity,
    )
    recovery_plan_path = tmp_path / "recovery-plan.json"
    recovery_plan_path.write_text(json.dumps(recovery_plan))
    recovery_reports = tmp_path / "recovery-reports"
    recovery_reports.mkdir()
    _write_wave(recovery_reports, manifests, "wave-2")
    recovery_validation = validate_wave(
        root, recovery_plan_path, manifests_dir, recovery_reports, "wave-2",
        RECOVERY_ORCHESTRATION_SHA, recovery_identity,
    )
    recovery_validation_path = tmp_path / "recovery-validation.json"
    recovery_validation_path.write_text(json.dumps(recovery_validation))
    monkeypatch.setattr("scripts.staged_preflight.RECOVERY_PLAN_SHA256", _file_sha(recovery_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.RECOVERY_VALIDATION_SHA256",
        _file_sha(recovery_validation_path),
    )
    monkeypatch.setattr(
        "scripts.staged_preflight.RECOVERY_REPORT_SHA256",
        {index: _file_sha(recovery_reports / str(index) / "mutation-preflight.json")
         for index in WAVES["wave-2"]},
    )
    continuation_identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "owner/repo/.github/workflows/staged-preflight-continuation.yml@refs/heads/test",
        "run_id": "39", "run_attempt": "1",
    }

    result = build_continuation_plan(
        root, source_plan_path, source_reports, recovery_plan_path, recovery_reports,
        recovery_validation_path, manifests_dir, "c" * 40, continuation_identity,
    )

    assert result["execution_wave"]["shards"] == WAVES["wave-3"]
    assert result["topology"]["expanded_jobs"] == 229
    assert result["origin_assignment"]["8"]["run_id"] == SOURCE_RUN_ID
    assert result["origin_assignment"]["0"]["run_id"] == RECOVERY_RUN_ID
    assert result["origin_assignment"]["35"]["run_id"] == "39"


def test_fresh_continuation_uses_validated_immutable_candidate_inputs(monkeypatch, tmp_path):
    root, manifests_dir, wave_1_reports, manifests, _, source_plan_path = _fixture(
        monkeypatch, tmp_path,
    )
    source_plan = json.loads(source_plan_path.read_text())
    source_plan["workflow"]["run_id"] = "37"
    source_plan["workflow"]["workflow_ref"] = SOURCE_WORKFLOW_REF
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(wave_1_reports, manifests, "wave-1")
    wave_2_reports = tmp_path / "wave-2-reports"
    wave_2_reports.mkdir()
    _write_wave(wave_2_reports, manifests, "wave-2")
    source_identity = source_plan["workflow"]
    validations = []
    for wave, reports in (("wave-1", wave_1_reports), ("wave-2", wave_2_reports)):
        validation = validate_wave(
            root, source_plan_path, manifests_dir, reports, wave, "a" * 40, source_identity,
        )
        path = tmp_path / f"{wave}-validation.json"
        path.write_text(json.dumps(validation))
        validations.append(path)
    continuation_identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "owner/repo/.github/workflows/staged-preflight-continuation.yml@refs/heads/test",
        "run_id": "38", "run_attempt": "1",
    }

    result = build_fresh_continuation_plan(
        root, source_plan_path, wave_1_reports, wave_2_reports,
        validations[0], validations[1], manifests_dir, _file_sha(source_plan_path),
        "37", "a" * 40, SOURCE_WORKFLOW_REF, FROZEN_CANDIDATE,
        continuation_identity, FROZEN_CANDIDATE,
    )

    assert result["candidate_sha"] == FROZEN_CANDIDATE
    assert result["execution_wave"]["shards"] == WAVES["wave-3"]
    assert result["source"]["validations"]["wave-2"]["passed"] is True
    assert result["origin_assignment"]["0"]["run_id"] == "37"
    assert result["origin_assignment"]["35"]["run_id"] == "38"


def test_fresh_continuation_rejects_changed_candidate_or_plan_digest(monkeypatch, tmp_path):
    root, manifests_dir, reports, _manifests, _, source_plan_path = _fixture(monkeypatch, tmp_path)
    validation = tmp_path / "validation.json"
    validation.write_text("{}")
    identity = {
        "repository": "owner/repo", "workflow": "Staged preflight continuation",
        "workflow_ref": "ref", "run_id": "38", "run_attempt": "1",
    }

    with pytest.raises(ValueError):
        build_fresh_continuation_plan(
            root, source_plan_path, reports, reports, validation, validation,
            manifests_dir, "0" * 64, "37", "a" * 40, SOURCE_WORKFLOW_REF,
            "b" * 40, identity, "f" * 40,
        )


def test_fresh_completion_record_reconciles_exact_once_corpus(monkeypatch, tmp_path):
    root, manifests_dir, reports, manifests, identity, _ = _fixture(monkeypatch, tmp_path)
    identity["run_id"] = "38"
    plan = build_plan(root, manifests_dir, "b" * 40, identity)
    plan.update({
        "mode": "fresh-staged-preflight-continuation",
        "source": {"run_id": "37", "run_attempt": "1"},
        "origin_assignment": {
            str(index): {"run_id": "37" if index not in WAVES["wave-3"] else "38",
                         "run_attempt": "1", "wave": next(name for name, shards in WAVES.items() if index in shards)}
            for index in range(256)
        },
    })
    for wave in WAVES:
        _write_wave(reports, manifests, wave)
    plan_path = tmp_path / "fresh-plan.json"
    plan_path.write_text(json.dumps(plan))
    aggregate_path = tmp_path / "aggregate.json"
    aggregate_path.write_text(json.dumps({
        "status": "completed", "passed": True, "revision": FROZEN_CANDIDATE,
        "shard_count": 256, "manifest_digests": plan["manifest_digests"],
        "generated": 256, "canonicalized": 256, "collisions": 0,
    }))

    result = build_fresh_completion_record(plan_path, reports, aggregate_path)

    assert result["kind"] == "fresh_staged_preflight"
    assert len(result["origins"]) == 256


def _file_sha(path):
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("fault", ["plan", "report", "runtime", "policy", "topology"])
def test_recovery_plan_rejects_incompatible_or_modified_source(monkeypatch, tmp_path, fault):
    root, manifests_dir, reports, manifests, _, _ = _fixture(monkeypatch, tmp_path)
    source_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF,
        "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_plan = build_plan(root, manifests_dir, SOURCE_ORCHESTRATION_SHA, source_identity)
    if fault == "runtime":
        source_plan["runtime"]["python"] = "0.0"
    elif fault == "policy":
        source_plan["policy"]["fettle_toml_sha256"] = "0" * 64
    elif fault == "topology":
        source_plan["manifest_digests"][0] = "f" * 64
    source_plan_path = tmp_path / "source-plan.json"
    source_plan_path.write_text(json.dumps(source_plan))
    _write_wave(reports, manifests)
    monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", _file_sha(source_plan_path))
    monkeypatch.setattr(
        "scripts.staged_preflight.SOURCE_REPORT_SHA256",
        {index: _file_sha(reports / str(index) / "mutation-preflight.json") for index in WAVES["wave-1"]},
    )
    if fault == "plan":
        monkeypatch.setattr("scripts.staged_preflight.SOURCE_PLAN_SHA256", "0" * 64)
    elif fault == "report":
        expected = dict(SOURCE_REPORT_SHA256)
        expected[WAVES["wave-1"][0]] = "0" * 64
        monkeypatch.setattr("scripts.staged_preflight.SOURCE_REPORT_SHA256", expected)
    recovery_identity = {
        "repository": "owner/repo", "workflow": "Mutation evidence",
        "workflow_ref": "owner/repo/.github/workflows/mutation.yml@refs/heads/recovery",
        "run_id": "38", "run_attempt": "1",
    }

    with pytest.raises(ValueError):
        build_recovery_plan(
            root, source_plan_path, manifests_dir, reports, "b" * 40, recovery_identity,
        )
