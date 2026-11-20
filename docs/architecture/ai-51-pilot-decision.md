# AI-51 pilot decision for approval

Status: ACCEPTED PRODUCT BASELINE, 2026-11-20. Targets below are
acceptance requirements, not measured capability or a customer SLA.
Yarin explicitly approved the pilot baseline and targets in this chat. This is
a product/architecture decision; it does not approve a deployment.

## Selected product boundary

One organization per installation for the first pilot, with multiple departments
and project access domains. Offer the same autonomous data plane in two locations:
customer infrastructure, or a dedicated installation operated by the vendor.
The customer owns its data and chooses the location. No shared customer database,
worker pool, credentials, artifact bucket or content-bearing log sink in this
pilot. Shared infrastructure is a later security and operating decision.

Treat repository code, dependencies, skills, tool results and retained artifacts
as potentially hostile. Select a VM-isolated Kubernetes RuntimeClass using Kata
Containers, on dedicated worker nodes separated from control-plane and broker
nodes. Neither a namespace nor an ordinary container is the hostile-code boundary.
No runtime fallback is permitted. Actual runtime, hypervisor, kernel and CNI
compatibility is a mandatory AI-53/56 deployment gate.

Use Direct API as the first inference transport; the customer supplies an internal
model endpoint in customer-hosted mode. Vendor-hosted mode requires an explicit
per-installation disclosure and approval of each inference endpoint. No default
cloud model, environment credential fallback or automatic provider failover.
The customer supplies the model/server/hardware inventory; AI-54 selects and
pins one combination after the quality benchmark below. API compatibility alone
does not certify tool calling. CLI engines and full conversation/home resume
remain outside this pilot.

## Reference implementation profile

| Component | Pilot choice | Acceptance owner and gate |
| --- | --- | --- |
| Kubernetes | v1.36 minor reference; exact maintained patch and distribution recorded before installation | Infrastructure owner, AI-53/56; conformance and node-failure evidence |
| Isolation | Kata VM runtime on dedicated Linux workers with hardware virtualization; exact release/kernel/hypervisor pinned in installation lock | Security + infrastructure, AI-53/56; deny unsupported hosts |
| Networking | Cilium with default-deny ingress/egress; explicitly addressed internal brokers; deny node, metadata and control-plane access | Security, AI-60; observed packet tests, including DNS and redirects |
| Persistence | PostgreSQL 18 reference, one authority for configuration, authorization, attempts and effects | Backend + operations, AI-52/55; migration and restore before cutover |
| Git | Customer-owned GitLab HTTPS repository for the first internal slice; exact version, CA and repository pinned per installation | Customer Git owner + integrations, AI-62; read-only acceptance first |
| Model | Customer-owned internal tool-capable endpoint through Direct API; exact model revision/server/image/hardware pinned after benchmark | Customer inference owner + AI lead, AI-54; no automatic substitute |
| Artifacts | Installation-owned encrypted object storage with versioning; temporary writable scratch per attempt | Backend + security, AI-57/58/65; provenance and item-level authorization |
| Packaging | Digest-pinned signed images and installation lock with SBOM, dependencies and compatibility evidence | Infrastructure, AI-66/67; offline variant has a separate gate |

This is a reference selection, not a supported-version certificate. A lock must
identify exact patches/digests for every row before execution. If the customer
cannot supply the selected Git/model/virtualization profile, stop and approve a
replacement ADR; do not silently substitute public Git, external inference or a
weaker sandbox. No public GitLab/cloud account or new infrastructure is provisioned
by this decision.

## Continuity, concurrency and authority

Persistent agent identity is organization/agent plus versioned configuration.
The memory domain is organization/project/access group, with provenance and ACLs
on every retained item. Different initiators do not automatically share access.
Every attempt gets a fresh checkout and private writable scratch. Persist only
explicitly approved artifacts; no restored home, executable hooks, caches of
credentials or automatic plugin/session loading.

Allow one writer per domain, enforced with durable ownership epochs and head CAS.
Parallel reads may use immutable authorized versions. Start with four admitted
attempts per installation; serialize additional work in the durable queue. An
approval records the exact evidence/action; it never adds a capability. Sensitive
publication requires a linked personal approver with current authority who is
independent of the initiator/author. Artifact promotion, external effect receipt,
execution completion and verified cleanup remain separate outcomes.
If a node is unreachable, absence from the API or elapsed cancellation time does
not prove termination. Keep the attempt unreleased and fence broker authority;
do not start a replacement writer on the assumption that the old process died.

## Information routes, failures and updates

