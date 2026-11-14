# Trust Remediation Implementation Plan

Date: 2026-11-13
Status: proposed. Implementation starts only after the mutation hardening (D4)
closes; see [TODO](engagement/TODO.md).
Owner: Milind (approval and merge authority); implementing engineer (delivery);
independent reviewer in a separate session (verification before merge).

Related artifacts: [program index](plan-index.md),
[extension ownership](behavior-map.md), [roadmap](ROADMAP.md),
[evidence contract](evidence-artifact-contract.md), [security policy](../SECURITY.md).

Audited revision: `main` at `1ffff5c01900bee48d1225c8799eed0b91e6c083` (v1.14.0).
Every file and line reference below is to that revision.

## 1. Objective and user flow

As someone who lets an AI coding agent work unattended, I want a green Fettle
result to mean that the gates I enabled actually ran, that the agent could not
switch them off, and that "tests passed" was established by something other
than the agent's own word.

Flow: install -> enable gates -> agent works -> gates fire on the installed
hook path -> verification is recorded with test counts -> an independent
verifier re-establishes the result and signs it -> a consumer checks the
signature against policy the agent could not change.

The 2026-11-13 audit found that the first half of this flow is partly hollow on
the installed path and that the second half does not exist. This plan closes
those gaps in priority order. The README is not reduced; each package makes
specific README sentences true (section 9).

## 2. Evidence base

The audit exported `main` read-only, ran five subsystem reads that had to prove
findings by reproduction, and then re-ran the most serious ones. Each finding
carries one marker:

| Marker | Meaning |
|---|---|
| R | Reproduced by the plan author on the audited revision |
| S | Reproduced by a subsystem read, with commands and output; not re-run by the plan author |
| C | Confirmed by reading the cited code; not executed |
| U | Unconfirmed; the package that owns it must confirm or close it first |

Every change in section 6 was checked against the cited function before being
written down. Where a design depends on an external fact, the fact was checked:

- **Python `-P`.** In a directory containing a hostile `fettle/dispatcher.py`
  and `logging.py`, `python -m fettle.dispatcher` printed the hostile output;
  `python -P -m fettle.dispatcher` ran the real dispatcher. `-P` exists from
  Python 3.11, which is Fettle's minimum.
- **OpenSSH signatures.** `ssh-keygen -Y sign -n <namespace>` and
  `ssh-keygen -Y verify -f allowed_signers -I <principal> -n <namespace>` were
  exercised with OpenSSH 10.5: a good signature verified; a changed payload and
  a wrong namespace both failed.
- **Claude Code hook semantics** (hooks reference, read 2026-11-13):
  exit 2 blocks and, when the hook also printed a blocking JSON decision, that
  decision's reason is used; any other non-zero exit, a crash or a timeout is
  non-blocking unless the hook sets `"onFailure": "block"` (v2.1.295 or later);
  the `cwd` field follows `cd`; the documentation names `PowerShell` and
  `NotebookEdit` as tools and does not mention `MultiEdit`.

Two audit items changed during planning:

- **Closed, not a defect:** "block reasons may be invisible on Claude Code".
  The host documentation shows the JSON reason is used on exit 2.
- **Downgraded:** "a label event may turn a failed `mutation evidence` check
  green". The job name is written as an expression
  (`name: ${{ 'mutation evidence' }}`, `mutation-pr.yml:254`), and
  `tests/test_doc_claims.py` and `tests/test_ci.py:1906,2392` pin that form.
  That is consistent with deliberate containment, if a skipped job reports
  under its unevaluated name; this plan has not confirmed that behaviour. It
  stays as a one-time confirmation in TR-0.

## 3. Assumptions, boundaries and decisions

Owner decisions recorded on 2026-11-13:

- Finish the mutation hardening first, including D4 run 3. Fixes follow.
- The README keeps advertising full capability. The gap is closed by making the
  claims true, not by weakening the text.
- The trust root is provider-neutral. It must work on any CI system and
  locally; no single hosting provider may be required.
- For every fix: the implementing agent opens the pull request; the independent
  reviewer verifies it and merges.

Boundaries:

- **Threat model.** The adversary is the governed agent, running as the
  developer's own user with shell access, careless or prompt-injected. Out of
  scope: compromise of CI secret storage, of protected-branch settings, of a
  human's signing key, and operating-system sandbox escape.
- **What local hooks can and cannot do.** On one user account, every file the
  hooks read is writable by the agent. Hooks therefore give fast feedback and
  stop careless behaviour; they cannot be the final authority against a hostile
  agent. Final authority moves to the independent verifier (design D-7).
  Packages TR-1 to TR-4 make the local path correct and tamper-evident; TR-5
  makes the result authentic.
- **Advisory first.** New enforcing behaviour ships advisory and is promoted by
  the existing ratchet process, as the standing rules require. The exception is
  repairing an existing enforce-mode gate that fails open: that is defect
  correction.
- **No new runtime dependency** in TR-0 to TR-4. TR-5 uses the system OpenSSH
  client and adds no Python dependency; a Sigstore signer is an optional extra.
- **Compatibility.** Public commands and valid-result formats are preserved.
  Artifact schema v1 is not changed; signatures are detached (D-7).
- This plan does not decide the future of the mutation programme. Those
  questions are listed as decisions in TR-8.

## 4. Sequencing and gates

Packages run in this order. Each is one pull request unless noted.

| Order | Package | Contains P0 | Depends on |
|---|---|---|---|
| 1 | TR-0 Baseline harness and confirmations | harness (T2) | — |
| 2 | TR-1 Shipped hook path | E1, E21, T1, E3, E4, E5 | TR-0 |
| 3 | TR-2 Control plane and policy floors | E2 | TR-1 |
| 4 | TR-3 Truthful verification | V2, V3a | TR-1 |
| 5 | TR-4 First-run correctness | G3, P2, P3 | TR-0 |
| 6 | TR-5 Trust root | — | TR-3 |
| 7 | TR-6 Guards | — | TR-1, TR-2 |
| 8 | TR-7 Coordination | — | TR-1 |
| 9 | TR-8 Pipeline and mutation decisions | — | D4 closed |
| 10 | TR-9 Polish | — | — |

TR-4 is independent and small; it may be pulled forward whenever the pipeline
is idle.

