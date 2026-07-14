# Fettle Single Dispatcher Spec (v2 Foundation)

## Executive Summary

Replace the current “N Python processes per hook event” architecture with one Python dispatcher process per hook event.

Current `PostToolUse(Write)` runs:

```text
run.sh quality_gate.py
run.sh post_edit.py
run.sh post_edit_ts.py
run.sh lean_sniffers.py
run.sh loop_detect.py
run.sh scope_creep.py
```

New behavior:

```text
run.sh dispatcher.py
```

The dispatcher:

1. Reads stdin once.
2. Loads config once.
3. Detects workspace once.
4. Selects applicable checks.
5. Runs them in deterministic order.
6. Aggregates advisory/blocking output.
7. Fails open on all dispatcher/check errors.
8. Emits timing metrics.

`SubagentStart → subagent_inject.js` remains separate and unchanged.

---

# 1. File Layout

Fettle remains rooted at:

```text
~/.claude/plugins/fettle/
```

Add a dispatcher package under `hooks/`:

```text
~/.claude/plugins/fettle/
├── hooks.json
├── hooks/
│   ├── run.sh
│   ├── dispatcher.py
│   │
│   ├── quality_gate.py              # existing CLI wrapper retained
│   ├── config_protect.py            # existing CLI wrapper retained
│   ├── mcp_trust_gate.py            # existing CLI wrapper retained
│   ├── destructive_guard.py         # existing CLI wrapper retained
│   ├── commit_message.py            # existing CLI wrapper retained
│   ├── post_edit.py                 # existing CLI wrapper retained
│   ├── post_edit_ts.py              # existing CLI wrapper retained
│   ├── lean_sniffers.py             # existing CLI wrapper retained
│   ├── post_bash_doc_check.py       # existing CLI wrapper retained
│   ├── loop_detect.py               # existing CLI wrapper retained
│   ├── scope_creep.py               # existing CLI wrapper retained
│   ├── stop_quality_gate.py         # existing CLI wrapper retained
│   ├── subagent_inject.js           # unchanged
│   │
│   └── fettle_dispatcher/
│       ├── __init__.py
│       ├── types.py
│       ├── config.py
│       ├── workspace.py
│       ├── registry.py
│       ├── aggregate.py
│       ├── timing.py
│       ├── legacy.py
│       └── checks/
│           ├── __init__.py
│           ├── quality_gate_check.py
│           ├── config_protect_check.py
│           ├── mcp_trust_gate_check.py
│           ├── destructive_guard_check.py
│           ├── commit_message_check.py
│           ├── post_edit_check.py
│           ├── post_edit_ts_check.py
│           ├── lean_sniffers_check.py
│           ├── post_bash_doc_check.py
│           ├── loop_detect_check.py
│           ├── scope_creep_check.py
│           └── stop_quality_gate_check.py
│
├── tests/
│   ├── dispatcher/
│   │   ├── test_dispatcher_selection.py
│   │   ├── test_dispatcher_aggregation.py
│   │   ├── test_dispatcher_budget.py
│   │   ├── test_dispatcher_fail_open.py
│   │   ├── test_dispatcher_timing.py
│   │   └── test_legacy_wrapper_parity.py
│   └── ... existing tests ...
│
└── .state/
    └── metrics.ndjson              # created lazily
```

## Why this layout?

- `dispatcher.py` is the hook entrypoint.
- `fettle_dispatcher/` contains shared dispatcher infrastructure.
- Existing script names remain in place so the current test suite continues to run.
- Existing scripts become thin wrappers over the new check modules.
- Checks are imported in-process by the dispatcher, not launched as subprocesses.

---

# 2. Check Registration

Checks register statically in `fettle_dispatcher/registry.py`.

Do **not** use dynamic package discovery. Static registration is faster, more explicit, easier to test, and avoids import surprises during hooks.

## `fettle_dispatcher/types.py`

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class Decision(str, Enum):
    ALLOW = "allow"
    ADVISORY = "advisory"
    BLOCK = "block"


@dataclass(frozen=True)
class HookInput:
    hook_event_name: str
    tool_name: str | None
    tool_input: dict[str, Any]
    cwd: Path
    session_id: str | None
    raw: dict[str, Any]


@dataclass
class Workspace:
    root: Path
    kind: str | None = None
    markers: tuple[str, ...] = ()


@dataclass
class DispatcherConfig:
    raw: dict[str, Any]

    def get_path(self, path: Sequence[str], default: Any = None) -> Any:
        cur: Any = self.raw
        for part in path:
            if not isinstance(cur, Mapping) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def check_enabled(self, check_name: str, default: bool = True) -> bool:
        if check_name in set(self.get_path(("dispatcher", "disabled_checks"), [])):
            return False

        explicit = self.get_path(("checks", check_name, "enabled"), None)
        if explicit is not None:
            return bool(explicit)

        return default


@dataclass
class HookContext:
    input: HookInput
    config: DispatcherConfig
    workspace: Workspace
    plugin_root: Path
    hook_start_monotonic: float
    global_deadline_monotonic: float

    @property
    def event(self) -> str:
        return self.input.hook_event_name

    @property
    def tool_name(self) -> str | None:
        return self.input.tool_name

    @property
    def tool_input(self) -> dict[str, Any]:
        return self.input.tool_input

    @property
    def cwd(self) -> Path:
        return self.input.cwd

    @property
    def target_path(self) -> Path | None:
        """
        Best-effort path extraction for file-oriented tools.
        Supports current Write/Edit/Read shape and future MultiEdit-like shapes.
        """
        for key in ("file_path", "path", "notebook_path"):
            value = self.tool_input.get(key)
            if isinstance(value, str) and value:
                p = Path(value)
                return p if p.is_absolute() else self.cwd / p
        return None

    @property
    def target_ext(self) -> str | None:
        p = self.target_path
        if not p:
            return None
        return p.suffix.lower()


