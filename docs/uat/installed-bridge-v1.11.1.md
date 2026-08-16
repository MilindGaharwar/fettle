# UAT Report: Installed Bridge v1.11.1

Date: 2026-08-16

## Scenarios Tested

| Scenario | Environment | Result |
|---|---|---|
| Build wheel and sdist with bridge resources | Local build | PASS; bridge resource and 17 workflows present in both artifacts |
| Clean wheel install and repeat initialization | Disposable home, repository, and virtual environment | PASS |
| Upgrade 1.11.0 registrations to 1.11.1 | Disposable mixed-state home | PASS; one current registration per host |
| Preserve unrelated host configuration | Sentinel settings for all host formats | PASS |
| Preserve wheel virtual-environment interpreter | Python 3.14 virtual environment | PASS; manifest and transports retain the absolute virtualenv path |
| Detect and repair a tampered bridge | Modified `opencode/fettle.ts` | PASS; `stale` with `run: fettle init`, then `supported-installed` |
| OpenCode real session invokes governance | OpenCode 1.18.15 | PASS; host wrote the requested file, surfaced F401, and recorded session-linked trace evidence |
| Claude Code real session | Claude Code 2.1.233, managed Bedrock authentication | BLOCKED; candidate plugin loaded, but the provider returned HTTP 429 before a tool call |
| Codex CLI real session | Codex CLI 0.147.0, isolated ChatGPT authentication | BLOCKED; the host created the requested file, but did not invoke configured Fettle hooks |
| Gemini CLI real session | Gemini CLI 0.55.1, Google OAuth | BLOCKED; Google rejected the retired client for the account tier with `UNSUPPORTED_CLIENT` |

## Evidence

- Focused bridge, initialization, dispatcher, and adapter tests: 91 passed;
  broader bridge, workflow, doctor, dispatcher, and host-adapter tests: 185 passed.
- Rebuilt `dist/finefettle-1.11.1-py3-none-any.whl` and
  `dist/finefettle-1.11.1.tar.gz` passed content inspection.
- Upgrade replay retained the OpenCode theme and Codex/Gemini sentinel values,
  replaced prior manifest-owned registrations, and retained exactly three
  dispatcher hooks in each command-hook configuration.
- The installed bridge manifest records the wheel virtual environment's
  absolute `bin/python`, not its resolved base interpreter.
- OpenCode session `ses_ff6b9d459ffelmeIZ4ww7qk8KB` wrote
  `app/host-session.py`, displayed Ruff F401 in the session, and produced an
  `adapter_check` violation in `$XDG_STATE_HOME/fettle/trace.jsonl` with the
  same session ID.
- Clean edits do not create trace rows by design; the real-session oracle used
  a deliberate lint violation so host invocation had persistent evidence.
- Codex session `01a0098d-225c-7a80-8cc1-6c565420ddd1` authenticated through
  ChatGPT and wrote the requested two-line F401 file. Codex reported its
  `hooks` feature as stable and enabled, but no Fettle trace or configured hook
  invocation was observed.
- Claude session `b17b927a-2f3a-49e9-98bb-4cedf4a2debe` loaded the candidate
  `1.11.1` bridge plugin under managed Bedrock authentication, then stopped on
  HTTP 429 before any tool call.
- Gemini OAuth reached the provider, which rejected CLI `0.55.1` with
  `UNSUPPORTED_CLIENT` and directed individual-tier users to Antigravity.

## Blockers And Recovery

| Host | Blocker | Recovery |
|---|---|---|
| Claude Code | Managed Bedrock provider returned HTTP 429 before a tool call | Repeat when provider capacity is available |
| Codex CLI | Authenticated session did not invoke enabled `hooks.json` commands | Resolve Codex 0.147 hook event/schema compatibility in issue #9, then repeat |
| Gemini CLI | OAuth rejected retired client `0.55.1` with `UNSUPPORTED_CLIENT` | Assess Antigravity migration in issue #8; use an eligible API/Workspace path only if already available |

The Codex lifecycle sentinel was intentionally a foreign top-level field.
Fettle preserved it, as required, while Codex 0.147.0 correctly rejected that
synthetic field under its strict runtime schema. Removing only the disposable
sentinel allowed the authenticated runtime test and exposed the unobserved
hook invocation separately.

## Accessibility And UX

- Initialization, diagnosis, repair, and blocker states are available as text.
- `fettle init --json` exposes the same distinctions without color or TTY use.
- Browser, mobile, visual-regression, and axe checks do not apply to these CLI
  integrations.

## Decision

CONDITIONAL PASS. Installed artifact publication, upgrade convergence,
configuration preservation, stale recovery, and OpenCode real-session
governance are observed. Authentication was established for Claude Code,
Codex CLI, and Gemini CLI, but their success criteria remain non-pass because
of provider throttling, unobserved Codex hook invocation, and upstream Gemini
client retirement respectively.
