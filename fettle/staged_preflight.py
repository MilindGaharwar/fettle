#!/usr/bin/env python3
"""Validate fixed staged-preflight execution and linked recovery evidence."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import platform
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

FROZEN_CANDIDATE = "0fc41fdfee13e09f4bda3dc5eee177030882aa36"
CAPACITY_AUTHORIZATION_ID = "AH-PREP-CONTAINMENT-20261019-C"
CAPACITY_RECOVERY_AUTHORIZATION_ID = "AH-CORPUS-RECOVERY-20261020-A"
CAPACITY_RECOVERY_EXPERIMENT_ID = "capval-corpus-recovery-20261020-a"
CAPACITY_RECOVERY_CANDIDATE = "65e63d953b45d3672c24df74d0a1364b83a0157b"
LINUX_MEASUREMENT_AUTHORIZATION_ID = "AH-LINUX-MEASUREMENT-20261021-A"
LINUX_MEASUREMENT_EXPERIMENT_ID = "capval-linux-measurement-20261021-a"
LINUX_MEASUREMENT_ENVIRONMENT_DIGEST = "4d3eae737ee23ffa53b58c9b1c401ff311bf5d59d05aed60182ddc9d116a7f01"
LINUX_MEASUREMENT_PLAN_DIGEST = "2aa89d8f0e2a8e81df01e8cb8ca7567a7571253f3dcc1e302ab5d67fc94ef5e6"
LINUX_MEASUREMENT_PLAN_SHA256 = "6a91a68c3e038e7d54f5ac5864d99f1e7fc3338355155e0ff41ac619152407b6"
LINUX_MEASUREMENT_ARTIFACT_ID = "12257307851"
LINUX_MEASUREMENT_ARTIFACT_SHA256 = "5d2d62bb3157befdc8b2c581a817613b6ee5b6eb4323e8753478e7cb9ddf3726"
LINUX_MEASUREMENT_RECOVERY_RUN_ID = "39406688602"
LINUX_MEASUREMENT_LINEAGE_DIGEST = "ffe7af1695d04f0b0e72ab5eeb3cd13e2f8e4777c89eb1e514f4cb917201fd4e"
LINUX_MEASUREMENT_PACKAGE_CONTROLLER_SHA = "23477676416ce5548c5f86c1938cacda0674cc05"
CAPACITY_RESOURCE_CEILINGS = {
    "preparation_workers": 952,
    "preparation_support": 168,
    "preparation_cancellation_uncertainty": 100,
    "measurement_workers": 240,
    "measurement_support": 25,
    "terminal_readback": 10,
    "measurement_cancellation_controllers": 30,
}
CAPACITY_RESOURCE_OWNERSHIP = {
    "preparation_workers": ["capacity enumeration workers"],
    "preparation_support": [
        "manifest preparation", "preparation admission gates", "sample freeze",
    ],
    "preparation_cancellation_uncertainty": [
        "preparation monitor setup", "provider polling", "terminal decision retrieval",
        "monitor evidence publication", "preparation cancellation request", "monitor shutdown",
    ],
    "measurement_workers": ["capacity measurement workers"],
    "measurement_support": ["measurement admission", "measurement batch gates", "in-run readback"],
    "terminal_readback": ["terminal provider readback"],
    "measurement_cancellation_controllers": ["measurement monitor and cancellation containment"],
}
CAPACITY_RECOVERY_RESOURCE_CEILINGS = {
    "recovery_freeze": 30,
    "measurement_workers": 240,
    "execution_support": 25,
    "terminal_readback": 10,
    "cancellation_controllers": 30,
}
CAPACITY_RECOVERY_RESOURCE_OWNERSHIP = {
    "recovery_freeze": ["retained artifact validation", "corpus recovery", "sample freeze"],
    "measurement_workers": ["frozen source capacity measurement workers"],
    "execution_support": ["execution admission", "measurement batch gates", "in-run readback"],
    "terminal_readback": ["terminal provider readback"],
    "cancellation_controllers": ["measurement monitor and cancellation containment"],
}


def validate_capacity_authorization(
    authorization_id: str, *, expected_authorization_id: str | None = None,
) -> str:
    """Validate a grant identity and, for consumers, its originating binding."""
    if (
        not isinstance(authorization_id, str)
        or re.fullmatch(r"AH-[A-Z0-9-]{1,61}", authorization_id) is None
        or (
            expected_authorization_id is not None
            and authorization_id != expected_authorization_id
        )
    ):
        raise ValueError("capacity diagnostic authorization is missing, stale, or conflicting")
    return authorization_id


def _capacity_authorization_contract(
    authorization_id: str, candidate_sha: str, experiment_id: str,
) -> dict:
    """Build an immutable run-specific capacity execution contract."""
    authorization_id = validate_capacity_authorization(authorization_id)
    if re.fullmatch(r"[0-9a-f]{40}", candidate_sha) is None:
        raise ValueError("capacity diagnostic candidate is malformed")
    if re.fullmatch(r"capval-[A-Za-z0-9_-]{1,57}", experiment_id) is None:
        raise ValueError("capacity diagnostic experiment ID is malformed")
    contract = {
        "schema_version": "1",
        "kind": "capacity_authorization_contract",
        "authorization_id": authorization_id,
        "candidate_sha": candidate_sha,
        "experiment_id": experiment_id,
        "scope": {
            "preparation_dispatches": 1,
            "measurement_units": 12,
            "measurement_attempts_per_unit": 1,
            "terminal_readback_dispatches": 1,
            "maximum_measurement_concurrency": 4,
        },
        "resource_ceiling_minutes": CAPACITY_RESOURCE_CEILINGS,
        "resource_ownership": CAPACITY_RESOURCE_OWNERSHIP,
        "resource_ceiling_total_minutes": 1525,
        "transferable": False,
    }
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    contract["digest"] = hashlib.sha256(encoded).hexdigest()
    return contract


def capacity_authorization_contract(
    authorization_id: str, candidate_sha: str, experiment_id: str,
) -> dict:
    """Admit the one owner-approved grant and build its execution contract."""
    if authorization_id != CAPACITY_AUTHORIZATION_ID:
        raise ValueError("capacity diagnostic authorization is not approved for dispatch")
    return _capacity_authorization_contract(
        authorization_id, candidate_sha, experiment_id,
    )


def capacity_recovery_authorization_contract(
    authorization_id: str, candidate_sha: str, experiment_id: str,
) -> dict:
    """Build the one approved corpus-recovery diagnostic contract."""
    if authorization_id != CAPACITY_RECOVERY_AUTHORIZATION_ID:
        raise ValueError("capacity recovery authorization is not approved for dispatch")
    if candidate_sha != CAPACITY_RECOVERY_CANDIDATE:
        raise ValueError("capacity recovery candidate is not approved for dispatch")
    if experiment_id != CAPACITY_RECOVERY_EXPERIMENT_ID:
        raise ValueError("capacity recovery experiment is not approved for dispatch")
    contract = _capacity_authorization_contract(
        authorization_id, candidate_sha, experiment_id,
    )
    contract["scope"] = {
        "recovery_dispatches": 4,
        "additional_recovery_dispatches": 2,
        "successful_recovery_freezes": 1,
        "fixed_failed_recovery_run_ids": ["39369184372", "39378451442"],
        "conditional_pre_admission_retries": 1,
        "enumeration_dispatches": 0,
        "measurement_units": 12,
        "measurement_attempts_per_unit": 1,
        "terminal_readback_dispatches": 1,
        "maximum_measurement_concurrency": 4,
    }
    contract["resource_ceiling_minutes"] = CAPACITY_RECOVERY_RESOURCE_CEILINGS
    contract["resource_ownership"] = CAPACITY_RECOVERY_RESOURCE_OWNERSHIP
    contract["resource_ceiling_total_minutes"] = 335
    payload = {key: value for key, value in contract.items() if key != "digest"}
    contract["digest"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return contract


def validate_capacity_recovery_authorization_contract(
    contract: dict, *, authorization_id: str, candidate_sha: str, experiment_id: str,
) -> dict:
    """Require exact reproduction of the recovery-only resource contract."""
    expected = capacity_recovery_authorization_contract(
        authorization_id, candidate_sha, experiment_id,
    )
    if contract != expected:
        raise ValueError("capacity recovery authorization contract is missing, stale, or conflicting")
    return contract


def linux_measurement_authorization_contract(
    authorization_id: str, candidate_sha: str, experiment_id: str, *,
    execution_controller_sha: str,
) -> dict:
    """Build the exact retained-package Linux measurement authorization."""
    if authorization_id != LINUX_MEASUREMENT_AUTHORIZATION_ID:
        raise ValueError("Linux measurement authorization is not approved for dispatch")
    if candidate_sha != CAPACITY_RECOVERY_CANDIDATE:
        raise ValueError("Linux measurement source candidate differs")
    if experiment_id != LINUX_MEASUREMENT_EXPERIMENT_ID:
        raise ValueError("Linux measurement experiment differs")
    if re.fullmatch(r"[0-9a-f]{40}", execution_controller_sha) is None:
        raise ValueError("Linux measurement execution controller differs")
    contract = {
        "schema_version": "1",
        "kind": "linux_measurement_authorization_contract",
        "authorization_id": authorization_id,
        "experiment_id": experiment_id,
        "source_candidate_sha": candidate_sha,
        "package_controller_sha": LINUX_MEASUREMENT_PACKAGE_CONTROLLER_SHA,
        "execution_controller_sha": execution_controller_sha,
        "retained_package": {
            "run_id": LINUX_MEASUREMENT_RECOVERY_RUN_ID,
            "artifact_id": LINUX_MEASUREMENT_ARTIFACT_ID,
            "artifact_sha256": LINUX_MEASUREMENT_ARTIFACT_SHA256,
            "lineage_digest": LINUX_MEASUREMENT_LINEAGE_DIGEST,
        },
        "binding": {
            "environment_digest": LINUX_MEASUREMENT_ENVIRONMENT_DIGEST,
            "plan_digest": LINUX_MEASUREMENT_PLAN_DIGEST,
            "plan_file_sha256": LINUX_MEASUREMENT_PLAN_SHA256,
        },
        "scope": {
            "recovery_dispatches": 0,
            "enumeration_dispatches": 0,
            "measurement_units": 12,
            "measurement_attempts_per_unit": 1,
            "measurement_batches": [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11]],
            "terminal_readback_dispatches": 1,
            "maximum_measurement_concurrency": 4,
        },
        "resource_ceiling_minutes": {
            "historical_recovery_charged": 8,
            "measurement_workers": 240,
            "execution_support": 25,
            "terminal_readback": 10,
            "cancellation_controllers": 30,
        },
        "transferable": False,
    }
    contract["digest"] = hashlib.sha256(
        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return contract


def capacity_measurement_authorization_contract(
    authorization_id: str, candidate_sha: str, experiment_id: str, *,
    execution_controller_sha: str,
) -> dict:
    """Route a measurement monitor to the authorization contract that owns it."""
    if authorization_id == LINUX_MEASUREMENT_AUTHORIZATION_ID:
        return linux_measurement_authorization_contract(
            authorization_id, candidate_sha, experiment_id,
            execution_controller_sha=execution_controller_sha,
        )
    if authorization_id == CAPACITY_RECOVERY_AUTHORIZATION_ID:
        return capacity_recovery_authorization_contract(
            authorization_id, candidate_sha, experiment_id,
        )
    if authorization_id == CAPACITY_AUTHORIZATION_ID:
        return capacity_authorization_contract(
            authorization_id, candidate_sha, experiment_id,
        )
    raise ValueError("capacity measurement authorization is not approved for dispatch")


def validate_linux_measurement_authorization_contract(
    contract: dict, *, authorization_id: str, candidate_sha: str,
    experiment_id: str, execution_controller_sha: str,
) -> dict:
    """Require exact reproduction of the Linux measurement authorization."""
    expected = linux_measurement_authorization_contract(
        authorization_id, candidate_sha, experiment_id,
        execution_controller_sha=execution_controller_sha,
    )
    if contract != expected:
        raise ValueError("Linux measurement authorization contract is missing, stale, or conflicting")
    return contract


def validate_linux_measurement_package_binding(
    plan: dict, lineage: dict, contract: dict, *, plan_file_sha256: str,
    authorization_id: str, candidate_sha: str, experiment_id: str,
    execution_controller_sha: str,
) -> dict:
    """Bind the retained historical package to the distinct Linux execution grant."""
    validate_linux_measurement_authorization_contract(
        contract, authorization_id=authorization_id, candidate_sha=candidate_sha,
        experiment_id=experiment_id, execution_controller_sha=execution_controller_sha,
    )
    units = plan.get("units") if isinstance(plan, dict) else None
    recovery = lineage.get("recovery") if isinstance(lineage, dict) else None
    if (
        not isinstance(units, list)
        or len(units) != 12
        or plan.get("revision") != candidate_sha
        or plan.get("digest") != LINUX_MEASUREMENT_PLAN_DIGEST
        or plan_file_sha256 != LINUX_MEASUREMENT_PLAN_SHA256
        or {unit.get("environment_digest") for unit in units if isinstance(unit, dict)}
        != {LINUX_MEASUREMENT_ENVIRONMENT_DIGEST}
        or lineage.get("digest") != LINUX_MEASUREMENT_LINEAGE_DIGEST
        or not isinstance(recovery, dict)
        or recovery.get("controller_sha") != LINUX_MEASUREMENT_PACKAGE_CONTROLLER_SHA
    ):
        raise ValueError("Linux measurement retained package binding differs")
    return contract


def validate_capacity_authorization_contract(
    contract: dict, *, authorization_id: str, candidate_sha: str, experiment_id: str,
) -> dict:
    """Require exact reproduction of the committed owner-approved contract."""
    expected = _capacity_authorization_contract(
        authorization_id, candidate_sha, experiment_id,
    )
    if contract != expected:
        raise ValueError("capacity authorization contract is missing, stale, or conflicting")
    return contract
SOURCE_RUN_ID = "37464324954"
SOURCE_ORCHESTRATION_SHA = "891562ba4909b16e6252a0eb7e8674393f43eba0"
SOURCE_WORKFLOW_REF = (
    "MilindGaharwar/fettle/.github/workflows/mutation.yml@"
    "refs/heads/audit/hardening-integration-20261005"
)
SOURCE_PLAN_SHA256 = "1e712595d7c6adccbd17aa284eaf4821afda82c9b61798022eeb6ea861190294"
SOURCE_REPORT_SHA256 = {
    8: "7ef152a1ef53135478f533bb854b1a3cd670e3eaded3189b8522caeb9c15adc1",
    27: "c75cd28c6c33ab5ece2e023cb50b9bf1eb6d8f037089823026d5315b0bf5f80d",
    28: "d5fb6a9fa5dd48f3b4f9d8c8923e1d07b3c439e07230895f6e15f629327a26ff",
    37: "342b6fe772134f1a5e46d3d06ada54a5e67ed493176b7d541d4c9fadc3a9ea90",
    48: "cd057e172def0beb8b5fad3504174ca6afbb6b370213e17d6cf1cdea5fbb8199",
    50: "67f0761dec5f96c1d8899501d7fd4a593e9186fe71b3471a9fa4db05c2e428dd",
    51: "b3221fe3776b4324e1df83ee2284e13a3cc66a5544ceaedc150d28fe62fd4f65",
    53: "932730a91b27186c2a15de0fd76ff461d2b2f41c8be2b1712739b27470511dcb",
}
RECOVERY_RUN_ID = "37476889333"
RECOVERY_ORCHESTRATION_SHA = "7da9f5d07884a5913bdbc38f28b34344c839a9f9"
RECOVERY_PLAN_SHA256 = "6882bd0f2cc46e73e86b44053257f9029e951c41c2d3d5767eb9fc29b0272b99"
RECOVERY_VALIDATION_SHA256 = "be9720e53a65cd794ceb4d446925359e78d92f18af1afd356ef1334de368d4ee"
CONTINUATION_RUN_ID = "37550308775"
CONTINUATION_ORCHESTRATION_SHA = "9a66e4fdc2edff60d65d6dd48d6d4e61dce2f807"
CONTINUATION_PLAN_SHA256 = "86c92b109a152e9dd456c93b4c453ae0d0381930103f8f94547f53bda341035d"
CONTINUATION_ARTIFACT_INVENTORY_SHA256 = "ffa3c03d9fc051fb2410c9efdb6b4ca2e7dc08488fb629d74f2ac811e102ac07"
SOURCE_ARTIFACT_INVENTORY_SHA256 = "17ea66dd5e34d56046e3fcd0e86cf73f919bfe417fa0e57e28fb3195f622948a"
RECOVERY_ARTIFACT_INVENTORY_SHA256 = "3d0158c0b72fcf622fcd1c7c5239d48229d098a06c1c6f39cbae0ba9fc8cbd6d"
DIAGNOSTIC_GENERATED = 45432
DIAGNOSTIC_CORPUS_DIGEST = "155a02b863d6b440211e09eef8daf189098554ca5871c5a484e7b65a3b005be2"
RECOVERY_REPORT_SHA256 = {
    0: "410373c3a18369b9c1708deaf1d26eb84bc4bc3c6822ad34a1772c6fb2b8c0a5",
    1: "b0892cce8c7503d7870919d1f05ee3f776173619931423d0c22877783a29f752",
    2: "823d836c4338acafa031efcf2f85df05570007dc1b86cd7f92b33c3c4d8188b3",
    3: "3234fb4b3104eaa1dad97d04aae682757b524153ef7e4f695b1d253c4541b097",
    4: "047c82d09636c47e799557b1141d683600995f18dcf289b112207b7b456e2799",
    5: "8dbb02de21a312d6ac01071500d396eb3c545a71eb97aa42ddec614639f2a552",
    6: "ac863e12708bba2c95d9b269e5f71890b0a4f63b800bbae1d5f0d2000e1a7c79",
    7: "a1aadee19be52acc2f500c000b9494ed0b887b9c65443023dd2444f345ffd5e5",
    9: "96f3de59d67ba3821bdf5d3ad2b65e1df7f5c0b80306ff9c602f90a5d626acd8",
    10: "8951441c09d40d13b8533fbaf8fbf5f2267da1e10e2203b341b38361eac0ca54",
    11: "3750b25dca78623abd9d06600d439b996c436d5ea2dd8093cb57424463cb9b4e",
    12: "750992ed42d68442352dfef74e460adad76c3c4aa9cb7d86d3d93dd79c8db845",
    13: "7cc5a02ebac49f3e8e18ce316cf64bed3828a7dc3946b4bc2230f83609685574",
    14: "4a6dc0f6a7c2ae815ce1c617318c7fbc506d11a95b276438efa1ffcda759a6e3",
    15: "bbdc243203aa6fb0d418a794a492e0db2115ef95a50dfa6b6f2ef79c85255f65",
    16: "880f6d00dff4eac05ea9c0cc8fac607658274b8b24b5e1df6d3361c28a021cf3",
    17: "09349cba8db51ce6dd41fbca36f662435f94edc82be4882c7cec41fe488e2fb4",
    18: "e271b9d1bb9a59386afd98fbd8a6c28681b2fb28e347da30402ec6d4322eedca",
    19: "0c760cd9c9f8bfd338792a2eed2d74cb9e981dfc1f5aa5a1c4ce2b0234f303af",
    20: "3f9817c3ea53e65963f4c64ff06b24783923285ab438862653a46f31b48760cf",
    21: "11b0d963d7ada57fbb2bb4bebe774238067abeb1c62493bf21a0e0c1978da243",
    22: "b0d8e12b6a21e000587fb63a533a61bc236a54b0ef0ed1afa1f5c622e68b3cd3",
    23: "09b800a456920ff407aa9dbb00beb75cf71d5896442bdbd2d3bf3e640e4aac41",
    24: "c1124f72f9f57f6a2e6c6afd5dc6c00538c70181074e13301767fe859eb7db05",
    25: "4e0be0a7923ac1339954f6bf2e437b08a1819a4258b2edb8dbba419a0b90e881",
    26: "b4f29f1a24239055130e1670e5f08004dcc0828a8f8320cd43cb3d843a17320c",
    29: "43ad72514df8cf6c5891bbb27230b6a249aae5026d0624e9283c87f565ce745f",
    30: "fbe56fc83a6b87068caec4af442aed3da8dca34facb4a89aad8a8af7948e1376",
    31: "52b78549e801f21d51e127922578e1d7394d1e97e35e9343af4e91ef7f278f10",
    32: "b2258b8603049be0218ffe3f29ffe6c1647d1104ecfd8185902dce4b3ea7963e",
    33: "4e8838e92a2d39ac307499da22f2521d496cb2492ff695b0ada09c7c44cea220",
    34: "2dff36180d5518b8006a6930160fdf94f2595138595753810e1b73d4e4328935",
}
SHARD_COUNT = 256
ARTIFACT_RETENTION_DAYS = 90
CALIBRATION_RUNNER_MINUTE_CEILING = 12_000
CALIBRATION_CANCELLATION_RESERVE = 1_200
CALIBRATION_LAUNCH_CUTOFF = 10_800
WAVES = {
    "wave-1": [8, 27, 28, 37, 48, 50, 51, 53],
    "wave-2": [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 16,
               17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 29, 30, 31, 32, 33, 34],
}
WAVES["wave-3"] = [
    index for index in range(SHARD_COUNT)
    if index not in set(WAVES["wave-1"] + WAVES["wave-2"])
]
MAX_PARALLEL = {"wave-1": 2, "wave-2": 4, "wave-3": 8}
BUDGET = {
    "operational_ceiling_runner_minutes": 1220,
    "wave_allowances": {"wave-1": 32, "wave-2": 120, "wave-3": 800},
    "orchestration_and_aggregation": 168,
    "cancellation_headroom": 100,
    "launch_ceiling": {"wave-2": 32, "wave-3": 152, "aggregate": 952, "complete": 1120},
}
MATRIX_JOB_LIMIT = 256
PROJECT_CONTINUATION_JOB_LIMIT = 256
CONTINUATION_SUPPORT_JOBS = 13
SOURCE_WORKFLOW_PATH = ".github/workflows/mutation.yml"
WAVE_3_BATCHES = [
    WAVES["wave-3"][offset:offset + 32]
    for offset in range(0, len(WAVES["wave-3"]), 32)
]

CALIBRATION_OBSERVER_ALLOWANCES = {
    "scheduling_minutes": 5,
    "polling_minutes": 1,
    "publication_minutes": 5,
    "cancellation_minutes": 5,
    "reconciliation_minutes": 5,
    "shutdown_minutes": 9,
}
CALIBRATION_SUPPORT_BOUNDS = {
    "mutation (calibration accounting)": 15,
    "mutation (assemble evidence)": 30,
    "mutation evidence": 10,
}
CAPACITY_PREPARATION_BUDGET = {
    "worker_ceiling_minutes": 952,
    "support_ceiling_minutes": 168,
    "cancellation_uncertainty_headroom_minutes": 100,
    "operational_ceiling_minutes": 1220,
    "worker_timeout_minutes": 35,
    "batch_size": 16,
    "tail_batch_size": 8,
    "full_batch_count": 14,
    "support_job_count": 21,
    "support_reserved_minutes": 120,
    "monitor_internal_deadline_minutes": 70,
    "monitor_job_timeout_minutes": 90,
}
_CAPACITY_ENUMERATION_JOB = re.compile(
    r"^(?:[^/]+ / )?capacity validation \(enumerate (\d+)\)$"
)
CALIBRATION_ACCOUNTING_LOG_MARKER = "FETTLE_CALIBRATION_ACCOUNTING_LOG_V1 "
CALIBRATION_ACCOUNTING_LOG_PAYLOAD_LIMIT = 256 * 1024
CALIBRATION_ACCOUNTING_LOG_CHUNK_SIZE = 12 * 1024
CALIBRATION_ACCOUNTING_LOG_CHUNK_LIMIT = 32

_CALIBRATION_JOB = re.compile(
    r"^(?:[^/]+ / )?mutation \(full shard (\d+), advisory\)$"
)
_CALIBRATION_ADMISSION_JOB = re.compile(
    r"^(?:[^/]+ / )?mutation \(validate calibration batch (\d+)\)$"
)
_CALIBRATION_INITIAL_ADMISSION_JOB = "mutation (require stage 3 observer readiness)"
_CALIBRATION_READINESS_PRODUCER_JOB = "mutation (publish stage 3 observer readiness)"


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _valid_accounting_lineage(lineage: object) -> bool:
    return (
        isinstance(lineage, list)
        and len(lineage) <= 16
        and all(
            isinstance(item, dict)
            and set(item) == {"run_id", "run_attempt"}
            and re.fullmatch(r"[1-9][0-9]*", str(item["run_id"]))
            and re.fullmatch(r"[1-9][0-9]*", str(item["run_attempt"]))
            for item in lineage
        )
    )


def build_calibration_accounting_log_envelope(
    payload: bytes,
    *,
    repository: str,
    candidate_sha: str,
    workflow_ref: str,
    workflow_sha: str,
    run_id: str,
    run_attempt: str,
    calibration_id: str,
    stage: str,
    primary_upload_outcome: str,
) -> str:
    """Wrap exact terminal-accounting bytes for bounded job-log retention."""
    if len(payload) > CALIBRATION_ACCOUNTING_LOG_PAYLOAD_LIMIT:
        raise ValueError("terminal accounting exceeds the 256 KiB log fallback limit")
    try:
        accounting = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("terminal accounting payload is malformed") from exc
    lineage = accounting.get("source_lineage", [])
    if (
        not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
        or not re.fullmatch(r"[0-9a-f]{40}", candidate_sha)
        or not workflow_ref.startswith(repository + "/.github/workflows/")
        or not re.fullmatch(r"[0-9a-f]{40}", workflow_sha)
        or not re.fullmatch(r"[1-9][0-9]*", run_id)
        or not re.fullmatch(r"[1-9][0-9]*", run_attempt)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", calibration_id)
        or stage not in {"1", "2", "3"}
        or primary_upload_outcome != "failure"
        or accounting.get("schema_version") != "1"
        or accounting.get("kind") != "calibration_budget_decision"
        or accounting.get("calibration_id") != calibration_id
        or accounting.get("stage") != stage
        or accounting.get("expected_run_id") != run_id
        or accounting.get("expected_run_attempt") != run_attempt
        or not _valid_accounting_lineage(lineage)
    ):
        raise ValueError("terminal accounting log identity is incomplete or incompatible")
    envelope = {
        "schema_version": "1",
        "kind": "calibration_accounting_log_envelope",
        "repository": repository,
        "candidate_sha": candidate_sha,
        "workflow_ref": workflow_ref,
        "workflow_sha": workflow_sha,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "calibration_id": calibration_id,
        "stage": stage,
        "accounting_schema_version": accounting["schema_version"],
        "accounting_kind": accounting["kind"],
        "source_lineage": lineage,
        "primary_upload_outcome": primary_upload_outcome,
        "payload_size": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_base64": base64.b64encode(payload).decode("ascii"),
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"))


def recover_calibration_accounting_log_envelope(
    log_bytes: bytes,
    *,
    repository: str,
    candidate_sha: str,
    workflow_ref: str,
    workflow_sha: str,
    run_id: str,
    run_attempt: str,
    calibration_id: str,
    stage: str,
) -> bytes:
    """Recover one exact, applicable accounting payload from a completed job log."""
    if len(log_bytes) > 4 * 1024 * 1024:
        raise ValueError("calibration accounting job log is oversized")
    try:
        lines = log_bytes.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise ValueError("calibration accounting job log is malformed") from exc
    records = [
        line.split(CALIBRATION_ACCOUNTING_LOG_MARKER, 1)[1]
        for line in lines if CALIBRATION_ACCOUNTING_LOG_MARKER in line
    ]
    if not records:
        raise ValueError("calibration accounting log fallback is unavailable")
    if len(records) > CALIBRATION_ACCOUNTING_LOG_CHUNK_LIMIT * 3:
        raise ValueError("calibration accounting log contains excessive records")
    try:
        chunks = [json.loads(item, object_pairs_hook=_reject_duplicate_json_keys) for item in records]
        totals = {item.get("total") for item in chunks}
        digests = {item.get("envelope_sha256") for item in chunks}
        if len(totals) != 1 or len(digests) != 1:
            raise ValueError("chunk metadata conflicts")
        total = totals.pop()
        digest = digests.pop()
        if (
            not isinstance(total, int) or isinstance(total, bool)
            or total < 1 or total > CALIBRATION_ACCOUNTING_LOG_CHUNK_LIMIT
            or not re.fullmatch(r"[0-9a-f]{64}", str(digest))
        ):
            raise ValueError("chunk metadata is malformed")
        by_index: dict[int, str] = {}
        for item in chunks:
            if set(item) != {"schema_version", "kind", "index", "total", "envelope_sha256", "chunk"}:
                raise ValueError("chunk shape is malformed")
            index = item["index"]
            chunk = item["chunk"]
            if (
                item["schema_version"] != "1"
                or item["kind"] != "calibration_accounting_log_chunk"
                or not isinstance(index, int) or isinstance(index, bool)
                or index < 0 or index >= total
                or not isinstance(chunk, str) or len(chunk) > CALIBRATION_ACCOUNTING_LOG_CHUNK_SIZE
            ):
                raise ValueError("chunk is malformed")
            if index in by_index and by_index[index] != chunk:
                raise ValueError("duplicate chunk conflicts")
            by_index[index] = chunk
        if set(by_index) != set(range(total)):
            raise ValueError("chunk sequence is incomplete")
        encoded = "".join(by_index[index] for index in range(total))
        if hashlib.sha256(encoded.encode("ascii")).hexdigest() != digest:
            raise ValueError("envelope digest differs")
        envelope = json.loads(encoded, object_pairs_hook=_reject_duplicate_json_keys)
        payload = base64.b64decode(envelope["payload_base64"], validate=True)
    except (KeyError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("calibration accounting log envelope is malformed") from exc
    expected = {
        "schema_version": "1", "kind": "calibration_accounting_log_envelope",
        "repository": repository, "candidate_sha": candidate_sha,
        "workflow_ref": workflow_ref, "workflow_sha": workflow_sha,
        "run_id": run_id, "run_attempt": run_attempt,
        "calibration_id": calibration_id, "stage": stage,
        "accounting_schema_version": "1", "accounting_kind": "calibration_budget_decision",
        "primary_upload_outcome": "failure",
    }
    if any(envelope.get(key) != value for key, value in expected.items()):
        raise ValueError("calibration accounting log provenance differs")
    if (
        len(payload) > CALIBRATION_ACCOUNTING_LOG_PAYLOAD_LIMIT
        or envelope.get("payload_size") != len(payload)
        or envelope.get("payload_sha256") != hashlib.sha256(payload).hexdigest()
    ):
        raise ValueError("calibration accounting log payload digest or size differs")
    try:
        accounting = json.loads(payload, object_pairs_hook=_reject_duplicate_json_keys)
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("recovered terminal accounting is malformed") from exc
    if (
        accounting.get("schema_version") != "1"
        or accounting.get("kind") != "calibration_budget_decision"
        or accounting.get("calibration_id") != calibration_id
        or accounting.get("stage") != stage
        or accounting.get("expected_run_id") != run_id
        or accounting.get("expected_run_attempt") != run_attempt
        or not _valid_accounting_lineage(accounting.get("source_lineage", []))
        or envelope.get("source_lineage") != accounting.get("source_lineage", [])
    ):
        raise ValueError("recovered terminal accounting applicability differs")
    return payload


def calibration_accounting_log_records(envelope: str) -> list[str]:
    """Split one envelope into bounded, ordered, digest-bound log records."""
    try:
        envelope.encode("ascii")
    except UnicodeError as exc:
        raise ValueError("calibration accounting log envelope is not ASCII") from exc
    chunks = [
        envelope[offset:offset + CALIBRATION_ACCOUNTING_LOG_CHUNK_SIZE]
        for offset in range(0, len(envelope), CALIBRATION_ACCOUNTING_LOG_CHUNK_SIZE)
    ]
    if not chunks or len(chunks) > CALIBRATION_ACCOUNTING_LOG_CHUNK_LIMIT:
        raise ValueError("calibration accounting log envelope exceeds the chunk limit")
    digest = hashlib.sha256(envelope.encode("ascii")).hexdigest()
    return [
        CALIBRATION_ACCOUNTING_LOG_MARKER + json.dumps({
            "schema_version": "1", "kind": "calibration_accounting_log_chunk",
            "index": index, "total": len(chunks), "envelope_sha256": digest,
            "chunk": chunk,
        }, sort_keys=True, separators=(",", ":"))
        for index, chunk in enumerate(chunks)
    ]


def calibration_observer_contract(
    shard_count: int,
    max_parallel: int,
    *,
    worker_timeout_minutes: int = 35,
    expected_shards: list[int] | None = None,
    worker_waves: int | None = None,
    admission_dependencies: int = 0,
) -> dict:
    """Derive a finite observer lifecycle without weakening worker or budget limits."""
    for name, value in (
        ("shard count", shard_count),
        ("maximum parallelism", max_parallel),
        ("worker timeout", worker_timeout_minutes),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"calibration observer {name} must be a positive integer")
    expected = list(range(shard_count)) if expected_shards is None else expected_shards
    if (
        len(expected) != shard_count
        or len(expected) != len(set(expected))
        or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in expected)
    ):
        raise ValueError("calibration observer expected shards are malformed")
    waves = math.ceil(shard_count / max_parallel) if worker_waves is None else worker_waves
    if (
        not isinstance(waves, int) or isinstance(waves, bool) or waves < 1
        or not isinstance(admission_dependencies, int) or isinstance(admission_dependencies, bool)
        or admission_dependencies < 0
    ):
        raise ValueError("calibration observer wave or admission topology is malformed")
    components = {
        "worker_waves_minutes": waves * worker_timeout_minutes,
        **CALIBRATION_OBSERVER_ALLOWANCES,
    }
    if admission_dependencies:
        components["admission_dependencies_minutes"] = admission_dependencies * 10
    observer_minutes = sum(
        value for name, value in components.items() if name != "shutdown_minutes"
    )
    return {
        "schema_version": "1",
        "kind": "calibration_observer_contract",
        "shard_count": shard_count,
        "expected_shards": expected,
        "max_parallel": max_parallel,
        "worker_timeout_minutes": worker_timeout_minutes,
        "worker_waves": waves,
        "admission_dependencies": admission_dependencies,
        "components": components,
        "observer_deadline_seconds": observer_minutes * 60,
        "job_timeout_minutes": observer_minutes + components["shutdown_minutes"],
        "completion_guaranteed": False,
    }


def calibration_stage_3_observer_contract(selected_shards: list[int]) -> dict:
    """Derive stage-3 containment from occupied fixed batches and required admissions."""
    if (
        not selected_shards
        or len(selected_shards) != len(set(selected_shards))
        or any(index not in WAVES["wave-3"] for index in selected_shards)
    ):
        raise ValueError("stage 3 observer selection is malformed")
    occupied = [
        number for number, batch in enumerate(WAVE_3_BATCHES, 1)
        if any(index in selected_shards for index in batch)
    ]
    return calibration_observer_contract(
        len(selected_shards), 32, expected_shards=selected_shards,
        worker_waves=len(occupied), admission_dependencies=len(WAVE_3_BATCHES) - 1,
    )


def calibration_stage_3_admitted_shards(
    selected_shards: list[int], jobs: list[dict],
) -> list[int]:
    """Return the exact stage-3 prefix admitted by successful sequential gates."""
    contract = calibration_stage_3_observer_contract(selected_shards)
    completed: set[int] = set()
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            continue
        match = _CALIBRATION_ADMISSION_JOB.fullmatch(job["name"])
        if match is None:
            continue
        batch = int(match.group(1))
        if batch not in range(1, 7) or batch in completed:
            raise ValueError("stage 3 admission identity is duplicate or malformed")
        if job.get("status") == "completed" and job.get("conclusion") == "success":
            completed.add(batch)
    prefix = 0
    while prefix + 1 in completed:
        prefix += 1
    if completed != set(range(1, prefix + 1)):
        raise ValueError("stage 3 admission success is non-contiguous")
    admitted_batches = min(prefix + 1, 7)
    admitted = {
        index for batch in WAVE_3_BATCHES[:admitted_batches] for index in batch
    }
    expected = contract["expected_shards"]
    return [index for index in expected if index in admitted]


def calibration_stage_3_completed_admissions(jobs: list[dict]) -> int:
    """Count the contiguous successful stage-3 admission handoffs."""
    completed: set[int] = set()
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            continue
        match = _CALIBRATION_ADMISSION_JOB.fullmatch(job["name"])
        if match is None:
            continue
        batch = int(match.group(1))
        if batch not in range(1, 7) or batch in completed:
            raise ValueError("stage 3 admission identity is duplicate or malformed")
        if job.get("status") == "completed" and job.get("conclusion") == "success":
            completed.add(batch)
    prefix = 0
    while prefix + 1 in completed:
        prefix += 1
    if completed != set(range(1, prefix + 1)):
        raise ValueError("stage 3 admission success is non-contiguous")
    return prefix


def calibration_stage_3_initial_admission_status(jobs: list[dict]) -> str:
    """Return the exact first-admission state used for prompt zero-worker containment."""
    producers = [
        job for job in jobs
        if isinstance(job, dict) and job.get("name") == _CALIBRATION_READINESS_PRODUCER_JOB
    ]
    if len(producers) > 1:
        raise ValueError("stage 3 readiness producer identity is duplicate")
    producer_state = "missing"
    producer_conclusion = None
    if producers:
        producer_status = producers[0].get("status")
        producer_conclusion = producers[0].get("conclusion")
        if producer_status in {"queued", "in_progress", "waiting", "pending"}:
            if producer_conclusion is not None:
                raise ValueError("stage 3 readiness producer state is malformed")
            producer_state = "pending"
        elif producer_status == "completed" and producer_conclusion in {
            "success", "failure", "cancelled", "timed_out", "action_required",
            "neutral", "skipped", "stale", "startup_failure",
        }:
            producer_state = "success" if producer_conclusion == "success" else "failure"
        else:
            raise ValueError("stage 3 readiness producer state is malformed")
    matches = [
        job for job in jobs
        if isinstance(job, dict) and job.get("name") == _CALIBRATION_INITIAL_ADMISSION_JOB
    ]
    if len(matches) > 1:
        raise ValueError("stage 3 initial admission identity is duplicate")
    if not matches:
        return "failure" if producer_state in {"success", "failure"} else "pending"
    if producer_state == "missing":
        raise ValueError("stage 3 readiness producer identity is missing")
    job = matches[0]
    status = job.get("status")
    conclusion = job.get("conclusion")
    if status in {"queued", "in_progress", "waiting", "pending"} and conclusion is None:
        return "failure" if producer_state == "failure" else "pending"
    if status != "completed" or conclusion not in {
        "success", "failure", "cancelled", "timed_out", "action_required",
        "neutral", "skipped", "stale", "startup_failure",
    }:
        raise ValueError("stage 3 initial admission state is malformed")
    if conclusion == "success":
        if producer_state != "success" or producer_conclusion != "success":
            raise ValueError("successful stage 3 admission conflicts with readiness producer")
        return "success"
    return "failure"


def build_calibration_observer_readiness(
    *, repository: str, run_id: str, run_attempt: str, candidate_sha: str,
    workflow_sha: str, calibration_id: str, artifact_name: str,
    monitor_job_id: int, produced_at: str, probe_only: bool = False,
) -> dict:
    """Build the exact typed readiness payload shared by production and probes."""
    if (
        not isinstance(monitor_job_id, int)
        or isinstance(monitor_job_id, bool)
        or monitor_job_id <= 0
    ):
        raise ValueError("observer readiness monitor job identity is malformed")
    if not isinstance(probe_only, bool):
        raise ValueError("observer readiness evidence profile is malformed")
    record = {
        "schema_version": "1", "kind": "calibration_observer_readiness",
        "repository": repository, "run_id": run_id, "run_attempt": run_attempt,
        "candidate_sha": candidate_sha, "workflow_sha": workflow_sha,
        "calibration_id": calibration_id, "stage": "3",
        "artifact_name": artifact_name, "monitor_job_id": monitor_job_id,
        "produced_at": produced_at, "ready": True,
    }
    if probe_only:
        record.update({
            "probe_only": True, "billing_authority": False, "passed": False,
            "authoritative_predecessor": False, "qualification_eligible": False,
        })
    return validate_calibration_observer_readiness(
        record, repository=repository, run_id=run_id, run_attempt=run_attempt,
        candidate_sha=candidate_sha, workflow_sha=workflow_sha,
        calibration_id=calibration_id, stage="3", artifact_name=artifact_name,
        monitor_job_id=monitor_job_id, observed_at=produced_at,
        probe_only=probe_only,
    )


def validate_calibration_observer_readiness(
    record: dict,
    *,
    repository: str,
    run_id: str,
    run_attempt: str,
    candidate_sha: str,
    workflow_sha: str,
    calibration_id: str,
    stage: str,
    artifact_name: str,
    monitor_job_id: int,
    observed_at: str,
    probe_only: bool = False,
) -> dict:
    """Validate exact current-attempt observer readiness and bounded freshness."""
    if not isinstance(probe_only, bool):
        raise ValueError("observer readiness evidence profile is malformed")
    if (
        not isinstance(monitor_job_id, int)
        or isinstance(monitor_job_id, bool)
        or monitor_job_id <= 0
        or not isinstance(record, dict)
        or not isinstance(record.get("monitor_job_id"), int)
        or isinstance(record.get("monitor_job_id"), bool)
        or record.get("monitor_job_id", 0) <= 0
    ):
        raise ValueError("observer readiness monitor job identity is malformed")
    expected = {
        "repository": repository, "run_id": run_id, "run_attempt": run_attempt,
        "candidate_sha": candidate_sha, "workflow_sha": workflow_sha,
        "calibration_id": calibration_id, "stage": stage,
        "artifact_name": artifact_name, "monitor_job_id": monitor_job_id,
    }
    expected_keys = {
        "schema_version", "kind", "repository", "run_id", "run_attempt",
        "candidate_sha", "workflow_sha", "calibration_id", "stage",
        "artifact_name", "monitor_job_id", "produced_at", "ready",
    }
    if probe_only:
        expected_keys.update({
            "probe_only", "billing_authority", "passed",
            "authoritative_predecessor", "qualification_eligible",
        })
    if set(record) != expected_keys or record.get("probe_only", False) is not probe_only:
        raise ValueError("observer readiness schema differs from the expected profile")
    if probe_only and any(
        record.get(field) is not False
        for field in (
            "billing_authority", "passed", "authoritative_predecessor",
            "qualification_eligible",
        )
    ):
        raise ValueError("observer readiness probe authority is malformed")
    if (
        record.get("schema_version") != "1"
        or record.get("kind") != "calibration_observer_readiness"
        or record.get("ready") is not True
        or any(record.get(key) != value for key, value in expected.items())
    ):
        raise ValueError("observer readiness identity differs from the current attempt")
    try:
        produced = datetime.fromisoformat(str(record["produced_at"]).replace("Z", "+00:00"))
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("observer readiness timestamp is malformed") from exc
    if produced.tzinfo is None or observed.tzinfo is None:
        raise ValueError("observer readiness timestamp is malformed")
    age = (observed - produced).total_seconds()
    if age < -60 or age > 600:
        raise ValueError("observer readiness timestamp is stale or outside clock tolerance")
    return record


def validate_readback_probe_admission(
    record: dict, *, repository: str, run_id: str, run_attempt: str,
    candidate_sha: str, workflow_sha: str, probe_id: str, scenario: str,
    artifact_name: str, monitor_job_id: int,
) -> dict:
    """Validate exact retained probe admission without granting authority."""
    expected_keys = {
        "schema_version", "kind", "repository", "run_id", "run_attempt",
        "candidate_sha", "workflow_sha", "calibration_id", "stage",
        "artifact_name", "observed_at", "provider_error_class",
        "artifact_download_attempt", "provider_attempts", "passed",
        "billing_authority", "probe_only", "authoritative_predecessor",
        "qualification_eligible", "provider_validation_passed", "monitor_job_id",
    }
    failed = scenario == "failed-initial-admission"
    if failed:
        expected_keys.update({"failure_code", "failure_class"})
    elif scenario != "success":
        raise ValueError("probe scenario is malformed")
    if not isinstance(record, dict) or set(record) != expected_keys:
        raise ValueError("probe admission schema differs from the expected scenario")
    if (
        not isinstance(monitor_job_id, int) or isinstance(monitor_job_id, bool)
        or monitor_job_id <= 0
        or not isinstance(record.get("monitor_job_id"), int)
        or isinstance(record.get("monitor_job_id"), bool)
        or record.get("monitor_job_id", 0) <= 0
    ):
        raise ValueError("probe admission monitor identity is malformed")
    expected = {
        "schema_version": "1", "kind": "calibration_readback_probe_admission",
        "repository": repository, "run_id": run_id, "run_attempt": run_attempt,
        "candidate_sha": candidate_sha, "workflow_sha": workflow_sha,
        "calibration_id": probe_id, "stage": "3", "artifact_name": artifact_name,
        "monitor_job_id": monitor_job_id, "passed": False,
        "billing_authority": False, "probe_only": True,
        "authoritative_predecessor": False, "qualification_eligible": False,
        "provider_validation_passed": True,
    }
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError("probe admission identity or authority is malformed")
    try:
        observed_at = datetime.fromisoformat(str(record["observed_at"]).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("probe admission observation time is malformed") from exc
    if observed_at.tzinfo is None:
        raise ValueError("probe admission observation time is malformed")
    attempts = record["provider_attempts"]
    download_attempt = record["artifact_download_attempt"]
    if (
        not isinstance(download_attempt, int) or isinstance(download_attempt, bool)
        or download_attempt not in {1, 2, 3}
        or not isinstance(attempts, list) or not attempts
        or any(
            not isinstance(attempt, dict)
            or set(attempt) not in (
                {"attempt", "attempted_at", "outcome"},
                {"attempt", "attempted_at", "outcome", "error_class"},
            )
            or attempt.get("attempt") != index
            or attempt.get("outcome") not in {"success", "failure"}
            for index, attempt in enumerate(attempts, 1)
        )
        or len(attempts) > 3 or attempts[-1].get("outcome") != "success"
    ):
        raise ValueError("probe admission provider attempts are malformed")
    for attempt in attempts:
        try:
            attempted_at = datetime.fromisoformat(
                str(attempt["attempted_at"]).replace("Z", "+00:00")
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("probe admission provider attempt time is malformed") from exc
        if attempted_at.tzinfo is None:
            raise ValueError("probe admission provider attempt time is malformed")
        if (
            attempt["outcome"] == "success" and "error_class" in attempt
            or attempt["outcome"] == "failure" and not isinstance(attempt.get("error_class"), str)
        ):
            raise ValueError("probe admission provider attempt outcome is malformed")
    if record["provider_error_class"] not in {
        "none", "access_denied", "transient_provider_error",
        "provider_resource_unavailable", "unclassified_provider_error",
        "artifact_download_retries_exhausted",
    }:
        raise ValueError("probe admission provider error class is malformed")
    if failed:
        if (
            record["failure_code"] != "forced_calibration_identity_mismatch"
            or record["failure_class"] != "ValueError"
        ):
            raise ValueError("probe admission failure is not the expected containment")
    return record


def evaluate_calibration_observer(
    contract: dict,
    jobs: list[dict],
    *,
    elapsed_seconds: int,
    budget_passed: bool,
    admitted_shards: list[int] | None = None,
    completed_admissions: int = 0,
    route_complete: bool = True,
    initial_admission_status: str = "not_applicable",
) -> dict:
    """Evaluate one controlled-clock observer sample without claiming completion."""
    if (
        contract.get("kind") != "calibration_observer_contract"
        or not isinstance(contract.get("shard_count"), int)
        or not isinstance(contract.get("observer_deadline_seconds"), int)
        or not isinstance(elapsed_seconds, int) or isinstance(elapsed_seconds, bool)
        or elapsed_seconds < 0
        or not isinstance(budget_passed, bool)
        or not isinstance(jobs, list)
        or not isinstance(completed_admissions, int) or isinstance(completed_admissions, bool)
        or completed_admissions < 0
        or completed_admissions > contract.get("admission_dependencies", 0)
        or not isinstance(route_complete, bool)
        or initial_admission_status not in {"not_applicable", "pending", "success", "failure"}
    ):
        raise ValueError("calibration observer sample is malformed")
    expected_shards = contract.get("expected_shards")
    if (
        not isinstance(expected_shards, list)
        or len(expected_shards) != contract["shard_count"]
        or len(expected_shards) != len(set(expected_shards))
    ):
        raise ValueError("calibration observer expected identities are malformed")
    admitted = expected_shards if admitted_shards is None else admitted_shards
    if (
        not isinstance(admitted, list) or len(admitted) != len(set(admitted))
        or any(index not in expected_shards for index in admitted)
    ):
        raise ValueError("calibration observer admitted identities are malformed")
    worker_jobs: dict[int, dict] = {}
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            continue
        name = job["name"]
        if (
            job.get("status") == "completed" and job.get("conclusion") == "skipped"
            and not job.get("runner_id") and not job.get("steps")
        ):
            continue
        match = _CALIBRATION_JOB.fullmatch(name)
        if match is None:
            if "mutation (full shard " in name:
                raise ValueError("calibration observer saw a malformed worker identity")
            continue
        index = int(match.group(1))
        if index not in expected_shards:
            raise ValueError("calibration observer saw an unexpected worker identity")
        if index not in admitted:
            raise ValueError("calibration observer saw a worker before admission")
        if index in worker_jobs:
            raise ValueError("calibration observer saw a duplicate worker identity")
        worker_jobs[index] = job
    terminal_shards = sorted(
        index for index, job in worker_jobs.items() if job.get("status") == "completed"
    )
    terminal = len(terminal_shards)
    expected = len(expected_shards)
    if initial_admission_status == "failure":
        action = "cancel"
        reason = "initial stage 3 admission failed"
    elif not budget_passed:
        action = "cancel"
        reason = "budget cutoff or accounting validation did not pass"
    elif (
        terminal_shards == sorted(expected_shards)
        and sorted(admitted) == sorted(expected_shards)
        and completed_admissions == contract.get("admission_dependencies", 0)
        and route_complete
    ):
        action = "complete"
        reason = "all admitted workers are terminal"
    elif elapsed_seconds >= contract["observer_deadline_seconds"]:
        action = "cancel"
        reason = "observer deadline expired before all admitted workers became terminal"
    else:
        action = "continue"
        reason = "admitted workers remain non-terminal within the observer deadline"
    return {
        "schema_version": "1",
        "kind": "calibration_observer_sample",
        "passed": action == "complete",
        "billing_authority": False,
        "completion_guaranteed": False,
        "elapsed_seconds": elapsed_seconds,
        "expected_workers": expected,
        "expected_shards": expected_shards,
        "admitted_shards": admitted,
        "observed_worker_jobs": len(worker_jobs),
        "terminal_workers": terminal,
        "terminal_shards": terminal_shards,
        "missing_terminal_shards": sorted(set(admitted) - set(terminal_shards)),
        "pending_admission_shards": sorted(set(expected_shards) - set(admitted)),
        "completed_admissions": completed_admissions,
        "expected_admissions": contract.get("admission_dependencies", 0),
        "route_complete": route_complete,
        "initial_admission_status": initial_admission_status,
        "action": action,
        "reason": reason,
        "contract": contract,
    }


def calibration_stage_3_batches(selected_shards: list[int]) -> list[list[int]]:
    """Return the reviewed fixed admission topology for calibration stage 3."""
    if selected_shards != WAVES["wave-3"]:
        raise ValueError("stage 3 admission requires the exact frozen shard membership")
    batches = [selected_shards[offset:offset + 32] for offset in range(0, len(selected_shards), 32)]
    if [len(batch) for batch in batches] != [32, 32, 32, 32, 32, 32, 24]:
        raise ValueError("stage 3 admission topology is malformed")
    return batches


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _load_api_pages(path: Path, collection: str) -> list[dict]:
    pages = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_json_keys,
    )
    if not isinstance(pages, list):
        pages = [pages]
    if not pages or any(
        not isinstance(page, dict) or not isinstance(page.get(collection), list)
        for page in pages
    ):
        raise ValueError(f"{collection} response is missing or malformed")
    values = [value for page in pages for value in page[collection]]
    if any(not isinstance(value, dict) for value in values):
        raise ValueError(f"{collection} response contains a malformed item")
    page_totals = [page.get("total_count") for page in pages]
    if any(
        not isinstance(total, int) or isinstance(total, bool) or total < 0
        for total in page_totals
    ):
        raise ValueError(f"{collection} response total_count is malformed")
    totals = set(page_totals)
    if totals != {len(values)}:
        raise ValueError(f"{collection} response pagination is incomplete")
    return values


def load_api_jobs_pages(path: Path) -> list[dict]:
    """Load a complete paginated Jobs API snapshot or fail closed."""
    jobs = _load_api_pages(path, "jobs")
    job_ids = [job.get("id") for job in jobs]
    if any(
        not isinstance(job_id, int) or isinstance(job_id, bool) or job_id <= 0
        for job_id in job_ids
    ):
        raise ValueError("jobs response contains a malformed job identity")
    if len(set(job_ids)) != len(job_ids):
        raise ValueError("jobs response contains duplicate job identities")
    return jobs


def load_api_workflow_run_pages(path: Path) -> list[dict]:
    """Load a complete workflow-runs snapshot with unique positive run IDs."""
    runs = _load_api_pages(path, "workflow_runs")
    run_ids = [run.get("id") for run in runs]
    if any(
        not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0
        for run_id in run_ids
    ):
        raise ValueError("workflow_runs response contains a malformed run identity")
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("workflow_runs response contains duplicate run identities")
    return runs


def validate_continuation_dispatches(
    runs_path: Path,
    source_run_id: str,
    current_run_id: str | None = None,
) -> dict:
    """Reject a second continuation for one immutable source run attempt."""
    if not re.fullmatch(r"[1-9][0-9]*", source_run_id):
        raise ValueError("source run ID must be a positive integer")
    expected_title = f"Staged preflight continuation for source {source_run_id}/1"
    runs = _load_api_pages(runs_path, "workflow_runs")
    matches = [run for run in runs if run.get("display_title") == expected_title]
    ids = [str(run.get("id", "")) for run in matches]
    if any(not re.fullmatch(r"[1-9][0-9]*", value) for value in ids):
        raise ValueError("matching continuation run identity is malformed")
    expected = [] if current_run_id is None else [current_run_id]
    if sorted(ids) != sorted(expected):
        raise ValueError("source run already has a continuation dispatch")
    return {
        "schema_version": "1", "status": "validated", "passed": True,
        "source_run_id": source_run_id, "continuation_run_ids": ids,
    }


def validate_source_handoff(
    run_path: Path,
    jobs_path: Path,
    artifacts_path: Path,
    *,
    repository: str,
    source_run_id: str,
    candidate_sha: str,
    source_orchestration_sha: str,
    source_workflow_ref: str,
) -> dict:
    """Admit only a complete wave-1/2 source or a handoff-only source failure."""
    run = _load_json(run_path)
    expected_ref = f"{repository}/{SOURCE_WORKFLOW_PATH}@refs/heads/{run.get('head_branch', '')}"
    if (
        str(run.get("id", "")) != source_run_id
        or run.get("run_attempt") != 1
        or run.get("status") != "completed"
        or run.get("conclusion") not in {"success", "failure"}
        or run.get("event") != "workflow_dispatch"
        or run.get("head_sha") != source_orchestration_sha
        or not re.fullmatch(r"[0-9a-f]{40}", candidate_sha)
        or source_workflow_ref != expected_ref
        or run.get("path") != SOURCE_WORKFLOW_PATH
        or not isinstance(run.get("head_repository"), dict)
        or run["head_repository"].get("full_name") != repository
    ):
        raise ValueError("source run identity or terminal provenance differs")

    jobs = _load_api_pages(jobs_path, "jobs")
    if any(
        str(job.get("run_id", "")) != source_run_id or job.get("run_attempt") != 1
        for job in jobs
    ):
        raise ValueError("source job origin differs from the source run attempt")
    by_name: dict[str, list[dict]] = {}
    for job in jobs:
        by_name.setdefault(str(job.get("name", "")), []).append(job)

    required = {
        "mutation (freeze staged preflight)",
        "mutation (validate staged preflight wave 1)",
        "mutation (validate staged preflight wave 2)",
        "mutation (monitor staged preflight budget)",
    }
    required.update(f"mutation (staged preflight wave 1 shard {index})" for index in WAVES["wave-1"])
    required.update(f"mutation (staged preflight wave 2 shard {index})" for index in WAVES["wave-2"])
    dispatch_name = "mutation (dispatch staged preflight continuation)"
    if any(len(by_name.get(name, [])) != 1 for name in required | {dispatch_name}):
        raise ValueError("source prerequisite job topology is incomplete or duplicated")
    if any(
        by_name[name][0].get("status") != "completed"
        or by_name[name][0].get("conclusion") != "success"
        or not isinstance(by_name[name][0].get("steps"), list)
        or any(
            step.get("conclusion") not in {"success", "skipped"}
            for step in by_name[name][0]["steps"]
        )
        for name in required
    ):
        raise ValueError("source prerequisite job failed or is incomplete")
    unexpected_execution = [
        job for name, entries in by_name.items() for job in entries
        if name not in required | {dispatch_name}
        and not (job.get("status") == "completed" and job.get("conclusion") == "skipped"
                and not job.get("steps")
                and not any(job.get(field) is not None for field in (
                    "runner_id", "runner_name", "runner_group_id", "runner_group_name",
                )))
    ]
    if unexpected_execution:
        raise ValueError("source run contains execution outside the reviewed handoff topology")

    dispatch = by_name[dispatch_name][0]
    if dispatch.get("status") != "completed" or dispatch.get("conclusion") not in {"success", "failure"}:
        raise ValueError("source dispatch job is not terminal")
    failed_steps = [
        step.get("name") for step in dispatch.get("steps", [])
        if step.get("conclusion") not in {"success", "skipped"}
    ]
    handoff_only_failure = (
        run["conclusion"] == "failure"
        and dispatch["conclusion"] == "failure"
        and failed_steps == ["Dispatch immutable continuation"]
    )
    if run["conclusion"] == "failure" and not handoff_only_failure:
        raise ValueError("source failure is not confined to the continuation handoff")
    if run["conclusion"] == "success" and dispatch["conclusion"] != "success":
        raise ValueError("successful source has an inconsistent dispatch job")

    artifacts = _load_api_pages(artifacts_path, "artifacts")
    names = [artifact.get("name") for artifact in artifacts]
    if len(names) != len(set(names)):
        raise ValueError("source artifacts contain duplicate names")
    required_artifacts = {
        f"mutation-staged-plan-{source_run_id}-1",
        f"mutation-preflight-wave-1-validation-{source_run_id}-1",
        f"mutation-preflight-wave-2-validation-{source_run_id}-1",
        f"mutation-preflight-monitor-{source_run_id}-1",
    }
    required_artifacts.update(
        f"mutation-preflight-{wave}-{source_run_id}-1-{index}"
        for wave in ("wave-1", "wave-2") for index in WAVES[wave]
    )
    if not required_artifacts.issubset(names):
        raise ValueError("source prerequisite artifacts are incomplete")
    for artifact in artifacts:
        if artifact.get("name") not in required_artifacts:
            continue
        origin = artifact.get("workflow_run", {})
        if (
            artifact.get("expired") is not False
            or str(origin.get("id", "")) != source_run_id
            or origin.get("head_sha") != source_orchestration_sha
        ):
            raise ValueError("source prerequisite artifact provenance differs")
    return {
        "schema_version": "1", "status": "validated", "passed": True,
        "source_run_id": source_run_id, "source_run_attempt": "1",
        "source_conclusion": run["conclusion"],
        "handoff_only_failure": handoff_only_failure,
        "prerequisite_job_count": len(required),
        "prerequisite_artifact_count": len(required_artifacts),
    }


def _load_manifests(
    root: Path,
    directory: Path,
    candidate_sha: str = FROZEN_CANDIDATE,
) -> list[dict]:
    sys.path.insert(0, str(root))
    from fettle.mutation_test import load_partition_manifest

    paths = sorted(directory.glob("partition-*.json"))
    manifests = [load_partition_manifest(path) for path in paths]
    manifests.sort(key=lambda item: item["shard_index"])
    if len(manifests) != SHARD_COUNT:
        raise ValueError(f"expected {SHARD_COUNT} manifests, found {len(manifests)}")
    if [item["shard_index"] for item in manifests] != list(range(SHARD_COUNT)):
        raise ValueError("manifest indexes are incomplete or duplicated")
    if any(
        item["revision"] != candidate_sha or item["shard_count"] != SHARD_COUNT
        for item in manifests
    ):
        raise ValueError("manifest candidate or topology differs from the frozen identity")
    return manifests


def build_plan(
    root: Path,
    manifests_dir: Path,
    orchestration_sha: str,
    identity: dict,
    candidate_sha: str = FROZEN_CANDIDATE,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", orchestration_sha):
        raise ValueError("orchestration SHA must be a full lowercase commit")
    if not re.fullmatch(r"[0-9a-f]{40}", candidate_sha):
        raise ValueError("candidate SHA must be a full lowercase commit")
    manifests = _load_manifests(root, manifests_dir, candidate_sha)
    members = [index for wave in WAVES.values() for index in wave]
    if len(members) != SHARD_COUNT or sorted(members) != list(range(SHARD_COUNT)):
        raise ValueError("fixed waves do not cover each shard exactly once")
    allocated = (
        sum(BUDGET["wave_allowances"].values())
        + BUDGET["orchestration_and_aggregation"]
        + BUDGET["cancellation_headroom"]
    )
    if allocated != BUDGET["operational_ceiling_runner_minutes"]:
        raise ValueError("predeclared budget does not reconcile")
    return {
        "schema_version": "1",
        "candidate_sha": candidate_sha,
        "orchestration_sha": orchestration_sha,
        "runtime": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
        },
        "dependencies": {
            "requirements_mutation_sha256": _file_digest(root / "requirements-mutation.txt"),
        },
        "policy": {"fettle_toml_sha256": _file_digest(root / ".fettle.toml")},
        "workflow": identity,
        "artifact_retention_days": ARTIFACT_RETENTION_DAYS,
        "shard_count": SHARD_COUNT,
        "manifest_digests": [item["digest"] for item in manifests],
        "manifest_topology_digest": _digest(manifests),
        "waves": {
            name: {"shards": shards, "max_parallel": MAX_PARALLEL[name]}
            for name, shards in WAVES.items()
        },
        "budget": BUDGET,
        "budget_notice": "Operational ceiling, not a guaranteed provider billing cap.",
    }


def validate_wave(
    root: Path,
    plan_path: Path,
    manifests_dir: Path,
    reports_dir: Path,
    wave: str,
    orchestration_sha: str,
    identity: dict,
) -> dict:
    plan = _load_json(plan_path)
    candidate_sha = plan.get("candidate_sha")
    if (
        not isinstance(candidate_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", candidate_sha)
        or plan.get("orchestration_sha") != orchestration_sha
        or plan.get("workflow") != identity
    ):
        raise ValueError("wave identity differs from the frozen plan")
    manifests = _load_manifests(root, manifests_dir, candidate_sha)
    if plan.get("manifest_digests") != [item["digest"] for item in manifests]:
        raise ValueError("wave manifest digests differ from the frozen topology")
    expected = plan.get("waves", {}).get(wave, {}).get("shards")
    if expected != WAVES.get(wave):
        raise ValueError("wave membership differs from the fixed plan")
    report_paths = sorted(reports_dir.rglob("mutation-preflight.json"))
    reports = [_load_json(path) for path in report_paths]
    if len(reports) != len(expected):
        raise ValueError(f"{wave} requires exactly {len(expected)} reports")
    by_index: dict[int, dict] = {}
    for report in reports:
        index = report.get("shard_index")
        if index in by_index or index not in expected:
            raise ValueError(f"{wave} contains a duplicate or substituted shard")
        manifest = manifests[index]
        fingerprints = report.get("fingerprints")
        corpus = report.get("corpus")
        if (
            report.get("status") != "completed"
            or report.get("passed") is not True
            or report.get("engine_version") != "2.5.1"
            or report.get("shard_count") != SHARD_COUNT
            or report.get("manifest_digest") != manifest["digest"]
            or report.get("line_ranges") != manifest["ranges"]
            or report.get("files") != manifest["files"]
            or report.get("generated") != report.get("canonicalized")
            or report.get("collisions") != 0
            or not isinstance(fingerprints, list)
            or not isinstance(corpus, list)
            or len(fingerprints) != report.get("generated")
            or len(corpus) != len(fingerprints)
            or len(fingerprints) != len(set(fingerprints))
            or any(not isinstance(item, dict) for item in corpus)
            or any(not isinstance(item, str) for item in fingerprints)
            or sorted(item.get("fingerprint") for item in corpus) != sorted(fingerprints)
        ):
            raise ValueError(f"shard {index!r} has failed, malformed, or incompatible evidence")
        by_index[index] = report
    if sorted(by_index) != sorted(expected):
        raise ValueError(f"{wave} reports are incomplete")
    return {
        "schema_version": "1",
        "status": "completed",
        "passed": True,
        "wave": wave,
        "candidate_sha": candidate_sha,
        "orchestration_sha": plan["orchestration_sha"],
        "shards": expected,
        "generated": sum(item["generated"] for item in reports),
        "report_digests": {
            str(index): _digest(by_index[index]) for index in sorted(by_index)
        },
    }


def build_recovery_plan(
    root: Path,
    source_plan_path: Path,
    manifests_dir: Path,
    source_reports_dir: Path,
    orchestration_sha: str,
    identity: dict,
) -> dict:
    if _file_digest(source_plan_path) != SOURCE_PLAN_SHA256:
        raise ValueError("source plan digest differs from the authorized recovery input")
    source_plan = _load_json(source_plan_path)
    source_identity = {
        "repository": identity["repository"],
        "workflow": identity["workflow"],
        "workflow_ref": SOURCE_WORKFLOW_REF,
        "run_id": SOURCE_RUN_ID,
        "run_attempt": "1",
    }
    if (
        source_plan.get("candidate_sha") != FROZEN_CANDIDATE
        or source_plan.get("orchestration_sha") != SOURCE_ORCHESTRATION_SHA
        or source_plan.get("workflow") != source_identity
    ):
        raise ValueError("source plan identity differs from the authorized recovery input")
    current = build_plan(root, manifests_dir, orchestration_sha, identity)
    compatibility_keys = (
        "candidate_sha", "runtime", "dependencies", "policy", "shard_count",
        "manifest_digests", "manifest_topology_digest", "waves", "budget",
    )
    if any(current[key] != source_plan.get(key) for key in compatibility_keys):
        raise ValueError("source and recovery execution identities are incompatible")
    source_report_paths = sorted(source_reports_dir.rglob("mutation-preflight.json"))
    if len(source_report_paths) != len(WAVES["wave-1"]):
        raise ValueError("recovery requires exactly eight source reports")
    source_reports = [_load_json(path) for path in source_report_paths]
    report_paths = {report.get("shard_index"): path for report, path in zip(source_reports, source_report_paths)}
    if sorted(report_paths) != sorted(WAVES["wave-1"]):
        raise ValueError("source report shard assignments are incomplete or duplicated")
    for index, expected_digest in SOURCE_REPORT_SHA256.items():
        if _file_digest(report_paths[index]) != expected_digest:
            raise ValueError(f"source report {index} digest differs from the authorized input")
    source_validation = validate_wave(
        root,
        source_plan_path,
        manifests_dir,
        source_reports_dir,
        "wave-1",
        SOURCE_ORCHESTRATION_SHA,
        source_identity,
    )
    return {
        **current,
        "mode": "staged-preflight-recovery",
        "source": {
            "run_id": SOURCE_RUN_ID,
            "run_attempt": "1",
            "orchestration_sha": SOURCE_ORCHESTRATION_SHA,
            "plan_sha256": SOURCE_PLAN_SHA256,
            "report_sha256": {str(key): value for key, value in SOURCE_REPORT_SHA256.items()},
            "validation": source_validation,
            "verdict": "original run remains permanently non-pass",
        },
        "execution_waves": {name: current["waves"][name] for name in ("wave-2", "wave-3")},
        "origin_assignment": {
            str(index): {
                "run_id": SOURCE_RUN_ID if index in WAVES["wave-1"] else identity["run_id"],
                "run_attempt": "1",
                "wave": next(name for name, shards in WAVES.items() if index in shards),
            }
            for index in range(SHARD_COUNT)
        },
    }


def build_recovery_record(plan_path: Path, reports_dir: Path, aggregate_path: Path) -> dict:
    plan = _load_json(plan_path)
    mode = plan.get("mode")
    if mode not in {"staged-preflight-recovery", "staged-preflight-continuation"}:
        raise ValueError("linked record requires a recovery or continuation plan")
    source = plan.get("source") if mode == "staged-preflight-recovery" else plan.get("sources", [None])[0]
    origins = plan.get("origin_assignment")
    manifest_digests = plan.get("manifest_digests")
    if (
        not isinstance(source, dict)
        or not isinstance(origins, dict)
        or not isinstance(manifest_digests, list)
        or len(manifest_digests) != SHARD_COUNT
    ):
        raise ValueError("recovery plan provenance is incomplete")
    report_paths = sorted(reports_dir.rglob("mutation-preflight.json"))
    if len(report_paths) != SHARD_COUNT:
        raise ValueError(f"recovery record requires exactly {SHARD_COUNT} reports")
    records: dict[int, dict] = {}
    generated = 0
    for path in report_paths:
        report = _load_json(path)
        index = report.get("shard_index")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index not in range(SHARD_COUNT)
            or index in records
        ):
            raise ValueError("recovery reports contain a missing, duplicate, or invalid shard index")
        if (
            report.get("status") != "completed"
            or report.get("passed") is not True
            or report.get("shard_count") != SHARD_COUNT
            or report.get("manifest_digest") != manifest_digests[index]
        ):
            raise ValueError(f"recovery report {index} is failed or incompatible")
        file_digest = _file_digest(path)
        origin = origins.get(str(index))
        if not isinstance(origin, dict):
            raise ValueError(f"recovery report {index} has no declared origin")
        if index in WAVES["wave-1"]:
            if (
                origin.get("run_id") != SOURCE_RUN_ID
                or origin.get("run_attempt") != "1"
                or file_digest != SOURCE_REPORT_SHA256[index]
            ):
                raise ValueError(f"reused report {index} differs from its immutable origin")
        else:
            expected_run = (
                RECOVERY_RUN_ID
                if mode == "staged-preflight-continuation" and index in WAVES["wave-2"]
                else plan.get("workflow", {}).get("run_id")
            )
            if origin.get("run_id") != expected_run or origin.get("run_attempt") != "1":
                raise ValueError(f"new report {index} differs from its recovery origin")
            if (
                mode == "staged-preflight-continuation"
                and index in WAVES["wave-2"]
                and file_digest != RECOVERY_REPORT_SHA256[index]
            ):
                raise ValueError(f"reused report {index} differs from its immutable origin")
        generated_value = report.get("generated")
        if not isinstance(generated_value, int) or isinstance(generated_value, bool):
            raise ValueError(f"recovery report {index} has malformed generated count")
        generated += generated_value
        records[index] = {
            **origin,
            "artifact_sha256": file_digest,
            "manifest_digest": manifest_digests[index],
            "generated": generated_value,
        }
    aggregate = _load_json(aggregate_path)
    if (
        aggregate.get("status") != "completed"
        or aggregate.get("passed") is not True
        or aggregate.get("revision") != FROZEN_CANDIDATE
        or aggregate.get("shard_count") != SHARD_COUNT
        or aggregate.get("manifest_digests") != manifest_digests
        or aggregate.get("generated") != generated
        or aggregate.get("canonicalized") != generated
        or aggregate.get("collisions") != 0
    ):
        raise ValueError("authoritative aggregate does not reconcile with recovery reports")
    return {
        "schema_version": "1",
        "status": "completed",
        "passed": True,
        "kind": ("linked_staged_preflight_recovery" if mode == "staged-preflight-recovery"
                 else "linked_staged_preflight_continuation"),
        "candidate_sha": FROZEN_CANDIDATE,
        "source_run_verdict": "permanently non-pass",
        "source": source,
        "sources": plan.get("sources"),
        "historical_verdicts": plan.get("historical_verdicts"),
        "recovery_workflow": plan["workflow"],
        "manifest_topology_digest": plan["manifest_topology_digest"],
        "aggregate_sha256": _file_digest(aggregate_path),
        "generated": generated,
        "origins": {str(index): records[index] for index in range(SHARD_COUNT)},
    }


def validate_report_artifacts(
    artifacts_path: Path,
    run_id: str,
    wave: str,
    expected_shards: list[int],
    expected_inventory_sha256: str,
) -> dict:
    pages = json.loads(artifacts_path.read_text(encoding="utf-8"))
    if not isinstance(pages, list):
        pages = [pages]
    if not pages or any(not isinstance(page, dict) or not isinstance(page.get("artifacts"), list)
                        for page in pages):
        raise ValueError("continuation artifact inventory is missing or malformed")
    artifacts = [artifact for page in pages for artifact in page["artifacts"]]
    reports = sorted(
        ({key: artifact.get(key) for key in ("id", "name", "size_in_bytes", "digest", "expired")}
         for artifact in artifacts
         if str(artifact.get("name", "")).startswith(
             f"mutation-preflight-wave-{wave}-{run_id}-1-"
         )),
        key=lambda artifact: artifact["name"],
    )
    indexes = []
    for artifact in reports:
        match = re.fullmatch(
            rf"mutation-preflight-wave-{wave}-{run_id}-1-(\d+)",
            str(artifact["name"]),
        )
        if (
            match is None
            or not isinstance(artifact["id"], int)
            or isinstance(artifact["id"], bool)
            or not isinstance(artifact["size_in_bytes"], int)
            or artifact["size_in_bytes"] <= 0
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact["digest"]))
            or artifact["expired"] is not False
        ):
            raise ValueError("continuation artifact inventory contains malformed evidence")
        indexes.append(int(match.group(1)))
    if len(indexes) != len(set(indexes)) or sorted(indexes) != sorted(expected_shards):
        raise ValueError("report artifact inventory is incomplete or substituted")
    digest = hashlib.sha256(
        json.dumps(reports, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if digest != expected_inventory_sha256:
        raise ValueError("report artifact inventory differs from the authorized input")
    return {"run_id": run_id, "run_attempt": "1", "reports": len(reports),
            "inventory_sha256": digest, "artifacts": reports}


def validate_continuation_artifacts(artifacts_path: Path) -> dict:
    return validate_report_artifacts(
        artifacts_path, CONTINUATION_RUN_ID, "3", WAVES["wave-3"],
        CONTINUATION_ARTIFACT_INVENTORY_SHA256,
    )


def build_aggregation_recovery_record(
    plan_path: Path,
    reports_dir: Path,
    aggregate_path: Path,
    source_artifact_inventory_path: Path,
    recovery_artifact_inventory_path: Path,
    continuation_artifact_inventory_path: Path,
    identity: dict,
) -> dict:
    if _file_digest(plan_path) != CONTINUATION_PLAN_SHA256:
        raise ValueError("continuation plan digest differs from the authorized aggregation input")
    plan = _load_json(plan_path)
    if (
        plan.get("mode") != "staged-preflight-continuation"
        or plan.get("candidate_sha") != FROZEN_CANDIDATE
        or plan.get("orchestration_sha") != CONTINUATION_ORCHESTRATION_SHA
        or plan.get("workflow", {}).get("run_id") != CONTINUATION_RUN_ID
        or plan.get("workflow", {}).get("run_attempt") != "1"
    ):
        raise ValueError("continuation plan identity differs from the authorized aggregation input")
    inventories = {
        SOURCE_RUN_ID: validate_report_artifacts(
            source_artifact_inventory_path, SOURCE_RUN_ID, "1", WAVES["wave-1"],
            SOURCE_ARTIFACT_INVENTORY_SHA256,
        ),
        RECOVERY_RUN_ID: validate_report_artifacts(
            recovery_artifact_inventory_path, RECOVERY_RUN_ID, "2", WAVES["wave-2"],
            RECOVERY_ARTIFACT_INVENTORY_SHA256,
        ),
        CONTINUATION_RUN_ID: validate_continuation_artifacts(
            continuation_artifact_inventory_path,
        ),
    }
    record = build_recovery_record(plan_path, reports_dir, aggregate_path)
    aggregate = _load_json(aggregate_path)
    if (
        aggregate.get("generated") != DIAGNOSTIC_GENERATED
        or aggregate.get("canonicalized") != DIAGNOSTIC_GENERATED
        or aggregate.get("collisions") != 0
        or aggregate.get("corpus_digest") != DIAGNOSTIC_CORPUS_DIGEST
    ):
        raise ValueError("authoritative aggregate differs from the diagnostic reconstruction")
    record.update({
        "kind": "staged_preflight_aggregation_recovery",
        "historical_verdicts": {
            SOURCE_RUN_ID: "permanently non-pass",
            RECOVERY_RUN_ID: "permanently non-pass",
            CONTINUATION_RUN_ID: "permanently non-pass",
        },
        "aggregation_recovery_workflow": identity,
        "artifact_inventories": inventories,
        "diagnostic_comparison": {
            "generated": DIAGNOSTIC_GENERATED,
            "canonicalized": DIAGNOSTIC_GENERATED,
            "collisions": 0,
            "corpus_digest": DIAGNOSTIC_CORPUS_DIGEST,
            "matched": True,
        },
    })
    return record


def validate_continuation_topology() -> dict:
    matrix_jobs = sum(len(batch) for batch in WAVE_3_BATCHES)
    expanded_jobs = matrix_jobs + CONTINUATION_SUPPORT_JOBS
    if (
        [len(batch) for batch in WAVE_3_BATCHES] != [32, 32, 32, 32, 32, 32, 24]
        or [index for batch in WAVE_3_BATCHES for index in batch] != WAVES["wave-3"]
        or any(len(batch) > MATRIX_JOB_LIMIT for batch in WAVE_3_BATCHES)
        or expanded_jobs > PROJECT_CONTINUATION_JOB_LIMIT
    ):
        raise ValueError("continuation workflow exceeds the reviewed project topology")
    return {
        "matrix_jobs": matrix_jobs,
        "matrix_batches": WAVE_3_BATCHES,
        "matrix_batch_sizes": [len(batch) for batch in WAVE_3_BATCHES],
        "support_jobs": CONTINUATION_SUPPORT_JOBS,
        "expanded_jobs": expanded_jobs,
        "per_matrix_platform_limit": MATRIX_JOB_LIMIT,
        "project_expanded_job_limit": PROJECT_CONTINUATION_JOB_LIMIT,
    }


_CONTINUATION_SHARD_JOB = re.compile(r"^mutation \(continuation shard (\d+)\)$")


def validate_continuation_batch(
    root: Path,
    plan_path: Path,
    manifests_dir: Path,
    reports_dir: Path,
    jobs_path: Path,
    artifacts_path: Path,
    *,
    batch: int,
    orchestration_sha: str,
    identity: dict,
) -> dict:
    """Admit the next fixed matrix only after exact cumulative batch evidence passes."""
    if batch not in range(1, len(WAVE_3_BATCHES)):
        raise ValueError("only batches with a successor can emit an admission matrix")
    plan = _load_json(plan_path)
    topology = validate_continuation_topology()
    candidate_sha = plan.get("candidate_sha")
    if (
        not isinstance(candidate_sha, str)
        or candidate_sha != orchestration_sha
        or plan.get("orchestration_sha") != orchestration_sha
        or plan.get("workflow") != identity
        or plan.get("topology") != topology
    ):
        raise ValueError("batch identity or topology differs from the unified successor plan")

    completed_batches = WAVE_3_BATCHES[:batch]
    completed_shards = [index for members in completed_batches for index in members]
    preceding_shards = WAVE_3_BATCHES[batch - 1]
    next_shards = WAVE_3_BATCHES[batch]
    manifests = _load_manifests(root, manifests_dir, candidate_sha)
    if plan.get("manifest_digests") != [item["digest"] for item in manifests]:
        raise ValueError("batch manifest digests differ from the frozen topology")

    jobs = _load_api_pages(jobs_path, "jobs")
    shard_jobs: dict[int, dict] = {}
    for job in jobs:
        if (
            str(job.get("run_id", "")) != identity["run_id"]
            or str(job.get("run_attempt", "")) != identity["run_attempt"]
        ):
            raise ValueError("batch job origin differs from the continuation run")
        match = _CONTINUATION_SHARD_JOB.fullmatch(str(job.get("name", "")))
        if match is None:
            continue
        index = int(match.group(1))
        if index in shard_jobs:
            raise ValueError("batch jobs contain a duplicate shard")
        shard_jobs[index] = job
    if any(index not in shard_jobs for index in completed_shards):
        raise ValueError("cumulative batch job membership is incomplete")
    if any(index not in completed_shards for index in shard_jobs):
        raise ValueError("a later batch was instantiated before admission")
    for index in completed_shards:
        job = shard_jobs[index]
        if (
            job.get("status") != "completed"
            or job.get("conclusion") != "success"
            or not isinstance(job.get("steps"), list)
            or not job["steps"]
            or any(step.get("conclusion") not in {"success", "skipped"} for step in job["steps"])
        ):
            raise ValueError(f"admitted batch shard {index} is not terminal-successful")

    artifacts = _load_api_pages(artifacts_path, "artifacts")
    artifact_prefix = f"mutation-preflight-wave-3-{identity['run_id']}-{identity['run_attempt']}-"
    artifact_indexes: list[int] = []
    for artifact in artifacts:
        name = str(artifact.get("name", ""))
        if not name.startswith(artifact_prefix):
            continue
        suffix = name.removeprefix(artifact_prefix)
        if not suffix.isdigit():
            raise ValueError("batch artifact has a malformed shard identity")
        index = int(suffix)
        origin = artifact.get("workflow_run")
        if (
            not isinstance(artifact.get("id"), int)
            or isinstance(artifact.get("id"), bool)
            or not isinstance(artifact.get("size_in_bytes"), int)
            or artifact["size_in_bytes"] <= 0
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact.get("digest", "")))
            or artifact.get("expired") is not False
            or not isinstance(origin, dict)
            or str(origin.get("id", "")) != identity["run_id"]
            or origin.get("head_sha") != orchestration_sha
        ):
            raise ValueError("batch artifact evidence is malformed or incompatible")
        artifact_indexes.append(index)
    if (
        len(artifact_indexes) != len(set(artifact_indexes))
        or sorted(artifact_indexes) != sorted(completed_shards)
    ):
        raise ValueError("cumulative batch artifact membership is incomplete or substituted")

    report_paths = sorted(reports_dir.rglob("mutation-preflight.json"))
    reports = [_load_json(path) for path in report_paths]
    by_index: dict[int, dict] = {}
    for report in reports:
        index = report.get("shard_index")
        if not isinstance(index, int) or isinstance(index, bool) or index in by_index:
            raise ValueError("cumulative batch reports contain a malformed or duplicate shard")
        if index not in completed_shards:
            raise ValueError("cumulative batch reports contain an unadmitted shard")
        manifest = manifests[index]
        fingerprints = report.get("fingerprints")
        corpus = report.get("corpus")
        if (
            report.get("status") != "completed"
            or report.get("passed") is not True
            or report.get("engine_version") != "2.5.1"
            or report.get("shard_count") != SHARD_COUNT
            or report.get("manifest_digest") != manifest["digest"]
            or report.get("line_ranges") != manifest["ranges"]
            or report.get("files") != manifest["files"]
            or report.get("generated") != report.get("canonicalized")
            or report.get("collisions") != 0
            or not isinstance(fingerprints, list)
            or not isinstance(corpus, list)
            or len(fingerprints) != report.get("generated")
            or len(corpus) != len(fingerprints)
            or len(fingerprints) != len(set(fingerprints))
            or any(not isinstance(item, dict) for item in corpus)
            or any(not isinstance(item, str) for item in fingerprints)
            or sorted(item.get("fingerprint") for item in corpus) != sorted(fingerprints)
        ):
            raise ValueError(f"batch report {index!r} is failed, malformed, or incompatible")
        by_index[index] = report
    if sorted(by_index) != sorted(completed_shards):
        raise ValueError("cumulative batch reports are incomplete")
    return {
        "schema_version": "1", "status": "completed", "passed": True,
        "candidate_sha": candidate_sha, "orchestration_sha": orchestration_sha,
        "validated_batch": batch, "validated_shards": preceding_shards,
        "cumulative_shards": completed_shards, "next_matrix": {"shard": next_shards},
        "report_digests": {str(index): _digest(by_index[index]) for index in sorted(by_index)},
    }


def build_fresh_continuation_plan(
    root: Path,
    source_plan_path: Path,
    wave_1_reports_dir: Path,
    wave_2_reports_dir: Path,
    wave_1_validation_path: Path,
    wave_2_validation_path: Path,
    manifests_dir: Path,
    source_plan_sha256: str,
    source_run_id: str,
    source_orchestration_sha: str,
    source_workflow_ref: str,
    orchestration_sha: str,
    identity: dict,
    candidate_sha: str,
) -> dict:
    if candidate_sha != orchestration_sha:
        raise ValueError("fresh continuation requires one unified successor identity")
    if not re.fullmatch(r"[0-9a-f]{64}", source_plan_sha256):
        raise ValueError("source plan digest must be a full lowercase SHA-256")
    if _file_digest(source_plan_path) != source_plan_sha256:
        raise ValueError("source plan digest differs from the immutable dispatch input")
    if not re.fullmatch(r"[1-9][0-9]*", source_run_id):
        raise ValueError("source run ID must be a positive integer")
    source_plan = _load_json(source_plan_path)
    source_identity = {
        "repository": identity["repository"],
        "workflow": "Mutation evidence",
        "workflow_ref": source_workflow_ref,
        "run_id": source_run_id,
        "run_attempt": "1",
    }
    if (
        source_plan.get("candidate_sha") != candidate_sha
        or source_plan.get("orchestration_sha") != source_orchestration_sha
        or source_plan.get("workflow") != source_identity
    ):
        raise ValueError("source plan identity differs from immutable dispatch inputs")
    current = build_plan(
        root, manifests_dir, orchestration_sha, identity, candidate_sha=candidate_sha,
    )
    compatibility_keys = (
        "candidate_sha", "runtime", "dependencies", "policy", "shard_count",
        "manifest_digests", "manifest_topology_digest", "waves", "budget",
    )
    if any(current[key] != source_plan.get(key) for key in compatibility_keys):
        raise ValueError("source and continuation execution identities are incompatible")
    validations = {}
    for wave, reports_dir, validation_path in (
        ("wave-1", wave_1_reports_dir, wave_1_validation_path),
        ("wave-2", wave_2_reports_dir, wave_2_validation_path),
    ):
        validation = validate_wave(
            root, source_plan_path, manifests_dir, reports_dir, wave,
            source_orchestration_sha, source_identity,
        )
        if validation != _load_json(validation_path):
            raise ValueError(f"{wave} validation does not reproduce from imported reports")
        validations[wave] = validation
    return {
        **current,
        "mode": "fresh-staged-preflight-continuation",
        "topology": validate_continuation_topology(),
        "source": {
            "run_id": source_run_id,
            "run_attempt": "1",
            "orchestration_sha": source_orchestration_sha,
            "workflow_ref": source_workflow_ref,
            "plan_sha256": source_plan_sha256,
            "validations": validations,
        },
        "execution_wave": current["waves"]["wave-3"],
        "origin_assignment": {
            str(index): {
                "run_id": source_run_id if index not in WAVES["wave-3"] else identity["run_id"],
                "run_attempt": "1",
                "wave": next(name for name, shards in WAVES.items() if index in shards),
            }
            for index in range(SHARD_COUNT)
        },
    }


def build_fresh_completion_record(
    plan_path: Path,
    reports_dir: Path,
    aggregate_path: Path,
) -> dict:
    plan = _load_json(plan_path)
    candidate_sha = plan.get("candidate_sha")
    origins = plan.get("origin_assignment")
    manifest_digests = plan.get("manifest_digests")
    if (
        plan.get("mode") != "fresh-staged-preflight-continuation"
        or not isinstance(candidate_sha, str)
        or not re.fullmatch(r"[0-9a-f]{40}", candidate_sha)
        or not isinstance(origins, dict)
        or not isinstance(manifest_digests, list)
        or len(manifest_digests) != SHARD_COUNT
    ):
        raise ValueError("fresh continuation plan provenance is incomplete")
    report_paths = sorted(reports_dir.rglob("mutation-preflight.json"))
    if len(report_paths) != SHARD_COUNT:
        raise ValueError(f"completion record requires exactly {SHARD_COUNT} reports")
    records: dict[int, dict] = {}
    generated = 0
    for path in report_paths:
        report = _load_json(path)
        index = report.get("shard_index")
        if (
            not isinstance(index, int) or isinstance(index, bool)
            or index not in range(SHARD_COUNT) or index in records
            or report.get("status") != "completed" or report.get("passed") is not True
            or report.get("shard_count") != SHARD_COUNT
            or report.get("manifest_digest") != manifest_digests[index]
        ):
            raise ValueError("completion reports are failed, incomplete, or incompatible")
        origin = origins.get(str(index))
        if not isinstance(origin, dict) or origin.get("run_attempt") != "1":
            raise ValueError(f"completion report {index} has no valid immutable origin")
        generated_value = report.get("generated")
        if not isinstance(generated_value, int) or isinstance(generated_value, bool):
            raise ValueError(f"completion report {index} has malformed generated count")
        generated += generated_value
        records[index] = {
            **origin,
            "artifact_sha256": _file_digest(path),
            "manifest_digest": manifest_digests[index],
            "generated": generated_value,
        }
    aggregate = _load_json(aggregate_path)
    if (
        aggregate.get("status") != "completed" or aggregate.get("passed") is not True
        or aggregate.get("revision") != candidate_sha
        or aggregate.get("shard_count") != SHARD_COUNT
        or aggregate.get("manifest_digests") != manifest_digests
        or aggregate.get("generated") != generated
        or aggregate.get("canonicalized") != generated
        or aggregate.get("collisions") != 0
    ):
        raise ValueError("authoritative aggregate does not reconcile with completion reports")
    return {
        "schema_version": "1", "status": "completed", "passed": True,
        "kind": "fresh_staged_preflight", "candidate_sha": candidate_sha,
        "source": plan["source"], "continuation_workflow": plan["workflow"],
        "manifest_topology_digest": plan["manifest_topology_digest"],
        "aggregate_sha256": _file_digest(aggregate_path), "generated": generated,
        "origins": {str(index): records[index] for index in range(SHARD_COUNT)},
    }


def build_continuation_plan(
    root: Path,
    source_plan_path: Path,
    source_reports_dir: Path,
    recovery_plan_path: Path,
    recovery_reports_dir: Path,
    recovery_validation_path: Path,
    manifests_dir: Path,
    orchestration_sha: str,
    identity: dict,
) -> dict:
    if _file_digest(source_plan_path) != SOURCE_PLAN_SHA256:
        raise ValueError("source plan digest differs from the authorized continuation input")
    if _file_digest(recovery_plan_path) != RECOVERY_PLAN_SHA256:
        raise ValueError("recovery plan digest differs from the authorized continuation input")
    if _file_digest(recovery_validation_path) != RECOVERY_VALIDATION_SHA256:
        raise ValueError("recovery validation digest differs from the authorized continuation input")
    recovery_plan = _load_json(recovery_plan_path)
    recovery_identity = {
        "repository": identity["repository"], "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": RECOVERY_RUN_ID, "run_attempt": "1",
    }
    if (
        recovery_plan.get("candidate_sha") != FROZEN_CANDIDATE
        or recovery_plan.get("orchestration_sha") != RECOVERY_ORCHESTRATION_SHA
        or recovery_plan.get("workflow") != recovery_identity
        or recovery_plan.get("source", {}).get("run_id") != SOURCE_RUN_ID
        or recovery_plan.get("source", {}).get("run_attempt") != "1"
    ):
        raise ValueError("recovery plan identity differs from the authorized continuation input")
    current = build_plan(root, manifests_dir, orchestration_sha, identity)
    compatibility_keys = (
        "candidate_sha", "runtime", "dependencies", "policy", "shard_count",
        "manifest_digests", "manifest_topology_digest", "waves", "budget",
    )
    if any(current[key] != recovery_plan.get(key) for key in compatibility_keys):
        raise ValueError("recovery and continuation execution identities are incompatible")
    source_identity = {
        "repository": identity["repository"], "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": SOURCE_RUN_ID, "run_attempt": "1",
    }
    source_validation = validate_wave(
        root, source_plan_path, manifests_dir, source_reports_dir, "wave-1",
        SOURCE_ORCHESTRATION_SHA, source_identity,
    )
    source_paths = {
        _load_json(path).get("shard_index"): path
        for path in source_reports_dir.rglob("mutation-preflight.json")
    }
    if sorted(source_paths) != sorted(WAVES["wave-1"]):
        raise ValueError("source reports are incomplete or duplicated")
    for index, expected_digest in SOURCE_REPORT_SHA256.items():
        if _file_digest(source_paths[index]) != expected_digest:
            raise ValueError(f"source report {index} digest differs from the authorized input")
    recovery_validation = validate_wave(
        root, recovery_plan_path, manifests_dir, recovery_reports_dir, "wave-2",
        RECOVERY_ORCHESTRATION_SHA, recovery_identity,
    )
    if recovery_validation != _load_json(recovery_validation_path):
        raise ValueError("recovery validation does not reproduce from imported reports")
    recovery_paths = {
        _load_json(path).get("shard_index"): path
        for path in recovery_reports_dir.rglob("mutation-preflight.json")
    }
    if sorted(recovery_paths) != sorted(WAVES["wave-2"]):
        raise ValueError("recovery reports are incomplete or duplicated")
    for index, expected_digest in RECOVERY_REPORT_SHA256.items():
        if _file_digest(recovery_paths[index]) != expected_digest:
            raise ValueError(f"recovery report {index} digest differs from the authorized input")
    return {
        **current,
        "mode": "staged-preflight-continuation",
        "topology": validate_continuation_topology(),
        "historical_verdicts": {
            SOURCE_RUN_ID: "permanently non-pass",
            RECOVERY_RUN_ID: "permanently non-pass",
        },
        "sources": [
            {"run_id": SOURCE_RUN_ID, "run_attempt": "1", "orchestration_sha": SOURCE_ORCHESTRATION_SHA,
             "plan_sha256": SOURCE_PLAN_SHA256, "validation": source_validation},
            {"run_id": RECOVERY_RUN_ID, "run_attempt": "1", "orchestration_sha": RECOVERY_ORCHESTRATION_SHA,
             "plan_sha256": RECOVERY_PLAN_SHA256, "validation": recovery_validation},
        ],
        "execution_wave": current["waves"]["wave-3"],
        "origin_assignment": {
            str(index): {
                "run_id": (SOURCE_RUN_ID if index in WAVES["wave-1"] else
                           RECOVERY_RUN_ID if index in WAVES["wave-2"] else identity["run_id"]),
                "run_attempt": "1",
                "wave": next(name for name, shards in WAVES.items() if index in shards),
            }
            for index in range(SHARD_COUNT)
        },
    }


def _parse_time(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"job {field} is missing or malformed")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"job {field} is not timezone-aware")
    return parsed


_RUNNER_IDENTITY_FIELDS = (
    "runner_id", "runner_name", "runner_group_id", "runner_group_name",
)


def _classify_runner_identity(job: dict) -> tuple[dict, str]:
    """Return normalized provider runner identity and its evidence classification."""
    if any(field not in job for field in _RUNNER_IDENTITY_FIELDS):
        raise ValueError(f"job {job.get('id')} runner identity is incomplete")
    identity = {field: job[field] for field in _RUNNER_IDENTITY_FIELDS}
    if (
        type(identity["runner_id"]) is int and identity["runner_id"] == 0
        and type(identity["runner_name"]) is str and identity["runner_name"] == ""
        and type(identity["runner_group_id"]) is int and identity["runner_group_id"] == 0
        and type(identity["runner_group_name"]) is str
        and identity["runner_group_name"] == ""
    ):
        return dict.fromkeys(_RUNNER_IDENTITY_FIELDS), "absent"
    if all(value is None for value in identity.values()):
        return identity, "absent"
    runner_id = identity["runner_id"]
    runner_name = identity["runner_name"]
    group_id = identity["runner_group_id"]
    group_name = identity["runner_group_name"]
    if (
        runner_id is not None and (type(runner_id) is not int or runner_id < 1)
        or runner_name is not None and (type(runner_name) is not str or not runner_name)
        or group_id is not None and (type(group_id) is not int or group_id < 0)
        or group_name is not None and (type(group_name) is not str or not group_name)
    ):
        raise ValueError(f"job {job.get('id')} runner identity is malformed")
    runner_pair = (runner_id is not None, runner_name is not None)
    group_pair = (group_id is not None, group_name is not None)
    classification = (
        "partial"
        if len(set(runner_pair)) != 1 or len(set(group_pair)) != 1 or not all(runner_pair)
        else "assigned"
    )
    return identity, classification


def _validated_job_page_ids(raw: bytes) -> tuple[list[dict], list[int]]:
    """Validate one paginated provider response without weakening accounting."""
    pages = json.loads(raw)
    if not isinstance(pages, list):
        pages = [pages]
    if not pages or any(
        not isinstance(page, dict) or not isinstance(page.get("jobs"), list)
        for page in pages
    ):
        raise ValueError("jobs response is missing or malformed")
    totals = {page.get("total_count") for page in pages}
    if len(totals) != 1 or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in totals
    ):
        raise ValueError("jobs response has missing or inconsistent total_count")
    jobs = [job for page in pages for job in page["jobs"]]
    ids = [job.get("id") for job in jobs if isinstance(job, dict)]
    if len(ids) != len(jobs) or any(
        not isinstance(job_id, int) or isinstance(job_id, bool) or job_id < 1
        for job_id in ids
    ):
        raise ValueError("jobs response has a missing or malformed job ID")
    if len(ids) != len(set(ids)):
        raise ValueError("jobs response contains duplicate job IDs")
    if totals != {len(jobs)}:
        raise ValueError("jobs response pagination is incomplete")
    return pages, sorted(ids)


def collect_stable_job_pages(
    output: Path,
    attempts_directory: Path,
    *,
    fetch: Callable[[float], str | bytes],
    max_attempts: int,
    max_elapsed_seconds: float,
    retry_delay_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Collect two valid consecutive observations with the same job-ID set."""
    if (
        type(max_attempts) is not int or max_attempts < 2
        or not isinstance(max_elapsed_seconds, (int, float))
        or isinstance(max_elapsed_seconds, bool) or max_elapsed_seconds <= 0
        or not isinstance(retry_delay_seconds, (int, float))
        or isinstance(retry_delay_seconds, bool) or retry_delay_seconds < 0
    ):
        raise ValueError("stable job collection bounds are malformed")
    attempts_directory.mkdir(parents=True, exist_ok=True)
    started = monotonic()
    previous_ids: list[int] | None = None
    errors = []
    for attempt in range(1, max_attempts + 1):
        elapsed = monotonic() - started
        remaining = max_elapsed_seconds - elapsed
        if remaining <= 0:
            break
        path = attempts_directory / f"attempt-{attempt}.json"
        try:
            value = fetch(remaining)
            raw = value.encode() if isinstance(value, str) else value
            if not isinstance(raw, bytes):
                raise ValueError("provider response is not bytes")
            path.write_bytes(raw)
            _pages, ids = _validated_job_page_ids(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, subprocess.SubprocessError) as exc:
            previous_ids = None
            errors.append({"attempt": attempt, "error": str(exc)})
        else:
            if ids == previous_ids:
                output.parent.mkdir(parents=True, exist_ok=True)
                temporary = output.with_name(output.name + ".tmp")
                temporary.write_bytes(raw)
                accepted_elapsed = monotonic() - started
                if accepted_elapsed > max_elapsed_seconds:
                    temporary.unlink(missing_ok=True)
                    errors.append({"attempt": attempt, "error": "elapsed limit exceeded"})
                    break
                temporary.replace(output)
                return {
                    "schema_version": "1",
                    "kind": "stable_provider_job_collection",
                    "attempts": attempt,
                    "stable_job_ids": ids,
                    "atomic_snapshot": False,
                    "elapsed_seconds": round(accepted_elapsed, 3),
                    "errors": errors,
                }
            previous_ids = ids
        if attempt < max_attempts:
            elapsed = monotonic() - started
            if elapsed >= max_elapsed_seconds:
                break
            sleep(min(retry_delay_seconds, max_elapsed_seconds - elapsed))
    raise ValueError(
        f"stable provider job collection unavailable after bounded retries: {errors}"
    )