| Route / data | Destination and authority | Failure/update behavior and evidence |
| --- | --- | --- |
| Browser: identity, prompts, results, logs | Installation HTTPS API; current tenant/department checks on reads and writes | No vendor analytics/CDN scripts; reconnect rereads scoped records; bundle dependencies locally |
| Git: source, commits, patches | Exact customer repository through internal broker and CA | No public mirror or credential fallback; redirect/DNS validation; unknown writes reconciled before retry |
| Model: prompts, code, tool results, output | Selected internal inference endpoint in closed profile | Endpoint failure blocks the run; no external retry; customer inference operator controls its own logs |
| MCP: arguments/results and secrets | Exact installation-approved server through per-call broker policy | No arbitrary URL/model-granted tool install; revoke/drift fails closed; provider logs disclosed in inventory |
| Worker: input, scratch, outputs | Per-attempt VM sandbox; outputs scanned/promoted through artifact service | Failure quarantines output; no automatic promotion; independent cleanup receipt and process-termination check |
| Database and effects | Installation PostgreSQL, encrypted backups in same approved boundary | Restore invalidates old attempt authority; reconcile UNKNOWN provider effects before enabling dispatch |
| Logs/audit: identity, decisions, usage, receipts | Installation log/audit stores; tenant-scoped views and separate infrastructure access | Redact secrets/content by policy; no raw payload forwarding to central vendor monitoring; export audited |
| Registry and plugin packages | Installation registry; approved signed/pinned packages | Stage and verify updates before use; never fetch missing dependencies during a closed run |
| Model discovery and UI assets | Local configured catalog and bundled assets | No public discovery/fonts/CDN fallback; unknown model blocks authoring/execution |
| DNS, NTP, CA and identity | Approved internal resolvers/time/CA/identity endpoints | Fail closed on TLS/identity failure; no alternate public resolver or clock endpoint |
| Licensing, telemetry and support | No online licensing or mandatory telemetry; optional categorical management metadata only | Standalone execution/recovery works without vendor; support access disabled by default |
| Upgrade, crash dumps and diagnostic export | Local staging and approved encrypted backup destination | Dumps may contain customer data and stay local; customer reviews/redacts any support export first |

Customer-hosted connected, vendor-hosted dedicated and Air-Gap have separate egress
inventories. A private tunnel does not change where a model or MCP processes data.
Air-Gap requires all registry/model/plugins/identity/time/update dependencies inside
the boundary and offline signing/revocation recovery in AI-67/74; it is not claimed
by acceptance of the connected pilot.

## Responsibility and operating model

Product owner: Yarin, or a named delegate recorded before sign-off. The product
owner accepts target/scope tradeoffs. Infrastructure owner signs the installation
lock; security owner signs isolation/egress/threat assumptions; backend owner signs
authority/migration/fencing; AI owner and customer inference owner sign model
quality. One person may hold multiple roles in a small pilot, but the named
sign-off and independent sensitive-action approver requirements remain recorded.

Customer owns repository/model credentials, identity policy, allowed data locations,
data-retention policy and customer-hosted infrastructure. Vendor owns product
patches and source contracts. Vendor operations owns dedicated hosted infrastructure;
customer operations owns customer-hosted uptime and keys. No operator automatically
has application tenant-data access. Support sessions require customer approval,
named individual, exact scope, audit and a maximum one-hour TTL; no standing access.

First pilot is single-active application/controller and single-primary database,
with durable storage and tested recovery, not zero-downtime HA. Disclose this before
onboarding. A future HA profile needs independent capacity/failover acceptance.
Existing SQLite installations remain on SQLite until full AI-52 migration passes:
backup, isolated rehearsal, counts/hashes/constraints/permissions, controlled writer
freeze, restore rehearsal, explicit cutover and reconciliation. A second database
must not become an independent authorization authority.

Encryption keys are installation-specific and kept outside database/artifact
backups in the approved local key-management boundary. In customer-hosted mode
the customer security owner holds recovery custody. In dedicated vendor-hosted
mode vendor security operates the key service under customer-approved policy;
access to key administration and backup restore requires two named custodians
and an audit record. Support operators receive neither key exports nor recovery
shares. Maintain a separately encrypted recovery copy under the same residency
policy, test restoring it with the data, and record key versions before rotation.
Losing all recovery copies makes encrypted data unrecoverable: do not bypass
encryption or silently reset keys. Suspected compromise requires revocation,
rotation, affected-attempt invalidation and review of already dispatched effects.

