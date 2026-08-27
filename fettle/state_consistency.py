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
from pathlib import Path
from typing import Any

from fettle.graph_types import canonical_digest, normalize_path

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
    kind: str
    argv: tuple[str, ...]
    cwd: str
    timeout_s: int
    env: tuple[str, ...] = ()
    output: str = "json-v1"
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
    setup_adapter: str = ""
    mutation_adapter: str = ""
    canonical_read_adapter: str = ""
    cleanup_adapter: str = ""
    adapters: dict[str, AdapterManifest] = field(default_factory=dict)
    redaction_retain_values: bool = False
    digest: str = ""

    @staticmethod
    def compute_digest(data: dict) -> str:
        identity = {k: v for k, v in data.items()
                    if k not in _NON_IDENTITY_KEYS}
        return canonical_digest(identity)


@dataclass(frozen=True)
class DiscoveredContract:
    path: Path
    contract: ConsistencyContract


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
    deadline = cons.get("deadline_ms", 30_000)
    poll_interval = cons.get("poll_interval_ms", 1_000)
    if (not isinstance(deadline, int) or isinstance(deadline, bool)
            or not 1 <= deadline <= 300_000):
        findings.append(_finding(
            "consistency.deadline_ms must be between 1 and 300000",
            "set a bounded deadline in milliseconds",
        ))
        deadline = 30_000
    if (not isinstance(poll_interval, int) or isinstance(poll_interval, bool)
            or not 1 <= poll_interval <= deadline):
        findings.append(_finding(
            "consistency.poll_interval_ms must be between 1 and deadline_ms",
            "set a positive polling interval no greater than the deadline",
        ))
        poll_interval = min(1_000, deadline)
    return model, deadline, poll_interval


_ALLOWED_TOP = {
    "fettle-consistency", "id", "title", "scope", "fact", "owner",
    "consistency", "setup", "mutation", "canonical_read", "observers",
    "comparator", "cleanup", "redaction", "adapters",
}

_ADAPTER_KEYS = {"kind", "argv", "cwd", "env", "timeout_s", "output"}
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _phase_adapter(data: dict, phase: str, findings: list[Finding]) -> str:
    value = data.get(phase)
    if value is None:
        return ""
    if not isinstance(value, dict):
        findings.append(_finding(f"'{phase}' must be a mapping",
                                 f"set {phase}.adapter to a named adapter"))
        return ""
    _reject_unknown(phase, set(value),
                    {"adapter", "retry_safe"} if phase == "mutation" else {"adapter"},
                    findings)
    adapter = value.get("adapter", "")
    if not isinstance(adapter, str) or not _ID_RE.fullmatch(adapter):
        findings.append(_finding(
            f"{phase}.adapter must be a stable adapter name",
            f"set {phase}.adapter to a name from 'adapters'",
        ))
        return ""
    return adapter


def _validate_adapter_path(value: object, name: str, findings: list[Finding]) -> str:
    if not isinstance(value, str):
        findings.append(_finding(f"adapter {name}.cwd must be a string",
                                 "use '.' or a repository-relative directory"))
        return ""
    if value == ".":
        return value
    try:
        return normalize_path(value)
    except (TypeError, ValueError):
        findings.append(_finding(
            f"adapter {name}.cwd must be repository-relative",
            "remove absolute paths and '..' traversal",
        ))
        return ""


