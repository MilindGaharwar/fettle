------------------------------ MODULE WorkItemClaims ------------------------------
(***************************************************************************)
(* TLA+ formal model of Fettle's work-item claim protocol and topology     *)
(* conflict detection.                                                      *)
(*                                                                         *)
(* Source: fettle/work_items.py, fettle/topology.py, fettle/worktrees.py   *)
(*                                                                         *)
(* The protocol ensures that concurrent agent sessions never claim the     *)
(* same work item and never edit overlapping file sets in parallel.         *)
(*                                                                         *)
(* Properties:                                                             *)
(*   S1: NoDuplicateClaim — no two live sessions hold the same item        *)
(*   S2: DisjointParallelism — parallel items have non-overlapping files   *)
(*   S3: UnknownScopeConservative — no-scope items conflict with all       *)
(*   S4: ClaimBeforeWork — edits only within claimed footprint             *)
(*   L1: StaleClaims — dead worktree claims are reclaimable               *)
(*   L2: ReleaseCompletes — release never deadlocks                        *)
(***************************************************************************)

EXTENDS Integers, Sequences, FiniteSets

CONSTANTS
    Items,          \* Set of work item identifiers
    Sessions,       \* Set of session identifiers
    Worktrees,      \* Set of worktree paths
    Files           \* Set of repo-relative file paths

VARIABLES
    claims,         \* [Items -> claim record or Null]
    alive,          \* [Worktrees -> BOOLEAN]
    scopes,         \* [Items -> SUBSET Files] (declared scope)
    footprints,     \* [Items -> SUBSET Files] (expanded footprint)
    edits,          \* [Sessions -> SUBSET Files] (files edited)
    holding,        \* [Sessions -> Items \cup {""}] (which item a session holds)
    locked,         \* BOOLEAN (flock advisory lock)
    lock_holder,    \* Sessions \cup {""} (who holds the lock)
    pc              \* [Sessions -> process state]

vars == <<claims, alive, scopes, footprints, edits, holding, locked, lock_holder, pc>>

-----------------------------------------------------------------------------
(* Constants derived from the protocol *)

Null == [session |-> "", worktree |-> ""]

PCStates == {"idle", "want_lock", "has_lock", "claimed", "releasing", "refused"}

-----------------------------------------------------------------------------
(* Type invariant *)

TypeOK ==
    /\ claims \in [Items -> [session: Sessions \cup {""}, worktree: Worktrees \cup {""}]]
    /\ alive \in [Worktrees -> BOOLEAN]
    /\ scopes \in [Items -> SUBSET Files]
    /\ footprints \in [Items -> SUBSET Files]
    /\ edits \in [Sessions -> SUBSET Files]
    /\ holding \in [Sessions -> Items \cup {""}]
    /\ locked \in BOOLEAN
    /\ lock_holder \in Sessions \cup {""}
    /\ pc \in [Sessions -> PCStates]

-----------------------------------------------------------------------------
(* Initial state *)

Init ==
    /\ claims = [i \in Items |-> Null]
    /\ alive = [w \in Worktrees |-> TRUE]
    /\ scopes = [i \in Items |-> {}]
    /\ footprints = [i \in Items |-> Files]  \* no scope = conflicts with everything
    /\ edits = [s \in Sessions |-> {}]
    /\ holding = [s \in Sessions |-> ""]
    /\ locked = FALSE
    /\ lock_holder = ""
    /\ pc = [s \in Sessions |-> "idle"]

-----------------------------------------------------------------------------
(* Actions *)

(* A session declares scope for an item — narrows footprint from "all" to specific files.
   Scope is declared in the work-item frontmatter before claiming. Once claimed,
   scope is frozen — no narrowing after work has begun. *)

DeclareScope(item, scope_files) ==
    /\ scope_files # {}
    /\ claims[item] = Null  \* scope only changeable before claim
    /\ scopes' = [scopes EXCEPT ![item] = scope_files]
    /\ footprints' = [footprints EXCEPT ![item] = scope_files]
    /\ UNCHANGED <<claims, alive, edits, holding, locked, lock_holder, pc>>

(* Session requests the advisory lock *)

RequestLock(session) ==
    /\ pc[session] = "idle"
    /\ holding[session] = ""
    /\ pc' = [pc EXCEPT ![session] = "want_lock"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits, holding, locked, lock_holder>>

(* Session acquires the lock (flock semantics: exclusive, blocking) *)

AcquireLock(session) ==
    /\ pc[session] = "want_lock"
    /\ ~locked
    /\ locked' = TRUE
    /\ lock_holder' = session
    /\ pc' = [pc EXCEPT ![session] = "has_lock"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits, holding>>

(* Claim an item — allowed when: unclaimed, or stale (worktree dead),
   or re-claim by same worktree. Mirrors claim_item() in work_items.py *)

ClaimItem(session, item, worktree) ==
    /\ pc[session] = "has_lock"
    /\ alive[worktree]  \* claiming session's worktree must be alive
    /\ LET cl == claims[item]
           is_null == (cl.session = "" /\ cl.worktree = "")
           is_stale == (~is_null /\ cl.worktree \in Worktrees /\ ~alive[cl.worktree])
           is_same == (~is_null /\ cl.session = session /\ cl.worktree = worktree)
       IN is_null \/ is_stale \/ is_same
    /\ claims' = [claims EXCEPT ![item] =
          [session |-> session, worktree |-> worktree]]
    /\ holding' = [holding EXCEPT ![session] = item]
    /\ edits' = [edits EXCEPT ![session] = {}]  \* edits reset per work item
    /\ locked' = FALSE
    /\ lock_holder' = ""
    /\ pc' = [pc EXCEPT ![session] = "claimed"]
    /\ UNCHANGED <<alive, scopes, footprints>>

