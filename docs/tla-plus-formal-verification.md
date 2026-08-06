# TLA+ Formal Verification Plan for Fettle

## Overview

This document defines five TLA+ specifications for Fettle's critical subsystems,
ordered from highest to lowest verification value. Each work package (WP) is
self-contained: it names the invariants to prove, provides the TLA+ spec, and
lists the model-checking parameters.

**Why TLA+:** Fettle's correctness guarantees depend on protocol-level properties
(monotonicity, fail-closed, mutual exclusion, temporal ordering) that unit tests
cannot exhaustively cover. TLA+ model-checking explores all reachable states,
finding violations that require specific interleavings or edge-case sequences.

---

## WP-1: Policy Capsule Delegation Protocol

**Priority:** Critical  
**Risk mitigated:** A child agent escapes inherited policy constraints  
**Source:** `fettle/policy_capsule.py`, `fettle/capsule_guard.py`, `fettle/spawn.py`  
**Estimated spec size:** ~120 lines TLA+  

### Properties to Verify

| ID | Property | Type | Description |
|----|----------|------|-------------|
| S1 | MonotonicStrictness | Safety | A child's effective policy is always >= strict as its parent's on every key |
| S2 | DepthBound | Safety | Lineage depth never exceeds MAX_LINEAGE_DEPTH (16) |
| S3 | TamperDetection | Safety | Any modification to the capsule body after writing -> all tool calls blocked |
| S4 | FailClosed | Safety | Env asserts capsule + (missing OR unreadable OR version skew) -> block |
| S5 | PlumbingIsolation | Safety | Machine-local plumbing keys never propagate from parent to child |
| L1 | ValidSpawnSucceeds | Liveness | A spawn with valid policy + depth < 16 always produces a usable capsule |
| L2 | NoSpuriousBlock | Liveness | A verified, untampered capsule never triggers capsule_guard block |

### TLA+ Specification

