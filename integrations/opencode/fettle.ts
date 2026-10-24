import { spawn } from "node:child_process"
import { homedir } from "node:os"
import { join } from "node:path"

import type { Plugin } from "@opencode-ai/plugin"

const pluginRoot = process.env.FETTLE_PLUGIN_ROOT ?? join(homedir(), ".claude", "plugins", "fettle")
const launcher = join(pluginRoot, "fettle", "run.sh")

const toolNames: Record<string, string> = {
  bash: "Bash",
  shell: "Bash",
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
    child.on("error", () => resolve({
      blocked: event === "PreToolUse",
      message: event === "PreToolUse" ? "Secret protection unavailable. Run `fettle doctor`." : "Fettle unavailable",
    }))
    child.on("close", (code) => {
      try {
        const result = JSON.parse(stdout || "{}")
        const output = result.hookSpecificOutput ?? {}
        resolve({
          blocked: code === 2 || result.decision === "block" || output.permissionDecision === "deny",
          message:
            result.reason ??
            output.permissionDecisionReason ??
            output.additionalContext ??
            result.systemMessage ??
            stderr.trim(),
        })
      } catch {
        resolve({
          blocked: event === "PreToolUse",
          message: event === "PreToolUse" ? "Secret protection returned invalid output. Run `fettle doctor`." : "Fettle returned invalid output",
        })
      }
    })
    child.stdin.end(JSON.stringify({
      hook_event_name: event,
      tool_name: tool,
      tool_input: normalizeArgs(args),
      fettle_host: "opencode",
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
      const tool = toolNames[input.tool] ?? input.tool
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

export default {
  id: "fettle.policy",
  async setup(ctx: any) {
    await ctx.tool.hook("execute.before", async (event: any) => {
      try {
        const tool = toolNames[event.tool] ?? event.tool
        const directory = event.input?.workdir ?? ctx.location.directory
        const result = await runFettle("PreToolUse", tool, event.input ?? {}, directory, event.sessionID)
        if (result.blocked) throw new Error(result.message || "Blocked by Fettle")
      } catch (error) {
        const message = error instanceof Error ? error.message : "Fettle policy check failed. Run `fettle doctor`."
        throw new Error(message)
      }
    })
    await ctx.tool.hook("execute.after", async (event: any) => {
      const tool = toolNames[event.tool]
      if (!tool) return
      const directory = event.input?.workdir ?? ctx.location.directory
      const result = await runFettle("PostToolUse", tool, event.input ?? {}, directory, event.sessionID)
      if (result.message && event.status === "completed" && Array.isArray(event.result?.content)) {
        event.result.content.push({ type: "text", text: `Fettle:\n${result.message}` })
      }
    })
    const controller = new AbortController()
    void (async () => {
      try {
        for await (const event of ctx.event.subscribe({ signal: controller.signal })) {
          if (event.type !== "session.idle") continue
          const result = await runFettle("Stop", undefined, {}, ctx.location.directory, event.properties.sessionID)
          if (result.message) console.error(`Fettle ${result.blocked ? "error" : "warning"}: ${result.message}`)
        }
      } catch {
        if (!controller.signal.aborted) console.error("Fettle Stop observer unavailable. Run `fettle doctor`.")
      }
    })()
    return () => controller.abort()
  },
  server: FettlePlugin,
}