@dataclass
class CheckResult:
    decision: Decision = Decision.ALLOW

    # Human-readable advisory/block message.
    message: str | None = None

    # Exact hookSpecificOutput fields this check wants to contribute.
    hook_specific_output: dict[str, Any] = field(default_factory=dict)

    # Debug metadata, never required by Claude.
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls) -> "CheckResult":
        return cls(decision=Decision.ALLOW)

    @classmethod
    def advisory(
        cls,
        message: str | None = None,
        *,
        hook_specific_output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "CheckResult":
        return cls(
            decision=Decision.ADVISORY,
            message=message,
            hook_specific_output=hook_specific_output or {},
            metadata=metadata or {},
        )

    @classmethod
    def block(
        cls,
        message: str,
        *,
        hook_specific_output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "CheckResult":
        return cls(
            decision=Decision.BLOCK,
            message=message,
            hook_specific_output=hook_specific_output or {},
            metadata=metadata or {},
        )


CheckRunner = Callable[[HookContext], CheckResult]


@dataclass(frozen=True)
class CheckSpec:
    name: str
    run: CheckRunner

    # Matching.
    events: frozenset[str]
    tools: frozenset[str] | None = None
    extensions: frozenset[str] | None = None

    # Lower runs earlier.
    order: int = 100

    # Defaults can be overridden in config.
    enabled_by_default: bool = True
    budget_ms: int | None = None

    def matches(self, ctx: HookContext) -> bool:
        if ctx.event not in self.events:
            return False

        if self.tools is not None and ctx.tool_name not in self.tools:
            return False

        if self.extensions is not None:
            ext = ctx.target_ext
            if ext not in self.extensions:
                return False

        return True

    def is_enabled(self, config: DispatcherConfig) -> bool:
        return config.check_enabled(self.name, self.enabled_by_default)
```

---

# 3. Check Module Interface

Each check module exports:

```python
SPEC: CheckSpec
```

The `SPEC.run` callable is the in-process implementation.

Example:

## `fettle_dispatcher/checks/config_protect_check.py`

```python
from __future__ import annotations

from fettle_dispatcher.types import CheckResult, CheckSpec, HookContext


PROTECTED_NAMES = {
    "hooks.json",
    "settings.json",
}


def run(ctx: HookContext) -> CheckResult:
    target = ctx.target_path
    if target is None:
        return CheckResult.allow()

    if target.name not in PROTECTED_NAMES:
        return CheckResult.allow()

    # Existing config-protect logic should be moved here.
    # This is illustrative.
    return CheckResult.block(
        f"Protected configuration file edit blocked: {target}",
        hook_specific_output={
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Fettle blocked modification of protected file: {target}",
        },
    )


SPEC = CheckSpec(
    name="config_protect",
    run=run,
    events=frozenset({"PreToolUse"}),
    tools=frozenset({"Write", "Edit"}),
    order=10,
    budget_ms=50,
)
```

## `fettle_dispatcher/checks/post_edit_ts_check.py`

```python
from __future__ import annotations

from fettle_dispatcher.types import CheckResult, CheckSpec, HookContext


def run(ctx: HookContext) -> CheckResult:
    # Existing post_edit_ts logic moves here.
    #
    # Must not read stdin.
    # Must not call sys.exit.
    # Must not print hook JSON directly.
    #
    # Return CheckResult instead.
    return CheckResult.allow()


SPEC = CheckSpec(
    name="post_edit_ts",
    run=run,
    events=frozenset({"PostToolUse"}),
    tools=frozenset({"Write", "Edit"}),
    extensions=frozenset({".ts", ".tsx", ".js", ".jsx"}),
    order=30,
    budget_ms=80,
)
```

---

# 4. Registry

## `fettle_dispatcher/registry.py`

```python
from __future__ import annotations

from fettle_dispatcher.types import CheckSpec

from fettle_dispatcher.checks import (
    quality_gate_check,
    config_protect_check,
    mcp_trust_gate_check,
    destructive_guard_check,
    commit_message_check,
    post_edit_check,
    post_edit_ts_check,
    lean_sniffers_check,
    post_bash_doc_check,
    loop_detect_check,
    scope_creep_check,
    stop_quality_gate_check,
)


CHECKS: tuple[CheckSpec, ...] = (
    # PreToolUse Write/Edit
    config_protect_check.SPEC,
    quality_gate_check.SPEC,

    # PreToolUse Bash
    mcp_trust_gate_check.SPEC,
    destructive_guard_check.SPEC,
    commit_message_check.SPEC,

    # PostToolUse Write/Edit/Bash/Read
    post_edit_check.SPEC,
    post_edit_ts_check.SPEC,
    lean_sniffers_check.SPEC,
    post_bash_doc_check.SPEC,
    loop_detect_check.SPEC,
    scope_creep_check.SPEC,

    # Stop
    stop_quality_gate_check.SPEC,
)


def select_checks(ctx) -> list[CheckSpec]:
    selected = [
        spec
        for spec in CHECKS
        if spec.matches(ctx) and spec.is_enabled(ctx.config)
    ]
    return sorted(selected, key=lambda s: (s.order, s.name))
```

---

# 5. Default Check Mapping

The dispatcher must reproduce current wiring semantics.

| Current hook | Dispatcher check specs |
|---|---|
| `PreToolUse(Write/Edit)` | `config_protect`, `quality_gate` |
| `PreToolUse(Bash)` | `mcp_trust_gate`, `destructive_guard`, `commit_message` |
| `PostToolUse(Write/Edit)` | `quality_gate`, `post_edit`, `post_edit_ts`, `lean_sniffers`, `loop_detect`, `scope_creep` |
| `PostToolUse(Bash)` | `quality_gate`, `post_bash_doc_check`, `loop_detect`, `scope_creep` |
| `PostToolUse(Read)` | `loop_detect` |
| `Stop` | `quality_gate`, `stop_quality_gate` |
| `SubagentStart` | unchanged JS hook |

Because `quality_gate.py` currently handles multiple events itself, its check spec should include all matching events/tools:

## `fettle_dispatcher/checks/quality_gate_check.py`

```python
from __future__ import annotations

from fettle_dispatcher.types import CheckResult, CheckSpec, HookContext


def run(ctx: HookContext) -> CheckResult:
    """
    Existing quality_gate logic moves here.

    It should branch internally on:
      - ctx.event
      - ctx.tool_name
      - ctx.target_path
      - ctx.config
      - ctx.workspace

    This preserves quality_gate's current multi-event behavior while avoiding
    repeated stdin/config/workspace work.
    """
    return CheckResult.allow()


SPEC = CheckSpec(
    name="quality_gate",
    run=run,
    events=frozenset({"PreToolUse", "PostToolUse", "Stop"}),
    tools=None,
    order=20,
    budget_ms=120,
)
```

Important: `quality_gate_check.run()` should internally no-op for irrelevant combinations exactly as `quality_gate.py` does today.

---

# 6. New `hooks.json`

`SubagentStart` remains JS.

All Python hook event entries point to `dispatcher.py`.

Recommended `hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/fettle/hooks/run.sh dispatcher.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|Bash|Read",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/fettle/hooks/run.sh dispatcher.py"
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "node ~/.claude/plugins/fettle/hooks/subagent_inject.js"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/plugins/fettle/hooks/run.sh dispatcher.py"
          }
        ]
      }
    ]
  }
}
```

This gives one Python command per hook event firing.

---

# 7. Config Changes

Existing config must continue to work.

Add optional config sections. Absence means current defaults.

Config location should use existing Fettle config loading rules. The dispatcher should not invent a separate config file if one already exists.

Recommended shape:

```json
{
  "dispatcher": {
    "enabled": true,

    "fail_open": true,

    "global_budget_ms": 400,

    "event_budgets_ms": {
      "PreToolUse": 250,
      "PostToolUse": 400,
      "Stop": 600
    },

    "disabled_checks": [],

    "check_budgets_ms": {
      "quality_gate": 120,
      "config_protect": 50,
      "mcp_trust_gate": 60,
      "destructive_guard": 60,
      "commit_message": 50,
      "post_edit": 80,
      "post_edit_ts": 80,
      "lean_sniffers": 80,
      "post_bash_doc_check": 80,
      "loop_detect": 50,
      "scope_creep": 80,
      "stop_quality_gate": 150
    },

    "timing": {
      "enabled": true,
      "metrics_path": "~/.claude/plugins/fettle/.state/metrics.ndjson",
      "include_in_hook_output": false
    },

    "debug": false
  },

  "checks": {
    "quality_gate": {
      "enabled": true
    },
    "config_protect": {
      "enabled": true
    },
    "mcp_trust_gate": {
      "enabled": true
    },
    "destructive_guard": {
      "enabled": true
    },
    "commit_message": {
      "enabled": true
    },
    "post_edit": {
      "enabled": true
    },
    "post_edit_ts": {
      "enabled": true
    },
    "lean_sniffers": {
      "enabled": true
    },
    "post_bash_doc_check": {
      "enabled": true
    },
    "loop_detect": {
      "enabled": true
    },
    "scope_creep": {
      "enabled": true
    },
    "stop_quality_gate": {
      "enabled": true
    }
  }
}
```

## Defaults

Hardcoded defaults in dispatcher:

```python
DEFAULT_EVENT_BUDGETS_MS = {
    "PreToolUse": 250,
    "PostToolUse": 400,
    "Stop": 600,
}

