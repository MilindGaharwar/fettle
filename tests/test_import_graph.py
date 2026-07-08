"""Tests for Fettle cross-file Python import analysis (WP-C3)."""

import os
import shutil
import tempfile
import time

import pytest

import sys
PLUGIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PLUGIN_DIR, "scripts"))

from import_graph import dependents_of, check_imports, check_contracts


@pytest.fixture
def project_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# --- Test 1: dependents_of returns files that import a given module -----------

def test_dependents_of_basic(project_dir):
    """3-file project: a.py imports b, c.py imports b -> dependents_of(b.py) = {a.py, c.py}."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("import b\n\nx = b.value\n")
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("value = 42\n")
    with open(os.path.join(project_dir, "c.py"), "w") as f:
        f.write("from b import value\n\ny = value + 1\n")

    b_path = os.path.join(project_dir, "b.py")
    deps = dependents_of(b_path, project_dir)
    dep_basenames = {os.path.basename(p) for p in deps}
    assert dep_basenames == {"a.py", "c.py"}


def test_dependents_of_no_dependents(project_dir):
    """File with no importers returns empty set."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("x = 1\n")
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("y = 2\n")

    a_path = os.path.join(project_dir, "a.py")
    deps = dependents_of(a_path, project_dir)
    assert deps == set()


# --- Test 2: broken import detection (module renamed) -------------------------

