"""WP-116 — Rule-pack integrity gates.

Every rule in every pack under rules/*.yml MUST have:
  tests/fixtures/rulepacks/<pack-stem>/<rule-id>/fire/    — code that fires it
  tests/fixtures/rulepacks/<pack-stem>/<rule-id>/silent/  — code that stays silent

A rule without both fixture dirs fails this suite — fixture-less rules are
unverifiable and unverifiable rules die silently (see v0.4.1: an invalid TS
pack disabled every TS check for a full release).

Also here:
  - mutation check: a corrupted pack must fail `semgrep --validate`
    (proves the integrity gate itself is alive);
  - generated-rule check: the promise rule emitted by project_rules.py
    must validate.

Fixture dirs are scanned with --project-root anchored at the fire/ or
silent/ dir, so paths.include/exclude behave exactly as in production
(path-scoped rules place files under pipeline/, cmd/, scripts/, ...).
"""

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PLUGIN_DIR = Path(__file__).resolve().parent.parent
RULES_DIR = PLUGIN_DIR / "rules"
FIXTURE_ROOT = PLUGIN_DIR / "tests" / "fixtures" / "rulepacks"

sys.path.insert(0, str(PLUGIN_DIR / "scripts"))
from fettle.project_rules import generate_promise_rule  # noqa: E402
from fettle.semgrep_util import validate_rule_pack  # noqa: E402

_ENV = {**os.environ, "PATH": os.path.expanduser("~/.local/bin") + ":" + os.environ.get("PATH", "")}


def _has_semgrep() -> bool:
    try:
        r = subprocess.run(["semgrep", "--version"], capture_output=True, timeout=5, env=_ENV)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_semgrep(), reason="semgrep not available")

PACKS = sorted(RULES_DIR.glob("*.yml"))


def _rule_ids(pack: Path) -> list[str]:
    data = yaml.safe_load(pack.read_text())
    return [r["id"] for r in data.get("rules", [])]


ALL_RULES = [(pack, rule_id) for pack in PACKS for rule_id in _rule_ids(pack)]
RULE_TEST_IDS = [f"{pack.stem}::{rule_id}" for pack, rule_id in ALL_RULES]


def _scan(pack: Path, target_dir: Path) -> list[str]:
    result = subprocess.run(
        ["semgrep", "scan", "--config", str(pack), "--json", "--quiet",
         "--metrics=off", "--project-root", ".", "."],
        capture_output=True, text=True, timeout=60, env=_ENV, cwd=str(target_dir),
    )
    data = json.loads(result.stdout)
    return [r["check_id"].split(".")[-1] for r in data.get("results", [])]


def _fixture_dir(pack: Path, rule_id: str, kind: str) -> Path:
    return FIXTURE_ROOT / pack.stem / rule_id / kind


def test_packs_discovered():
    assert PACKS, "no rule packs found under rules/"
    assert len(ALL_RULES) >= 23, f"expected >= 23 rules, found {len(ALL_RULES)}"


@pytest.mark.parametrize("pack,rule_id", ALL_RULES, ids=RULE_TEST_IDS)
def test_rule_fires_on_fire_fixture(pack, rule_id):
    fire = _fixture_dir(pack, rule_id, "fire")
    assert fire.is_dir() and any(fire.rglob("*")), (
        f"INTEGRITY: rule '{rule_id}' has no fire/ fixture at {fire} — "
        f"a rule without fixtures is unverifiable and can die silently."
    )
    assert rule_id in _scan(pack, fire), (
        f"rule '{rule_id}' did not fire on its fire/ fixture"
    )


@pytest.mark.parametrize("pack,rule_id", ALL_RULES, ids=RULE_TEST_IDS)
def test_rule_silent_on_silent_fixture(pack, rule_id):
    silent = _fixture_dir(pack, rule_id, "silent")
    assert silent.is_dir() and any(silent.rglob("*")), (
        f"INTEGRITY: rule '{rule_id}' has no silent/ fixture at {silent} — "
        f"precision is unverifiable without a negative case."
    )
    assert rule_id not in _scan(pack, silent), (
        f"rule '{rule_id}' fired on its silent/ fixture (false positive)"
    )


# ── mutation check: the gate itself must be alive ────────────────────


def test_corrupted_pack_fails_validation(tmp_path):
    source = RULES_DIR / "llm-antipatterns.yml"
    corrupted = tmp_path / "corrupted.yml"
    # Inject a duplicate key — the exact defect class that shipped in v0.4.0.
    text = source.read_text().replace(
        "    severity: ERROR", "    severity: ERROR\n    severity: WARNING", 1
    )
    corrupted.write_text(text)
    valid, _ = validate_rule_pack(str(corrupted))
    assert not valid, (
        "MUTATION CHECK FAILED: validation accepted a pack with a "
        "duplicate key — the integrity gate is not actually guarding."
    )


def test_uncorrupted_pack_passes_validation():
    valid, err = validate_rule_pack(str(RULES_DIR / "llm-antipatterns.yml"))
    assert valid, err


# ── generated rules must meet the same bar ───────────────────────────


def test_generated_promise_rule_validates(tmp_path):
    cfg = {"rules": {"extra_dirs": [], "promise_apis": ["jQuery.ajax"]}}
    generated = generate_promise_rule(cfg, str(tmp_path))
    valid, err = validate_rule_pack(generated)
    assert valid, f"generated rule failed validation:\n{err}"
    shutil.rmtree(tmp_path / ".fettle", ignore_errors=True)
