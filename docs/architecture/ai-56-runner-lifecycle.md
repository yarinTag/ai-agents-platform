# AI-56: durable isolated Runner lifecycle

Ticket: https://trello.com/c/rWYD4MJn. Stacked on AI-53 security foundation.
Status: initial source slice; not a working Kubernetes execution backend.

## Scope and decisions

Build the Runner control-plane contract independently of model engines. A Job
gets scoped input and short-lived broker authority, never platform credentials
or Kubernetes administration. Each attempt owns a separate namespace, VM-isolated
Job and writable copy; persistent state is promoted through the separately
authorized version service. No shared writable checkout, Docker/host fallback or
inferred permission from a profile fingerprint.

AI-51 has not selected an approved runtime/cluster product profile. AI-52 and
AI-55 have not delivered the production durable state/fencing substrate. This
change does not substitute a local journal for their HA/production acceptance.
It implements immutable plans, an opt-in SQLite claim journal and read-only
Kubernetes reconciliation contract. No live create/delete transport, readiness
receipt validator or backend wiring is included. Consequently this slice cannot
advance a run to Ready, Running or Released. Those reserved states are defined
for the later verified adapter, not simulated today.

## Plan and authorization boundary

`runner.models.RunnerPlan` stores schema_version=1, nested SandboxAttempt (tenant,
attempt ID, profile hash), full SandboxProfile (image/resources/runtime/overhead),
initiator_id, agent_id, environment_id, domain_id, base_version, config_revision,
input_sha256, requested_at and deadline_at. IDs are bounded, strict and nonempty.
Deadline is an absolute server Unix timestamp; preparation and execution together
must fit profile.deadline_seconds. Retries/restarts do not reset it. Canonical
SHA-256 changes for any plan change. Profile/attempt binding is revalidated before
persisting and inspecting. No command, secret or arbitrary PodSpec is accepted.

Only a trusted future Runner admission service may construct plans. It must read
current tenant/user/agent/environment/domain authorization, profile registry,
current budget and fencing epoch before creating or continuing an attempt. The
journal does not perform those authorization checks and is not an API. Do not
expose its internal rows or claim tokens as a client-controlled execution surface.
Production migration must preserve tenant ownership and durable attempts; no
current database is opened or migrated by importing these source modules.

## Journal schema and transaction contracts

`storage.sandbox_runner.initialize(conn)` explicitly creates sandbox_runner_attempts
only on a supplied connection. It is not registered in schema initialization or
DatabaseManager. RunnerJournal accepts a transactional connection factory; normal
exit commits, failure rolls back, sqlite3.Row is required. Every mutation takes
BEGIN IMMEDIATE. Schema columns:

| Column | Contract |
| --- | --- |
| organization_id, attempt_id | Composite primary key, all reads/writes tenant scoped |
| plan_json, plan_sha256 | Full immutable plan and canonical fingerprint |
| state | Requested, Preparing, Ready, Running, Stopping, Released, CleanupFailed |
| revision | Starts at 1, increments on effective mutation |
| revoked | 0 or 1, sticky; stop/unknown outcome revokes |
| operation | Provision, Start, Stop, Delete or null |
| operation_state | IDLE, STARTED, UNKNOWN |
| claim_token | Random internal claim fence; never credentials for the agent |
| resources_json | At most five exact planned kind/name/UID acknowledged receipts |
| reason, updated_at | Server-owned bounded reason code and Unix timestamp |

No organization FK/cascade is added to this standalone source journal: deleting
an organization must not silently destroy the only cleanup receipts for a live
Job. Production integration needs explicit tombstone/retention semantics in AI-52.
This journal is not a complete audit history, distributed lease system or HA DB.

- `create(plan)`: idempotent only for the exact plan in the same tenant/attempt;
  changed plan conflicts. New entries require a currently valid lifetime.
- `claim(org, attempt, revision, operation)`: revision CAS plus no outstanding
  effect. Provision: Requested -> Preparing; Start requires Ready; Stop requires
  Stopping; Delete requires Stopping/CleanupFailed. Provision/Start reject expiry
  or revocation. The claim is recorded before any future external operation.
- `record_resource`: capture every acknowledged UID immediately, including late
  create responses after cancellation. Requires the same active token and planned
  object identity; Provision cannot record a Job and Start can record only a Job.
  A replacement UID conflicts. Labels/name matches cannot adopt existing objects.
  Late receipts with the exact retained token are accepted even after UNKNOWN;
  adding provenance never clears the unknown fence or revocation.
