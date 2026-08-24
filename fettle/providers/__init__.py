"""Native providers for the ephemeral hypergraph (P46)."""

from __future__ import annotations

from fettle.providers.base import (
    EdgeDraft,
    NodeDraft,
    Provider,
    ProviderResult,
)
from fettle.providers.python_import_provider import python_import_provider
from fettle.providers.spec_provider import spec_provider
from fettle.providers.trace_marker_provider import trace_marker_provider
from fettle.providers.work_item_provider import work_item_provider
from fettle.providers.workspace_provider import workspace_provider


def default_providers() -> tuple[Provider, ...]:
    return (
        spec_provider,
        trace_marker_provider,
        work_item_provider,
        workspace_provider,
        python_import_provider,
    )


__all__ = [
    "EdgeDraft",
    "NodeDraft",
    "Provider",
    "ProviderResult",
    "default_providers",
]
