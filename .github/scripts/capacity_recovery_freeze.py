#!/usr/bin/env python3
"""Validate retained provider artifacts and freeze one recovery package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

from fettle.config import load_config
from fettle.mutation_test import (
    _write_json_atomic,
    aggregate_capacity_validation_shards,
    build_capacity_recovery_lineage,
    build_capacity_validation_plan,
    load_partition_manifest,
    validate_capacity_recovery_lineage,
)


SOURCE_SHA = "65e63d953b45d3672c24df74d0a1364b83a0157b"
SOURCE_RUN_ID = "39263581356"
SOURCE_EXPERIMENT_ID = "capval-prep-containment-20261019-c"


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--enumeration-zips", required=True)
    parser.add_argument("--manifests", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--accounting", required=True)
    parser.add_argument("--gate-18-zip", required=True)
    parser.add_argument("--monitor-zip", required=True)
    parser.add_argument("--controller-sha", required=True)
    parser.add_argument("--source-python", required=True)
    parser.add_argument("--recovery-experiment-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = Path(args.source_root).resolve()
    source_python = Path(os.path.abspath(args.source_python))
    provider = Path(args.provider).resolve()
    zips = Path(args.enumeration_zips).resolve()
    manifests_dir = Path(args.manifests).resolve()
    output = Path(args.output).resolve()
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    if revision != SOURCE_SHA or args.controller_sha == SOURCE_SHA:
        raise ValueError("capacity recovery source and controller identities are not separate")

    artifact_pages = _read(provider / "artifacts.json")
    job_pages = _read(provider / "final-jobs.json")
    if not isinstance(artifact_pages, list) or not isinstance(job_pages, list):
        raise ValueError("capacity recovery provider pages are malformed")
    artifacts = [a for page in artifact_pages for a in page.get("artifacts", [])]
    prefix = f"capacity-validation-enumeration-{SOURCE_RUN_ID}-"
    enumeration = {int(a["name"].removeprefix(prefix)): a for a in artifacts if a.get("name", "").startswith(prefix)}
    if sorted(enumeration) != list(range(256)):
        raise ValueError("capacity recovery provider artifacts are incomplete")

    reports = []
    for index in range(256):
        archive = zips / f"{index}.zip"
        advertised = enumeration[index].get("digest", "").removeprefix("sha256:")
        if _sha(archive) != advertised:
            raise ValueError(f"capacity recovery artifact {index} digest differs")
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            if names != ["capacity-validation-enumeration.json"]:
                raise ValueError(f"capacity recovery artifact {index} content differs")
            report = json.loads(bundle.read(names[0]))
        if report.get("shard_index") != index:
            raise ValueError(f"capacity recovery artifact {index} shard identity differs")
        reports.append(report)

    gate_zip = Path(args.gate_18_zip).resolve()
    monitor_zip = Path(args.monitor_zip).resolve()
    if _sha(gate_zip) != "6215c9dd61fe67deaacee09958177115782de2acaf4b80dbd02b0c4928b616ca":
        raise ValueError("capacity recovery gate 18 artifact digest differs")
    if _sha(monitor_zip) != "cefe007d9ff958e4c7c504176544f439e8fb03d63d85b62b5b87391c5ae0f8f4":
        raise ValueError("capacity recovery monitor artifact digest differs")
    with zipfile.ZipFile(gate_zip) as bundle:
        gate_collection_bytes = bundle.read("capacity-preparation-collection.json")
        gate_jobs_bytes = bundle.read("capacity-preparation-jobs.json")
    gate_pages = json.loads(gate_jobs_bytes)
    gate_job = next(
        (job for page in gate_pages for job in page.get("jobs", [])
         if job.get("id") == 118127166658),
        None,
    )
    if not isinstance(gate_job, dict) or "(249)" not in str(gate_job.get("name", "")):
        raise ValueError("capacity recovery gate 18 nonterminal snapshot is missing")
    with zipfile.ZipFile(monitor_zip) as bundle:
        decision_bytes = bundle.read("final-decision.json")
    decision = json.loads(decision_bytes)
    historical_evidence = {
        "gate_18": {
            "artifact_sha256": _sha(gate_zip),
            "collection_sha256": hashlib.sha256(gate_collection_bytes).hexdigest(),
            "jobs_sha256": hashlib.sha256(gate_jobs_bytes).hexdigest(),
            "observed_nonterminal_job_id": gate_job.get("id"),
            "observed_nonterminal_shard": 249,
            "observed_status": gate_job.get("status"),
            "observed_conclusion": gate_job.get("conclusion"),
            "disposition": "failed_closed_non_pass",
        },
        "monitor": {
            "artifact_sha256": _sha(monitor_zip),
            "final_decision_sha256": hashlib.sha256(decision_bytes).hexdigest(),
            "action": decision.get("action"),
            "terminal_evidence": decision.get("terminal_evidence"),
            "next_permitted_action": decision.get("next_permitted_action"),
        },
    }

    cfg = load_config(str(source), strict=True)["mutation"]
    corpus = aggregate_capacity_validation_shards(
        str(source), reports, cfg["paths"], cfg["exclude"], 256,
        candidate_sha=SOURCE_SHA, experiment_id=SOURCE_EXPERIMENT_ID,
    )
    if (
        corpus.get("status") != "enumerated"
        or corpus.get("corpus_digest") != "bec653555a4bdbd32159699f3c0bd3826403b326a287a5bf0cc97b157dee6ccf"
        or len(corpus.get("fingerprints", [])) != 52609
    ):
        raise ValueError("capacity recovery rebuilt corpus differs")
    manifests = [load_partition_manifest(manifests_dir / f"partition-{index}.json") for index in range(256)]
    if [manifest["digest"] for manifest in manifests] != corpus.get("manifest_digests"):
        raise ValueError("capacity recovery manifests differ")
    history = _read(Path(args.history))
    predictions = _read(Path(args.predictions))
    selection = build_capacity_validation_plan(
        str(source), cfg, corpus, manifests,
        experiment_id=SOURCE_EXPERIMENT_ID, revision=SOURCE_SHA,
        historical_measured_files=set(history["measured_files"]),
        historical_source=history["source"], prediction_seconds=predictions,
    )
    selected_files = sorted({unit["file"] for unit in selection["units"]})
    identity_process = subprocess.run(
        [str(source_python), "-I", "-c", """
