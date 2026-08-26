"""P34 mutation testing with bounded, fail-visible mutmut evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shlex
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from fettle import __version__
from fettle.evidence import EvidenceArtifact

MUTMUT_VERSION = "2.5.1"
_STATES = ("killed", "survived", "timeout", "suspicious", "untested", "skipped")
_CACHE_STATES = {
    "ok_killed": "killed",
    "bad_survived": "survived",
    "bad_timeout": "timeout",
    "ok_suspicious": "suspicious",
    "untested": "untested",
    "skipped": "skipped",
}
_ENV = {
    **os.environ,
    "PATH": os.pathsep.join((
        str(Path(sys.executable).parent),
        os.path.expanduser("~/.local/bin"),
        os.environ.get("PATH", ""),
    )),
}
_STABILITY_RUNTIME_MS = 35 * 60 * 1000
_TEST_RUNNER = "python -m pytest -x --assert=plain {mapped_tests}"
_MAX_SHOW_BYTES = 50 * 1024 * 1024
_PARTITION_SCHEMA_VERSION = "1"
_MUTATION_CACHE_SCHEMA_VERSION = "1"
_CHECKPOINT_SCHEMA_VERSION = "1"
_MUTATION_WATCH_NAMES = (
    ".fettle.toml", "pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini",
    "uv.lock", "poetry.lock", "Pipfile.lock", "requirements.txt", "requirements-dev.txt",
)
_MUTATION_CACHE_DIR = Path(".fettle/mutation-cache")


def _run(argv: list[str], root: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=root, env=_ENV, capture_output=True, text=True, timeout=timeout)


def _bounded(text: str) -> str:
    return text.strip()[-2000:]


def _error(status: str, message: str, **evidence) -> dict:
    return {"status": status, "message": message, "score": None, "passed": False, **evidence}


def _get_changed_py_files(root: str, paths: list[str], base: str) -> dict:
    """Select existing implementation files against an explicit merge base."""
    try:
        merge_base = _run(["git", "merge-base", base, "HEAD"], root, 10)
        if merge_base.returncode or not merge_base.stdout.strip():
            return _error("unknown", "Cannot resolve merge base: " + _bounded(merge_base.stderr))
        sha = merge_base.stdout.strip()
        diff = _run(["git", "diff", "--name-status", "-M", sha, "HEAD", "--"], root, 10)
    except subprocess.TimeoutExpired:
        return _error("unknown", "Git change selection timed out")
    except OSError as exc:
        return _error("tool_error", f"Git change selection failed: {exc}")

    if diff.returncode:
        return _error("unknown", "Cannot select changed files: " + _bounded(diff.stderr))
    selected: set[str] = set()
    deleted: set[str] = set()
    for line in diff.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            return _error("unknown", "Unrecognized git --name-status output")
        status, path = parts[0][:1], parts[-1]
        if not path.endswith(".py") or (paths and not any(path.startswith(item) for item in paths)):
            continue
        if status == "D":
            deleted.add(path)
        elif status in {"A", "M", "R", "C"} and (Path(root) / path).is_file():
            selected.add(path)
    return {"status": "completed", "merge_base": sha, "files": sorted(selected), "deleted": sorted(deleted)}


def _get_all_py_files(root: str, paths: list[str]) -> list[str]:
    root_path = Path(root)
    files: set[str] = set()
    for item in paths:
        target = root_path / item
        if target.is_file() and target.suffix == ".py":
            files.add(target.relative_to(root_path).as_posix())
        elif target.is_dir():
            files.update(path.relative_to(root_path).as_posix() for path in target.rglob("*.py") if path.is_file())
    return sorted(files)


def _shard_files(root: str, files: list[str], index: int, count: int) -> list[str]:
    """Partition files deterministically while balancing source byte size."""
    if count < 1 or not 0 <= index < count:
        raise ValueError("shard index must be within shard count")
    if not files:
        raise ValueError("cannot shard an empty file list")
    shards: list[list[str]] = [[] for _ in range(count)]
    sizes = [0] * count
    ordered = sorted(files, key=lambda path: (-(Path(root) / path).stat().st_size, path))
    for path in ordered:
        target = min(range(count), key=lambda item: (sizes[item], item))
        shards[target].append(path)
        sizes[target] += (Path(root) / path).stat().st_size
    return sorted(shards[index])


def _shard_ranges(
    root: str,
    files: list[str],
    index: int,
    count: int,
    default_chunk_lines: int = 60,
    chunk_lines: dict[str, int] | None = None,
    test_mappings: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Partition source lines exactly once, balancing mapped-test execution cost."""
    if count < 1 or not 0 <= index < count:
        raise ValueError("shard index must be within shard count")
    mapping = _mapped_tests(root, files, test_mappings)
    test_weights = {
        file: max(1, sum((Path(root) / test).stat().st_size for test in tests))
        for file, tests in mapping.items()
    }
    chunks: list[tuple[dict, int]] = []
    for file in files:
        line_count = len((Path(root) / file).read_text(encoding="utf-8").splitlines())
        chunk_size = (chunk_lines or {}).get(file, default_chunk_lines)
        for start in range(1, line_count + 1, chunk_size):
            chunk = {"file": file, "start": start, "end": min(start + chunk_size - 1, line_count)}
            chunks.append((chunk, (chunk["end"] - chunk["start"] + 1) * test_weights[file]))
    if len(chunks) < count:
        raise ValueError("shard count exceeds source range count")
    shards: list[list[dict]] = [[] for _ in range(count)]
    weights = [0] * count
    file_chunks = [{file: 0 for file in files} for _ in range(count)]
    for chunk, weight in sorted(chunks, key=lambda item: (-item[1], item[0]["file"], item[0]["start"])):
        target = min(range(count), key=lambda item: (file_chunks[item][chunk["file"]], weights[item], item))
        shards[target].append(chunk)
        weights[target] += weight
        file_chunks[target][chunk["file"]] += 1
    return sorted(shards[index], key=lambda item: (item["file"], item["start"]))


def _patch_for_ranges(root: str, ranges: list[dict]) -> str:
    """Create a parse-only unified diff whose added lines whitelist mutation locations."""
    root_path = Path(root)
    sections: list[str] = []
    for item in ranges:
        lines = (root_path / item["file"]).read_text(encoding="utf-8").splitlines()
        selected = lines[item["start"] - 1:item["end"]]
        sections.extend([
            f"--- a/{item['file']}",
            f"+++ b/{item['file']}",
            f"@@ -{item['start']},0 +{item['start']},{len(selected)} @@",
            *["+" + line for line in selected],
        ])
    return "\n".join(sections) + "\n"


