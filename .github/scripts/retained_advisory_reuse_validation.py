#!/usr/bin/env python3
"""Validate legacy advisory reports against an exact source tree, offline only."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from fettle.config import load_config
from fettle.mutation_test import (
    _canonical_digest,
    aggregate_shards,
    build_advisory_reuse_identity,
    load_partition_manifest,
    prepare_advisory_reuse,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _load_reports(path: Path) -> list[dict]:
    return [
        json.loads(report.read_text(encoding="utf-8"))
        for report in sorted(path.rglob("mutation-report.json"))
    ]


def validate_retained_reuse(
    source_root: Path,
    manifest_root: Path,
    report_root: Path,
    evidence_index_path: Path,
    *,
    source_run_id: str,
    source_run_attempt: str,
) -> dict:
    """Prove that an exact legacy corpus can migrate into identity-bound reuse."""
    evidence_index = json.loads(evidence_index_path.read_text(encoding="utf-8"))
    source_revision = evidence_index.get("revision")
    if (
        not isinstance(source_revision, str)
        or not re.fullmatch(r"[0-9a-f]{40}", source_revision)
        or _git(source_root, "rev-parse", "HEAD") != source_revision
        or _git(source_root, "status", "--porcelain")
    ):
        raise ValueError("source checkout is not the clean exact retained revision")

    manifests = [
        load_partition_manifest(path)
        for path in sorted(
            manifest_root.glob("partition-*.json"),
            key=lambda path: int(path.stem.split("-")[1]),
        )
    ]
    reports = _load_reports(report_root)
    shard_count = len(manifests)
    expected_indexes = list(range(shard_count))
    if (
        shard_count < 1
        or [manifest.get("shard_index") for manifest in manifests] != expected_indexes
        or sorted(report.get("shard_index") for report in reports) != expected_indexes
        or any(manifest.get("revision") != source_revision for manifest in manifests)
        or any(report.get("revision") != source_revision for report in reports)
    ):
        raise ValueError("retained manifests and reports do not form one complete corpus")

    mutation = load_config(str(source_root))["mutation"]
    migrated_reports = []
    for manifest, report in zip(manifests, sorted(reports, key=lambda item: item["shard_index"])):
        if report.get("manifest_digest") != manifest.get("digest"):
            raise ValueError("retained report does not bind its manifest")
        migrated_reports.append(
            {
                **report,
                "advisory_reuse_identity": build_advisory_reuse_identity(
                    str(source_root), manifest, mutation
                ),
            }
        )

    with tempfile.TemporaryDirectory(prefix="fettle-retained-reuse-") as temporary:
        docs_root = Path(temporary) / "repo"
        shutil.copytree(source_root, docs_root, ignore=shutil.ignore_patterns(".git"))
        _git(docs_root, "init", "-q")
        _git(docs_root, "config", "user.email", "reuse-proof@example.invalid")
        _git(docs_root, "config", "user.name", "Reuse Proof")
        _git(docs_root, "add", ".")
        _git(docs_root, "commit", "-qm", "retained source")
        docs = docs_root / "docs"
        docs.mkdir(exist_ok=True)
        (docs / "retained-reuse-proof.md").write_text("offline reuse proof\n")
        _git(docs_root, "add", "docs/retained-reuse-proof.md")
        _git(docs_root, "commit", "-qm", "docs: validate retained reuse")
        docs_revision = _git(docs_root, "rev-parse", "HEAD")

        current_manifests = deepcopy(manifests)
        for manifest in current_manifests:
            manifest["revision"] = docs_revision
            manifest.pop("digest", None)
            manifest["digest"] = _canonical_digest(manifest)
        current_mutation = load_config(str(docs_root))["mutation"]
        reuse = prepare_advisory_reuse(
            str(docs_root),
            current_mutation,
            current_manifests,
            migrated_reports,
            source_run_id=source_run_id,
            source_run_attempt=source_run_attempt,
        )
        aggregate = aggregate_shards(
            str(docs_root),
            reuse["reports"],
            sorted({file for manifest in current_manifests for file in manifest["files"]}),
            [],
            shard_count,
            current_mutation["score_target"],
            current_mutation["test_mappings"],
            current_mutation,
            current_manifests,
            advisory=True,
        )

    expected_counts = evidence_index.get("headline_outcomes")
    outcome_fields = ("killed", "survived", "timeout", "suspicious", "untested", "skipped")
    observed_counts = {field: aggregate.get(field) for field in outcome_fields}
    if (
        reuse.get("matrix") != {"shard": []}
        or reuse.get("reused_shards") != expected_indexes
        or aggregate.get("status") != "completed"
        or aggregate.get("passed") is not True
        or aggregate.get("aggregation_mode") != "advisory"
        or aggregate.get("qualification_eligible") is not False
        or aggregate.get("reused_shards") != expected_indexes
        or not isinstance(expected_counts, dict)
        or observed_counts != {field: expected_counts.get(field) for field in outcome_fields}
    ):
        raise ValueError(
            "retained advisory reuse proof did not satisfy its contract: "
            + json.dumps({
                "reuse_status": reuse.get("status"),
                "reuse_count": len(reuse.get("reused_shards", [])),
                "matrix": reuse.get("matrix"),
                "aggregate": aggregate,
                "expected_counts": expected_counts,
                "observed_counts": observed_counts,
            }, default=str)[:4000]
        )
    return {
        "schema_version": "1",
        "status": "completed",
        "passed": True,
        "source_run_id": source_run_id,
        "source_run_attempt": source_run_attempt,
        "source_revision": source_revision,
        "docs_only_revision": docs_revision,
        "shard_count": shard_count,
        "reused_shards": shard_count,
        "reexecuted_shards": 0,
        "counts": observed_counts,
        "aggregation_mode": "advisory",
        "qualification_eligible": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--evidence-index", type=Path, required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-attempt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate_retained_reuse(
            args.source_root,
            args.manifests,
            args.reports,
            args.evidence_index,
            source_run_id=args.source_run_id,
            source_run_attempt=args.source_run_attempt,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema_version": "1", "status": "unknown", "passed": False, "message": str(exc)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "completed" and result.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
