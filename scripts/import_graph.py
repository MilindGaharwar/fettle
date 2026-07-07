"""Cross-file Python import analysis — AST-based import graph, broken import detector, contract checker."""

import ast
import os
import sys

STDLIB_TOP_LEVEL = frozenset(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else frozenset()


def _parse_imports(file_path: str) -> list[dict]:
    """Parse a Python file and return a list of import records."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (SyntaxError, OSError):
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"type": "import", "module": alias.name, "names": [], "line": node.lineno})
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [a.name for a in node.names] if node.names else []
            imports.append({"type": "from", "module": node.module, "names": names, "line": node.lineno})
    return imports


def _resolve_module(module_name: str, project_root: str) -> str | None:
    """Resolve a dotted module name to a file path within the project, or None."""
    parts = module_name.split(".")
    candidates = [
        os.path.join(project_root, *parts) + ".py",
        os.path.join(project_root, *parts, "__init__.py"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _top_level_module(module_name: str) -> str:
    return module_name.split(".")[0]


def _is_local_module(module_name: str, project_root: str) -> bool:
    """True if module_name can be resolved to a file in project_root."""
    return _resolve_module(module_name, project_root) is not None


def _is_stdlib(module_name: str) -> bool:
    top = _top_level_module(module_name)
    if STDLIB_TOP_LEVEL:
        return top in STDLIB_TOP_LEVEL
    try:
        __import__(top)
        import importlib.util
        spec = importlib.util.find_spec(top)
        if spec and spec.origin:
            return "site-packages" not in spec.origin
        return True
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _is_installed(module_name: str) -> bool:
    """True if module_name is importable (installed third-party package)."""
    import importlib.util
    try:
        return importlib.util.find_spec(_top_level_module(module_name)) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _in_project_venv(module_name: str, project_root: str) -> bool:
    """True if the top-level package exists in the project's own virtualenv.

    Hooks run under their own interpreter, so importlib cannot see packages
    installed only in the project venv — without this check every project
    dependency reads as an unresolvable import (alpha-agent, 2026-07-07).
    """
    import glob
    top = _top_level_module(module_name)
    pattern = os.path.join(project_root, ".venv", "lib", "python*", "site-packages", top)
    return bool(glob.glob(pattern) or glob.glob(pattern + ".py"))


def _exported_names(file_path: str) -> set[str]:
    """Return the set of top-level names defined in a Python file."""
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=file_path)
    except (SyntaxError, OSError):
        return set()

    names = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif node.names:
                for alias in node.names:
                    names.add(alias.asname or alias.name)
    return names


def _collect_py_files(project_root: str) -> list[str]:
    """Collect all .py files under project_root."""
    py_files = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for fname in filenames:
            if fname.endswith(".py"):
                py_files.append(os.path.join(dirpath, fname))
    return py_files


def _file_to_module(file_path: str, project_root: str) -> str | None:
    """Convert a file path to a dotted module name relative to project_root."""
    rel = os.path.relpath(file_path, project_root)
    if rel.endswith("__init__.py"):
        rel = os.path.dirname(rel)
    elif rel.endswith(".py"):
        rel = rel[:-3]
    else:
        return None
    return rel.replace(os.sep, ".")


def dependents_of(file_path: str, project_root: str) -> set[str]:
    """Return the set of .py files in project_root that import the given file."""
    target_module = _file_to_module(file_path, project_root)
    if not target_module:
        return set()

    target_parts = target_module.split(".")
    result = set()

    for py_file in _collect_py_files(project_root):
        if os.path.abspath(py_file) == os.path.abspath(file_path):
            continue
        for imp in _parse_imports(py_file):
            imp_parts = imp["module"].split(".")
            if imp_parts == target_parts or imp_parts[:len(target_parts)] == target_parts:
                result.add(py_file)
                break
    return result


ALLOWED_DYNAMIC_IMPORTS: set[str] = set()  # add project-specific dynamic imports via config (WP-9)


def check_imports(file_path: str, project_root: str) -> list[dict]:
    """Check that all static imports in file_path resolve to files in project_root or stdlib."""
    errors = []
    for imp in _parse_imports(file_path):
        module = imp["module"]
        top = _top_level_module(module)

        if module in ALLOWED_DYNAMIC_IMPORTS or top in ALLOWED_DYNAMIC_IMPORTS:
            continue
        if _is_stdlib(module):
            continue
        if _is_installed(module):
            continue
        if _in_project_venv(module, project_root):
            continue
        if _is_local_module(module, project_root):
            continue
        if _is_local_module(top, project_root):
            continue

        errors.append({
            "file": file_path,
            "line": imp["line"],
            "module": module,
            "error": f"Cannot resolve module '{module}' in project or stdlib",
        })
    return errors


def check_contracts(file_path: str, project_root: str) -> list[dict]:
    """Check that 'from X import name' statements reference names that exist in X."""
    errors = []
    for imp in _parse_imports(file_path):
        if imp["type"] != "from" or not imp["names"]:
            continue
        module = imp["module"]
        if _is_stdlib(module):
            continue

        resolved = _resolve_module(module, project_root)
        if not resolved:
            continue

        exported = _exported_names(resolved)
        for name in imp["names"]:
            if name == "*":
                continue
            if _resolve_module(f"{module}.{name}", project_root):
                continue  # `from pkg import submodule` needs no __init__ re-export
            if name not in exported:
                errors.append({
                    "file": file_path,
                    "line": imp["line"],
                    "module": module,
                    "name": name,
                    "error": f"Name '{name}' not found in '{module}' ({resolved})",
                })
    return errors