**Pipeline cost.** Until TR-8 changes it, every source-changing pull request
re-dispatches most of the 256 mutation shards (measured: 253 for a two-file
change) and only one matrix can run at a time. Plan for up to 17 hours per
source-changing pull request. Tests-only and workflow-only changes measured
zero shards.

**Definition of done for every package**

1. Each fixed finding has a regression test that fails on the merge base and
   passes on the head. The pull request records both runs.
2. Hook-path behaviour is asserted through the end-to-end harness from TR-0, in
   both launch modes, not only by calling a function.
3. CI-pinned `ruff check .`, the full suite under an isolated `XDG_STATE_HOME`,
   pre-commit hooks and `fettle completion validate` pass.
4. The behavior map and user docs named by the package are updated in the same
   pull request.
5. A completion manifest `docs/completion/trust-remediation-<package>.json`
   binds each criterion to a retained command output and the head commit SHA.
6. Before merge, the independent reviewer re-runs each finding's reproduction
   on the pull-request head. Until TR-5 lands, this human-directed re-run is
   the acceptance authority, because completion validation accepts asserted
   text today (finding V8).

Forbidden in every package: lowering thresholds, excluding files or ranges,
skip or xfail, `# pragma: no mutate` without a fingerprint-specific reason, and
edits to `.github/mutation-observed-ledger.json`.

## 5. Designs

### D-1 Edit journal owned by the dispatcher

**Today.** Only `post_edit.main()` appends to `edits.jsonl`
(`post_edit.py:55-62`), only for `.py` files, and only when the lint gate is
enabled. The installed hooks call the dispatcher, which registers
`adapter_check` for post-edit work and never writes the journal. Seven readers
depend on it: `verify_gate.py:718`, `stop_quality_gate.py:149,230`,
`quality_gate.py:421`, `coverage_gate.py:351`, `deploy_gate.py:46,63`,
`post_bash_doc_check.py:54,136`, `session_report.py:37`.

**Design.**

- New module `fettle/edit_journal.py` with `record(session_id, path, tool)`,
  `entries(session_id) -> JournalRead` and `mark_tested(session_id)`.
  `JournalRead` carries the parsed entries and a count of malformed lines.
- The dispatcher calls `record` itself, before check selection, on every
  `PostToolUse` whose tool class mutates files (D-3), for every target path and
  every language. It is not a check, so it cannot be disabled or starved of
  budget.
- Writes are single `O_APPEND` writes of one line. Readers treat a malformed
  line as "unknown", never as "no edits" (fixes E6).
- The journal is no longer the only evidence that code changed. At the first
  event of a session the dispatcher records a session-start record (source
  snapshot digest and effective policy digest) in the session state directory.
  At Stop, a gate needs verification if the journal lists code edits **or** the
  current source snapshot differs from the session-start snapshot in code
  files. If the session-start record is missing, the gate falls back to "the
  tree has code changes relative to HEAD". Deleting the journal therefore no
  longer satisfies the gate.
- All seven readers move to `edit_journal.entries`. The
  `FETTLE_EDIT_TRACKING` override is kept for tests.

### D-2 Project root resolution

**Today.** `resolve_with_provenance` reads `<cwd>/.fettle.toml`
(`config.py:510,524`) and the dispatcher passes the payload `cwd`
(`dispatcher.py:141`). The host documents that `cwd` follows `cd`.

**Design.**

- New `paths.find_project_root(start)`: the nearest ancestor containing `.git`
  (directory or file, so worktrees work); if none, the nearest ancestor
  containing `.fettle.toml`; if none, `start`. Git root is preferred so that a
  permissive `.fettle.toml` dropped into a subdirectory cannot become the root.
- `HookInput` gains `invocation_cwd`. After normalisation the dispatcher sets
  `cwd` to the project root and keeps the original in `invocation_cwd`.
  `HookContext.target_path` resolves relative paths against `invocation_cwd`.
- Directory-level `.fettle.toml` files continue to apply only through the
  existing `_ancestor_dir_layers` path, and only to tighten (D-5).

### D-3 Tool taxonomy and multi-target events

**Today.** `CheckSpec.matches` compares `ctx.tool_name` to exact names
(`dispatcher_types.py:209-218`). Translators map a few names
(`agents/codex.py:27-31`, `agents/opencode.py:35-41`, `agents/gemini.py:31-35`).
Codex multi-file patches get no `file_path` (`agents/codex.py:36-43`).

**Design.**

- New `fettle/agents/tools.py` holds one table per host mapping native tool
  names, case-insensitively, to the canonical names the registry already uses:
  `Bash`, `Write`, `Edit`, `Read`. Added mappings: `NotebookEdit`, `MultiEdit`,
  `multiedit`, `patch`, `apply_patch` to `Edit`; `PowerShell` to `Bash`;
  `Grep`, `Glob` and host equivalents to a new canonical `Search`.
- `HookInput` gains `targets: tuple[Path, ...]`. Translators fill it from
  `file_path`, `path`, `notebook_path`, and every file named in a patch.
- When an event has more than one target, the dispatcher runs the path-scoped
  checks once per target within the same budget; the first block wins.
- An unknown tool name that carries a path key is treated as `Edit` for
  path-protection checks on `PreToolUse` only.
- The Claude Code `PostToolUse` matcher in `hooks/hooks.json` becomes `*`, as
  `PreToolUse` already is, so new tool names reach the dispatcher.

### D-4 Launch isolation and host failure mode

**Today.** The bridge registers `python -m fettle.dispatcher`
(`bridge.py:61-64`, and the OpenCode transport at `bridge.py:97`), which puts
the governed repository first on the import path. `run.sh` exits 0 when no
interpreter is found (`run.sh:45-48`). A crash at import exits 1, which Claude
Code treats as non-blocking.

**Design.**

- Launch with `-P` everywhere: `dispatcher_command()`, the OpenCode transport
  arguments, and `exec "$PYTHON" -P "$SCRIPT_DIR/$TARGET"` in `run.sh`.
- `run.sh` exits 1, not 0, when no interpreter is found, with the existing
  message on stderr. The host then applies its own failure rule.
- Claude Code `PreToolUse` registration sets `"onFailure": "block"`. It is not
  set on `Stop`, where the host documents it has no effect.
- For Codex, Gemini and OpenCode, TR-0 reads each host's documented behaviour
  for hook crash and timeout and records it in `fettle/host-capabilities.json`.
  Where a host offers a fail-closed option it is set; where it does not, the
  capability file and `fettle doctor` say so. Nothing is assumed.