```tla
------------------------------ MODULE PolicyCapsule ------------------------------
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    MaxDepth,        \* = 16 (lineage cap)
    Agents,          \* model set: {parent, child1, child2, grandchild}
    PolicyKeys,      \* model set: {mode_a, mode_b, coverage_threshold}
    ModeValues,      \* ordered: {off, advisory, enforce}
    NumericValues    \* directed thresholds: subset of Int

VARIABLES
    capsules,        \* agent -> capsule record (policy, digest, lineage)
    effective,       \* agent -> resolved effective policy
    blocked,         \* agent -> BOOLEAN (capsule_guard verdict)
    tampered,        \* capsule paths that an adversary has modified
    pc              \* process counter for agent lifecycle

vars == <<capsules, effective, blocked, tampered, pc>>

-----------------------------------------------------------------------------
\* Mode strictness ladder (higher = stricter)
ModeRank(m) == CASE m = "off"      -> 0
               []   m = "advisory"  -> 1
               []   m = "enforce"   -> 2

\* Monotonic merge: child gets max(parent, local) per key
MonotonicMerge(parent_policy, local_policy) ==
    [key \in PolicyKeys |->
        IF key \in {"mode_a", "mode_b"} THEN
            \* Mode keys: higher rank wins
            IF ModeRank(local_policy[key]) > ModeRank(parent_policy[key])
            THEN local_policy[key]
            ELSE parent_policy[key]
        ELSE
            \* Numeric thresholds (coverage): max wins (stricter = higher)
            IF local_policy[key] > parent_policy[key]
            THEN local_policy[key]
            ELSE parent_policy[key]
    ]

\* Digest computation (abstract: identity function on policy)
Digest(policy) == policy

-----------------------------------------------------------------------------
\* Actions

Init ==
    /\ capsules = [a \in Agents |-> IF a = "parent" THEN
                    [policy |-> [key \in PolicyKeys |-> "advisory"],
                     digest |-> Digest([key \in PolicyKeys |-> "advisory"]),
                     lineage |-> <<>>]
                   ELSE [policy |-> <<>>, digest |-> <<>>, lineage |-> <<>>]]
    /\ effective = [a \in Agents |-> [key \in PolicyKeys |-> "off"]]
    /\ blocked = [a \in Agents |-> FALSE]
    /\ tampered = {}
    /\ pc = [a \in Agents |-> "idle"]

\* Parent writes a capsule for a child
WriteCapsule(parent, child) ==
    /\ pc[parent] = "ready"
    /\ pc[child] = "idle"
    /\ Len(capsules[parent].lineage) < MaxDepth
    /\ LET parent_cap == capsules[parent]
           new_lineage == Append(parent_cap.lineage, parent)
       IN capsules' = [capsules EXCEPT ![child] =
              [policy |-> parent_cap.policy,
               digest |-> Digest(parent_cap.policy),
               lineage |-> new_lineage]]
    /\ pc' = [pc EXCEPT ![child] = "capsule_written"]
    /\ UNCHANGED <<effective, blocked, tampered>>

\* Adversary tampers with a written capsule
Tamper(agent) ==
    /\ pc[agent] = "capsule_written"
    /\ tampered' = tampered \cup {agent}
    /\ UNCHANGED <<capsules, effective, blocked, pc>>

\* Child verifies and merges (capsule_guard + merge_for_child)
VerifyAndMerge(agent, local_policy) ==
    /\ pc[agent] = "capsule_written"
    /\ LET cap == capsules[agent]
           digest_ok == (agent \notin tampered) /\ (cap.digest = Digest(cap.policy))
           lineage_ok == Len(cap.lineage) <= MaxDepth
       IN IF ~digest_ok \/ ~lineage_ok
          THEN \* Fail closed
               /\ blocked' = [blocked EXCEPT ![agent] = TRUE]
               /\ pc' = [pc EXCEPT ![agent] = "blocked"]
               /\ UNCHANGED <<capsules, effective, tampered>>
          ELSE \* Verified: merge monotonically
               /\ effective' = [effective EXCEPT ![agent] =
                      MonotonicMerge(cap.policy, local_policy)]
               /\ pc' = [pc EXCEPT ![agent] = "ready"]
               /\ UNCHANGED <<capsules, blocked, tampered>>

\* Depth-exceeded spawn attempt (must fail)
SpawnAtMaxDepth(parent, child) ==
    /\ pc[parent] = "ready"
    /\ Len(capsules[parent].lineage) >= MaxDepth
    /\ pc' = [pc EXCEPT ![parent] = "spawn_rejected"]
    /\ UNCHANGED <<capsules, effective, blocked, tampered>>

-----------------------------------------------------------------------------
\* Invariants (Safety Properties)

\* S1: Monotonic strictness — effective child policy >= parent on every key
MonotonicStrictness ==
    \A agent \in Agents :
        pc[agent] = "ready" /\ capsules[agent].lineage # <<>> =>
            \A key \in PolicyKeys :
                LET parent == capsules[agent].lineage[Len(capsules[agent].lineage)]
                IN pc[parent] = "ready" =>
                   ModeRank(effective[agent][key]) >= ModeRank(effective[parent][key])

\* S2: Lineage depth never exceeds MaxDepth
DepthBound ==
    \A agent \in Agents : Len(capsules[agent].lineage) <= MaxDepth

\* S3: Tampered capsule -> agent is blocked
TamperDetection ==
    \A agent \in Agents :
        (agent \in tampered /\ pc[agent] \in {"blocked", "ready"}) =>
            blocked[agent] = TRUE

\* S4: Fail closed on verification failure
FailClosed ==
    \A agent \in Agents :
        (pc[agent] = "blocked") => blocked[agent] = TRUE

\* L2: Untampered + valid -> never blocked
NoSpuriousBlock ==
    \A agent \in Agents :
        (agent \notin tampered /\ pc[agent] = "ready") =>
            blocked[agent] = FALSE

-----------------------------------------------------------------------------
\* Temporal properties

\* L1: Valid spawn eventually succeeds
ValidSpawnSucceeds ==
    \A parent, child \in Agents :
        (pc[parent] = "ready" /\ Len(capsules[parent].lineage) < MaxDepth) ~>
            (pc[child] \in {"ready", "blocked"})

-----------------------------------------------------------------------------
Next ==
    \E parent, child \in Agents :
        \/ WriteCapsule(parent, child)
        \/ Tamper(child)
        \/ \E local \in [PolicyKeys -> ModeValues \cup NumericValues] :
               VerifyAndMerge(child, local)
        \/ SpawnAtMaxDepth(parent, child)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
```

### Model-Checking Parameters

| Parameter | Value |
|-----------|-------|
| Agents | `{"parent", "child1", "child2", "grandchild"}` |
| MaxDepth | `3` (scaled down from 16 for tractability — same logic) |
| PolicyKeys | `{"mode_a", "mode_b", "coverage"}` |
| ModeValues | `{"off", "advisory", "enforce"}` |
| NumericValues | `{50, 70, 90}` |

### Deliverables

1. `specs/tla/PolicyCapsule.tla` — the spec above
2. `specs/tla/PolicyCapsule.cfg` — TLC model config
3. `specs/tla/PolicyCapsuleTest.tla` — concrete scenarios (counterexample seeds)

---

## WP-2: Work Item Claims & Topology Coordination

**Priority:** High  
**Risk mitigated:** Two agents edit the same files concurrently (semantic merge conflict)  
**Source:** `fettle/work_items.py`, `fettle/topology.py`, `fettle/worktrees.py`  
**Estimated spec size:** ~150 lines TLA+  

### Properties to Verify

| ID | Property | Type | Description |
|----|----------|------|-------------|
| S1 | NoDuplicateClaim | Safety | No two live sessions can hold the same item simultaneously |
| S2 | DisjointParallelism | Safety | Items approved for parallel execution have non-overlapping footprints |
| S3 | UnknownScopeConservative | Safety | An item with no scope conflicts with all other items |
| S4 | ClaimBeforeWork | Safety | No edits to files in an item's scope without holding its claim |
| L1 | StaleClaims Reclaimable | Liveness | A claim whose worktree is gone can always be taken by another session |
| L2 | ReleaseSucceeds | Liveness | A session that releases always succeeds (no deadlock) |

### TLA+ Specification

