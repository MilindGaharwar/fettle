#!/usr/bin/env python3
"""Validate fixed staged-preflight execution and linked recovery evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

FROZEN_CANDIDATE = "0fc41fdfee13e09f4bda3dc5eee177030882aa36"
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
    "operational_ceiling_runner_minutes": 740,
    "wave_allowances": {"wave-1": 20, "wave-2": 75, "wave-3": 500},
    "orchestration_and_aggregation": 45,
    "cancellation_headroom": 100,
    "launch_ceiling": {"wave-2": 20, "wave-3": 95, "aggregate": 595, "complete": 640},
}
MATRIX_JOB_LIMIT = 256
CONTINUATION_SUPPORT_JOBS = 7


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


def _load_manifests(root: Path, directory: Path) -> list[dict]:
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
        item["revision"] != FROZEN_CANDIDATE or item["shard_count"] != SHARD_COUNT
        for item in manifests
    ):
        raise ValueError("manifest candidate or topology differs from the frozen identity")
    return manifests


def build_plan(root: Path, manifests_dir: Path, orchestration_sha: str, identity: dict) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", orchestration_sha):
        raise ValueError("orchestration SHA must be a full lowercase commit")
    manifests = _load_manifests(root, manifests_dir)
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
        "candidate_sha": FROZEN_CANDIDATE,
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
    if (
        plan.get("candidate_sha") != FROZEN_CANDIDATE
        or plan.get("orchestration_sha") != orchestration_sha
        or plan.get("workflow") != identity
    ):
        raise ValueError("wave identity differs from the frozen plan")
    manifests = _load_manifests(root, manifests_dir)
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
        "candidate_sha": FROZEN_CANDIDATE,
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


def validate_continuation_topology() -> dict:
    matrix_jobs = len(WAVES["wave-3"])
    expanded_jobs = matrix_jobs + CONTINUATION_SUPPORT_JOBS
    if matrix_jobs != 216 or expanded_jobs > MATRIX_JOB_LIMIT:
        raise ValueError("continuation workflow exceeds the fixed matrix-job topology")
    return {
        "matrix_jobs": matrix_jobs,
        "support_jobs": CONTINUATION_SUPPORT_JOBS,
        "expanded_jobs": expanded_jobs,
        "platform_limit": MATRIX_JOB_LIMIT,
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


def account_runner_minutes(
    jobs_path: Path,
    now: datetime | None = None,
    *,
    expected_run_id: str | None = None,
    expected_run_attempt: str | None = None,
) -> dict:
    raw = jobs_path.read_bytes()
    pages = json.loads(raw)
    if not isinstance(pages, list):
        pages = [pages]
    if not pages or any(
        not isinstance(page, dict) or not isinstance(page.get("jobs"), list)
        for page in pages
    ):
        raise ValueError("jobs response is missing or malformed")
    jobs = [job for page in pages for job in page["jobs"]]
    if not jobs:
        raise ValueError("jobs response is empty")
    totals = {page.get("total_count") for page in pages}
    if len(totals) != 1 or not all(
        isinstance(value, int) and not isinstance(value, bool) for value in totals
    ):
        raise ValueError("jobs response has missing or inconsistent total_count")
    ids = [job.get("id") for job in jobs if isinstance(job, dict)]
    if len(ids) != len(jobs) or any(
        not isinstance(job_id, int) or isinstance(job_id, bool) for job_id in ids
    ):
        raise ValueError("jobs response has a missing or malformed job ID")
    if len(ids) != len(set(ids)):
        raise ValueError("jobs response contains duplicate job IDs")
    if totals != {len(jobs)}:
        raise ValueError("jobs response pagination is incomplete")
    total = 0.0
    current = now or datetime.now(UTC)
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
        runner_fields = ("runner_id", "runner_name", "runner_group_id", "runner_group_name")
        if any(field not in job for field in runner_fields):
            raise ValueError(f"job {job['id']} runner identity is incomplete")
        runner_identity = {field: job[field] for field in runner_fields}
        runner_id = runner_identity["runner_id"]
        has_runner_identity = any(value is not None for value in runner_identity.values())
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
            status in {"queued", "requested", "pending", "waiting"}
            and conclusion is None and not has_runner_identity and not steps and completed is None
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
        elif status == "in_progress" and conclusion is None and completed is None:
            end = current
            basis = "elapsed through observation time"
        else:
            raise ValueError(f"job {job['id']} usage is indeterminate")
        if end < start:
            raise ValueError(f"executed job {job['id']} timing is reversed")
        minutes = (end - start).total_seconds() / 60
        total += minutes
        included.append({
            "id": job["id"], "name": job.get("name"), "status": status,
            "conclusion": conclusion, "runner_id": runner_id, "started_at": started,
            "completed_at": completed, "minutes": round(minutes, 2), "basis": basis,
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
) -> dict:
    prior = account_runner_minutes(
        prior_jobs_path,
        now,
        expected_run_id=expected_prior_run_id,
        expected_run_attempt=expected_prior_run_attempt,
    )
    current = account_runner_minutes(
        current_jobs_path,
        now,
        expected_run_id=expected_current_run_id,
        expected_run_attempt=expected_current_run_attempt,
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


def combine_accounting_sources(sources: list[tuple[Path, str, str]], now: datetime | None = None) -> dict:
    if not sources:
        raise ValueError("at least one accounting source is required")
    reports = [
        account_runner_minutes(path, now, expected_run_id=run_id, expected_run_attempt=attempt)
        for path, run_id, attempt in sources
    ]
    return {
        "schema_version": "1",
        "kind": "combined_operational_runner_time_estimate",
        "billing_authority": False,
        "estimated_runner_minutes": round(sum(item["estimated_runner_minutes"] for item in reports), 2),
        "sources": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    recovery = sub.add_parser("recovery-plan")
    continuation = sub.add_parser("continuation-plan")
    recovery_record = sub.add_parser("recovery-record")
    wave = sub.add_parser("validate-wave")
    budget = sub.add_parser("budget-gate")
    for command in (plan, recovery, continuation, wave):
        command.add_argument("--root", type=Path, required=True)
        command.add_argument("--manifests", type=Path, required=True)
        command.add_argument("--repository", required=True)
        command.add_argument("--workflow", required=True)
        command.add_argument("--workflow-ref", required=True)
        command.add_argument("--run-id", required=True)
        command.add_argument("--run-attempt", required=True)
    plan.add_argument("--orchestration-sha", required=True)
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
    recovery_record.add_argument("--plan", type=Path, required=True)
    recovery_record.add_argument("--reports", type=Path, required=True)
    recovery_record.add_argument("--aggregate", type=Path, required=True)
    recovery_record.add_argument("--output", type=Path, required=True)
    wave.add_argument("--plan", type=Path, required=True)
    wave.add_argument("--reports", type=Path, required=True)
    wave.add_argument("--wave", choices=tuple(WAVES), required=True)
    wave.add_argument("--orchestration-sha", required=True)
    wave.add_argument("--output", type=Path, required=True)
    budget.add_argument("--jobs", type=Path, required=True)
    budget.add_argument("--prior-jobs", type=Path)
    budget.add_argument("--prior-run-id")
    budget.add_argument("--prior-run-attempt")
    budget.add_argument("--additional-prior-jobs", type=Path)
    budget.add_argument("--additional-prior-run-id")
    budget.add_argument("--additional-prior-run-attempt")
    budget.add_argument("--run-id", required=True)
    budget.add_argument("--run-attempt", required=True)
    budget.add_argument("--output", type=Path, required=True)
    budget.add_argument(
        "--next-wave",
        choices=("wave-2", "wave-3", "aggregate", "complete"),
        required=True,
    )
    args = parser.parse_args()
    try:
        if args.command == "budget-gate":
            prior_values = (args.prior_jobs, args.prior_run_id, args.prior_run_attempt)
            additional_values = (args.additional_prior_jobs, args.additional_prior_run_id,
                                 args.additional_prior_run_attempt)
            if (any(value is not None for value in prior_values) and not all(value is not None for value in prior_values)
                    or any(value is not None for value in additional_values) and not all(value is not None for value in additional_values)
                    or args.additional_prior_jobs is not None and args.prior_jobs is None):
                raise ValueError("each prior jobs source, run ID, and run attempt must be supplied together")
            if args.prior_jobs is None:
                accounting = account_runner_minutes(
                    args.jobs,
                    expected_run_id=args.run_id,
                    expected_run_attempt=args.run_attempt,
                )
            elif args.additional_prior_jobs is None:
                accounting = combine_accounting(
                    args.prior_jobs,
                    args.jobs,
                    expected_prior_run_id=args.prior_run_id,
                    expected_prior_run_attempt=args.prior_run_attempt,
                    expected_current_run_id=args.run_id,
                    expected_current_run_attempt=args.run_attempt,
                )
            else:
                accounting = combine_accounting_sources([
                    (args.prior_jobs, args.prior_run_id, args.prior_run_attempt),
                    (args.additional_prior_jobs, args.additional_prior_run_id,
                     args.additional_prior_run_attempt),
                    (args.jobs, args.run_id, args.run_attempt),
                ])
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
        identity = {
            "repository": args.repository,
            "workflow": args.workflow,
            "workflow_ref": args.workflow_ref,
            "run_id": args.run_id,
            "run_attempt": args.run_attempt,
        }
        if args.command == "plan":
            result = build_plan(args.root, args.manifests, args.orchestration_sha, identity)
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