### D-5 Control-plane protection and policy floors

**Today.**

- `config_protect` protects linter configs only (`config_protect.py:19-33`) and
  only for the `Write` and `Edit` tools. `.fettle.toml`, `.fettle-ignore`, the
  `.fettle/` evidence directory and host hook settings are unprotected.
- `CheckSpec.is_enabled` honours `[dispatcher] disabled_checks` and
  `checks.<name>.enabled = false` for every check, including `fail_closed`
  ones (`dispatcher_types.py:220-229`).
- Organisation and team packs merge **under** the repository layer
  (`config.py:513-541`), so the repository overrides them.
- The capsule merge keeps the local value for any key the capsule does not
  name (`policy_capsule.py:260-262`), which lets a child add
  `dispatcher.disabled_checks`.
- A missing or malformed `[extends]` cache is skipped with a stderr line
  (`policy_remote.py:143-159`).

**Design.**

- **Floor layers.** Organisation pack, remote policy and capsule are floors.
  Resolution becomes: `local = defaults + repository`; then each floor is
  applied with the monotonic rule that `policy_capsule.merge_for_child` already
  implements (gate `mode` by rank, gate `enabled` by OR, numeric keys by
  `STRICTER_DIRECTION`, `role` by rank). Keys outside those classes keep
  today's default-and-override behaviour. Release policy tables
  (`assurance.release.<name>`) become a floor class: a repository may only
  narrow the accepted states.
- **Weakening-only keys.** `dispatcher.disabled_checks` and
  `dispatcher.checks.<name>.enabled = false` are never honoured for
  `fail_closed` checks when they come from the repository layer. Under any
  floor layer they are honoured only if the floor itself lists them. Every
  ignored entry is reported, as capsule overrides already are.
- **Remote policy.** A declared `[extends]` whose cache is missing, tampered or
  malformed is a policy load error under `strict=True` (the hook path), with
  the recovery action `fettle policy sync`.
- **Protected control plane.** The protected set is: `.fettle.toml` at the
  root and in ancestor directories, `.fettle-ignore`, the `.fettle/` directory,
  the session state directory, and host hook settings
  (`.claude/settings.json`, `.claude/settings.local.json`, `.codex/hooks.json`,
  `.gemini/settings.json`, the OpenCode plugin file). For file tools the check
  resolves the real path, folds case on case-insensitive file systems, and
  covers creation as well as modification. For shell tools it detects protected
  paths as write targets (redirection, `tee`, `sed -i`, `rm`, `mv`, `cp`,
  `truncate`, `chmod`); this is documented as best effort.
- **Tamper evidence.** At Stop, the effective policy digest is compared with
  the session-start record (D-1). A change without a recorded approval blocks
  in enforce mode and is advisory otherwise. The Assurance Record's
  `policy_integrity` dimension reports this instead of a constant PASS.
- **Recovery.** A policy load error no longer blocks the edit that repairs the
  policy file: when the only target of an `Edit` or `Write` is a policy file
  that currently fails to load, the event is allowed with an advisory.
- **Honest limit.** These measures stop mistakes and leave evidence. Against a
  hostile agent the authority is the verifier, which loads policy from the base
  ref (D-7).

### D-6 Test evidence

**Today.** `run_verify` sets `ok = (returncode == 0)`
(`verify_gate.py:245`), the workspace path does the same
(`verify_gate.py:356`), and the artifact payload is
`{"exit_code", "scope"}` (`verify_gate.py:613-616`). `test_command = "true"`
therefore verifies green. `discover_test_config` reads `test_command` straight
from the repository file (`test_discovery.py:28-37`), bypassing policy layers.

**Design.**

- New module `fettle/test_evidence.py`. For a pytest command (the discovered
  default, or a custom command whose arguments invoke pytest) it adds
  `--junitxml=<path under .fettle/>` and parses the result into
  `{collected, executed, passed, failed, errors, skipped}`, where
  `executed = collected - skipped`.
- For other commands, `[gates.verify] report = "<path>"` names a JUnit XML file
  the command produces. JUnit is the common format across Go, Rust and
  JavaScript runners.
- The artifact payload gains `tests` (the counts, or `null`) and `argv`. Both
  are inside the hashed content.
- Result rules: exit 0 with `executed == 0` is a `violation` with the reason
  "no tests executed". Exit 0 with counts unavailable is `unknown`. The second
  rule ships advisory for one minor release (the gate reports it without
  blocking), then follows the ratchet.
- `test_command` is read through the policy resolver, so floors apply.
- Default scope changes from `impacted` to `full` for the Stop gate's
  acceptance; `impacted` remains available as an explicit, faster choice and is
  labelled as partial in the record (fixes V7).

### D-7 Trust root: signed attestations

**Goal.** A consumer can check that the Assurance Record for commit C was
produced by a verifier identity the agent could not act as, under policy the
agent could not weaken. Today no key, signature or outside anchor exists;
every digest is unkeyed SHA-256 (`evidence.py:199-208`,
`evidence_ledger.py:109`), so a short script can forge a passing record.

**Components.**

1. **Attestation.** A detached signature over a canonical statement. Artifact
   schema v1 is unchanged, which matters because `_ARTIFACT_FIELDS` is an exact
   field set (`evidence.py:36-41`).

   ```json
   {
     "schema_version": "1",
     "kind": "fettle.attestation",
     "subject": {"revision": "<commit>", "tree": "<tree>",
                 "source_snapshot_digest": "sha256:..."},
     "artifact": {"kind": "fettle.assurance", "artifact_digest": "sha256:..."},
     "policy": {"digest": "sha256:...", "base_ref": "<ref>", "base_revision": "<commit>"},
     "verifier": {"principal": "<name>", "environment": "<free text>"},
     "level": "A2",
     "issued_at": "<UTC instant>"
   }
   ```

   The statement is serialised with the existing `canonical_json`. The envelope
   is `{"statement": {...}, "signatures": [{"format": "sshsig",
   "principal": "...", "signature": "<armored>"}]}`, stored at
   `.fettle/attestations/<artifact digest>.json`.

2. **Signer interface.** New `fettle/signing.py` with `Signer.sign(payload,
   namespace)` and `Verifier.verify(payload, signature, trust)`.
   - Default implementation: OpenSSH signatures through `ssh-keygen -Y`, with
     namespace `fettle-attestation`. Keys are ordinary SSH keys in a file or an
     agent. Any CI system can hold one as a secret, and people can sign with a
     key they already use for git.
   - Optional implementation behind an extra: Sigstore keyless signing, for
     providers that issue workload identity tokens.
   - A missing `ssh-keygen` is a `tool_error`, never a pass.

