------------------------------ MODULE PolicyCapsule ------------------------------
(***************************************************************************)
(* TLA+ formal model of Fettle's policy capsule delegation protocol.       *)
(*                                                                         *)
(* Source: fettle/policy_capsule.py, fettle/capsule_guard.py,              *)
(*         fettle/authorship_gate.py                                        *)
(*                                                                         *)
(* The capsule protocol ensures that child agents spawned by a parent      *)
(* can never operate under a weaker policy than the parent's. Properties:  *)
(*   S1: MonotonicStrictness — child effective >= parent on every key       *)
(*   S2: DepthBound — lineage never exceeds MAX_LINEAGE_DEPTH              *)
(*   S3: TamperDetection — modified capsule -> all tool calls blocked      *)
(*   S4: FailClosed — env asserts invalid capsule -> block                 *)
(*   S5: PlumbingIsolation — plumbing keys stay local                      *)
(*   S6: RoleMonotonicity — child role rank >= parent role rank             *)
(*   S7: RoleFileAuthority — implementer never edits test, tester never    *)
(*       edits impl                                                         *)
(*   L1: ValidSpawnSucceeds — valid spawn always produces usable capsule   *)
(*   L2: NoSpuriousBlock — verified untampered capsule never blocked       *)
(***************************************************************************)

EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS
    MaxDepth,       \* Lineage cap (production = 16, model = 3)
    Agents,         \* Set of agent identifiers
    PolicyKeys,     \* Set of policy key names
    PlumbingKeys,   \* Subset of PolicyKeys that are machine-local
    ModeValues,     \* Ordered mode values (e.g., {"off", "advisory", "enforce"})
    FileKinds       \* {"test", "impl"} — file categories for role authority

VARIABLES
    capsules,       \* [agent -> record: policy, digest, lineage, written]
    effective,      \* [agent -> policy function]
    blocked,        \* [agent -> BOOLEAN]
    tampered,       \* Set of agents whose capsule was tampered
    local_used,     \* [agent -> policy function] local policy used during merge
    role,           \* [agent -> role string] effective role after merge
    edits,          \* [agent -> SUBSET FileKinds] file kinds edited by this agent
    pc              \* [agent -> process state]

vars == <<capsules, effective, blocked, tampered, local_used, role, edits, pc>>

-----------------------------------------------------------------------------
(* Role definitions — must precede TypeOK *)

Roles == {"solo", "implementer", "tester", "reviewer"}

RoleRank(r) == CASE r = "solo"        -> 0
               []   r = "implementer"  -> 1
               []   r = "tester"       -> 1
               []   r = "reviewer"     -> 2

MergeRole(parent_role, local_role) ==
    IF RoleRank(local_role) >= RoleRank(parent_role)
    THEN local_role
    ELSE parent_role

-----------------------------------------------------------------------------
(* Type invariant *)

PCStates == {"idle", "ready", "capsule_written", "blocked", "spawn_rejected"}

TypeOK ==
    /\ \A a \in Agents :
        /\ capsules[a].policy \in [PolicyKeys -> ModeValues]
        /\ capsules[a].digest \in [PolicyKeys -> ModeValues]
        /\ capsules[a].written \in BOOLEAN
        /\ \A i \in 1..Len(capsules[a].lineage) : capsules[a].lineage[i] \in Agents
    /\ effective \in [Agents -> [PolicyKeys -> ModeValues]]
    /\ blocked \in [Agents -> BOOLEAN]
    /\ tampered \subseteq Agents
    /\ role \in [Agents -> Roles]
    /\ edits \in [Agents -> SUBSET FileKinds]
    /\ pc \in [Agents -> PCStates]

-----------------------------------------------------------------------------
(* Mode strictness ladder: higher rank = stricter enforcement *)

ModeRank(m) == CASE m = "off"      -> 0
               []   m = "advisory"  -> 1
               []   m = "enforce"   -> 2

StricterMode(a, b) == IF ModeRank(a) >= ModeRank(b) THEN a ELSE b

(* Monotonic merge: for each key, result = max(parent, local) by rank.
   Plumbing keys always take the local value (D-A5). *)

MonotonicMerge(parent_policy, local_policy) ==
    [key \in PolicyKeys |->
        IF key \in PlumbingKeys
        THEN local_policy[key]
        ELSE StricterMode(parent_policy[key], local_policy[key])
    ]

(* Abstract digest: identity on policy dict. In production this is SHA-256. *)

Digest(policy) == policy

-----------------------------------------------------------------------------
(* Initial state: one root agent is "ready" with a baseline policy;
   all others are idle with no capsule. *)

RootAgent == CHOOSE a \in Agents : TRUE

BaselinePolicy == [key \in PolicyKeys |-> "advisory"]

NullCapsule == [policy |-> BaselinePolicy,
                digest |-> BaselinePolicy,
                lineage |-> <<>>,
                written |-> FALSE]

Init ==
    /\ capsules = [a \in Agents |->
          IF a = RootAgent
          THEN [policy |-> BaselinePolicy,
                digest |-> Digest(BaselinePolicy),
                lineage |-> <<>>,
                written |-> TRUE]
          ELSE NullCapsule]
    /\ effective = [a \in Agents |->
          IF a = RootAgent
          THEN BaselinePolicy
          ELSE [key \in PolicyKeys |-> "off"]]
    /\ blocked = [a \in Agents |-> FALSE]
    /\ tampered = {}
    /\ local_used = [a \in Agents |-> BaselinePolicy]
    /\ role = [a \in Agents |-> "solo"]
    /\ edits = [a \in Agents |-> {}]
    /\ pc = [a \in Agents |->
          IF a = RootAgent THEN "ready" ELSE "idle"]

-----------------------------------------------------------------------------
(* Actions *)

(* A ready parent writes a capsule for an idle child.
   The capsule carries the parent's EFFECTIVE policy (the merged result),
   not the raw capsule the parent received. This matches the production
   code: write_capsule() is called with load_config()'s output, which
   already has apply_env_capsule() merged in.
   Precondition: parent lineage + 1 <= MaxDepth (D-A6). *)

WriteCapsule(parent, child, child_role) ==
    /\ parent # child
    /\ pc[parent] = "ready"
    /\ pc[child] = "idle"
    /\ Len(capsules[parent].lineage) < MaxDepth
    /\ child_role \in Roles
    /\ RoleRank(child_role) >= RoleRank(role[parent])  \* cannot widen
    /\ LET new_lineage == Append(capsules[parent].lineage, parent)
           parent_effective == effective[parent]
       IN capsules' = [capsules EXCEPT ![child] =
              [policy |-> parent_effective,
               digest |-> Digest(parent_effective),
               lineage |-> new_lineage,
               written |-> TRUE]]
    /\ role' = [role EXCEPT ![child] = child_role]
    /\ pc' = [pc EXCEPT ![child] = "capsule_written"]
    /\ UNCHANGED <<effective, blocked, tampered, local_used, edits>>

(* Parent attempts to spawn but lineage is at cap — must fail loudly. *)

SpawnAtMaxDepth(parent, child) ==
    /\ parent # child
    /\ pc[parent] = "ready"
    /\ pc[child] = "idle"
    /\ Len(capsules[parent].lineage) >= MaxDepth
    /\ pc' = [pc EXCEPT ![parent] = "spawn_rejected"]
    /\ UNCHANGED <<capsules, effective, blocked, tampered, local_used, role, edits>>

(* An adversary tampers with a written capsule (modifies policy body
   without updating digest — simulates file modification). *)

Tamper(agent) ==
    /\ pc[agent] = "capsule_written"
    /\ agent \notin tampered
    /\ tampered' = tampered \cup {agent}
    /\ \E new_policy \in [PolicyKeys -> ModeValues] :
          /\ new_policy # capsules[agent].policy  \* actual modification
          /\ capsules' = [capsules EXCEPT ![agent].policy = new_policy]
    /\ UNCHANGED <<effective, blocked, local_used, role, edits, pc>>

(* Child verifies capsule and merges with local policy.
   Fail-closed: digest mismatch or lineage overflow -> blocked. *)

VerifyAndMerge(agent, local_policy) ==
    /\ pc[agent] = "capsule_written"
    /\ LET cap == capsules[agent]
           digest_ok == (cap.digest = Digest(cap.policy))
           lineage_ok == Len(cap.lineage) <= MaxDepth
       IN IF ~digest_ok \/ ~lineage_ok
          THEN \* FAIL CLOSED: capsule_guard blocks all tool calls
               /\ blocked' = [blocked EXCEPT ![agent] = TRUE]
               /\ pc' = [pc EXCEPT ![agent] = "blocked"]
               /\ UNCHANGED <<capsules, effective, tampered, local_used, role, edits>>
          ELSE \* VERIFIED: merge monotonically stricter
               /\ effective' = [effective EXCEPT ![agent] =
                      MonotonicMerge(cap.policy, local_policy)]
               /\ local_used' = [local_used EXCEPT ![agent] = local_policy]
               /\ pc' = [pc EXCEPT ![agent] = "ready"]
               /\ UNCHANGED <<capsules, blocked, tampered, role, edits>>