def account_runner_minutes(
    jobs_path: Path,
    now: datetime | None = None,
    *,
    expected_run_id: str | None = None,
    expected_run_attempt: str | None = None,
    job_timeout_minutes: int | None = None,
) -> dict:
    raw = jobs_path.read_bytes()
    pages, ids = _validated_job_page_ids(raw)
    jobs = [job for page in pages for job in page["jobs"]]
    if not jobs:
        raise ValueError("jobs response is empty")
    total = 0.0
    current = now or datetime.now(UTC)
    observation_is_explicit = now is not None
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("observation time must be timezone-aware")
    if job_timeout_minutes is not None and (
        not isinstance(job_timeout_minutes, int) or isinstance(job_timeout_minutes, bool)
        or job_timeout_minutes < 1
    ):
        raise ValueError("job timeout must be a positive integer")
    included = []
    excluded = []
    anomalies = []
    for job in jobs:
        run_id = str(job.get("run_id", ""))
        run_attempt = str(job.get("run_attempt", ""))
        if (
            expected_run_id is not None and run_id != expected_run_id
            or expected_run_attempt is not None and run_attempt != expected_run_attempt
        ):
            raise ValueError(f"job {job['id']} origin differs from the expected run attempt")
        started = job.get("started_at")
        completed = job.get("completed_at")
        status = job.get("status")
        conclusion = job.get("conclusion")
        runner_identity, runner_classification = _classify_runner_identity(job)
        runner_id = runner_identity["runner_id"]
        partial_runner_identity = runner_classification == "partial"
        if partial_runner_identity and status == "completed":
            raise ValueError(f"job {job['id']} runner identity is partial")
        has_runner_identity = runner_classification != "absent"
        steps = job.get("steps")
        if not isinstance(steps, list):
            raise ValueError(f"job {job['id']} steps are missing or malformed")
        if status == "completed" and conclusion == "skipped":
            if has_runner_identity or steps:
                raise ValueError(f"skipped job {job['id']} has execution evidence")
            excluded.append({
                "id": job["id"], "name": job.get("name"), "status": status,
                "conclusion": conclusion, "reason": "completed skipped job did not acquire a runner",
                "excluded_fields": ["started_at", "completed_at"],
                "started_at": started, "completed_at": completed,
            })
            try:
                if _parse_time(completed, "completed_at") < _parse_time(started, "started_at"):
                    anomalies.append({
                        "id": job["id"], "reason": "skipped job timestamps are reversed",
                        "started_at": started, "completed_at": completed,
                    })
            except (TypeError, ValueError):
                anomalies.append({
                    "id": job["id"], "reason": "skipped job timestamps are missing or malformed",
                    "started_at": started, "completed_at": completed,
                })
            continue
        if (
            status == "completed" and conclusion == "cancelled"
            and not has_runner_identity and not steps
        ):
            bounded_worker = (
                job_timeout_minutes is not None
                and _CALIBRATION_JOB.fullmatch(str(job.get("name", ""))) is not None
            )
            anomalies.append({
                "id": job["id"],
                "reason": "cancelled job has no affirmative execution disposition",
                "started_at": started,
                "completed_at": completed,
                "runner_identity": runner_identity,
                "steps": steps,
                "conservative_timeout_minutes": (
                    job_timeout_minutes if bounded_worker else None
                ),
            })
            if not bounded_worker:
                raise ValueError(
                    f"cancelled job {job['id']} execution is indeterminate; raw anomaly preserved"
                )
            total += job_timeout_minutes
            included.append({
                "id": job["id"], "name": job.get("name"), "status": status,
                "conclusion": conclusion, "runner_id": runner_id,
                "started_at": started, "completed_at": completed,
                "minutes": float(job_timeout_minutes),
                "basis": "conservative worker-timeout charge for ambiguous cancellation",
                "execution_evidence": "ambiguous",
            })
            continue
        if (
            status in {"queued", "requested", "pending", "waiting"}
            and conclusion is None and not has_runner_identity and not steps
            and started is None and completed is None
        ):
            excluded.append({
                "id": job["id"], "name": job.get("name"), "status": status,
                "conclusion": conclusion, "reason": "job had not acquired a runner at observation",
                "excluded_fields": ["started_at", "completed_at"],
                "started_at": started, "completed_at": completed,
            })
            continue
        start = _parse_time(started, "started_at")
        if status == "completed":
            if conclusion is None:
                raise ValueError(f"completed job {job['id']} has no conclusion")
            end = _parse_time(completed, "completed_at")
            basis = "completed observed interval"
        elif (
            status in {"in_progress", "queued", "requested", "pending", "waiting"}
            and conclusion is None and completed is None
            and (status == "in_progress" or has_runner_identity or steps)
        ):
            end = current
            if partial_runner_identity:
                anomalies.append({
                    "id": job["id"],
                    "reason": "active job runner identity is partial during acquisition",
                    "runner_identity": runner_identity,
                })
            basis = (
                "elapsed through observation time"
                if status == "in_progress"
                else "runner-acquisition transition elapsed through observation time"
            )
        elif (
            status in {"queued", "requested", "pending", "waiting"}
            and conclusion is None and completed is None
            and not has_runner_identity and not steps and started is not None
        ):
            if not observation_is_explicit or job_timeout_minutes is None:
                raise ValueError(
                    f"job {job['id']} acquisition exposure has no explicit observation bound"
                )
            reported_start = _parse_time(started, "started_at")
            dispatched = _parse_time(job.get("created_at"), "created_at")
            exposure_start = dispatched
            if current < reported_start or current < dispatched:
                raise ValueError(f"job {job['id']} acquisition timing is reversed")
            start = exposure_start
            end = current
            anomalies.append({
                "id": job["id"],
                "reason": "queued job reported started_at without execution evidence",
                "resource_usage_basis": "bounded exposure only; not evidence of execution",
                "observed_at": current.isoformat(),
                "exposure_started_at": exposure_start.isoformat(),
                "timeout_minutes": job_timeout_minutes,
                "timeout_bound_applied": False,
                "timeout_note": (
                    "reported start is revision-prone, so execution timeout cannot safely "
                    "truncate dispatch-to-observation exposure"
                ),
            })
            basis = "queued acquisition exposure bounded from dispatch through observation"
        else:
            raise ValueError(f"job {job['id']} usage is indeterminate")
        if end < start:
            raise ValueError(f"executed job {job['id']} timing is reversed")
        minutes = (end - start).total_seconds() / 60
        total += minutes
        if status == "in_progress" or has_runner_identity or steps:
            execution_evidence = "confirmed"
        elif status == "completed":
            execution_evidence = "ambiguous"
        else:
            execution_evidence = "absent"
        included.append({
            "id": job["id"], "name": job.get("name"), "status": status,
            "conclusion": conclusion, "runner_id": runner_id, "started_at": started,
            "completed_at": completed, "minutes": round(minutes, 2), "basis": basis,
            "execution_evidence": execution_evidence,
        })
    return {
        "schema_version": "1",
        "kind": "operational_runner_time_estimate",
        "billing_authority": False,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "expected_run_id": expected_run_id,
        "expected_run_attempt": expected_run_attempt,
        "observed_at": current.isoformat(),
        "page_count": len(pages),
        "job_count": len(jobs),
        "estimated_runner_minutes": round(total, 2),
        "included_jobs": included,
        "excluded_jobs": excluded,
        "anomalies": anomalies,
    }