3. **Trust policy.** A `[trust]` table and an OpenSSH `allowed_signers` file:

   ```toml
   [trust]
   allowed_signers = ".fettle/allowed_signers"
   verifier_principals = ["ci-verifier"]
   human_principals = ["milind"]
   required_level = "A2"
   ```

   **Rule: gate policy and trust policy are read from the base ref, not from
   the tree under verification.** `fettle attest verify --base <ref>` loads
   `.fettle.toml` and `allowed_signers` with `git show <base>:<path>`. A change
   to those files is verified under the old policy and is reported as a policy
   change that needs a human-signed approval.

4. **Verifier run.** `fettle attest run` executes where the agent cannot
   write: a CI job on any provider, or a separate local account. It makes a
   clean checkout of commit C, loads policy from the base ref, runs
   verification with full scope, builds the Assurance Record and signs the
   statement.
   - **Key custody requirement (provider-neutral):** the signing key is
     available only to pipeline definitions the change author cannot modify.
   - **Two-job pattern:** job A has no key; it executes project code and
     uploads raw results (JUnit XML, exit codes, snapshot digests). Job B holds
     the key and never executes project code; it validates the raw results
     against base-ref policy, builds the record and signs. A change therefore
     cannot exfiltrate the key.
   - TR-5 ships worked recipes for GitHub Actions and GitLab CI, and a generic
     description for other systems.

5. **Consumers.** `fettle attest verify` exits 0 only if all hold: the
   signature verifies for a principal in `verifier_principals` and the
   namespace; `subject.revision` equals the commit under test;
   `artifact.artifact_digest` matches the record; `policy.digest` equals the
   policy computed from the base ref; the level meets `required_level`.
   `fettle assurance --policy <name>` gains `min_level`. The release gate and
   the required CI check call `attest verify`.

6. **Assurance levels**, recorded in the Assurance Record:

   | Level | Meaning |
   |---|---|
   | A0 | Self-reported; no canonical artifact |
   | A1 | Canonical artifacts bound to source, policy and scope; unsigned (today) |
   | A2 | Independently re-executed and signed by a verifier principal |
   | A3 | A2, plus a signed ledger checkpoint published outside the repository |

7. **Human identity.** Override records (`overrides.py`) and completion
   manifests must carry a signature from a principal in `human_principals`,
   checked against the base-ref `allowed_signers`. Unsigned overrides become
   advisory-only (fixes V5).

8. **Ledger.** `verify_chain` gains a signed checkpoint: terminal hash, record
   count and revision, signed by the verifier. Truncation and history
   replacement are then detectable against the last checkpoint (fixes V9).

**Limits stated plainly.**

- Tests are project code. A hostile change can still make its tests vacuous.
  The layered answer is: the test command comes from base-ref policy; the
  executed-test count may not fall below the base ref's count without a
  human-signed approval; changes to test configuration are reported; and
  mutation of changed lines (a TR-8 decision) detects tests that cannot fail.
- Policy capsules cannot be made authentic against a hostile child on the same
  account, because any key the parent stores is readable by the child. TR-2
  fixes the reproduced loosening paths; the capsule documentation is corrected
  to say "tighten-only against mistakes"; hostile-child resistance needs
  operating-system isolation and is out of scope here.

**Rollout.** (1) `signing.py`, statement format, `attest sign|verify`, tests;
no behaviour change. (2) `attest run`, the two-job recipes, and Fettle's own CI
producing attestations as a non-required check. (3) Assurance levels in the
record, `min_level` in release policy, the check made required on Fettle's own
`main`. (4) Signed overrides, completion manifests and ledger checkpoints.

### D-8 Secret boundary model

**Today.** `run_check` blocks when `_ENV_DUMP` matches anywhere in the command
string (`runtime_secret_guard.py:36,157`), which blocks a commit message that
contains the word "env". `_shell_paths` scans files only when one of six reader
commands is present and only for tokens that `shlex.split` yields
(`runtime_secret_guard.py:106-126`), so `cat creds.txt; true` and
`grep "" creds.txt` pass. A `shlex` error is a block.

**Design.**

- **Command position.** A small splitter breaks a command into simple commands
  on `;`, `&&`, `||`, `|`, `&` and newlines, unwraps `$(...)`, backticks and
  `sh|bash|zsh -c`, and strips leading `VAR=value` words. An environment dump
  is `printenv`, bare `env`, `export -p`, bare `set` or `declare -p|-x` **in
  command position**. `env VAR=x cmd` is analysed as `cmd`.
- **Referenced files.** Any word that names an existing file, after `~` and
  `$HOME` expansion and bounded glob expansion, is content-scanned, whatever
  the command. The reader-command precondition is removed.
- **Protected paths.** New `[secrets] protected_paths` globs, with defaults
  such as `.env`, `.env.*`, `*.pem`, `id_rsa*`, `.netrc`, `.npmrc`, `.pypirc`,
  `~/.aws/credentials` and `~/.ssh/*`. A reference to a protected path blocks
  regardless of content detection.
- **Search tools.** `Search`-class tools (D-3) with a path are scanned like
  `Read`.
- **Unparseable commands.** A tokeniser error no longer blocks by itself. The
  guard falls back to scanning path-like substrings and blocks only on a hit.
- **Patterns.** Add `[A-Z0-9_]*(SECRET|PASSWORD|TOKEN|KEY)[A-Z0-9_]*=` style
  assignments, GitHub fine-grained tokens, Slack tokens, JWTs and URL
  passwords; redact the whole PEM block, not only the header.
- **Documented residue.** Paths computed at run time, scripts written and then
  run, and interpreter one-liners that build a path remain outside what a
  pre-tool text check can see. The docs say so and point to output filtering
  and sandboxing.

## 6. Work packages

### TR-0 Baseline harness and confirmations

Fixes: T2. Confirms: M5. Size: M. No behaviour change.

Changes:

- New `tests/test_installed_hooks_e2e.py`. A fixture creates a scratch git
  repository with redirected `HOME`, `XDG_STATE_HOME` and `XDG_CONFIG_HOME`,
  and obtains the hook command in both launch modes: the command string from
  `hooks/hooks.json` with the plugin root substituted, and
  `fettle.bridge.dispatcher_command()`. Payloads come from
  `tests/fixtures/agent_payloads/conformance.json` plus new fixtures for each
  host's edit, shell, read and stop events.
