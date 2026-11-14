---
fettle-work-item: v2
id: trust-remediation-tr1
status: done
scope:
  - fettle/
  - hooks/hooks.json
  - tests/test_installed_hooks_e2e.py
  - tests/test_trust_remediation_tr1.py
  - tests/test_agents.py
  - tests/test_host_event_parity.py
  - tests/test_dispatcher*.py
  - tests/test_installed_bridge.py
  - tests/test_run_sh.py
  - docs/behavior-map.md
  - docs/installed-governance-bridge.md
  - docs/trust-remediation-implementation-plan.md
  - docs/trust-remediation.ux-spec.md
  - docs/backlog/trust-remediation-tr1.md
  - docs/completion/trust-remediation-tr1.json
  - docs/completion/evidence/trust-remediation-tr1/
spec: trust-remediation-implementation-plan
---

# TR-1 shipped hook path

Make the command installed into agent hosts the authoritative enforcement path.
The dispatcher owns edit recording, project-root policy loading, host tool
normalisation, multi-target fan-out, and required-check failure semantics.

## Resolution

Done. Both installed launch modes exercise the same dispatcher and canonical
check entry points. Retained evidence covers journal deletion and malformation,
subdirectory invocation, edit aliases, multi-target patches, repository-local
import shadowing, malformed PreToolUse input, missing interpreter failure, the
full regression and quality gates, and a bounded narrow mutation replay. The
replay completed with 144 survivors, retained as explicit test-strength debt.