def observed_runner_minutes(jobs_path: Path, now: datetime | None = None) -> float:
    return account_runner_minutes(jobs_path, now)["estimated_runner_minutes"]


def combine_accounting(
    prior_jobs_path: Path,
    current_jobs_path: Path,
    now: datetime | None = None,
    *,
    expected_prior_run_id: str,
    expected_prior_run_attempt: str,
    expected_current_run_id: str,
    expected_current_run_attempt: str,
    job_timeout_minutes: int | None = None,
) -> dict:
    prior = account_runner_minutes(
        prior_jobs_path,
        now,
        expected_run_id=expected_prior_run_id,
        expected_run_attempt=expected_prior_run_attempt,
        job_timeout_minutes=job_timeout_minutes,
    )
    current = account_runner_minutes(
        current_jobs_path,
        now,
        expected_run_id=expected_current_run_id,
        expected_run_attempt=expected_current_run_attempt,
        job_timeout_minutes=job_timeout_minutes,
    )
    return {
        "schema_version": "1",
        "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False,
        "estimated_runner_minutes": round(
            prior["estimated_runner_minutes"] + current["estimated_runner_minutes"], 2,
        ),
        "sources": [prior, current],
    }


def combine_accounting_sources(
    sources: list[tuple[Path, str, str]],
    now: datetime | None = None,
    *,
    job_timeout_minutes: int | None = None,
) -> dict:
    if not sources:
        raise ValueError("at least one accounting source is required")
    reports = [
        account_runner_minutes(
            path, now, expected_run_id=run_id, expected_run_attempt=attempt,
            job_timeout_minutes=job_timeout_minutes,
        )
        for path, run_id, attempt in sources
    ]
    return {
        "schema_version": "1",
        "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False,
        "estimated_runner_minutes": round(sum(item["estimated_runner_minutes"] for item in reports), 2),
        "sources": reports,
    }