- Baseline cases that pass today and must keep passing: a protected linter
  config edit is blocked in enforce mode from the repository root; `rm -rf` is
  blocked in enforce mode; `cat` of a file containing a detected key is
  blocked; an unreadable policy file blocks.
- Host failure-mode table: read the Codex, Gemini and OpenCode hook
  documentation for crash, timeout and working-directory behaviour and record
  the findings, with the date read, in `fettle/host-capabilities.json`. Also
  record the input field names of the Claude Code `PowerShell` and
  `NotebookEdit` tools, which D-3 needs.
- M5 confirmation: on a documentation-only draft pull request, let
  `mutation evidence` complete, add an ordinary label, and record the check
  runs for the head SHA. Close the finding or move it to TR-8.

Acceptance: the harness runs in CI on every supported Python; the host table is
complete or lists what could not be determined; M5 has a recorded outcome.

### TR-1 Shipped hook path

Fixes: E1, E21, T1, E3, E4, E5 (P0); E6, E11, E23 (P1); E22 (P2). Size: L.
Designs: D-1, D-2, D-3, D-4.

| ID | Finding | Marker |
|---|---|---|
| E1 | With the tests, verify or coverage gate enabled, the installed hooks never record edits, so those Stop gates always allow | R |
| E21 | Twelve modules hold two copies of their logic, a script `main()` and a dispatcher `run_check()` | R |
| T1 | Guard tests drive the script copy; in `destructive_guard.run_check`, flipping `mode == "enforce"` survives the mutation run | R |
| E3 | Policy is read from the payload `cwd`; a subdirectory gets defaults | R |
| E4 | Edit-tool variants skip the edit gates | R, S |
| E5 | `python -m fettle.dispatcher` imports from the governed repository first | R |
| E6 | A malformed payload or journal line turns a block into an allow | S |
| E11 | Enforce-mode gates that are never "required" fail open on a crash | S |
| E22 | A missing interpreter exits 0; host crash and timeout are non-blocking | C |
| E23 | The Claude Code `PowerShell` tool is not mapped, so shell guards never see it | C |

Changes:

- `fettle/edit_journal.py` (new), dispatcher integration and reader migration
  as in D-1.
- `fettle/paths.py`: add `find_project_root`. `fettle/dispatcher_types.py`:
  add `invocation_cwd` and `targets` to `HookInput`; `target_path` resolves
  against `invocation_cwd`. `fettle/dispatcher.py:main`: resolve the root after
  normalisation and before `load_config`.
- `fettle/agents/tools.py` (new) and the four translators as in D-3;
  per-target fan-out in the dispatcher loop; `hooks/hooks.json` matcher.
- `fettle/bridge.py:dispatcher_command`, the OpenCode transport and
  `fettle/run.sh` as in D-4; `"onFailure": "block"` in the Claude Code
  `PreToolUse` registration.
- **One entry point per check.** For each of the twelve modules
  (`commit_message`, `config_protect`, `destructive_guard`, `lean_sniffers`,
  `loop_detect`, `lsp_server`, `mcp_trust_gate`, `post_bash_doc_check`,
  `post_edit`, `quality_gate`, `scope_creep`, `stop_quality_gate`), `main()`
  becomes a thin wrapper that builds a `HookContext` and calls `run_check`.
  `lsp_server` is excluded if its `main()` is the server entry point; the
  package confirms this first.
- `fettle/dispatcher.py:116-125`: an unparseable or non-object payload is a
  block when the raw input names a `PreToolUse` event, and a traced allow
  otherwise.
- `fettle/dispatcher_registry.py`: give `worklog`, `post_bash_doc_check`,
  `boundary_rules`, `provenance_gate` and `runtime_output_guard` their
  `policy_gates`, so enforce mode makes them required.

Tests:

- Harness, both launch modes: after a `PostToolUse` edit of a code file with
  the verify gate in enforce mode, Stop blocks; after deleting the journal,
  Stop still blocks; from a subdirectory `cwd`, a protected edit is still
  blocked; `NotebookEdit`, a Codex two-file patch and OpenCode `multiedit` on a
  protected file are blocked; a repository-local `fettle/dispatcher.py` does
  not change the decision.
- For each migrated module, the existing script-level tests keep passing and a
  new test calls the dispatcher path for the enforce and advisory branches.
- A journal with one malformed line yields "unknown", not allow.

Docs: behavior map rows for hook guards; `docs/CAPABILITIES.md` host notes.

Risks: readers of the journal are many; migrate them in one commit with the
harness as the safety net. Changing `cwd` to the root could affect checks that
assumed the invocation directory; the harness subdirectory cases cover this.

### TR-2 Control plane and policy floors

Fixes: E2 (P0); E12, E15, E17, E18, V6, G8, and the reproduced part of G4 (P1,
P2). Size: L. Design: D-5.

| ID | Finding | Marker |
|---|---|---|
| E2 | `.fettle.toml`, session state and host settings are unprotected; `disabled_checks` disables fail-closed checks | R |
| E12 | Config protection misses new files, symlinks, case variants and relative paths; its block message explains how to disable it | S |
| E15 | A corrupt policy file blocks the edit that would repair it | S |
| E17 | Loop, scope and lean state are written under the install directory; the trace is global across repositories | S |
| E18 | `[dispatcher]` keys are honoured but absent from the schema | S |
| V6 | The repository layer overrides organisation release policy | S, C |
| G8 | Remote policy fails open on cache miss or malformed `[extends]` | S, C |
| G4 | A child's local `disabled_checks` survives the capsule merge | S, C |

Changes:

- `fettle/config.py:resolve_with_provenance`: apply floors as in D-5; make a
  declared but unavailable `[extends]` a strict load error.
- `fettle/policy_capsule.py`: extract the monotonic walk for reuse; treat the
  weakening-only keys as in D-5.
- `fettle/dispatcher_types.py:CheckSpec.is_enabled`: refuse repository-layer
  disabling of `fail_closed` checks; needs the provenance of the key, so
  `load_config` exposes which layer set `dispatcher.*`.
- `fettle/config_protect.py`: the protected control-plane set, real-path and
  case handling, creation coverage, shell write-target detection; remove the
  "Disable:" hint from the block message.
