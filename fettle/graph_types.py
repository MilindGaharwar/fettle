"""Canonical immutable records for change-integrity graphs."""

from __future__ import annotations

import hashlib
import json
import posixpath
import unicodedata
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, Mapping

GRAPH_SCHEMA_VERSION = 1
CANONICALIZATION_VERSION = 1


def normalize_text(value: str) -> str:
    """Normalize graph strings without changing their case."""
    if not isinstance(value, str):
        raise TypeError("canonical strings must be str")
    return unicodedata.normalize("NFC", value)


def normalize_path(value: str) -> str:
    """Return a portable repository-relative path."""
    value = normalize_text(value).replace("\\", "/")
    normalized = posixpath.normpath(value)
    if normalized in ("", ".") or normalized.startswith("/") or normalized == ".." or normalized.startswith("../"):
        raise ValueError("path must be repository-relative and non-empty")
    return normalized


def _canonical_value(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        raise TypeError("floats are not permitted in canonical graph data")
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("canonical object keys must be strings")
        normalized_items = [(normalize_text(key), item) for key, item in value.items()]
        normalized_keys = [key for key, _item in normalized_items]
        if len(set(normalized_keys)) != len(normalized_keys):
            raise ValueError("canonical object keys normalize to the same value")
        return {
            key: _canonical_value(item)
            for key, item in sorted(normalized_items, key=lambda pair: pair[0].encode("utf-8"))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Encode supported values as stable UTF-8 JSON."""
    return json.dumps(
        _canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def canonical_attributes(attributes: Mapping[str, Any] | None = None) -> str:
    if attributes is None:
        attributes = {}
    if not isinstance(attributes, Mapping):
        raise TypeError("attributes must be an object")
    return canonical_json(attributes)


def _validate_canonical_object(value: str) -> None:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("attributes_json must be a canonical JSON object") from exc
    if not isinstance(decoded, dict) or canonical_json(decoded) != value:
        raise ValueError("attributes_json must be a canonical JSON object")


class SourceSnapshotClass(str, Enum):
    COMMITTED = "committed"
    WORKING = "working"


class SourceObjectType(str, Enum):
    FILE = "file"
    SYMLINK = "symlink"
    GITLINK = "gitlink"
    TOMBSTONE = "tombstone"


class SourcePathClass(str, Enum):
    TRACKED = "tracked"
    UNTRACKED = "untracked"
    IGNORED_SEMANTIC = "ignored_semantic"


class SubmoduleHandling(str, Enum):
    GITLINK_ONLY = "gitlink_only"
    RECURSIVELY_MANIFESTED = "recursively_manifested"
    DECLARED_INCOMPLETE = "declared_incomplete"


class FreshnessState(str, Enum):
    CURRENT = "current"
    BUILDING = "building"
    INCOMPLETE = "incomplete"
    SUPERSEDED = "superseded"
    CORRUPT = "corrupt"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, order=True)
class SourceEntry:
    path: str
    object_type: SourceObjectType
    executable: bool
    content_digest: str
    size: int
    path_class: SourcePathClass = SourcePathClass.TRACKED
    deleted: bool = False
    symlink_text: str = ""
    resolved_target_id: str = ""
    gitlink_commit: str = ""
    submodule_handling: SubmoduleHandling | None = None

    @classmethod
    def create(
        cls,
        path: str,
        object_type: SourceObjectType,
        content_digest: str,
        size: int,
        *,
        path_class: SourcePathClass = SourcePathClass.TRACKED,
        executable: bool = False,
        deleted: bool = False,
        symlink_text: str = "",
        resolved_target_id: str = "",
        gitlink_commit: str = "",
        submodule_handling: SubmoduleHandling | None = None,
    ) -> SourceEntry:
        return cls(
            normalize_path(path), object_type, executable, normalize_text(content_digest), size,
            path_class, deleted, normalize_text(symlink_text), normalize_text(resolved_target_id),
            normalize_text(gitlink_commit), submodule_handling,
        )

    def __post_init__(self) -> None:
        if self.size < 0:
            raise ValueError("source entry size must be non-negative")
        if self.object_type == SourceObjectType.SYMLINK and not self.symlink_text:
            raise ValueError("symlink text is required")
        if self.object_type == SourceObjectType.GITLINK and (not self.gitlink_commit or self.submodule_handling is None):
            raise ValueError("gitlink commit and handling are required")
        if self.object_type == SourceObjectType.TOMBSTONE:
            if not self.deleted or self.content_digest or self.size:
                raise ValueError("tombstone must be deleted with no content")
        elif self.deleted:
            raise ValueError("only a tombstone may be deleted")
        if self.object_type != SourceObjectType.SYMLINK and self.symlink_text:
            raise ValueError("symlink text is only valid for symlinks")
        if self.object_type != SourceObjectType.SYMLINK and self.resolved_target_id:
            raise ValueError("resolved target identity is only valid for symlinks")
        if self.object_type != SourceObjectType.GITLINK and (self.gitlink_commit or self.submodule_handling is not None):
            raise ValueError("gitlink fields are only valid for gitlinks")


@dataclass(frozen=True)
class SourceRepositoryState:
    head_commit: str
    head_tree: str
    index_tree: str
    index_conflict_stages: tuple[tuple[str, int, str], ...]
    detached: bool
    sparse_checkout_state: str
    lfs_state: str
    unborn: bool = False

    def __post_init__(self) -> None:
        conflicts: list[tuple[str, int, str]] = []
        for path, stage, object_id in self.index_conflict_stages:
            if stage not in (1, 2, 3):
                raise ValueError("index conflict stage must be 1, 2, or 3")
            if not object_id:
                raise ValueError("index conflict object identity is required")
            conflicts.append((normalize_path(path), stage, normalize_text(object_id)))
        if not self.index_tree or not self.sparse_checkout_state or not self.lfs_state:
            raise ValueError("index, sparse-checkout, and LFS states are required")
        if bool(self.head_commit) != bool(self.head_tree):
            raise ValueError("HEAD commit and tree must both be present or both be empty for unborn HEAD")
        if self.unborn == bool(self.head_commit):
            raise ValueError("unborn state must exactly describe an absent HEAD")
        object.__setattr__(self, "index_conflict_stages", tuple(sorted(set(conflicts))))


@dataclass(frozen=True)
class SourceIdentity:
    id: str
    snapshot_class: SourceSnapshotClass
    repository_id: str
    normalized_root: str
    entries: tuple[SourceEntry, ...]
    repository_state: SourceRepositoryState
    policy_digest: str
    policy_provenance_digest: str
    provider_manifest_digest: str
    schema_version: int = GRAPH_SCHEMA_VERSION
    canonicalization_version: int = CANONICALIZATION_VERSION

    @classmethod
    def create(
        cls,
        snapshot_class: SourceSnapshotClass,
        repository_id: str,
        normalized_root: str,
        entries: tuple[SourceEntry, ...],
        *,
        repository_state: SourceRepositoryState,
        policy_digest: str,
        policy_provenance_digest: str,
        provider_manifest_digest: str,
    ) -> SourceIdentity:
        required = (
            repository_id, normalized_root, policy_digest, policy_provenance_digest,
            provider_manifest_digest,
        )
        if not all(normalize_text(value) for value in required):
            raise ValueError("source identity fields must be non-empty")
        if len({entry.path for entry in entries}) != len(entries):
            raise ValueError("source entry paths must be unique")
        ordered_entries = tuple(sorted(entries, key=lambda entry: entry.path.encode("utf-8")))
        payload = {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "snapshot_class": snapshot_class,
            "repository_id": normalize_text(repository_id),
            "repository_state": repository_state,
            "entries": ordered_entries,
            "policy_digest": normalize_text(policy_digest),
            "policy_provenance_digest": normalize_text(policy_provenance_digest),
            "provider_manifest_digest": normalize_text(provider_manifest_digest),
        }
        return cls(
            canonical_digest(payload), snapshot_class, normalize_text(repository_id),
            normalize_text(normalized_root), ordered_entries, repository_state, normalize_text(policy_digest),
            normalize_text(policy_provenance_digest), normalize_text(provider_manifest_digest),
        )


@dataclass(frozen=True)
class FreshnessAssessment:
    requested_source_id: str
    generation_source_id: str
    state: FreshnessState
    reason: str = ""

    @classmethod
    def create(
        cls,
        requested_source_id: str,
        generation_source_id: str,
        state: FreshnessState,
        reason: str = "",
    ) -> FreshnessAssessment:
        requested_source_id = normalize_text(requested_source_id)
        generation_source_id = normalize_text(generation_source_id)
        reason = normalize_text(reason)
        if not requested_source_id:
            raise ValueError("requested source is required")
        if state == FreshnessState.CURRENT:
            if not generation_source_id or requested_source_id != generation_source_id:
                raise ValueError("current freshness requires a matching source")
            if reason:
                raise ValueError("current freshness cannot include a failure reason")
        elif not reason:
            raise ValueError("non-current freshness requires a reason")
        return cls(requested_source_id, generation_source_id, state, reason)

    @property
    def authorizes_current_action(self) -> bool:
        return self.state == FreshnessState.CURRENT


@dataclass(frozen=True)
class Provenance:
    provider_id: str
    source_id: str
    location: str = ""

    def __post_init__(self) -> None:
        for field_name in ("provider_id", "source_id"):
            if not normalize_text(getattr(self, field_name)):
                raise ValueError(f"{field_name} must be non-empty")


@dataclass(frozen=True)
class Node:
    id: str
    kind: str
    stable_key: str
    attributes_json: str
    provenance: tuple[Provenance, ...]
    schema_version: int = GRAPH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _validate_canonical_object(self.attributes_json)

    @classmethod
    def create(
        cls,
        kind: str,
        stable_key: str,
        attributes: Mapping[str, Any] | None = None,
        provenance: tuple[Provenance, ...] = (),
    ) -> Node:
        kind = normalize_text(kind)
        stable_key = normalize_text(stable_key)
        if not kind or not stable_key:
            raise ValueError("node kind and stable_key must be non-empty")
        attributes_json = canonical_attributes(attributes)
        ordered_provenance = tuple(sorted(set(provenance), key=lambda item: canonical_json(item)))
        identity = {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "kind": kind,
            "stable_key": stable_key,
        }
        return cls(canonical_digest(identity), kind, stable_key, attributes_json, ordered_provenance)


@dataclass(frozen=True, order=True)
class Incidence:
    edge_id: str
    node_id: str
    role: str
    direction: str
    ordinal: int = 0

    def __post_init__(self) -> None:
        if not self.edge_id or not self.node_id or not self.role or not self.direction:
            raise ValueError("incidence identifiers, role, and direction must be non-empty")
        if self.direction not in ("in", "out"):
            raise ValueError("incidence direction must be in or out")
        if self.ordinal < 0:
            raise ValueError("incidence ordinal must be non-negative")


@dataclass(frozen=True)
class Hyperedge:
    id: str
    type: str
    attributes_json: str
    provider_fact_set_id: str
    confidence_basis_points: int
    incidence_signature: tuple[tuple[str, str, str, int], ...]
    schema_version: int = GRAPH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _validate_canonical_object(self.attributes_json)

    @classmethod
    def create(
        cls,
        edge_type: str,
        incidences: tuple[tuple[str, str, str, int], ...],
        provider_fact_set_id: str,
        attributes: Mapping[str, Any] | None = None,
        confidence_basis_points: int = 10_000,
    ) -> Hyperedge:
        edge_type = normalize_text(edge_type)
        if not edge_type or not provider_fact_set_id or not incidences:
            raise ValueError("edge type, provider fact set, and incidences are required")
        if not 0 <= confidence_basis_points <= 10_000:
            raise ValueError("confidence must be between 0 and 10000 basis points")
        signature = tuple(sorted(set(incidences)))
        attributes_json = canonical_attributes(attributes)
        identity = {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "type": edge_type,
            "attributes": json.loads(attributes_json),
            "provider_fact_set_id": provider_fact_set_id,
            "incidences": signature,
        }
        return cls(
            canonical_digest(identity), edge_type, attributes_json, provider_fact_set_id,
            confidence_basis_points, signature,
        )


@dataclass(frozen=True)
class GraphGeneration:
    source_snapshot_id: str
    traversal_rule_set_digest: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    incidence_ids: tuple[str, ...]
    provider_fact_set_ids: tuple[str, ...]
    digest: str
    schema_version: int = GRAPH_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        source_snapshot_id: str,
        traversal_rule_set_digest: str,
        node_ids: tuple[str, ...],
        edge_ids: tuple[str, ...],
        incidence_ids: tuple[str, ...],
        provider_fact_set_ids: tuple[str, ...],
    ) -> GraphGeneration:
        if not source_snapshot_id or not traversal_rule_set_digest:
            raise ValueError("source snapshot and traversal rule set are required")
        nodes = tuple(sorted(set(node_ids)))
        edges = tuple(sorted(set(edge_ids)))
        incidences = tuple(sorted(set(incidence_ids)))
        providers = tuple(sorted(set(provider_fact_set_ids)))
        payload = {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "source_snapshot_id": source_snapshot_id,
            "traversal_rule_set_digest": traversal_rule_set_digest,
            "node_ids": nodes,
            "edge_ids": edges,
            "incidence_ids": incidences,
            "provider_fact_set_ids": providers,
        }
        return cls(
            source_snapshot_id, traversal_rule_set_digest, nodes, edges, incidences,
            providers, canonical_digest(payload),
        )
