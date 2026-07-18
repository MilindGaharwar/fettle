"""Fettle ratchet workflow — per-rule TP/FP evidence, promote/demote with measurement.

Makes advisory-first a product feature: rules start advisory, promote to enforce
only when measured evidence supports it, demote requires the same evidence standard.

Data stored at {project_root}/.fettle/ratchet.json.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


SCHEMA_VERSION = "1"


@dataclass
class Evidence:
    """Aggregated evidence for a single rule."""

    total_fires: int = 0
    true_positives: int = 0
    false_positives: int = 0
    last_fire: str | None = None
    last_fp_stamp: str | None = None

    @property
    def fp_rate(self) -> float:
        if self.total_fires == 0:
            return 0.0
        return self.false_positives / self.total_fires


def _empty_ratchet() -> dict:
    """Return an empty ratchet data structure."""
    return {"schema_version": SCHEMA_VERSION, "rules": {}}


def load_ratchet(project_root: Path) -> dict:
    """Load .fettle/ratchet.json, return empty schema if missing."""
    ratchet_path = project_root / ".fettle" / "ratchet.json"
    if not ratchet_path.exists():
        return _empty_ratchet()
    try:
        data = json.loads(ratchet_path.read_text())
        if not isinstance(data, dict) or "rules" not in data:
            return _empty_ratchet()
        return data
    except (json.JSONDecodeError, OSError):
        return _empty_ratchet()


def save_ratchet(project_root: Path, data: dict) -> None:
    """Atomic write of ratchet data to .fettle/ratchet.json."""
    ratchet_dir = project_root / ".fettle"
    ratchet_dir.mkdir(parents=True, exist_ok=True)
    ratchet_path = ratchet_dir / "ratchet.json"

    content = json.dumps(data, indent=2) + "\n"
    # Atomic write: tmp in same dir then os.replace
    fd, tmp_path = tempfile.mkstemp(dir=str(ratchet_dir), suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        os.replace(tmp_path, str(ratchet_path))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _get_trace_path() -> str:
    """Get the trace JSONL path (mirrors trace.py logic)."""
    state_dir = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(state_dir, "fettle", "trace.jsonl")


def _get_fp_path() -> str:
    """Get the false-positives JSONL path (mirrors fp_stamp.py logic)."""
    state_dir = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
    return os.path.join(state_dir, "fettle", "false-positives.jsonl")


def _read_jsonl(path: str) -> list[dict]:
    """Read a JSONL file, skipping malformed lines."""
    if not os.path.isfile(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def aggregate_evidence(project_root: Path) -> dict[str, Evidence]:
    """Scan trace and FP files to compute per-rule evidence.

    Counts findings from trace entries where hook is post_edit or quality_gate
    and status is violation or advisory. Counts FP stamps per rule from the
    false-positives file.
    """
    trace_path = _get_trace_path()
    fp_path = _get_fp_path()

    # Count fires per rule from trace
    rule_fires: dict[str, int] = {}
    rule_last_fire: dict[str, str] = {}

    relevant_hooks = {"post_edit", "quality_gate"}
    relevant_statuses = {"violation", "advisory"}

    for entry in _read_jsonl(trace_path):
        hook = entry.get("hook", "")
        status = entry.get("status", "")
        if hook not in relevant_hooks or status not in relevant_statuses:
            continue
        findings = entry.get("findings", [])
        timestamp = entry.get("timestamp", "")
        for finding in findings:
            code = finding.get("code", "")
            if not code:
                continue
            rule_fires[code] = rule_fires.get(code, 0) + 1
            if timestamp:
                rule_last_fire[code] = timestamp

    # Count FP stamps per rule
    rule_fps: dict[str, int] = {}
    rule_last_fp: dict[str, str] = {}

    for entry in _read_jsonl(fp_path):
        rule = entry.get("rule", "")
        if not rule:
            continue
        rule_fps[rule] = rule_fps.get(rule, 0) + 1
        timestamp = entry.get("timestamp", "")
        if timestamp:
            rule_last_fp[rule] = timestamp

    # Merge into Evidence objects
    all_rules = set(rule_fires.keys()) | set(rule_fps.keys())
    result: dict[str, Evidence] = {}

    for rule in all_rules:
        fires = rule_fires.get(rule, 0)
        fps = rule_fps.get(rule, 0)
        tps = max(fires - fps, 0)
        result[rule] = Evidence(
            total_fires=fires,
            true_positives=tps,
            false_positives=fps,
            last_fire=rule_last_fire.get(rule),
            last_fp_stamp=rule_last_fp.get(rule),
        )

    return result


def promote_rule(
    project_root: Path,
    rule_id: str,
    min_fires: int = 5,
    max_fp_rate: float = 0.2,
) -> str:
    """Promote advisory -> enforce ONLY if evidence supports it.

    Returns status message (success or reason for refusal).
    """
    evidence = aggregate_evidence(project_root)
    rule_evidence = evidence.get(rule_id)

    if rule_evidence is None:
        return f"Refused: no evidence found for rule '{rule_id}'"

    if rule_evidence.total_fires < min_fires:
        return (
            f"Refused: rule '{rule_id}' has {rule_evidence.total_fires} fires "
            f"(minimum {min_fires} required)"
        )

    if rule_evidence.fp_rate > max_fp_rate:
        return (
            f"Refused: rule '{rule_id}' FP rate is {rule_evidence.fp_rate:.1%} "
            f"(maximum {max_fp_rate:.0%} allowed)"
        )

    # Load, update, save
    data = load_ratchet(project_root)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    if rule_id not in data["rules"]:
        data["rules"][rule_id] = {
            "mode": "advisory",
            "promoted_at": None,
            "demoted_at": None,
            "evidence": asdict(rule_evidence),
        }

    rule_data = data["rules"][rule_id]

    if rule_data.get("mode") == "enforce":
        return f"Rule '{rule_id}' is already in enforce mode"

    rule_data["mode"] = "enforce"
    rule_data["promoted_at"] = now
    rule_data["evidence"] = asdict(rule_evidence)

    save_ratchet(project_root, data)
    return (
        f"Promoted '{rule_id}' to enforce "
        f"(fires={rule_evidence.total_fires}, "
        f"FP rate={rule_evidence.fp_rate:.1%})"
    )


def demote_rule(project_root: Path, rule_id: str, reason: str) -> str:
    """Demote enforce -> advisory, requires a reason.

    Returns status message.
    """
    if not reason.strip():
        return "Refused: a reason is required for demotion"

    data = load_ratchet(project_root)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    if rule_id not in data["rules"]:
        data["rules"][rule_id] = {
            "mode": "advisory",
            "promoted_at": None,
            "demoted_at": None,
            "evidence": asdict(Evidence()),
        }

    rule_data = data["rules"][rule_id]

    if rule_data.get("mode") == "advisory":
        return f"Rule '{rule_id}' is already in advisory mode"

    rule_data["mode"] = "advisory"
    rule_data["demoted_at"] = now
    rule_data["demotion_reason"] = reason

    # Refresh evidence snapshot
    evidence = aggregate_evidence(project_root)
    if rule_id in evidence:
        rule_data["evidence"] = asdict(evidence[rule_id])

    save_ratchet(project_root, data)
    return f"Demoted '{rule_id}' to advisory (reason: {reason})"


def ratchet_status(project_root: Path) -> list[dict]:
    """Returns per-rule status: mode, fire count, FP rate, promotion/demotion eligibility."""
    data = load_ratchet(project_root)
    evidence = aggregate_evidence(project_root)

    # Merge known rules from both sources
    all_rules = set(data.get("rules", {}).keys()) | set(evidence.keys())
    rows: list[dict] = []

    for rule_id in sorted(all_rules):
        rule_data = data.get("rules", {}).get(rule_id, {})
        rule_ev = evidence.get(rule_id, Evidence())

        mode = rule_data.get("mode", "advisory")
        fires = rule_ev.total_fires
        fp_rate = rule_ev.fp_rate

        # Eligible for promotion: advisory, enough fires, low FP rate
        eligible_promote = (
            mode == "advisory"
            and fires >= 5
            and fp_rate <= 0.2
        )

        # Eligible for demotion: currently enforced
        eligible_demote = mode == "enforce"

        rows.append({
            "rule": rule_id,
            "mode": mode,
            "total_fires": fires,
            "true_positives": rule_ev.true_positives,
            "false_positives": rule_ev.false_positives,
            "fp_rate": fp_rate,
            "eligible_promote": eligible_promote,
            "eligible_demote": eligible_demote,
            "promoted_at": rule_data.get("promoted_at"),
            "demoted_at": rule_data.get("demoted_at"),
        })

    return rows


def _print_status_table(rows: list[dict]) -> None:
    """Print a human-readable status table."""
    if not rows:
        print("No rules tracked yet. Run checks to accumulate evidence.")
        return

    print(f"{'Rule':<25} {'Mode':<10} {'Fires':<7} {'TP':<5} {'FP':<5} {'FP%':<7} {'Promote?':<10} {'Demote?':<10}")
    print("-" * 85)
    for row in rows:
        fp_pct = f"{row['fp_rate']:.0%}" if row["total_fires"] > 0 else "n/a"
        promote = "yes" if row["eligible_promote"] else ""
        demote = "yes" if row["eligible_demote"] else ""
        print(
            f"{row['rule']:<25} {row['mode']:<10} {row['total_fires']:<7} "
            f"{row['true_positives']:<5} {row['false_positives']:<5} "
            f"{fp_pct:<7} {promote:<10} {demote:<10}"
        )


def cmd_ratchet(args: argparse.Namespace) -> None:
    """CLI handler for `fettle ratchet` subcommand."""
    from paths import find_repo_root

    project_root = find_repo_root()
    if not project_root:
        print("Error: not inside a repository.", file=sys.stderr)
        sys.exit(1)

    action = getattr(args, "ratchet_action", None)

    if action == "status":
        rows = ratchet_status(project_root)
        _print_status_table(rows)

    elif action == "promote":
        rule_id = args.rule_id
        result = promote_rule(project_root, rule_id)
        print(result)
        if result.startswith("Refused"):
            sys.exit(1)

    elif action == "demote":
        rule_id = args.rule_id
        reason = getattr(args, "reason", None) or ""
        if not reason.strip():
            print("Error: --reason is required for demotion.", file=sys.stderr)
            sys.exit(1)
        result = demote_rule(project_root, rule_id, reason)
        print(result)

    elif action == "sync":
        evidence = aggregate_evidence(project_root)
        data = load_ratchet(project_root)
        for rule_id, ev in evidence.items():
            if rule_id not in data["rules"]:
                data["rules"][rule_id] = {
                    "mode": "advisory",
                    "promoted_at": None,
                    "demoted_at": None,
                    "evidence": asdict(ev),
                }
            else:
                data["rules"][rule_id]["evidence"] = asdict(ev)
        save_ratchet(project_root, data)
        print(f"Synced evidence for {len(evidence)} rule(s).")

    else:
        print("Usage: fettle ratchet {status|promote|demote|sync}")
        sys.exit(1)