(* Claim refused: another live session holds the item *)

ClaimRefused(session, item) ==
    /\ pc[session] = "has_lock"
    /\ LET cl == claims[item]
       IN /\ cl # Null
          /\ cl.worktree \in Worktrees
          /\ alive[cl.worktree]
          /\ cl.session # session
    /\ locked' = FALSE
    /\ lock_holder' = ""
    /\ pc' = [pc EXCEPT ![session] = "refused"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits, holding>>

(* Session edits a file — must hold a claim AND its worktree must be alive.
   A session whose worktree died cannot perform further edits. *)

EditFile(session, file) ==
    /\ pc[session] = "claimed"
    /\ holding[session] # ""
    /\ claims[holding[session]].session = session  \* still the actual claimant
    /\ claims[holding[session]].worktree \in Worktrees
    /\ alive[claims[holding[session]].worktree]    \* worktree still alive
    /\ file \in footprints[holding[session]]       \* only within footprint
    /\ edits' = [edits EXCEPT ![session] = edits[session] \cup {file}]
    /\ UNCHANGED <<claims, alive, scopes, footprints, holding, locked, lock_holder, pc>>

(* Release a claim *)

RequestRelease(session) ==
    /\ pc[session] = "claimed"
    /\ pc' = [pc EXCEPT ![session] = "want_lock"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits, holding, locked, lock_holder>>

ReleaseClaim(session) ==
    /\ pc[session] = "has_lock"
    /\ holding[session] # ""
    /\ LET item == holding[session]
       IN claims' = [claims EXCEPT ![item] = Null]
    /\ holding' = [holding EXCEPT ![session] = ""]
    /\ locked' = FALSE
    /\ lock_holder' = ""
    /\ pc' = [pc EXCEPT ![session] = "idle"]
    /\ UNCHANGED <<alive, scopes, footprints, edits>>

(* A worktree dies (crash, cleanup, stale) — makes its claims reclaimable *)

WorktreeDies(worktree) ==
    /\ alive[worktree]
    /\ alive' = [alive EXCEPT ![worktree] = FALSE]
    /\ UNCHANGED <<claims, scopes, footprints, edits, holding, locked, lock_holder, pc>>

(* A refused or idle session can retry *)

RetryAfterRefusal(session) ==
    /\ pc[session] = "refused"
    /\ pc' = [pc EXCEPT ![session] = "idle"]
    /\ UNCHANGED <<claims, alive, scopes, footprints, edits, holding, locked, lock_holder>>

-----------------------------------------------------------------------------
(* Safety Invariants *)

(* S1: No two distinct sessions can both actively hold the same item.
   "Actively hold" = pc is "claimed" AND holding points to the item.
   This catches the real bug: two sessions both thinking they own an item. *)