def _mapped_tests(
    root: str,
    files: list[str],
    test_mappings: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Map each production module to convention and direct-import tests."""
    root_path = Path(root)
    test_paths = sorted((root_path / "tests").glob("test_*.py"))
    imports: dict[str, set[str]] = {}
    for test_path in test_paths:
        relative = test_path.relative_to(root_path).as_posix()
        try:
            tree = ast.parse(test_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.setdefault(alias.name, set()).add(relative)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.setdefault(node.module, set()).add(relative)
                for alias in node.names:
                    imports.setdefault(f"{node.module}.{alias.name}", set()).add(relative)

    mapped: dict[str, list[str]] = {}
    for file in files:
        module = file.removesuffix(".py").replace("/", ".")
        if module.endswith(".__init__"):
            module = module.removesuffix(".__init__")
        matches = set(imports.get(module, set())) | set((test_mappings or {}).get(file, []))
        stem = Path(file).stem
        if stem not in {"__init__", "__main__"}:
            candidate = root_path / "tests" / f"test_{stem}.py"
            if candidate.is_file():
                matches.add(candidate.relative_to(root_path).as_posix())
        mapped[file] = sorted(matches)
    return mapped


def _has_mutmut() -> bool:
    return shutil.which("mutmut", path=_ENV["PATH"]) is not None


def _parse_result_ids(output: str) -> list[str]:
    output = output.strip()
    if not output:
        return []
    if not re.fullmatch(r"\d+(?: \d+)*", output):
        raise ValueError("unrecognized mutmut result-ids output")
    return output.split()


def _canonical_path(path: str) -> str:
    path = unicodedata.normalize("NFC", path.replace("\\", "/"))
    if path.startswith("/") or re.match(r"^[A-Za-z]:/", path) or any(part == ".." for part in path.split("/")):
        raise ValueError("mutation path is outside the repository")
    path = path.removeprefix("a/").removeprefix("b/")
    if not path or path.startswith("/"):
        raise ValueError("mutation path is invalid")
    return path


def _mutation_hunks(lines: list[str]) -> list[dict]:
    indexes = [index for index, line in enumerate(lines) if line.startswith("@@ ")]
    if not indexes or indexes[0] != 2:
        raise ValueError("mutation detail must contain valid hunks")
    hunks = []
    for position, index in enumerate(indexes):
        match = re.fullmatch(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*", lines[index])
        if not match:
            raise ValueError("mutation detail must contain valid hunks")
        body = lines[index + 1:indexes[position + 1] if position + 1 < len(indexes) else len(lines)]
        if any(line and line[0] not in " +-\\" for line in body):
            raise ValueError("mutation detail contains malformed hunk lines")
        old = [unicodedata.normalize("NFC", line[1:]) for line in body if line.startswith((" ", "-"))]
        new = [unicodedata.normalize("NFC", line[1:]) for line in body if line.startswith((" ", "+"))]
        old_count = int(match.group(2) or 1)
        new_count = int(match.group(4) or 1)
        synthetic_eof_blank = (
            old[-1:] == new[-1:] == [""]
            and len(old) == old_count + 1
            and len(new) == new_count + 1
        )
        if (len(old) != old_count or len(new) != new_count) and not synthetic_eof_blank:
            raise ValueError("mutation detail hunk size does not match its header")
        old_start = int(match.group(1))
        if old and old_start < 1:
            raise ValueError("mutation detail hunk start is invalid")
        hunks.append({"old_start": old_start, "old": old, "new": new})
    return hunks


def _parse_mutation_diff(diff: str, expected_file: str | None = None) -> tuple[str, list[str], list[str]]:
    lines = diff.splitlines()
    if len(lines) < 4 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
        raise ValueError("mutation detail is not a unified diff")
    old_file = _canonical_path(lines[0][4:].split("\t", 1)[0])
    new_file = _canonical_path(lines[1][4:].split("\t", 1)[0])
    if old_file != new_file or (expected_file is not None and old_file != _canonical_path(expected_file)):
        raise ValueError("mutation detail path does not match its source file")
    _mutation_hunks(lines)
    removed = [line[1:] for line in lines[3:] if line.startswith("-")]
    added = [line[1:] for line in lines[3:] if line.startswith("+")]
    if not removed and not added:
        raise ValueError("mutation detail has no change")
    return old_file, removed, added


def _apply_multi_hunk_diff(source: str, diff: str) -> tuple[str, int]:
    source_lines = source.splitlines()
    edits: list[tuple[int, list[str], list[str]]] = []
    for hunk in _mutation_hunks(diff.splitlines()):
        old, new = hunk["old"], hunk["new"]
        start = hunk["old_start"] - 1 if old else hunk["old_start"]
        if start > len(source_lines) or start + len(old) > len(source_lines):
            raise ValueError("mutation hunk is outside source")
        if source_lines[start:start + len(old)] != old:
            raise ValueError("mutation hunk does not match source")
        prefix = 0
        while prefix < min(len(old), len(new)) and old[prefix] == new[prefix]:
            prefix += 1
        suffix = 0
        while (
            suffix < min(len(old) - prefix, len(new) - prefix)
            and old[len(old) - suffix - 1] == new[len(new) - suffix - 1]
        ):
            suffix += 1
        removed = old[prefix:len(old) - suffix if suffix else None]
        added = new[prefix:len(new) - suffix if suffix else None]
        edit = (start + prefix, removed, added)
        if removed or added:
            edits.append(edit)
    canonical_edits = [(start, tuple(old), tuple(new)) for start, old, new in edits]
    if len(canonical_edits) != len(set(canonical_edits)):
        raise ValueError("mutation hunks contain duplicate edits")
    ordered = sorted(canonical_edits)
    for previous, current in zip(ordered, ordered[1:]):
        if previous[0] + len(previous[1]) > current[0]:
            raise ValueError("mutation hunks contain conflicting edits")
    for start, old, new in reversed(ordered):
        source_lines[start:start + len(old)] = new
    if not ordered:
        raise ValueError("mutation detail has no change")
    mutated = "\n".join(source_lines) + ("\n" if source.endswith("\n") else "")
    return mutated, ordered[0][0] + 1


def _parse_show_all(output: str, expected_ids: set[str], max_bytes: int = _MAX_SHOW_BYTES) -> dict[str, str]:
    if len(output.encode("utf-8")) > max_bytes:
        raise ValueError("mutmut show output is too large")
    markers = list(re.finditer(r"(?m)^# mutant (\d+)\s*$", output))
    records: dict[str, str] = {}
    for index, marker in enumerate(markers):
        engine_id = marker.group(1)
        if engine_id in records:
            raise ValueError(f"duplicate mutation detail for engine ID {engine_id}")
        end = markers[index + 1].start() if index + 1 < len(markers) else len(output)
        detail = output[marker.end():end].strip("\n")
        summary = re.search(
            r"(?m)^(?:Timed out .*|Suspicious .*|Survived .*|Untested/skipped) \(\d+\)\n\n"
            r"---- [^\n]+ \(\d+\) ----$",
            detail,
        )
        records[engine_id] = detail[:summary.start()].strip("\n") + "\n" if summary else detail + "\n"
    missing = sorted(expected_ids - set(records), key=int)
    if missing:
        raise ValueError(f"mutation details are missing: {missing}")
    return {engine_id: records[engine_id] for engine_id in expected_ids}


def _find_replacement(
    source: str,
    removed: list[str],
    added: list[str],
    preferred_line: int | None = None,
) -> tuple[str, int]:
    source_lines = source.splitlines()
    matches = [
        index for index in range(len(source_lines) - len(removed) + 1)
        if source_lines[index:index + len(removed)] == removed
    ]
    if len(matches) > 1 and preferred_line is not None:
        distance = min(abs(index + 1 - preferred_line) for index in matches)
        matches = [index for index in matches if abs(index + 1 - preferred_line) == distance]
    if len(matches) != 1:
        raise ValueError("mutation replacement cannot be located uniquely")
    index = matches[0]
    mutated = source_lines[:index] + added + source_lines[index + len(removed):]
    return "\n".join(mutated) + ("\n" if source.endswith("\n") else ""), index + 1


def _find_insertion(source: str, diff: str, added: list[str], preferred_line: int) -> tuple[str, int]:
    source_lines = source.splitlines()
    body = diff.splitlines()[3:]
    old_hunk = [line[1:] for line in body if line.startswith((" ", "-"))]
    insertion_offset = sum(line.startswith((" ", "-")) for line in body[:next(
        index for index, line in enumerate(body) if line.startswith("+")
    )])
    if not old_hunk:
        raise ValueError("mutation insertion cannot be anchored uniquely")
    matches = [
        index for index in range(len(source_lines) - len(old_hunk) + 1)
        if source_lines[index:index + len(old_hunk)] == old_hunk
    ]
    if len(matches) > 1:
        distance = min(abs(index + 1 - preferred_line) for index in matches)
        matches = [index for index in matches if abs(index + 1 - preferred_line) == distance]
    if len(matches) != 1:
        raise ValueError("mutation insertion cannot be anchored uniquely")
    index = matches[0] + insertion_offset
    mutated = source_lines[:index] + added + source_lines[index:]
    return "\n".join(mutated) + ("\n" if source.endswith("\n") else ""), index + 1


def _enclosing_symbol(tree: ast.AST, line: int) -> ast.AST:
    candidates = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.lineno <= line <= getattr(node, "end_lineno", node.lineno)
    ]
    return min(candidates, key=lambda node: getattr(node, "end_lineno", node.lineno) - node.lineno) if candidates else tree


def _symbol_name(tree: ast.AST, node: ast.AST) -> str:
    if node is tree:
        return "<module>"
    parents = [
        candidate for candidate in ast.walk(tree)
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and candidate.lineno <= node.lineno
        and getattr(candidate, "end_lineno", candidate.lineno) >= getattr(node, "end_lineno", node.lineno)
    ]
    parents.sort(key=lambda candidate: (candidate.lineno, -getattr(candidate, "end_lineno", candidate.lineno)))
    return ".".join(unicodedata.normalize("NFC", candidate.name) for candidate in parents)


def _ast_difference(before: ast.AST, after: ast.AST, path: tuple[str, ...] = ()) -> tuple[ast.AST, ast.AST, tuple[str, ...]]:
    if type(before) is not type(after):
        return before, after, path
    differences: list[tuple[ast.AST, ast.AST, tuple[str, ...]]] = []
    for field in before._fields:
        old_value, new_value = getattr(before, field), getattr(after, field)
        if isinstance(old_value, ast.AST) and isinstance(new_value, ast.AST):
            if ast.dump(old_value, include_attributes=False) != ast.dump(new_value, include_attributes=False):
                differences.append(_ast_difference(old_value, new_value, (*path, field)))
        elif isinstance(old_value, list) and isinstance(new_value, list) and len(old_value) == len(new_value):
            for old_item, new_item in zip(old_value, new_value, strict=True):
                if isinstance(old_item, ast.AST) and isinstance(new_item, ast.AST):
                    if ast.dump(old_item, include_attributes=False) != ast.dump(new_item, include_attributes=False):
                        anchor = f"{field}:{type(old_item).__name__}"
                        differences.append(_ast_difference(old_item, new_item, (*path, anchor)))
                elif old_item != new_item:
                    return before, after, path
        elif old_value != new_value:
            return before, after, path
    if len(differences) != 1:
        return before, after, path
    old_node, new_node, child_path = differences[0]
    if isinstance(old_node, (ast.operator, ast.unaryop, ast.boolop, ast.cmpop)):
        return before, after, path
    return old_node, new_node, child_path


def _fingerprint_digest(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _canonical_digest(value: object) -> str:
    content = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()


def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def merge_mutation_checkpoints(checkpoints: list[dict], expected_fingerprints: set[str]) -> dict:
    """Merge compatible terminal evidence while leaving failed attempts pending."""
    if not checkpoints:
        raise ValueError("at least one mutation checkpoint is required")
    first = checkpoints[0]
    required = {"schema_version", "calibration_id", "identity", "outcomes", "attempts"}
    allowed = required | {"status", "pending"}
    if not required <= set(first) <= allowed or first.get("schema_version") != _CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("mutation checkpoint has an unsupported schema")
    calibration_id = first.get("calibration_id")
    identity = first.get("identity")
    if not isinstance(calibration_id, str) or not calibration_id or not isinstance(identity, dict):
        raise ValueError("mutation checkpoint identity is incomplete")
    outcomes: dict[str, dict] = {}
    attempts: list[dict] = []
    seen_attempts: set[str] = set()
    terminal_states = set(_STATES) - {"untested"}
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict) or not required <= set(checkpoint) <= allowed:
            raise ValueError("mutation checkpoint has an unsupported schema")
        if checkpoint.get("schema_version") != _CHECKPOINT_SCHEMA_VERSION:
            raise ValueError("mutation checkpoint has an unsupported schema")
        if checkpoint.get("calibration_id") != calibration_id:
            raise ValueError("mutation checkpoints belong to different calibrations")
        if checkpoint.get("identity") != identity:
            raise ValueError("mutation checkpoint identity differs")
        checkpoint_outcomes = checkpoint.get("outcomes")
        checkpoint_attempts = checkpoint.get("attempts")
        if not isinstance(checkpoint_outcomes, dict) or not isinstance(checkpoint_attempts, list):
            raise ValueError("mutation checkpoint evidence is malformed")
        for fingerprint, outcome in checkpoint_outcomes.items():
            if fingerprint not in expected_fingerprints:
                raise ValueError("mutation checkpoint contains a fingerprint outside its corpus")
            if (
                not isinstance(outcome, dict)
                or outcome.get("state") not in terminal_states
                or not isinstance(outcome.get("duration_ms"), int)
                or isinstance(outcome.get("duration_ms"), bool)
                or outcome["duration_ms"] < 0
            ):
                raise ValueError("mutation checkpoint outcome is malformed")
            previous = outcomes.get(fingerprint)
            if previous is not None and previous["state"] != outcome["state"]:
                raise ValueError("mutation checkpoints contain conflicting terminal outcomes")
            if previous is None or outcome["duration_ms"] < previous["duration_ms"]:
                outcomes[fingerprint] = dict(outcome)
        for attempt in checkpoint_attempts:
            if not isinstance(attempt, dict) or attempt.get("fingerprint") not in expected_fingerprints:
                raise ValueError("mutation checkpoint attempt is outside its corpus")
            if attempt.get("status") not in {"completed", "execution_error"}:
                raise ValueError("mutation checkpoint attempt is malformed")
            digest = _canonical_digest(attempt)
            if digest not in seen_attempts:
                attempts.append(dict(attempt))
                seen_attempts.add(digest)
    pending = len(expected_fingerprints - outcomes.keys())
    return {
        "schema_version": _CHECKPOINT_SCHEMA_VERSION,
        "calibration_id": calibration_id,
        "identity": identity,
        "outcomes": outcomes,
        "attempts": attempts,
        "status": "completed" if pending == 0 else "incomplete",
        "pending": pending,
    }


def pending_mutation_records(corpus: list[dict], checkpoint: dict) -> list[dict]:
    """Select canonical corpus records that lack a terminal outcome."""
    outcomes = checkpoint.get("outcomes")
    if not isinstance(outcomes, dict):
        raise ValueError("mutation checkpoint outcomes are malformed")
    fingerprints = [record.get("fingerprint") for record in corpus if isinstance(record, dict)]
    if len(fingerprints) != len(corpus) or len(fingerprints) != len(set(fingerprints)):
        raise ValueError("mutation corpus fingerprints are incomplete or duplicated")
    if not set(outcomes) <= set(fingerprints):
        raise ValueError("mutation checkpoint contains a fingerprint outside its corpus")
    return sorted(
        (record for record in corpus if record["fingerprint"] not in outcomes),
        key=lambda record: record["fingerprint"],
    )


def execute_pending_mutations(
    root: str,
    corpus: list[dict],
    mapping: dict[str, list[str]],
    line_ranges: list[dict],
    checkpoint: dict,
    timeout: int,
    checkpoint_path: Path | None = None,
) -> dict:
    """Execute only pending canonical mutants after verifying current local IDs."""
    expected = {record["fingerprint"] for record in corpus}
    merged = merge_mutation_checkpoints([checkpoint], expected)
    if checkpoint_path is not None:
        _write_json_atomic(checkpoint_path, merged)
    started = time.monotonic()
    for file in sorted(mapping):
        file_pending = [record for record in pending_mutation_records(corpus, merged) if record["file"] == file]
        if not file_pending:
            continue
        ranges = [item for item in line_ranges if item["file"] == file]
        remaining = timeout - int(time.monotonic() - started)
        if remaining < 1:
            break
        generated = _preflight_mutmut(
            root, [file], mapping[file], {file: mapping[file]}, remaining, ranges,
        )
        if generated.get("status") != "completed":
            break
        current = {record["fingerprint"]: record for record in generated.get("corpus", [])}
        file_expected = {record["fingerprint"] for record in corpus if record["file"] == file}
        if set(current) != file_expected:
            raise ValueError(f"regenerated mutation corpus differs for {file}")
        for record in file_pending:
            remaining = timeout - int(time.monotonic() - started)
            if remaining < 1:
                break
            engine_id = current[record["fingerprint"]].get("locator", {}).get("engine_id")
            attempt_started = time.monotonic()
            try:
                run = _run([
                    "mutmut", "run", engine_id, "--test-time-base", str(timeout), "--runner",
                    "python -m pytest -x --assert=plain " + shlex.join(mapping[file]),
                ], root, remaining)
                if run.returncode < 0 or run.returncode & 1 or run.returncode & ~15:
                    raise OSError(f"mutmut exited with {run.returncode}")
                ids, error = _collect_range_results(root, ranges, MUTMUT_VERSION, run.returncode)
                if error:
                    raise OSError(error["message"])
                if ids is None:
                    raise OSError("mutmut did not return mutation results")
                observed = [state for state in _STATES if engine_id in ids[state]]
                if len(observed) != 1 or observed[0] == "untested":
                    raise OSError("mutmut did not produce one terminal outcome")
                duration_ms = round((time.monotonic() - attempt_started) * 1000)
                merged["outcomes"][record["fingerprint"]] = {
                    "state": observed[0], "duration_ms": duration_ms,
                }
                merged["attempts"].append({
                    "fingerprint": record["fingerprint"], "status": "completed",
                    "state": observed[0], "duration_ms": duration_ms,
                })
                merged["pending"] = len(expected - merged["outcomes"].keys())
                merged["status"] = "completed" if merged["pending"] == 0 else "incomplete"
                if checkpoint_path is not None:
                    _write_json_atomic(checkpoint_path, merged)
            except (OSError, subprocess.TimeoutExpired) as exc:
                merged["attempts"].append({
                    "fingerprint": record["fingerprint"], "status": "execution_error",
                    "message": str(exc),
                })
                if checkpoint_path is not None:
                    _write_json_atomic(checkpoint_path, merged)
                break
        if any(
            attempt["status"] == "execution_error"
            for attempt in merged["attempts"][-len(file_pending):]
        ):
            break
    merged["pending"] = len(expected - merged["outcomes"].keys())
    merged["status"] = "completed" if merged["pending"] == 0 else "incomplete"
    if checkpoint_path is not None:
        _write_json_atomic(checkpoint_path, merged)
    return merged


def report_from_mutation_checkpoint(corpus: list[dict], checkpoint: dict) -> dict:
    """Derive outcome counts and public non-killed evidence from a complete ledger."""
    if checkpoint.get("status") != "completed" or checkpoint.get("pending") != 0:
        raise ValueError("mutation checkpoint is incomplete")
    outcomes = checkpoint.get("outcomes", {})
    fingerprints = {record["fingerprint"] for record in corpus}
    if set(outcomes) != fingerprints:
        raise ValueError("mutation checkpoint does not exactly cover its corpus")
    counts = {state: 0 for state in _STATES}
    records = []
    for record in corpus:
        state = outcomes[record["fingerprint"]]["state"]
        counts[state] += 1
        if state != "killed":
            records.append({**record, "state": state})
    return {
        **counts,
        "non_killed": sorted(records, key=lambda record: record["fingerprint"]),
        "duration_ms": sum(outcome["duration_ms"] for outcome in outcomes.values()),
    }


def run_resumable_mutation_shard(
    root: str,
    cfg: dict,
    manifest_path: Path,
    preflight_path: Path,
    calibration_id: str,
    checkpoint_path: Path,
    timeout: int,
    resume_paths: list[Path] | None = None,
) -> dict:
    """Resume one manifest-bound calibration shard from compatible checkpoints."""
    try:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", calibration_id):
            raise ValueError("calibration ID must use 1-64 letters, numbers, hyphens, or underscores")
        manifest = load_partition_manifest(manifest_path)
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        if not isinstance(preflight, dict) or preflight.get("status") != "completed":
            raise ValueError("retained mutation preflight is not completed")
        if preflight.get("revision") != manifest["revision"]:
            raise ValueError("retained mutation preflight revision differs from manifest")
        aggregate_corpus = preflight.get("corpus")
        declared_fingerprints = preflight.get("fingerprints")
        if not isinstance(aggregate_corpus, list) or not isinstance(declared_fingerprints, list):
            raise ValueError("retained mutation preflight corpus is malformed")
        sorted_corpus = sorted(aggregate_corpus, key=lambda record: record.get("fingerprint", "") if isinstance(record, dict) else "")
        aggregate_fingerprints = [
            record.get("fingerprint") for record in sorted_corpus if isinstance(record, dict)
        ]
        if (
            len(aggregate_fingerprints) != len(aggregate_corpus)
            or aggregate_fingerprints != sorted(declared_fingerprints)
            or preflight.get("corpus_digest") != _canonical_digest(sorted_corpus)
        ):
            raise ValueError("retained mutation preflight corpus digest differs")
        manifest_digests = preflight.get("manifest_digests")
        if (
            not isinstance(manifest_digests, list)
            or len(manifest_digests) != manifest["shard_count"]
            or manifest_digests[manifest["shard_index"]] != manifest["digest"]
        ):
            raise ValueError("retained mutation preflight is not bound to this manifest")
        corpus = [
            record for record in aggregate_corpus
            if isinstance(record, dict) and record.get("shard_index") == manifest["shard_index"]
        ]
        fingerprints = {record.get("fingerprint") for record in corpus}
        if len(fingerprints) != len(corpus) or None in fingerprints:
            raise ValueError("retained mutation preflight shard corpus is malformed")
        mapping = _mapped_tests(root, manifest["files"], cfg.get("test_mappings", {}))
        if any(not tests for tests in mapping.values()):
            raise ValueError("retained mutation preflight shard has unmapped tests")
        environment_identity = _runtime_cache_identity(root, manifest["files"], mapping, cfg)
        if environment_identity is None:
            raise ValueError("mutation execution environment identity is incomplete")
        identity = {
            "revision": manifest["revision"],
            "preflight_digest": _canonical_digest(preflight),
            "manifest_digest": manifest["digest"],
            "corpus_digest": _canonical_digest(sorted(corpus, key=lambda record: record["fingerprint"])),
            "environment_digest": _checkpoint_environment_digest(environment_identity),
        }
        checkpoints = []
        for path in resume_paths or []:
            checkpoints.append(json.loads(path.read_text(encoding="utf-8")))
        if checkpoints:
            checkpoint = merge_mutation_checkpoints(checkpoints, fingerprints)
            if checkpoint["calibration_id"] != calibration_id or checkpoint["identity"] != identity:
                raise ValueError("resume checkpoint identity differs from this calibration")
        else:
            checkpoint = {
                "schema_version": _CHECKPOINT_SCHEMA_VERSION,
                "calibration_id": calibration_id,
                "identity": identity,
                "outcomes": {},
                "attempts": [],
            }
        result = execute_pending_mutations(
            root, corpus, mapping, manifest["ranges"], checkpoint, timeout, checkpoint_path,
        )
        if result["status"] != "completed":
            return result
        outcome_report = report_from_mutation_checkpoint(corpus, result)
        for engine_id, record in enumerate(outcome_report["non_killed"], start=1):
            record["engine_id"] = str(engine_id)
            record["rerun_command"] = shlex.join([
                "mutmut", "run", record["locator"]["engine_id"],
            ])
        policy = evaluate_policy(outcome_report, cfg)
        return {
            "schema_version": "2", "status": "completed",
            "revision": manifest["revision"], "merge_base": None, "selection": "shard",
            "files_tested": manifest["files"], "deleted_files": [],
            "engine_version": MUTMUT_VERSION, "test_runner": _TEST_RUNNER,
            "tests_run": sorted({test for tests in mapping.values() for test in tests}),
            "line_ranges": manifest["ranges"], "shard_index": manifest["shard_index"],
            "shard_count": manifest["shard_count"], **outcome_report, **policy,
            "threshold": float(cfg.get("score_target", 70)),
        }
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return _error("unknown", f"Cannot resume mutation shard: {exc}")


def write_timeout_evidence(path: Path, timeout_s: int, manifest: dict | None = None) -> None:
    identity = {}
    if manifest is not None:
        identity = {
            "revision": manifest["revision"],
            "shard_index": manifest["shard_index"],
            "shard_count": manifest["shard_count"],
        }
    _write_json_atomic(path, _error(
        "tool_error", f"Mutation execution exceeded its {timeout_s}s deadline",
        partial=True, **identity,
    ))


def format_github_summary(report: dict, artifact_name: str, artifact_url: str) -> str:
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    records = comparison.get("records", [])
    new_survivors = sum(
        record.get("disposition") == "new"
        for record in records if isinstance(records, list) and isinstance(record, dict)
    )
    delta = comparison.get("score_delta")
    delta_text = "n/a" if delta is None else f"{delta:+.1f}"
    lines = [
        "## Mutation evidence", "",
        f"Status: **{report.get('status', 'unknown')}**  ",
        f"Evidence: **{'usable' if report.get('status') == 'completed' else 'unusable'}**  ",
        f"Score: **{report.get('score', 'n/a')}**  ",
        f"Delta: **{delta_text}**  ",
        f"Killed: **{report.get('killed', 0)}**  ",
        f"Survived: **{report.get('survived', 0)}**  ",
        f"New survivors: **{new_survivors}**  ",
        f"Artifact: [{artifact_name}]({artifact_url})",
    ]
    if report.get("message"):
        lines.extend(["", f"Message: {report['message']}"])
    return "\n".join(lines) + "\n"


def build_mutation_cache_identity(
    root: str,
    files: list[str],
    mapping: dict[str, list[str]],
    config: dict,
    *,
    dependencies: list[dict],
    environment: dict[str, str],
    engine_version: str = MUTMUT_VERSION,
) -> dict:
    """Build an exact content identity; incomplete inputs are never cacheable."""
    root_path = Path(root)
    if set(environment) != {"python", "platform"} or any(
        not isinstance(value, str) or not value for value in environment.values()
    ):
        raise ValueError("mutation cache environment identity is incomplete")
    normalized_dependencies = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise ValueError("mutation cache dependency identity is incomplete")
        digest_fields = ("record_digest", "direct_url_digest", "editable_source_digest")
        present_digests = {key: dependency[key] for key in digest_fields if key in dependency}
        if (
            not isinstance(dependency.get("name"), str) or not dependency["name"]
            or not isinstance(dependency.get("version"), str) or not dependency["version"]
            or not present_digests
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for value in present_digests.values())
            or not ({"record_digest", "editable_source_digest"} & present_digests.keys())
            or {"record_digest", "editable_source_digest"} <= present_digests.keys()
        ):
            raise ValueError("mutation cache dependency identity is incomplete")
        normalized_dependencies.append(dependency)

    watched = set(files)
    watched.update(test for tests in mapping.values() for test in tests)
    watched.update(name for name in _MUTATION_WATCH_NAMES if (root_path / name).is_file())
    tests_path = root_path / "tests"
    if tests_path.is_dir():
        watched.update(path.relative_to(root_path).as_posix() for path in tests_path.rglob("conftest.py"))
        fixtures_path = tests_path / "fixtures"
        if fixtures_path.is_dir():
            ignored_fixture_parts = {".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv", "__pycache__"}
            watched.update(
                path.relative_to(root_path).as_posix()
                for path in fixtures_path.rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and not any(part in ignored_fixture_parts for part in path.relative_to(fixtures_path).parts)
            )

    file_digests = {}
    for relative in sorted(watched):
        try:
            canonical = _canonical_path(relative)
            path = root_path / canonical
            if not path.is_file() or not path.resolve().is_relative_to(root_path.resolve()):
                raise OSError("not a repository file")
            file_digests[canonical] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError(f"mutation cache watched file is unreadable: {relative}") from exc

    payload = {
        "engine": {"name": "mutmut", "version": engine_version},
        "environment": environment,
        "files": file_digests,
        "mapping": mapping,
        "config": config,
        "dependencies": sorted(normalized_dependencies, key=lambda item: (item["name"].casefold(), item["version"])),
    }
    return {
        "schema_version": _MUTATION_CACHE_SCHEMA_VERSION,
        "digest": _canonical_digest(payload),
        "inputs": payload,
    }


def _source_tree_digest(root: Path) -> str:
    if not root.is_dir():
        raise ValueError(f"mutation cache editable source is unreadable: {root}")
    ignored = {
        ".fettle", ".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv",
        "__pycache__", ".mutmut-cache", "mutation-manifests", "mutation-preflight-shards",
        "retained-preflight", "resume-checkpoints", "mutation-checkpoint.json", "mutation-report.json",
    }
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.relative_to(root).parts)
    )
    try:
        return _canonical_digest([
            [path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()]
            for path in files
        ])
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"mutation cache editable source is unreadable: {root}") from exc


def collect_mutation_dependency_identities(
    distributions: list[importlib.metadata.Distribution],
) -> list[dict]:
    """Collect installed wheel or editable source identities without guessing."""
    identities = []
    for distribution in distributions:
        name, version = distribution.metadata.get("Name"), distribution.version
        if not name or not version:
            raise ValueError("mutation cache dependency metadata is incomplete")
        direct_url_text = distribution.read_text("direct_url.json")
        identity = {"name": name, "version": version}
        if direct_url_text is not None:
            try:
                direct_url = json.loads(direct_url_text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"mutation cache direct URL metadata is invalid for {name}") from exc
            identity["direct_url_digest"] = hashlib.sha256(direct_url_text.encode()).hexdigest()
        else:
            direct_url = None
        if isinstance(direct_url, dict) and direct_url.get("dir_info", {}).get("editable") is True:
            parsed = urlparse(str(direct_url.get("url", "")))
            if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
                raise ValueError(f"mutation cache editable source is unreadable for {name}")
            identity["editable_source_digest"] = _source_tree_digest(Path(unquote(parsed.path)))
        else:
            record = distribution.read_text("RECORD")
            metadata_path = Path(str(getattr(distribution, "_path", "")))
            if record is None and metadata_path.name.endswith(".egg-info"):
                identity["editable_source_digest"] = _source_tree_digest(metadata_path.parent)
            elif record is None:
                raise ValueError(f"mutation cache dependency {name} has no RECORD")
            else:
                identity["record_digest"] = hashlib.sha256(record.encode()).hexdigest()
        identities.append(identity)
    return sorted(identities, key=lambda item: (item["name"].casefold(), item["version"]))


def mutation_cache_reusable(cache_entry: dict, current_identity: dict) -> bool:
    """Allow reuse only when both identity envelopes are valid and exactly equal."""
    if not isinstance(cache_entry, dict) or not isinstance(current_identity, dict):
        return False
    cached = cache_entry.get("identity")
    for identity in (cached, current_identity):
        if (
            not isinstance(identity, dict)
            or set(identity) != {"schema_version", "digest", "inputs"}
            or identity["schema_version"] != _MUTATION_CACHE_SCHEMA_VERSION
            or not isinstance(identity["inputs"], dict)
            or identity["digest"] != _canonical_digest(identity["inputs"])
        ):
            return False
    return cached == current_identity


def _checkpoint_environment_digest(cache_identity: dict) -> str:
    """Bind execution semantics without installation-instance metadata."""
    inputs = cache_identity["inputs"]
    dependencies = [
        {"name": dependency["name"], "version": dependency["version"]}
        for dependency in inputs["dependencies"]
    ]
    return _canonical_digest({
        "engine": inputs["engine"],
        "environment": inputs["environment"],
        "dependencies": dependencies,
    })


def _read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("cache entry is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(descriptor)


def restore_mutation_native_cache(root: str, current_identity: dict) -> bool:
    """Restore mutmut's native cache only from an exact, regular-file entry."""
    root_path = Path(root)
    cache_dir = root_path / _MUTATION_CACHE_DIR
    identity_path = cache_dir / "identity.json"
    native_path = cache_dir / "mutmut-cache.sqlite"
    try:
        entry = json.loads(_read_regular_file(identity_path).decode("utf-8"))
        if not mutation_cache_reusable(entry, current_identity):
            return False
        data = _read_regular_file(native_path)
        if entry.get("native_digest") != hashlib.sha256(data).hexdigest():
            return False
        fd, temporary = tempfile.mkstemp(dir=str(root_path), prefix=".mutmut-cache.")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, root_path / ".mutmut-cache")
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return True


