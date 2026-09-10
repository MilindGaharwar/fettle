"""Collect rank-blind contextual-impact cases from repository history."""

from __future__ import annotations

import json
import random
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

from fettle.contextual_impact import analyze_contextual_impact
from fettle.graph_builder import build_ephemeral_graph
from fettle.graph_cli import _resolve_seeds
from fettle.graph_types import canonical_digest

_REVIEWERS = (
    ("ai-reviewer", "ai", "general", 89),
    ("glm-reviewer", "ai", "glm", 47),
)


def collect_historical_cases(
    root: str,
    *,
    repository_name: str | None = None,
    source_prefixes: tuple[str, ...] = ("fettle/", "rules/", "specs/"),
    excluded_prefixes: tuple[str, ...] = (),
    analysis_subdirectory: str = ".",
    target_per_split: int = 20,
    history_limit: int = 250,
) -> tuple[dict, dict[str, dict]]:
    """Collect unlabeled cases and rank-blind packets from committed history."""
    repository = Path(root).resolve()
    name = repository_name or repository.name
    repository_digest = canonical_digest(_git(repository, "remote", "get-url", "origin"))
    revisions = _git_lines(
        repository, "log", "--no-merges", f"-{history_limit}", "--format=%H",
        "--", *(prefix.rstrip("/") for prefix in source_prefixes), "tests",
    )
    cases = []
    with tempfile.TemporaryDirectory(prefix="fettle-contextual-corpus-") as temporary:
        checkout = Path(temporary) / "checkout"
        for revision in revisions:
            changed_paths = _changed_paths(repository, revision)
            production_paths = [
                path for path in changed_paths
                if path.startswith(source_prefixes)
                and not path.startswith(excluded_prefixes)
            ]
            if not production_paths:
                continue
            _git(repository, "worktree", "add", "--detach", str(checkout), revision)
            try:
                analysis_root = checkout / analysis_subdirectory
                result = build_ephemeral_graph(str(analysis_root))
                if result["status"] != "completed":
                    continue
                graph = result["graph"]
                analysis_paths = [
                    _analysis_path(path, analysis_subdirectory) for path in production_paths
                ]
                seeds, unresolved = _resolve_seeds(graph, analysis_paths)
                if not seeds:
                    continue
                analysis = analyze_contextual_impact(graph, tuple(seeds))
                if analysis.state != "complete" or len(analysis.contextual) < 10:
                    continue
                provider_digest = canonical_digest(
                    sorted(item.fact_set_id for item in graph.provider_results)
                )
                id_to_key = {node_id: key for key, node_id in graph.stable_keys().items()}
                impact_universe = sorted(
                    id_to_key[node_id]
                    for node_id in graph.closure(seeds) - seeds
                    if node_id in id_to_key
                )
                actual_required = [item.stable_key for item in analysis.required]
                demotion_candidates = sorted(set(impact_universe) - set(actual_required))
                cases.append({
                    "id": f"{name}-{revision[:12]}",
                    "repository_digest": repository_digest,
                    "revision": revision,
                    "subject": _git(repository, "show", "-s", "--format=%s", revision),
                    "group": f"{name}/{_subsystem_group(production_paths, source_prefixes)}",
                    "changed_paths": production_paths,
                    "unresolved_paths": unresolved,
                    "graph_digest": graph.generation.digest,
                    "provider_digest": provider_digest,
                    "analysis_digest": analysis.analysis_digest,
                    "ranking_eligible": True,
                    "required_universe_digest": canonical_digest(impact_universe),
                    "required_universe_count": len(impact_universe),
                    "required_candidate_universe": sorted(set(actual_required)) + demotion_candidates[:20],
                    "actual_required": actual_required,
                    "required_targets": None,
                    "candidates": [{
                        "stable_key": item.stable_key,
                        "score": item.score,
                        "depth": item.paths[0].depth,
                        "relevance": None,
                        "rationale": None,
                        "reviews": [],
                    } for item in analysis.contextual],
                })
            finally:
                _git(repository, "worktree", "remove", "--force", str(checkout))
            if len(cases) >= target_per_split * 3:
                break
    selected = _assign_splits(cases, target_per_split=target_per_split)
    draft = {
        "schema_version": 2,
        "status": "awaiting_blind_review",
        "repository": name,
        "review_protocol": _review_protocol(),
        "target_per_split": target_per_split,
        "cases": selected,
    }
    return draft, _review_packets(selected)


