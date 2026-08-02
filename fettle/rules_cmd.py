"""Fettle rules — machine-drafted rule file lifecycle (WP-163, C3).

`rules/proposed/` (machine-drafted quarantine, never loaded by gates) and
`rules/learned/` (human-approved, loadable via `.fettle.toml
[rules].extra_dirs`) are stages of a file lifecycle:

    fettle rules list                   # both stages + ratchet evidence
    fettle rules promote <id>           # proposed -> learned (HUMAN gate)
    fettle rules promote --candidates   # computed stats, no decisions
    fettle rules demote <id> --reason   # learned -> proposed

Boundary with `fettle ratchet`: ratchet governs the *mode* (advisory vs
enforce) of a loaded rule with an evidence bar; this module governs *which
files exist where*. File promotion has no evidence threshold — the human
judgment is the gate (D-C4); a proposal with an empty pattern (evidence
brief) is refused until completed.
"""

from __future__ import annotations

import re
from pathlib import Path

from fettle.learn import LEARNED_RULES_DIR, PROPOSED_RULES_DIR

_EMPTY_PATTERN_RE = re.compile(r"^\s*pattern:\s*(''|\"\")\s*$", re.MULTILINE)

# Ratchet's evidence bars, reused for candidate listing (not decisions).
_PROMOTE_MIN_FIRES = 5
_PROMOTE_MAX_FP = 0.2
_DEMOTE_MIN_FIRES = 3
_DEMOTE_MIN_FP = 0.5


def _stage_dir(root: Path, stage: str) -> Path:
    return root / (PROPOSED_RULES_DIR if stage == "proposed" else LEARNED_RULES_DIR)


def _pattern_is_empty(path: Path) -> bool:
    try:
        return bool(_EMPTY_PATTERN_RE.search(path.read_text(encoding="utf-8")))
    except OSError:
        return True  # unreadable = not promotable


def list_rules(root: Path) -> list[dict]:
    """Proposed + learned rule files joined with ratchet evidence by id."""
    from fettle.ratchet import aggregate_evidence

    evidence = aggregate_evidence(root)
    rows: list[dict] = []
    for stage in ("proposed", "learned"):
        stage_path = _stage_dir(root, stage)
        if not stage_path.is_dir():
            continue
        for yml in sorted(stage_path.glob("*.yml")):
            ev = evidence.get(yml.stem)
            rows.append({
                "id": yml.stem,
                "stage": stage,
                "path": str(yml.relative_to(root)),
                "pattern_empty": _pattern_is_empty(yml),
                "fires": ev.total_fires if ev else 0,
                "false_positives": ev.false_positives if ev else 0,
                "fp_rate": round(ev.fp_rate, 3) if ev else 0.0,
            })
    return rows


def promote_rule_file(root: Path, rule_id: str) -> tuple[bool, str]:
    """Move a proposal to rules/learned/ — the explicit human approval step."""
    src = _stage_dir(root, "proposed") / f"{rule_id}.yml"
    dst = _stage_dir(root, "learned") / f"{rule_id}.yml"
    if not src.is_file():
        return False, f"no proposal named '{rule_id}' in {PROPOSED_RULES_DIR}/"
    if dst.exists():
        return False, f"'{rule_id}' already exists in {LEARNED_RULES_DIR}/"
    if _pattern_is_empty(src):
        return False, (
            f"'{rule_id}' is an evidence brief with an empty pattern — "
            "complete the pattern before promoting"
        )
    content = src.read_text(encoding="utf-8")
    content = content.replace("status: proposed", "status: learned")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")
    src.unlink()
    return True, (
        f"promoted '{rule_id}' → {LEARNED_RULES_DIR}/ — load it via "
        "[rules].extra_dirs; mode starts advisory (fettle ratchet governs enforce)"
    )


def demote_rule_file(root: Path, rule_id: str, reason: str) -> tuple[bool, str]:
    """Move a learned rule back to quarantine, recording why."""
    if not reason.strip():
        return False, "a reason is required for demotion"
    src = _stage_dir(root, "learned") / f"{rule_id}.yml"
    dst = _stage_dir(root, "proposed") / f"{rule_id}.yml"
    if not src.is_file():
        return False, f"no learned rule named '{rule_id}' in {LEARNED_RULES_DIR}/"
    if dst.exists():
        return False, f"'{rule_id}' already exists in {PROPOSED_RULES_DIR}/"
    content = src.read_text(encoding="utf-8")
    content = content.replace("status: learned", "status: proposed")
    content += f'# demoted: "{reason.strip()}"\n'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")
    src.unlink()
    return True, f"demoted '{rule_id}' → {PROPOSED_RULES_DIR}/ (reason: {reason.strip()})"


def promotion_candidates(root: Path) -> dict:
    """Computed stats for human decisions — never acts (D-C4).

    - pending: proposals awaiting review (evidence briefs flagged)
    - promote: learned advisory rules meeting ratchet's evidence bar
    - demote: noisy learned rules (FP > 50% over >= 3 fires)
    """
    from fettle.ratchet import load_ratchet

    rows = list_rules(root)
    modes = {rid: rd.get("mode", "advisory")
             for rid, rd in load_ratchet(root).get("rules", {}).items()}

    pending = [r for r in rows if r["stage"] == "proposed"]
    learned = [r for r in rows if r["stage"] == "learned"]
    promote = [
        r for r in learned
        if modes.get(r["id"], "advisory") == "advisory"
        and r["fires"] >= _PROMOTE_MIN_FIRES and r["fp_rate"] <= _PROMOTE_MAX_FP
    ]
    demote = [
        r for r in learned
        if r["fires"] >= _DEMOTE_MIN_FIRES and r["fp_rate"] > _DEMOTE_MIN_FP
    ]
    return {"pending": pending, "promote": promote, "demote": demote}


def render_rules_table(rows: list[dict]) -> str:
    if not rows:
        return ("No proposed or learned rules. "
                "Draft some: fettle learn --from-trace")
    lines = [f"{'Rule':<32} {'Stage':<10} {'Fires':<7} {'FP%':<7} Note"]
    lines.append("-" * 70)
    for r in rows:
        fp_pct = f"{r['fp_rate']:.0%}" if r["fires"] else "n/a"
        note = "needs pattern" if r["pattern_empty"] else ""
        lines.append(f"{r['id']:<32} {r['stage']:<10} {r['fires']:<7} "
                     f"{fp_pct:<7} {note}")
    return "\n".join(lines)


def render_candidates(data: dict) -> str:
    lines = ["── Rule pipeline candidates (stats computed, decisions are yours) ──"]
    for section, title, action in (
        ("pending", "Pending proposals", "fettle rules promote <id>"),
        ("promote", "Mode-promotion candidates (advisory → enforce)",
         "fettle ratchet promote <id>"),
        ("demote", "Noisy rules (demotion candidates)",
         "fettle rules demote <id> --reason ..."),
    ):
        rows = data[section]
        lines.append(f"\n{title}: {len(rows)}")
        for r in rows:
            flag = " [needs pattern]" if r.get("pattern_empty") else ""
            lines.append(f"  • {r['id']} — fires {r['fires']}, "
                         f"FP {r['fp_rate']:.0%}{flag}")
        if rows:
            lines.append(f"  → {action}")
    return "\n".join(lines)