def test_check_imports_broken_module(project_dir):
    """a.py imports b, but b.py was renamed to d.py -> error for 'import b'."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("import b\n\nx = b.value\n")
    with open(os.path.join(project_dir, "d.py"), "w") as f:
        f.write("value = 42\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert len(errors) >= 1
    assert any("b" in e["module"] for e in errors)


def test_check_imports_valid(project_dir):
    """a.py imports b, b.py exists -> no errors."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("import b\n")
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("value = 42\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert errors == []


def test_check_imports_from_import(project_dir):
    """a.py does 'from b import value', b.py deleted -> error."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("from b import value\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert len(errors) >= 1
    assert any("b" in e["module"] for e in errors)


# --- Test 3: missing function detection ---------------------------------------

def test_check_contracts_missing_function(project_dir):
    """a.py does 'from b import foo', but b.py has no foo -> error."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("from b import foo\n")
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("def bar():\n    return 1\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_contracts(a_path, project_dir)
    assert len(errors) >= 1
    assert any("foo" in e["name"] for e in errors)


def test_check_contracts_valid(project_dir):
    """a.py does 'from b import foo', b.py defines foo -> no errors."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("from b import foo\n")
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("def foo():\n    return 1\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_contracts(a_path, project_dir)
    assert errors == []


def test_check_contracts_variable_export(project_dir):
    """a.py does 'from b import VALUE', b.py defines VALUE as a variable -> no errors."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("from b import VALUE\n")
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("VALUE = 42\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_contracts(a_path, project_dir)
    assert errors == []


# --- Test 4: dynamic imports handled gracefully --------------------------------

def test_dynamic_import_skipped(project_dir):
    """importlib.import_module('x') is skipped, no error even though x doesn't exist."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write('import importlib\nmod = importlib.import_module("x")\n')

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert errors == []


def test_dynamic_import_mixed(project_dir):
    """File with both static and dynamic imports: only static checked."""
    with open(os.path.join(project_dir, "b.py"), "w") as f:
        f.write("x = 1\n")
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write('import b\nimport importlib\nmod = importlib.import_module("nonexistent")\n')

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert errors == []


# --- Test 5: subpackage imports ------------------------------------------------

def test_check_imports_subpackage(project_dir):
    """a.py does 'from pkg.sub import func' -- pkg/sub.py exists with func -> no error."""
    pkg_dir = os.path.join(project_dir, "pkg")
    os.makedirs(pkg_dir)
    with open(os.path.join(pkg_dir, "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(pkg_dir, "sub.py"), "w") as f:
        f.write("def func():\n    return 1\n")
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("from pkg.sub import func\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert errors == []
    errors2 = check_contracts(a_path, project_dir)
    assert errors2 == []


# --- Test 6: performance -- 50-file graph in <500ms ---------------------------

def test_performance_50_files(project_dir):
    """Build import graph for 50-file hub project in under 500ms."""
    with open(os.path.join(project_dir, "core.py"), "w") as f:
        f.write("value = 0\n")
    for i in range(49):
        with open(os.path.join(project_dir, f"mod_{i}.py"), "w") as f:
            f.write(f"from core import value\nresult = value + {i}\n")

    target = os.path.join(project_dir, "core.py")

    start = time.perf_counter()
    deps = dependents_of(target, project_dir)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert len(deps) == 49
    assert elapsed_ms < 500, f"Took {elapsed_ms:.0f}ms, expected <500ms"


# --- Test: stdlib imports are skipped ------------------------------------------

def test_stdlib_imports_skipped(project_dir):
    """Imports of stdlib modules (os, sys, json) produce no errors."""
    with open(os.path.join(project_dir, "a.py"), "w") as f:
        f.write("import os\nimport sys\nimport json\nfrom pathlib import Path\n")

    a_path = os.path.join(project_dir, "a.py")
    errors = check_imports(a_path, project_dir)
    assert errors == []


# --- Regressions: import false positives on real-world project layouts ---

def test_third_party_in_project_venv_is_skipped(project_dir):
    """A package in the project's .venv but not the hook's python must pass.

    Regression: third-party deps were flagged as unresolvable because the
    hook runs under its own interpreter and importlib can't see a project
    virtualenv it was not launched from.
    """
    sp = os.path.join(project_dir, ".venv", "lib", "python3.14", "site-packages", "notinhookenv")
    os.makedirs(sp)
    open(os.path.join(sp, "__init__.py"), "w").close()
    a_path = os.path.join(project_dir, "a.py")
    with open(a_path, "w") as f:
        f.write("import notinhookenv\nfrom notinhookenv.sub import thing\n")
    assert check_imports(a_path, project_dir) == []


def test_check_contracts_submodule_import_is_valid(project_dir):
    """`from pkg import submodule` is valid even without __init__ re-export.

    Regression: `from pkg import submodule` was flagged as
    "'submodule' not found in 'pkg'" when the package's __init__ did not
    re-export the submodule — a valid Python import wrongly rejected.
    """
    pkg = os.path.join(project_dir, "pkg")
    os.makedirs(pkg)
    open(os.path.join(pkg, "__init__.py"), "w").close()
    with open(os.path.join(pkg, "sub.py"), "w") as f:
        f.write("x = 1\n")
    a_path = os.path.join(project_dir, "a.py")
    with open(a_path, "w") as f:
        f.write("from pkg import sub\n")
    assert check_contracts(a_path, project_dir) == []


def test_submodule_leniency_keeps_missing_names_blocked(project_dir):
    """The submodule rule must not mask names that truly don't exist."""
    pkg = os.path.join(project_dir, "pkg")
    os.makedirs(pkg)
    with open(os.path.join(pkg, "__init__.py"), "w") as f:
        f.write("real = 1\n")
    a_path = os.path.join(project_dir, "a.py")
    with open(a_path, "w") as f:
        f.write("from pkg import ghost\n")
    errors = check_contracts(a_path, project_dir)
    assert len(errors) == 1
    assert errors[0]["name"] == "ghost"


def test_src_layout_package_resolves(project_dir):
    """Regression: src-layout (`src/<pkg>/`) is a standard packaging
    layout — `import <pkg>` must resolve against src/, not only repo root."""
    pkg = os.path.join(project_dir, "src", "mypkg")
    os.makedirs(pkg)
    open(os.path.join(pkg, "__init__.py"), "w").close()
    with open(os.path.join(pkg, "mod.py"), "w") as f:
        f.write("x = 1\n")
    a_path = os.path.join(project_dir, "a.py")
    with open(a_path, "w") as f:
        f.write("import mypkg\nfrom mypkg.mod import x\n")
    assert check_imports(a_path, project_dir) == []


def test_declared_dependency_is_skipped(project_dir):
    """Regression: a dependency run via an ephemeral env (e.g.
    `uv run --with X`) leaves no .venv to probe, but it is declared in
    pyproject.toml — a declared dependency must not be flagged."""
    with open(os.path.join(project_dir, "pyproject.toml"), "w") as f:
        f.write('[project]\nname = "x"\n[project.optional-dependencies]\ndev = ["pytest>=7.0"]\n')
    a_path = os.path.join(project_dir, "a.py")
    with open(a_path, "w") as f:
        f.write("import pytest\n")
    assert check_imports(a_path, project_dir) == []


def test_undeclared_unknown_module_still_flagged(project_dir):
    """The declared-dep rule must not blind the checker to real typos."""
    with open(os.path.join(project_dir, "pyproject.toml"), "w") as f:
        f.write('[project]\nname = "x"\ndependencies = ["requests"]\n')
    a_path = os.path.join(project_dir, "a.py")
    with open(a_path, "w") as f:
        f.write("import definitely_not_a_module_xyz\n")
    errors = check_imports(a_path, project_dir)
    assert len(errors) == 1