```tla
------------------------------ MODULE WorkItemClaims ------------------------------
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    Items,          \* {"item-a", "item-b", "item-c"}
    Sessions,       \* {"sess-1", "sess-2", "sess-3"}
    Worktrees,      \* {"wt-1", "wt-2", "wt-3"}
    Files           \* {"file-x.py", "file-y.py", "file-z.py"}

VARIABLES
    claims,         \* item -> {session, worktree} | NULL
    alive,          \* worktree -> BOOLEAN (simulates worktree existence)
    scopes,         \* item -> SUBSET Files (declared scope)
    footprints,     \* item -> SUBSET Files (expanded footprint)
    edits,          \* session -> SUBSET Files (files edited so far)
    locked,         \* BOOLEAN (flock simulation)
    pc              \* session -> state

vars == <<claims, alive, scopes, footprints, edits, locked, pc>>

NULL == [session |-> "none", worktree |-> "none"]

-----------------------------------------------------------------------------
Init ==
    /\ claims = [i \in Items |-> NULL]
    /\ alive = [w \in Worktrees |-> TRUE]
    /\ scopes = [i \in Items |-> {}]  \* initially no scope (conservative)
    /\ footprints = [i \in Items |-> Files]  \* unknown = all files
    /\ edits = [s \in Sessions |-> {}]
    /\ locked = FALSE
    /\ pc = [s \in Sessions |-> "idle"]

\* Session declares scope for an item (enables parallelism)
DeclareScope(item, scope_files) ==
    /\ scopes' = [scopes EXCEPT ![item] = scope_files]
    /\ footprints' = [footprints EXCEPT ![item] = scope_files]
    /\ UNCHANGED <<claims, alive, edits, locked, pc>>

\* Acquire the advisory lock
AcquireLock(session) ==
    /\ ~locked
    /\ pc[session] = "want_lock"
    /\ locked' = TRUE
    /\ pc' = [pc EXCEPT ![session] = "has_lock"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits>>

\* Claim an item (under lock)
ClaimItem(session, item, worktree) ==
    /\ pc[session] = "has_lock"
    /\ \/ claims[item] = NULL                          \* unclaimed
       \/ ~alive[claims[item].worktree]                \* stale (worktree gone)
       \/ claims[item].worktree = worktree             \* re-claim by same wt
    /\ claims' = [claims EXCEPT ![item] =
          [session |-> session, worktree |-> worktree]]
    /\ locked' = FALSE
    /\ pc' = [pc EXCEPT ![session] = "claimed"]
    /\ UNCHANGED <<alive, scopes, footprints, edits>>

\* Claim refused (live claim by another)
ClaimRefused(session, item) ==
    /\ pc[session] = "has_lock"
    /\ claims[item] # NULL
    /\ alive[claims[item].worktree]
    /\ claims[item].session # session
    /\ locked' = FALSE
    /\ pc' = [pc EXCEPT ![session] = "refused"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits>>

\* Release a claim
ReleaseItem(session, item) ==
    /\ pc[session] \in {"claimed", "has_lock"}
    /\ claims[item].session = session
    /\ claims' = [claims EXCEPT ![item] = NULL]
    /\ IF pc[session] = "has_lock" THEN locked' = FALSE ELSE UNCHANGED locked
    /\ pc' = [pc EXCEPT ![session] = "idle"]
    /\ UNCHANGED <<alive, scopes, footprints, edits>>

\* Worktree dies (simulates crash / cleanup)
WorktreeDies(worktree) ==
    /\ alive[worktree]
    /\ alive' = [alive EXCEPT ![worktree] = FALSE]
    /\ UNCHANGED <<claims, scopes, footprints, edits, locked, pc>>

\* Session edits a file (only legal if claim held)
EditFile(session, file) ==
    /\ pc[session] = "claimed"
    /\ edits' = [edits EXCEPT ![session] = edits[session] \cup {file}]
    /\ UNCHANGED <<claims, alive, scopes, footprints, locked, pc>>

\* Topology: check if two items can parallelize
CanParallelize(item_a, item_b) ==
    footprints[item_a] \cap footprints[item_b] = {}

-----------------------------------------------------------------------------
\* Safety Invariants

\* S1: No two live sessions hold the same item
NoDuplicateClaim ==
    \A i \in Items :
        claims[i] # NULL /\ alive[claims[i].worktree] =>
            ~\E j \in Items :
                j # i /\ claims[j] # NULL /\
                claims[j].session = claims[i].session /\
                claims[j].worktree = claims[i].worktree /\
                j = i  \* (stronger: no two sessions on same item)

NoDuplicateClaimStrong ==
    \A i \in Items :
        claims[i] # NULL /\ alive[claims[i].worktree] =>
            \A s \in Sessions :
                (s # claims[i].session) =>
                    ~(\E item2 \in Items :
                        item2 = i /\ claims[item2].session = s /\
                        alive[claims[item2].worktree])

\* S2: Parallel items have disjoint footprints
DisjointParallelism ==
    \A i, j \in Items :
        (i # j /\ claims[i] # NULL /\ claims[j] # NULL /\
         alive[claims[i].worktree] /\ alive[claims[j].worktree] /\
         claims[i].session # claims[j].session) =>
            footprints[i] \cap footprints[j] = {}

\* S3: No scope declared -> footprint = all files
UnknownScopeConservative ==
    \A i \in Items :
        scopes[i] = {} => footprints[i] = Files

\* S4: Edits only within claimed item's footprint
ClaimBeforeWork ==
    \A s \in Sessions :
        pc[s] = "claimed" =>
            \E i \in Items :
                claims[i].session = s /\
                edits[s] \subseteq footprints[i]

\* L1: Stale claims are reclaimable (enabled by WorktreeDies)
\* (Verified as a temporal property below)

-----------------------------------------------------------------------------
\* Temporal Properties

\* L1: If a worktree dies, its claims become reclaimable
StaleClaims ==
    \A w \in Worktrees, i \in Items :
        (claims[i] # NULL /\ claims[i].worktree = w /\ ~alive[w]) ~>
            (\E s \in Sessions : claims[i].session = s /\ claims[i].worktree # w)
            \/ claims[i] = NULL

\* L2: Release always completes (no deadlock in lock path)
ReleaseCompletes ==
    \A s \in Sessions :
        (pc[s] = "claimed") ~> (pc[s] = "idle")

-----------------------------------------------------------------------------
Next ==
    \/ \E s \in Sessions, i \in Items, w \in Worktrees :
        \/ (pc' = [pc EXCEPT ![s] = "want_lock"] /\ UNCHANGED <<claims, alive, scopes, footprints, edits, locked>>)
        \/ AcquireLock(s)
        \/ ClaimItem(s, i, w)
        \/ ClaimRefused(s, i)
        \/ ReleaseItem(s, i)
        \/ \E f \in Files : EditFile(s, f)
    \/ \E w \in Worktrees : WorktreeDies(w)
    \/ \E i \in Items, scope \in SUBSET Files : DeclareScope(i, scope)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
```