(* A ready child can itself spawn deeper children (recursive delegation). *)
(* This is modeled by WriteCapsule with the child as parent. *)

(* A ready agent edits a file. The authorship_gate enforces:
   - implementer: can only edit "impl" files
   - tester: can only edit "test" files
   - reviewer: cannot edit anything
   - solo: can edit both *)

EditFile(agent, file_kind) ==
    /\ pc[agent] = "ready"
    /\ ~blocked[agent]
    /\ file_kind \in FileKinds
    /\ \/ role[agent] = "solo"
       \/ (role[agent] = "implementer" /\ file_kind = "impl")
       \/ (role[agent] = "tester" /\ file_kind = "test")
    \* reviewer has no matching disjunct — cannot edit
    /\ edits' = [edits EXCEPT ![agent] = edits[agent] \cup {file_kind}]
    /\ UNCHANGED <<capsules, effective, blocked, tampered, local_used, role, pc>>

-----------------------------------------------------------------------------
(* Safety Invariants *)

(* S1: Monotonic strictness — every ready child's effective policy is
   >= strict as its parent's effective policy on every non-plumbing key. *)

MonotonicStrictness ==
    \A agent \in Agents :
        (pc[agent] = "ready" /\ Len(capsules[agent].lineage) > 0) =>
            LET parent == capsules[agent].lineage[Len(capsules[agent].lineage)]
            IN pc[parent] = "ready" =>
               \A key \in PolicyKeys \ PlumbingKeys :
                   ModeRank(effective[agent][key]) >= ModeRank(effective[parent][key])

(* S2: Lineage depth never exceeds MaxDepth in any reachable state. *)

DepthBound ==
    \A agent \in Agents : Len(capsules[agent].lineage) <= MaxDepth

(* S3: A tampered agent can NEVER reach "ready" state — it must be blocked.
   This is the real tamper detection guarantee: tampering always gets caught. *)

TamperDetection ==
    \A agent \in Agents :
        (agent \in tampered /\ pc[agent] # "capsule_written") =>
            pc[agent] = "blocked"

(* S4: If verification fails (for any reason), agent is blocked. *)

FailClosed ==
    \A agent \in Agents :
        pc[agent] = "blocked" => blocked[agent] = TRUE

(* S5: Plumbing keys in effective policy equal the local policy used during
   merge, NOT the parent's capsule policy. This ensures machine-local keys
   (paths, endpoints) don't propagate across worktree boundaries (D-A5). *)

PlumbingIsolation ==
    \A agent \in Agents :
        (pc[agent] = "ready" /\ Len(capsules[agent].lineage) > 0) =>
            \A key \in PlumbingKeys :
                effective[agent][key] = local_used[agent][key]

(* L2: A verified, untampered capsule never triggers block. *)

NoSpuriousBlock ==
    \A agent \in Agents :
        (agent \notin tampered /\ pc[agent] = "ready") =>
            blocked[agent] = FALSE

(* S6: Role monotonicity — a child's effective role rank is always >=
   its parent's role rank. A child can never widen its authority. *)

RoleMonotonicity ==
    \A agent \in Agents :
        (pc[agent] = "ready" /\ Len(capsules[agent].lineage) > 0) =>
            LET parent == capsules[agent].lineage[Len(capsules[agent].lineage)]
            IN pc[parent] = "ready" =>
               RoleRank(role[agent]) >= RoleRank(role[parent])

(* S7: Role-based file authority — an implementer never edits a test file,
   a tester never edits an implementation file, a reviewer edits nothing.
   This is the core authorship separation safety guarantee. *)

RoleFileAuthority ==
    \A agent \in Agents :
        pc[agent] = "ready" =>
            /\ (role[agent] = "implementer" => "test" \notin edits[agent])
            /\ (role[agent] = "tester" => "impl" \notin edits[agent])
            /\ (role[agent] = "reviewer" => edits[agent] = {})

-----------------------------------------------------------------------------
(* Temporal properties *)

(* L1: A valid spawn (depth < cap, untampered) eventually reaches "ready". *)

ValidSpawnEventuallyReady ==
    \A parent, child \in Agents :
        (parent # child /\ pc[parent] = "ready" /\
         pc[child] = "idle" /\ Len(capsules[parent].lineage) < MaxDepth)
        ~> (pc[child] \in {"ready", "blocked"})

-----------------------------------------------------------------------------
(* Next-state relation *)

Next ==
    \/ \E parent, child \in Agents :
        \/ \E r \in Roles : WriteCapsule(parent, child, r)
        \/ SpawnAtMaxDepth(parent, child)
        \/ Tamper(child)
        \/ \E local \in [PolicyKeys -> ModeValues] :
               VerifyAndMerge(child, local)
    \/ \E agent \in Agents, fk \in FileKinds :
           EditFile(agent, fk)

(* Fairness: every enabled action eventually fires *)

Fairness == WF_vars(Next)

Spec == Init /\ [][Next]_vars /\ Fairness

=============================================================================