def validate_calibration_accounting(report: dict) -> tuple[list[tuple[str, str]], float]:
    """Validate one typed accounting record and return its origins and effective floor."""
    if not isinstance(report, dict):
        raise ValueError("accounting report is malformed")
    observed = report.get("estimated_runner_minutes")
    if (
        report.get("schema_version") != "1"
        or report.get("billing_authority") is not False
        or not isinstance(observed, (int, float)) or isinstance(observed, bool)
        or not math.isfinite(observed) or observed < 0
    ):
        raise ValueError("accounting report is malformed")
    kind = report.get("kind")
    if kind == "operational_runner_time_estimate":
        run_id = report.get("expected_run_id")
        attempt = report.get("expected_run_attempt")
        charged = report.get("charged_runner_minutes", observed)
        if (
            not isinstance(run_id, str) or not re.fullmatch(r"[1-9][0-9]*", run_id)
            or attempt != "1"
        ):
            raise ValueError("historical accounting source identity is malformed")
        if (
            not isinstance(charged, (int, float)) or isinstance(charged, bool)
            or not math.isfinite(charged) or charged < observed
        ):
            raise ValueError("historical accounting effective charge is malformed")
        return [(run_id, attempt)], float(charged)

    sources = report.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("historical accounting kind or sources are malformed")
    validated = [validate_calibration_accounting(source) for source in sources]
    identities = [identity for source_ids, _value in validated for identity in source_ids]
    if len(identities) != len(set(identities)):
        raise ValueError("accounting source lineage contains a duplicate origin")
    source_total = round(sum(value for _identities, value in validated), 2)

    if kind == "combined_operational_runner_time_estimate":
        reconciled = report.get("terminal_reconciled_runner_minutes", observed)
        if (
            not isinstance(reconciled, (int, float)) or isinstance(reconciled, bool)
            or not math.isfinite(reconciled) or reconciled < 0
            or not math.isclose(reconciled, source_total, rel_tol=0, abs_tol=0.01)
        ):
            raise ValueError("combined accounting total does not reconcile")
        if "terminal_reconciled_runner_minutes" in report:
            floor = report.get("historical_observed_runner_minutes_floor")
            applied = report.get("historical_floor_applied")
            if (
                not isinstance(floor, (int, float)) or isinstance(floor, bool)
                or not math.isfinite(floor) or floor < 0
                or not isinstance(applied, bool)
                or not math.isclose(observed, max(reconciled, floor), rel_tol=0, abs_tol=0.01)
                or applied is not (floor > reconciled)
            ):
                raise ValueError("historical accounting floor is malformed")
        return identities, float(observed)

    if kind != "calibration_budget_decision":
        raise ValueError("historical accounting kind or sources are malformed")
    charged = report.get("charged_runner_minutes")
    monitor_floor = report.get("monitor_floor_runner_minutes")
    reserve = report.get("bounded_support_reserve_minutes")
    reservations = report.get("bounded_support_reservations")
    lag = report.get("cancellation_lag_charge")
    active_jobs = report.get("active_jobs")
    cancellation_reserve = report.get("cancellation_reserve")
    launch_cutoff = report.get("launch_cutoff")
    lifecycle = report.get("observer_evidence", {}).get("lifecycle")
    lineage = report.get("source_lineage")
    expected_lineage = [
        {"run_id": run_id, "run_attempt": attempt} for run_id, attempt in identities
    ]
    numeric = (charged, monitor_floor, reserve, lag)
    included = report.get("included_jobs")
    terminal_source = sources[-1]
    while terminal_source.get("kind") == "calibration_budget_decision":
        nested = terminal_source.get("sources")
        if not isinstance(nested, list) or not nested:
            raise ValueError("calibration budget decision is malformed or contradictory")
        terminal_source = nested[-1]
    source_included = terminal_source.get("included_jobs")
    active_statuses = {"in_progress", "queued", "requested", "pending", "waiting"}
    canonical_active_jobs = (
        sum(job.get("status") in active_statuses for job in included)
        if isinstance(included, list) and all(isinstance(job, dict) for job in included)
        else None
    )
    support_bounds = CALIBRATION_SUPPORT_BOUNDS
    canonical_reservations = None
    if (
        isinstance(reserve, (int, float)) and not isinstance(reserve, bool)
        and isinstance(included, list) and support_bounds
        and len(support_bounds) == len(reservations)
    ):
        try:
            canonical_reservations = reserve_bounded_support_minutes({
                "estimated_runner_minutes": observed - reserve,
                "included_jobs": included,
            }, support_bounds)
        except ValueError:
            canonical_reservations = None
    if (
        report.get("passed") is not True
        or report.get("stage") not in {"1", "2", "3"}
        or not isinstance(report.get("calibration_id"), str)
        or report.get("ceiling") != CALIBRATION_RUNNER_MINUTE_CEILING
        or cancellation_reserve != CALIBRATION_CANCELLATION_RESERVE
        or launch_cutoff != CALIBRATION_LAUNCH_CUTOFF
        or not isinstance(active_jobs, int) or isinstance(active_jobs, bool) or active_jobs < 0
        or included != source_included
        or active_jobs != canonical_active_jobs
        or report.get("cancellation_lag_minutes_per_active_job") != 5
        or lag != active_jobs * 5
        or any(not isinstance(value, (int, float)) or isinstance(value, bool)
               or not math.isfinite(value) or value < 0 for value in numeric)
        or charged < observed
        or not isinstance(reservations, list) or not reservations
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("name"), str) or not item["name"]
            or not isinstance(item.get("bound_minutes"), int)
            or isinstance(item.get("bound_minutes"), bool) or item["bound_minutes"] < 1
            or not isinstance(item.get("already_observed_minutes"), (int, float))
            or isinstance(item.get("already_observed_minutes"), bool)
            or not math.isfinite(item["already_observed_minutes"])
            or item["already_observed_minutes"] < 0
            or item["already_observed_minutes"] > item["bound_minutes"]
            or not isinstance(item.get("reserved_minutes"), (int, float))
            or isinstance(item.get("reserved_minutes"), bool)
            or not math.isfinite(item["reserved_minutes"])
            or item["reserved_minutes"] < 0
            or not math.isclose(
                item["reserved_minutes"],
                item["bound_minutes"] - item["already_observed_minutes"],
                rel_tol=0, abs_tol=0.01,
            )
            for item in reservations
        )
        or not math.isclose(
            reserve,
            sum(item["reserved_minutes"] for item in reservations),
            rel_tol=0, abs_tol=0.01,
        )
        or canonical_reservations is None
        or reservations != canonical_reservations["bounded_support_reservations"]
        or reserve != canonical_reservations["bounded_support_reserve_minutes"]
        or not math.isclose(observed, max(source_total, monitor_floor) + reserve,
                            rel_tol=0, abs_tol=0.01)
        or not math.isclose(charged, observed + lag, rel_tol=0, abs_tol=0.01)
        or charged > launch_cutoff
        or lineage != expected_lineage
        or not _complete_calibration_lifecycle(lifecycle, report.get("stage"))
    ):
        raise ValueError("calibration budget decision is malformed or contradictory")
    return identities, float(charged)