### Model-Checking Parameters

| Parameter | Value |
|-----------|-------|
| Items | `{"item-a", "item-b", "item-c"}` |
| Sessions | `{"sess-1", "sess-2", "sess-3"}` |
| Worktrees | `{"wt-1", "wt-2", "wt-3"}` |
| Files | `{"x.py", "y.py", "z.py"}` |

### Deliverables

1. `specs/tla/WorkItemClaims.tla` — the spec above
2. `specs/tla/WorkItemClaims.cfg` — TLC config
3. `specs/tla/TopologyConflicts.tla` — dedicated spec for `find_conflicts` pairwise logic

---

## WP-3: Verify Gate Temporal Ordering

**Priority:** Medium  
**Risk mitigated:** Stale/invalid verification stamp passes the Stop gate  
**Source:** `fettle/verify_gate.py`  
**Estimated spec size:** ~100 lines TLA+  

### Properties to Verify

| ID | Property | Type | Description |
|----|----------|------|-------------|
| S1 | FreshStampRequired | Safety | Stamp older than latest edit (mtime) + tree changed -> gate blocks/advises |
| S2 | SessionBinding | Safety | Stamp from session X cannot satisfy gate in session Y |
| S3 | GreenRequired | Safety | A red stamp (ok=false) never passes the gate |
| S4 | CoverageComplete | Safety | Impacted-scope stamp must cover all files edited this session |
| S5 | WorkspaceCoverage | Safety | Multi-workspace edits require all affected workspaces verified |
| L1 | ValidPathClears | Liveness | edit -> verify (green, same session, covers edits) -> Stop always passes |

### TLA+ Specification

