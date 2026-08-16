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
| Claude Code real session | Claude Code 2.1.233 | BLOCKED; isolated home is not logged in |
| Codex CLI real session | Codex CLI 0.147.0, disposable install | BLOCKED; API returned HTTP 401 with no bearer authentication |
| Gemini CLI real session | Gemini CLI 0.55.1, disposable install | BLOCKED; no Gemini authentication method is configured |

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

## Blockers And Recovery

| Host | Blocker | Recovery |
|---|---|---|
| Claude Code | `Not logged in` in the isolated home | Run `claude /login` for that home, then repeat the session |
| Codex CLI | OpenAI API HTTP 401; no bearer or basic authentication | Run `codex login` or configure `OPENAI_API_KEY`, enable hooks, then repeat |
| Gemini CLI | No auth method in isolated `settings.json` | Configure Gemini login, `GEMINI_API_KEY`, Vertex AI, or GCA, then repeat |

The Codex lifecycle sentinel was intentionally a foreign top-level field.
Fettle preserved it, as required, while Codex 0.147.0 correctly rejected that
synthetic field under its strict runtime schema. Removing only the disposable
sentinel isolated the remaining session blocker to authentication.

## Accessibility And UX

- Initialization, diagnosis, repair, and blocker states are available as text.
- `fettle init --json` exposes the same distinctions without color or TTY use.
- Browser, mobile, visual-regression, and axe checks do not apply to these CLI
  integrations.

## Decision

CONDITIONAL PASS. Installed artifact publication, upgrade convergence,
configuration preservation, stale recovery, and OpenCode real-session
governance are observed. Claude Code, Codex CLI, and Gemini CLI real sessions
remain blocked by unavailable isolated-home credentials and are not counted as
passes.
