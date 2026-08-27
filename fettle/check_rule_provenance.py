"""Fail closed when distributable rule assets lack provenance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


RULE_SUFFIXES = {".yml", ".yaml", ".toml"}
PLACEHOLDERS = {"", "?", "n/a", "tbd", "todo", "unknown"}


def _rule_files(rules_dir: Path) -> set[str]:
    return {
        path.relative_to(rules_dir).as_posix()
        for path in rules_dir.rglob("*")
        if path.is_file() and path.suffix in RULE_SUFFIXES
    }


def _entries(manifest: Path) -> tuple[dict[str, tuple[str, str, str]], list[str]]:
    entries: dict[str, tuple[str, str, str]] = {}
    errors: list[str] = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            errors.append(f"{manifest}:{line_number}: expected four table columns")
            continue
        path = cells[0].strip("`")
        values = tuple(cells[1:])
        if path in entries:
            errors.append(f"{manifest}:{line_number}: duplicate entry for {path}")
        elif any(value.casefold() in PLACEHOLDERS for value in values):
            errors.append(f"{manifest}:{line_number}: placeholder provenance for {path}")
        else:
            entries[path] = values
    return entries, errors


def validate(rules_dir: Path) -> list[str]:
    manifest = rules_dir / "PROVENANCE.md"
    if not manifest.is_file():
        return [f"missing provenance manifest: {manifest}"]
    entries, errors = _entries(manifest)
    files = _rule_files(rules_dir)
    errors.extend(
        f"unsupported rule extension casing: {path.relative_to(rules_dir).as_posix()}"
        for path in rules_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in RULE_SUFFIXES and path.suffix not in RULE_SUFFIXES
    )
    errors.extend(f"missing provenance entry: {path}" for path in sorted(files - entries.keys()))
    errors.extend(f"stale provenance entry: {path}" for path in sorted(entries.keys() - files))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rules_dir", nargs="?", type=Path, default=Path("rules"))
    args = parser.parse_args(argv)
    errors = validate(args.rules_dir)
    if errors:
        for error in errors:
            print(f"rule provenance: {error}", file=sys.stderr)
        return 1
    print(f"rule provenance: {len(_rule_files(args.rules_dir))} asset(s) documented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