```tla
------------------------------ MODULE VerifyGate ------------------------------
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    SessionId,       \* the current session identifier
    OtherSession,    \* a different session (for cross-session tests)
    CodeFiles,       \* {"src/a.py", "src/b.py", "tests/test_a.py"}
    Workspaces       \* {"root", "packages/lib"}

VARIABLES
    edits,           \* sequence of edit events (file, timestamp)
    stamp,           \* verification stamp record or NULL
    clock,           \* monotonic logical clock
    gate_result,     \* "allow" | "advisory" | "block"
    pc              \* process state

vars == <<edits, stamp, clock, gate_result, pc>>

NULL_STAMP == [ok |-> FALSE, session_id |-> "", ts |-> 0,
               scope |-> "none", impacted |-> {}, workspaces |-> {}]

-----------------------------------------------------------------------------
Init ==
    /\ edits = <<>>
    /\ stamp = NULL_STAMP
    /\ clock = 0
    /\ gate_result = "allow"
    /\ pc = "coding"

\* Developer edits a code file
EditCodeFile(file, workspace) ==
    /\ pc = "coding"
    /\ clock' = clock + 1
    /\ edits' = Append(edits, [file |-> file, ts |-> clock', workspace |-> workspace])
    /\ UNCHANGED <<stamp, gate_result, pc>>

\* Run fettle verify (minutes-world) — may succeed or fail
RunVerify(ok, scope, session, covered_files, covered_workspaces) ==
    /\ pc = "coding"
    /\ clock' = clock + 1
    /\ stamp' = [ok |-> ok,
                 session_id |-> session,
                 ts |-> clock',
                 scope |-> scope,
                 impacted |-> covered_files,
                 workspaces |-> covered_workspaces]
    /\ UNCHANGED <<edits, gate_result, pc>>

\* Edit after verify (makes stamp stale)
EditAfterVerify(file, workspace) ==
    /\ pc = "coding"
    /\ stamp.ts > 0  \* stamp exists
    /\ clock' = clock + 1
    /\ edits' = Append(edits, [file |-> file, ts |-> clock', workspace |-> workspace])
    /\ UNCHANGED <<stamp, gate_result, pc>>

\* Stop event: run_check evaluates the gate
EvaluateGate ==
    /\ pc = "coding"
    /\ pc' = "stopped"
    /\ LET
        has_code_edits == Len(edits) > 0
        stamp_exists == stamp.ts > 0
        same_session == stamp.session_id = SessionId
        stamp_fresh == \A i \in 1..Len(edits) : edits[i].ts <= stamp.ts
        stamp_green == stamp.ok
        all_files_covered ==
            IF stamp.scope = "full" THEN TRUE
            ELSE {edits[i].file : i \in 1..Len(edits)} \subseteq stamp.impacted
        all_workspaces_covered ==
            {edits[i].workspace : i \in 1..Len(edits)} \subseteq stamp.workspaces
       IN
        gate_result' = CASE
            ~has_code_edits -> "allow"
            [] ~stamp_exists -> "block"
            [] ~same_session -> "block"
            [] ~stamp_fresh  -> "block"
            [] ~stamp_green  -> "block"
            [] ~all_files_covered -> "block"
            [] ~all_workspaces_covered -> "block"
            [] OTHER -> "allow"
    /\ UNCHANGED <<edits, stamp, clock>>

-----------------------------------------------------------------------------
\* Safety Invariants

\* S1: Stale stamp cannot produce "allow"
FreshStampRequired ==
    (pc = "stopped" /\ gate_result = "allow" /\ Len(edits) > 0) =>
        \A i \in 1..Len(edits) : edits[i].ts <= stamp.ts

\* S2: Cross-session stamp cannot produce "allow"
SessionBinding ==
    (pc = "stopped" /\ gate_result = "allow" /\ Len(edits) > 0) =>
        stamp.session_id = SessionId

\* S3: Red stamp cannot produce "allow"
GreenRequired ==
    (pc = "stopped" /\ gate_result = "allow" /\ Len(edits) > 0) =>
        stamp.ok = TRUE

\* S4: Impacted-scope stamp covers all edited files
CoverageComplete ==
    (pc = "stopped" /\ gate_result = "allow" /\ Len(edits) > 0 /\
     stamp.scope # "full") =>
        {edits[i].file : i \in 1..Len(edits)} \subseteq stamp.impacted

\* S5: All affected workspaces verified
WorkspaceCoverage ==
    (pc = "stopped" /\ gate_result = "allow" /\ Len(edits) > 0) =>
        {edits[i].workspace : i \in 1..Len(edits)} \subseteq stamp.workspaces

\* L1: Correct sequence always passes
ValidPathClears ==
    (pc = "stopped" /\
     stamp.ok = TRUE /\
     stamp.session_id = SessionId /\
     (\A i \in 1..Len(edits) : edits[i].ts <= stamp.ts) /\
     (stamp.scope = "full" \/
      {edits[i].file : i \in 1..Len(edits)} \subseteq stamp.impacted) /\
     {edits[i].workspace : i \in 1..Len(edits)} \subseteq stamp.workspaces)
    => gate_result = "allow"

-----------------------------------------------------------------------------
Next ==
    \/ \E f \in CodeFiles, w \in Workspaces : EditCodeFile(f, w)
    \/ \E ok \in BOOLEAN, scope \in {"full", "impacted"},
         sess \in {SessionId, OtherSession},
         covered \in SUBSET CodeFiles,
         ws \in SUBSET Workspaces :
            RunVerify(ok, scope, sess, covered, ws)
    \/ \E f \in CodeFiles, w \in Workspaces : EditAfterVerify(f, w)
    \/ EvaluateGate

Spec == Init /\ [][Next]_vars

=============================================================================
```

### Model-Checking Parameters

| Parameter | Value |
|-----------|-------|
| SessionId | `"current"` |
| OtherSession | `"other"` |
| CodeFiles | `{"a.py", "b.py", "c.py"}` |
| Workspaces | `{"root", "lib"}` |

### Deliverables

1. `specs/tla/VerifyGate.tla` — the spec above
2. `specs/tla/VerifyGate.cfg` — TLC config
3. Test traces: edit-then-stop (must block), edit-verify-stop (must pass), edit-verify-edit-stop (must block)

---

## WP-4: Dispatcher Budget & Priority Protocol

**Priority:** Low  
**Risk mitigated:** A slow check starves higher-priority checks or crashes the session  
**Source:** `fettle/dispatcher.py`, `fettle/dispatcher_registry.py`  
**Estimated spec size:** ~80 lines TLA+  

### Properties to Verify

