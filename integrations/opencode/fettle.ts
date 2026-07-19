import { spawn } from "node:child_process"
import { homedir } from "node:os"
import { join } from "node:path"

import type { Plugin } from "@opencode-ai/plugin"

const pluginRoot = process.env.FETTLE_PLUGIN_ROOT ?? join(homedir(), ".claude", "plugins", "fettle")
const launcher = join(pluginRoot, "scripts", "run.sh")

const toolNames: Record<string, string> = {
  bash: "Bash",
  edit: "Edit",
  read: "Read",
  write: "Write",
}

function normalizeArgs(args: Record<string, unknown>) {
  const normalized = { ...args }
  const filePath = args.filePath ?? args.file_path
  if (typeof filePath === "string") normalized.file_path = filePath
  return normalized
}

function runFettle(event: string, tool: string | undefined, args: Record<string, unknown>, directory: string, sessionID: string) {
  return new Promise<{ blocked: boolean; message: string }>((resolve) => {
    const child = spawn("/bin/bash", [launcher, "dispatcher.py"], {
      cwd: directory,
      env: process.env,
      stdio: ["pipe", "pipe", "pipe"],
    })
    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => (stdout += chunk))
    child.stderr.on("data", (chunk) => (stderr += chunk))
    child.on("error", (error) => resolve({ blocked: false, message: `Fettle unavailable: ${error.message}` }))
    child.on("close", (code) => {
      try {
        const result = JSON.parse(stdout || "{}")
        const output = result.hookSpecificOutput ?? {}
        resolve({
          blocked: code === 2 || output.permissionDecision === "deny",
          message: output.permissionDecisionReason ?? output.additionalContext ?? stderr.trim(),
        })
      } catch {
        resolve({ blocked: false, message: stderr.trim() || "Fettle returned invalid output" })
      }
    })
    child.stdin.end(JSON.stringify({
      hook_event_name: event,
      tool_name: tool,
      tool_input: normalizeArgs(args),
      cwd: directory,
      session_id: sessionID,
    }))
  })
}

export const FettlePlugin = (async ({ client, directory }) => {
  async function notify(message: string, variant: "warning" | "error") {
    if (!message) return
    await client.tui.showToast({
      body: { title: "Fettle", message, variant, duration: variant === "error" ? 10000 : 6000 },
    }).catch(() => undefined)
  }

  return {
    "tool.execute.before": async (input, output) => {
      const tool = toolNames[input.tool]
      if (!tool || !["Bash", "Edit", "Write"].includes(tool)) return
      const result = await runFettle("PreToolUse", tool, output.args ?? {}, directory, input.sessionID)
      if (result.blocked) throw new Error(result.message || "Blocked by Fettle")
      await notify(result.message, "warning")
    },
    "tool.execute.after": async (input, output) => {
      const tool = toolNames[input.tool]
      if (!tool) return
      const result = await runFettle("PostToolUse", tool, input.args ?? {}, directory, input.sessionID)
      const message = result.message
      if (message) output.output = `${output.output}\n\nFettle:\n${message}`
      await notify(message, result.blocked ? "error" : "warning")
    },
    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const result = await runFettle("Stop", undefined, {}, directory, event.properties.sessionID)
      await notify(result.message, result.blocked ? "error" : "warning")
    },
  }
}) satisfies Plugin
