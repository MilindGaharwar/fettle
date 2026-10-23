"""P34 mutation evidence integrity contracts."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from fettle.mutation_test import (
    build_capacity_validation_plan,
    _canonical_digest,
    evaluate_capacity_validation_decision,
    merge_mutation_checkpoints,
    load_capacity_validation_plan,
    run_capacity_validation_unit,
    validate_capacity_validation_package,
    reconcile_capacity_recovery_provider_accounting,
)

FIXTURES = Path(__file__).parent / "fixtures" / "mutation"


FIXTURES = Path(__file__).parent / "fixtures" / "mutation"

def _capacity_preflight():
    from fettle.staged_preflight import capacity_authorization_contract
    manifests = []
    corpus = []
    fingerprints = []
    for group in range(6):
        for file_index in range(2):
            shard = group * 2 + file_index
            file = f"src/group_{group}_{file_index}.py"
            ranges = [
                {"file": file, "start": 1, "end": 10},
                {"file": file, "start": 11, "end": 20},
            ]
            manifest = {
                "schema_version": "1", "revision": "a" * 40, "shard_index": shard,
                "shard_count": 12, "files": [file], "ranges": ranges,
            }
            manifest["digest"] = _canonical_digest(manifest)
            manifests.append(manifest)
            mapped_tests = [f"tests/test_group_{group}_{file_index}.py"] + [
                f"tests/test_group_{group}_{index}.py"
                for index in range(group + 1) if index != file_index
            ]
            for ordinal in range(file_index + 1):
                fingerprint = f"{group:02x}{file_index:02x}{ordinal:02x}".ljust(64, "a")
                fingerprints.append(fingerprint)
                corpus.append({
                    "fingerprint": fingerprint, "file": file,
                    # Canonical lines need not be literally inside a manifest range.
                    "line": 30 + ordinal,
                    "mapped_tests": mapped_tests,
                    "shard_index": shard,
                })
    corpus.sort(key=lambda item: item["fingerprint"])
    preflight = {
        "kind": "capacity_validation_corpus", "status": "enumerated", "passed": False,
        "qualification_eligible": False, "billing_authority": False,
        "authoritative_predecessor": False,
        "authorization_id": "AH-PREP-CONTAINMENT-20261019-C",
        "authorization_contract": capacity_authorization_contract(
            "AH-PREP-CONTAINMENT-20261019-C", "a" * 40, "capval-local",
        ),
        "revision": "a" * 40,
        "shard_count": 12,
        "corpus": corpus, "fingerprints": sorted(fingerprints),
        "corpus_digest": _canonical_digest(corpus),
        "manifest_digests": [item["digest"] for item in manifests],
    }
    return preflight, manifests


def _capacity_mapping():
    return {
        f"src/group_{group}_{file_index}.py": [f"tests/test_group_{group}_{file_index}.py"] + [
            f"tests/test_group_{group}_{index}.py"
            for index in range(group + 1) if index != file_index
        ]
        for group in range(6) for file_index in range(2)
    }


def _capacity_historical_source():
    return {
        "candidate_sha": "9" * 40,
        "run_ids": ["31850858224", "31865158733"],
        "artifact_counts": {"31850858224": 514, "31865158733": 514},
        "historical_fingerprint_digest": "75807358bcaaed80efb2f0f3cd5ed99e9f573f2ded26c50e2c6281c851abe5b3",
        "candidate_matched_fingerprint_digest": "cc57b1f709083447884b31ac5f67d647d9fc15a73b2e84bda18d68e06e0aa1de",
        "candidate_matched_fingerprint_count": 0,
        "candidate_measured_file_digest": _canonical_digest([]),
        "candidate_measured_file_count": 0,
        "engine_version": "2.5.1",
        "evidence_role": "modeling_only_terminal_non_pass",
        "reusable_for_candidate": False,
    }


def test_capacity_plan_selects_whole_file_units_across_six_cost_strata(tmp_path):
    preflight, manifests = _capacity_preflight()
    predictions = {"optimistic": 10, "central": 20, "conservative": 30, "stress": 40}

    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        first = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds=predictions,
        )
        second = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, list(reversed(manifests)),
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds=predictions,
        )

    assert first["coverage"]["selected_units"] == 12
    assert [unit["cost_stratum"] for unit in first["units"]] == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert [len(unit["fingerprints"]) for unit in first["units"]] == [1, 2] * 6
    assert all(len(unit["ranges"]) == 2 for unit in first["units"])
    assert all(unit["historically_measured_file"] is False for unit in first["units"])
    assert first["passed"] is False and first["qualification_eligible"] is False
    contract = first["decision_contract"]
    assert contract["prediction_error"]["absolute_relative_error_median_max"] == 0.35
    assert contract["ranking"]["reject_distinct_group_inversions_min"] == 2
    assert contract["timers"]["execution"]["deadline_seconds"] == 720
    assert contract["timers"]["workflow_step"]["deadline_seconds"] == 840
    assert contract["timers"]["operating_target"]["deadline_seconds"] == 960
    assert contract["timers"]["whole_worker"]["deadline_seconds"] == 1200
    assert contract["censoring"]["shorter_timeout_never_proves_operating_target_exceeded"] is True
    assert contract["outcome_precedence"][-1] == "inconclusive"
    assert contract["substitution_allowed"] is contract["rerun_allowed"] is False
    assert first["authorization_id"] == "AH-PREP-CONTAINMENT-20261019-C"
    assert second == first

    path = tmp_path / "plan.json"
    path.write_text(json.dumps(first))
    assert load_capacity_validation_plan(path) == first


def test_capacity_plan_accepts_equal_mapping_membership_and_preserves_execution_order():
    preflight, manifests = _capacity_preflight()
    recorded = preflight["corpus"][0]["mapped_tests"]
    assert len(recorded) == 1
    preflight["corpus"][0]["mapped_tests"] = list(reversed(recorded))
    actual = _capacity_mapping()
    target = next(iter(actual))
    actual[target] = ["tests/test_secondary.py", *actual[target]]
    for record in preflight["corpus"]:
        if record["file"] == target:
            record["mapped_tests"] = sorted(actual[target])
    preflight["corpus_digest"] = _canonical_digest(preflight["corpus"])

    with (
        patch("fettle.mutation_test._mapped_tests", side_effect=lambda _root, files, _mapping: {
            file: actual[file] for file in files
        }),
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        plan = build_capacity_validation_plan(
            ".", {"test_mappings": actual}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
        )

    selected = [unit for unit in plan["units"] if unit["file"] == target]
    assert all(unit["mapped_tests"] == actual[target] for unit in selected)


def test_capacity_plan_rejects_fewer_than_twelve_unmeasured_file_windows():
    preflight, manifests = _capacity_preflight()
    preflight["corpus"] = [record for record in preflight["corpus"] if record["shard_index"] < 11]
    preflight["fingerprints"] = [record["fingerprint"] for record in preflight["corpus"]]
    preflight["corpus_digest"] = _canonical_digest(preflight["corpus"])

    with pytest.raises(ValueError, match="twelve historically unmeasured"):
        with (
            patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
            patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
        ):
            build_capacity_validation_plan(
                ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
                experiment_id="capval-local", revision="a" * 40,
                historical_measured_files=set(), historical_source=_capacity_historical_source(),
                prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
            )


def test_capacity_file_window_attribution_rejects_unowned_fingerprint():
    preflight, manifests = _capacity_preflight()
    preflight["corpus"][0] = {**preflight["corpus"][0], "shard_index": 1}
    preflight["corpus_digest"] = _canonical_digest(preflight["corpus"])

    with pytest.raises(ValueError, match="do not exactly cover"):
        build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
        )


def test_capacity_plan_rejects_tampering_and_calibration_inventory(tmp_path):
    preflight, manifests = _capacity_preflight()
    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        plan = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
        )
    plan["units"][0]["fingerprints"].append("f" * 64)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))

    with pytest.raises(ValueError, match="digest differs"):
        load_capacity_validation_plan(path)
    from fettle.mutation_test import read_calibration_representation_inventory
    with pytest.raises(ValueError, match="malformed"):
        read_calibration_representation_inventory(path)

    from fettle.mutation_test import (
        load_mutation_report_candidates,
    )
    reports, quarantined = load_mutation_report_candidates(tmp_path)
    assert reports == []
    assert quarantined == []
    with pytest.raises(ValueError):
        merge_mutation_checkpoints([plan], set())


def test_capacity_unit_executes_only_frozen_fingerprints_and_is_non_authoritative(tmp_path):
    preflight, manifests = _capacity_preflight()
    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        plan = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
        )
    unit = plan["units"][0]
    source = tmp_path / unit["file"]
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n" * 20)
    tests = tmp_path / unit["mapped_tests"][0]
    tests.parent.mkdir(parents=True)
    tests.write_text("def test_value():\n    assert True\n")
    plan_path = tmp_path / "plan.json"
    preflight_path = tmp_path / "preflight.json"
    plan_path.write_text(json.dumps(plan))
    preflight_path.write_text(json.dumps(preflight))
    completed = {
        "outcomes": {fp: {"state": "killed", "duration_ms": 5} for fp in unit["fingerprints"]},
        "attempts": [], "pending": 0, "status": "completed",
    }

    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
        patch("fettle.mutation_test.execute_pending_mutations", return_value=completed) as execute,
    ):
        result = run_capacity_validation_unit(
            str(tmp_path), {"test_mappings": _capacity_mapping()}, plan_path, preflight_path, 0, 720,
        )

    assert result["status"] == "completed"
    assert result["passed"] is result["qualification_eligible"] is False
    assert result["billing_authority"] is result["authoritative_predecessor"] is False
    assert result["source_restoration"]["restored"] is True
    assert [record["fingerprint"] for record in execute.call_args.args[1]] == unit["fingerprints"]
    assert execute.call_args.args[3] == unit["ranges"]
    assert execute.call_args.args[5] == 720


def test_capacity_unit_preserves_partial_and_rejects_foreign_inputs(tmp_path):
    preflight, manifests = _capacity_preflight()
    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        plan = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
        )
    plan_path = tmp_path / "plan.json"
    preflight_path = tmp_path / "preflight.json"
    plan_path.write_text(json.dumps(plan))
    preflight_path.write_text(json.dumps({**preflight, "revision": "b" * 40}))

    with patch("fettle.mutation_test.execute_pending_mutations") as execute:
        result = run_capacity_validation_unit(
            str(tmp_path), {}, plan_path, preflight_path, 0, 720,
        )

    assert result["status"] == "unknown"
    assert result["passed"] is result["qualification_eligible"] is False
    assert result["authorization_id"] == plan["authorization_id"]
    assert result["authorization_contract"] == plan["authorization_contract"]
    execute.assert_not_called()


def test_capacity_package_reproduces_and_rejects_tampered_corpus(tmp_path):
    preflight, manifests = _capacity_preflight()
    manifest_dir = tmp_path / "capacity-manifests"
    manifest_dir.mkdir()
    for manifest in manifests:
        (manifest_dir / f"partition-{manifest['shard_index']}.json").write_text(json.dumps(manifest))
    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        plan = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds={"optimistic": 10, "central": 20, "conservative": 30, "stress": 40},
        )
        plan_path = tmp_path / "capacity-validation-plan.json"
        corpus_path = tmp_path / "capacity-validation-corpus.json"
        plan_path.write_text(json.dumps(plan))
        corpus_path.write_text(json.dumps(preflight))
        plan_file_sha256 = __import__("hashlib").sha256(plan_path.read_bytes()).hexdigest()
        validated = validate_capacity_validation_package(
            ".", {"test_mappings": _capacity_mapping()}, tmp_path,
            revision="a" * 40, experiment_id="capval-local",
            plan_file_sha256=plan_file_sha256,
        )
        assert validated == plan
        corpus_path.write_text(json.dumps({**preflight, "revision": "b" * 40}))
        with pytest.raises(ValueError, match="corpus digest differs"):
            validate_capacity_validation_package(
                ".", {"test_mappings": _capacity_mapping()}, tmp_path,
                revision="a" * 40, experiment_id="capval-local",
                plan_file_sha256=plan_file_sha256,
            )
        with pytest.raises(ValueError, match="file SHA-256 differs"):
            validate_capacity_validation_package(
                ".", {"test_mappings": _capacity_mapping()}, tmp_path,
                revision="a" * 40, experiment_id="capval-local",
                plan_file_sha256="0" * 64,
            )


def test_capacity_recovery_provider_accounting_is_separate_bounded_and_non_authoritative():
    from fettle.staged_preflight import capacity_recovery_authorization_contract

    source_sha = "65e63d953b45d3672c24df74d0a1364b83a0157b"
    controller = "b" * 40
    authorization = "AH-CORPUS-RECOVERY-20261020-A"
    experiment = "capval-corpus-recovery-20261020-a"
    contract = capacity_recovery_authorization_contract(authorization, source_sha, experiment)
    source = {
        "schema_version": "1", "kind": "capacity_validation_recovery_execution_source",
        "source_candidate_sha": source_sha, "controller_sha": controller,
        "recovery_experiment_id": experiment, "recovery_run_id": "100",
        "plan_file_sha256": "p" * 64, "authorization_id": authorization,
        "authorization_contract": contract,
    }
    run = {
        "id": 123, "run_attempt": 1, "head_sha": controller,
        "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
        "path": ".github/workflows/mutation.yml",
    }
    recovery_run = {**run, "id": 100}

    def job(name, job_id, *, run_id=123):
        return {
            "id": job_id, "name": name, "status": "completed", "conclusion": "success",
            "run_id": run_id, "run_attempt": 1,
            "started_at": "2026-10-20T10:00:00Z", "completed_at": "2026-10-20T10:01:00Z",
        }

    workers = [job(f"capacity recovery validation unit {index}", index + 1) for index in range(12)]
    support = [
        job("capacity recovery (execution admission)", 13),
        job("capacity recovery (execution finalization)", 14),
    ]
    controller_job = job(
        "capacity-recovery-measurement-monitor / capacity validation (monitor measurement containment)", 15,
    )
    jobs = [*workers, *support, controller_job]
    freeze_jobs = [job("capacity validation (recover retained corpus)", 16, run_id=100)]
    failed_freeze_jobs = [
        {**job("capacity validation (recover retained corpus)", 17, run_id=39369184372), "conclusion": "failure"},
    ]
    failed_recovery_run = {
        **run, "id": 39369184372,
        "head_sha": "276ac10bb7b2ec7b80346e821c2324d12bfab73f",
        "conclusion": "failure",
    }
    missing_input_recovery_run = {
        **run, "id": 39378451442,
        "head_sha": "8e46125ff7d0e6f7d3a845faed32fb14336a5185",
        "conclusion": "failure",
    }
    missing_input_freeze_jobs = [
        {**job("capacity validation (recover retained corpus)", 18, run_id=39378451442), "conclusion": "failure"},
    ]

    ledger = reconcile_capacity_recovery_provider_accounting(
        run, [{"total_count": len(jobs), "jobs": jobs}], recovery_run,
        [{"total_count": 1, "jobs": freeze_jobs}], failed_recovery_run,
        [{"total_count": 1, "jobs": failed_freeze_jobs}], missing_input_recovery_run,
        [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
        repository="owner/repo", source_revision=source_sha, controller_sha=controller,
        recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
        plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
        recovery_authorization_contract=contract,
    )

    assert ledger["status"] == "completed" and ledger["passed"] is False
    assert ledger["billing_authority"] is False
    assert ledger["worker"]["ceiling_minutes"] == 240
    assert ledger["recovery_freeze"]["ceiling_minutes"] == 30
    assert ledger["recovery_freeze"]["minutes"] == 3
    assert ledger["support"]["ceiling_minutes"] == 25
    assert ledger["cancellation_controller"]["ceiling_minutes"] == 30
    assert ledger["terminal_readback"]["ceiling_minutes"] == 10
    assert ledger["terminal_readback"]["charged_minutes"] == 10
    assert ledger["historical_non_billing_floor_minutes"]["workers"] == 475.89
    exhausted_workers = [
        {**item, "completed_at": "2026-10-20T10:21:00Z"} for item in workers
    ]
    exhausted_ledger = reconcile_capacity_recovery_provider_accounting(
        run, [{"total_count": len(jobs), "jobs": [
            *exhausted_workers, *support, controller_job,
        ]}], recovery_run, [{"total_count": 1, "jobs": freeze_jobs}],
        failed_recovery_run, [{"total_count": 1, "jobs": failed_freeze_jobs}],
        missing_input_recovery_run,
        [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
        repository="owner/repo", source_revision=source_sha, controller_sha=controller,
        recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
        plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
        recovery_authorization_contract=contract,
    )
    assert exhausted_ledger["worker"]["minutes"] == 252
    assert exhausted_ledger["worker"]["ceiling_minutes"] == 240
    assert exhausted_ledger["status"] == "non_pass"
    retry_recovery_run = {
        **run, "id": 39391306615,
        "head_sha": "ebd1e057ae3497b6ec72ef709a08d0c33d1b2bb8",
        "conclusion": "failure",
    }
    retry_freeze_jobs = [
        {
            **job("capacity validation (recover retained corpus)", 118523223941, run_id=39391306615),
            "conclusion": "failure", "started_at": "2026-10-20T08:08:56Z",
            "completed_at": "2026-10-20T08:10:03Z",
        },
    ]
    retry_ledger = reconcile_capacity_recovery_provider_accounting(
        run, [{"total_count": len(jobs), "jobs": jobs}], recovery_run,
        [{"total_count": 1, "jobs": freeze_jobs}], failed_recovery_run,
        [{"total_count": 1, "jobs": failed_freeze_jobs}], missing_input_recovery_run,
        [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
        repository="owner/repo", source_revision=source_sha, controller_sha=controller,
        recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
        plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
        recovery_authorization_contract=contract, retry_recovery_run=retry_recovery_run,
        retry_recovery_job_pages=[{"total_count": 1, "jobs": retry_freeze_jobs}],
    )
    assert retry_ledger["recovery_freeze"]["minutes"] == 5
    with pytest.raises(ValueError, match="execution job identity"):
        reconcile_capacity_recovery_provider_accounting(
            run, [{"total_count": len(jobs), "jobs": [
                {**workers[0], "run_id": 999}, *workers[1:], *support, controller_job,
            ]}], recovery_run, [{"total_count": 1, "jobs": freeze_jobs}],
            failed_recovery_run, [{"total_count": 1, "jobs": failed_freeze_jobs}],
            missing_input_recovery_run,
            [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
            repository="owner/repo", source_revision=source_sha, controller_sha=controller,
            recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
            plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
            recovery_authorization_contract=contract,
        )
    with pytest.raises(ValueError, match="recovery freeze job identity"):
        reconcile_capacity_recovery_provider_accounting(
            run, [{"total_count": len(jobs), "jobs": jobs}], recovery_run,
            [{"total_count": 1, "jobs": [{**freeze_jobs[0], "run_attempt": 2}]}],
            failed_recovery_run, [{"total_count": 1, "jobs": failed_freeze_jobs}],
            missing_input_recovery_run,
            [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
            repository="owner/repo", source_revision=source_sha, controller_sha=controller,
            recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
            plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
            recovery_authorization_contract=contract,
        )
    nonterminal_predecessor = [{
        "total_count": 1,
        "jobs": [{**failed_freeze_jobs[0], "status": "in_progress", "conclusion": None}],
    }]
    with pytest.raises(ValueError, match="predecessor jobs"):
        reconcile_capacity_recovery_provider_accounting(
            run, [{"total_count": len(jobs), "jobs": jobs}], recovery_run,
            [{"total_count": 1, "jobs": freeze_jobs}], failed_recovery_run,
            nonterminal_predecessor, missing_input_recovery_run,
            [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
            repository="owner/repo", source_revision=source_sha, controller_sha=controller,
            recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
            plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
            recovery_authorization_contract=contract,
        )
    with pytest.raises(ValueError, match="stale"):
        reconcile_capacity_recovery_provider_accounting(
            {**run, "head_sha": source_sha}, [{"total_count": len(jobs), "jobs": jobs}],
            recovery_run, [{"total_count": 1, "jobs": freeze_jobs}], failed_recovery_run,
            [{"total_count": 1, "jobs": failed_freeze_jobs}], missing_input_recovery_run,
            [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
            repository="owner/repo", source_revision=source_sha, controller_sha=controller,
            recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
            plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
            recovery_authorization_contract=contract,
        )
    with pytest.raises(ValueError, match="freeze provider identity"):
        reconcile_capacity_recovery_provider_accounting(
            run, [{"total_count": len(jobs), "jobs": jobs}],
            {**recovery_run, "conclusion": "failure"},
            [{"total_count": 1, "jobs": freeze_jobs}], failed_recovery_run,
            [{"total_count": 1, "jobs": failed_freeze_jobs}], missing_input_recovery_run,
            [{"total_count": 1, "jobs": missing_input_freeze_jobs}], source,
            repository="owner/repo", source_revision=source_sha, controller_sha=controller,
            recovery_experiment_id=experiment, execution_run_id="123", recovery_run_id="100",
            plan_file_sha256="p" * 64, recovery_authorization_id=authorization,
            recovery_authorization_contract=contract,
        )



def _capacity_decision_fixture(tmp_path):
    preflight, manifests = _capacity_preflight()
    predictions = {
        "optimistic": 30, "central": 60, "conservative": 90, "stress": 120,
    }
    with (
        patch("fettle.mutation_test._runtime_cache_identity", return_value={"environment": "fixture"}),
        patch("fettle.mutation_test._checkpoint_environment_digest", return_value="e" * 64),
    ):
        plan = build_capacity_validation_plan(
            ".", {"test_mappings": _capacity_mapping()}, preflight, manifests,
            experiment_id="capval-local", revision="a" * 40,
            historical_measured_files=set(), historical_source=_capacity_historical_source(),
            prediction_seconds=predictions,
        )
    reports = []
    for unit in plan["units"]:
        seconds = round(len(unit["fingerprints"]) * predictions["central"])
        report = {
            "status": "completed", "unit_index": unit["unit_index"], "unit": unit,
            "plan_digest": plan["digest"], "elapsed_ms": seconds * 1000,
        }
        reports.append(report)
    return plan, reports


def test_capacity_decision_invests_only_when_every_frozen_gate_passes(tmp_path):
    plan, reports = _capacity_decision_fixture(tmp_path)

    decision = evaluate_capacity_validation_decision(
        plan, reports, {index: 800 for index in range(12)},
    )

    assert decision["outcome"] == "invest"
    assert decision["exact_units"] == list(range(12))
    assert len(decision["ranking"]["concordant_groups"]) == 6
    assert decision["ranking"]["material_inversion_groups"] == []


def test_capacity_decision_rejects_two_distinct_material_group_inversions(tmp_path):
    plan, reports = _capacity_decision_fixture(tmp_path)
    inverted_groups = {
        plan["units"][0]["cost_stratum"],
        next(unit["cost_stratum"] for unit in plan["units"]
             if unit["cost_stratum"] != plan["units"][0]["cost_stratum"]),
    }
    for report in reports:
        unit = report["unit"]
        if unit["cost_stratum"] in inverted_groups:
            report["elapsed_ms"] = (200 if unit["cost_class"] == "low" else 100) * 1000

    decision = evaluate_capacity_validation_decision(
        plan, reports, {index: 800 for index in range(12)},
    )

    assert decision["outcome"] == "reject_ranking"
    assert {int(item) for item in decision["ranking"]["material_inversion_groups"]} == inverted_groups


def test_capacity_decision_preserves_inconclusive_for_shorter_censor(tmp_path):
    plan, reports = _capacity_decision_fixture(tmp_path)
    reports[0] = {"status": "incomplete", "unit_index": 0}

    decision = evaluate_capacity_validation_decision(
        plan, reports, {index: 800 for index in range(12)},
    )

    assert decision["outcome"] == "inconclusive"
    assert decision["unknown_or_censored_units"] == [0]
    assert decision["granularity"]["exact_whole_worker_target_exceedances"] == []
    assert decision["granularity"]["shorter_timeout_inference_allowed"] is False


def test_capacity_decision_rejects_only_exact_whole_worker_target_exceedance(tmp_path):
    plan, reports = _capacity_decision_fixture(tmp_path)

    decision = evaluate_capacity_validation_decision(
        plan, reports, {**{index: 800 for index in range(12)}, 3: 961},
    )

    assert decision["outcome"] == "reject_granularity"
    assert decision["granularity"]["exact_whole_worker_target_exceedances"] == [3]


def test_capacity_decision_rejects_zero_or_malformed_provider_worker_intervals(tmp_path):
    plan, reports = _capacity_decision_fixture(tmp_path)

    for malformed in (
        {**{index: 800 for index in range(12)}, 3: 0},
        {**{index: 800 for index in range(12)}, 3: True},
    ):
        with pytest.raises(ValueError, match="provider worker timing is malformed"):
            evaluate_capacity_validation_decision(plan, reports, malformed)