def _complete_calibration_lifecycle(lifecycle: object, stage: object) -> bool:
    """Require a nonempty, stage-bound observer lifecycle and its embedded contract."""
    if not isinstance(lifecycle, dict) or stage not in {"1", "2", "3"}:
        return False
    expected = lifecycle.get("expected_shards")
    terminal = lifecycle.get("terminal_shards")
    admitted = lifecycle.get("admitted_shards")
    contract = lifecycle.get("contract")
    if (
        lifecycle.get("kind") != "calibration_observer_sample"
        or lifecycle.get("action") != "complete" or lifecycle.get("passed") is not True
        or not isinstance(expected, list) or not expected
        or len(expected) != len(set(expected))
        or any(
            not isinstance(index, int) or isinstance(index, bool)
            or index not in WAVES[f"wave-{stage}"] for index in expected
        )
        or not isinstance(terminal, list) or terminal != expected
        or not isinstance(admitted, list) or admitted != expected
        or any(
            not isinstance(index, int) or isinstance(index, bool)
            for indexes in (terminal, admitted) for index in indexes
        )
        or not isinstance(contract, dict)
    ):
        return False
    try:
        canonical = (
            calibration_stage_3_observer_contract(expected)
            if stage == "3"
            else calibration_observer_contract(
                len(expected), 8 if stage == "1" else 16,
                expected_shards=expected,
            )
        )
    except (TypeError, ValueError):
        return False
    return (
        contract == canonical
        and lifecycle.get("schema_version") == "1"
        and lifecycle.get("billing_authority") is False
        and lifecycle.get("completion_guaranteed") is False
        and isinstance(lifecycle.get("elapsed_seconds"), int)
        and not isinstance(lifecycle.get("elapsed_seconds"), bool)
        and 0 <= lifecycle["elapsed_seconds"] <= canonical["observer_deadline_seconds"]
        and lifecycle.get("expected_workers") == len(expected)
        and lifecycle.get("observed_worker_jobs") == len(expected)
        and lifecycle.get("terminal_workers") == len(expected)
        and lifecycle.get("missing_terminal_shards") == []
        and lifecycle.get("pending_admission_shards") == []
        and lifecycle.get("completed_admissions") == canonical["admission_dependencies"]
        and lifecycle.get("expected_admissions") == canonical["admission_dependencies"]
        and lifecycle.get("route_complete") is True
        and lifecycle.get("reason") == "all admitted workers are terminal"
    )