def write_collection(draft: dict, packets: dict[str, dict], output_dir: str) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "draft.json").write_text(json.dumps(draft, indent=2) + "\n")
    for reviewer, packet in packets.items():
        (destination / f"review-{reviewer}.json").write_text(json.dumps(packet, indent=2) + "\n")


def combine_collections(drafts: list[dict], *, target_per_split: int) -> tuple[dict, dict[str, dict]]:
    """Combine preassigned repository drafts without weakening split isolation."""
    cases = [case for draft in drafts for case in draft.get("cases", [])]
    case_ids = [case.get("id") for case in cases]
    if len(case_ids) != len(set(case_ids)) or not all(case_ids):
        raise ValueError("combined contextual case ids must be unique and non-empty")
    groups: dict[str, str] = {}
    for case in cases:
        group = case.get("group")
        split = case.get("split")
        if not group or split not in {"development", "held_out"}:
            raise ValueError("combined contextual cases require split and group")
        if group in groups and groups[group] != split:
            raise ValueError(f"split leakage: group {group} appears in both splits")
        groups[group] = split
    counts = {
        split: sum(case["split"] == split for case in cases)
        for split in ("development", "held_out")
    }
    if any(count != target_per_split for count in counts.values()):
        raise ValueError(f"combined corpus requires exactly {target_per_split} cases per split")
    combined = {
        "schema_version": 2,
        "status": "awaiting_blind_review",
        "repositories": [draft.get("repository") for draft in drafts],
        "review_protocol": _review_protocol(),
        "target_per_split": target_per_split,
        "cases": sorted(cases, key=lambda case: (case["split"], case["id"])),
    }
    return combined, _review_packets(combined["cases"])


def apply_owner_decisions(reconciliation: dict, decisions: list[dict], *, owner: str) -> dict:
    """Apply an exact set of owner decisions to an unresolved reconciliation packet."""
    if not owner.strip():
        raise ValueError("reconciliation owner must be non-empty")
    result = deepcopy(reconciliation)
    unresolved = {}
    all_items = []
    for case in result.get("cases", []):
        for kind, field in (
            ("required", "required_disagreements"),
            ("contextual", "contextual_disagreements"),
        ):
            for item in case.get(field, []):
                all_items.append(item)
                if item.get("owner_decision") is None:
                    unresolved[(case["id"], kind, item["stable_key"])] = item

    supplied = {}
    for decision in decisions:
        key = (decision.get("case_id"), decision.get("kind"), decision.get("stable_key"))
        if key in supplied:
            raise ValueError(f"duplicate owner decision: {key}")
        value = decision.get("decision")
        rationale = decision.get("rationale")
        if (
            key[1] == "required" and type(value) is not bool
            or key[1] == "contextual" and value not in {"relevant", "irrelevant"}
            or key[1] not in {"required", "contextual"}
            or not isinstance(rationale, str) or not rationale.strip()
        ):
            raise ValueError(f"invalid owner decision: {key}")
        supplied[key] = decision
    if set(supplied) != set(unresolved):
        raise ValueError("owner decisions must exactly cover unresolved disagreements")

    for key, item in unresolved.items():
        decision = supplied[key]
        item["owner_decision"] = decision["decision"]
        item["owner_rationale"] = decision["rationale"].strip()
    remaining = sum(item.get("owner_decision") is None for item in all_items)
    result["owner"] = owner.strip()
    result["status"] = "reconciled" if not remaining else "awaiting_owner_reconciliation"
    result["summary"] = {
        "affected_cases": sum(
            bool(case.get("required_disagreements") or case.get("contextual_disagreements"))
            for case in result["cases"]
        ),
        "required_disagreements": sum(
            len(case.get("required_disagreements", [])) for case in result["cases"]
        ),
        "contextual_disagreements": sum(
            len(case.get("contextual_disagreements", [])) for case in result["cases"]
        ),
        "total_disagreements": len(all_items),
        "resolved": len(all_items) - remaining,
        "remaining": remaining,
    }
    return result