Before upgrade, pause new dispatch, drain or explicitly fence active attempts,
verify a consistent backup and restore drill, and compare the old/new server,
schema, broker and worker compatibility matrix. Preserve the effect ledger and
receipts across the boundary. Roll back binaries only against a schema explicitly
declared compatible. For an incompatible migration, restore into an isolated
installation, invalidate surviving authority, and reconcile all post-backup
effects before opening dispatch. Failure remains a visible maintenance state;
never run mixed incompatible writers or automatically replay uncertain effects.

## Proposed numeric pilot acceptance targets

| Measure | Target and method | Gate / accountable role |
| --- | --- | --- |
| Task quality | At least 18/20 fixed representative tasks satisfy human-reviewed acceptance criteria; no hidden retries; report interventions | AI-54, AI owner + product |
| Tool safety | 0 unauthorized effects or cross-tenant disclosures across the security suite; malformed/uncertain outputs fail closed | AI-53/58/59/60/74, security |
| Capacity | 4 simultaneous attempts in distinct domains; 1 writer/domain; reference hardware recorded; 100-run soak | AI-55/56/64/74, infrastructure |
| Preparation | p95 <=120 seconds from admission to verified Ready, cached signed images and input <=100 MiB; cold pulls measured separately | AI-56/62/74, infrastructure |
| Task duration | p95 <=10 minutes on the frozen 20-task benchmark, including model/tool latency; 15-minute hard attempt deadline | AI-54/56/74, AI + infrastructure |
| Cancellation | New broker actions denied within 5 seconds of committed revocation; process termination evidence within 60 seconds; dispatched requests may require reconciliation | AI-55/56/59/74, backend + security |
| Cleanup | p95 <=120 seconds after termination; stuck resources visible within 60 seconds; never label Released without evidence | AI-56/69/74, infrastructure |
| Availability | 99.5% monthly API availability target during agreed pilot observation; planned maintenance counted and disclosed; no contractual SLA | AI-69/74, operations |
| Recovery | RPO <=15 minutes for DB/artifact metadata and accepted artifacts; RTO <=4 hours in an isolated full restore drill, including authority invalidation/reconciliation | AI-52/55/69/74, operations |
| Retention | Execution content 30 days; security audit 180 days; encrypted backups 30 days; customer-approved changes before ingestion | AI-57/69, customer data owner |

Freeze the twenty benchmark tasks, expected artifacts and intervention/retry
rules before measuring. Quality acceptance does not replace security acceptance.

Budgets must be explicit per department before a run; GPU/inference is customer
supplied and no numeric currency rate is invented. Preserve provider-reported,
estimated and unavailable prices distinctly. Cost of four concurrent VM attempts
(not necessarily four worker nodes), dedicated
storage and operational backup is higher than shared hosting; reduce concurrency
through an approved target revision rather than reducing isolation.

## Decision and review record

The product owner approved the choices/targets above. Security/infrastructure/model
compatibility certificates remain implementation gates with the owners above,
not open product defaults. Architecture review scenarios: hostile dependency tries
metadata access; two writers race promotion; approver is revoked; node is lost
after provider dispatch; restore finds a surviving worker; model endpoint fails;
registry is unavailable during upgrade; support asks for raw logs. For each case
the contracts above require bounded access, fail-closed admission and explicit
reconciliation without automatic data export or authority expansion.

Approval record, 2026-11-20: Yarin answered “מאשר את בסיס הפיילוט והיעדים” to the
concrete packet and numerical targets. Independent architecture Advisor reviewed
the packet against the deployment/sandbox models and failure scenarios. Its three
required clarifications (supersession, encryption-key custody/recovery and bounded
upgrade rollback) are incorporated here. Unreachable-node and benchmark-freezing
clarifications are also incorporated. This source review is not a deployment,
security penetration test or certification by customer infrastructure/security
operators. Those named roles sign the installation lock at the downstream gates.
Amend this document and the installation decision history if targets or profile
change. Operational acceptance remains in the downstream tickets.

## Primary references consulted 2026-11-20

- [Kubernetes maintained versions](https://kubernetes.io/releases/): v1.36 is a maintained reference minor; patch support changes and must be checked at lock time.
- [Kubernetes multi-tenancy](https://kubernetes.io/docs/concepts/security/multi-tenancy/): deployment isolation requires more than namespace separation.
- [Cilium policy](https://docs.cilium.io/en/stable/network/kubernetes/policy/): native and extended policy types have distinct behavior; inspect the actual effective rules.
- [PostgreSQL versioning](https://www.postgresql.org/support/versioning/): use maintained releases and patch updates.
- [vLLM tool calling](https://docs.vllm.ai/en/stable/features/tool_calling/): serving/tool parser configuration is model dependent; benchmark the actual combination.