DEFAULT_GLOBAL_BUDGET_MS = 400
DEFAULT_FAIL_OPEN = True
DEFAULT_TIMING_ENABLED = True
DEFAULT_TIMING_IN_OUTPUT = False
```

## Rollback switch

Support env var:

```text
FETTLE_DISABLE_DISPATCHER=1
```

If set, `dispatcher.py` should immediately fail open with exit `0`.

This is a safety valve during migration.

---

# 8. Config Loading

## `fettle_dispatcher/config.py`

The dispatcher must call the existing Fettle config loader exactly once.

If current config loading lives in one of the existing scripts, move it into a shared function here and update the script wrapper to call it.

Implementation contract:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fettle_dispatcher.types import DispatcherConfig


def load_config(plugin_root: Path, cwd: Path) -> DispatcherConfig:
    """
    Load Fettle config once.

    Must:
      - preserve existing config precedence
      - fail open by returning defaults on errors
      - avoid printing
      - avoid sys.exit
    """
    raw: dict[str, Any] = {}

    # Replace this with existing Fettle config precedence.
    candidates = [
        cwd / ".fettle.json",
        plugin_root / "config.json",
    ]

    for path in candidates:
        try:
            if path.exists():
                with path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    raw.update(loaded)
        except Exception:
            # Fail open: broken config disables nothing.
            continue

    return DispatcherConfig(raw=raw)


def event_budget_ms(config: DispatcherConfig, event: str) -> int:
    by_event = config.get_path(("dispatcher", "event_budgets_ms", event), None)
    if isinstance(by_event, int) and by_event > 0:
        return by_event

    global_budget = config.get_path(("dispatcher", "global_budget_ms"), None)
    if isinstance(global_budget, int) and global_budget > 0:
        return global_budget

    if event == "PreToolUse":
        return 250
    if event == "PostToolUse":
        return 400
    if event == "Stop":
        return 600

    return 400


def check_budget_ms(config: DispatcherConfig, check_name: str, default: int | None) -> int | None:
    configured = config.get_path(("dispatcher", "check_budgets_ms", check_name), None)
    if isinstance(configured, int) and configured > 0:
        return configured
    return default


def timing_enabled(config: DispatcherConfig) -> bool:
    value = config.get_path(("dispatcher", "timing", "enabled"), True)
    return bool(value)


def timing_include_in_output(config: DispatcherConfig) -> bool:
    value = config.get_path(("dispatcher", "timing", "include_in_hook_output"), False)
    return bool(value)


def metrics_path(config: DispatcherConfig, plugin_root: Path) -> Path:
    configured = config.get_path(("dispatcher", "timing", "metrics_path"), None)
    if isinstance(configured, str) and configured:
        return Path(os.path.expanduser(configured))
    return plugin_root / ".state" / "metrics.ndjson"
```

