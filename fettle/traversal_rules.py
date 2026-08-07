"""Deterministic bounded traversal contracts for change impact."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fettle.graph_types import canonical_digest
from fettle.overrides import OverrideRecord
from fettle.provider_contract import Completeness, ProviderFactSet, ProviderRunState, TrustClass


class TraversalState(str, Enum):
    COMPLETE = "complete"
    UNKNOWN = "unknown"
    LIMIT_REACHED = "limit_reached"


class ObligationResolution(str, Enum):
    UPDATED = "updated"
    VERIFIED_UNCHANGED = "verified_unchanged"
    NOT_APPLICABLE = "not_applicable"
    OVERRIDDEN = "overridden"


class RuleSurface(str, Enum):
    ADVISORY = "advisory"
    ENFORCING = "enforcing"


@dataclass(frozen=True, order=True)
class ObligationTemplate:
    obligation_type: str
    instruction: str

    def __post_init__(self) -> None:
        if not self.obligation_type or not self.instruction:
            raise ValueError("obligation template fields must be non-empty")


@dataclass(frozen=True)
class Obligation:
    id: str
    obligation_type: str
    target_id: str
    impact_closure_digest: str
    instruction: str

    @classmethod
    def create(
        cls,
        obligation_type: str,
        target_id: str,
        impact_closure_digest: str,
        instruction: str,
    ) -> Obligation:
        fields = (obligation_type, target_id, impact_closure_digest, instruction)
        if not all(fields):
            raise ValueError("obligation fields must be non-empty")
        identity = {
            "obligation_type": obligation_type,
            "target_id": target_id,
            "impact_closure_digest": impact_closure_digest,
            "instruction": instruction,
        }
        return cls(canonical_digest(identity), *fields)


@dataclass(frozen=True)
class ObligationDecision:
    id: str
    obligation_id: str
    resolution: ObligationResolution
    actor: str = ""
    reason: str = ""
    expiry: str = ""
    revision: str = ""
    policy_digest: str = ""
    graph_digest: str = ""
    evidence_id: str = ""
    override_id: str = ""

    @classmethod
    def create(
        cls,
        obligation_id: str,
        resolution: ObligationResolution,
        *,
        actor: str = "",
        reason: str = "",
        expiry: str = "",
        revision: str = "",
        policy_digest: str = "",
        graph_digest: str = "",
        evidence_id: str = "",
        override: OverrideRecord | None = None,
    ) -> ObligationDecision:
        if not obligation_id:
            raise ValueError("obligation id is required")
        if resolution == ObligationResolution.VERIFIED_UNCHANGED and not evidence_id:
            raise ValueError("verified unchanged requires evidence")
        if resolution == ObligationResolution.NOT_APPLICABLE and not reason:
            raise ValueError("not applicable requires a reason")
        if resolution == ObligationResolution.OVERRIDDEN:
            if override is None:
                raise ValueError("overridden resolution requires a canonical override record")
            expected_check = "change-integrity.obligation"
            expected_scope = f"obligations/{obligation_id}"
            if override.check_id != expected_check or override.scope != expected_scope:
                raise ValueError("override record does not match the obligation")
            actor = override.actor
            reason = override.reason
            expiry = override.expiry
            revision = override.revision
            policy_digest = override.policy_digest
            evidence_id = override.evidence_id
        override_id = override.override_id if override is not None else ""
        payload = {
            "obligation_id": obligation_id,
            "resolution": resolution,
            "actor": actor,
            "reason": reason,
            "expiry": expiry,
            "revision": revision,
            "policy_digest": policy_digest,
            "graph_digest": graph_digest,
            "evidence_id": evidence_id,
            "override_id": override_id,
        }
        return cls(canonical_digest(payload), obligation_id, resolution, actor, reason, expiry,
                   revision, policy_digest, graph_digest, evidence_id, override_id)


@dataclass(frozen=True, order=True)
class TraversalFact:
    source_id: str
    target_id: str
    edge_id: str
    edge_type: str
    role: str
    direction: str
    provider_id: str
    trust_class: TrustClass

    def __post_init__(self) -> None:
        required = (
            self.source_id, self.target_id, self.edge_id, self.edge_type,
            self.role, self.direction, self.provider_id,
        )
        if not all(required):
            raise ValueError("traversal fact fields must be non-empty")
        if self.direction not in ("in", "out"):
            raise ValueError("traversal fact direction must be in or out")


@dataclass(frozen=True)
class TraversalRule:
    rule_id: str
    version: int
    permitted_edge_types: tuple[str, ...]
    permitted_roles: tuple[str, ...]
    permitted_directions: tuple[str, ...]
    accepted_trust_classes: tuple[TrustClass, ...]
    required_provider_ids: tuple[str, ...]
    trigger_node_kinds: tuple[str, ...]
    change_classes: tuple[str, ...]
    impact_classifications: tuple[str, ...]
    obligation_templates: tuple[ObligationTemplate, ...]
    surfaces: tuple[RuleSurface, ...]
    recovery_command: str
    max_depth: int
    fanout_cap: int
    result_cap: int

    def __post_init__(self) -> None:
        if not self.rule_id or self.version <= 0:
            raise ValueError("rule id and positive version are required")
        if min(self.max_depth, self.fanout_cap, self.result_cap) <= 0:
            raise ValueError("traversal bounds must be positive")
        required_collections = (
            self.permitted_edge_types, self.permitted_roles, self.permitted_directions,
            self.accepted_trust_classes, self.required_provider_ids, self.trigger_node_kinds,
            self.change_classes, self.impact_classifications, self.surfaces,
        )
        if not all(required_collections) or not self.recovery_command:
            raise ValueError("traversal triggers, bounds, outputs, surface, and recovery are required")
        if not set(self.permitted_directions) <= {"in", "out"}:
            raise ValueError("permitted directions must be in or out")

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ImpactClosure:
    rule_digest: str
    changed_node_ids: tuple[str, ...]
    affected_node_ids: tuple[str, ...]
    traversed_edge_ids: tuple[str, ...]
    provider_fact_set_ids: tuple[str, ...]
    provider_completeness: tuple[tuple[str, str, str], ...]
    obligation_ids: tuple[str, ...]
    state: TraversalState
    reason: str
    digest: str


def traverse(
    changed_node_ids: tuple[str, ...],
    facts: tuple[TraversalFact, ...],
    provider_fact_sets: tuple[ProviderFactSet, ...],
    rule: TraversalRule,
) -> ImpactClosure:
    """Traverse accepted facts with deterministic cycle and limit handling."""
    changed = tuple(sorted(set(changed_node_ids)))
    fact_set_ids_by_provider: dict[str, set[str]] = {}
    for item in provider_fact_sets:
        fact_set_ids_by_provider.setdefault(item.provider_id, set()).add(item.id)
    conflicts = sorted(
        provider_id for provider_id, fact_set_ids in fact_set_ids_by_provider.items()
        if len(fact_set_ids) > 1
    )
    provider_ids = tuple(sorted({item.id for item in provider_fact_sets}))
    provider_completeness = tuple(sorted(
        (item.provider_id, item.run_state.value, item.completeness.value)
        for item in provider_fact_sets
    ))
    if conflicts:
        return _closure(rule, changed, (), (), provider_ids, provider_completeness, TraversalState.UNKNOWN,
                        "conflicting provider fact sets: " + ", ".join(conflicts))
    providers = {item.provider_id: item for item in provider_fact_sets}
    unavailable = [
        provider_id for provider_id in sorted(set(rule.required_provider_ids))
        if provider_id not in providers
        or providers[provider_id].run_state not in (ProviderRunState.PASS, ProviderRunState.VIOLATION)
        or providers[provider_id].completeness != Completeness.COMPLETE
    ]
    if unavailable:
        return _closure(rule, changed, (), (), provider_ids, provider_completeness, TraversalState.UNKNOWN,
                        "required providers unavailable or incomplete: " + ", ".join(unavailable))

    accepted = [
        fact for fact in sorted(set(facts))
        if fact.edge_type in rule.permitted_edge_types
        and fact.role in rule.permitted_roles
        and fact.direction in rule.permitted_directions
        and fact.trust_class in rule.accepted_trust_classes
        and fact.provider_id in providers
    ]
    adjacency: dict[str, list[TraversalFact]] = {}
    for fact in accepted:
        adjacency.setdefault(fact.source_id, []).append(fact)

    visited = set(changed)
    affected: set[str] = set()
    edge_ids: set[str] = set()
    frontier = list(changed)
    limit_reason = ""
    for _depth in range(rule.max_depth):
        next_frontier: list[str] = []
        for source_id in sorted(frontier):
            outgoing = adjacency.get(source_id, [])
            if len(outgoing) > rule.fanout_cap:
                limit_reason = f"fan-out cap exceeded at {source_id}"
                outgoing = outgoing[:rule.fanout_cap]
            for fact in outgoing:
                edge_ids.add(fact.edge_id)
                if fact.target_id in visited:
                    continue
                if len(affected) >= rule.result_cap:
                    limit_reason = "result cap reached"
                    break
                visited.add(fact.target_id)
                affected.add(fact.target_id)
                next_frontier.append(fact.target_id)
            if len(affected) >= rule.result_cap:
                break
        frontier = next_frontier
        if not frontier or len(affected) >= rule.result_cap:
            break
    if frontier and not limit_reason:
        limit_reason = "maximum depth reached"

    state = TraversalState.LIMIT_REACHED if limit_reason else TraversalState.COMPLETE
    return _closure(
        rule, changed, tuple(sorted(affected)), tuple(sorted(edge_ids)), provider_ids,
        provider_completeness, state, limit_reason,
    )


def _closure(
    rule: TraversalRule,
    changed: tuple[str, ...],
    affected: tuple[str, ...],
    edges: tuple[str, ...],
    providers: tuple[str, ...],
    provider_completeness: tuple[tuple[str, str, str], ...],
    state: TraversalState,
    reason: str,
) -> ImpactClosure:
    impact_context_digest = canonical_digest({
        "rule_digest": rule.digest,
        "changed_node_ids": changed,
        "affected_node_ids": affected,
        "traversed_edge_ids": edges,
        "provider_completeness": provider_completeness,
    })
    obligations = tuple(
        Obligation.create(template.obligation_type, target_id, impact_context_digest, template.instruction)
        for target_id in affected
        for template in rule.obligation_templates
    ) if state == TraversalState.COMPLETE else ()
    obligation_ids = tuple(sorted(obligation.id for obligation in obligations))
    payload = {
        "rule_digest": rule.digest,
        "changed_node_ids": changed,
        "affected_node_ids": affected,
        "traversed_edge_ids": edges,
        "provider_fact_set_ids": providers,
        "provider_completeness": provider_completeness,
        "obligation_ids": obligation_ids,
        "state": state,
        "reason": reason,
    }
    return ImpactClosure(
        rule.digest, changed, affected, edges, providers, provider_completeness,
        obligation_ids, state, reason, canonical_digest(payload),
    )
