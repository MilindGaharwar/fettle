"""WP-H — Function Complexity Limits.

PostToolUse(Write|Edit) check for cyclomatic and cognitive complexity
of modified Python functions. Stdlib ast only, no external deps.
"""

from __future__ import annotations

import ast
import os
import time


def _cyclomatic(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Cyclomatic complexity: count decision points + 1."""
    score = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node:
            continue
        if isinstance(child, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While)):
            score += 1
        elif isinstance(child, (ast.ExceptHandler, ast.match_case)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += len(child.values) - 1
        elif isinstance(child, ast.comprehension):
            score += 1 + len(child.ifs)
    return score


def _cognitive(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Cognitive complexity: nesting-penalized score."""
    score = 0

    def _walk(body: list[ast.stmt], depth: int) -> None:
        nonlocal score
        for stmt in body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(stmt, ast.If):
                score += 1 + depth
                _walk(stmt.body, depth + 1)
                elif_node = stmt
                while elif_node.orelse:
                    if len(elif_node.orelse) == 1 and isinstance(elif_node.orelse[0], ast.If):
                        elif_node = elif_node.orelse[0]
                        score += 1 + depth
                        _walk(elif_node.body, depth + 1)
                    else:
                        _walk(elif_node.orelse, depth + 1)
                        break
            elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
                score += 1 + depth
                _walk(stmt.body, depth + 1)
                if stmt.orelse:
                    _walk(stmt.orelse, depth + 1)
            elif isinstance(stmt, ast.Try):
                _walk(stmt.body, depth)
                for handler in stmt.handlers:
                    score += 1 + depth
                    _walk(handler.body, depth + 1)
                if stmt.orelse:
                    _walk(stmt.orelse, depth)
                if stmt.finalbody:
                    _walk(stmt.finalbody, depth)
            elif isinstance(stmt, ast.Match):
                for case in stmt.cases:
                    score += 1 + depth
                    _walk(case.body, depth + 1)
            elif isinstance(stmt, (ast.With, ast.AsyncWith)):
                _walk(stmt.body, depth)
            else:
                for child in ast.iter_child_nodes(stmt):
                    if isinstance(child, ast.BoolOp):
                        score += len(child.values) - 1
                    elif isinstance(child, ast.IfExp):
                        score += 1 + depth
                if isinstance(stmt, (ast.Break, ast.Continue)):
                    score += 1

    _walk(node.body, 0)
    return score


def analyze_functions(
    tree: ast.Module,
    changed_lines: set[int] | None,
) -> list[dict]:
    """Analyze complexity of modified functions. Returns findings."""
    findings: list[dict] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        start = node.lineno
        if node.decorator_list:
            start = min(d.lineno for d in node.decorator_list)
        end = node.end_lineno or node.lineno

        if changed_lines is not None:
            if not changed_lines.intersection(range(start, end + 1)):
                continue

        cyc = _cyclomatic(node)
        cog = _cognitive(node)
        findings.append({
            "name": node.name,
            "lineno": node.lineno,
            "end_lineno": end,
            "cyclomatic": cyc,
            "cognitive": cog,
        })

    return findings


def run_check(ctx):
    """Dispatcher-compatible entry point for complexity checking."""
    from fettle.dispatcher_types import CheckResult

    file_path = ctx.tool_input.get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return CheckResult.allow()

    if not os.path.isfile(file_path):
        return CheckResult.allow()

    cfg = ctx.config.get("gates", {}).get("complexity", {})
    if not cfg.get("enabled", True):
        return CheckResult.allow()

    max_cyc = int(cfg.get("max_cyclomatic", 10))
    max_cog = int(cfg.get("max_cognitive", 15))
    enforce = cfg.get("enforce", False)

    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            source = f.read()
        tree = ast.parse(source)
    except (OSError, SyntaxError):
        return CheckResult.allow()

    from fettle.lean_sniffers import _get_changed_lines
    cwd = str(ctx.cwd)
    changed_lines = _get_changed_lines(file_path, cwd)

    # Honor dispatcher budget
    if getattr(ctx, "check_deadline_monotonic", 0) and time.monotonic() >= ctx.check_deadline_monotonic:
        return CheckResult.allow()

    func_results = analyze_functions(tree, changed_lines)
    violations: list[str] = []

    for fr in func_results:
        reasons = []
        if max_cyc > 0 and fr["cyclomatic"] > max_cyc:
            reasons.append(f"cyclomatic {fr['cyclomatic']}/{max_cyc}")
        if max_cog > 0 and fr["cognitive"] > max_cog:
            reasons.append(f"cognitive {fr['cognitive']}/{max_cog}")
        if reasons:
            basename = os.path.basename(file_path)
            violations.append(f"{basename}:{fr['lineno']} {fr['name']}() — {', '.join(reasons)}")

    if not violations:
        return CheckResult.allow()

    msg = "Complexity limits exceeded:\n" + "\n".join(f"  {v}" for v in violations[:5])
    if enforce:
        return CheckResult.block(msg, hook_specific_output={
            "hookEventName": ctx.input.hook_event_name,
            "additionalContext": msg,
        })
    return CheckResult.advisory(msg, hook_specific_output={
        "hookEventName": ctx.input.hook_event_name,
        "additionalContext": msg,
    })