---

# 9. Workspace Detection

## `fettle_dispatcher/workspace.py`

Move current workspace detection into a shared function.

```python
from __future__ import annotations

from pathlib import Path

from fettle_dispatcher.types import Workspace


def detect_workspace(cwd: Path) -> Workspace:
    """
    Detect workspace once.

    Must:
      - preserve existing Fettle workspace-root rules
      - fail open by returning cwd on errors
      - not print
      - not sys.exit
    """
    try:
        cur = cwd.resolve()
        for parent in (cur, *cur.parents):
            markers = []
            for name in (".git", "package.json", "pyproject.toml", "lakefile.lean"):
                if (parent / name).exists():
                    markers.append(name)

            if markers:
                return Workspace(
                    root=parent,
                    kind="project",
                    markers=tuple(markers),
                )

        return Workspace(root=cur, kind=None, markers=())
    except Exception:
        return Workspace(root=cwd, kind=None, markers=())
```

---

# 10. Dispatcher Loop

## `hooks/dispatcher.py`

This is the only Python hook command target.

```python
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

# Allow `bash run.sh dispatcher.py` from hooks directory.
HOOKS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOKS_DIR.parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from fettle_dispatcher.aggregate import Aggregator
from fettle_dispatcher.config import event_budget_ms, load_config
from fettle_dispatcher.registry import select_checks
from fettle_dispatcher.timing import write_metrics
from fettle_dispatcher.types import DispatcherConfig, HookContext, HookInput, Workspace
from fettle_dispatcher.workspace import detect_workspace


def _allow_output(additional_context: str | None = None) -> dict[str, Any]:
    hso: dict[str, Any] = {}
    if additional_context:
        hso["additionalContext"] = additional_context
    return {"hookSpecificOutput": hso}


def _parse_stdin(raw: str) -> dict[str, Any]:
    loaded = json.loads(raw or "{}")
    if not isinstance(loaded, dict):
        raise ValueError("hook stdin JSON must be an object")
    return loaded


def _build_hook_input(payload: dict[str, Any]) -> HookInput:
    cwd_raw = payload.get("cwd") or os.getcwd()
    cwd = Path(cwd_raw)

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    return HookInput(
        hook_event_name=str(payload.get("hook_event_name") or ""),
        tool_name=payload.get("tool_name"),
        tool_input=tool_input,
        cwd=cwd,
        session_id=payload.get("session_id"),
        raw=payload,
    )


def main() -> int:
    start = time.monotonic()

    if os.environ.get("FETTLE_DISABLE_DISPATCHER") == "1":
        print(json.dumps(_allow_output(), separators=(",", ":")))
        return 0

    # Read stdin exactly once.
    try:
        raw_stdin = sys.stdin.read()
        payload = _parse_stdin(raw_stdin)
    except Exception:
        # Fail open. Stdin can be malformed, empty, or unavailable.
        print(json.dumps(_allow_output(), separators=(",", ":")))
        return 0

    try:
        hook_input = _build_hook_input(payload)
    except Exception:
        print(json.dumps(_allow_output(), separators=(",", ":")))
        return 0

    # Load config once.
    try:
        config = load_config(PLUGIN_ROOT, hook_input.cwd)
    except Exception:
        config = DispatcherConfig(raw={})

    # Detect workspace once.
    try:
        workspace = detect_workspace(hook_input.cwd)
    except Exception:
        workspace = Workspace(root=hook_input.cwd)

    budget_ms = event_budget_ms(config, hook_input.hook_event_name)
    deadline = start + (budget_ms / 1000.0)

    ctx = HookContext(
        input=hook_input,
        config=config,
        workspace=workspace,
        plugin_root=PLUGIN_ROOT,
        hook_start_monotonic=start,
        global_deadline_monotonic=deadline,
    )

    aggregator = Aggregator(ctx=ctx, total_budget_ms=budget_ms)

    try:
        checks = select_checks(ctx)
    except Exception as exc:
        # Registry failure must fail open.
        aggregator.record_dispatcher_error("select_checks", exc)
        checks = []

    for spec in checks:
        now = time.monotonic()
        elapsed_ms = int((now - start) * 1000)

        if now > deadline:
            aggregator.record_budget_exhausted(spec.name)
            break

        check_start = time.monotonic()
        try:
            result = spec.run(ctx)
            if result is None:
                # Defensive fail-open.
                from fettle_dispatcher.types import CheckResult
                result = CheckResult.allow()
        except Exception as exc:
            # One crashing check must not kill others.
            aggregator.record_check_error(spec.name, exc)
            continue
        finally:
            check_elapsed_ms = int((time.monotonic() - check_start) * 1000)

        aggregator.add_result(spec.name, result, check_elapsed_ms)

        if aggregator.has_block:
            break

    output, exit_code = aggregator.finish()

    try:
        write_metrics(ctx, aggregator)
    except Exception:
        # Metrics must never affect hook behavior.
        pass

    print(json.dumps(output, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Absolute last-resort fail-open.
        # Do not leak stack traces to stdout because stdout must be JSON.
        try:
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass
        print(json.dumps(_allow_output(), separators=(",", ":")))
        raise SystemExit(0)
```

