"""Provider declarations and fail-closed fact-set contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from fettle.graph_types import canonical_digest, normalize_text


class TrustClass(str, Enum):
    AUTHORITATIVE = "authoritative"
    DERIVED = "derived"
    HEURISTIC = "heuristic"
    EXTERNAL = "external"


class ProviderRunState(str, Enum):
    PASS = "pass"
    VIOLATION = "violation"
    TOOL_ERROR = "tool_error"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Completeness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProviderLimits:
    max_runtime_ms: int
    max_files: int
    max_bytes: int
    max_facts: int
    max_nodes: int
    max_edges: int
    max_incidences: int
    max_attribute_bytes: int
    max_diagnostics: int
    max_output_bytes: int

    def __post_init__(self) -> None:
        if min(
            self.max_runtime_ms, self.max_files, self.max_bytes, self.max_facts,
            self.max_nodes, self.max_edges, self.max_incidences, self.max_attribute_bytes,
            self.max_diagnostics, self.max_output_bytes,
        ) <= 0:
            raise ValueError("all provider limits must be positive")


@dataclass(frozen=True)
class ProviderDeclaration:
    provider_id: str
    version: str
    implementation_digest: str
    owner: str
    trust_class: TrustClass
    deterministic: bool
    artifact_kinds: tuple[str, ...]
    languages: tuple[str, ...]
    workspace_types: tuple[str, ...]
    input_classes: tuple[str, ...]
    configuration_inputs: tuple[str, ...]
    environment_allowlist: tuple[str, ...]
    output_node_types: tuple[str, ...]
    output_edge_types: tuple[str, ...]
    output_incidence_types: tuple[str, ...]
    applicability_rule: str
    canonical_output_rule: str
    invalidation_rule: str
    tombstone_behavior: str
    limits: ProviderLimits

    def __post_init__(self) -> None:
        required = (
            self.provider_id, self.version, self.implementation_digest, self.owner,
            self.applicability_rule, self.canonical_output_rule, self.invalidation_rule,
            self.tombstone_behavior,
        )
        if not all(normalize_text(value) for value in required):
            raise ValueError("provider declaration fields must be non-empty")
        if not self.artifact_kinds or not self.languages or not self.workspace_types:
            raise ValueError("provider applicability kinds, languages, and workspaces are required")
        if not self.input_classes:
            raise ValueError("provider input classes are required")
        if not (self.output_node_types or self.output_edge_types or self.output_incidence_types):
            raise ValueError("provider output types are required")
        for field_name in (
            "artifact_kinds", "languages", "workspace_types", "input_classes",
            "configuration_inputs", "environment_allowlist", "output_node_types",
            "output_edge_types", "output_incidence_types",
        ):
            values = getattr(self, field_name)
            object.__setattr__(self, field_name, tuple(sorted(set(values))))

    @property
    def digest(self) -> str:
        return canonical_digest(self)


@dataclass(frozen=True)
class ProviderFactSet:
    provider_id: str
    provider_version: str
    implementation_digest: str
    config_digest: str
    input_digest: str
    run_state: ProviderRunState
    completeness: Completeness
    completeness_scope: tuple[str, ...]
    deterministic: bool
    trust_class: TrustClass
    fact_ids: tuple[str, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        required = (
            self.provider_id, self.provider_version, self.implementation_digest,
            self.config_digest, self.input_digest,
        )
        if not all(normalize_text(value) for value in required):
            raise ValueError("provider fact-set identity fields must be non-empty")
        if self.run_state == ProviderRunState.PASS and self.completeness != Completeness.COMPLETE:
            raise ValueError("a successful provider fact set must be complete")
        if self.run_state in (ProviderRunState.TOOL_ERROR, ProviderRunState.UNKNOWN, ProviderRunState.NOT_APPLICABLE):
            if self.completeness == Completeness.COMPLETE or self.fact_ids:
                raise ValueError("a non-success provider cannot be complete or emit facts")
        if self.run_state == ProviderRunState.NOT_APPLICABLE and self.fact_ids:
            raise ValueError("a non-applicable provider cannot emit facts")
        if self.run_state in (ProviderRunState.TOOL_ERROR, ProviderRunState.UNKNOWN) and not self.message:
            raise ValueError("failed or unknown provider results require a message")
        object.__setattr__(self, "fact_ids", tuple(sorted(set(self.fact_ids))))
        object.__setattr__(self, "completeness_scope", tuple(sorted(set(self.completeness_scope))))

    @property
    def id(self) -> str:
        return canonical_digest(self)