def freeze_reviewed_corpus(
    *, case_draft: dict, review_packets: list[dict], reconciliation: dict,
) -> dict:
    """Create a frozen v2 corpus from two blind reviews and owner reconciliation."""
    if reconciliation.get("status") != "reconciled":
        raise ValueError("owner reconciliation must be complete before freezing")
    reviewers = [packet.get("reviewer") for packet in review_packets]
    if len(reviewers) != 2 or len(set(reviewers)) != 2:
        raise ValueError("freezing requires exactly two distinct review packets")
    packet_cases = {
        reviewer: {case["id"]: case for case in packet.get("cases", [])}
        for reviewer, packet in zip(reviewers, review_packets, strict=True)
    }
    decisions = {}
    for case in reconciliation.get("cases", []):
        for kind, field in (
            ("required", "required_disagreements"),
            ("contextual", "contextual_disagreements"),
        ):
            for item in case.get(field, []):
                value = item.get("owner_decision")
                rationale = item.get("owner_rationale")
                key = (case["id"], kind, item["stable_key"])
                if key in decisions:
                    raise ValueError(f"duplicate reconciled disagreement: {key}")
                if (
                    kind == "required" and type(value) is not bool
                    or kind == "contextual" and value not in {"relevant", "irrelevant"}
                    or not isinstance(rationale, str) or not rationale.strip()
                ):
                    raise ValueError("every disagreement requires an owner decision and rationale")
                decisions[key] = (value, rationale.strip())

    cases = []
    used_decisions = set()
    for source_case in case_draft.get("cases", []):
        case_id = source_case["id"]
        required_reviews = {}
        contextual_reviews = {}
        for reviewer in reviewers:
            try:
                reviewed = packet_cases[reviewer][case_id]
            except KeyError as exc:
                raise ValueError(f"{case_id}: missing review from {reviewer}") from exc
            required_reviews[reviewer] = {
                item["stable_key"]: item for item in reviewed.get("required_candidates", [])
            }
            contextual_reviews[reviewer] = {
                item["stable_key"]: item for item in reviewed.get("contextual_candidates", [])
            }

        required_targets = []
        for key in source_case["required_candidate_universe"]:
            reviews = [required_reviews[reviewer].get(key) for reviewer in reviewers]
            if any(not item or type(item.get("required")) is not bool or not item.get("rationale")
                   for item in reviews):
                raise ValueError(f"{case_id}: incomplete required review for {key}")
            values = [item["required"] for item in reviews]
            if values[0] == values[1]:
                decision = values[0]
            else:
                try:
                    decision_key = (case_id, "required", key)
                    decision = decisions[decision_key][0]
                except KeyError as exc:
                    raise ValueError(f"{case_id}: unreconciled required disagreement for {key}") from exc
                used_decisions.add(decision_key)
            if decision:
                required_targets.append(key)

        candidates = []
        for candidate in source_case["candidates"]:
            key = candidate["stable_key"]
            reviews = [contextual_reviews[reviewer].get(key) for reviewer in reviewers]
            if any(
                not item or item.get("relevance") not in {"relevant", "irrelevant"}
                or not item.get("rationale") for item in reviews
            ):
                raise ValueError(f"{case_id}: incomplete contextual review for {key}")
            values = [item["relevance"] for item in reviews]
            if values[0] == values[1]:
                relevance = values[0]
                rationale = f"Both blinded reviewers agreed: {reviews[0]['rationale']}"
            else:
                try:
                    decision_key = (case_id, "contextual", key)
                    relevance, rationale = decisions[decision_key]
                except KeyError as exc:
                    raise ValueError(f"{case_id}: unreconciled contextual disagreement for {key}") from exc
                used_decisions.add(decision_key)
            candidates.append({
                **candidate,
                "relevance": relevance,
                "rationale": rationale,
                "reviews": [
                    {
                        "reviewer": reviewer,
                        "relevance": item["relevance"],
                        "rationale": item["rationale"],
                    }
                    for reviewer, item in zip(reviewers, reviews, strict=True)
                ],
            })
        oracle_digest = canonical_digest({
            "required_targets": sorted(required_targets),
            "contextual_relevance": sorted(
                (item["stable_key"], item["relevance"]) for item in candidates
            ),
        })
        relevance_counts = {
            value: sum(item["relevance"] == value for item in candidates)
            for value in ("relevant", "irrelevant")
        }
        cases.append({
            **source_case,
            "ranking_eligible": (
                source_case.get("ranking_eligible", False)
                and len(candidates) >= 10
                and relevance_counts["relevant"] >= 2
                and relevance_counts["irrelevant"] >= 2
            ),
            "oracle_digest": oracle_digest,
            "required_targets": sorted(required_targets),
            "candidates": candidates,
        })
    if used_decisions != set(decisions):
        raise ValueError("reconciliation must exactly match reviewer disagreements")

    protocol = case_draft["review_protocol"]
    return {
        "schema_version": 2,
        "status": "frozen",
        "repositories": case_draft.get("repositories", []),
        "review": {
            "reviewers": reviewers,
            "reviewer_roles": protocol["reviewer_roles"],
            "reviewer_model_classes": protocol["reviewer_model_classes"],
            "ai_independence": protocol["ai_independence"],
            "disagreement_resolution": protocol["disagreement_resolution"],
            "labeling": protocol["labeling"],
            "minimum_ranking_cases_per_split": case_draft["target_per_split"],
            "minimum_candidates_per_case": 10,
            "minimum_relevant_per_case": 2,
            "minimum_irrelevant_per_case": 2,
            "precision_at_10": (
                "relevant candidates in the first 10 divided by candidates returned in the first 10"
            ),
            "promotion_threshold": (
                "at least 10% relative held-out precision gain with 100% required-impact recall"
            ),
        },
        "cases": cases,
    }