import json,sys
from fettle.config import load_config
from fettle.mutation_test import _mapped_tests,_runtime_cache_identity
root=sys.argv[1]; files=json.loads(sys.argv[2]); cfg=load_config(root,strict=True)[\"mutation\"]
print(json.dumps({f:_runtime_cache_identity(root,[f],_mapped_tests(root,[f],cfg.get(\"test_mappings\",{})),cfg) for f in files},sort_keys=True))
""", str(source), json.dumps(selected_files)],
        check=True, capture_output=True, text=True, timeout=120,
        cwd=source, env={key: value for key, value in os.environ.items() if key != "PYTHONPATH"},
    )
    source_environments = json.loads(identity_process.stdout)
    if set(source_environments) != set(selected_files) or any(
        value is None for value in source_environments.values()
    ):
        raise ValueError("capacity recovery source environment identity is incomplete")
    plan = build_capacity_validation_plan(
        str(source), cfg, corpus, manifests,
        experiment_id=SOURCE_EXPERIMENT_ID, revision=SOURCE_SHA,
        historical_measured_files=set(history["measured_files"]),
        historical_source=history["source"], prediction_seconds=predictions,
        environment_identities=source_environments,
    )

    output.mkdir(parents=True, exist_ok=False)
    _write_json_atomic(output / "capacity-validation-corpus.json", corpus)
    _write_json_atomic(output / "capacity-validation-plan.json", plan)
    shutil.copytree(manifests_dir, output / "capacity-manifests")
    shutil.copy2(args.history, output / "capacity-history.json")
    shutil.copy2(args.predictions, output / "capacity-predictions.json")
    plan_sha = _sha(output / "capacity-validation-plan.json")
    source_executor_sha = _sha(source / "fettle/mutation_test.py")
    lineage = build_capacity_recovery_lineage(
        corpus, plan, artifact_pages, job_pages, _read(Path(args.accounting)),
        historical_evidence,
        controller_sha=args.controller_sha,
        source_executor_sha256=source_executor_sha,
        recovery_experiment_id=args.recovery_experiment_id,
        plan_file_sha256=plan_sha,
    )
    validate_capacity_recovery_lineage(
        lineage, corpus, plan, controller_sha=args.controller_sha,
        recovery_experiment_id=args.recovery_experiment_id,
        plan_file_sha256=plan_sha,
    )
    _write_json_atomic(output / "capacity-validation-recovery-lineage.json", lineage)
    (output / "capacity-validation-plan.sha256").write_text(
        f"{plan_sha}  capacity-validation-plan.json\n", encoding="utf-8",
    )
    inventory = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        inventory.append({"path": path.relative_to(output).as_posix(), "sha256": _sha(path)})
    _write_json_atomic(output / "capacity-validation-recovery-inventory.json", {
        "schema_version": "1", "kind": "capacity_validation_recovery_inventory",
        "source_candidate_sha": SOURCE_SHA, "controller_sha": args.controller_sha,
        "files": inventory,
    })
    print(json.dumps({"plan_sha256": plan_sha, "lineage_digest": lineage["digest"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
