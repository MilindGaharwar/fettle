"""Fettle v0.5.0 — WP-79: Dependency validation checker.

AST-based import extraction, compare against declared deps,
detect undeclared imports in Python code.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

from finding import CheckFinding, FindingSeverity


_STDLIB_MODULES: set[str] | None = None


def is_stdlib(module_name: str) -> bool:
    """Check if a module is part of Python's standard library."""
    global _STDLIB_MODULES
    if _STDLIB_MODULES is None:
        _STDLIB_MODULES = _build_stdlib_set()
    return module_name in _STDLIB_MODULES


def _build_stdlib_set() -> set[str]:
    """Build set of stdlib module names for current Python version."""
    try:
        from sys import stdlib_module_names
        return set(stdlib_module_names)
    except ImportError:
        pass
    # Fallback for Python < 3.10
    return {
        "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
        "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
        "binhex", "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb",
        "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
        "colorsys", "compileall", "concurrent", "configparser", "contextlib",
        "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv",
        "ctypes", "curses", "dataclasses", "datetime", "dbm", "decimal",
        "difflib", "dis", "distutils", "doctest", "email", "encodings",
        "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput",
        "fnmatch", "fractions", "ftplib", "functools", "gc", "getopt",
        "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq",
        "hmac", "html", "http", "idlelib", "imaplib", "imghdr", "imp",
        "importlib", "inspect", "io", "ipaddress", "itertools", "json",
        "keyword", "lib2to3", "linecache", "locale", "logging", "lzma",
        "mailbox", "mailcap", "marshal", "math", "mimetypes", "mmap",
        "modulefinder", "multiprocessing", "netrc", "nis", "nntplib",
        "numbers", "operator", "optparse", "os", "ossaudiodev", "pathlib",
        "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
        "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
        "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc",
        "queue", "quopri", "random", "re", "readline", "reprlib",
        "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
        "selectors", "shelve", "shlex", "shutil", "signal", "site",
        "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "sqlite3",
        "sre_compile", "sre_constants", "sre_parse", "ssl", "stat",
        "statistics", "string", "stringprep", "struct", "subprocess",
        "sunau", "symtable", "sys", "sysconfig", "syslog", "tabnanny",
        "tarfile", "telnetlib", "tempfile", "termios", "test", "textwrap",
        "threading", "time", "timeit", "tkinter", "token", "tokenize",
        "tomllib", "trace", "traceback", "tracemalloc", "tty", "turtle",
        "turtledemo", "types", "typing", "unicodedata", "unittest",
        "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
        "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml",
        "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
        "_thread", "__future__",
    }


def extract_imports(file_path: str) -> set[str]:
    """Extract top-level imported module names from a Python file using AST."""
    try:
        source = Path(file_path).read_text()
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return set()

    imports: set[str] = set()
    conditional_imports: set[str] = set()

    for node in ast.walk(tree):
        # Skip TYPE_CHECKING blocks
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            for child in ast.walk(node):
                if isinstance(child, (ast.Import, ast.ImportFrom)):
                    for alias in (child.names if isinstance(child, ast.Import) else []):
                        conditional_imports.add(alias.name.split(".")[0])
                    if isinstance(child, ast.ImportFrom) and child.module:
                        conditional_imports.add(child.module.split(".")[0])
            continue

        # Skip try/except blocks (conditional imports)
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                for child in ast.walk(handler):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        for alias in (child.names if isinstance(child, ast.Import) else []):
                            conditional_imports.add(alias.name.split(".")[0])
                        if isinstance(child, ast.ImportFrom) and child.module:
                            conditional_imports.add(child.module.split(".")[0])
            for child in ast.iter_child_nodes(node):
                if child in node.handlers:
                    continue
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Import):
                        for alias in sub.names:
                            conditional_imports.add(alias.name.split(".")[0])
                    elif isinstance(sub, ast.ImportFrom) and sub.module:
                        conditional_imports.add(sub.module.split(".")[0])
            continue

        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    return imports - conditional_imports


def _is_type_checking_guard(node: ast.If) -> bool:
    """Check if an if node is `if TYPE_CHECKING:`."""
    test = node.test
    return (
        (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
        or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
    )


def get_declared_deps(cwd: str) -> set[str]:
    """Get declared dependencies from pyproject.toml or requirements.txt."""
    root = Path(cwd)
    deps: set[str] = set()

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            raw_deps = data.get("project", {}).get("dependencies", [])
            for dep in raw_deps:
                name = _normalize_dep_name(dep)
                if name:
                    deps.add(name)
            # Also check optional deps
            optional = data.get("project", {}).get("optional-dependencies", {})
            for group_deps in optional.values():
                for dep in group_deps:
                    name = _normalize_dep_name(dep)
                    if name:
                        deps.add(name)
        except (tomllib.TOMLDecodeError, OSError):
            pass

    req_txt = root / "requirements.txt"
    if req_txt.is_file():
        try:
            for line in req_txt.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    name = _normalize_dep_name(line)
                    if name:
                        deps.add(name)
        except OSError:
            pass

    return deps


def _normalize_dep_name(dep_spec: str) -> str:
    """Extract and normalize package name from a dependency spec."""
    name = re.split(r"[>=<!\[;@\s]", dep_spec)[0].strip()
    return name.lower().replace("-", "").replace("_", "")


def _get_local_packages(cwd: str) -> set[str]:
    """Detect local packages (directories with __init__.py)."""
    root = Path(cwd)
    packages: set[str] = set()
    for item in root.iterdir():
        if item.is_dir() and (item / "__init__.py").is_file():
            packages.add(item.name)
    # Also check src layout
    src = root / "src"
    if src.is_dir():
        for item in src.iterdir():
            if item.is_dir() and (item / "__init__.py").is_file():
                packages.add(item.name)
    return packages


def check_undeclared(cwd: str, files: list[str]) -> list[CheckFinding]:
    """Check for undeclared imports in the given files."""
    declared = get_declared_deps(cwd)
    local_packages = _get_local_packages(cwd)
    findings: list[CheckFinding] = []

    for file_path in files:
        imports = extract_imports(file_path)
        for module in sorted(imports):
            if is_stdlib(module):
                continue
            if module in local_packages:
                continue
            normalized = module.lower().replace("-", "").replace("_", "")
            if normalized in declared:
                continue
            # Check common name mappings
            if _is_known_mapping(module, declared):
                continue
            findings.append(CheckFinding(
                checker="dep-check",
                severity=FindingSeverity.WARNING,
                file=file_path,
                line=0,
                message=f"Undeclared dependency: '{module}' is imported but not in pyproject.toml",
                suggested_fix=f"Add '{module}' to [project].dependencies",
                rerun_command="fettle check --changed",
            ))

    return findings


_NAME_MAPPINGS = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "attr": "attrs",
    "gi": "pygobject",
    "wx": "wxpython",
    "Crypto": "pycryptodome",
    "serial": "pyserial",
    "usb": "pyusb",
    "dotenv": "python-dotenv",
}


def _is_known_mapping(module: str, declared: set[str]) -> bool:
    """Check if module maps to a known different package name."""
    mapped = _NAME_MAPPINGS.get(module)
    if mapped:
        normalized = mapped.lower().replace("-", "").replace("_", "")
        return normalized in declared
    return False
