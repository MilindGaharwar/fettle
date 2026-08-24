"""P53/SC1 — Canonical state-consistency contract schema (frozen).

Defines the immutable, versioned records for cross-view consistency
contracts per docs/state-consistency-implementation-plan.md §5–§6:

    ConsistencyContract, AdapterManifest, OperationEvidence, Observation,
    ConsistencyRun, ConsistencyOutcome

Canonical encoding follows the graph-contract rules: canonical JSON,
stable ordering, full SHA-256 identities, and rejection of unknown fields
where digest semantics could change. This package intentionally contains
NO execution code — runners arrive in SC3+ only after these contracts are
frozen and their adversarial fixtures pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from fettle.graph_types import canonical_digest

CONTRACT_SCHEMA = "fettle-consistency/v1"

VALID_MODELS = frozenset({"immediate", "eventual"})
VALID_COMPARATORS = frozenset({"normalized", "exact"})
VALID_OUTCOMES = frozenset({
    "converged", "divergent", "stale", "temporal_divergence",
    "not_applicable", "unknown", "tool_error", "config_error",
})

_ID_RE = re.compile(r"^[a-z0-9]+(?:[-_.][a-z0-9]+)*$")

# Keys that never participate in contract identity (runtime values/secrets).
_NON_IDENTITY_KEYS = frozenset({"redaction", "secrets", "generated_values"})


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    severity: str
    message: str
    fix: str


def _finding(message: str, fix: str, line: int = 1,
             severity: str = "ERROR") -> Finding:
    return Finding("state-consistency contract", line, severity, message, fix)


def _reject_unknown(section: str, present: set[str], allowed: set[str],
                    findings: list[Finding]) -> None:
    unknown = sorted(present - allowed)
    if unknown:
        findings.append(_finding(
            f"unknown key(s) in '{section}': {', '.join(unknown)}",
            "remove them; unknown fields could change digest semantics",
        ))


def _require(data: dict, key: str, findings: list[Finding]) -> Any:
    if key not in data:
        findings.append(_finding(f"missing required key '{key}'",
                                 f"add '{key}: ...'"))
        return None
    return data[key]


@dataclass(frozen=True)
class AdapterManifest:
    name: str
    kind: str  # commands | native_test
    argv_or_ref: str
    timeout_s: int
    inputs: tuple[str, ...] = ()
    implementation_digest: str = ""


@dataclass(frozen=True)
class ConsistencyContract:
    id: str
    title: str
    fact: str
    owner: str
    scope: tuple[str, ...]
    model: str
    deadline_ms: int
    poll_interval_ms: int
    observers: tuple[dict, ...]
    comparator_kind: str
    mutation_retry_safe: bool
    adapters: dict[str, AdapterManifest] = field(default_factory=dict)
    redaction_retain_values: bool = False
    digest: str = ""

    @staticmethod
    def compute_digest(data: dict) -> str:
        identity = {k: v for k, v in data.items()
                    if k not in _NON_IDENTITY_KEYS}
        return canonical_digest(identity)


def _validate_consistency_section(data: dict, findings: list[Finding]) -> tuple[str, int, int]:
    cons = data.get("consistency") or {}
    if not isinstance(cons, dict):
        findings.append(_finding("'consistency' must be a mapping",
                                 "set model/deadline/poll"))
        return "", 30_000, 1_000
    model = str(cons.get("model", ""))
    if model not in VALID_MODELS:
        findings.append(_finding(
            f"consistency.model {model!r} invalid",
            f"use one of {sorted(VALID_MODELS)}"))
    _reject_unknown("consistency", set(cons),
                    {"model", "deadline_ms", "poll_interval_ms"}, findings)
    return (model, int(cons.get("deadline_ms", 30_000)),
            int(cons.get("poll_interval_ms", 1_000)))


_ALLOWED_TOP = {
    "fettle-consistency", "id", "title", "scope", "fact", "owner",
    "consistency", "setup", "mutation", "canonical_read", "observers",
    "comparator", "cleanup", "redaction",
}


def _validate_header(data: dict, findings: list) -> str:
    if str(data.get("fettle-consistency", "")) != "v1":
        findings.append(_finding(
            "missing or unsupported 'fettle-consistency' version",
            "add 'fettle-consistency: v1'"))
    cid = str(_require(data, "id", findings) or "")
    if cid and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", cid):
        findings.append(_finding(f"invalid id {cid!r}", "use kebab-case"))
    _require(data, "fact", findings)
    _require(data, "owner", findings)
    return cid


def _validate_scope(data: dict, findings: list) -> tuple:
    scope = data.get("scope") or []
    if not isinstance(scope, list) or not scope:
        findings.append(_finding("'scope' must be a non-empty glob list",
                                 "add at least one governed path pattern"))
        return ()
    return tuple(scope)


def _validate_comparator(data: dict, findings: list) -> str:
    comparator = data.get("comparator") or {}
    if not isinstance(comparator, dict):
        comparator = {}
    kind = str(comparator.get("kind", ""))
    if kind not in VALID_COMPARATORS:
        findings.append(_finding(
            f"comparator.kind {kind!r} invalid",
            f"use one of {sorted(VALID_COMPARATORS)}"))
    return kind


def _validate_observers(data: dict, findings: list) -> list:
    observers = data.get("observers") or []
    if not isinstance(observers, list) or not observers:
        findings.append(_finding("'observers' must list at least one view",
                                 "add an observer with id/surface/adapter"))
        return []
    return [dict(o) for o in observers]


def _validate_unknown_top(data: dict, findings: list) -> None:
    unknown = sorted(set(data) - _ALLOWED_TOP)
    if unknown:
        findings.append(_finding(
            f"unknown top-level key(s): {', '.join(unknown)}",
            "remove them; freeze new keys via SC1 review first"))


def parse_contract(text: str, source: str = "<contract>") -> \
        tuple[ConsistencyContract | None, list[Finding]]:
    """Parse + validate one fettle-consistency YAML document."""
    import yaml

    findings: list[Finding] = []
    try:
        docs = [d for d in yaml.safe_load_all(text) if d is not None]
    except yaml.YAMLError as exc:
        return None, [_finding(f"invalid YAML: {exc}",
                               "fix the YAML syntax")]
    data = docs[0] if docs else {}
    if not isinstance(data, dict):
        return None, [_finding("contract must be a mapping",
                               "start with 'fettle-consistency: v1'")]

    if str(data.get("fettle-consistency", "")) != "v1":
        findings.append(_finding(
            "missing or unsupported 'fettle-consistency' version",
            "add 'fettle-consistency: v1'",
        ))
    cid = _validate_header(data, findings)
    scope = _validate_scope(data, findings)
    model, deadline_ms, poll_ms = _validate_consistency_section(data, findings)
    ckind = _validate_comparator(data, findings)
    observers = _validate_observers(data, findings)
    _validate_unknown_top(data, findings)

    if any(f.severity == "ERROR" for f in findings):
        return None, findings

    contract = ConsistencyContract(
        id=cid,
        title=str(data.get("title", "")),
        fact=str(data["fact"]),
        owner=str(data["owner"]),
        scope=tuple(scope),
        model=model,
        deadline_ms=deadline_ms,
        poll_interval_ms=poll_ms,
        observers=tuple(dict(o) for o in observers),
        comparator_kind=ckind,
        mutation_retry_safe=bool((data.get("mutation") or {})
                                 .get("retry_safe", True)),
        digest=ConsistencyContract.compute_digest(data),
    )
    return contract, findings


def lint_contract_text(text: str, source: str = "<contract>") -> list[dict]:
    """Findings as plain dicts, matching house lint shapes."""
    _contract, findings = parse_contract(text, source)
    return [f.__dict__ | {"rule": "CONSISTENCY_CONTRACT_LINT"}
            for f in findings]


TEMPLATE_V1 = """\
---
fettle-consistency: v1
id: <kebab-case-contract-id>
title: <human title>
scope:
  - "<governed/path/**>"
fact: <dotted.fact.path>
owner: <owning-service>
consistency:
  model: immediate            # or: eventual
  deadline_ms: 30000
  poll_interval_ms: 1000
mutation:
  adapter: <adapter-name>
  retry_safe: false
canonical_read:
  adapter: <adapter-name>
observers:
  - id: <view-name>
    surface: api              # api | cli | web | library
    adapter: <adapter-name>
comparator:
  kind: normalized            # or: exact
cleanup:
  adapter: <adapter-name>
redaction:
  retain_values: false
---
"""