- `fettle/config_schema.py`: add the `[dispatcher]` table.
- `fettle/scope_creep.py:66-69`, `loop_detect.py:71-74`,
  `lean_sniffers.py:468-471`: use `config.state_dir`. Trace records gain the
  project root path so `explain` and `report` can filter by repository.
- `fettle/assurance.py:_policy_integrity_dimension`: report the session
  comparison from D-5.

Tests: harness cases for each bypass in E2 and E12; a floor matrix test
(organisation enforce versus repository advisory, release policy narrowing,
capsule plus local `disabled_checks`); remote policy unavailable blocks with
the recovery action; state files land under the redirected state directory.

Docs: `docs/CONFIG.md` (floors, `[dispatcher]`, `[trust]` placeholder),
`docs/MULTI-AGENT.md` (capsule guarantee wording).

Risks: floors change resolution for anyone using organisation packs as
defaults. Mitigation: only the listed key classes become floors, and
`fettle config --explain` shows which layer won and why.

### TR-3 Truthful verification

Fixes: V2, V3a (P0); V4, V7, V10, V11, V13, E8, P13 (P1, P2). Size: L.
Design: D-6.

| ID | Finding | Marker |
|---|---|---|
| V2 | Stop gates read the stamp's unhashed `ok`; editing it turns red to green | R |
| V3a | Exit code 0 is "passed" even with zero tests or `test_command = "true"` | R |
| V4 | The assurance `ci` dimension accepts a stamp for an earlier commit | S, C |
| V7 | Default scope `impacted` passes while another test file fails | S |
| V10 | `fettle assurance` raises on real trace entries because `ts` is a float | S, C |
| V11 | `policy_integrity` and `scope` are constant PASS; deleting a red CI stamp gives "not applicable" | S, C |
| V13 | `baseline create` writes no fingerprints; all-skipped CI runs count as green | S |
| E8 | The "tests ran" marker is set by loose command patterns before the command runs | S, C |
| P13 | `fettle brief` reports a stale verify as green | S, C |

Changes:

- `fettle/verify_gate.py:run_check`: the gate reads `stamp["ok"]` at line 795
  and checks only validity at line 874. Use the `EvidenceValidationResult`
  from `validate_canonical_evidence` and require `result_state` PASS; stop
  reading `stamp["ok"]` and the per-workspace `ok`. The helper
  `_canonical_evidence_validity` (line 710) is removed.
- `fettle/ci_gate.py`: the same change for the CI Stop gate, which reads
  `stamp["ok"]` at lines 650 and 692 and checks only validity at line 663;
  `tests/test_ci_gate.py:481` is updated with the helper.
- `fettle/test_evidence.py` (new), `run_verify` and
  `_run_workspace_verification` as in D-6; `test_discovery.py` reads through
  the resolver.
- `fettle/assurance.py:_ci_dimension`: compare the stamp's `sha` with the
  assessed commit; a mismatch is UNKNOWN. A retained failing push record with
  no CI stamp is UNKNOWN, not NOT_APPLICABLE.
- `fettle/assurance.py:266-278`: project trace entries to canonical-safe fields
  before digesting; convert `ts` to an integer.
- `fettle/quality_gate.py`: remove `TEST_PATTERNS` stamping (lines 44-61,
  335-357). "Tested" means a valid verify artifact for the current source
  snapshot.
- `fettle/brief.py:60-77`: report verify and CI state through the same
  validators the gates use.
- `fettle/baseline.py:64` and `fettle/ci_gate.py:66,74`: write fingerprints;
  treat an all-skipped run as non-green.

Tests: stamp-edit and CI-stamp-edit harness cases; `true`, skip-all and
zero-collection cases; a stale-CI case; assurance on a trace with real entries;
brief after a breaking edit.

Docs: `docs/evidence-artifact-contract.md` payload section; README trust-loop
wording stays, now backed by tests.

Risks: recording counts changes results for repositories with custom test
commands. Mitigation: the "counts unavailable" rule ships advisory first.

### TR-4 First-run correctness

Fixes: G3, P2, P3 (P0); P1, P4, P5, P6 (P1, P2). Size: M. Design: D-8
(command-position part only; the rest is TR-6).

| ID | Finding | Marker |
|---|---|---|
| G3 | The secret guard blocks ordinary commands containing the word `env`, an unbalanced apostrophe, or a read of a missing file | R |
| P2 | `init --profile ... --dry-run` writes the config, and overwrites with `--force` | R |
| P3 | `fettle explain` raises `IndexError` after a failed verify | R |
| P1 | `fettle demo` detects with a private syntax-tree walk, not the engine | R |
| P4 | A missing Semgrep discards Ruff findings | S, C |
| P5 | `doctor` says "healthy" with tools missing and a malformed config | S |
| P6 | The hook path runs plain `ruff check`, not the bundled rules | S |

Changes:

- `fettle/runtime_secret_guard.py:run_check`: command-position environment
  detection and the tokeniser fallback from D-8; a read of a non-existent file
  is allowed.
- `fettle/cli.py:636-652`: compute the config, and under `--dry-run` print the
  intended write instead of calling `write_config`.
- `fettle/explain.py:61`: guard the empty-findings case; describe a verify
  failure as a verify failure.
- `fettle/demo.py:33-44`: replace `_broad_handler_line` with a call to the
  scan engine on the fixture; keep the demo offline and deterministic. If the
  engine path needs Semgrep, the demo uses the Ruff rule that flags a broad
  exception and says which engine ran.
- `fettle/cli.py:120-135`: print findings before tool errors; keep exit 2.
- `fettle/doctor.py`: required-capability failures make the summary
  "degraded", not "healthy".
- `fettle/adapters/python_adapter.py:49-60`: pass the bundled Ruff config, as
  `fettle check` does.

Tests: the audit's false-positive command list; a dry-run that leaves the tree
byte-identical; explain after a red verify; demo output derived from the
engine; check output with Semgrep absent.

### TR-5 Trust root

Fixes: V1, V3b, V5, V8, V9, and the rest of G4. Size: L, in the four rollout
steps of D-7; each step is its own pull request. Design: D-7.

| ID | Finding | Marker |
|---|---|---|
| V1 | No key, signature or outside anchor; a short script forges a passing record and a "verified" ledger | S, C |
| V3b | Tests can be neutralised from inside the repository | S |
| V5 | Overrides are self-grantable | S, C |
| V8 | Completion validation passes on asserted text; no manifests means complete | S, C |
| V9 | Ledger truncation reads "verified"; a fabricated checkpoint replaces history | S, C |