def calibration_accounting_lineage(records: list[dict]) -> list[dict[str, str]]:
    """Flatten validated accounting origins in their single-import order."""
    identities = [
        identity
        for record in records
        for identity in validate_calibration_accounting(record)[0]
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("accounting source lineage contains a duplicate origin")
    return [{"run_id": run_id, "run_attempt": attempt} for run_id, attempt in identities]


def retain_historical_accounting_floor(accounting: dict, historical_paths: list[Path]) -> dict:
    """Keep later reconciliation from reducing previously observed exposure."""
    expected_identities, terminal = validate_calibration_accounting(accounting)
    if not historical_paths:
        return accounting
    historical = []
    for path in historical_paths:
        report = _load_json(path)
        report_identities, observed = validate_calibration_accounting(report)
        if (
            len(report_identities) < len(expected_identities)
            or report_identities[-len(expected_identities):] != expected_identities
        ):
            raise ValueError("historical accounting has incompatible origin")
        historical.append({
            "path": str(path),
            "sha256": _file_digest(path),
            "estimated_runner_minutes": observed,
        })
    floor = max(item["estimated_runner_minutes"] for item in historical)
    return {
        **accounting,
        "terminal_reconciled_runner_minutes": terminal,
        "historical_observed_runner_minutes_floor": floor,
        "estimated_runner_minutes": round(max(terminal, floor), 2),
        "historical_floor_applied": floor > terminal,
        "historical_accounting": historical,
    }


def build_calibration_launch_accounting(
    current: dict,
    *,
    stage: str,
    calibration_id: str,
    ceiling: int,
    resume_run_id: str,
    prior_stage_run_id: str,
    predecessor: dict | None,
) -> dict:
    """Bind current launch usage to exactly one validated cumulative predecessor floor."""
    if (
        stage not in {"1", "2", "3"}
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", calibration_id)
        or ceiling != CALIBRATION_RUNNER_MINUTE_CEILING
        or not isinstance(resume_run_id, str)
        or not isinstance(prior_stage_run_id, str)
    ):
        raise ValueError("calibration launch identity is malformed")
    def numeric(value: str) -> bool:
        return bool(re.fullmatch(r"[1-9][0-9]*", value))
    if resume_run_id and not numeric(resume_run_id):
        raise ValueError("calibration resume run identity is malformed")
    if prior_stage_run_id and not numeric(prior_stage_run_id):
        raise ValueError("calibration prior-stage run identity is malformed")

    if stage == "1" and not resume_run_id:
        if prior_stage_run_id or predecessor is not None:
            raise ValueError("fresh stage 1 calibration has contradictory predecessor accounting")
        prior = 0.0
        predecessor_mode = "fresh-stage-1"
        predecessor_run_id = None
        predecessor_lineage: list[dict[str, str]] = []
    else:
        if stage == "1":
            if prior_stage_run_id:
                raise ValueError("stage 1 continuation cannot declare prior-stage accounting")
        elif not prior_stage_run_id:
            raise ValueError("later calibration stage is missing prior-stage identity")
        if predecessor is None:
            raise ValueError("required calibration predecessor accounting is missing")
        if predecessor.get("kind") != "calibration_budget_decision":
            raise ValueError("calibration predecessor accounting is incompatible")
        expected_stage = stage if resume_run_id else str(int(stage) - 1)
        predecessor_run_id = resume_run_id or prior_stage_run_id
        try:
            identities, prior = validate_calibration_accounting(predecessor)
        except ValueError as exc:
            raise ValueError("calibration predecessor accounting is incompatible") from exc
        valid = (
            predecessor.get("calibration_id") == calibration_id
            and predecessor.get("stage") == expected_stage
            and predecessor.get("ceiling") == ceiling
            and identities[-1] == (predecessor_run_id, "1")
        )
        if not valid:
            raise ValueError("calibration predecessor accounting is incompatible")
        if (
            resume_run_id and stage != "1"
            and (len(identities) < 2 or identities[-2] != (prior_stage_run_id, "1"))
        ):
            raise ValueError("calibration resume accounting conflicts with prior-stage lineage")
        predecessor_mode = "same-stage-resume" if resume_run_id else "prior-stage"
        predecessor_lineage = [
            {"run_id": run_id, "run_attempt": attempt} for run_id, attempt in identities
        ]

    observed = current.get("estimated_runner_minutes")
    if (
        current.get("schema_version") != "1"
        or current.get("kind") != "operational_runner_time_estimate"
        or current.get("billing_authority") is not False
        or not isinstance(observed, (int, float)) or isinstance(observed, bool)
        or not math.isfinite(observed) or observed < 0
        or not isinstance(current.get("included_jobs"), list)
    ):
        raise ValueError("current calibration launch accounting is malformed")
    return {
        **current,
        "stage": stage,
        "calibration_id": calibration_id,
        "ceiling": ceiling,
        "prior_runner_minutes": prior,
        "calibration_predecessor": {
            "mode": predecessor_mode,
            "resume_run_id": resume_run_id or None,
            "prior_stage_run_id": prior_stage_run_id or None,
            "accounting_run_id": predecessor_run_id,
            "source_lineage": predecessor_lineage,
        },
        "estimated_runner_minutes": round(observed + prior, 2),
    }


def combine_calibration_monitor_accounting(
    usage: dict,
    launch: dict,
    *,
    stage: str,
    calibration_id: str,
    ceiling: int,
) -> dict:
    """Apply a validated launch predecessor floor to one current monitor observation."""
    prior = launch.get("prior_runner_minutes")
    predecessor = launch.get("calibration_predecessor")
    predecessor_mode = predecessor.get("mode") if isinstance(predecessor, dict) else None
    resume_run_id = predecessor.get("resume_run_id") if isinstance(predecessor, dict) else None
    prior_stage_run_id = (
        predecessor.get("prior_stage_run_id") if isinstance(predecessor, dict) else None
    )
    accounting_run_id = (
        predecessor.get("accounting_run_id") if isinstance(predecessor, dict) else None
    )
    source_lineage = predecessor.get("source_lineage") if isinstance(predecessor, dict) else None
    lineage_identities = (
        [
            (item.get("run_id"), item.get("run_attempt"))
            for item in source_lineage
        ]
        if isinstance(source_lineage, list)
        and all(
            isinstance(item, dict) and set(item) == {"run_id", "run_attempt"}
            for item in source_lineage
        )
        else None
    )
    valid_lineage = (
        lineage_identities is not None
        and len(lineage_identities) == len(set(lineage_identities))
        and all(
            isinstance(run_id, str) and re.fullmatch(r"[1-9][0-9]*", run_id)
            and attempt == "1"
            for run_id, attempt in lineage_identities
        )
    )
    if (
        launch.get("stage") != stage
        or launch.get("calibration_id") != calibration_id
        or launch.get("ceiling") != ceiling
        or not isinstance(prior, (int, float)) or isinstance(prior, bool)
        or not math.isfinite(prior) or prior < 0
        or not isinstance(predecessor, dict)
        or not valid_lineage
        or predecessor_mode not in {
            "fresh-stage-1", "same-stage-resume", "prior-stage",
        }
        or (predecessor_mode == "fresh-stage-1" and (
            stage != "1" or prior != 0
            or resume_run_id is not None or prior_stage_run_id is not None
            or accounting_run_id is not None
            or lineage_identities != []
        ))
        or (predecessor_mode == "same-stage-resume" and (
            not isinstance(resume_run_id, str)
            or accounting_run_id != resume_run_id
            or not lineage_identities
            or lineage_identities[-1] != (resume_run_id, "1")
            or (stage == "1" and prior_stage_run_id is not None)
            or (stage != "1" and (
                not isinstance(prior_stage_run_id, str)
                or len(lineage_identities) < 2
                or lineage_identities[-2] != (prior_stage_run_id, "1")
            ))
        ))
        or (predecessor_mode == "prior-stage" and (
            stage == "1" or resume_run_id is not None
            or not isinstance(prior_stage_run_id, str)
            or accounting_run_id != prior_stage_run_id
            or not lineage_identities
            or lineage_identities[-1] != (prior_stage_run_id, "1")
        ))
    ):
        raise ValueError("calibration launch accounting contract is incompatible")
    observed = usage.get("estimated_runner_minutes")
    if (
        not isinstance(observed, (int, float)) or isinstance(observed, bool)
        or not math.isfinite(observed) or observed < 0
    ):
        raise ValueError("calibration monitor usage is malformed")
    return {
        **usage,
        "stage": stage,
        "calibration_id": calibration_id,
        "ceiling": ceiling,
        "prior_runner_minutes": float(prior),
        "calibration_predecessor": predecessor,
        "estimated_runner_minutes": round(observed + prior, 2),
    }


def evaluate_calibration_budget(
    accounting: dict,
    *,
    ceiling: int,
    cancellation_reserve: int,
) -> dict:
    """Apply a conservative launch cutoff without claiming a provider billing cap."""
    observed = accounting.get("estimated_runner_minutes")
    if (
        not isinstance(observed, (int, float)) or isinstance(observed, bool)
        or observed < 0
    ):
        raise ValueError("calibration usage is missing or malformed")
    if (
        not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling < 1
        or not isinstance(cancellation_reserve, int) or isinstance(cancellation_reserve, bool)
        or cancellation_reserve < 0 or cancellation_reserve >= ceiling
    ):
        raise ValueError("calibration ceiling or cancellation reserve is invalid")
    cutoff = ceiling - cancellation_reserve
    included = accounting.get("included_jobs")
    active_statuses = {"in_progress", "queued", "requested", "pending", "waiting"}
    if not isinstance(included, list):
        raise ValueError("calibration included job accounting is malformed")
    for job in included:
        if not isinstance(job, dict) or job.get("status") not in {"completed", *active_statuses}:
            raise ValueError("calibration included job accounting is malformed")
        if job.get("status") != "completed" and (
            not isinstance(job.get("minutes"), (int, float))
            or isinstance(job.get("minutes"), bool)
            or job["minutes"] < 0
            or not isinstance(job.get("basis"), str)
            or job.get("execution_evidence") not in {"confirmed", "absent"}
        ):
            raise ValueError("calibration included job active accounting is malformed")
        if job.get("status") != "in_progress" and job.get("status") != "completed" and (
            job.get("execution_evidence") != "absent"
            or job.get("basis") != "queued acquisition exposure bounded from dispatch through observation"
        ):
            raise ValueError("calibration included job acquisition accounting is malformed")
    active_jobs = sum(job.get("status") in active_statuses for job in included)
    cancellation_lag_minutes = active_jobs * 5
    charged = observed + cancellation_lag_minutes
    return {
        **accounting,
        "ceiling": ceiling,
        "cancellation_reserve": cancellation_reserve,
        "launch_cutoff": cutoff,
        "active_jobs": active_jobs,
        "cancellation_lag_minutes_per_active_job": 5,
        "cancellation_lag_charge": cancellation_lag_minutes,
        "charged_runner_minutes": round(charged, 2),
        "billing_authority": False,
        "budget_notice": (
            "Operational launch and cancellation control; provider cancellation latency "
            "can exceed the estimate and this is not a guaranteed billing cap."
        ),
        "passed": charged <= cutoff,
    }


def reserve_bounded_support_minutes(
    accounting: dict,
    support_bounds: dict[str, int],
) -> dict:
    """Conservatively reserve unobserved time for explicitly bounded support jobs."""
    observed = accounting.get("estimated_runner_minutes")
    included = accounting.get("included_jobs")
    if (
        not isinstance(observed, (int, float)) or isinstance(observed, bool) or observed < 0
        or not isinstance(included, list)
        or not isinstance(support_bounds, dict) or not support_bounds
        or any(
            not isinstance(name, str) or not name
            or not isinstance(bound, int) or isinstance(bound, bool) or bound < 1
            for name, bound in support_bounds.items()
        )
    ):
        raise ValueError("bounded support accounting is malformed")
    by_name: dict[str, dict] = {}
    for job in included:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            raise ValueError("bounded support included job is malformed")
        if job["name"] in support_bounds:
            if job["name"] in by_name:
                raise ValueError("bounded support job identity is duplicated")
            by_name[job["name"]] = job
    reservations = []
    for name, bound in support_bounds.items():
        job = by_name.get(name)
        already_observed = 0.0
        if job is not None:
            minutes = job.get("minutes")
            if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
                raise ValueError("bounded support observed minutes are malformed")
            already_observed = (
                float(bound) if job.get("status") == "completed"
                else min(float(minutes), float(bound))
            )
        reserve = round(max(0.0, bound - already_observed), 2)
        reservations.append({
            "name": name, "bound_minutes": bound,
            "already_observed_minutes": already_observed,
            "reserved_minutes": reserve,
        })
    total = round(sum(item["reserved_minutes"] for item in reservations), 2)
    return {
        **accounting,
        "estimated_runner_minutes": round(observed + total, 2),
        "bounded_support_reserve_minutes": total,
        "bounded_support_reservations": reservations,
    }


def evaluate_capacity_preparation_admission(
    accounting: dict,
    *,
    admitted_shards: list[int],
    next_shards: list[int],
    require_admitted_terminal: bool = True,
) -> dict:
    """Reserve complete capacity-preparation exposure before another fixed batch."""
    policy = CAPACITY_PREPARATION_BUDGET
    if sum((
        policy["worker_ceiling_minutes"],
        policy["support_ceiling_minutes"],
        policy["cancellation_uncertainty_headroom_minutes"],
    )) != policy["operational_ceiling_minutes"]:
        raise ValueError("capacity preparation budget categories do not reconcile")
    if (
        not isinstance(accounting, dict)
        or accounting.get("kind") not in {
            "operational_runner_time_estimate", "combined_operational_runner_time_estimate",
        }
        or accounting.get("billing_authority") is not False
    ):
        raise ValueError("capacity preparation accounting is malformed")
    included = accounting.get("included_jobs")
    if included is None and accounting.get("kind") == "combined_operational_runner_time_estimate":
        sources = accounting.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ValueError("capacity preparation accounting sources are malformed")
        included = [job for source in sources for job in source.get("included_jobs", [])]
    if not isinstance(included, list) or any(not isinstance(job, dict) for job in included):
        raise ValueError("capacity preparation included jobs are malformed")
    for values, label in ((admitted_shards, "admitted"), (next_shards, "next")):
        if (
            not isinstance(values, list) or values != sorted(set(values))
            or any(type(index) is not int or not 0 <= index < SHARD_COUNT for index in values)
        ):
            raise ValueError(f"capacity preparation {label} shards are malformed")
    if set(admitted_shards) & set(next_shards):
        raise ValueError("capacity preparation next shards overlap prior admission")
    if len(next_shards) > policy["batch_size"]:
        raise ValueError("capacity preparation batch exceeds the fixed size")

    workers = []
    seen = set()
    active_statuses = {"in_progress", "queued", "requested", "pending", "waiting"}
    for job in included:
        match = _CAPACITY_ENUMERATION_JOB.fullmatch(str(job.get("name", "")))
        if match is None:
            continue
        index = int(match.group(1))
        if index in seen or index not in admitted_shards:
            raise ValueError("capacity preparation worker identity is duplicated or unadmitted")
        seen.add(index)
        minutes = job.get("minutes")
        if (
            not isinstance(minutes, (int, float)) or isinstance(minutes, bool)
            or not math.isfinite(minutes) or minutes < 0
        ):
            raise ValueError("capacity preparation worker timing is malformed")
        status = job.get("status")
        if status not in {"completed", *active_statuses}:
            raise ValueError("capacity preparation worker status is indeterminate")
        if status == "completed" and job.get("conclusion") != "success":
            raise ValueError("capacity preparation worker did not succeed")
        if minutes > policy["worker_timeout_minutes"]:
            raise ValueError("capacity preparation worker exceeded its accounting bound")
        workers.append({**job, "shard_index": index})

    completed = sorted(job["shard_index"] for job in workers if job["status"] == "completed")
    active = sorted(job["shard_index"] for job in workers if job["status"] in active_statuses)
    if require_admitted_terminal and (completed != admitted_shards or active):
        raise ValueError("capacity preparation admitted workers are not complete and terminal")
    if not require_admitted_terminal and not set(completed + active) <= set(admitted_shards):
        raise ValueError("capacity preparation worker observation exceeds admission")

    observed_worker = round(sum(float(job["minutes"]) for job in workers), 2)
    not_yet_observed = sorted(set(admitted_shards) - set(completed) - set(active))
    active_remaining = round(sum(
        policy["worker_timeout_minutes"] - float(job["minutes"])
        for job in workers if job["status"] in active_statuses
    ) + len(not_yet_observed) * policy["worker_timeout_minutes"], 2)
    next_reservation = len(next_shards) * policy["worker_timeout_minutes"]
    worker_reserved_total = round(observed_worker + active_remaining + next_reservation, 2)
    result = {
        "schema_version": "1",
        "kind": "capacity_preparation_admission",
        "billing_authority": False,
        "completion_guaranteed": False,
        "admitted_shards": admitted_shards,
        "completed_shards": completed,
        "active_shards": active,
        "not_yet_observed_shards": not_yet_observed,
        "next_shards": next_shards,
        "worker": {
            "ceiling_minutes": policy["worker_ceiling_minutes"],
            "observed_minutes": observed_worker,
            "active_remaining_reservation_minutes": active_remaining,
            "next_batch_reservation_minutes": next_reservation,
            "reserved_total_minutes": worker_reserved_total,
            "double_counted_elapsed_minutes": 0,
            "transferable": False,
        },
        "support": {
            "ceiling_minutes": policy["support_ceiling_minutes"],
            "reserved_total_minutes": policy["support_ceiling_minutes"],
            "transferable": False,
        },
        "cancellation_uncertainty": {
            "ceiling_minutes": policy["cancellation_uncertainty_headroom_minutes"],
            "reserved_total_minutes": policy["cancellation_uncertainty_headroom_minutes"],
            "transferable": False,
        },
        "operational_ceiling_minutes": policy["operational_ceiling_minutes"],
        "passed": worker_reserved_total <= policy["worker_ceiling_minutes"],
        "notice": "Containment reservation only; it does not guarantee corpus completion.",
    }
    return result


def capacity_preparation_batches() -> list[list[int]]:
    """Return the fixed exact-once preparation topology."""
    policy = CAPACITY_PREPARATION_BUDGET
    full_stop = policy["full_batch_count"] * policy["batch_size"]
    batches = [
        list(range(start, start + policy["batch_size"]))
        for start in range(0, full_stop, policy["batch_size"])
    ]
    batches.extend(
        list(range(start, start + policy["tail_batch_size"]))
        for start in range(full_stop, SHARD_COUNT, policy["tail_batch_size"])
    )
    if [index for batch in batches for index in batch] != list(range(SHARD_COUNT)):
        raise ValueError("capacity preparation topology is incomplete or overlapping")
    return batches


def validate_capacity_preparation_terminal_decision(
    decision: dict, *, gate_id: int, authorization_id: str, candidate_sha: str,
    experiment_id: str, run_id: str, run_attempt: str,
    accounting_source: Path,
) -> dict:
    """Validate a source-bound terminal reservation decision from one admission gate."""
    batches = capacity_preparation_batches()
    if type(gate_id) is not int or not 0 <= gate_id < len(batches):
        raise ValueError("capacity preparation terminal gate identity is malformed")
    expected_admitted = [index for batch in batches[:gate_id] for index in batch]
    expected_next = batches[gate_id]
    if not isinstance(decision, dict):
        raise ValueError("capacity preparation terminal decision is malformed")
    evidence = decision.get("evidence")
    worker = decision.get("worker")
    if not isinstance(accounting_source, Path) or not accounting_source.is_file():
        raise ValueError("capacity preparation terminal accounting source is missing")
    source_sha256 = hashlib.sha256(accounting_source.read_bytes()).hexdigest()
    expected = {
        "schema_version": "1",
        "kind": "capacity_preparation_admission",
        "billing_authority": False,
        "completion_guaranteed": False,
        "authorization_id": authorization_id,
        "candidate_sha": candidate_sha,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "admitted_shards": expected_admitted,
        "completed_shards": expected_admitted,
        "active_shards": [],
        "not_yet_observed_shards": [],
        "next_shards": expected_next,
        "passed": False,
        "next_permitted_action": "stop_and_reconcile",
    }
    if any(decision.get(key) != value for key, value in expected.items()):
        raise ValueError("capacity preparation terminal decision is stale or conflicting")
    replayed = evaluate_capacity_preparation_admission(
        account_runner_minutes(
            accounting_source,
            expected_run_id=run_id,
            expected_run_attempt=run_attempt,
            job_timeout_minutes=CAPACITY_PREPARATION_BUDGET["worker_timeout_minutes"],
        ),
        admitted_shards=expected_admitted,
        next_shards=expected_next,
    )
    for key in (
        "completed_shards", "active_shards", "not_yet_observed_shards",
        "worker", "support", "cancellation_uncertainty", "operational_ceiling_minutes",
        "passed",
    ):
        if decision.get(key) != replayed[key]:
            raise ValueError("capacity preparation terminal decision conflicts with its source")
    if (
        not isinstance(evidence, dict)
        or evidence.get("provider_jobs") != "capacity-preparation-jobs.json"
        or evidence.get("accounting_source_sha256") != source_sha256
        or not isinstance(worker, dict)
        or worker.get("ceiling_minutes") != CAPACITY_PREPARATION_BUDGET["worker_ceiling_minutes"]
    ):
        raise ValueError("capacity preparation terminal accounting is malformed")
    if worker["reserved_total_minutes"] <= worker["ceiling_minutes"]:
        raise ValueError("capacity preparation terminal reservation is malformed")
    return decision


def build_calibration_terminal_accounting(
    current: dict,
    monitor: dict,
    lifecycle: dict,
    *,
    stage: str,
    calibration_id: str,
    ceiling: int,
    support_bounds: dict[str, int],
    predecessor: dict | None = None,
    predecessor_run_id: str = "",
    predecessor_stage: str = "",
) -> dict:
    """Build the typed terminal decision consumed by recovery and later stages."""
    if support_bounds != CALIBRATION_SUPPORT_BOUNDS:
        raise ValueError("terminal support bounds differ from the calibration policy")
    current_ids, current_floor = validate_calibration_accounting(current)
    if len(current_ids) != 1:
        raise ValueError("current terminal accounting origin is malformed")
    monitor_ids, _monitor_effective = validate_calibration_accounting(monitor)
    monitor_floor = max(
        monitor["estimated_runner_minutes"], monitor.get("charged_runner_minutes", 0),
    )
    if (
        stage not in {"1", "2", "3"}
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", calibration_id)
        or ceiling != CALIBRATION_RUNNER_MINUTE_CEILING
        or monitor_ids != current_ids
        or monitor.get("stage") != stage
        or monitor.get("calibration_id") != calibration_id
        or monitor.get("ceiling") != ceiling
        or monitor.get("passed") is not True
        or not _complete_calibration_lifecycle(lifecycle, stage)
    ):
        raise ValueError("terminal observer evidence is incomplete or incompatible")
    records = [current]
    total = current_floor
    if predecessor is not None:
        if predecessor.get("kind") != "calibration_budget_decision":
            raise ValueError("prior cumulative accounting is incompatible")
        try:
            identities, predecessor_floor = validate_calibration_accounting(predecessor)
        except ValueError as exc:
            raise ValueError("prior cumulative accounting is incompatible") from exc
        if (
            not predecessor_run_id
            or predecessor_stage not in {"1", "2", "3"}
            or identities[-1] != (predecessor_run_id, "1")
            or predecessor.get("stage") != predecessor_stage
            or predecessor.get("calibration_id") != calibration_id
            or predecessor.get("ceiling") != ceiling
        ):
            raise ValueError("prior cumulative accounting is incompatible")
        records.insert(0, predecessor)
        total = round(total + predecessor_floor, 2)
    cumulative = {
        "schema_version": "1",
        "kind": "calibration_budget_decision",
        "billing_authority": False,
        "stage": stage,
        "calibration_id": calibration_id,
        "estimated_runner_minutes": max(total, monitor_floor),
        "included_jobs": current["included_jobs"],
        "sources": records,
        "source_lineage": calibration_accounting_lineage(records),
        "monitor_floor_runner_minutes": monitor_floor,
    }
    reserved = reserve_bounded_support_minutes(cumulative, support_bounds)
    result = evaluate_calibration_budget(
        reserved, ceiling=ceiling,
        cancellation_reserve=CALIBRATION_CANCELLATION_RESERVE,
    )
    result["observer_evidence"] = {"lifecycle": lifecycle}
    return result


def bind_calibration_observer_evidence(
    accounting: dict, lifecycle: dict, *, budget_sha256: str | None = None,
) -> dict:
    """Bind complete lifecycle evidence after the terminal budget decision is built."""
    if (
        accounting.get("kind") != "calibration_budget_decision"
        or not _complete_calibration_lifecycle(lifecycle, accounting.get("stage"))
        or budget_sha256 is not None
        and not re.fullmatch(r"[0-9a-f]{64}", budget_sha256)
    ):
        raise ValueError("terminal observer evidence is incomplete or incompatible")
    evidence = {"lifecycle": lifecycle}
    if budget_sha256 is not None:
        evidence["budget_sha256"] = budget_sha256
    return {**accounting, "observer_evidence": evidence}


def plan_calibration_continuation(
    provenance_path: Path,
    jobs_path: Path,
    checkpoints_dir: Path,
    reports_dir: Path,
    manifests: list[dict],
    selected_shards: list[int],
    calibration_id: str,
    expected_run_id: str,
    expected_run_attempt: str,
    expected_revision: str,
    expected_stage: str,
    historical_accounting_paths: list[Path] | None = None,
    artifact_inventory_path: Path | None = None,
    source_run_path: Path | None = None,
) -> dict:
    """Select sparse continuation shards from checkpoints plus execution provenance."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", calibration_id):
        raise ValueError("calibration ID is invalid")
    provenance = _load_json(provenance_path)
    if (
        provenance.get("schema_version") != "1"
        or provenance.get("kind") != "calibration_source"
        or provenance.get("run_id") != expected_run_id
        or provenance.get("run_attempt") != expected_run_attempt
        or provenance.get("revision") != expected_revision
        or provenance.get("mode") != "calibration"
        or provenance.get("calibration_id") != calibration_id
        or provenance.get("calibration_stage") != expected_stage
        or "continuation_of" not in provenance
        or provenance.get("continuation_of") is not None
    ):
        raise ValueError("calibration source run provenance differs")
    manifest_by_shard = {
        item.get("shard_index"): item for item in manifests if isinstance(item, dict)
    }
    if (
        len(manifest_by_shard) != len(manifests)
        or any(
            not isinstance(index, int) or isinstance(index, bool)
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("digest", "")))
            for index, item in manifest_by_shard.items()
        )
        or len(selected_shards) != len(set(selected_shards))
        or any(index not in manifest_by_shard for index in selected_shards)
    ):
        raise ValueError("calibration manifest topology is malformed")
    accounting = account_runner_minutes(
        jobs_path, expected_run_id=expected_run_id,
        expected_run_attempt=expected_run_attempt, job_timeout_minutes=35,
    )
    accounting = retain_historical_accounting_floor(
        accounting, historical_accounting_paths or [],
    )
    raw = json.loads(jobs_path.read_text(encoding="utf-8"))
    pages = raw if isinstance(raw, list) else [raw]
    jobs_by_shard: dict[int, dict] = {}
    producer_job_ids: set[int] = set()
    for job in (job for page in pages for job in page["jobs"]):
        match = _CALIBRATION_JOB.fullmatch(str(job.get("name", "")))
        if not match:
            continue
        index = int(match.group(1))
        if index in jobs_by_shard:
            raise ValueError(f"shard {index} has conflicting execution provenance")
        job_id = job.get("id")
        if (
            not isinstance(job_id, int) or isinstance(job_id, bool) or job_id < 1
            or job_id in producer_job_ids
        ):
            raise ValueError("calibration producer job identity is malformed or duplicated")
        producer_job_ids.add(job_id)
        jobs_by_shard[index] = job
    if set(jobs_by_shard) != set(selected_shards):
        raise ValueError("calibration job provenance is incomplete or contains extra shards")
    checkpoint_artifacts: dict[int, dict] = {}
    source_run = _load_json(source_run_path) if source_run_path is not None else None
    if source_run is not None and (
        str(source_run.get("id", "")) != expected_run_id
        or str(source_run.get("run_attempt", "")) != expected_run_attempt
        or source_run.get("status") != "completed"
        or source_run.get("head_sha") != expected_revision
    ):
        raise ValueError("calibration source workflow run provenance differs")
    if artifact_inventory_path is not None:
        artifact_prefix = f"mutation-checkpoint-{calibration_id}-"
        for artifact in _load_api_pages(artifact_inventory_path, "artifacts"):
            name = str(artifact.get("name", ""))
            if not name.startswith(artifact_prefix):
                continue
            suffix = name.removeprefix(artifact_prefix)
            if not suffix.isdigit():
                raise ValueError("checkpoint artifact has a malformed shard identity")
            index = int(suffix)
            if index not in selected_shards:
                raise ValueError("checkpoint artifact is outside the selected calibration stage")
            origin = artifact.get("workflow_run")
            if (
                index in checkpoint_artifacts
                or not isinstance(artifact.get("id"), int)
                or isinstance(artifact.get("id"), bool)
                or not isinstance(artifact.get("size_in_bytes"), int)
                or artifact["size_in_bytes"] <= 0
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(artifact.get("digest", "")))
                or artifact.get("expired") is not False
                or not isinstance(origin, dict)
                or str(origin.get("id", "")) != expected_run_id
                or origin.get("head_sha") != expected_revision
            ):
                raise ValueError("checkpoint artifact provenance is malformed or incompatible")
            checkpoint_artifacts[index] = artifact
    checkpoint_by_shard: dict[int, tuple[Path, dict]] = {}
    shared_identity: tuple[str, str, str] | None = None
    for path in sorted(checkpoints_dir.rglob("mutation-checkpoint.json")) if checkpoints_dir.exists() else []:
        checkpoint = _load_json(path)
        identity = checkpoint.get("identity")
        if (
            not isinstance(identity, dict)
            or set(identity) != {
                "revision", "preflight_digest", "manifest_digest",
                "corpus_digest", "environment_digest",
            }
            or not re.fullmatch(r"[0-9a-f]{40}", str(identity.get("revision", "")))
            or any(
                not re.fullmatch(r"[0-9a-f]{64}", str(identity.get(field, "")))
                for field in (
                    "preflight_digest", "manifest_digest", "corpus_digest",
                    "environment_digest",
                )
            )
        ):
            raise ValueError(f"checkpoint {path} identity is incomplete")
        compatible_identity = (
            identity["revision"], identity["preflight_digest"], identity["environment_digest"],
        )
        if identity["revision"] != expected_revision:
            raise ValueError(f"checkpoint {path} revision differs from the candidate")
        if shared_identity is not None and compatible_identity != shared_identity:
            raise ValueError("calibration checkpoints have conflicting shared identity")
        shared_identity = compatible_identity
        matches = [index for index in selected_shards if isinstance(identity, dict)
                   and identity.get("manifest_digest") == manifest_by_shard[index]["digest"]]
        if len(matches) != 1:
            raise ValueError(f"checkpoint {path} has incompatible manifest identity")
        index = matches[0]
        if index in checkpoint_by_shard:
            raise ValueError(f"shard {index} has conflicting checkpoint evidence")
        if checkpoint.get("calibration_id") != calibration_id:
            raise ValueError(f"shard {index} checkpoint belongs to another calibration")
        if (checkpoint.get("schema_version") != "1"
                or checkpoint.get("status") not in {"completed", "incomplete"}
                or not isinstance(checkpoint.get("pending"), int)
                or isinstance(checkpoint.get("pending"), bool) or checkpoint["pending"] < 0
                or not isinstance(checkpoint.get("outcomes"), dict)
                or not isinstance(checkpoint.get("attempts"), list)
                or (checkpoint["status"] == "completed") != (checkpoint["pending"] == 0)):
            raise ValueError(f"shard {index} checkpoint is malformed")
        checkpoint_by_shard[index] = (path, checkpoint)
    reports_by_shard: dict[int, list[dict]] = {index: [] for index in selected_shards}
    quarantined_reports = []
    for path in sorted(reports_dir.rglob("mutation-report.json")) if reports_dir.exists() else []:
        try:
            report = _load_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            if path.stat().st_size != 0:
                raise ValueError(f"report {path} is malformed and cannot be quarantined") from exc
            quarantined_reports.append({
                "path": path.as_posix(), "sha256": _file_digest(path), "size": 0,
                "reason": "zero-byte historical report interrupted before atomic publication",
            })
            continue
        index = report.get("shard_index")
        if index is None and report.get("status") == "incomplete":
            identity = report.get("identity")
            matches = [
                shard for shard, (_, checkpoint) in checkpoint_by_shard.items()
                if isinstance(identity, dict)
                and identity.get("manifest_digest") == manifest_by_shard[shard]["digest"]
                and report == checkpoint
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"partial report {path} does not match exactly one retained checkpoint"
                )
            index = matches[0]
        if index not in reports_by_shard:
            raise ValueError(f"report {path} is outside the selected calibration stage")
        reports_by_shard[index].append(report)
    retry = []
    states: dict[str, dict] = {}
    for index in selected_shards:
        job = jobs_by_shard[index]
        checkpoint_entry = checkpoint_by_shard.get(index)
        _, runner_classification = _classify_runner_identity(job)
        has_runner = runner_classification != "absent"
        never_started = (not has_runner and not job.get("steps") and (
            job.get("status") in {"queued", "requested", "pending", "waiting"}
            or job.get("status") == "completed"
            and job.get("conclusion") == "skipped"))
        if checkpoint_entry is not None:
            path, checkpoint = checkpoint_entry
            artifact = checkpoint_artifacts.get(index)
            if artifact_inventory_path is not None and (
                artifact is None or path.parent.name != artifact["name"]
            ):
                raise ValueError(f"shard {index} checkpoint lacks source artifact provenance")
            if checkpoint["status"] == "completed" and checkpoint["pending"] == 0:
                if job.get("status") != "completed" or job.get("conclusion") != "success":
                    raise ValueError(
                        f"completed shard {index} has incompatible producer status"
                    )
                if any(report.get("status") != "completed" for report in reports_by_shard[index]):
                    raise ValueError(f"completed shard {index} has contradictory retained reports")
                completed_reports = [report for report in reports_by_shard[index]
                                     if report.get("status") == "completed"]
                if len(completed_reports) > 1:
                    raise ValueError(
                        f"completed shard {index} has conflicting retained reports"
                    )
                if not completed_reports:
                    raise ValueError(
                        f"completed shard {index} is missing its canonical report"
                    )
                report = completed_reports[0]
                if (report.get("calibration_id") != calibration_id
                        or report.get("revision") != checkpoint["identity"]["revision"]
                        or report.get("preflight_digest") != checkpoint["identity"]["preflight_digest"]
                        or report.get("manifest_digest") != checkpoint["identity"]["manifest_digest"]
                        or report.get("corpus_digest") != checkpoint["identity"]["corpus_digest"]
                        or report.get("environment_digest") != checkpoint["identity"]["environment_digest"]):
                    raise ValueError(f"completed shard {index} report identity differs")
                state = "completed"
                representation = {
                    "kind": "report", "path": next(
                        path.as_posix() for path in sorted(reports_dir.rglob("mutation-report.json"))
                        if path.stat().st_size and _load_json(path) == report
                    ),
                }
            else:
                if job.get("status") == "completed" and job.get("conclusion") == "success":
                    raise ValueError(f"successful shard {index} has an incomplete checkpoint")
                if checkpoint.get("incomplete_reason") != "deadline_exhausted":
                    raise ValueError(
                        f"shard {index} is not a fixed-deadline-exhausted checkpoint"
                    )
                if any(
                    not isinstance(attempt, dict)
                    or attempt.get("status") == "execution_error"
                    for attempt in checkpoint["attempts"]
                ):
                    raise ValueError(
                        f"shard {index} checkpoint contains genuine failure evidence"
                    )
                partial_reports = [report for report in reports_by_shard[index]
                                   if report.get("status") == "incomplete"]
                cancelled_producer = (
                    job.get("status") == "completed"
                    and job.get("conclusion") == "cancelled"
                    and (has_runner or job.get("steps"))
                )
                required_steps = {
                    "Resumable calibration shard evidence": ("completed", "failure"),
                    "Retain resumable execution checkpoint": ("completed", "success"),
                    "Retain mutation shard": ("completed", "failure"),
                }
                matching_steps = {
                    name: [step for step in job.get("steps", [])
                           if isinstance(step, dict) and step.get("name") == name]
                    for name in required_steps
                }
                failed_producer = (
                    job.get("status") == "completed"
                    and job.get("conclusion") in {"failure", "timed_out"}
                    and all(
                        len(matching_steps[name]) == 1
                        and (matching_steps[name][0].get("status"),
                             matching_steps[name][0].get("conclusion")) == outcome
                        for name, outcome in required_steps.items()
                    )
                )
                if job.get("conclusion") in {"failure", "timed_out"} and any(
                    len(steps) > 1 for steps in matching_steps.values()
                ):
                    raise ValueError(f"shard {index} has ambiguous producer step evidence")
                if job.get("conclusion") in {"failure", "timed_out"} and not failed_producer:
                    raise ValueError(
                        f"shard {index} lacks exact failed-producer step evidence"
                    )
                completed_reports = [report for report in reports_by_shard[index]
                                     if report.get("status") == "completed"]
                if completed_reports:
                    raise ValueError(
                        f"partial shard {index} has an unexpected completed report"
                    )
                if failed_producer:
                    if (
                        source_run is None or artifact is None
                        or path.parent.name != artifact["name"]
                    ):
                        raise ValueError(
                            f"shard {index} checkpoint lacks source artifact provenance"
                        )
                if cancelled_producer:
                    raise ValueError(
                        f"shard {index} cancellation is not deadline-exhaustion authority"
                    )
                checkpoint_only = not partial_reports and failed_producer
                if not checkpoint_only and (
                    len(partial_reports) != 1 or partial_reports[0] != checkpoint
                ):
                    raise ValueError(
                        f"partial shard {index} requires exactly one matching retained report"
                    )
                state = "started_partial_checkpoint_only" if checkpoint_only else "started_partial"
                representation = {"kind": "checkpoint", "path": path.as_posix()}
                if artifact is not None:
                    representation["source_artifact"] = {
                        "id": artifact["id"], "name": artifact["name"],
                        "archive_digest": artifact["digest"],
                        "size_in_bytes": artifact["size_in_bytes"],
                        "source_run_id": expected_run_id,
                        "source_run_attempt": expected_run_attempt,
                        "producer_job_id": job["id"],
                    }
                retry.append(index)
            states[str(index)] = {"state": state, "job_id": job["id"],
                                  "checkpoint": path.as_posix(), "pending": checkpoint["pending"],
                                  "representation": {
                                      **representation,
                                      "sha256": _file_digest(Path(representation["path"])),
                                  }}
            continue
        if never_started:
            raise ValueError(
                f"shard {index} did not produce a deadline-exhausted checkpoint"
            )
        elif job.get("status") == "completed" and job.get("conclusion") == "success":
            raise ValueError(f"successful shard {index} has no checkpoint")
        elif has_runner or job.get("steps"):
            raise ValueError(
                f"shard {index} did not produce a deadline-exhausted checkpoint"
            )
        else:
            raise ValueError(f"shard {index} missing checkpoint has indeterminate provenance")
    representations = {
        str(index): {
            **states[str(index)].get("representation", {"kind": "pending", "path": None}),
            "state": states[str(index)]["state"],
        }
        for index in selected_shards
    }
    return {"schema_version": "1", "calibration_id": calibration_id,
            "source_run_id": expected_run_id, "source_run_attempt": expected_run_attempt,
            "matrix": {"shard": retry}, "shard_count": len(retry),
            "shards": states, "accounting": accounting,
            "validated_representations": representations,
            "quarantined_reports": quarantined_reports}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    recovery = sub.add_parser("recovery-plan")
    continuation = sub.add_parser("continuation-plan")
    fresh_continuation = sub.add_parser("fresh-continuation-plan")
    recovery_record = sub.add_parser("recovery-record")
    fresh_record = sub.add_parser("fresh-completion-record")
    aggregation_record = sub.add_parser("aggregation-recovery-record")
    wave = sub.add_parser("validate-wave")
    budget = sub.add_parser("budget-gate")
    stable_jobs = sub.add_parser("collect-stable-jobs")
    calibration_continuation = sub.add_parser("plan-calibration-continuation")
    calibration_budget = sub.add_parser("calibration-budget")
    source_handoff = sub.add_parser("validate-source-handoff")
    dispatches = sub.add_parser("validate-continuation-dispatches")
    batch_admission = sub.add_parser("validate-continuation-batch")
    for command in (plan, recovery, continuation, fresh_continuation, wave):
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--manifests", type=Path, required=True)
        command.add_argument("--repository", required=True)
        command.add_argument("--workflow", required=True)
        command.add_argument("--workflow-ref", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--run-attempt", required=True)
    plan.add_argument("--orchestration-sha", required=True)
    plan.add_argument("--candidate-sha", default=FROZEN_CANDIDATE)
    plan.add_argument("--output", type=Path, required=True)
    recovery.add_argument("--source-plan", type=Path, required=True)
    recovery.add_argument("--source-reports", type=Path, required=True)
    recovery.add_argument("--orchestration-sha", required=True)
    recovery.add_argument("--output", type=Path, required=True)
    continuation.add_argument("--source-plan", type=Path, required=True)
    continuation.add_argument("--source-reports", type=Path, required=True)
    continuation.add_argument("--recovery-plan", type=Path, required=True)
    continuation.add_argument("--recovery-reports", type=Path, required=True)
    continuation.add_argument("--recovery-validation", type=Path, required=True)
    continuation.add_argument("--orchestration-sha", required=True)
    continuation.add_argument("--output", type=Path, required=True)
    fresh_continuation.add_argument("--source-plan", type=Path, required=True)
    fresh_continuation.add_argument("--wave-1-reports", type=Path, required=True)
    fresh_continuation.add_argument("--wave-2-reports", type=Path, required=True)
    fresh_continuation.add_argument("--wave-1-validation", type=Path, required=True)
    fresh_continuation.add_argument("--wave-2-validation", type=Path, required=True)
    fresh_continuation.add_argument("--source-plan-sha256", required=True)
    fresh_continuation.add_argument("--source-run-id", required=True)
    fresh_continuation.add_argument("--source-orchestration-sha", required=True)
    fresh_continuation.add_argument("--source-workflow-ref", required=True)
    fresh_continuation.add_argument("--candidate-sha", required=True)
    fresh_continuation.add_argument("--orchestration-sha", required=True)
    fresh_continuation.add_argument("--output", type=Path, required=True)
    recovery_record.add_argument("--plan", type=Path, required=True)
    recovery_record.add_argument("--reports", type=Path, required=True)
    recovery_record.add_argument("--aggregate", type=Path, required=True)
    recovery_record.add_argument("--output", type=Path, required=True)
    fresh_record.add_argument("--plan", type=Path, required=True)
    fresh_record.add_argument("--reports", type=Path, required=True)
    fresh_record.add_argument("--aggregate", type=Path, required=True)
    fresh_record.add_argument("--output", type=Path, required=True)
    aggregation_record.add_argument("--plan", type=Path, required=True)
    aggregation_record.add_argument("--reports", type=Path, required=True)
    aggregation_record.add_argument("--aggregate", type=Path, required=True)
    aggregation_record.add_argument("--source-artifact-inventory", type=Path, required=True)
    aggregation_record.add_argument("--recovery-artifact-inventory", type=Path, required=True)
    aggregation_record.add_argument("--continuation-artifact-inventory", type=Path, required=True)
    aggregation_record.add_argument("--repository", required=True)
    aggregation_record.add_argument("--workflow", required=True)
    aggregation_record.add_argument("--workflow-ref", required=True)
    aggregation_record.add_argument("--run-id", required=True)
    aggregation_record.add_argument("--run-attempt", required=True)
    aggregation_record.add_argument("--output", type=Path, required=True)
    wave.add_argument("--plan", type=Path, required=True)
    wave.add_argument("--reports", type=Path, required=True)
    wave.add_argument("--wave", choices=tuple(WAVES), required=True)
    wave.add_argument("--orchestration-sha", required=True)
    wave.add_argument("--output", type=Path, required=True)
    budget.add_argument("--jobs", type=Path, required=True)
    budget.add_argument("--observed-at")
    budget.add_argument("--job-timeout-minutes", type=int)
    budget.add_argument("--historical-accounting", type=Path, action="append", default=[])
    budget.add_argument("--prior-jobs", type=Path)
    budget.add_argument("--prior-run-id")
    budget.add_argument("--prior-run-attempt")
    budget.add_argument("--additional-prior-jobs", type=Path)
    budget.add_argument("--additional-prior-run-id")
    budget.add_argument("--additional-prior-run-attempt")
    budget.add_argument("--source", nargs=3, action="append", metavar=("JOBS", "RUN_ID", "ATTEMPT"))
    budget.add_argument("--run-id", required=True)
    budget.add_argument("--run-attempt", required=True)
    budget.add_argument("--output", type=Path, required=True)
    budget.add_argument(
        "--next-wave",
        choices=("wave-2", "wave-3", "aggregate", "complete"),
        required=True,
    )
    stable_jobs.add_argument("--endpoint", required=True)
    stable_jobs.add_argument("--output", type=Path, required=True)
    stable_jobs.add_argument("--attempts-directory", type=Path, required=True)
    stable_jobs.add_argument("--report", type=Path, required=True)
    stable_jobs.add_argument("--max-attempts", type=int, required=True)
    stable_jobs.add_argument("--max-elapsed-seconds", type=float, required=True)
    stable_jobs.add_argument("--retry-delay-seconds", type=float, required=True)
    calibration_continuation.add_argument("--jobs", type=Path, required=True)
    calibration_continuation.add_argument("--artifacts", type=Path, required=True)
    calibration_continuation.add_argument("--source-run", type=Path, required=True)
    calibration_continuation.add_argument("--provenance", type=Path, required=True)
    calibration_continuation.add_argument("--checkpoints", type=Path, required=True)
    calibration_continuation.add_argument("--reports", type=Path, required=True)
    calibration_continuation.add_argument("--manifests", type=Path, required=True)
    calibration_continuation.add_argument("--stage", choices=("1", "2", "3"), required=True)
    calibration_continuation.add_argument("--calibration-id", required=True)
    calibration_continuation.add_argument("--run-id", required=True)
    calibration_continuation.add_argument("--run-attempt", required=True)
    calibration_continuation.add_argument("--revision", required=True)
    calibration_continuation.add_argument(
        "--historical-accounting", type=Path, action="append", default=[],
    )
    calibration_continuation.add_argument("--output", type=Path, required=True)
    calibration_budget.add_argument("--accounting", type=Path, required=True)
    calibration_budget.add_argument("--ceiling", type=int, required=True)
    calibration_budget.add_argument("--cancellation-reserve", type=int, required=True)
    calibration_budget.add_argument("--output", type=Path, required=True)
    source_handoff.add_argument("--run", type=Path, required=True)
    source_handoff.add_argument("--jobs", type=Path, required=True)
    source_handoff.add_argument("--artifacts", type=Path, required=True)
    source_handoff.add_argument("--repository", required=True)
    source_handoff.add_argument("--source-run-id", required=True)
    source_handoff.add_argument("--candidate-sha", required=True)
    source_handoff.add_argument("--source-orchestration-sha", required=True)
    source_handoff.add_argument("--source-workflow-ref", required=True)
    source_handoff.add_argument("--output", type=Path, required=True)
    dispatches.add_argument("--runs", type=Path, required=True)
    dispatches.add_argument("--source-run-id", required=True)
    dispatches.add_argument("--current-run-id")
    dispatches.add_argument("--output", type=Path, required=True)
    batch_admission.add_argument("--root", type=Path, required=True)
    batch_admission.add_argument("--plan", type=Path, required=True)
    batch_admission.add_argument("--manifests", type=Path, required=True)
    batch_admission.add_argument("--reports", type=Path, required=True)
    batch_admission.add_argument("--jobs", type=Path, required=True)
    batch_admission.add_argument("--artifacts", type=Path, required=True)
    batch_admission.add_argument("--batch", type=int, required=True)
    batch_admission.add_argument("--orchestration-sha", required=True)
    batch_admission.add_argument("--repository", required=True)
    batch_admission.add_argument("--workflow", required=True)
    batch_admission.add_argument("--workflow-ref", required=True)
    batch_admission.add_argument("--run-id", required=True)
    batch_admission.add_argument("--run-attempt", required=True)
    batch_admission.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "collect-stable-jobs":
            def fetch(timeout: float) -> bytes:
                return subprocess.run(
                    ["gh", "api", "--paginate", "--slurp", args.endpoint],
                    check=True, capture_output=True, timeout=timeout,
                ).stdout

            result = collect_stable_job_pages(
                args.output, args.attempts_directory, fetch=fetch,
                max_attempts=args.max_attempts,
                max_elapsed_seconds=args.max_elapsed_seconds,
                retry_delay_seconds=args.retry_delay_seconds,
            )
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "validate-source-handoff":
            result = validate_source_handoff(
                args.run, args.jobs, args.artifacts, repository=args.repository,
                source_run_id=args.source_run_id, candidate_sha=args.candidate_sha,
                source_orchestration_sha=args.source_orchestration_sha,
                source_workflow_ref=args.source_workflow_ref,
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "validate-continuation-dispatches":
            result = validate_continuation_dispatches(
                args.runs, args.source_run_id, args.current_run_id,
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "validate-continuation-batch":
            identity = {
                "repository": args.repository, "workflow": args.workflow,
                "workflow_ref": args.workflow_ref, "run_id": args.run_id,
                "run_attempt": args.run_attempt,
            }
            result = validate_continuation_batch(
                args.root, args.plan, args.manifests, args.reports, args.jobs,
                args.artifacts, batch=args.batch,
                orchestration_sha=args.orchestration_sha, identity=identity,
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "plan-calibration-continuation":
            manifests = [_load_json(path) for path in sorted(args.manifests.glob("partition-*.json"))]
            result = plan_calibration_continuation(
                args.provenance, args.jobs, args.checkpoints, args.reports, manifests,
                WAVES[f"wave-{args.stage}"], args.calibration_id, args.run_id,
                args.run_attempt, args.revision, args.stage, args.historical_accounting,
                args.artifacts,
                args.source_run,
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "calibration-budget":
            result = evaluate_calibration_budget(
                _load_json(args.accounting), ceiling=args.ceiling,
                cancellation_reserve=args.cancellation_reserve,
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0 if result["passed"] else 2
        if args.command == "budget-gate":
            observed_at = (
                datetime.fromisoformat(args.observed_at.replace("Z", "+00:00"))
                if args.observed_at else None
            )
            if args.source and any(value is not None for value in (
                args.prior_jobs, args.prior_run_id, args.prior_run_attempt,
                args.additional_prior_jobs, args.additional_prior_run_id,
                args.additional_prior_run_attempt,
            )):
                raise ValueError("repeatable sources cannot be combined with legacy prior sources")
            prior_values = (args.prior_jobs, args.prior_run_id, args.prior_run_attempt)
            additional_values = (args.additional_prior_jobs, args.additional_prior_run_id,
                                 args.additional_prior_run_attempt)
            if (any(value is not None for value in prior_values) and not all(value is not None for value in prior_values)
                    or any(value is not None for value in additional_values) and not all(value is not None for value in additional_values)
                    or args.additional_prior_jobs is not None and args.prior_jobs is None):
                raise ValueError("each prior jobs source, run ID, and run attempt must be supplied together")
            if args.source:
                accounting = combine_accounting_sources([
                    (Path(path), run_id, attempt) for path, run_id, attempt in args.source
                ] + [(args.jobs, args.run_id, args.run_attempt)], observed_at,
                    job_timeout_minutes=args.job_timeout_minutes)
            elif args.prior_jobs is None:
                accounting = account_runner_minutes(
                    args.jobs,
                    observed_at,
                    expected_run_id=args.run_id,
                    expected_run_attempt=args.run_attempt,
                    job_timeout_minutes=args.job_timeout_minutes,
                )
            elif args.additional_prior_jobs is None:
                accounting = combine_accounting(
                    args.prior_jobs,
                    args.jobs,
                    observed_at,
                    expected_prior_run_id=args.prior_run_id,
                    expected_prior_run_attempt=args.prior_run_attempt,
                    expected_current_run_id=args.run_id,
                    expected_current_run_attempt=args.run_attempt,
                    job_timeout_minutes=args.job_timeout_minutes,
                )
            else:
                accounting = combine_accounting_sources([
                    (args.prior_jobs, args.prior_run_id, args.prior_run_attempt),
                    (args.additional_prior_jobs, args.additional_prior_run_id,
                     args.additional_prior_run_attempt),
                    (args.jobs, args.run_id, args.run_attempt),
                ], observed_at, job_timeout_minutes=args.job_timeout_minutes)
            accounting = retain_historical_accounting_floor(
                accounting, args.historical_accounting,
            )
            observed = accounting["estimated_runner_minutes"]
            ceiling = BUDGET["launch_ceiling"][args.next_wave]
            result = {**accounting,
                "launch_ceiling": ceiling,
                "next_wave": args.next_wave,
                "passed": observed <= ceiling,
            }
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0 if result["passed"] else 2
        if args.command == "recovery-record":
            result = build_recovery_record(args.plan, args.reports, args.aggregate)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "fresh-completion-record":
            result = build_fresh_completion_record(args.plan, args.reports, args.aggregate)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        if args.command == "aggregation-recovery-record":
            identity = {
                "repository": args.repository, "workflow": args.workflow,
                "workflow_ref": args.workflow_ref, "run_id": args.run_id,
                "run_attempt": args.run_attempt,
            }
            result = build_aggregation_recovery_record(
                args.plan, args.reports, args.aggregate, args.source_artifact_inventory,
                args.recovery_artifact_inventory, args.continuation_artifact_inventory,
                identity,
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            return 0
        identity = {
            "repository": args.repository,
            "workflow": args.workflow,
            "workflow_ref": args.workflow_ref,
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
        }
        if args.command == "plan":
            result = build_plan(
                args.root, args.manifests, args.orchestration_sha, identity,
                candidate_sha=args.candidate_sha,
            )
        elif args.command == "recovery-plan":
            result = build_recovery_plan(
                args.root,
                args.source_plan,
                args.manifests,
                args.source_reports,
                args.orchestration_sha,
                identity,
            )
        elif args.command == "continuation-plan":
            result = build_continuation_plan(
                args.root, args.source_plan, args.source_reports, args.recovery_plan,
                args.recovery_reports, args.recovery_validation, args.manifests,
                args.orchestration_sha, identity,
            )
        elif args.command == "fresh-continuation-plan":
            result = build_fresh_continuation_plan(
                args.root, args.source_plan, args.wave_1_reports, args.wave_2_reports,
                args.wave_1_validation, args.wave_2_validation, args.manifests,
                args.source_plan_sha256, args.source_run_id,
                args.source_orchestration_sha, args.source_workflow_ref,
                args.orchestration_sha, identity, args.candidate_sha,
            )
        else:
            result = validate_wave(
                args.root,
                args.plan,
                args.manifests,
                args.reports,
                args.wave,
                args.orchestration_sha,
                identity,
            )
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"staged preflight rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
