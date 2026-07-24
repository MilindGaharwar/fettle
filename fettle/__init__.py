"""Fettle — quality enforcement for AI-assisted development.

Public API (WP-139): stable entry points for programmatic use. Everything
else under fettle.* is internal and may change between minor versions.
"""

__version__ = "1.0.2"

__all__ = ["__version__", "load_config", "scan_project", "find_repo_root"]


def __getattr__(name):  # lazy — keep `import fettle` dependency-free
    if name == "load_config":
        from fettle.config import load_config
        return load_config
    if name == "scan_project":
        from fettle.quality_scan import scan_project
        return scan_project
    if name == "find_repo_root":
        from fettle.paths import find_repo_root
        return find_repo_root
    raise AttributeError(f"module 'fettle' has no attribute {name!r}")