def _validate_adapters(data: dict, findings: list[Finding]) -> dict[str, AdapterManifest]:
    raw = data.get("adapters") or {}
    if not isinstance(raw, dict):
        findings.append(_finding("'adapters' must be a mapping",
                                 "map each adapter name to its command manifest"))
        return {}
    adapters: dict[str, AdapterManifest] = {}
    for name, value in sorted(raw.items()):
        if not isinstance(name, str) or not _ID_RE.fullmatch(name):
            findings.append(_finding(f"invalid adapter name {name!r}",
                                     "use letters, digits, dots, dashes, or underscores"))
            continue
        if not isinstance(value, dict):
            findings.append(_finding(f"adapter {name!r} must be a mapping",
                                     "declare kind, argv, timeout_s, and output"))
            continue
        _reject_unknown(f"adapters.{name}", set(value), _ADAPTER_KEYS, findings)
        kind = value.get("kind")
        if kind != "command":
            findings.append(_finding(f"adapter {name}.kind must be 'command'",
                                     "use an argv-based repository command"))
        argv = value.get("argv")
        if (not isinstance(argv, list) or not argv or len(argv) > 64
                or not all(isinstance(item, str) and item for item in argv)):
            findings.append(_finding(
                f"adapter {name}.argv must be a string array with at most 64 items",
                "use explicit argv items; shell strings are unsupported",
            ))
            argv = []
        env = value.get("env", [])
        if (not isinstance(env, list)
                or not all(isinstance(item, str) and _ENV_NAME_RE.fullmatch(item)
                           for item in env)):
            findings.append(_finding(
                f"adapter {name}.env must contain environment variable names only",
                "list names such as FETTLE_SUBJECT_ID, never values or assignments",
            ))
            env = []
        timeout = value.get("timeout_s", 30)
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 300:
            findings.append(_finding(f"adapter {name}.timeout_s must be between 1 and 300",
                                     "set a bounded integer timeout"))
            timeout = 30
        output = value.get("output", "json-v1")
        if output != "json-v1":
            findings.append(_finding(f"adapter {name}.output must be 'json-v1'",
                                     "emit one versioned JSON observation"))
        cwd = _validate_adapter_path(value.get("cwd", "."), name, findings)
        adapters[name] = AdapterManifest(
            name=name, kind=str(kind or ""), argv=tuple(argv), cwd=cwd,
            timeout_s=timeout, env=tuple(env), output=str(output),
            implementation_digest=canonical_digest(value),
        )
    return adapters


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
    if len(observers) > 64:
        findings.append(_finding("'observers' must contain at most 64 observers",
                                 "split the contract into bounded runs"))
        return []
    normalized = []
    seen: set[str] = set()
    for observer in observers:
        if not isinstance(observer, dict):
            findings.append(_finding("each observer must be a mapping",
                                     "declare observer id, surface, and adapter"))
            continue
        _reject_unknown("observer", set(observer), {"id", "surface", "adapter"}, findings)
        observer_id = observer.get("id")
        adapter = observer.get("adapter")
        if not isinstance(observer_id, str) or not _ID_RE.fullmatch(observer_id):
            findings.append(_finding("observer.id must be a stable name",
                                     "use letters, digits, dots, dashes, or underscores"))
            continue
        if observer_id in seen:
            findings.append(_finding(f"duplicate observer id {observer_id!r}",
                                     "give every observer a unique id"))
        seen.add(observer_id)
        if not isinstance(adapter, str) or not _ID_RE.fullmatch(adapter):
            findings.append(_finding(f"observer {observer_id}.adapter must be a stable name",
                                     "reference a name from 'adapters'"))
        normalized.append(dict(observer))
    return normalized


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
    setup_adapter = _phase_adapter(data, "setup", findings)
    mutation_adapter = _phase_adapter(data, "mutation", findings)
    canonical_read_adapter = _phase_adapter(data, "canonical_read", findings)
    cleanup_adapter = _phase_adapter(data, "cleanup", findings)
    adapters = _validate_adapters(data, findings)
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
        setup_adapter=setup_adapter,
        mutation_adapter=mutation_adapter,
        canonical_read_adapter=canonical_read_adapter,
        cleanup_adapter=cleanup_adapter,
        adapters=adapters,
        redaction_retain_values=bool((data.get("redaction") or {})
                                     .get("retain_values", False)),
        digest=ConsistencyContract.compute_digest(data),
    )
    return contract, findings


def validate_executable_contract(contract: ConsistencyContract) -> list[Finding]:
    """Validate execution prerequisites without running repository code."""
    findings: list[Finding] = []
    required = {
        "mutation adapter": contract.mutation_adapter,
        "canonical-read adapter": contract.canonical_read_adapter,
        "cleanup adapter": contract.cleanup_adapter,
    }
    for label, adapter in required.items():
        if not adapter:
            findings.append(_finding(f"missing {label}",
                                     "declare the phase's named adapter"))
        elif adapter not in contract.adapters:
            findings.append(_finding(f"{label} {adapter!r} has no manifest",
                                     "add it to the contract's 'adapters' map"))
    if contract.setup_adapter and contract.setup_adapter not in contract.adapters:
        findings.append(_finding(
            f"setup adapter {contract.setup_adapter!r} has no manifest",
            "add it to the contract's 'adapters' map",
        ))
    for observer in contract.observers:
        adapter = observer.get("adapter", "")
        if adapter not in contract.adapters:
            findings.append(_finding(
                f"observer adapter {adapter!r} has no manifest",
                "add it to the contract's 'adapters' map",
            ))
    return findings


def discover_contracts(root: str | Path) -> tuple[list[DiscoveredContract], list[Finding]]:
    """Discover marked contracts deterministically without executing them."""
    root_path = Path(root)
    discovered: list[DiscoveredContract] = []
    findings: list[Finding] = []
    by_id: dict[str, Path] = {}
    for path in sorted(root_path.rglob("*.md")):
        if any(part in {".git", ".venv", "node_modules"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines or not (
            lines[0].startswith("fettle-consistency:")
            or len(lines) > 1 and lines[0] == "---"
            and lines[1].startswith("fettle-consistency:")
        ):
            continue
        contract, parsed_findings = parse_contract(text, str(path.relative_to(root_path)))
        findings.extend(parsed_findings)
        if contract is None:
            continue
        previous = by_id.get(contract.id)
        if previous is not None:
            findings.append(_finding(
                f"duplicate contract id {contract.id!r} in {previous} and {path}",
                "give every consistency contract a unique id",
            ))
            continue
        by_id[contract.id] = path
        discovered.append(DiscoveredContract(path, contract))
    return discovered, findings


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
adapters:
  <adapter-name>:
    kind: command
    argv: ["<repository-command>"]
    cwd: "."
    env: ["FETTLE_SUBJECT_ID"]
    timeout_s: 30
    output: json-v1
redaction:
  retain_values: false
---
"""