def save_mutation_native_cache(root: str, identity: dict) -> bool:
    """Atomically retain native mutmut state after successful execution."""
    if not mutation_cache_reusable({"identity": identity}, identity):
        return False
    root_path = Path(root)
    native_path = root_path / ".mutmut-cache"
    cache_dir = root_path / _MUTATION_CACHE_DIR
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = _read_regular_file(native_path)
        metadata = {
            "identity": identity,
            "native_digest": hashlib.sha256(data).hexdigest(),
        }
        for target, content in (
            (cache_dir / "mutmut-cache.sqlite", data),
            (cache_dir / "identity.json", (json.dumps(metadata, sort_keys=True) + "\n").encode()),
        ):
            fd, temporary = tempfile.mkstemp(dir=str(cache_dir), suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, target)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    except OSError:
        return False
    return True


def _runtime_cache_identity(
    root: str,
    files: list[str],
    mapping: dict[str, list[str]],
    cfg: dict,
) -> dict | None:
    try:
        dependencies = collect_mutation_dependency_identities(list(importlib.metadata.distributions()))
        return build_mutation_cache_identity(
            root, files, mapping, cfg, dependencies=dependencies,
            environment={
                "python": platform.python_version(),
                "platform": f"{platform.system()}-{platform.machine()}",
            },
        )
    except (OSError, UnicodeError, ValueError):
        return None


def _revision(root: str) -> str:
    result = _run(["git", "rev-parse", "HEAD"], root, 10)
    revision = result.stdout.strip()
    if result.returncode or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("cannot resolve tested revision")
    return revision