Changes: `fettle/signing.py`, `fettle/attest.py` and a `fettle attest`
command group (`sign`, `verify`, `run`); `[trust]` in the config schema;
`min_level` in release policy evaluation (`assurance.py:486`); signature checks
in `overrides.py` and `completion.py`; signed checkpoints in
`evidence_ledger.py`; `completion.py:226` treats "no manifests" and "no
required criteria" as not complete, and compares `revision` with a real commit.
CI recipes under `docs/` for GitHub Actions and GitLab CI.

Tests: sign and verify round trip; a changed statement, wrong namespace,
unknown principal, wrong revision, wrong policy digest and insufficient level
each fail; policy loaded from the base ref ignores a weakened working-tree
policy; the audit's forgery script no longer yields a passing
`attest verify`; an unsigned override is advisory-only.

Acceptance: Fettle's own `main` requires a verified A2 attestation.

### TR-6 Guards

Fixes: G1, G2, G9 (P1); G5, G6, G7, G10, G11, G12, G13, G14, G16 (P2).
Size: L. Design: D-8.

| ID | Finding | Where | Marker |
|---|---|---|---|
| G1 | Secret reads through other commands, globs, `~`, a trailing `;`, and search tools pass | `runtime_secret_guard.py:106-126` | R, S |
| G2 | Common secret formats are not detected; PEM bodies survive redaction | `runtime_secret_guard.py:15-35` | R, S |
| G9 | The subagent hook reads any file named by `injection_file` | `hooks/subagent_inject.js:67-70` | S, C |
| G5 | Destructive guard: newline and safe-prefix holes; missing equivalents; false blocks | `destructive_guard.py:19-58` | R, S |
| G6 | Spawn gate misses flag-first and wrapped launches | `agent_spawn_gate.py:28-35` | S |
| G7 | MCP allowlist writable from the shell; registration ungated | `mcp_trust_gate.py:17-27,164` | S |
| G10 | Role escapes; `--role` inert by default | `policy_capsule.py:296-302`, `authorship_gate.py:60-62` | S |
| G11 | Output guard sees four tool types only | `runtime_output_guard.py:31-49` | S |
| G12 | Release and deploy gate logic errors | `release_gate.py:41-45`, `deploy_gate.py:44-58` | S |
| G13 | Bash audit can log secrets; hash covers 100 bytes | `bash_audit.py:48,58-61` | S |
| G14 | Runners pass task text without an argument separator | `runners/claude.py:38` and peers | U |
| G16 | `fettle review` posts source to a repository-configured endpoint without a host check | `review.py:45-72` | U |

Changes: the rest of D-8 in `runtime_secret_guard.py`; the destructive guard
uses the same command splitter and matches in command position;
`subagent_inject.js` restricts `injection_file` to the repository and to
non-protected paths; the MCP allowlist and role settings join the protected
control plane from TR-2; G14 and G16 are confirmed first, then fixed or closed.

Tests: the audit's bypass matrices for the secret boundary and the destructive
guard become parametrised harness tests, with expected block or allow per row
and the documented residue marked as such.

### TR-7 Coordination

Fixes: C1 (P1); C2, C3, C4, C5 (P2). Size: M.

| ID | Finding | Where | Marker |
|---|---|---|---|
| C1 | `topology apply` creates worktrees under `.fettle/worktrees`, which item discovery and `check --all --fix` then scan | `spec_model.py:36-38`, `worktrees.py:23`, `cli.py:104-111` | S, C |
| C2 | Claims are not owner-checked; a corrupt file wipes claims | `work_items.py:244-266` | S |
| C3 | The claims gate ignores scope | `claims_gate.py:39-41` | S |
| C4 | Status and reports never attribute activity to workers | `topology_apply.py:69,135`, `session_report.py:100` | S |
| C5 | Plans are not session-bound | `session_plan.py:134-152` | S |

Changes: add `.fettle` to the scanners' skip set and make `check --fix`
honour it; claims carry and check the owning session; the claims gate compares
the edited path with the claimed item's scope; completion reports are written
to the common git directory so the orchestrator can read them; plan ticks
record the session.

### TR-8 Pipeline and mutation decisions

Fixes: M4 (P1); M6, M7, M9, M12, M15 (P2). Decides: D1 to D5. Size: M plus
decisions. Starts after D4 closes.

| ID | Finding | Where | Marker |
|---|---|---|---|
| M4 | While one advisory matrix runs, every other pull request's admission gate fails, including zero-scope ones | `mutation-pr.yml:27-39`, `mutation_advisory_runs.py:24-39` | S, C |
| M6 | Fingerprints differ between Python 3.12 and 3.13 or later | `mutation_test.py:4030-4037` | S |
| M7 | Admission projection is keyed by shard index and the minute ceiling is not enforced | `mutation_test.py:3762-3922,5401-5430` | R, S |
| M9 | Mutation runs tests in Fettle's own environment | `mutation_test.py:53-65` | U |
| M12 | A weekly schedule launches 256 jobs | `mutation.yml:6,462-498` | U |
| M15 | The release job holding signing permissions also runs tests and unhashed installs | `release.yml:89-106,182` | U |

Changes: move the serialisation guard after scope is known and skip it for
zero-shard pull requests; pin the fingerprint representation so it does not
depend on `ast.dump`; confirm and then fix M9, M12 and M15.

Decisions to bring to the owner, each with measured options:

| ID | Decision |
|---|---|
| D1 | Should the mutation check fail on weak tests in changed lines, once message-string mutants are filtered? Today `passed` ignores the score |
| D2 | Should the mutation engine remain in its own mutation scope? It takes about 84% of ledger runtime |
| D3 | Keep or archive the incident-specific calibration and capacity machinery |
| D4 | After three full runs: record the result, or propose a baseline and ratchet |
| D5 | Partition stability: a small edit changes 194 of 256 shard manifests |

### TR-9 Polish

Fixes the P3 items: hook latency (seven interpreter starts per event in
`run.sh`), path heuristics for directories named `test` or `gen`, dead modules
(`event.py`, `cache.py`), the secret guard's missing size cap, telemetry
opt-in forgery, `fettle mutation` on Windows (`fcntl` import in
`mutation_baseline.py:14`), fingerprint collisions, fractional-minute
accounting, the overwritten mutation step summary, shared workflow concurrency
group, survivor baseline clean-up, flaky kills, internal codes in help text,
`.fettle/` not git-ignored by `init`, bare "tool not found" messages for
non-Python edits, documentation navigation, synchronous `spawn`, the thin
work-item model, and cross-machine sharing. Each is confirmed against the code
before it is changed. Size: S each; L in total.