| ID | Property | Type | Description |
|----|----------|------|-------------|
| S1 | BudgetRespected | Safety | Total wall-clock never exceeds event budget (modulo current check overrun) |
| S2 | PriorityOrder | Safety | Checks execute in registry priority order (no reordering) |
| S3 | FirstBlockWins | Safety | After a BLOCK result, no further checks execute |
| S4 | FailOpen | Safety | A check exception never produces a BLOCK — only allow/advisory |
| S5 | EscalationThreshold | Safety | Repeated failures surface advisory only after >= 3 occurrences |
| L1 | AlwaysTerminates | Liveness | The dispatcher always produces output (never hangs) |

### TLA+ Specification

```tla
------------------------------ MODULE Dispatcher ------------------------------
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    Checks,          \* ordered sequence: <<"capsule_guard", "tdd_gate", "adapter_check">>
    BudgetMs,        \* event budget: e.g. 250
    CheckDurations   \* check -> duration in ms (model)

VARIABLES
    elapsed,         \* total elapsed ms
    index,           \* current check index (1..Len(Checks)+1)
    results,         \* sequence of (check, decision) pairs
    errors,          \* sequence of check names that threw
    output,          \* final decision: "allow" | "advisory" | "block" | NULL
    has_block,       \* BOOLEAN — short-circuit flag
    budget_exhausted \* check name where budget ran out, or ""

vars == <<elapsed, index, results, errors, output, has_block, budget_exhausted>>

NULL == ""

-----------------------------------------------------------------------------
Init ==
    /\ elapsed = 0
    /\ index = 1
    /\ results = <<>>
    /\ errors = <<>>
    /\ output = NULL
    /\ has_block = FALSE
    /\ budget_exhausted = ""

\* Check budget before running next check
CheckBudget ==
    /\ index <= Len(Checks)
    /\ ~has_block
    /\ output = NULL
    /\ elapsed >= BudgetMs
    /\ budget_exhausted' = Checks[index]
    /\ output' = IF has_block THEN "block"
                 ELSE IF Len(results) > 0 THEN "advisory"
                 ELSE "allow"
    /\ index' = Len(Checks) + 1  \* terminate
    /\ UNCHANGED <<elapsed, results, errors, has_block>>

\* Run a check successfully
RunCheck(decision) ==
    /\ index <= Len(Checks)
    /\ ~has_block
    /\ output = NULL
    /\ elapsed < BudgetMs
    /\ LET check == Checks[index]
           duration == CheckDurations[check]
       IN /\ elapsed' = elapsed + duration
          /\ results' = Append(results, [check |-> check, decision |-> decision])
          /\ has_block' = (decision = "block")
          /\ index' = IF decision = "block" THEN Len(Checks) + 1 ELSE index + 1
    /\ UNCHANGED <<errors, output, budget_exhausted>>

\* Check throws an exception (fail-open: treated as allow)
CheckException ==
    /\ index <= Len(Checks)
    /\ ~has_block
    /\ output = NULL
    /\ elapsed < BudgetMs
    /\ LET check == Checks[index]
           duration == CheckDurations[check]
       IN /\ elapsed' = elapsed + duration
          /\ errors' = Append(errors, check)
          /\ index' = index + 1
    /\ UNCHANGED <<results, output, has_block, budget_exhausted>>

\* Finalize output (all checks done or short-circuited)
Finalize ==
    /\ output = NULL
    /\ (index > Len(Checks) \/ has_block)
    /\ output' = IF has_block THEN "block"
                 ELSE IF \E i \in 1..Len(results) :
                          results[i].decision = "advisory"
                      THEN "advisory"
                 ELSE "allow"
    /\ UNCHANGED <<elapsed, index, results, errors, has_block, budget_exhausted>>

-----------------------------------------------------------------------------
\* Safety Invariants

\* S1: Elapsed never wildly exceeds budget (at most one check overrun)
BudgetRespected ==
    output # NULL =>
        elapsed <= BudgetMs + (IF Len(Checks) > 0
                               THEN CheckDurations[Checks[Len(Checks)]]
                               ELSE 0)

\* S2: Results are in priority order
PriorityOrder ==
    \A i \in 1..(Len(results) - 1) :
        \E a, b \in 1..Len(Checks) :
            results[i].check = Checks[a] /\
            results[i+1].check = Checks[b] /\
            a < b

\* S3: Nothing executes after a block
FirstBlockWins ==
    \A i \in 1..Len(results) :
        results[i].decision = "block" => i = Len(results)

\* S4: Exceptions never produce block
FailOpen ==
    \A e \in 1..Len(errors) :
        output # NULL => output # "block" \/ has_block
        \* More precisely: the blocked decision came from a result, not an error

\* L1: Always terminates (output eventually non-null)
AlwaysTerminates == <>(output # NULL)

-----------------------------------------------------------------------------
Next ==
    \/ CheckBudget
    \/ \E d \in {"allow", "advisory", "block"} : RunCheck(d)
    \/ CheckException
    \/ Finalize

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
```

### Model-Checking Parameters

| Parameter | Value |
|-----------|-------|
| Checks | `<<"capsule_guard", "tdd_gate", "adapter_check", "scope_creep">>` |
| BudgetMs | `250` |
| CheckDurations | `[capsule_guard |-> 5, tdd_gate |-> 30, adapter_check |-> 150, scope_creep |-> 20]` |

### Deliverables

