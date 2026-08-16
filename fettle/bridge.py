"""Versioned transport bridge for agent hosts installed from a wheel."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fettle import __version__

_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BridgeResult:
    status: str
    detail: str


@dataclass(frozen=True)
class BridgeValidation:
    ok: bool
    status: str
    detail: str


def bridge_base() -> Path:
    """Return the platform user-data root for versioned bridges."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "fettle" / "bridge"
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        return Path(root) / "fettle" / "bridge" if root else Path.home() / "AppData" / "Local" / "fettle" / "bridge"
    root = os.environ.get("XDG_DATA_HOME")
    return (Path(root) if root else Path.home() / ".local" / "share") / "fettle" / "bridge"


def bridge_dir() -> Path:
    return bridge_base() / __version__


def _shell_command(arguments: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(arguments)
    return shlex.join(arguments)


def _is_link_like(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(is_junction and is_junction())


def dispatcher_command() -> str:
    """Return a shell-safe command containing no event-controlled data."""
    executable = os.path.abspath(sys.executable)
    return _shell_command([executable, "-m", "fettle.dispatcher"])


def _source_subagent_hook() -> Path:
    package = Path(__file__).parent / "_bridge" / "subagent_inject.js"
    if package.is_file():
        return package
    return Path(__file__).parent.parent / "hooks" / "subagent_inject.js"


def _commands_source() -> Path:
    from fettle._resources import commands_dir
    return commands_dir()


def _opencode_transport() -> str:
    executable = json.dumps(os.path.abspath(sys.executable))
    return f'''import {{ spawn }} from "node:child_process"

import type {{ Plugin }} from "@opencode-ai/plugin"

const python = {executable}
const toolNames: Record<string, string> = {{ bash: "Bash", edit: "Edit", read: "Read", write: "Write" }}

function normalizeArgs(args: Record<string, unknown>) {{
  const normalized = {{ ...args }}
  const filePath = args.filePath ?? args.file_path
  if (typeof filePath === "string") normalized.file_path = filePath
  return normalized
}}

function runFettle(event: string, tool: string | undefined, args: Record<string, unknown>, directory: string, sessionID: string) {{
  return new Promise<{{ blocked: boolean; message: string }}>((resolve) => {{
    const child = spawn(python, ["-m", "fettle.dispatcher"], {{ cwd: directory, env: process.env, stdio: ["pipe", "pipe", "pipe"] }})
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => (stdout += chunk))
    child.stderr.on("data", (chunk) => (stderr += chunk))
    child.on("error", (error) => resolve({{ blocked: false, message: `Fettle unavailable: ${{error.message}}` }}))
    child.on("close", (code) => {{
      try {{
        const result = JSON.parse(stdout || "{{}}")
        const output = result.hookSpecificOutput ?? {{}}
        resolve({{
          blocked: code === 2 || result.decision === "block" || output.permissionDecision === "deny",
          message: result.reason ?? output.permissionDecisionReason ?? output.additionalContext ?? result.systemMessage ?? stderr.trim(),
        }})
      }} catch {{
        resolve({{ blocked: false, message: stderr.trim() || "Fettle returned invalid output" }})
      }}
    }})
    child.stdin.end(JSON.stringify({{ hook_event_name: event, tool_name: tool, tool_input: normalizeArgs(args), cwd: directory, session_id: sessionID }}))
  }})
}}

export const FettlePlugin = (async ({{ client, directory }}) => {{
  async function notify(message: string, variant: "warning" | "error") {{
    if (!message) return
    await client.tui.showToast({{ body: {{ title: "Fettle", message, variant, duration: variant === "error" ? 10000 : 6000 }} }}).catch(() => undefined)
  }}
  return {{
    "tool.execute.before": async (input, output) => {{
      const tool = toolNames[input.tool]
      if (!tool || !["Bash", "Edit", "Write"].includes(tool)) return
      const result = await runFettle("PreToolUse", tool, output.args ?? {{}}, directory, input.sessionID)
      if (result.blocked) throw new Error(result.message || "Blocked by Fettle")
      await notify(result.message, "warning")
    }},
    "tool.execute.after": async (input, output) => {{
      const tool = toolNames[input.tool]
      if (!tool) return
      const result = await runFettle("PostToolUse", tool, input.args ?? {{}}, directory, input.sessionID)
      if (result.message) output.output = `${{output.output}}\n\nFettle:\n${{result.message}}`
      await notify(result.message, result.blocked ? "error" : "warning")
    }},
    event: async ({{ event }}) => {{
      if (event.type !== "session.idle") return
      const result = await runFettle("Stop", undefined, {{}}, directory, event.properties.sessionID)
      await notify(result.message, result.blocked ? "error" : "warning")
    }},
  }}
}}) satisfies Plugin
'''


def _write_tree(root: Path, published_root: Path) -> None:
    (root / "hooks").mkdir(parents=True)
    (root / "opencode").mkdir()
    shutil.copy2(_source_subagent_hook(), root / "hooks" / "subagent_inject.js")
    shutil.copytree(_commands_source(), root / "commands")
    (root / "opencode" / "fettle.ts").write_text(_opencode_transport())
    command = dispatcher_command()
    hooks = {
        "description": "Fettle installed-package hooks",
        "hooks": {
            "PreToolUse": [{"matcher": "Write|Edit|Bash", "hooks": [{"type": "command", "command": command, "timeout": 10}]}],
            "PostToolUse": [{"matcher": "Write|Edit|Bash|Read", "hooks": [{"type": "command", "command": command, "timeout": 15}]}],
            "SubagentStart": [{"hooks": [{"type": "command", "command": _shell_command(["node", str(published_root / "hooks" / "subagent_inject.js")]), "timeout": 5}]}],
            "Stop": [{"hooks": [{"type": "command", "command": command, "timeout": 60}]}],
        },
    }
    (root / "hooks" / "hooks.json").write_text(json.dumps(hooks, indent=2) + "\n")
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    manifest = {
        "schema_version": _SCHEMA_VERSION,
        "fettle_version": __version__,
        "python": os.path.abspath(sys.executable),
        "files": files,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (root / "manifest.json").chmod(stat.S_IRUSR | stat.S_IWUSR)


def validate_bridge() -> BridgeValidation:
    root = bridge_dir()
    if _is_link_like(root):
        return BridgeValidation(False, "conflict", "bridge path is a symlink — resolve it manually")
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        if manifest.get("schema_version") != _SCHEMA_VERSION or manifest.get("fettle_version") != __version__:
            raise ValueError("manifest version mismatch")
        if manifest.get("python") != os.path.abspath(sys.executable):
            raise ValueError("Python environment changed")
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("manifest file inventory is missing")
        for relative, expected in files.items():
            path = root / relative
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError(f"file digest mismatch: {relative}")
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        return BridgeValidation(False, "stale", f"installed bridge invalid ({exc}) — run: fettle init")
    return BridgeValidation(True, "supported-installed", f"installed bridge {__version__} valid at {root}")


def publish_bridge(*, dry_run: bool) -> BridgeResult:
    base = bridge_base()
    root = bridge_dir()
    if _is_link_like(base) or _is_link_like(root):
        return BridgeResult("error", "bridge path is a symlink — resolve it manually")
    if root.exists():
        validation = validate_bridge()
        if validation.ok:
            return BridgeResult("ok", validation.detail)
        if not (root / "manifest.json").is_file():
            return BridgeResult("error", "bridge directory is not manifest-owned — resolve it manually")
    if dry_run:
        return BridgeResult("created", f"(dry-run) would publish installed bridge at {root}")
    base.parent.mkdir(parents=True, exist_ok=True)
    base.mkdir(mode=0o700, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{__version__}.tmp-", dir=base))
    backup = base / f".{__version__}.backup"
    try:
        _write_tree(temporary, root)
        if root.exists():
            if backup.exists():
                shutil.rmtree(backup)
            os.replace(root, backup)
        os.replace(temporary, root)
    except (OSError, ValueError) as exc:
        shutil.rmtree(temporary, ignore_errors=True)
        if backup.exists() and not root.exists():
            os.replace(backup, root)
        return BridgeResult("error", f"could not publish installed bridge: {exc}")
    validation = validate_bridge()
    if validation.ok:
        shutil.rmtree(backup, ignore_errors=True)
    elif backup.exists():
        shutil.rmtree(root, ignore_errors=True)
        os.replace(backup, root)
    return BridgeResult("created" if validation.ok else "error", validation.detail)