---

# 11. Output Aggregation

## Rules

1. First block wins.
2. Advisory messages are concatenated in execution order.
3. If no block:
   - exit `0`
   - output advisory context if present
4. If block:
   - exit `2`
   - use first blocking check’s blocking fields
   - include advisory context generated before the block
5. Later checks are not run after a block.
6. Check crashes become internal timing/error metrics, not user-visible blocks.
7. Dispatcher crashes fail open.

## Advisory concatenation

Multiple advisory results:

```python
CheckResult.advisory("A")
CheckResult.advisory("B")
```

Produce:

```json
{
  "hookSpecificOutput": {
    "additionalContext": "A\n\nB"
  }
}
```

If a check returns:

```python
CheckResult.advisory(
    hook_specific_output={"additionalContext": "A"}
)
```

that contributes `"A"`.

If both `message` and `hook_specific_output.additionalContext` are present, prefer `additionalContext` to avoid duplicate text.

## Blocking output

A blocking result:

```python
CheckResult.block(
    "Dangerous command blocked",
    hook_specific_output={
        "permissionDecision": "deny",
        "permissionDecisionReason": "Fettle blocked dangerous command"
    }
)
```

Produces exit `2` and:

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "deny",
    "permissionDecisionReason": "Fettle blocked dangerous command"
  }
}
```

If there were previous advisories:

```json
{
  "hookSpecificOutput": {
    "permissionDecision": "deny",
    "permissionDecisionReason": "Fettle blocked dangerous command",
    "additionalContext": "Previous advisory"
  }
}
```

If the blocking result omits `permissionDecision`, the aggregator must add:

```json
"permissionDecision": "deny"
```

For `PreToolUse` blocks, also add `permissionDecisionReason` from the block message if absent.

## `fettle_dispatcher/aggregate.py`

```python
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from typing import Any

from fettle_dispatcher.config import timing_include_in_output
from fettle_dispatcher.types import CheckResult, Decision, HookContext


@dataclass
class CheckTiming:
    name: str
    elapsed_ms: int
    decision: str


@dataclass
class Aggregator:
    ctx: HookContext
    total_budget_ms: int

    advisories: list[str] = field(default_factory=list)
    first_block: CheckResult | None = None
    timings: list[CheckTiming] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    budget_exhausted_before: str | None = None

    @property
    def has_block(self) -> bool:
        return self.first_block is not None

    def _extract_context(self, result: CheckResult) -> str | None:
        hso_context = result.hook_specific_output.get("additionalContext")
        if isinstance(hso_context, str) and hso_context.strip():
            return hso_context.strip()

        if result.message and result.decision == Decision.ADVISORY:
            return result.message.strip()

        return None

    def add_result(self, check_name: str, result: CheckResult, elapsed_ms: int) -> None:
        self.timings.append(
            CheckTiming(
                name=check_name,
                elapsed_ms=elapsed_ms,
                decision=result.decision.value,
            )
        )

        if result.decision == Decision.BLOCK:
            if self.first_block is None:
                self.first_block = result
            return

        context = self._extract_context(result)
        if context:
            self.advisories.append(context)

    def record_check_error(self, check_name: str, exc: BaseException) -> None:
        self.errors.append(
            {
                "phase": "check",
                "check": check_name,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=8),
            }
        )
        self.timings.append(
            CheckTiming(
                name=check_name,
                elapsed_ms=0,
                decision="error_fail_open",
            )
        )

    def record_dispatcher_error(self, phase: str, exc: BaseException) -> None:
        self.errors.append(
            {
                "phase": phase,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=8),
            }
        )

    def record_budget_exhausted(self, next_check_name: str) -> None:
        self.budget_exhausted_before = next_check_name

    def _timing_payload(self) -> dict[str, Any]:
        return {
            "budgetMs": self.total_budget_ms,
            "checks": [
                {
                    "name": t.name,
                    "elapsedMs": t.elapsed_ms,
                    "decision": t.decision,
                }
                for t in self.timings
            ],
            "budgetExhaustedBefore": self.budget_exhausted_before,
            "errorCount": len(self.errors),
        }

    def finish(self) -> tuple[dict[str, Any], int]:
        hso: dict[str, Any] = {}

        advisory_context = "\n\n".join(self.advisories).strip()

        if self.first_block is not None:
            hso.update(self.first_block.hook_specific_output)

            if advisory_context:
                existing = hso.get("additionalContext")
                if isinstance(existing, str) and existing.strip():
                    hso["additionalContext"] = advisory_context + "\n\n" + existing.strip()
                else:
                    hso["additionalContext"] = advisory_context

            if not hso.get("permissionDecision"):
                hso["permissionDecision"] = "deny"

            if not hso.get("permissionDecisionReason") and self.first_block.message:
                hso["permissionDecisionReason"] = self.first_block.message

            if timing_include_in_output(self.ctx.config):
                hso["fettleTiming"] = self._timing_payload()

            return {"hookSpecificOutput": hso}, 2

        if advisory_context:
            hso["additionalContext"] = advisory_context

        if timing_include_in_output(self.ctx.config):
            hso["fettleTiming"] = self._timing_payload()

        return {"hookSpecificOutput": hso}, 0