1. `specs/tla/Dispatcher.tla` — the spec above
2. `specs/tla/Dispatcher.cfg` — TLC config
3. Trace analysis: budget exhaustion scenario, exception-then-block scenario

---

## WP-5: TDD Gate Phase Ordering

**Priority:** Low  
**Risk mitigated:** Implementation edits pass without test-first evidence  
**Source:** `fettle/tdd_gate.py`  
**Estimated spec size:** ~70 lines TLA+  

### Properties to Verify

| ID | Property | Type | Description |
|----|----------|------|-------------|
| S1 | TestFirstRequired | Safety | In enforce mode, an impl edit without prior test_edit for that module is blocked |
| S2 | PreexistingTestSuffices | Safety | If accept_preexisting is true and a test file exists on disk, impl is allowed |
| S3 | TestEvidencePersists | Safety | A test_edit event is never lost (append-only log) |
| S4 | ExemptPathsPass | Safety | Files matching exempt patterns are never blocked |
| L1 | TestThenImplPasses | Liveness | test_edit(M) then impl_edit(M) always produces ALLOW on PreToolUse |

### TLA+ Specification

```tla
------------------------------ MODULE TDDGate ------------------------------
EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    Modules,         \* {"auth", "api", "utils"}
    ExemptFiles,     \* {"README.md", "config.toml"}
    Mode            \* "advisory" | "enforce"

VARIABLES
    evidence,        \* SUBSET Modules (modules with test-first evidence)
    preexisting,     \* SUBSET Modules (modules with test files on disk)
    event_log,       \* sequence of events
    last_decision,   \* "allow" | "advisory" | "block"
    pc              \* "idle" | "editing_test" | "editing_impl"

vars == <<evidence, preexisting, event_log, last_decision, pc>>

AcceptPreexisting == TRUE  \* config flag

-----------------------------------------------------------------------------
Init ==
    /\ evidence = {}
    /\ preexisting = {}  \* can be set to any subset for scenario
    /\ event_log = <<>>
    /\ last_decision = "allow"
    /\ pc = "idle"

\* A test file exists on disk for a module (environment setup)
TestExistsOnDisk(module) ==
    /\ preexisting' = preexisting \cup {module}
    /\ UNCHANGED <<evidence, event_log, last_decision, pc>>

\* PostToolUse: record a test edit
EditTestFile(module) ==
    /\ pc' = "editing_test"
    /\ evidence' = evidence \cup {module}
    /\ event_log' = Append(event_log, [event |-> "test_edit", module |-> module])
    /\ last_decision' = "allow"  \* PostToolUse always allows
    /\ UNCHANGED preexisting

\* PreToolUse: attempt to edit an implementation file
EditImplFile(module) ==
    /\ pc' = "editing_impl"
    /\ LET
        has_evidence == module \in evidence
        has_preexisting == AcceptPreexisting /\ module \in preexisting
        allowed == has_evidence \/ has_preexisting
       IN
        last_decision' =
            IF allowed THEN "allow"
            ELSE IF Mode = "enforce" THEN "block"
            ELSE "advisory"
    /\ event_log' = Append(event_log, [event |-> "impl_edit", module |-> module])
    /\ UNCHANGED <<evidence, preexisting>>

\* PostToolUse: record the impl edit (if not blocked)
RecordImplEdit(module) ==
    /\ pc = "editing_impl"
    /\ last_decision \in {"allow", "advisory"}  \* blocked edits don't execute
    /\ pc' = "idle"
    /\ UNCHANGED <<evidence, preexisting, event_log, last_decision>>

\* Edit an exempt file (always passes, no recording)
EditExemptFile ==
    /\ last_decision' = "allow"
    /\ pc' = "idle"
    /\ UNCHANGED <<evidence, preexisting, event_log>>

\* Reset to idle
ResetToIdle ==
    /\ pc' = "idle"
    /\ UNCHANGED <<evidence, preexisting, event_log, last_decision>>

-----------------------------------------------------------------------------
\* Safety Invariants

\* S1: In enforce mode, impl without evidence is blocked
TestFirstRequired ==
    (pc = "editing_impl" /\ Mode = "enforce") =>
        (last_decision = "block" \/
         \E i \in 1..Len(event_log) :
            event_log[i].event = "test_edit" /\
            event_log[i].module = event_log[Len(event_log)].module) \/
        (AcceptPreexisting /\
         event_log[Len(event_log)].module \in preexisting)

\* S2: Preexisting test file is sufficient
PreexistingTestSuffices ==
    \A m \in Modules :
        (m \in preexisting /\ AcceptPreexisting /\ pc = "editing_impl" /\
         event_log[Len(event_log)].module = m) =>
            last_decision \in {"allow", "advisory"}

\* S3: Evidence is monotonically growing (append-only)
TestEvidencePersists ==
    \A i \in 1..Len(event_log) :
        event_log[i].event = "test_edit" =>
            event_log[i].module \in evidence

\* L1: test then impl always passes
TestThenImplPasses ==
    \A m \in Modules :
        (m \in evidence /\ pc = "editing_impl" /\
         event_log[Len(event_log)].module = m) =>
            last_decision = "allow"

-----------------------------------------------------------------------------
Next ==
    \/ \E m \in Modules : EditTestFile(m)
    \/ \E m \in Modules : EditImplFile(m)
    \/ \E m \in Modules : RecordImplEdit(m)
    \/ \E m \in Modules : TestExistsOnDisk(m)
    \/ EditExemptFile
    \/ ResetToIdle

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

=============================================================================
```

