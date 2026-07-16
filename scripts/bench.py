#!/usr/bin/env python3
"""WP-118 — Noise benchmark for rule packs (`fettle bench`).

Runs every pack in rules/ over named corpora, computes findings-per-KLOC
per rule, and compares against committed budgets. A rule regressing past
its budget fails the bench. New (unbudgeted) rules are reported, never
blocking — budgets are adopted deliberately via --update-budgets.
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = PLUGIN_ROOT / "rules"

_SOURCE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".go")


@dataclass
class CorpusMeasurement:
    kloc: float
    findings_per_rule: dict[str, int] = field(default_factory=dict)

    def rate_per_kloc(self, rule_id: str) -> float:
        if self.kloc <= 0:
            return 0.0
        return self.findings_per_rule.get(rule_id, 0) / self.kloc


@dataclass
class BenchResult:
    measurements: dict[str, CorpusMeasurement]
    violations: list[str]
    unbudgeted: dict[str, list[str]]

    @property
    def passed(self) -> bool:
        return not self.violations


def load_budgets(path: str | Path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def _count_kloc(corpus_dir: Path) -> float:
    total = 0
    for f in corpus_dir.rglob("*"):
        if f.is_file() and f.suffix in _SOURCE_EXTENSIONS:
            total += sum(1 for _ in f.open(errors="replace"))
    return total / 1000.0


def _scan_corpus(corpus_dir: Path) -> dict[str, int]:
    config_args: list[str] = []
    for pack in sorted(RULES_DIR.glob("*.yml")):
        config_args.extend(["--config", str(pack)])
    proc = subprocess.run(
        ["semgrep", "scan", *config_args, "--json", "--quiet", "--metrics=off",
         "--project-root", ".", "."],
        capture_output=True, text=True, timeout=600, cwd=str(corpus_dir),
    )
    data = json.loads(proc.stdout)
    counts: dict[str, int] = {}
    for r in data.get("results", []):
        rule_id = r["check_id"].split(".")[-1]
        counts[rule_id] = counts.get(rule_id, 0) + 1
    return counts


def run_bench(
    corpora: dict[str, str],
    budgets: dict,
    update_budgets_path: str | Path | None = None,
) -> BenchResult:
    """Measure all corpora, enforce budgets, optionally write new budgets."""
    measurements: dict[str, CorpusMeasurement] = {}
    violations: list[str] = []
    unbudgeted: dict[str, list[str]] = {}

    for name, root in corpora.items():
        corpus_dir = Path(root)
        if not corpus_dir.is_dir():
            raise FileNotFoundError(f"corpus '{name}' not found at {root}")
        m = CorpusMeasurement(kloc=_count_kloc(corpus_dir), findings_per_rule=_scan_corpus(corpus_dir))
        measurements[name] = m
        corpus_budgets = budgets.get(name, {})
        unbudgeted[name] = sorted(r for r in m.findings_per_rule if r not in corpus_budgets)
        for rule_id, budget in corpus_budgets.items():
            rate = m.rate_per_kloc(rule_id)
            if rate > budget:
                violations.append(
                    f"{name}: {rule_id} at {rate:.2f} findings/KLOC exceeds budget {budget:.2f}"
                )

    if update_budgets_path is not None:
        # Round UP to 4 decimals: a freshly written budget must pass its own
        # immediate re-verify (rounding down fails at the equality boundary).
        new_budgets = {
            name: {
                rule: math.ceil(m.rate_per_kloc(rule) * 10000) / 10000
                for rule in sorted(m.findings_per_rule)
            }
            for name, m in measurements.items()
        }
        Path(update_budgets_path).write_text(json.dumps(new_budgets, indent=2) + "\n")

    return BenchResult(measurements=measurements, violations=violations, unbudgeted=unbudgeted)
