"""Policy capsule — delegation-safe policy continuity (WP-156, Stage A).

Design doc: docs/engagement/12-stage-a-policy-continuity.md.

A capsule is a content-addressed snapshot of a parent session's effective
merged policy, handed to child agents via $FETTLE_POLICY_CAPSULE. Children
resolve and verify it, then merge it OVER their locally-discovered config
with monotonic semantics: a child may deviate only in the *stricter*
direction (D-A2: list additions weaken → capsule wins; D-A5: machine-local
plumbing keys stay local).

Verification is fail-closed on tampering (digest mismatch, filename
mismatch, unparseable file the env asserts exists) and fail-open on version
skew (D-A1: a newer fettle_capsule version is ignored with a warning, not
treated as an attack — mixed-version fleets are normal).

Stdlib only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

CAPSULE_VERSION = 1
MAX_LINEAGE_DEPTH = 16
ENV_VAR = "FETTLE_POLICY_CAPSULE"

# Machine-local plumbing: the ONLY paths where the local value beats the
# capsule by design — a child in another checkout must not inherit its
# parent's absolute paths or endpoints (D-A5). Prefix match on dotted paths.
PLUMBING_KEYS: frozenset[str] = frozenset({
    "paths", "review", "uat", "worktrees.root",
})

# Mode ladder for gates.*.mode — higher rank = stricter. Unknown modes rank
# as advisory (1): mis-ranking an unknown value must not silently disable.
_MODE_RANK: dict[str, int] = {
    "off": 0, "silent": 0, "none": 0, "report": 0,
    "advisory": 1,
    "soft": 2, "enforce": 2, "strict": 2,
}

# Directed numeric thresholds: which end is stricter (D-A2 table).
STRICTER_DIRECTION: dict[str, str] = {
    "gates.complexity.max_cyclomatic": "min",
    "gates.complexity.max_cognitive": "min",
    "gates.coverage.threshold": "max",
    "gates.coverage.minimum_branch_percent": "max",
    "gates.loop_detect.threshold": "min",
    "gates.scope_creep.warning_threshold": "min",
    "gates.scope_creep.critical_threshold": "min",
    "gates.plan.threshold": "min",
}

_MAX_FINDINGS = 20

_last_error: str = ""
_last_ignored: list[dict] = []


def _capsules_dir() -> Path:
    base = os.environ.get("FETTLE_STATE_DIR")
    if not base:
        xdg = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        base = os.path.join(xdg, "fettle")
    path = Path(base) / "capsules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def canonical_digest(policy: dict) -> str:
    """sha256 over canonical JSON of the policy body — and ONLY the body.

    Origin/lineage are provenance, not policy; they may differ between
    re-serializations without changing what is enforced (design §2.1).
    """
    body = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def write_capsule(
    policy: dict,
    origin: dict,
    lineage: list[str] | tuple[str, ...] = (),
) -> Path:
    """Atomically write a capsule; returns its path.

    Raises ValueError when the lineage chain is already at the depth cap
    (D-A6) — a runaway spawn recursion must fail at the spawner, loudly.
    """
    chain = list(lineage)
    if len(chain) >= MAX_LINEAGE_DEPTH:
        raise ValueError(
            f"capsule lineage depth {len(chain)} >= cap {MAX_LINEAGE_DEPTH} — "
            "refusing to spawn deeper (runaway delegation?)"
        )
    digest = canonical_digest(policy)
    doc = {
        "fettle_capsule": CAPSULE_VERSION,
        "digest": digest,
        "policy": policy,
        "origin": dict(origin),
        "lineage": chain,
    }
    path = _capsules_dir() / f"{digest[:16]}.json"
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    tmp.write_text(json.dumps(doc), encoding="utf-8")
    os.replace(tmp, path)
    return path


def verify(doc: Any, path: Path | None = None) -> str:
    """'' when the capsule is intact; a human-readable reason otherwise."""
    if not isinstance(doc, dict):
        return "capsule is not a JSON object"
    policy = doc.get("policy")
    if not isinstance(policy, dict):
        return "capsule has no policy body"
    digest = doc.get("digest", "")
    actual = canonical_digest(policy)
    if actual != digest:
        return "digest mismatch — policy body was modified after the capsule was written"
    if path is not None and path.stem != digest[:16] and not path.name.endswith(".tmp"):
        return f"filename does not match capsule digest ({path.name} vs {digest[:16]}.json)"
    lineage = doc.get("lineage", [])
    if not isinstance(lineage, list) or len(lineage) > MAX_LINEAGE_DEPTH:
        return "capsule lineage is malformed or exceeds the depth cap"
    return ""


def resolve_env_capsule() -> tuple[dict | None, str]:
    """Resolve and verify $FETTLE_POLICY_CAPSULE.

    Returns (capsule_doc, error):
      (None, "")      — env not set: normal solo mode
      (doc,  "")      — verified capsule
      (None, reason)  — the env ASSERTS a capsule that is missing, tampered,
                        or of an unsupported schema version: fail closed
                        (capsule_guard blocks on this)
    """
    global _last_error
    _last_error = ""
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw:
        return None, ""
    path = Path(raw)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        _last_error = f"policy capsule unreadable at {path}: {exc}"
        return None, _last_error
    version = doc.get("fettle_capsule") if isinstance(doc, dict) else None
    if isinstance(version, int) and version > CAPSULE_VERSION:
        # D-A1 (revised 2026-08-03, audit H-02): when the env ASSERTS a
        # capsule, an unsupported schema version must fail CLOSED. The
        # capsule file is child-writable — treating newer versions as benign
        # skew let a child bump the version field (which is outside the
        # policy digest) and silently escape inherited policy.
        _last_error = (
            f"policy capsule at {path} declares schema version {version} "
            f"(this fettle reads {CAPSULE_VERSION}). Refusing to run with "
            "unverifiable delegated policy — update fettle in the child "
            "environment or re-spawn with a compatible parent."
        )
        return None, _last_error
    reason = verify(doc, path)
    if reason:
        _last_error = f"policy capsule at {path}: {reason}"
        return None, _last_error
    return doc, ""


def last_error() -> str:
    """Sticky verification error from the most recent resolution."""
    return _last_error


def last_ignored() -> list[dict]:
    """Suppressed weaker-local overrides from the most recent merge."""
    return _last_ignored


def apply_env_capsule(cfg: dict) -> dict:
    """Merge a verified env capsule OVER `cfg`, monotonically stricter.

    No env / version skew → cfg unchanged. Verification error → cfg
    unchanged too — the error is sticky (last_error) and capsule_guard
    blocks on it; load_config itself must never raise or block.
    """
    global _last_ignored
    _last_ignored = []
    doc, err = resolve_env_capsule()
    if not doc or err:
        return cfg
    merged, ignored = merge_for_child(doc["policy"], cfg)
    _last_ignored = ignored
    return merged


def _rank(mode: Any) -> int:
    return _MODE_RANK.get(str(mode).lower(), 1)


def _is_plumbing(path: str) -> bool:
    return any(path == p or path.startswith(p + ".") for p in PLUMBING_KEYS)


def merge_for_child(
    capsule_policy: dict, local: dict
) -> tuple[dict, list[dict]]:
    """Child effective policy = capsule policy, monotonically stricter.

    Walks the union of both trees. Per key class (design §2.3):
    gate modes → ladder max; gates.*.enabled → True wins; directed
    numerics → stricter end; plumbing → local; everything else → capsule.
    Keys only the local config knows (newer fettle in the child) keep
    their local value — the capsule is silent on them.

    Returns (effective, ignored_overrides) where each ignored override is
    {"key", "capsule", "local"} — silent policy correction is its own
    failure mode, so every suppressed deviation is surfaced.
    """
    findings: list[dict] = []

    def note(path: str, cap_v: Any, loc_v: Any) -> None:
        if len(findings) < _MAX_FINDINGS:
            findings.append({"key": path, "capsule": cap_v, "local": loc_v})

    def walk(cap: dict, loc: dict, prefix: str) -> dict:
        out: dict = {}
        for key in set(cap) | set(loc):
            path = f"{prefix}.{key}" if prefix else key
            in_cap, in_loc = key in cap, key in loc
            cap_v = cap.get(key)
            loc_v = loc.get(key)
            if not in_cap:
                out[key] = copy.deepcopy(loc_v)  # capsule silent → local
                continue
            if not in_loc:
                out[key] = copy.deepcopy(cap_v)
                continue
            if _is_plumbing(path):
                out[key] = copy.deepcopy(loc_v)  # D-A5
                continue
            if isinstance(cap_v, dict) and isinstance(loc_v, dict):
                out[key] = walk(cap_v, loc_v, path)
                continue
            if cap_v == loc_v:
                out[key] = copy.deepcopy(cap_v)
                continue
            # Leaf conflict — apply the monotonic rule for its class.
            if key == "mode" and prefix.startswith("gates."):
                if _rank(loc_v) > _rank(cap_v):
                    out[key] = loc_v  # stricter child wins
                else:
                    out[key] = cap_v
                    note(path, cap_v, loc_v)
                continue
            if key == "enabled" and prefix.startswith("gates."):
                out[key] = bool(cap_v) or bool(loc_v)  # more enforcement wins
                if out[key] != loc_v:
                    note(path, cap_v, loc_v)
                continue
            direction = STRICTER_DIRECTION.get(path)
            if direction and isinstance(cap_v, (int, float)) \
                    and isinstance(loc_v, (int, float)):
                stricter = min(cap_v, loc_v) if direction == "min" else max(cap_v, loc_v)
                out[key] = stricter
                if stricter != loc_v:
                    note(path, cap_v, loc_v)
                continue
            # Default: capsule wins (covers loosening lists per D-A2).
            out[key] = copy.deepcopy(cap_v)
            note(path, cap_v, loc_v)
        return out

    return walk(capsule_policy, local, ""), findings