Also in TR-9: triage of the roughly 10,300 non-message mutation survivors in
the trust-critical modules (`verify_gate` 125, `completion` 92, `assurance` 94,
`mcp_trust_gate` 84, `dispatcher` 82), using the D4 run 1 report.

## 7. Finding register

Priority: P0 fix first; P1 trust; P2 hardening; P3 polish; V verify first.

| ID | Priority | Package | | ID | Priority | Package |
|---|---|---|---|---|---|---|
| E1 | P0 | TR-1 | | V1 | P1 | TR-5 |
| E21 | P0 | TR-1 | | V3b | P1 | TR-5 |
| T1 | P0 | TR-1 | | V4 | P1 | TR-3 |
| T2 | P0 | TR-0 | | V5 | P1 | TR-5 |
| E2 | P0 | TR-2 | | V6 | P1 | TR-2 |
| E3 | P0 | TR-1 | | V7 | P1 | TR-3 |
| E4 | P0 | TR-1 | | V8 | P1 | TR-5 |
| E5 | P0 | TR-1 | | V9 | P1 | TR-5 |
| V2 | P0 | TR-3 | | V10 | P1 | TR-3 |
| V3a | P0 | TR-3 | | G1 | P1 | TR-6 |
| G3 | P0 | TR-4 | | G2 | P1 | TR-6 |
| P2 | P0 | TR-4 | | G4 | P1 | TR-2, TR-5 |
| P3 | P0 | TR-4 | | G8 | P1 | TR-2 |
| M5 | V | TR-0 | | G9 | P1 | TR-6 |
| E6 | P1 | TR-1 | | P1 | P1 | TR-4 |
| E8 | P1 | TR-3 | | P4 | P1 | TR-4 |
| E11 | P1 | TR-1 | | P13 | P1 | TR-3 |
| E12 | P1 | TR-2 | | C1 | P1 | TR-7 |
| E23 | P1 | TR-1 | | M4 | P1 | TR-8 |
| E15 | P2 | TR-2 | | G5–G7 | P2 | TR-6 |
| E17 | P2 | TR-2 | | G10–G14, G16 | P2 | TR-6 |
| E18 | P2 | TR-2 | | M6, M7, M9, M12, M15 | P2 | TR-8 |
| E22 | P2 | TR-1 | | P5, P6 | P2 | TR-4 |
| V11 | P2 | TR-3 | | C2–C5 | P2 | TR-7 |
| V13 | P2 | TR-3 | | all P3 items | P3 | TR-9 |

Remaining P2 items not owned above are scheduled as follows: E7 (blocks
missing from the audit trail), E9 (budget behaviour under load), E13
(quality-gate warnings not reaching the agent) and E14 (TDD gate path rules)
go with TR-1 if they fit the harness, otherwise TR-9; V12 (unbound inputs)
goes with TR-5; P8 (hard dependencies), P10 (test discovery beyond pytest
config), P12 (user-global hooks), P14 (spec coverage from a marker) and P17
(CI coverage of Windows, the installed wheel and the other hosts) go with
TR-9; T3 (survivor triage) is in TR-9.

## 8. Verification strategy

- **End-to-end first.** The TR-0 harness executes the registered hook command.
  A fix is not accepted on a unit test alone when the finding was on the hook
  path.
- **Red then green.** Each regression test is run against the merge base and
  the head; both outputs go into the pull request.
- **Reproductions become tests.** The audit's bypass matrices are kept as
  parametrised cases with an expected outcome per row.
- **Mutation, narrowly.** For each package, run a narrow mutation replay of
  the changed line ranges, capped at 60 minutes, and report survivors. Do not
  weaken anything to remove them.
- **Independent re-run.** The reviewer re-runs each reproduction on the
  pull-request head before merging.
- **Claims as tests.** `tests/test_doc_claims.py` gains one executable
  predicate per README sentence in section 9, each driving the harness.

## 9. README claims and the package that makes each true

| README sentence | Made true by |
|---|---|
| "Catch mistakes while the agent still has context" on every supported edit tool | TR-1 |
| "Fail-visible semantics: missing tools, stale artifacts, malformed reports, timeouts, and crashes remain non-pass outcomes" | TR-1, TR-3 |
| "Verify independently. `fettle verify` runs repository tests and binds the result" | TR-3 (counts), TR-5 (independence) |
| "Prove what passed before the change ships" | TR-3, TR-5 |
| "Delegated work may tighten constraints, not silently loosen them" | TR-2 (reproduced paths); wording aligned with D-7 limits |
| "Digest-pinned central policy" | TR-2 |
| "Pre-tool secret access blocking on all four hosts" | TR-4, TR-6 |
| "Tamper-evident ledger" | TR-5 |
| "Missing evidence does not become success" | TR-3, TR-5 |
| `fettle demo` "detects it" | TR-4 |

## 10. Risks

| Risk | Mitigation |
|---|---|
| Each source-changing pull request costs a long mutation matrix | Packages are sized as single pull requests; TR-0 and tests-only work measured zero shards; TR-8 brings the pipeline decisions |
| Floors change policy resolution for existing users | Only listed key classes become floors; `config --explain` shows the winning layer |
| Recording test counts breaks custom test commands | Counts-unavailable ships advisory for one minor release |
| `-P` or `onFailure` behaves differently on a host version | TR-0 records host behaviour before TR-1 changes registration; `doctor` reports the host version |
| OpenSSH is missing on a user's machine | Signing is needed only where attestations are produced or verified; absence is a `tool_error` with a clear action, and local A1 use is unaffected |
| The signing key is exposed to project code | Two-job pattern: the job that holds the key never executes project code |
| A package's own completion check passes vacuously | The reviewer's independent re-run is the acceptance authority until TR-5 |

## 11. Completion

Each package closes with its manifest under `docs/completion/`, criteria of
type `command` bound to the head commit, and the reviewer's re-run recorded in
the pull request. The program closes when TR-0 to TR-8 are merged, the README
claim predicates in section 9 pass, and Fettle's own `main` requires a
verified A2 attestation.
