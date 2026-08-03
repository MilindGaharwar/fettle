"""Tests for fettle.complexity_check — cyclomatic/cognitive complexity gate."""

import ast
import textwrap

from fettle.complexity_check import _cognitive, _cyclomatic, analyze_functions, run_check
from fettle.dispatcher_types import Decision, HookContext, HookInput


def _parse_func(source):
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node
    raise ValueError("no function found")


class TestCyclomatic:
    def test_simple_function(self):
        node = _parse_func("def f(): return 1")
        assert _cyclomatic(node) == 1

    def test_if_adds_one(self):
        node = _parse_func("def f(x):\n  if x: return 1\n  return 0")
        assert _cyclomatic(node) == 2

    def test_for_loop(self):
        node = _parse_func("def f(xs):\n  for x in xs: pass")
        assert _cyclomatic(node) == 2

    def test_boolean_ops(self):
        node = _parse_func("def f(a, b, c):\n  if a and b and c: pass")
        assert _cyclomatic(node) == 4  # 1 + if(1) + and-chain(2)

    def test_except_handler(self):
        node = _parse_func("def f():\n  try:\n    pass\n  except ValueError:\n    pass")
        assert _cyclomatic(node) == 2

    def test_comprehension_with_if(self):
        node = _parse_func("def f(xs):\n  return [x for x in xs if x > 0]")
        assert _cyclomatic(node) == 3  # 1 + comp(1) + comp-if(1)


class TestCognitive:
    def test_simple_function(self):
        node = _parse_func("def f(): return 1")
        assert _cognitive(node) == 0

    def test_single_if(self):
        node = _parse_func("def f(x):\n  if x: return 1\n  return 0")
        assert _cognitive(node) == 1  # 1 + 0 nesting

    def test_nested_if(self):
        node = _parse_func("""\
def f(x, y):
    if x:
        if y:
            return 1
    return 0
""")
        assert _cognitive(node) == 3  # outer if(1+0) + inner if(1+1)

    def test_for_loop(self):
        node = _parse_func("def f(xs):\n  for x in xs: pass")
        assert _cognitive(node) == 1


class TestAnalyzeFunctions:
    def test_filters_by_changed_lines(self):
        source = "def a(): pass\ndef b(): pass\n"
        tree = ast.parse(source)
        results = analyze_functions(tree, {1})
        assert len(results) == 1
        assert results[0]["name"] == "a"

    def test_no_filter_returns_all(self):
        source = "def a(): pass\ndef b(): pass\n"
        tree = ast.parse(source)
        results = analyze_functions(tree, None)
        assert len(results) == 2


class TestRunCheck:
    def test_non_python_file_allows(self, tmp_path, monkeypatch):
        ctx = _make_ctx(tmp_path, monkeypatch, file_path="/tmp/x.ts")
        result = run_check(ctx)
        assert result.decision == Decision.ALLOW

    def test_simple_file_allows(self, tmp_path, monkeypatch):
        py = tmp_path / "simple.py"
        py.write_text("def hello(): return 1\n")
        ctx = _make_ctx(tmp_path, monkeypatch, file_path=str(py))
        result = run_check(ctx)
        assert result.decision == Decision.ALLOW

    def test_complex_function_advisory(self, tmp_path, monkeypatch):
        source = "def f(a,b,c,d,e,f,g,h,i,j,k):\n"
        source += "".join(f"  if {chr(97+i)}: pass\n" for i in range(12))
        py = tmp_path / "complex.py"
        py.write_text(source)
        ctx = _make_ctx(tmp_path, monkeypatch, file_path=str(py),
                        config={"gates": {"complexity": {
                            "enabled": True, "max_cyclomatic": 5, "max_cognitive": 5,
                            "mode": "advisory"}}})
        result = run_check(ctx)
        assert result.decision == Decision.ADVISORY

    def test_enforce_mode_blocks(self, tmp_path, monkeypatch):
        source = "def f(a,b,c,d,e):\n"
        source += "".join(f"  if {chr(97+i)}: pass\n" for i in range(12))
        py = tmp_path / "complex.py"
        py.write_text(source)
        ctx = _make_ctx(tmp_path, monkeypatch, file_path=str(py),
                        config={"gates": {"complexity": {
                            "enabled": True, "max_cyclomatic": 5, "max_cognitive": 5,
                            "mode": "enforce"}}})
        result = run_check(ctx)
        assert result.decision == Decision.BLOCK

    def test_disabled_gate_allows(self, tmp_path, monkeypatch):
        py = tmp_path / "x.py"
        py.write_text("def f():\n" + "  if True: pass\n" * 20)
        ctx = _make_ctx(tmp_path, monkeypatch, file_path=str(py),
                        config={"gates": {"complexity": {"enabled": False}}})
        result = run_check(ctx)
        assert result.decision == Decision.ALLOW


def _make_ctx(tmp_path, monkeypatch, file_path="", config=None):
    monkeypatch.chdir(tmp_path)
    inp = HookInput(
        hook_event_name="PostToolUse",
        tool_name="Write",
        tool_input={"file_path": file_path},
        cwd=tmp_path,
        session_id="test",
        raw={},
    )
    return HookContext(
        input=inp,
        config=config or {"gates": {"complexity": {"enabled": True, "max_cyclomatic": 10, "max_cognitive": 15, "mode": "advisory"}}},
        plugin_root=tmp_path,
        hook_start_monotonic=0.0,
        global_deadline_monotonic=9999.0,
    )