- `finish(..., NOT_DISPATCHED)`: clear only a definitely unsent operation with no
  recorded effects. Preparing returns to Requested unless cancellation has already
  moved it to Stopping. Existing effects are conservatively rejected, even if they
  predate this claim; a future per-operation receipt ledger must refine this.
- `finish(..., UNKNOWN)`: retain the claim and resource records, revoke authority
  and enter CleanupFailed. No automatic replay, lease expiry takeover, retry counter
  reset or operator-provided success boolean exists. A crashed STARTED claim stays
  fenced until explicit future reconciliation; it is not automatically reclaimed.
- `request_stop`: idempotently persist revocation and Stopping before cleanup.
  Preserve STARTED/UNKNOWN claims and all UIDs. Late acknowledged effects remain
  recordable. Stop never declares termination or releases resources.

## Read-only Kubernetes adapter contract

`inspect_job(reader, plan, owned)` builds paths from validated plans and expected
manifest names, not user URLs. ClusterReader.get must use a fixed trusted cluster,
authenticated TLS, no redirects/environment auth, deadlines/response bounds, and
map only authenticated HTTP404 to None. Errors and malformed data yield UNKNOWN
without provider bodies. No concrete transport is implemented in this slice.

The inspector first verifies the recorded namespace UID, then exact Job UID and
profile annotation. A replaced namespace/Job is UNKNOWN. API-defaulted or mutated
templates are UNKNOWN until a reviewed structural comparison is supplied; no
generic ignore-unknown-fields policy is used. Conditions report TERMINAL only for
unambiguous Job Complete/Failed; PRESENT does not mean the agent is ready. ABSENT
does not prove that a partitioned node stopped its process. Neither absence nor
terminal Job conditions may advance Released or clear UNKNOWN effects.

## Next implementation gates

1. Complete approved AI-51/53 cluster profile, VM RuntimeClass/overhead/node proof,
   CNI and fail-closed admission. AI-52/55 supply production state and fencing.
2. Implement trusted transport and durable per-effect ledger. Provision namespace,
   token-free SA, quota and deny-all network in order. Record each UID, reject
   collisions; reconcile ambiguous creates without adopting names alone.
3. Stage the authorized input manifest and independently verify its digest and
   disposable copy before Ready. No model decides its own readiness.
4. Start creates exactly one approved Job after current policy/deadline/fence
   checks. Job activeDeadlineSeconds uses remaining absolute lifetime, not the
   original full timeout. No Job retry without a fresh attempt and authorization.
5. Reconciliation records Job UID and subordinate Pod ownership, node loss,
   missing callbacks, image pull/resource/CSI errors and cancellation. Never
   replay an UNKNOWN model/PR effect. Reconcile reads separately from mutations.
6. Stop revokes broker authority before terminating the whole process/VM tree.
   Delete uses UID preconditions, foreground propagation and observed cleanup.
   Released requires no in-flight effects, observed resource/volume/network
   removal AND reliable process termination evidence, including partitioned nodes.
7. Wire opt-in orchestration only after previous gates; no fallback. Add startup
   recovery, retention/tombstones and explicit audited operator reconciliation.

Acceptance requires real authorized Kubernetes tests for restart races, parallel
claims, cancellation during provisioning/start, late responses, lost nodes,
ownership replacement, image pull failure, capacity exhaustion, CSI failures,
admission failure and complete cleanup. Source-only SQLite tests cover initial
claim fencing and tenant/plan identity; they do not establish cluster behavior.
Tests, builds, imports, startup and live infrastructure verification were not run.

## Independent source review

A separate review agent inspected AI-53 and AI-56 source without modifying it or
running tests. AI-53 findings led to required fingerprinted VM overhead in quota,
single-character RuntimeClass validation and documented restricted image grammar.
AI-56 review identified loss of late UID evidence after UNKNOWN; record_resource
now accepts only the exact retained token for receipt storage while retaining
revocation and the UNKNOWN replay fence. A source regression covers that case.
The reviewer confirmed the fixes and found no further blocking defect in this
inactive slice. A duplicated validation block identified during re-review was
removed. This is independent AI source feedback, not human security certification,
executed tests or cluster acceptance evidence.