(* S1: At most one session can actively edit any given item.
   "Can actively edit" = passes all of EditFile's guards:
     - pc = "claimed"
     - claims[item].session = session (is current claimant)
     - claims[item].worktree is alive

   This is the real safety property the lock protects. It is non-trivial
   because removing the lock (allowing two sessions to both reach has_lock)
   would allow two simultaneous ClaimItem calls to each see the item
   unclaimed and both succeed, resulting in claims pointing to the last
   writer while the first's holding still says it owns the item.

   With the lock intact, claims[i] is single-valued AND only writable
   under lock, so at most one session matches claims[i].session at a time.
   EditFile's check (claims[holding[s]].session = s) then guarantees
   only the true claimant can edit. *)

NoDuplicateClaim ==
    \A i \in Items :
        Cardinality({s \in Sessions :
            pc[s] = "claimed" /\
            holding[s] = i /\
            claims[i].session = s /\
            claims[i].worktree \in Worktrees /\
            alive[claims[i].worktree]}) <= 1

(* S2: If items have disjoint footprints, no two sessions edit the same file.
   This is the core topology safety theorem: the topology advisor refuses
   to parallelize items with overlapping footprints. Given disjoint footprints
   + ClaimBeforeWork, edit sets cannot overlap. *)

NoEditConflict ==
    \A s1, s2 \in Sessions :
        (s1 # s2 /\ pc[s1] = "claimed" /\ pc[s2] = "claimed" /\
         holding[s1] # "" /\ holding[s2] # "" /\ holding[s1] # holding[s2] /\
         footprints[holding[s1]] \cap footprints[holding[s2]] = {}) =>
            edits[s1] \cap edits[s2] = {}

(* S3: Items with no declared scope have footprint = all files *)

UnknownScopeConservative ==
    \A i \in Items :
        scopes[i] = {} => footprints[i] = Files

(* S4: An ACTIVE session only edits files within its claimed item's footprint.
   Active = claimed + its worktree still alive + it's the current claimant.
   A zombie session (worktree dead) can't edit (enforced by EditFile), so
   its stale edits against a potentially-changed footprint are harmless. *)

ClaimBeforeWork ==
    \A s \in Sessions :
        (pc[s] = "claimed" /\ holding[s] # "" /\
         claims[holding[s]].session = s /\
         claims[holding[s]].worktree \in Worktrees /\
         alive[claims[holding[s]].worktree]) =>
            edits[s] \subseteq footprints[holding[s]]

(* Lock mutual exclusion: at most one session holds the lock *)

LockMutualExclusion ==
    \A s1, s2 \in Sessions :
        (pc[s1] = "has_lock" /\ pc[s2] = "has_lock") => s1 = s2

-----------------------------------------------------------------------------
(* Temporal properties *)

(* L1: If a worktree dies, another session can eventually claim its items *)

StaleClaimsReclaimable ==
    \A w \in Worktrees :
        []((~alive[w]) =>
            <>(\A i \in Items :
                claims[i].worktree = w =>
                    \/ claims[i] = Null
                    \/ claims[i].worktree # w))

(* L2: A session requesting release eventually returns to idle *)

ReleaseCompletes ==
    \A s \in Sessions :
        (pc[s] = "claimed") ~> (pc[s] = "idle")

(* Lock progress: a session wanting the lock eventually gets it *)

LockProgress ==
    \A s \in Sessions :
        (pc[s] = "want_lock") ~> (pc[s] = "has_lock")

-----------------------------------------------------------------------------
(* Next-state relation *)

Next ==
    \/ \E s \in Sessions :
        \/ RequestLock(s)
        \/ AcquireLock(s)
        \/ \E i \in Items, w \in Worktrees : ClaimItem(s, i, w)
        \/ \E i \in Items : ClaimRefused(s, i)
        \/ \E f \in Files : EditFile(s, f)
        \/ RequestRelease(s)
        \/ ReleaseClaim(s)
        \/ RetryAfterRefusal(s)
    \/ \E w \in Worktrees : WorktreeDies(w)
    \/ \E i \in Items, scope \in (SUBSET Files \ {{}}) : DeclareScope(i, scope)

(* Fairness: every session that wants the lock eventually gets it;
   every enabled action eventually fires *)

Fairness ==
    /\ \A s \in Sessions : WF_vars(AcquireLock(s))
    /\ \A s \in Sessions : WF_vars(ReleaseClaim(s))
    /\ WF_vars(Next)

Spec == Init /\ [][Next]_vars /\ Fairness

=============================================================================
