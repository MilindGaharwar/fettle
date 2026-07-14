#!/usr/bin/env node
// WP-104 — SubagentStart hook: inject The Ladder into spawned subagents.
// Must complete in <50ms. Fail-open on all errors.
"use strict";

const fs = require("fs");
const path = require("path");

const LADDER = `Before writing new code, stop at the first rung that holds:
1. Does this need to exist? Speculative = skip. YAGNI.
2. Already in this codebase? Grep first. Reuse > rewrite.
3. Stdlib/platform does it? Use it.
4. Already-installed dep solves it? Never add a dep for what few lines do.
5. One-liner? Do that.
6. Only then: minimum code that works.

No unrequested abstractions. Deletion over addition. Shortest working diff.
NEVER simplify away: input validation, error handling, security, accessibility.`;

function loadConfig(projectDir) {
  if (!projectDir) return { enabled: true, injection_file: "", mode: "advisory" };
  const cfgPath = path.join(projectDir, ".fettle.toml");
  try {
    const content = fs.readFileSync(cfgPath, "utf8");
    const section = content.match(/\[gates\.subagent\]([\s\S]*?)(?=\n\[|$)/);
    if (!section) return { enabled: true, injection_file: "", mode: "advisory" };
    const block = section[1];
    const enabled = block.match(/enabled\s*=\s*(true|false)/);
    const injFile = block.match(/injection_file\s*=\s*"([^"]*)"/);
    const mode = block.match(/mode\s*=\s*"([^"]*)"/);
    return {
      enabled: enabled ? enabled[1] === "true" : true,
      injection_file: injFile ? injFile[1] : "",
      mode: mode ? mode[1] : "advisory",
    };
  } catch {
    return { enabled: true, injection_file: "", mode: "advisory" };
  }
}

function main() {
  let input;
  try {
    const raw = fs.readFileSync(0, "utf8");
    if (!raw.trim()) process.exit(0);
    input = JSON.parse(raw);
  } catch {
    process.exit(0);
  }

  const projectDir = process.env.FETTLE_PROJECT_DIR || input.cwd || "";
  const cfg = loadConfig(projectDir);

  if (!cfg.enabled || cfg.mode === "off") process.exit(0);

  const matcher = process.env.FETTLE_SUBAGENT_MATCHER;
  if (matcher) {
    const agentType = input.agent_type || "";
    try {
      if (!new RegExp(matcher).test(agentType)) process.exit(0);
    } catch {
      // Invalid regex → fail-open, inject anyway
    }
  }

  let content = LADDER;
  if (cfg.injection_file) {
    try {
      content = fs.readFileSync(cfg.injection_file, "utf8").trim();
    } catch {
      // Fall back to built-in ladder
      content = LADDER;
    }
  }

  const output = {
    hookSpecificOutput: {
      hookEventName: "SubagentStart",
      additionalContext: content,
    },
  };
  process.stdout.write(JSON.stringify(output) + "\n");
}

main();