```

---

# 12. Timing Metrics

Timing must be self-reported without spamming Claude context by default.

Write NDJSON to:

```text
~/.claude/plugins/fettle/.state/metrics.ndjson
```

Each invocation appends one line.

## `fettle_dispatcher/timing.py`

```python
from __future__ import annotations

import json
import time
from pathlib import Path

from fettle_dispatcher.aggregate import Aggregator
from fettle_dispatcher.config import metrics_path, timing_enabled
from fettle_dispatcher.types import HookContext


def write_metrics(ctx: HookContext, aggregator: Aggregator) -> None:
    if not timing_enabled(ctx.config):
        return

    path = metrics_path(ctx.config, ctx.plugin_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "ts": time.time(),
        "sessionId": ctx.input.session_id,
        "event": ctx.event,
        "tool": ctx.tool_name,
        "cwd": str(ctx.cwd),
        "workspace": str(ctx.workspace.root),
        "budgetMs": aggregator.total_budget_ms,
        "checks": [
            {
                "name": t.name,
                "elapsedMs": t.elapsed_ms,
                "decision": t.decision,
            }
            for t in aggregator.timings
        ],
        "budgetExhaustedBefore": aggregator.budget_exhausted_before,
        "errors": [
            {
                "phase": e.get("phase"),
                "check": e.get("check"),
                "errorType": e.get("error_type"),
                "error": e.get("error"),
            }
            for e in aggregator.errors
        ],
        "blocked": aggregator.has_block,
    }

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, separators=(",", ":")) + "\n")
```

---

# 13. Error Isolation

## Requirements

The dispatcher must fail open for:

- malformed stdin
- missing fields
- config parse errors
- workspace detection errors
- registry import/selection errors
- individual check exceptions
- metrics write failures
- unexpected top-level dispatcher exceptions

## Per-check crash behavior

If a check raises:

```python
raise RuntimeError("boom")
```

The dispatcher:

1. records error in metrics
2. continues to the next check if time remains
3. exits `0` unless another check blocks
4. emits valid JSON stdout

## Important implementation rule

Check modules must not:

- call `sys.exit`
- read from stdin
- write JSON to stdout
- mutate global config
- launch their old script as a subprocess

The dispatcher only eliminates process overhead if checks run in-process.

---

# 14. Time Budgeting

## Global event budget

Default:

```text
PreToolUse  : 250ms
PostToolUse : 400ms
Stop        : 600ms
```

Before each check:

```python
if time.monotonic() > ctx.global_deadline_monotonic:
    abort remaining checks
```

This satisfies:

> abort remaining checks if elapsed > budget

## Per-check budget

Each `CheckSpec` may define `budget_ms`.

The initial implementation should treat per-check budget as advisory/cooperative unless existing checks already support deadlines.

Checks should consult:

```python
ctx.global_deadline_monotonic
```

before expensive operations.

Optional later improvement: Unix `signal.setitimer()` hard timeout. Do not add that in v2 foundation unless a known check can hang; hard timeouts complicate tests and portability.

---

# 15. Legacy Wrapper Compatibility

Existing scripts must continue to work and existing tests should continue to pass.

Do not delete or rename existing scripts.

Instead, convert each existing script to:

1. read stdin
2. build `HookContext`
3. call the corresponding check module
4. aggregate one result
5. print JSON
6. exit `0` or `2`

## Shared helper

## `fettle_dispatcher/legacy.py`

```python
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Callable

from fettle_dispatcher.aggregate import Aggregator
from fettle_dispatcher.config import event_budget_ms, load_config
from fettle_dispatcher.types import CheckResult, HookContext, HookInput, Workspace
from fettle_dispatcher.workspace import detect_workspace


def run_legacy_single_check(plugin_root: Path, check_name: str, runner: Callable[[HookContext], CheckResult]) -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        print(json.dumps({"hookSpecificOutput": {}}, separators=(",", ":")))
        return 0

    start = time.monotonic()

    try:
        cwd = Path(payload.get("cwd") or ".")
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            tool_input = {}

        hook_input = HookInput(
            hook_event_name=str(payload.get("hook_event_name") or ""),
            tool_name=payload.get("tool_name"),
            tool_input=tool_input,
            cwd=cwd,
            session_id=payload.get("session_id"),
            raw=payload,
        )

        config = load_config(plugin_root, cwd)
        workspace = detect_workspace(cwd)
        budget_ms = event_budget_ms(config, hook_input.hook_event_name)

        ctx = HookContext(
            input=hook_input,
            config=config,
            workspace=workspace,
            plugin_root=plugin_root,
            hook_start_monotonic=start,
            global_deadline_monotonic=start + budget_ms / 1000.0,
        )

        aggregator = Aggregator(ctx=ctx, total_budget_ms=budget_ms)

        result = runner(ctx)
        aggregator.add_result(check_name, result or CheckResult.allow(), 0)

        output, exit_code = aggregator.finish()
        print(json.dumps(output, separators=(",", ":")))
        return exit_code

    except Exception:
        print(json.dumps({"hookSpecificOutput": {}}, separators=(",", ":")))
        return 0
