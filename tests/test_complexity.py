"""WP-H — Function Complexity Limits tests."""

import ast
import os
import textwrap
from pathlib import Path
from unittest.mock import patch

from complexity_check import _cyclomatic, _cognitive, analyze_functions, run_check
from dispatcher_types import Decision, HookContext, HookInput


def _parse_func(code: str) -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(code))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            return node
    raise ValueError("No function found")


def test_cyclomatic_simple():
    func = _parse_func("def f():\n    return 1\n")
    assert _cyclomatic(func) == 1


def test_cyclomatic_branches():
    func = _parse_func("""
def f(x):
    if x > 0:
        for i in range(x):
            if i % 2:
                pass
    return x
""")
    # 1 (base) + 1 (if) + 1 (for) + 1 (if) = 4
    assert _cyclomatic(func) == 4


def test_cyclomatic_boolop():
    func = _parse_func("""
def f(a, b, c):
    if a and b or c:
        pass
""")
    # 1 (base) + 1 (if) + 2 (BoolOp: `and` has 2 values → +1, `or` has 2 values → +1)
    # Actually: `a and b or c` parses as BoolOp(Or, [BoolOp(And, [a, b]), c])
    # Outer Or: len=2 → +1, Inner And: len=2 → +1, If: +1
    assert _cyclomatic(func) == 4


def test_cognitive_simple():
    func = _parse_func("def f():\n    return 1\n")
    assert _cognitive(func) == 0


def test_cognitive_nested():
    func = _parse_func("""
def f(x):
    if x:
        for i in range(x):
            if i:
                pass
""")
    # if: 1+0=1, for: 1+1=2, if: 1+2=3 → total=6
    assert _cognitive(func) == 6


def test_analyze_only_changed_functions():
    code = textwrap.dedent("""
def simple():
    return 1

def complex_one(x):
    if x:
        if x > 1:
            if x > 2:
                if x > 3:
                    pass
""")
    tree = ast.parse(code)
    # Only mark lines for complex_one (lines 5-10)
    results = analyze_functions(tree, changed_lines={5, 6, 7, 8, 9, 10})
    assert len(results) == 1
    assert results[0]["name"] == "complex_one"


def test_analyze_untouched_function_excluded():
    code = textwrap.dedent("""
def untouched():
    if True:
        if True:
            if True:
                pass

def touched():
    return 1
""")
    tree = ast.parse(code)
    results = analyze_functions(tree, changed_lines={8, 9})
    assert len(results) == 1
    assert results[0]["name"] == "touched"


def _make_ctx(file_path: str, config_overrides: dict | None = None):
    config = {
        "gates": {
            "complexity": {
                "enabled": True,
                "enforce": False,
                "max_cyclomatic": 10,
                "max_cognitive": 15,
            },
        },
    }
    if config_overrides:
        config["gates"]["complexity"].update(config_overrides)

    hook_input = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Edit",
        tool_input={"file_path": file_path},
        cwd=Path(os.path.dirname(file_path)),
        session_id="test-complexity",
        raw={},
    )
    return HookContext(
        input=hook_input,
        config=config,
        plugin_root=Path(__file__).parent.parent,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=999999.0,
    )


def test_run_check_advisory_on_complex_function(tmp_path):
    code = textwrap.dedent("""
def monster(a, b, c, d, e, f, g, h, i, j, k):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            if g:
                                if h:
                                    if i:
                                        if j:
                                            if k:
                                                pass
""")
    src = tmp_path / "complex.py"
    src.write_text(code)

    ctx = _make_ctx(str(src))
    with patch("lean_sniffers._get_changed_lines", return_value=None):
        result = run_check(ctx)
    assert result.decision == Decision.ADVISORY
    assert "monster" in result.message
    assert "cyclomatic" in result.message


def test_run_check_allows_simple_function(tmp_path):
    src = tmp_path / "simple.py"
    src.write_text("def hello():\n    return 'world'\n")

    ctx = _make_ctx(str(src))
    with patch("lean_sniffers._get_changed_lines", return_value=None):
        result = run_check(ctx)
    assert result.decision == Decision.ALLOW


def test_run_check_syntax_error_graceful(tmp_path):
    src = tmp_path / "broken.py"
    src.write_text("def incomplete(:\n")

    ctx = _make_ctx(str(src))
    result = run_check(ctx)
    assert result.decision == Decision.ALLOW
