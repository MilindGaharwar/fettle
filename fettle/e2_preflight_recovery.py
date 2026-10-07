#!/usr/bin/env python3
"""Validate the one-time E2 staged-preflight handoff recovery."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from fettle.staged_preflight import WAVES, validate_wave

REPOSITORY = "MilindGaharwar/fettle"
RECOVERY_BRANCH = "recovery/e2-preflight-continuation-20261007"
CANDIDATE_SHA = "f5560685d1f9eaea05107947fb0ecab791ad9478"
SOURCE_RUN_ID = "37573662156"
SOURCE_RUN_ATTEMPT = "1"
SOURCE_FAILURE_JOB_ID = 112642844198
SOURCE_WORKFLOW_REF = (
    "MilindGaharwar/fettle/.github/workflows/mutation.yml@"
    "refs/heads/audit/hardening-integration-20261005"
)
SOURCE_PLAN_SHA256 = "a6fbc9607212d36215d917284859d336ee6db2a370b7ea379a3ad574a4402efa"
WAVE_VALIDATION_SHA256 = {
    "wave-1": "79cecd231af6e02f0446f3b786586dd153efcf066bd90a2ca5a34c52e53f385b",
    "wave-2": "957be2f61b792bc3d19827816e6b2cbf2b31e1b2e9f0347a1ef03f98069bfe50",
}
REPORT_ARTIFACT_INVENTORY_SHA256 = {
    "wave-1": "6c27601067b5698b051a3829ee8216d0bb4659d383e25db9517efbe4f97b6c43",
    "wave-2": "1fb893196965b99516ec2c26f33c77c907d74509ef252961dc86a922f9afe52d",
}
REPORT_SHA256 = {
    0: "84c6caf1c65b78eb056e48798a881da7791fea896ba104384d633f2b0c433ae9",
    1: "e56aee0db861947ea97f79b0af0dc3ea5783e730a844867d773db54b3ff68826",
    2: "df60127c064a7839d74b70bebcf7ca677f58dfa07ea54e0a10d94fd704eef816",
    3: "ed52c5b868f6181a66f22f24b6c38481bf51af57fce5b90e083a12a6954a94ff",
    4: "0698915b0d3b7156f638a5b9a4276423ddf5f5fb81960668c525b7988c2f37bd",
    5: "e28ed185c1fd132d881664ce12db5e0b4a189d643cae28665dbc32d05f8ed452",
    6: "d0855dafee8d7fd5bf8f4d0657604d5b5aa4f563907bf90c29f6adeea158ec45",
    7: "92ab63b4e225e7d6d543779ca1e949b603b2190e129840e2afa44ef1cb37be6e",
    8: "cd4d97cf9833e9deed1a735af6d15176d0ca54d7d58efb222a98ba2c19cd2b25",
    9: "a205da5f3852d562a683a4a358e495c907073b32e656f589128767653cd78625",
    10: "ba5c0e8645f85d1a9ebea159a460d3728d7ed06f3c8db6c378b44c85495060fa",
    11: "21e70357e410b3db6ad7bce751c0000966de668560a6104c6df7a53d1c3a028b",
    12: "2b7d574ae855fcf41f62bfa0f8fb792263017641613e01403c9e18dd59d80797",
    13: "695f4abb4e00c6cb43cf819d8fd658d4a3d9a7c6c0ba9c38d1d8e30d766c6ab0",
    14: "82ee7ee34b34990366a8ffde3349a4cafbee13bb8770d182513c77c331b88a69",
    15: "e1d0edf081d1503bdc75bc1cc658b3afe4bf3b3f5998dee9d432fd35556fa968",
    16: "6eb6cd030f5147f8e72a473a312d5291ab579554b55119d0e05051951b785c64",
    17: "07920f2af735725072cf70efeca63311e2cb9bf4b7c9477933d98a72e7ae38a5",
    18: "8b14cf2da192a4bd307f2cdb90157992a22ac623262eb5d8b173571f387d73e3",
    19: "8c39fac25ec1e2cb7ba8cb0073082c4f8d0531be304e94dde62ce44f8d67ca82",
    20: "30bf142048b33a6b8445deaf8d21ed7c2972caafacb446468d4e1625116a3a8b",
    21: "0cfdf416332e7a6347353ad751b6f1e6e4f8b17d7022f593c39abbd7d19c84b1",
    22: "d0ce8d062ac2b0d7dd4613d8436e1fbfb5713622faeb4734b33c7be9129d2e78",
    23: "514c77d6d4ce6c32d002ffb322e6c2049a4786f4c3640df591b8ab1476903802",
    24: "5f4f5dd49487e222e99338efac0a327abe3cbde638be35742375c7721d30d925",
    25: "a34c9de742152722c8c70b792cb4604ad58e244dca796dcfe436a68b9687ea9d",
    26: "3c46bae3fad383387f3b4563680b8d9d23f50f8148d6a4118437ce1d9caee7d8",
    27: "878aa1cafeaf7afd4c6f5d8def75339cd152fbece0dd892a6355fc11250c73ce",
    28: "599701d2c42c77b34ecf2c412302153051463e2714fcbd3a9abb785344ca53a7",
    29: "8ae032a8b92b1d392fb022285fc9c06e85d9ecd7606902262423be86f3b6788c",
    30: "b3798279913cd5950fb6ae15e056ea93ddb2368c884e9206ca306c70a735c255",
    31: "6c21b4380d44b1f405a22b93464c2a220e6676435e18566097575d23566435e6",
    32: "7190b86683e39300fc5e8cdd4a83600dcf04f688c7065955c78342bd8e092b75",
    33: "1cf87170176fffeff64004686cd6e8d5758a0a03300bc15bd583eb2d656f1166",
    34: "14e3f53786111947d85caf5f21f547fc4384ea67964362532465fcb4c8541023",
    37: "5a3190562f29f969318380e16bdd65b2d4be5765781f89c91ef00a7330e0726f",
    48: "03564cf885dcdede923e49037e56a6c098f11b865a0f53a134489bea7240caa1",
    50: "eb36490f3c90ad277b59e03524bbc4cac924b66df280ccf2582a9f795907bb21",
    51: "6e437e7127a9e5424617359e6179772dbd8c0d84f5ce02e25ddfcfa4f0282a0d",
    53: "f0c886be72b7c4f23cf5ae475358230a85faa45fd6da9a1b587417cedcb681ea",
}


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jobs(path: Path) -> list[dict]:
    pages = _load(path)
    if not isinstance(pages, list) or not pages:
        raise ValueError("source jobs are missing or malformed")
    jobs = [job for page in pages for job in page.get("jobs", [])]
    if any(page.get("total_count") != len(jobs) for page in pages):
        raise ValueError("source job pagination is incomplete")
    return jobs


def validate_source_exception(
    *, root: Path, source_run_path: Path, source_jobs_path: Path, source_failure_log_path: Path,
    source_artifacts_path: Path,
    prior_runs_path: Path, plan_path: Path, manifests_dir: Path,
    wave_1_reports: Path, wave_2_reports: Path, wave_1_validation: Path,
    wave_2_validation: Path,
    orchestration_sha: str, current_run_id: str,
) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", orchestration_sha):
        raise ValueError("recovery orchestration SHA is malformed")
    if not re.fullmatch(r"[1-9][0-9]*", current_run_id):
        raise ValueError("current recovery run ID is malformed")
    run = _load(source_run_path)
    if not isinstance(run, dict) or (
        str(run.get("id")) != SOURCE_RUN_ID
        or str(run.get("run_attempt")) != SOURCE_RUN_ATTEMPT
        or run.get("head_sha") != CANDIDATE_SHA
        or run.get("path") != ".github/workflows/mutation.yml"
        or run.get("event") != "workflow_dispatch"
        or run.get("head_branch") != "audit/hardening-integration-20261005"
        or run.get("status") != "completed"
        or run.get("conclusion") != "failure"
    ):
        raise ValueError("source run is not the authorized failed E2 attempt")

    jobs = _jobs(source_jobs_path)
    if any(str(job.get("run_id")) != SOURCE_RUN_ID or str(job.get("run_attempt")) != "1"
           for job in jobs):
        raise ValueError("source jobs contain a different run attempt")
    failures = [job for job in jobs if job.get("conclusion") not in {"success", "skipped"}]
    if (
        len(failures) != 1 or failures[0].get("id") != SOURCE_FAILURE_JOB_ID
        or failures[0].get("name") != "mutation (dispatch staged preflight continuation)"
    ):
        raise ValueError("source failure was not confined to the dispatch handoff")
    failed_steps = [step for step in failures[0].get("steps", []) if step.get("conclusion") == "failure"]
    if [step.get("name") for step in failed_steps] != ["Dispatch immutable continuation"]:
        raise ValueError("source failure step differs from the authorized handoff failure")
    failure_log = source_failure_log_path.read_text(encoding="utf-8")
    if "failed to run git: fatal: not a git repository" not in failure_log:
        raise ValueError("source failure log does not contain the authorized handoff error")
    if any(str(job.get("name", "")).startswith("mutation (continuation shard ") for job in jobs):
        raise ValueError("source run contains unexpected wave-3 execution")

    prior_runs = _load(prior_runs_path)
    if not isinstance(prior_runs, list):
        raise ValueError("prior continuation run inventory is malformed")
    competing = [
        item for item in prior_runs if isinstance(item, dict)
        and str(item.get("databaseId")) != current_run_id
        and item.get("event") == "workflow_dispatch"
        and (
            item.get("headSha") == CANDIDATE_SHA
            or item.get("headBranch") == RECOVERY_BRANCH
        )
    ]
    if competing:
        raise ValueError("an E2 continuation or recovery execution already exists")

    pages = _load(source_artifacts_path)
    if not isinstance(pages, list) or not pages:
        raise ValueError("source artifact inventory is missing or malformed")
    artifacts = [item for page in pages for item in page.get("artifacts", [])]
    if any(page.get("total_count") != len(artifacts) for page in pages):
        raise ValueError("source artifact pagination is incomplete")
    if any(str(item.get("name", "")).startswith("mutation-preflight-wave-3-") for item in artifacts):
        raise ValueError("source artifacts contain unexpected wave-3 evidence")
    for wave in ("wave-1", "wave-2"):
        selected = sorted(
            ({key: item.get(key) for key in ("id", "name", "size_in_bytes", "digest", "expired")}
             for item in artifacts if str(item.get("name", "")).startswith(
                 f"mutation-preflight-{wave}-{SOURCE_RUN_ID}-1-")),
            key=lambda item: str(item["name"]),
        )
        expected = WAVES[wave]
        indexes = []
        for item in selected:
            match = re.fullmatch(
                rf"mutation-preflight-{wave}-{SOURCE_RUN_ID}-1-(\d+)",
                str(item["name"]),
            )
            if (
                match is None or not isinstance(item["id"], int)
                or not isinstance(item["size_in_bytes"], int) or item["size_in_bytes"] <= 0
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(item["digest"]))
                or item["expired"] is not False
            ):
                raise ValueError(f"{wave} artifact inventory is malformed")
            indexes.append(int(match.group(1)))
        inventory_digest = hashlib.sha256(
            json.dumps(selected, sort_keys=True, separators=(",", ":")).encode(),
        ).hexdigest()
        if sorted(indexes) != sorted(expected) or len(indexes) != len(set(indexes)):
            raise ValueError(f"{wave} artifact assignments are incomplete or duplicated")
        if inventory_digest != REPORT_ARTIFACT_INVENTORY_SHA256[wave]:
            raise ValueError(f"{wave} artifact inventory differs from the authorized source")

    if _sha256(plan_path) != SOURCE_PLAN_SHA256:
        raise ValueError("source plan differs from the authorized E2 plan")
    plan = _load(plan_path)
    if not isinstance(plan, dict) or plan.get("candidate_sha") != CANDIDATE_SHA:
        raise ValueError("source plan candidate differs from E2")
    manifests = sorted(manifests_dir.glob("partition-*.json"))
    if len(manifests) != 256:
        raise ValueError("source manifest set is incomplete")

    source_identity = {
        "repository": REPOSITORY, "workflow": "Mutation evidence",
        "workflow_ref": SOURCE_WORKFLOW_REF, "run_id": SOURCE_RUN_ID,
        "run_attempt": SOURCE_RUN_ATTEMPT,
    }
    validations = {}
    for wave, reports, retained in (
        ("wave-1", wave_1_reports, wave_1_validation),
        ("wave-2", wave_2_reports, wave_2_validation),
    ):
        if _sha256(retained) != WAVE_VALIDATION_SHA256[wave]:
            raise ValueError(f"retained {wave} validation digest changed")
        reproduced = validate_wave(
            root, plan_path, manifests_dir, reports, wave, CANDIDATE_SHA,
            source_identity,
        )
        if reproduced != _load(retained):
            raise ValueError(f"retained {wave} validation does not reproduce")
        validations[wave] = reproduced

    paths = [*wave_1_reports.rglob("mutation-preflight.json"),
             *wave_2_reports.rglob("mutation-preflight.json")]
    found: dict[int, str] = {}
    for path in paths:
        report = _load(path)
        if not isinstance(report, dict) or not isinstance(report.get("shard_index"), int):
            raise ValueError("source report identity is malformed")
        index = report["shard_index"]
        if index in found:
            raise ValueError("source reports contain a duplicate shard assignment")
        found[index] = _sha256(path)
    if found != REPORT_SHA256:
        raise ValueError("source report files differ from the authorized E2 corpus")

    return {
        "schema_version": "1", "status": "validated", "passed": True,
        "kind": "operator_authorized_dispatch_recovery",
        "candidate_sha": CANDIDATE_SHA,
        "recovery_orchestration_sha": orchestration_sha,
        "recovery_run_id": current_run_id,
        "source_run": {"run_id": SOURCE_RUN_ID, "run_attempt": "1",
                       "verdict": "permanently failed; dispatch handoff only"},
        "plan_sha256": SOURCE_PLAN_SHA256,
        "manifest_topology_digest": plan["manifest_topology_digest"],
        "retained_reports": len(found), "validations": validations,
        "execution_wave": {"shards": WAVES["wave-3"], "max_parallel": 8},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--source-jobs", type=Path, required=True)
    parser.add_argument("--source-failure-log", type=Path, required=True)
    parser.add_argument("--source-artifacts", type=Path, required=True)
    parser.add_argument("--prior-runs", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--wave-1-reports", type=Path, required=True)
    parser.add_argument("--wave-2-reports", type=Path, required=True)
    parser.add_argument("--wave-1-validation", type=Path, required=True)
    parser.add_argument("--wave-2-validation", type=Path, required=True)
    parser.add_argument("--orchestration-sha", required=True)
    parser.add_argument("--current-run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_source_exception(
            root=args.root, source_run_path=args.source_run, source_jobs_path=args.source_jobs,
            source_failure_log_path=args.source_failure_log,
            source_artifacts_path=args.source_artifacts, prior_runs_path=args.prior_runs,
            plan_path=args.plan, manifests_dir=args.manifests,
            wave_1_reports=args.wave_1_reports, wave_2_reports=args.wave_2_reports,
            wave_1_validation=args.wave_1_validation,
            wave_2_validation=args.wave_2_validation,
            orchestration_sha=args.orchestration_sha,
            current_run_id=args.current_run_id,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"E2 recovery rejected: {exc}", file=sys.stderr)
        return 2
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