def load_partition_manifest(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot parse mutation partition manifest {path}: {exc}") from exc
    required = {"schema_version", "revision", "shard_index", "shard_count", "files", "ranges", "digest"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema_version") != _PARTITION_SCHEMA_VERSION:
        raise ValueError("mutation partition manifest has an unsupported schema")
    payload = {key: value[key] for key in required - {"digest"}}
    if value["digest"] != _canonical_digest(payload):
        raise ValueError("mutation partition manifest digest does not match content")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", str(value["revision"]))
        or not isinstance(value["shard_index"], int) or isinstance(value["shard_index"], bool)
        or not isinstance(value["shard_count"], int) or isinstance(value["shard_count"], bool)
        or value["shard_count"] < 1 or not 0 <= value["shard_index"] < value["shard_count"]
        or not isinstance(value["files"], list) or value["files"] != sorted(set(value["files"]))
        or not isinstance(value["ranges"], list)
    ):
        raise ValueError("mutation partition manifest contains invalid identity")
    if value["files"] != sorted({item.get("file") for item in value["ranges"] if isinstance(item, dict)}):
        raise ValueError("mutation partition manifest files do not match ranges")
    return value


def write_partition_manifests(root: str, cfg: dict, output_dir: Path) -> list[Path]:
    files = [
        path for path in _get_all_py_files(root, cfg.get("paths", ["src/"]))
        if not any(path.startswith(item) for item in cfg.get("exclude", ["tests/", "migrations/"]))
    ]
    count = int(cfg.get("full_shards", 1))
    if count < 1 or count > 256:
        raise ValueError("mutation full_shards must be between 1 and 256")
    revision = _revision(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        ranges = _shard_ranges(
            root, files, index, count, int(cfg.get("default_chunk_lines", 60)),
            cfg.get("chunk_lines", {}), cfg.get("test_mappings", {}),
        )
        payload = {
            "schema_version": _PARTITION_SCHEMA_VERSION,
            "revision": revision,
            "shard_index": index,
            "shard_count": count,
            "files": sorted({item["file"] for item in ranges}),
            "ranges": ranges,
        }
        path = output_dir / f"partition-{index}.json"
        content = {**payload, "digest": _canonical_digest(payload)}
        path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def write_changed_partition_manifests(
    root: str,
    cfg: dict,
    output_dir: Path,
    base: str,
) -> tuple[list[Path], list[str]]:
    """Write bounded manifests that exactly cover the current changed-file scope."""
    selection = _get_changed_py_files(root, cfg.get("paths", ["src/"]), base)
    if selection["status"] != "completed":
        raise ValueError(selection["message"])
    files = [
        path for path in selection["files"]
        if not any(path.startswith(item) for item in cfg.get("exclude", ["tests/", "migrations/"]))
    ]
    if not files:
        return [], []
    default_chunk_lines = int(cfg.get("default_chunk_lines", 60))
    chunk_lines = cfg.get("chunk_lines", {})
    chunk_count = sum(
        (len((Path(root) / file).read_text(encoding="utf-8").splitlines()) + chunk_lines.get(file, default_chunk_lines) - 1)
        // chunk_lines.get(file, default_chunk_lines)
        for file in files
    )
    changed_cfg = {
        **cfg,
        "paths": files,
        "exclude": [],
        "full_shards": min(256, chunk_count),
    }
    return write_partition_manifests(root, changed_cfg, output_dir), files


def _canonical_mutant(
    root: str,
    file: str,
    source: str,
    diff: str,
    engine_id: str,
    state: str,
    mapped_tests: list[str],
) -> dict:
    del root
    canonical_file, removed, added = _parse_mutation_diff(diff, file)
    normalized_source = unicodedata.normalize("NFC", source)
    normalized_removed = [unicodedata.normalize("NFC", line) for line in removed]
    normalized_added = [unicodedata.normalize("NFC", line) for line in added]
    if normalized_source.endswith("\n") and normalized_removed[-1:] == [""] and normalized_added[-1:] == [""]:
        normalized_removed.pop()
        normalized_added.pop()
    diff_lines = diff.splitlines()
    hunk = re.match(r"@@ -(\d+)", diff_lines[2])
    context_before = next(
        (index for index, value in enumerate(diff_lines[3:]) if value.startswith(("-", "+"))),
        0,
    )
    preferred_line = int(hunk.group(1)) + context_before if hunk else None
    if len(_mutation_hunks(diff_lines)) > 1:
        mutated_source, line = _apply_multi_hunk_diff(normalized_source, diff)
    elif normalized_removed:
        mutated_source, line = _find_replacement(
            normalized_source, normalized_removed, normalized_added, preferred_line,
        )
    elif preferred_line is not None:
        mutated_source, line = _find_insertion(
            normalized_source, diff, normalized_added, preferred_line,
        )
    else:
        raise ValueError("mutation insertion cannot be anchored uniquely")
    try:
        before_tree = ast.parse(normalized_source)
    except SyntaxError as exc:
        raise ValueError("mutation source is not valid Python") from exc

    def textual_record() -> dict:
        before_symbol = _enclosing_symbol(before_tree, line)
        symbol = _symbol_name(before_tree, before_symbol)
        before = "\n".join(normalized_removed).strip()
        after = "\n".join(normalized_added).strip()
        context = [
            unicodedata.normalize("NFC", value[1:])
            for value in diff_lines[3:] if value.startswith(" ")
        ]
        symbol_start = getattr(before_symbol, "lineno", 1)
        symbol_end = getattr(before_symbol, "end_lineno", len(normalized_source.splitlines()))
        symbol_lines = normalized_source.splitlines()[symbol_start - 1:symbol_end]
        anchor = normalized_removed or context
        occurrences = [
            index for index in range(len(symbol_lines) - len(anchor) + 1)
            if symbol_lines[index:index + len(anchor)] == anchor
        ]
        occurrence = occurrences.index(line - symbol_start) if line - symbol_start in occurrences else None
        identity = json.dumps(
            [
                "v2", canonical_file, symbol, ["textual"], "textual",
                before, after, context, occurrence,
            ],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return {
            "fingerprint_version": "2",
            "fingerprint": _fingerprint_digest(identity),
            "source_context_digest": _canonical_digest(
                [canonical_file, symbol, ast.dump(before_symbol, include_attributes=False)]
            ),
            "engine_id": engine_id,
            "locator": {"file": canonical_file, "engine_id": engine_id},
            "state": state,
            "file": canonical_file,
            "line": line,
            "symbol": symbol,
            "operator": "textual",
            "before": before,
            "after": after,
            "mapped_tests": sorted(set(mapped_tests)),
            "rerun_command": shlex.join(["mutmut", "run", engine_id]),
        }

    if not normalized_removed or not normalized_added:
        return textual_record()
    try:
        after_tree = ast.parse(mutated_source)
    except SyntaxError:
        return textual_record()
    before_symbol = _enclosing_symbol(before_tree, line)
    after_symbol = _enclosing_symbol(after_tree, line)
    symbol = _symbol_name(before_tree, before_symbol)
    if symbol != _symbol_name(after_tree, after_symbol):
        raise ValueError("mutation changes its structural anchor")
    old_node, new_node, structural_path = _ast_difference(before_symbol, after_symbol)
    if ast.dump(old_node, include_attributes=False) == ast.dump(new_node, include_attributes=False):
        raise ValueError("mutation detail has no structural AST change")
    before = unicodedata.normalize("NFC", ast.unparse(old_node))
    after = unicodedata.normalize("NFC", ast.unparse(new_node))
    operator = f"{type(old_node).__name__}->{type(new_node).__name__}"
    if type(old_node) is type(new_node):
        operator = type(old_node).__name__
    old_dump = ast.dump(old_node, include_attributes=False)
    occurrences = sorted(
        (
            (node.lineno, node.col_offset)
            for node in ast.walk(before_symbol)
            if hasattr(node, "lineno") and ast.dump(node, include_attributes=False) == old_dump
        ),
    )
    occurrence = occurrences.index((old_node.lineno, old_node.col_offset)) if len(occurrences) > 1 else None
    identity_parts = [
        "v2", canonical_file, symbol, structural_path, operator,
        old_dump, ast.dump(new_node, include_attributes=False),
    ]
    if occurrence is not None:
        identity_parts.append(occurrence)
    identity = json.dumps(
        identity_parts,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return {
        "fingerprint_version": "2",
        "fingerprint": _fingerprint_digest(identity),
        "source_context_digest": _canonical_digest(
            [canonical_file, symbol, ast.dump(before_symbol, include_attributes=False)]
        ),
        "engine_id": engine_id,
        "locator": {"file": canonical_file, "engine_id": engine_id},
        "state": state,
        "file": canonical_file,
        "line": line,
        "symbol": symbol,
        "operator": operator,
        "before": before,
        "after": after,
        "mapped_tests": sorted(set(mapped_tests)),
        "rerun_command": shlex.join(["mutmut", "run", engine_id]),
    }


def _collect_mutant_records(
    root: str,
    ids: dict[str, list[str]],
    mapped_tests: list[str] | dict[str, list[str]],
    expected_files: list[str] | None = None,
) -> tuple[list[dict] | None, dict | None]:
    states = {engine_id: state for state in _STATES for engine_id in ids[state]}
    if not states:
        return [], None
    selected_files = {_canonical_path(item) for item in expected_files} if expected_files is not None else None
    try:
        shown = _run(["mutmut", "show", "all"], root, 120)
        if shown.returncode:
            return None, _error("tool_error", "mutmut show all failed", stderr=_bounded(shown.stderr or shown.stdout))
        try:
            details = _parse_show_all(shown.stdout, set(states))
        except ValueError as exc:
            if "mutation details are missing" not in str(exc):
                raise
            details = {}
            for engine_id in sorted(states, key=int):
                detail = _run(["mutmut", "show", engine_id], root, 120)
                if detail.returncode:
                    return None, _error(
                        "tool_error", f"mutmut show {engine_id} failed",
                        stderr=_bounded(detail.stderr or detail.stdout),
                    )
                details[engine_id] = detail.stdout
        for engine_id, state in list(states.items()):
            if state in {"untested", "skipped"} and not details[engine_id].strip():
                ids[state].remove(engine_id)
                del states[engine_id]
        records = []
        for engine_id in sorted(states, key=int):
            file, _, _ = _parse_mutation_diff(details[engine_id])
            if selected_files is not None and file not in selected_files:
                raise ValueError(f"mutation detail is outside selected scope: {file}")
            source = (Path(root) / file).read_text(encoding="utf-8")
            tests = mapped_tests.get(file, []) if isinstance(mapped_tests, dict) else mapped_tests
            if not tests:
                raise ValueError(f"mutation detail has no mapped tests for {file}")
            try:
                record = _canonical_mutant(
                    root, file, source, details[engine_id], engine_id, states[engine_id], tests,
                )
            except ValueError as exc:
                return None, _error(
                    "unknown",
                    f"Cannot construct canonical mutant evidence: {exc}",
                    diagnostics=[{
                        "engine_id": engine_id,
                        "file": file,
                        "stage": "canonicalization",
                        "reason": str(exc),
                        "raw_diff": _bounded(details[engine_id]),
                    }],
                )
            records.append(record)
    except subprocess.TimeoutExpired:
        return None, _error("tool_error", "mutmut detail collection timed out")
    except (OSError, UnicodeError, ValueError) as exc:
        return None, _error("unknown", f"Cannot construct canonical mutant evidence: {exc}")
    fingerprints = [record["fingerprint"] for record in records]
    if len(fingerprints) != len(set(fingerprints)):
        return None, _error("unknown", "Canonical mutant fingerprint is duplicated or collided")
    return records, None


def _validate_report_schema(report: dict) -> None:
    if report.get("schema_version") == "1":
        raise ValueError("schema version 1 mutation evidence is read-only and cannot be compared")
    if report.get("schema_version") != "2":
        raise ValueError("unsupported mutation report schema")
    records = report.get("non_killed")
    if not isinstance(records, list):
        raise ValueError("schema v2 requires complete non-killed records")
    counts = [report.get(state) for state in _STATES]
    if any(not isinstance(count, int) or isinstance(count, bool) or count < 0 for count in counts):
        raise ValueError("schema v2 contains invalid outcome counts")
    expected = sum(report[state] for state in _STATES[1:])
    required = {
        "fingerprint", "source_context_digest", "engine_id", "state", "file", "line",
        "operator", "before", "after", "mapped_tests", "rerun_command",
    }
    if len(records) != expected or any(not isinstance(record, dict) or not required <= set(record) for record in records):
        raise ValueError("schema v2 requires complete non-killed records")
    if any(
        not isinstance(record["state"], str)
        or record["state"] not in _STATES[1:]
        or not isinstance(record["fingerprint"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", record["fingerprint"])
        or not isinstance(record["source_context_digest"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", record["source_context_digest"])
        or not isinstance(record["engine_id"], str)
        or not isinstance(record["mapped_tests"], list)
        or any(not isinstance(test, str) for test in record["mapped_tests"])
        or not isinstance(record["line"], int)
        or isinstance(record["line"], bool)
        or record["line"] < 1
        or any(not isinstance(record[field], str) or not record[field] for field in ("file", "operator", "rerun_command"))
        or not isinstance(record["before"], str)
        or not isinstance(record["after"], str)
        or not (record["before"] or record["after"])
        for record in records
    ):
        raise ValueError("schema v2 contains malformed non-killed records")
    for state in _STATES[1:]:
        if sum(record["state"] == state for record in records) != report.get(state, 0):
            raise ValueError("schema v2 non-killed record outcomes do not match counts")
    engine_ids = [record["engine_id"] for record in records]
    if len(engine_ids) != len(set(engine_ids)) or any(not re.fullmatch(r"\d+", item) for item in engine_ids):
        raise ValueError("schema v2 requires unique numeric engine IDs")
    if any(not record["mapped_tests"] or record["mapped_tests"] != sorted(set(record["mapped_tests"])) for record in records):
        raise ValueError("schema v2 requires mapped tests for every non-killed record")
    fingerprints = [record["fingerprint"] for record in records]
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError("schema v2 requires unique mutant fingerprints")


def build_mutation_report_artifact(
    report: dict,
    report_location: str,
    *,
    run_ids: list[str],
    calibration_ids: list[str] | None = None,
    expected_report_digest: str | None = None,
    observation_id: str | None = None,
    observed_at: str | None = None,
) -> EvidenceArtifact:
    """Reference a complete schema-v2 report without replacing domain evidence."""
    _validate_report_schema(report)
    if report.get("status") != "completed":
        raise ValueError("mutation artifact requires a completed report")
    if not isinstance(report.get("passed"), bool):
        raise ValueError("completed mutation report requires a boolean policy result")
    if not re.fullmatch(r"[0-9a-f]{40}", str(report.get("revision", ""))):
        raise ValueError("completed mutation report revision is invalid")
    digest_fields = (
        "policy_digest", "source_scope_digest", "test_mapping_digest", "line_range_digest",
    )
    if any(not re.fullmatch(r"[0-9a-f]{64}", str(report.get(field, ""))) for field in digest_fields):
        raise ValueError("completed mutation report identity digests are invalid")
    if (
        not isinstance(run_ids, list) or not run_ids or run_ids != list(dict.fromkeys(run_ids))
        or any(not isinstance(item, str) or not item for item in run_ids)
    ):
        raise ValueError("mutation artifact run IDs are invalid")
    calibration_ids = calibration_ids or []
    if (
        not isinstance(calibration_ids, list)
        or calibration_ids != list(dict.fromkeys(calibration_ids))
        or any(not isinstance(item, str) or not item for item in calibration_ids)
    ):
        raise ValueError("mutation artifact calibration IDs are invalid")
    report_calibration = report.get("calibration_id")
    if report_calibration is not None and report_calibration not in calibration_ids:
        raise ValueError("mutation artifact calibration identity differs from the report")

    location = _canonical_path(report_location)
    report_digest = "sha256:" + _canonical_digest(report)
    if expected_report_digest is not None and expected_report_digest != report_digest:
        raise ValueError("mutation report digest does not match retained content")
    source_digest = "sha256:" + report["source_scope_digest"]
    policy_digest = "sha256:" + report["policy_digest"]
    scope_digest = "sha256:" + _canonical_digest({
        "selection": report.get("selection"),
        "files_tested": report.get("files_tested"),
        "tests_run": report.get("tests_run"),
        "line_ranges": report.get("line_ranges"),
    })
    return EvidenceArtifact.create(
        kind="fettle.mutation.report",
        producer={
            "id": "fettle.mutation",
            "version": __version__,
            "implementation_digest": "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        result_state="pass" if report["passed"] else "violation",
        completeness="complete",
        trust_class="authoritative",
        source={"snapshot_digest": source_digest, "revision": report["revision"]},
        policy_digest=policy_digest,
        scope_digest=scope_digest,
        observation_id=observation_id or "mutation-" + uuid.uuid4().hex,
        observed_at=observed_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        payload={
            "report": {
                "location": location,
                "digest": report_digest,
                "schema_version": report["schema_version"],
            },
            "identity_digests": {field: report[field] for field in digest_fields},
            "counts": {state: report[state] for state in _STATES},
            "run_ids": run_ids,
            "calibration_ids": calibration_ids,
        },
    )


def _rerun_mutant(root: str, record: dict, current_ids: dict[str, list[str]], timeout: int) -> dict:
    engine_id, state = record.get("engine_id"), record.get("state")
    occurrences = sum(ids.count(engine_id) for ids in current_ids.values()) if isinstance(engine_id, str) else 0
    if not isinstance(engine_id, str) or not re.fullmatch(r"\d+", engine_id) or engine_id not in current_ids.get(state, []) or occurrences != 1:
        return _error("unknown", "Selected mutant engine ID is missing, stale, or ambiguous")
    try:
        result = _run(["mutmut", "run", engine_id], root, timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error("tool_error", f"Cannot rerun selected mutant: {exc}")
    if result.returncode < 0 or result.returncode & 1 or result.returncode & ~15:
        return _error("unknown", "Selected mutant rerun outcome changed", rerun_exit_code=result.returncode)
    rerun_ids, error = _collect_results(root, MUTMUT_VERSION, result.returncode)
    if error:
        return error
    assert rerun_ids is not None
    observed = [outcome for outcome in _STATES if engine_id in rerun_ids[outcome]]
    if observed != [state]:
        return _error("unknown", "Selected mutant rerun outcome changed", expected_state=state, observed_states=observed)
    return {"status": "completed", "passed": False, "state": state, "engine_id": engine_id}


def _collect_results(root: str, engine_version: str, run_exit_code: int) -> tuple[dict[str, list[str]] | None, dict | None]:
    try:
        results = _run(["mutmut", "results"], root, 30)
        if results.returncode:
            return None, _error(
                "tool_error", "mutmut results failed", engine_version=engine_version,
                run_exit_code=run_exit_code, results_exit_code=results.returncode,
                stderr=_bounded(results.stderr or results.stdout),
            )
        ids: dict[str, list[str]] = {}
        for state in _STATES:
            result_ids = _run(["mutmut", "result-ids", state], root, 30)
            if result_ids.returncode:
                return None, _error(
                    "tool_error", f"mutmut result-ids {state} failed",
                    engine_version=engine_version, result_ids_exit_code=result_ids.returncode,
                    stderr=_bounded(result_ids.stderr or result_ids.stdout),
                )
            ids[state] = _parse_result_ids(result_ids.stdout)
    except ValueError as exc:
        return None, _error("unknown", str(exc), engine_version=engine_version, run_exit_code=run_exit_code)
    except subprocess.TimeoutExpired:
        return None, _error("tool_error", "mutmut result collection timed out", engine_version=engine_version)
    except OSError as exc:
        return None, _error("tool_error", f"Cannot read mutmut results: {exc}", engine_version=engine_version)
    all_ids = [item for state_ids in ids.values() for item in state_ids]
    if len(all_ids) != len(set(all_ids)):
        return None, _error("unknown", "mutmut reported overlapping outcome IDs", engine_version=engine_version)
    return ids, None


def _collect_range_results(root: str, line_ranges: list[dict], engine_version: str, run_exit_code: int) -> tuple[dict[str, list[str]] | None, dict | None]:
    cache = Path(root) / ".mutmut-cache"
    try:
        connection = sqlite3.connect(f"file:{cache.resolve()}?mode=ro", uri=True)
        rows = connection.execute(
            "SELECT Mutant.id, SourceFile.filename, Line.line_number, Mutant.status "
            "FROM Mutant JOIN Line ON Mutant.line = Line.id "
            "JOIN SourceFile ON Line.sourcefile = SourceFile.id"
        ).fetchall()
        connection.close()
    except sqlite3.Error as exc:
        return None, _error(
            "tool_error", f"Cannot read mutmut range results: {exc}",
            engine_version=engine_version, run_exit_code=run_exit_code,
        )
    allowed = {(item["file"], line) for item in line_ranges for line in range(item["start"], item["end"] + 1)}
    ids = {state: [] for state in _STATES}
    for mutant_id, filename, line, status in rows:
        if (filename, line) not in allowed:
            continue
        state = _CACHE_STATES.get(status)
        if state is None:
            return None, _error("unknown", f"mutmut reported unknown status {status}", engine_version=engine_version)
        ids[state].append(str(mutant_id))
    return ids, None


def _reset_generated_mutants(root: str, records: list[dict]) -> dict | None:
    """Make the exact canonicalized corpus executable after the no-op preflight."""
    locators = [(record.get("engine_id"), record.get("file")) for record in records]
    if (
        len(locators) != len(set(locators))
        or any(not isinstance(engine_id, str) or not re.fullmatch(r"\d+", engine_id)
               or not isinstance(file, str) or not file for engine_id, file in locators)
    ):
        return _error("tool_error", "Mutation preflight cache locators are incomplete or duplicated")
    cache = Path(root) / ".mutmut-cache"
    try:
        connection = sqlite3.connect(cache)
        with connection:
            for engine_id, file in locators:
                row = connection.execute(
                    "SELECT SourceFile.filename FROM Mutant "
                    "JOIN Line ON Mutant.line = Line.id "
                    "JOIN SourceFile ON Line.sourcefile = SourceFile.id "
                    "WHERE Mutant.id = ?",
                    (int(engine_id),),
                ).fetchone()
                if row != (file,):
                    raise ValueError("generated mutant locator does not match native cache")
            connection.executemany(
                "UPDATE Mutant SET status = 'untested' WHERE id = ?",
                [(int(engine_id),) for engine_id, _ in locators],
            )
            connection.execute(
                "DELETE FROM MiscData WHERE key IN ('baseline_time_elapsed', 'hash_of_tests')"
            )
            statuses = dict(connection.execute("SELECT id, status FROM Mutant").fetchall())
            if any(statuses.get(int(engine_id)) != "untested" for engine_id, _ in locators):
                raise ValueError("generated mutant reset is incomplete")
        connection.close()
    except (sqlite3.Error, ValueError) as exc:
        return _error("tool_error", f"Cannot reset mutation preflight cache: {exc}")
    return None


def _preflight_mutmut(
    root: str,
    files: list[str],
    tests: list[str],
    test_mapping: dict[str, list[str]],
    timeout: int,
    line_ranges: list[dict] | None = None,
) -> dict:
    """Generate and canonicalize mutmut's complete detail corpus without project tests."""
    if not files or not tests:
        return _error("unknown", "Mutation preflight requires source files and targeted tests")
    try:
        version = _run(["mutmut", "version"], root, 30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error("tool_error", f"Cannot check mutmut version: {exc}")
    match = re.fullmatch(r"\s*mutmut version (\d+\.\d+\.\d+)\s*", version.stdout)
    actual = match.group(1) if match else "unrecognized"
    if version.returncode or actual != MUTMUT_VERSION:
        return _error(
            "tool_error",
            f"Unsupported mutmut version {actual}; install mutmut=={MUTMUT_VERSION}",
            engine_version=actual,
            version_exit_code=version.returncode,
            stderr=_bounded(version.stderr),
        )
    patch_path: str | None = None
    try:
        argv = [
            "mutmut", "run", "--paths-to-mutate=" + ",".join(files),
            "--runner", "python -c pass", "--no-progress", "--simple-output",
        ]
        if line_ranges:
            with tempfile.NamedTemporaryFile("w", suffix=".patch", dir=root, delete=False) as patch:
                patch.write(_patch_for_ranges(root, line_ranges))
                patch_path = patch.name
            argv.extend(["--use-patch-file", patch_path])
        run = _run(argv, root, timeout)
    except subprocess.TimeoutExpired:
        return _error("tool_error", f"Mutation preflight timed out after {timeout}s", engine_version=actual)
    except OSError as exc:
        return _error("tool_error", f"Cannot execute mutmut preflight: {exc}", engine_version=actual)
    finally:
        if patch_path:
            Path(patch_path).unlink(missing_ok=True)
    if run.returncode < 0 or run.returncode & 1 or run.returncode & ~15:
        return _error(
            "tool_error", "mutmut preflight generation failed", engine_version=actual,
            run_exit_code=run.returncode, stderr=_bounded(run.stderr or run.stdout),
        )
    ids, error = (
        _collect_range_results(root, line_ranges, actual, run.returncode)
        if line_ranges else _collect_results(root, actual, run.returncode)
    )
    if error:
        return error
    assert ids is not None
    generated = sum(len(state_ids) for state_ids in ids.values())
    if generated == 0:
        if line_ranges:
            return {
                "status": "completed", "passed": True, "engine_version": actual,
                "generated": 0, "canonicalized": 0, "collisions": 0,
                "files": sorted(files), "fingerprints": [], "corpus": [], "line_ranges": line_ranges,
            }
        return _error("unknown", "Mutation preflight generated no mutants", engine_version=actual)
    records, error = _collect_mutant_records(root, ids, test_mapping, files)
    if error:
        return {**error, "engine_version": actual, "generated": generated}
    assert records is not None
    generated = sum(len(state_ids) for state_ids in ids.values())
    fingerprints = [record["fingerprint"] for record in records]
    if len(records) != generated or len(fingerprints) != len(set(fingerprints)):
        return _error(
            "unknown", "Mutation preflight corpus is incomplete or contains collisions",
            engine_version=actual, generated=generated, canonicalized=len(records),
        )
    reset_error = _reset_generated_mutants(root, records)
    if reset_error:
        return {**reset_error, "engine_version": actual, "generated": generated}
    return {
        "status": "completed",
        "passed": True,
        "engine_version": actual,
        "generated": generated,
        "canonicalized": len(records),
        "collisions": 0,
        "files": sorted(files),
        "fingerprints": sorted(fingerprints),
        "corpus": sorted(records, key=lambda record: record["fingerprint"]),
        **({"line_ranges": line_ranges} if line_ranges else {}),
    }


def _preflight_shard_modules(
    root: str,
    mapping: dict[str, list[str]],
    line_ranges: list[dict],
    timeout: int,
) -> dict:
    """Generate each module separately so numeric locators remain executable."""
    started = time.monotonic()
    reports = []
    for file in sorted(mapping):
        remaining = timeout - int(time.monotonic() - started)
        if remaining < 1:
            return _error("tool_error", f"Mutation preflight timed out after {timeout}s")
        try:
            (Path(root) / ".mutmut-cache").unlink(missing_ok=True)
        except OSError as exc:
            return _error("tool_error", f"Cannot isolate mutation preflight cache: {exc}")
        ranges = [item for item in line_ranges if item["file"] == file]
        report = _preflight_mutmut(
            root, [file], mapping[file], {file: mapping[file]}, remaining, ranges,
        )
        if report["status"] != "completed":
            return report
        reports.append(report)
    corpus = [record for report in reports for record in report["corpus"]]
    fingerprints = [record["fingerprint"] for record in corpus]
    if len(fingerprints) != len(set(fingerprints)):
        return _error("unknown", "Mutation preflight corpus contains collisions")
    generated = sum(report["generated"] for report in reports)
    return {
        "status": "completed", "passed": True, "engine_version": MUTMUT_VERSION,
        "generated": generated, "canonicalized": len(corpus), "collisions": 0,
        "files": sorted(mapping), "fingerprints": sorted(fingerprints),
        "corpus": sorted(corpus, key=lambda record: record["fingerprint"]),
        "line_ranges": line_ranges,
    }


def _run_mutmut(
    root: str,
    files: list[str],
    tests: list[str],
    timeout: int,
    line_ranges: list[dict] | None = None,
    test_mapping: dict[str, list[str]] | None = None,
) -> dict:
    """Run mutmut 2.5.1 and reconstruct each outcome from verified ID output."""
    if not tests:
        return _error("unknown", "Mutation execution requires at least one targeted test")
    try:
        version = _run(["mutmut", "version"], root, 30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error("tool_error", f"Cannot check mutmut version: {exc}")
    match = re.fullmatch(r"\s*mutmut version (\d+\.\d+\.\d+)\s*", version.stdout)
    actual = match.group(1) if match else "unrecognized"
    if version.returncode or actual != MUTMUT_VERSION:
        return _error(
            "tool_error",
            f"Unsupported mutmut version {actual}; install mutmut=={MUTMUT_VERSION}",
            engine_version=actual,
            version_exit_code=version.returncode,
            stderr=_bounded(version.stderr),
        )

    started = time.monotonic()
    patch_path: str | None = None
    try:
        if line_ranges:
            with tempfile.NamedTemporaryFile("w", suffix=".patch", dir=root, delete=False) as patch:
                patch.write(_patch_for_ranges(root, line_ranges))
                patch_path = patch.name
        argv = [
            "mutmut", "run", "--paths-to-mutate=" + ",".join(files),
            "--runner", "python -m pytest -x --assert=plain " + shlex.join(tests),
            "--no-progress", "--simple-output",
        ]
        if patch_path:
            argv.extend(["--use-patch-file", patch_path])
        run = _run(
            argv,
            root,
            timeout,
        )
    except subprocess.TimeoutExpired:
        return _error("tool_error", f"Mutation run timed out after {timeout}s", engine_version=actual)
    except OSError as exc:
        return _error("tool_error", f"Cannot execute mutmut: {exc}", engine_version=actual)
    finally:
        if patch_path:
            Path(patch_path).unlink(missing_ok=True)

    # mutmut 2.x uses bits 2/4/8 for survivor/timeout/suspicious outcomes.
    if run.returncode < 0 or run.returncode & 1 or run.returncode & ~15:
        return _error(
            "tool_error",
            "mutmut run failed",
            engine_version=actual,
            run_exit_code=run.returncode,
            stderr=_bounded(run.stderr or run.stdout),
        )
    ids, error = (
        _collect_range_results(root, line_ranges, actual, run.returncode)
        if line_ranges else _collect_results(root, actual, run.returncode)
    )
    if error:
        return error
    assert ids is not None
    records, error = _collect_mutant_records(root, ids, test_mapping or tests, files)
    if error:
        return {**error, "engine_version": actual, "run_exit_code": run.returncode}
    assert records is not None

    non_killed = [record for record in records if record["state"] != "killed"]
    return {
        "status": "completed",
        "engine_version": actual,
        "test_runner": _TEST_RUNNER,
        "tests_run": tests,
        "line_ranges": line_ranges or [],
        "run_exit_code": run.returncode,
        "results_exit_code": 0,
        **{state: len(ids[state]) for state in _STATES},
        "non_killed": non_killed,
        "survivor_preview": [record for record in non_killed if record["state"] == "survived"][:20],
        "survivors": [record["fingerprint"] for record in non_killed if record["state"] == "survived"],
        "stderr": _bounded(run.stderr),
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def _run_shard_modules(root: str, mapping: dict[str, list[str]], line_ranges: list[dict], timeout: int) -> dict:
    """Run each module with only its mapped tests, within one shard deadline."""
    started = time.monotonic()
    results: list[dict] = []
    module_runs: list[dict] = []
    for file in sorted(mapping):
        remaining = timeout - int(time.monotonic() - started)
        if remaining < 1:
            return _error(
                "tool_error", f"Mutation shard timed out after {timeout}s",
                duration_ms=round((time.monotonic() - started) * 1000), module_runs=module_runs,
            )
        try:
            (Path(root) / ".mutmut-cache").unlink(missing_ok=True)
        except OSError as exc:
            return _error(
                "tool_error", f"Cannot isolate mutation module cache: {exc}",
                duration_ms=round((time.monotonic() - started) * 1000), module_runs=module_runs,
            )
        ranges = [item for item in line_ranges if item["file"] == file]
        module_started = time.monotonic()
        result = _run_mutmut(root, [file], mapping[file], remaining, ranges, {file: mapping[file]})
        module_run = {
            "file": file,
            "line_ranges": ranges,
            "tests_run": mapping[file],
            "timeout_s": remaining,
            "duration_ms": round((time.monotonic() - module_started) * 1000),
            "status": result["status"],
        }
        if result["status"] == "completed":
            module_run["mutants"] = sum(result[state] for state in _STATES)
        elif result.get("message"):
            module_run["message"] = result["message"]
        module_runs.append(module_run)
        if result["status"] != "completed":
            return {
                **result,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "module_runs": module_runs,
            }
        results.append(result)
    counts = {state: sum(result[state] for result in results) for state in _STATES}
    records = [item for result in results for item in result.get("non_killed", [])]
    for engine_id, record in enumerate(records, start=1):
        record["engine_id"] = str(engine_id)
    return {
        "status": "completed",
        "engine_version": MUTMUT_VERSION,
        "test_runner": _TEST_RUNNER,
        "tests_run": sorted({test for tests in mapping.values() for test in tests}),
        "line_ranges": line_ranges,
        "run_exit_code": 0,
        "results_exit_code": 0,
        **counts,
        "non_killed": records,
        "survivor_preview": [item for result in results for item in result.get("survivor_preview", [])][:20],
        "survivors": [item for result in results for item in result.get("survivors", [])],
        "stderr": "\n".join(result.get("stderr", "") for result in results if result.get("stderr")),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "module_runs": module_runs,
    }


def compute_score(killed: int, survived: int, timeout: int, suspicious: int, untested: int) -> float | None:
    del timeout, suspicious, untested
    total = killed + survived
    return None if total == 0 else killed / total * 100


def evaluate_policy(report: dict, cfg: dict) -> dict:
    """Evaluate raw mutation outcomes without converting evidence debt into test failures."""
    mode = cfg.get("mode", "advisory")
    score = compute_score(*(report[state] for state in _STATES[:5]))
    violations: list[str] = []
    debt: list[str] = []
    checks = (
        ("untested", "max_untested", 0, "untested"),
        ("timeout", "max_mutant_timeouts", None, "timeout"),
        ("suspicious", "max_suspicious_mutants", None, "suspicious"),
    )
    for state, key, default, label in checks:
        budget = cfg.get(key, default)
        count = report[state]
        if budget is None:
            if count:
                debt.append(f"{label} outcome budget is uncalibrated ({count} observed)")
        elif count > budget:
            violations.append(f"{label} budget exceeded: {count} > {budget}")
    target = float(cfg.get("score_target", 70))
    decided = report["killed"] + report["survived"]
    minimum = int(cfg.get("minimum_scored_mutants", 0))
    score_eligible = decided >= minimum
    if score is None:
        violations.append("no decided mutants were reported")
    elif not score_eligible:
        debt.append(f"mutation score decision suppressed below minimum: {decided} < {minimum}")
    elif score < target:
        violations.append(f"mutation score below target: {score:.1f} < {target:.1f}")
    reasons = [*violations, *debt]
    return {
        "mode": mode,
        "score": None if score is None else round(score, 1),
        "score_eligible": score_eligible,
        "eligible": not violations and not debt,
        "passed": mode != "enforce" or not violations,
        "reasons": reasons,
    }


def select_shard_attempts(reports: list[dict], shard_count: int) -> list[dict]:
    """Select one completed report per shard while rejecting conflicting retries."""
    attempts: dict[int, list[dict]] = {index: [] for index in range(shard_count)}
    for report in reports:
        index = report.get("shard_index") if isinstance(report, dict) else None
        if (
            not isinstance(index, int) or isinstance(index, bool)
            or index not in attempts or report.get("shard_count") != shard_count
        ):
            raise ValueError("shard attempt has invalid topology")
        attempts[index].append(report)
    selected = []
    for index in range(shard_count):
        completed = [report for report in attempts[index] if report.get("status") == "completed"]
        if not completed:
            raise ValueError(f"shard {index} has no completed attempt")
        canonical = {_canonical_digest(report) for report in completed}
        if len(canonical) != 1:
            raise ValueError(f"shard {index} has conflicting completed attempts")
        selected.append(completed[0])
    return selected


def prepare_shard_replay_matrix(reports: list[dict], shard_count: int) -> dict:
    """Derive a bounded retry matrix after the initial shard matrix is terminal."""
    if len(reports) > shard_count:
        raise ValueError(f"replay preparation accepts at most {shard_count} initial reports")
    by_index: dict[int, dict] = {}
    revisions = set()
    for report in reports:
        index = report.get("shard_index") if isinstance(report, dict) else None
        if (
            not isinstance(index, int) or isinstance(index, bool)
            or not 0 <= index < shard_count or index in by_index
            or report.get("shard_count") != shard_count
            or not re.fullmatch(r"[0-9a-f]{40}", str(report.get("revision", "")))
        ):
            raise ValueError(f"initial shard report {index!r} has invalid or duplicated identity")
        by_index[index] = report
        revisions.add(report["revision"])
    if len(revisions) > 1:
        raise ValueError("initial shard reports have conflicting identity")
    replay = [
        index for index in range(shard_count)
        if index not in by_index or by_index[index].get("status") != "completed"
    ]
    return {"status": "completed", "passed": True, "matrix": {"shard": replay}, "shard_count": len(replay)}


def aggregate_shards(
    root: str,
    reports: list[dict],
    paths: list[str],
    excluded: list[str],
    shard_count: int,
    threshold: float,
    test_mappings: dict[str, list[str]] | None = None,
    policy_config: dict | None = None,
) -> dict:
    """Combine only complete, equivalent shards that exactly cover full scope."""
    if shard_count < 1:
        return _error("unknown", "Aggregation requires a positive shard count")
    if len(reports) != shard_count:
        return _error("unknown", f"Aggregation requires exactly {shard_count} shard reports")
    reports = sorted(reports, key=lambda report: report.get("shard_index", -1))
    expected_indexes = list(range(shard_count))
    if [report.get("shard_index") for report in reports] != expected_indexes:
        return _error("unknown", "Shard indexes are incomplete or duplicated")
    for index, report in enumerate(reports):
        if report.get("status") != "completed":
            return _error("tool_error", f"Shard {index} is not completed")
        if report.get("schema_version") != "2" or report.get("selection") != "shard":
            return _error("unknown", f"Shard {index} has unsupported evidence")
        if not isinstance(report.get("files_tested"), list) or not report["files_tested"]:
            return _error("unknown", f"Shard {index} has no tested files")
        try:
            _validate_report_schema(report)
        except ValueError as exc:
            return _error("unknown", f"Shard {index} has invalid evidence: {exc}")
        if report.get("shard_count") != shard_count:
            return _error("unknown", f"Shard {index} has inconsistent shard count")
        if report.get("engine_version") != MUTMUT_VERSION or report.get("test_runner") != _TEST_RUNNER:
            return _error("unknown", f"Shard {index} has unsupported execution identity")
        if not re.fullmatch(r"[0-9a-f]{40}", str(report.get("revision", ""))):
            return _error("unknown", f"Shard {index} has an invalid revision")
        expected_tests = sorted({
            test
            for tests in _mapped_tests(root, report["files_tested"], test_mappings).values()
            for test in tests
        })
        if report.get("tests_run") != expected_tests or not expected_tests:
            return _error("unknown", f"Shard {index} has an invalid test mapping")
        counts = [report.get(state) for state in _STATES]
        if any(not isinstance(count, int) or isinstance(count, bool) or count < 0 for count in counts):
            return _error("unknown", f"Shard {index} has invalid outcomes")
        ranges = report.get("line_ranges")
        if not isinstance(ranges, list) or not ranges:
            return _error("unknown", f"Shard {index} has no source ranges")
        duration = report.get("duration_ms")
        if not isinstance(duration, int) or isinstance(duration, bool) or duration < 0:
            return _error("unknown", f"Shard {index} has invalid duration")
    first = reports[0]
    identity = ("revision", "engine_version", "test_runner")
    if any(any(report.get(key) != first.get(key) for key in identity) for report in reports[1:]):
        return _error("unknown", "Shard execution identities differ")

    expected = [
        path for path in _get_all_py_files(root, paths)
        if not any(path.startswith(item) for item in excluded)
    ]
    tested = sorted({path for report in reports for path in report.get("files_tested", [])})
    if tested != expected:
        return _error("unknown", "Shard file scope does not match full mutation scope")
    expected_lines = {(file, line) for file in expected for line in range(1, len((Path(root) / file).read_text(encoding="utf-8").splitlines()) + 1)}
    tested_lines: list[tuple[str, int]] = []
    for report in reports:
        for item in report["line_ranges"]:
            if not isinstance(item, dict) or set(item) != {"file", "start", "end"}:
                return _error("unknown", "Shard source ranges are malformed")
            if item["file"] not in report["files_tested"] or not isinstance(item["start"], int) or not isinstance(item["end"], int):
                return _error("unknown", "Shard source ranges are malformed")
            tested_lines.extend((item["file"], line) for line in range(item["start"], item["end"] + 1))
    if len(tested_lines) != len(set(tested_lines)) or set(tested_lines) != expected_lines:
        return _error("unknown", "Shard source ranges do not exactly cover full mutation scope")
    try:
        revision = _run(["git", "rev-parse", "HEAD"], root, 10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error("tool_error", "Cannot verify aggregate revision: " + str(exc))
    if revision.returncode or revision.stdout.strip() != first["revision"]:
        return _error("unknown", "Shard revision does not match aggregate checkout")
    counts = {state: sum(report[state] for report in reports) for state in _STATES}
    score = compute_score(*(counts[state] for state in _STATES[:5]))
    if score is None:
        return _error("unknown", "Aggregated shards reported zero scored mutants")
    records = [{**item} for report in reports for item in report["non_killed"]]
    fingerprints = [record["fingerprint"] for record in records]
    if len(fingerprints) != len(set(fingerprints)):
        return _error("unknown", "Aggregated mutant fingerprints are duplicated or collided")
    for engine_id, record in enumerate(records, start=1):
        record["engine_id"] = str(engine_id)
        record["rerun_command"] = shlex.join(["mutmut", "run", str(engine_id)])
    survivors = [record["fingerprint"] for record in records if record["state"] == "survived"]
    mapping = _mapped_tests(root, expected, test_mappings)
    line_ranges = sorted(
        (item for report in reports for item in report["line_ranges"]),
        key=lambda item: (item["file"], item["start"]),
    )
    policy = policy_config or {"score_target": threshold}
    policy_result = evaluate_policy(counts, policy)
    evidence_identity = {
        "policy_digest": _canonical_digest({
            key: policy.get(key) for key in (
                "mode", "score_target", "minimum_scored_mutants", "max_new_actionable_survivors",
                "max_untested", "max_mutant_timeouts", "max_suspicious_mutants",
            )
        }),
        "source_scope_digest": _canonical_digest({
            file: hashlib.sha256((Path(root) / file).read_bytes()).hexdigest()
            for file in expected
        }),
        "test_mapping_digest": _canonical_digest(mapping),
        "line_range_digest": _canonical_digest(line_ranges),
    }
    return {
        "schema_version": "2",
        "status": "completed",
        "revision": first["revision"],
        "merge_base": None,
        "selection": "all",
        "files_tested": expected,
        "deleted_files": [],
        "engine_version": first["engine_version"],
        "test_runner": first["test_runner"],
        "tests_run": sorted({test for report in reports for test in report["tests_run"]}),
        "line_ranges": line_ranges,
        "shard_count": shard_count,
        **evidence_identity,
        **counts,
        "non_killed": records,
        "survivor_preview": [record for record in records if record["state"] == "survived"][:20],
        "survivors": survivors,
        **policy_result,
        "threshold": threshold,
        "duration_ms": max(report["duration_ms"] for report in reports),
        "total_duration_ms": sum(report["duration_ms"] for report in reports),
    }


def aggregate_preflight_shards(
    root: str,
    reports: list[dict],
    paths: list[str],
    excluded: list[str],
    shard_count: int,
) -> dict:
    """Accept a preflight corpus only when bounded shards exactly cover it once."""
    if len(reports) != shard_count:
        return _error("unknown", f"Preflight aggregation requires exactly {shard_count} shard reports")
    reports = sorted(reports, key=lambda report: report.get("shard_index", -1))
    if [report.get("shard_index") for report in reports] != list(range(shard_count)):
        return _error("unknown", "Preflight shard indexes are incomplete or duplicated")
    fingerprints: list[str] = []
    corpus: list[dict] = []
    tested_lines: list[tuple[str, int]] = []
    for index, report in enumerate(reports):
        if report.get("status") != "completed" or report.get("passed") is not True:
            return _error("tool_error", f"Preflight shard {index} is not completed")
        if report.get("engine_version") != MUTMUT_VERSION or report.get("shard_count") != shard_count:
            return _error("unknown", f"Preflight shard {index} has inconsistent execution identity")
        if report.get("generated") != report.get("canonicalized"):
            return _error("unknown", f"Preflight shard {index} does not reconcile generated details")
        shard_fingerprints = report.get("fingerprints")
        shard_corpus = report.get("corpus")
        ranges = report.get("line_ranges")
        if (
            not isinstance(shard_fingerprints, list) or not isinstance(shard_corpus, list)
            or not isinstance(ranges, list) or not ranges
            or sorted(record.get("fingerprint") for record in shard_corpus if isinstance(record, dict))
            != sorted(shard_fingerprints)
            or not re.fullmatch(r"[0-9a-f]{64}", str(report.get("manifest_digest", "")))
        ):
            return _error("unknown", f"Preflight shard {index} has incomplete evidence")
        fingerprints.extend(shard_fingerprints)
        corpus.extend({**record, "shard_index": index} for record in shard_corpus)
        for item in ranges:
            if not isinstance(item, dict) or set(item) != {"file", "start", "end"}:
                return _error("unknown", f"Preflight shard {index} has malformed ranges")
            tested_lines.extend((item["file"], line) for line in range(item["start"], item["end"] + 1))
    expected_files = [
        path for path in _get_all_py_files(root, paths)
        if not any(path.startswith(item) for item in excluded)
    ]
    expected_lines = {
        (file, line)
        for file in expected_files
        for line in range(1, len((Path(root) / file).read_text(encoding="utf-8").splitlines()) + 1)
    }
    if len(tested_lines) != len(set(tested_lines)) or set(tested_lines) != expected_lines:
        return _error("unknown", "Preflight shards do not exactly cover full mutation scope")
    if len(fingerprints) != len(set(fingerprints)):
        return _error("unknown", "Preflight shards contain duplicate or colliding fingerprints")
    generated = sum(report["generated"] for report in reports)
    return {
        "status": "completed", "passed": True, "engine_version": MUTMUT_VERSION,
        "revision": _revision(root),
        "shard_count": shard_count, "generated": generated, "canonicalized": generated,
        "collisions": 0, "files": expected_files, "fingerprints": sorted(fingerprints),
        "corpus": sorted(corpus, key=lambda record: record["fingerprint"]),
        "corpus_digest": _canonical_digest(sorted(corpus, key=lambda record: record["fingerprint"])),
        "manifest_digests": [report["manifest_digest"] for report in reports],
    }


def evaluate_stability(reports: list[dict], run_ids: list[str] | None = None) -> dict:
    """Accept only three equivalent, successful full-run mutation reports."""
    if len(reports) != 3:
        return {"status": "unstable", "errors": ["stability requires exactly three reports"]}
    if run_ids is not None and len(run_ids) != 3:
        return {"status": "unstable", "errors": ["stability requires exactly three run IDs"]}

    for index, report in enumerate(reports, start=1):
        if report.get("status") != "completed":
            return {"status": "unstable", "errors": [f"report {index} is not completed"]}
        if report.get("schema_version") != "2":
            return {"status": "unstable", "errors": [f"report {index} has an unsupported schema"]}
        try:
            _validate_report_schema(report)
        except ValueError as exc:
            return {"status": "unstable", "errors": [f"report {index} has invalid evidence: {exc}"]}
        if report.get("selection") != "all":
            return {"status": "unstable", "errors": [f"report {index} is not a full mutation run"]}
        if not re.fullmatch(r"[0-9a-f]{40}", str(report.get("revision", ""))):
            return {"status": "unstable", "errors": [f"report {index} has an invalid revision"]}
        if report.get("engine_version") != MUTMUT_VERSION:
            return {"status": "unstable", "errors": [f"report {index} has an unsupported engine"]}
        if report.get("test_runner") != _TEST_RUNNER:
            return {"status": "unstable", "errors": [f"report {index} has an unsupported test runner"]}
        if not isinstance(report.get("files_tested"), list) or not report["files_tested"]:
            return {"status": "unstable", "errors": [f"report {index} has no tested files"]}
        tests_run = report.get("tests_run")
        if not isinstance(tests_run, list) or not tests_run or tests_run != sorted(set(tests_run)):
            return {"status": "unstable", "errors": [f"report {index} has invalid targeted tests"]}
        if not isinstance(report.get("line_ranges"), list) or not report["line_ranges"]:
            return {"status": "unstable", "errors": [f"report {index} has no source ranges"]}
        counts = [report.get(state) for state in _STATES]
        if any(not isinstance(count, int) or isinstance(count, bool) or count < 0 for count in counts):
            return {"status": "unstable", "errors": [f"report {index} has invalid outcomes"]}
        expected_score = compute_score(*(report[state] for state in _STATES[:5]))
        if expected_score is None or report.get("score") != round(expected_score, 1):
            return {"status": "unstable", "errors": [f"report {index} has an invalid score"]}
        duration = report.get("duration_ms")
        if not isinstance(duration, int) or isinstance(duration, bool) or not 0 <= duration <= _STABILITY_RUNTIME_MS:
            return {"status": "unstable", "errors": [f"report {index} exceeds the runtime bound"]}

    first = reports[0]
    if any(report["revision"] != first["revision"] for report in reports[1:]):
        return {"status": "unstable", "errors": ["report revisions differ"]}
    identity = ("engine_version", "test_runner", "files_tested", "tests_run", "line_ranges")
    if any(any(report[key] != first[key] for key in identity) for report in reports[1:]):
        return {"status": "unstable", "errors": ["report execution scopes differ"]}
    outcomes = (*_STATES, "score")
    if any(any(report[key] != first[key] for key in outcomes) for report in reports[1:]):
        return {"status": "unstable", "errors": ["report outcomes differ"]}
    canonical = sorted((record["fingerprint"], record["state"]) for record in first["non_killed"])
    if any(sorted((record["fingerprint"], record["state"]) for record in report["non_killed"]) != canonical for report in reports[1:]):
        return {"status": "unstable", "errors": ["report canonical mutant outcomes differ"]}

    return {
        "status": "stable",
        "baseline": {
            "schema_version": "2",
            "revision": first["revision"],
            "engine_version": first["engine_version"],
            "test_runner": first["test_runner"],
            "files_tested": first["files_tested"],
            "non_killed": first["non_killed"],
            **{key: first[key] for key in outcomes},
            "run_ids": run_ids or [],
            "max_duration_ms": max(report["duration_ms"] for report in reports),
        },
    }


def _rerun(root: str, paths: list[str], timeout: int, threshold: float, base: str, all_files: bool) -> str:
    argv = [
        sys.executable, "-m", "fettle.mutation_test", "--root", root,
        "--paths", ",".join(paths), "--timeout", str(timeout), "--threshold", str(threshold),
    ]
    argv.extend(["--all"] if all_files else ["--base", base])
    return shlex.join([*argv, "--json"])


def run_mutation_test(root: str, cfg: dict) -> dict:
    paths = cfg.get("paths", ["src/"])
    excluded = cfg.get("exclude", ["tests/", "migrations/"])
    timeout = int(cfg.get("timeout_s", 600))
    # Learning (2026-08-25): large files need proportionally longer mutation
    # timeouts. Scale by line count: base 600s for ≤500 lines, +1s per line above.
    if cfg.get("auto_scale_timeout", True):
        for file_path in paths:
            abs_path = Path(root) / file_path
            if abs_path.is_file():
                line_count = len(abs_path.read_text(encoding="utf-8").splitlines())
                scaled = max(timeout, 600 + max(0, line_count - 500))
                timeout = max(timeout, scaled)
    threshold = float(cfg.get("score_target", cfg.get("threshold", 70)))
    base = str(cfg.get("base", "origin/main"))
    all_files = bool(cfg.get("all", False))
    shard_index = cfg.get("shard_index")
    shard_count = cfg.get("shard_count")
    test_mappings = cfg.get("test_mappings", {})
    default_chunk_lines = int(cfg.get("default_chunk_lines", 60))
    chunk_lines = cfg.get("chunk_lines", {})
    manifest = load_partition_manifest(Path(cfg["manifest"])) if cfg.get("manifest") else None
    if manifest is not None:
        if manifest["shard_count"] != cfg.get("full_shards", manifest["shard_count"]):
            return _error("unknown", "Mutation partition manifest shard count does not match configuration")
        all_files = True
        shard_index = manifest["shard_index"]
        shard_count = manifest["shard_count"]
    rerun = _rerun(root, paths, timeout, threshold, base, all_files)
    if not _has_mutmut():
        return _error(
            "tool_error",
            f"mutmut not found. Install: python -m pip install mutmut=={MUTMUT_VERSION}",
            rerun_command=rerun,
        )

    try:
        revision_result = _run(["git", "rev-parse", "HEAD"], root, 10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _error("tool_error", f"Cannot resolve tested revision: {exc}", rerun_command=rerun)
    revision = revision_result.stdout.strip()
    if revision_result.returncode or not re.fullmatch(r"[0-9a-f]{40}", revision):
        return _error("unknown", "Cannot resolve tested revision", rerun_command=rerun)
    if manifest is not None and manifest["revision"] != revision:
        return _error("unknown", "Mutation partition manifest revision is stale", rerun_command=rerun)
    if all_files:
        try:
            (Path(root) / ".mutmut-cache").unlink(missing_ok=True)
        except OSError as exc:
            return _error("tool_error", f"Cannot clear native mutation cache: {exc}", rerun_command=rerun)

    selection = (
        {"status": "completed", "merge_base": None, "files": _get_all_py_files(root, paths), "deleted": []}
        if all_files else _get_changed_py_files(root, paths, base)
    )
    if selection["status"] != "completed":
        return {**selection, "files_tested": [], "deleted_files": selection.get("deleted", []), "rerun_command": rerun}
    files = [path for path in selection["files"] if not any(path.startswith(item) for item in excluded)]
    line_ranges: list[dict] | None = None
    if shard_index is not None or shard_count is not None:
        if not all_files or not isinstance(shard_index, int) or not isinstance(shard_count, int):
            return _error("unknown", "Sharding requires --all, --shard-index, and --shard-count")
        try:
            line_ranges = _shard_ranges(
                root, files, shard_index, shard_count,
                default_chunk_lines, chunk_lines, test_mappings,
            )
            files = sorted({item["file"] for item in line_ranges})
            if manifest is not None and (manifest["files"] != files or manifest["ranges"] != line_ranges):
                return _error("unknown", "Mutation partition manifest does not match recomputed scope")
        except (OSError, ValueError) as exc:
            return _error("unknown", "Cannot choose mutation partition: " + str(exc))
    common = {
        "schema_version": "2",
        "revision": revision,
        "merge_base": selection["merge_base"],
        "selection": "shard" if shard_index is not None else ("all" if all_files else "changed"),
        "files_tested": files,
        "deleted_files": selection["deleted"],
        "rerun_command": rerun,
    }
    if shard_index is not None:
        common.update({"shard_index": shard_index, "shard_count": shard_count})
    if not files:
        return {
            "status": "not_applicable", "message": "No existing implementation files changed",
            "score": None, "passed": True, **common,
        }
    mapping = _mapped_tests(root, files, test_mappings)
    unmapped = [file for file, tests in mapping.items() if not tests]
    if unmapped:
        return _error("unknown", "No targeted tests mapped for: " + ", ".join(unmapped), **common)
    tests = sorted({test for mapped in mapping.values() for test in mapped})
    source_scope = {
        file: hashlib.sha256((Path(root) / file).read_bytes()).hexdigest()
        for file in files
    }
    evidence_identity = {
        "policy_digest": _canonical_digest({
            key: cfg.get(key) for key in (
                "mode", "score_target", "minimum_scored_mutants", "max_new_actionable_survivors",
                "max_untested", "max_mutant_timeouts", "max_suspicious_mutants",
            )
        }),
        "source_scope_digest": _canonical_digest(source_scope),
        "test_mapping_digest": _canonical_digest(mapping),
        "line_range_digest": _canonical_digest(line_ranges or [
            {"file": file, "start": 1, "end": len((Path(root) / file).read_text(encoding="utf-8").splitlines())}
            for file in files
        ]),
    }
    cache_identity = None if all_files or line_ranges else _runtime_cache_identity(root, files, mapping, cfg)
    cache_reused = bool(
        cache_identity is not None and restore_mutation_native_cache(root, cache_identity)
    )
    result = (
        _run_shard_modules(root, mapping, line_ranges, timeout)
        if line_ranges else _run_mutmut(root, files, tests, timeout, test_mapping=mapping)
    )
    if result["status"] != "completed":
        return {**result, **common}
    if cache_identity is not None:
        save_mutation_native_cache(root, cache_identity)
    result["cache_reused"] = cache_reused
    policy = evaluate_policy(result, cfg)
    if policy["score"] is None:
        if line_ranges:
            return {**result, **policy, **evidence_identity, "threshold": threshold, "passed": True, **common}
        evidence = {key: value for key, value in result.items() if key != "status"}
        return _error("unknown", "mutmut reported zero scored mutants", **evidence, **common)
    return {**result, **policy, **evidence_identity, "threshold": threshold, **common}


def run_mutation_preflight(root: str, cfg: dict) -> dict:
    paths = cfg.get("paths", ["src/"])
    excluded = cfg.get("exclude", ["tests/", "migrations/"])
    if not _has_mutmut():
        return _error(
            "tool_error",
            f"mutmut not found. Install: python -m pip install mutmut=={MUTMUT_VERSION}",
        )
    try:
        (Path(root) / ".mutmut-cache").unlink(missing_ok=True)
    except OSError as exc:
        return _error("tool_error", f"Cannot clear native mutation cache: {exc}")
    manifest = load_partition_manifest(Path(cfg["manifest"])) if cfg.get("manifest") else None
    files = [
        path for path in _get_all_py_files(root, paths)
        if not any(path.startswith(item) for item in excluded)
    ]
    line_ranges = None
    if manifest is not None:
        revision = _revision(root)
        if manifest["revision"] != revision:
            return _error("unknown", "Mutation preflight partition manifest revision is stale")
        files = manifest["files"]
        line_ranges = manifest["ranges"]
    if not files:
        return _error("unknown", "Mutation preflight found no configured implementation files")
    mapping = _mapped_tests(root, files, cfg.get("test_mappings", {}))
    unmapped = [file for file, tests in mapping.items() if not tests]
    if unmapped:
        return _error("unknown", "No targeted tests mapped for: " + ", ".join(unmapped))
    tests = sorted({test for mapped in mapping.values() for test in mapped})
    timeout = int(cfg.get("full_timeout_s", 2100))
    result = (
        _preflight_shard_modules(root, mapping, line_ranges, timeout)
        if line_ranges else _preflight_mutmut(root, files, tests, mapping, timeout)
    )
    if manifest is not None:
        result.update({
            "shard_index": manifest["shard_index"], "shard_count": manifest["shard_count"],
            "manifest_digest": manifest["digest"],
        })
    return result


def format_report(report: dict) -> str:
    lines = ["# Mutation Test Report", "", f"**Status:** {report['status']}"]
    if report.get("message"):
        lines.extend(["", report["message"]])
    if report["status"] == "completed":
        lines.extend([
            f"**Score:** {report['score']}%" + (" PASS" if report["passed"] else " FAIL"),
            f"**Engine:** mutmut {report['engine_version']}",
            *[f"**{state.title()}:** {report[state]}" for state in _STATES],
            f"**Threshold:** {report['threshold']}%",
        ])
        preview = report.get("survivor_preview", [])
        if preview:
            lines.extend([
                "", "## Surviving Mutants",
                *[f"- {item['file']}:{item['line']} {item['before']} -> {item['after']} (`{item['rerun_command']}`)" for item in preview],
            ])
    if report.get("rerun_command"):
        lines.extend(["", f"**Rerun:** `{report['rerun_command']}`"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fettle mutation testing")
    parser.add_argument("--root", default=".")
    parser.add_argument("--paths")
    parser.add_argument("--base")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    parser.add_argument("--manifest", help="Digest-bound full-run partition manifest")
    parser.add_argument("--manifest-scope", metavar="DIRECTORY", help="Complete manifest set defining execution scope")
    parser.add_argument("--prepare-manifests", metavar="DIRECTORY", help="Write configured full-run manifests")
    parser.add_argument("--prepare-changed-manifests", metavar="DIRECTORY", help="Write bounded changed-scope manifests")
    parser.add_argument("--prepare-replay-matrix", metavar="DIRECTORY", help="Select incomplete initial shards for retry")
    parser.add_argument("--aggregate", metavar="DIRECTORY", help="Aggregate reports; requires --shard-count")
    parser.add_argument("--aggregate-scope", metavar="DIRECTORY", help="Digest-bound manifests defining aggregate scope")
    parser.add_argument("--preflight-manifest", help="Run bounded preflight from a partition manifest")
    parser.add_argument("--aggregate-preflight", metavar="DIRECTORY", help="Aggregate bounded preflight reports")
    parser.add_argument("--resume-manifest", help="Run a resumable manifest-bound calibration shard")
    parser.add_argument("--retained-preflight", help="Complete retained preflight aggregate")
    parser.add_argument("--calibration-id", help="Logical calibration identity")
    parser.add_argument("--checkpoint-output", help="Atomic resumable checkpoint output")
    parser.add_argument("--resume-checkpoints", help="Directory containing same-calibration checkpoints")
    parser.add_argument("--initialize-timeout-report", metavar="PATH", help=argparse.SUPPRESS)
    parser.add_argument("--github-summary", metavar="REPORT", help=argparse.SUPPRESS)
    parser.add_argument("--artifact-name", help=argparse.SUPPRESS)
    parser.add_argument("--artifact-url", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    from fettle.config import load_config

    mutation = load_config(args.root)["mutation"]
    if args.initialize_timeout_report:
        manifest = load_partition_manifest(Path(args.manifest)) if args.manifest else None
        write_timeout_evidence(Path(args.initialize_timeout_report), args.timeout or 720, manifest)
        return 0
    if args.github_summary:
        try:
            report = json.loads(Path(args.github_summary).read_text(encoding="utf-8"))
            if not isinstance(report, dict):
                raise ValueError("mutation summary report must be a JSON object")
            summary = format_github_summary(
                report, args.artifact_name or "mutation-evidence", args.artifact_url or "#",
            )
            Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(summary, encoding="utf-8")
        except (KeyError, OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"Cannot write mutation summary: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.prepare_replay_matrix:
        try:
            if args.shard_count is None or args.shard_count < 1:
                raise ValueError("--prepare-replay-matrix requires a positive --shard-count")
            report_paths = sorted(Path(args.prepare_replay_matrix).rglob("mutation-report.json"))
            reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
            report = prepare_shard_replay_matrix(reports, args.shard_count)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            report = _error("unknown", f"Cannot prepare mutation replay: {exc}")
        print(json.dumps(report, indent=2) if args.json else format_report(report))
        return 0 if report["status"] == "completed" else 2
    if args.prepare_manifests or args.prepare_changed_manifests:
        try:
            if args.prepare_changed_manifests:
                paths, changed_files = write_changed_partition_manifests(
                    args.root, mutation, Path(args.prepare_changed_manifests), args.base or mutation["base"],
                )
            else:
                paths = write_partition_manifests(args.root, mutation, Path(args.prepare_manifests))
                changed_files = []
            report = {
                "status": "completed", "passed": True, "shard_count": len(paths),
                "matrix": {"shard": list(range(len(paths)))},
                **({"files": changed_files} if args.prepare_changed_manifests else {}),
            }
        except (OSError, ValueError) as exc:
            report = _error("unknown", f"Cannot prepare mutation manifests: {exc}")
        print(json.dumps(report, indent=2) if args.json else format_report(report))
        return 0 if report["status"] == "completed" else 2
    paths = args.paths.split(",") if args.paths else mutation["paths"]
    excluded = mutation["exclude"]
    threshold = args.threshold if args.threshold is not None else mutation["score_target"]
    timeout = args.timeout if args.timeout is not None else (
        mutation["full_timeout_s"] if args.all else mutation["timeout_s"]
    )
    base = args.base or mutation["base"]
    if args.resume_manifest:
        missing = [
            name for name, value in (
                ("--retained-preflight", args.retained_preflight),
                ("--calibration-id", args.calibration_id),
                ("--checkpoint-output", args.checkpoint_output),
            ) if not value
        ]
        if missing:
            report = _error("unknown", "--resume-manifest requires " + ", ".join(missing))
        else:
            resume_paths = (
                sorted(Path(args.resume_checkpoints).rglob("mutation-checkpoint.json"))
                if args.resume_checkpoints else []
            )
            report = run_resumable_mutation_shard(
                args.root, mutation, Path(args.resume_manifest), Path(args.retained_preflight),
                args.calibration_id, Path(args.checkpoint_output), timeout, resume_paths,
            )
    elif args.preflight_manifest:
        report = run_mutation_preflight(args.root, {**mutation, "manifest": args.preflight_manifest})
    elif args.aggregate_preflight:
        if args.shard_count is None or args.shard_count < 1:
            report = _error("unknown", "--aggregate-preflight requires a positive --shard-count")
        else:
            report_paths = sorted(Path(args.aggregate_preflight).rglob("mutation-preflight.json"))
            try:
                reports = [json.loads(path.read_text()) for path in report_paths]
            except (OSError, json.JSONDecodeError) as exc:
                report = _error("unknown", f"Cannot read preflight shard reports: {exc}")
            else:
                report = aggregate_preflight_shards(args.root, reports, paths, excluded, args.shard_count)
    elif args.aggregate:
        if args.shard_count is None or args.shard_count < 1:
            report = _error("unknown", "--aggregate requires a positive --shard-count")
        else:
            report_paths = sorted(Path(args.aggregate).rglob("mutation-report.json"))
            try:
                reports = [json.loads(path.read_text()) for path in report_paths]
                if args.aggregate_scope:
                    manifests = [
                        load_partition_manifest(path)
                        for path in sorted(Path(args.aggregate_scope).glob("partition-*.json"))
                    ]
                    if len(manifests) != args.shard_count:
                        raise ValueError("aggregate scope manifests are incomplete")
                    paths = sorted({file for manifest in manifests for file in manifest["files"]})
                    selection = _get_changed_py_files(args.root, mutation["paths"], args.base or mutation["base"])
                    if selection["status"] != "completed":
                        raise ValueError(selection["message"])
                    expected = [
                        file for file in selection["files"]
                        if not any(file.startswith(item) for item in excluded)
                    ]
                    if paths != expected:
                        raise ValueError("aggregate manifests do not match changed-file scope")
            except (OSError, json.JSONDecodeError) as exc:
                report = _error("unknown", f"Cannot read shard reports: {exc}")
            except ValueError as exc:
                report = _error("unknown", f"Cannot verify aggregate scope: {exc}")
            else:
                try:
                    reports = select_shard_attempts(reports, args.shard_count)
                except ValueError as exc:
                    report = _error("unknown", f"Cannot reconcile shard attempts: {exc}")
                    output = json.dumps(report, indent=2) if args.json else format_report(report)
                    sys.stdout.write(output + ("" if output.endswith("\n") else "\n"))
                    return 2
                report = aggregate_shards(
                    args.root, reports, paths, excluded, args.shard_count, threshold,
                    mutation["test_mappings"], mutation,
                )
    else:
        if args.manifest_scope:
            try:
                scope_manifests = [
                    load_partition_manifest(path)
                    for path in sorted(Path(args.manifest_scope).glob("partition-*.json"))
                ]
                if args.shard_count is None or len(scope_manifests) != args.shard_count:
                    raise ValueError("execution scope manifests are incomplete")
                paths = sorted({file for manifest in scope_manifests for file in manifest["files"]})
            except (OSError, ValueError) as exc:
                report = _error("unknown", f"Cannot verify execution scope: {exc}")
                output = json.dumps(report, indent=2) if args.json else format_report(report)
                sys.stdout.write(output + ("" if output.endswith("\n") else "\n"))
                return 2
        report = run_mutation_test(args.root, {
            **mutation,
            "paths": paths, "exclude": excluded, "base": base, "all": args.all,
            "timeout_s": timeout, "score_target": threshold,
            "shard_index": args.shard_index, "shard_count": args.shard_count,
            "manifest": args.manifest,
            **({"full_shards": args.shard_count} if args.manifest and args.shard_count is not None else {}),
        })
    output = json.dumps(report, indent=2) if args.json else format_report(report)
    sys.stdout.write(output + ("" if output.endswith("\n") else "\n"))
    if report["status"] not in {"completed", "not_applicable"}:
        return 2
    return 0 if report.get("passed", True) else 1


if __name__ == "__main__":
    sys.exit(main())
