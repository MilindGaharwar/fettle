"""``fettle spawn`` — the blessed path for launching child agents (WP-157, A4).

Design doc: docs/engagement/12-stage-a-policy-continuity.md §3.1.

Writes a policy capsule from the current effective config (which is itself
capsule-derived when this session is already a child — chains compose),
exports FETTLE_POLICY_CAPSULE + FETTLE_PARENT_SESSION to the child, and
launches it via the Stage 13 runner registry. ``--worktree ITEM`` provisions
a claimed per-item worktree as the child's cwd.

Fail-visible contract mirrors the runners': expected failures land in
SpawnResult.error, never as exceptions.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from fettle.runners import AgentRunner, RunnerResult


@dataclass
class SpawnResult:
    """Outcome of one governed child-agent launch."""

    runner: str = ""
    capsule_path: str = ""
    capsule_digest: str = ""
    child_cwd: str = ""
    worktree_item: str = ""
    session_id: str = ""          # the spawning (parent) session id
    lineage: list[str] = field(default_factory=list)
    run: RunnerResult | None = None
    error: str = ""               # non-empty → the spawn failed before/at launch


def _parent_session_id() -> str:
    """Best-effort identity for the spawning session (trace lineage root)."""
    for var in ("FETTLE_SESSION_ID", "CLAUDE_SESSION_ID"):
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return f"spawn-{int(time.time())}-{os.getpid()}"


def spawn_agent(
    runner_name: str,
    task: str,
    cwd: str,
    worktree_item: str = "",
    timeout_s: int = 600,
    runner: AgentRunner | None = None,
) -> SpawnResult:
    """Launch ``runner_name`` on ``task`` under the current effective policy.

    ``runner`` is injectable for tests; production resolves the registry.
    """
    from fettle import __version__
    from fettle.config import load_config
    from fettle.paths import find_repo_root
    from fettle.policy_capsule import resolve_env_capsule, write_capsule
    from fettle.trace import log_decision

    result = SpawnResult(runner=runner_name, worktree_item=worktree_item)

    repo_root = find_repo_root(cwd)
    if not repo_root:
        result.error = "not inside a repository (no .git or .fettle.toml found)"
        return result

    # Effective policy — already capsule-merged when we are ourselves a child.
    config = load_config(str(repo_root))
    parent_doc, err = resolve_env_capsule()
    if err:
        result.error = f"refusing to spawn under an unverifiable capsule: {err}"
        return result
    lineage: list[str] = []
    if parent_doc:
        lineage = list(parent_doc.get("lineage", [])) + [parent_doc["digest"][:16]]

    session_id = _parent_session_id()
    result.session_id = session_id
    result.lineage = lineage

    try:
        capsule_path = write_capsule(
            config,
            origin={
                "repo_root": str(repo_root),
                "repo": Path(repo_root).name,
                "session_id": session_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "fettle_version": __version__,
            },
            lineage=lineage,
        )
    except (ValueError, OSError) as exc:
        result.error = f"could not write policy capsule: {exc}"
        return result
    result.capsule_path = str(capsule_path)
    result.capsule_digest = capsule_path.stem

    child_cwd = Path(cwd)
    if worktree_item:
        from fettle.work_items import claim_item
        from fettle.worktrees import create_worktree, worktrees_root

        wt_path = worktrees_root(str(repo_root), config) / worktree_item
        if not wt_path.is_dir():
            wt_path_created, wt_err = create_worktree(str(repo_root), worktree_item, config)
            if wt_err:
                result.error = f"worktree provisioning failed: {wt_err}"
                return result
            wt_path = wt_path_created
        claim_err = claim_item(str(repo_root), worktree_item, session_id, str(wt_path))
        if claim_err:
            result.error = f"work-item claim failed: {claim_err}"
            return result
        child_cwd = wt_path
    result.child_cwd = str(child_cwd)

    if runner is None:
        from fettle.runners import get_runner
        try:
            runner = get_runner(runner_name)
        except ValueError as exc:
            result.error = str(exc)
            return result
    if not runner.available():
        result.error = f"{runner_name} CLI not available — cannot launch child agent"
        return result

    # Children inherit the parent process env: set, launch, restore.
    saved = {k: os.environ.get(k) for k in ("FETTLE_POLICY_CAPSULE", "FETTLE_PARENT_SESSION")}
    os.environ["FETTLE_POLICY_CAPSULE"] = str(capsule_path)
    os.environ["FETTLE_PARENT_SESSION"] = session_id
    try:
        result.run = runner.run(task, cwd=child_cwd, timeout_s=timeout_s)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    status = "pass" if not result.run.error else "tool_error"
    log_decision(
        "spawn", status, tool=runner_name, file=str(child_cwd),
        findings=[{
            "code": "SPAWN",
            "capsule": result.capsule_digest,
            "lineage": lineage,
            "worktree_item": worktree_item,
            "runner_error": result.run.error,
        }],
        session_id=session_id,
    )
    return result
