"""Fettle v0.5.0 — Language adapter registry.

WP-78: Defines the adapter protocol and provides discovery/registry.
"""

from __future__ import annotations

from typing import Protocol

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fettle.finding import CheckFinding
from fettle.profile import Profile


class LanguageAdapter(Protocol):
    """Protocol that all language adapters must implement."""

    language: str

    def detect(self, profile: Profile) -> bool: ...
    def lint(self, tier: str, files: list[str]) -> list[CheckFinding]: ...
    def format_check(self, tier: str, files: list[str]) -> list[CheckFinding]: ...
    def typecheck(self, tier: str, files: list[str]) -> list[CheckFinding]: ...
    def test(self, tier: str, files: list[str]) -> list[CheckFinding]: ...
    def build(self, tier: str) -> list[CheckFinding]: ...
    def dependency_check(self, files: list[str]) -> list[CheckFinding]: ...


_REGISTRY: list[LanguageAdapter] = []


def register_adapter(adapter: LanguageAdapter) -> None:
    """Register a language adapter."""
    _REGISTRY.append(adapter)


def list_adapters() -> list[LanguageAdapter]:
    """Return all registered adapters."""
    _ensure_loaded()
    return list(_REGISTRY)


def get_adapter(language: str) -> LanguageAdapter | None:
    """Get adapter by language name."""
    _ensure_loaded()
    for a in _REGISTRY:
        if a.language == language:
            return a
    return None


_loaded = False


def _ensure_loaded():
    global _loaded
    if _loaded:
        return
    _loaded = True
    from fettle.adapters.python_adapter import PythonAdapter
    from fettle.adapters.typescript_adapter import TypeScriptAdapter
    from fettle.adapters.rust_adapter import RustAdapter
    from fettle.adapters.go_adapter import GoAdapter
    if not any(a.language == "python" for a in _REGISTRY):
        register_adapter(PythonAdapter())
    if not any(a.language == "typescript" for a in _REGISTRY):
        register_adapter(TypeScriptAdapter())
    if not any(a.language == "rust" for a in _REGISTRY):
        register_adapter(RustAdapter())
    if not any(a.language == "go" for a in _REGISTRY):
        register_adapter(GoAdapter())