### Model-Checking Parameters

| Parameter | Value |
|-----------|-------|
| Modules | `{"auth", "api", "utils"}` |
| ExemptFiles | `{"readme", "config"}` |
| Mode | `"enforce"` (check both; also run with `"advisory"`) |

### Deliverables

1. `specs/tla/TDDGate.tla` — the spec above
2. `specs/tla/TDDGate.cfg` — TLC config (enforce mode)
3. `specs/tla/TDDGateAdvisory.cfg` — TLC config (advisory mode)

---

## Implementation Plan

### Phase 1: Infrastructure (1 day)

| Task | Description |
|------|-------------|
| 1.1 | Create `specs/tla/` directory structure |
| 1.2 | Add TLC runner script (`specs/tla/run-all.sh`) |
| 1.3 | Add CI integration (GitHub Actions with `tlaplus/tla-toolbox` Docker) |
| 1.4 | Document TLA+ setup in `specs/tla/README.md` |

### Phase 2: WP-1 Policy Capsule (2 days)

| Task | Description |
|------|-------------|
| 2.1 | Write `PolicyCapsule.tla` + `.cfg` |
| 2.2 | Run TLC, fix specification until all invariants pass |
| 2.3 | Inject known bugs (remove depth check, weaken merge) — verify TLC catches them |
| 2.4 | Write mutation tests: each removed line should violate an invariant |
| 2.5 | Document findings and any code fixes discovered |

### Phase 3: WP-2 Work Items & Topology (2 days)

| Task | Description |
|------|-------------|
| 3.1 | Write `WorkItemClaims.tla` + `.cfg` |
| 3.2 | Write `TopologyConflicts.tla` (focused on `find_conflicts` pairwise logic) |
| 3.3 | Run TLC with 3 items x 3 sessions — verify NoDuplicateClaim |
| 3.4 | Add stale-claim reclamation scenario |
| 3.5 | Inject race condition (remove flock) — verify TLC finds duplicate claim |

### Phase 4: WP-3 Verify Gate (1 day)

| Task | Description |
|------|-------------|
| 4.1 | Write `VerifyGate.tla` + `.cfg` |
| 4.2 | Run TLC with 3 files x 2 workspaces |
| 4.3 | Verify all 5 safety properties hold |
| 4.4 | Inject stale-stamp bug — verify TLC catches it |

### Phase 5: WP-4 Dispatcher (1 day)

| Task | Description |
|------|-------------|
| 5.1 | Write `Dispatcher.tla` + `.cfg` |
| 5.2 | Run TLC with 4 checks, budget=250ms |
| 5.3 | Verify budget, ordering, fail-open properties |
| 5.4 | Test escalation threshold with repeated-failure trace |

### Phase 6: WP-5 TDD Gate (0.5 day)

| Task | Description |
|------|-------------|
| 6.1 | Write `TDDGate.tla` + two `.cfg` files |
| 6.2 | Run TLC in both modes |
| 6.3 | Verify test-first ordering holds in enforce, advisory warns but doesn't block |

### Phase 7: Integration & Reporting (0.5 day)

| Task | Description |
|------|-------------|
| 7.1 | Run full suite, collect state-space statistics |
| 7.2 | Document any bugs found by model checking |
| 7.3 | Add `fettle tla` CLI command to run specs locally |
| 7.4 | Update ROADMAP.md with TLA+ verification status |

---

## State-Space Estimates

| WP | States (est.) | Time (est.) | Diameter |
|----|--------------|-------------|----------|
| WP-1 Policy Capsule | ~50K | <30s | 8 |
| WP-2 Work Items | ~200K | <2min | 12 |
| WP-3 Verify Gate | ~10K | <10s | 6 |
| WP-4 Dispatcher | ~5K | <5s | 5 |
| WP-5 TDD Gate | ~3K | <5s | 4 |

These are estimates with the small model parameters listed above. Production-scale
parameters (16 depth, many files) would require symmetry reduction or APALACHE.

---

## Value Assessment

| WP | Bugs TLA+ Could Find | Confidence |
|----|----------------------|------------|
| WP-1 | Policy escalation via merge order, lineage overflow, version-field escape | Very High |
| WP-2 | Race in claim (flock removed/bypassed), parallel items with hidden overlap | High |
| WP-3 | Stale stamp accepted, cross-session stamp reuse, impacted-scope gap | Medium-High |
| WP-4 | Priority inversion, silent fail-closed, budget accounting off-by-one | Medium |
| WP-5 | False positive block, evidence loss on crash | Low-Medium |

---

## Prerequisites

- TLA+ Toolbox or VS Code TLA+ extension
- Java 11+ (TLC model checker runtime)
- `tla2tools.jar` (download from https://github.com/tlaplus/tlaplus/releases)

Run: `java -jar tla2tools.jar -modelcheck specs/tla/<Module>.cfg`