def _assign_splits(cases: list[dict], *, target_per_split: int) -> list[dict]:
    by_group: dict[str, list[dict]] = {}
    for case in cases:
        by_group.setdefault(case["group"], []).append(case)
    selected = {"development": [], "held_out": []}
    group_split: dict[str, str] = {}
    for group, grouped_cases in sorted(by_group.items(), key=lambda item: (-len(item[1]), item[0])):
        split = min(selected, key=lambda name: (len(selected[name]), name))
        group_split[group] = split
        selected[split].extend(grouped_cases)
    result = []
    for split in ("development", "held_out"):
        for case in selected[split][:target_per_split]:
            result.append({**case, "split": split})
    if any(len(selected[split][:target_per_split]) < target_per_split for split in selected):
        raise ValueError("repository history did not yield enough leakage-safe cases")
    assert all(group_split[case["group"]] == case["split"] for case in result)
    return sorted(result, key=lambda case: (case["split"], case["id"]))


def _review_packets(cases: list[dict]) -> dict[str, dict]:
    packets = {}
    for reviewer, role, model_class, seed in _REVIEWERS:
        randomizer = random.Random(seed)
        packet_cases = []
        for case in cases:
            candidates = [item["stable_key"] for item in case["candidates"]]
            randomizer.shuffle(candidates)
            required = list(case["required_candidate_universe"])
            randomizer.shuffle(required)
            packet_cases.append({
                "id": case["id"],
                "revision": case["revision"],
                "subject": case["subject"],
                "changed_paths": case["changed_paths"],
                "required_universe_digest": case["required_universe_digest"],
                "required_universe_count": case["required_universe_count"],
                "required_candidates": [
                    {"stable_key": key, "required": None, "rationale": None}
                    for key in required
                ],
                "contextual_candidates": [
                    {"stable_key": key, "relevance": None, "rationale": None}
                    for key in candidates
                ],
            })
        packets[reviewer] = {
            "schema_version": 1,
            "reviewer": reviewer,
            "reviewer_role": role,
            "reviewer_model_class": model_class,
            "independence": "fresh-context-blinded" if role == "ai" else "owner-review",
            "instructions": (
                "Review candidates independently. Do not inspect draft.json, ranking scores, "
                "or the other packet. The AI reviewer must use a fresh context with access only "
                "to this packet and the referenced repository revisions."
            ),
            "cases": packet_cases,
        }
    return packets


def _review_protocol() -> dict:
    return {
        "reviewers": [reviewer for reviewer, _role, _model, _seed in _REVIEWERS],
        "reviewer_roles": {
            reviewer: role for reviewer, role, _model, _seed in _REVIEWERS
        },
        "reviewer_model_classes": {
            reviewer: model for reviewer, _role, model, _seed in _REVIEWERS
        },
        "labeling": "blind-randomized",
        "ai_independence": "fresh-context-blinded",
        "disagreement_resolution": "owner-reconciles-after-both-ai-reviews",
    }


def _changed_paths(root: Path, revision: str) -> list[str]:
    return _git_lines(
        root, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", revision,
    )


def _analysis_path(path: str, analysis_subdirectory: str) -> str:
    prefix = analysis_subdirectory.strip("/")
    if not prefix or prefix == ".":
        return path
    return path.removeprefix(f"{prefix}/")


def _subsystem_group(
    paths: list[str], source_prefixes: tuple[str, ...] = ("fettle/",),
) -> str:
    first = sorted(paths)[0]
    parts = Path(first).parts
    for prefix in source_prefixes:
        if first.startswith(prefix):
            relative = Path(first.removeprefix(prefix))
            if len(relative.parts) > 1:
                return f"{prefix.rstrip('/')}/{relative.parts[0]}"
            return f"{prefix.rstrip('/')}/{relative.stem.split('_', 1)[0]}"
    return "/".join(parts[:2])


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), *args), capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _git_lines(root: Path, *args: str) -> list[str]:
    return [line for line in _git(root, *args).splitlines() if line]
