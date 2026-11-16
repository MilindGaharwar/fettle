# Semgrep and live UAT qualification follow-up

Date: 2026-11-16. Tested candidate:
`4030de04759ea756d3c3c95a85e920afcf9954d7`.
This follow-up changes validation records only; runtime, tests, rules, timeouts
and existing qualification artifacts remain unchanged.

## Semgrep investigation

The earlier failure was a subprocess timeout after 60 seconds with no captured
output in `test_configured_promise_api_fires_end_to_end`. The captured evidence
cannot identify the stalled phase. The same test passed again with defaults
(7.97 seconds), then in four alternating isolated runs: default 3.41 seconds,
optional telemetry/version checks disabled 2.74 seconds, default 2.75 seconds,
and optional checks disabled 2.86 seconds. Both positive detection and the
negative awaited-promise assertion executed in every passing run.

The test prepends the user's local tool directory to PATH; it resolves the
installed Semgrep launcher rather than necessarily the test virtualenv's copy.
The generated rule is local and digest-named. Optional version/telemetry traffic
is a possible delay source, but these comparisons do not establish causality.
A transient host/process/network delay remains possible. There is no retained
trace from the timed-out process to distinguish them. No reproducible parser,
rule or Fettle orchestration defect was found. Do not increase timeouts, disable
findings or claim the intermittent stall is fixed from these observations.

## Live qualification

The existing dedicated `colima-fettle-uat` profile was stopped initially. It was
started for this run. The shared default profile stayed stopped. The dedicated
daemon had no containers and retained the exact required Python and browser
image identities. The upstream Playwright v1.63.0 seccomp profile was retrieved
from its public repository and verified against the existing required SHA-256
`cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849`.
The tests applied the existing chroot allowance and verified the effective profile;
no security policy, image identity or acceptance criterion was relaxed.

With disposable XDG state/configuration and the existing tool virtualenv on PATH:

- `FETTLE_UAT_DOCKER=1 FETTLE_UAT_VM_RESTART=1 pytest tests/test_uat_session.py`
  selecting API capture/replay, observed-state restart, failed-capture recovery
  and SIGKILL/VM restart: **10 passed**, 349 deselected, 81.18 seconds.
- `FETTLE_UAT_DOCKER=1 pytest tests/test_uat_session.py -k browser_form_submission`:
  **10 passed**, 349 deselected, 50.23 seconds.

An early browser invocation was interrupted before any test completed so that
browser qualification could run separately from the API/VM sequence. Its result
is not counted as a pass. The completed browser run followed the API/VM run.
Passing negative cases establish their specified contradiction/blocking behavior;
they do not mean seeded defective products passed acceptance.

## Preservation and limits

Original dirty Fettle files, modes and staging are preserved. Protected Book Brain
packet/answer histories remain local and unchanged. No raw prompts, private
histories, runtime receipts or machine-specific logs are committed. Live tests
use disposable products and their existing ownership-scoped resource cleanup.
The dedicated VM is returned to its initial stopped state after resource checks.

The earlier broad test interruptions/timeouts remain recorded. These targeted
runs close the previously unexecuted 20 VM/Docker cases for the stated candidate
and host; they do not establish human UAT parity, general host support, formal
assurance or a full uninterrupted-suite pass. The intermittent Semgrep stall
remains unexplained and should receive process-level diagnostics if it recurs.

Fettle full scan: **427 files, zero findings or tool errors**. Documentation
checks, privacy scrub and Git whitespace checks are run before publication.