```

## Example wrapper

Existing `hooks/config_protect.py` becomes:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOKS_DIR.parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from fettle_dispatcher.legacy import run_legacy_single_check
from fettle_dispatcher.checks.config_protect_check import run


if __name__ == "__main__":
    raise SystemExit(run_legacy_single_check(PLUGIN_ROOT, "config_protect", run))
```

This preserves CLI behavior for the existing tests.

---

# 16. Refactoring `quality_gate.py`

`quality_gate.py` is special because it currently handles multiple events itself.

Refactor as follows:

## New core module

```text
hooks/fettle_dispatcher/checks/quality_gate_check.py
```

Responsibilities:

- contain the former quality gate decision logic
- accept `HookContext`
- return `CheckResult`
- no stdin/stdout/sys.exit
- no duplicate config/workspace detection

## Existing script

```text
hooks/quality_gate.py
```

Becomes a wrapper:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = HOOKS_DIR.parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from fettle_dispatcher.legacy import run_legacy_single_check
from fettle_dispatcher.checks.quality_gate_check import run


if __name__ == "__main__":
    raise SystemExit(run_legacy_single_check(PLUGIN_ROOT, "quality_gate", run))
```

## Compatibility contract

Given the same stdin payload and config, old `quality_gate.py` and new wrapper must produce semantically equivalent output:

- same exit code
- same blocking/advisory decision
- same `permissionDecision` when blocking
- same `permissionDecisionReason` text unless tests rely on exact JSON ordering
- same `additionalContext` content

JSON key ordering is not a contract.

---

# 17. Migration Plan

## Phase 1 — Add dispatcher infrastructure without changing hooks

Add:

```text
hooks/dispatcher.py
hooks/fettle_dispatcher/*
tests/dispatcher/*
```

Keep current `hooks.json`.

Run all existing tests.

Expected: no behavior change.

## Phase 2 — Extract check logic

For each existing script:

1. Move core logic into `fettle_dispatcher/checks/<name>_check.py`.
2. Make it return `CheckResult`.
3. Replace original script with legacy wrapper.
4. Run that script’s existing tests.
5. Add one parity test if output is complex.

Suggested extraction order:

1. `config_protect`
2. `destructive_guard`
3. `mcp_trust_gate`
4. `commit_message`
5. `post_edit`
6. `post_edit_ts`
7. `lean_sniffers`
8. `post_bash_doc_check`
9. `loop_detect`
10. `scope_creep`
11. `stop_quality_gate`
12. `quality_gate`

Do `quality_gate` last because it spans events.

## Phase 3 — Dispatcher integration tests

Add fake check specs in tests and assert:

- selection
- ordering
- aggregation
- fail-open
- budget abort
- timing

No production hook change yet.

## Phase 4 — Switch `hooks.json`

Backup existing file:

```bash
cp ~/.claude/plugins/fettle/hooks.json ~/.claude/plugins/fettle/hooks.json.legacy
```

Write new dispatcher-based `hooks.json`.

## Phase 5 — Observe metrics

Inspect:

```bash
tail -n 20 ~/.claude/plugins/fettle/.state/metrics.ndjson
```

Verify:

- only one Python hook invocation per event
- checks selected correctly
- no frequent errors
- budget is not routinely exhausted

## Phase 6 — Rollback if needed

Immediate rollback options:

```bash
FETTLE_DISABLE_DISPATCHER=1
```

or restore:

```bash
cp ~/.claude/plugins/fettle/hooks.json.legacy ~/.claude/plugins/fettle/hooks.json
```

---

# 18. TDD Contracts

Add dispatcher tests before switching `hooks.json`.

## `tests/dispatcher/test_dispatcher_selection.py`

### Contract: event/tool matching

Given input:

```json
{
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": {"file_path": "a.py"},
  "cwd": "/tmp/project",
  "session_id": "s"
}
```

`select_checks(ctx)` includes:

```text
config_protect
quality_gate
```

and excludes:

```text
post_edit
loop_detect
scope_creep
destructive_guard
```

### Contract: PostToolUse Write

Includes:

```text
quality_gate
post_edit
loop_detect
scope_creep
```

Includes `post_edit_ts` only for extensions:

```text
.ts .tsx .js .jsx
```

### Contract: PostToolUse Read

Includes:

```text
loop_detect
```

Excludes:

```text
quality_gate
post_edit
scope_creep
```

unless current `quality_gate` semantics require Read, in which case encode current behavior explicitly.

### Contract: disabled checks

Config:

```json
{
  "dispatcher": {
    "disabled_checks": ["loop_detect"]
  }
}
```

removes `loop_detect`.

Config:

```json
{
  "checks": {
    "scope_creep": {
      "enabled": false
    }
  }
}
```

removes `scope_creep`.

---

## `tests/dispatcher/test_dispatcher_aggregation.py`

### Contract: advisories concatenate

Given three checks:

```python
A -> advisory("one")
B -> allow()
C -> advisory("two")
```

Dispatcher output:

```json
{
  "hookSpecificOutput": {
    "additionalContext": "one\n\ntwo"
  }
}
```

Exit code:

```text
0
```

### Contract: first block wins

Given:

```python
A -> advisory("before")
B -> block("blocked by B", permissionDecisionReason="B")
C -> block("blocked by C", permissionDecisionReason="C")
```

Dispatcher:

- does not run `C`
- exits `2`
- emits reason `"B"`
- includes advisory `"before"`

### Contract: block defaults

Given:

```python
B -> CheckResult.block("blocked")
```

Output includes:

```json
{
  "permissionDecision": "deny",
  "permissionDecisionReason": "blocked"
}
```

---

## `tests/dispatcher/test_dispatcher_budget.py`

### Contract: budget aborts remaining checks

Set event budget to `1ms`.

Check A sleeps enough to exceed budget and returns allow.

Expected:

- A ran
- B did not run
- exit `0`
- metrics/aggregator records `budgetExhaustedBefore == "B"`

### Contract: budget checked before each check

If budget is already expired before first selected check:

- no checks run
- exit `0`
- valid JSON output

---

## `tests/dispatcher/test_dispatcher_fail_open.py`

### Contract: malformed stdin

Input:

```text
not-json
```

Output:

```json
{"hookSpecificOutput":{}}
```

Exit:

```text
0
```

### Contract: config loader exception

Monkeypatch `load_config` to raise.

Expected:

- dispatcher exits `0`
- selected checks can still run with default config, or dispatcher allows if context cannot be built
- stdout is valid JSON

### Contract: check exception

Given:

```python
A -> raises RuntimeError
B -> advisory("still ran")
```

Expected:

- exit `0`
- output contains `"still ran"`
- no traceback on stdout
- metrics contains error count `1`

### Contract: metrics failure

Monkeypatch `write_metrics` to raise.

Expected:

- dispatcher still emits normal output
- exit code unchanged

---

## `tests/dispatcher/test_dispatcher_timing.py`

### Contract: metrics written

Given timing enabled, after dispatcher run:

```text
.state/metrics.ndjson
```

contains one JSON line with:

```json
{
  "event": "PostToolUse",
  "tool": "Write",
  "budgetMs": 400,
  "checks": [
    {
      "name": "some_check",
      "elapsedMs": 1,
      "decision": "allow"
    }
  ],
  "blocked": false
}
```

Do not assert exact elapsed time except it is an integer `>= 0`.

### Contract: timing optionally included in hook output

Config:

```json
{
  "dispatcher": {
    "timing": {
      "include_in_hook_output": true
    }
  }
}
```

Output includes:

```json
{
  "hookSpecificOutput": {
    "fettleTiming": {
      "budgetMs": 400,
      "checks": []
    }
  }
}
```

---

## `tests/dispatcher/test_legacy_wrapper_parity.py`

For each refactored script:

1. Feed representative stdin payload.
2. Call the legacy wrapper script.
3. Call the check module through dispatcher single-check helper.
4. Assert same semantic decision.

At minimum:

```text
quality_gate.py
config_protect.py
destructive_guard.py
loop_detect.py
scope_creep.py
```

---

# 19. Performance Expectations

Current `PostToolUse(Write)`:

```text
6 sequential Python processes
6 × run.sh Python lookup
6 × interpreter startup
6 × imports
6 × config load
6 × workspace detection
6 × actual check
```

Typical current latency estimate:

```text
process startup/import/config overhead:
  6 × 60–80ms = 360–480ms

actual check work:
  6 × 10–50ms = 60–300ms

total:
  ~420–780ms
```

New dispatcher:

```text
1 × run.sh Python lookup
1 × interpreter startup
1 × imports
1 × config load
1 × workspace detection
N in-process checks
```

Expected latency:

```text
startup/import/config/workspace:
  ~70–110ms

actual checks:
  ~60–180ms

total:
  ~130–290ms
```

Expected improvement:

```text
PostToolUse(Write): 55–75% lower latency
PreToolUse(Bash): 45–65% lower latency
Stop: 35–55% lower latency
```

The largest win comes from eliminating repeated interpreter startup and repeated config/workspace work.

---

# 20. Implementation Checklist

## Must-have for v2 foundation

- [ ] Add `hooks/dispatcher.py`
- [ ] Add `hooks/fettle_dispatcher/types.py`
- [ ] Add `hooks/fettle_dispatcher/config.py`
- [ ] Add `hooks/fettle_dispatcher/workspace.py`
- [ ] Add `hooks/fettle_dispatcher/registry.py`
- [ ] Add `hooks/fettle_dispatcher/aggregate.py`
- [ ] Add `hooks/fettle_dispatcher/timing.py`
- [ ] Add `hooks/fettle_dispatcher/legacy.py`
- [ ] Add check modules under `hooks/fettle_dispatcher/checks/`
- [ ] Convert old scripts to wrappers
- [ ] Keep `subagent_inject.js` unchanged
- [ ] Add dispatcher tests
- [ ] Preserve existing test suite
- [ ] Update `hooks.json`
- [ ] Add rollback backup

## Non-goals for this foundation

Do not implement these yet:

- daemonized long-running dispatcher
- socket server
- multiprocessing
- external dependencies
- async framework
- hard kill of checks
- changing Claude hook format
- replacing JS `SubagentStart`

---

# 21. Final Compatibility Guarantees

After migration:

1. Claude Code still sees normal plugin `hooks.json`.
2. Hook commands are still `{"type": "command", "command": "..."}`.
3. stdin contract is unchanged.
4. stdout remains JSON.
5. exit `0` means allow/advisory.
6. exit `2` means block.
7. all errors fail open.
8. `SubagentStart` remains JS and fast.
9. existing script-level tests continue to pass.
10. existing scripts remain directly runnable.
