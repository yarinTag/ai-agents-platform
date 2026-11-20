# AI-51: deployment boundary and first implementation slice

Status: implementation decision for initial source contracts, 2026-11-20.
Not a production, isolation, residency, HA or Air-Gap acceptance record.

## Product decision

One product supports customer-hosted and vendor-hosted dedicated data planes.
The first recommended pilot is a vendor-operated dedicated installation that can
also be handed over to the customer. Shared hosting is a later operating profile,
not an implicit extension of this one. Standalone operation must not depend on a
vendor account, licensing call, authorization service or recovery service.

The data plane owns execution, policy, inference access, MCP connections, secrets,
artifacts, execution logs, security audit and backups. A future optional vendor
management service receives only explicitly selected installation version,
update-availability and categorical health fields. It has no execution authority.
Health codes must be server-defined categories, never exception strings or user
content. This slice implements no management connection.

Customer-hosted means all declared customer-data services remain in the customer
boundary. Connected operation may still need approved infrastructure destinations;
it does not permit external inference under this profile. A different product
profile would be needed for customer-managed execution with external inference.
Vendor-hosted dedicated permits declared customer/external services with an exact
service-level egress inventory. That inventory is a disclosure, not network policy
or consent evidence. Remote MCP access never proves that returned data stays local.

## Implemented offline contract

`poc/governance/deployment_profile.py` defines strict frozen operator declarations:

- DeploymentProfile v1: installation_id, organization_id, revision, mode
  customer_hosted|vendor_hosted_dedicated, connectivity connected|air_gapped,
  database postgresql, continuity approved_artifacts, service placements,
  approved_data_egress, management_enabled and management_metadata.
- ServicePlacement: service, boundary customer|vendor|external, registry resource_id.
  Every one of the nine service categories must occur; multiple resources per
  category are allowed, duplicate category/resource identities are rejected.
- Execution, policy and secrets remain in the selected local data plane.
  approved_data_egress exactly matches categories placed outside that boundary.
  Customer-hosted permits none. Air-Gap requires customer-hosted, no remote
  services and disabled vendor management.
- Fingerprinting revalidates instances, sorts inventory/set fields and hashes
  canonical JSON. A fingerprint binds a declaration; it is neither signature,
  permission, operator approval nor proof of the actual service destination.

These are internal Python models only. No API, environment parsing, active policy
registration, connection, schema migration or startup wiring is added. No default
approved deployment exists. A future registry must resolve resource_id to trusted
current tenant-owned configuration and observed enforcement evidence; a model or
workflow cannot populate an authoritative declaration. Nested runtime resources,
TLS identities, DNS/redirect validation and support grants are separate contracts.

## Joint AI-52/55 implementation boundary

AI-52 owns repository interfaces, production schema, migrations, transactions,
retention and backup/restore. PostgreSQL is the production target, not a claim that
the active SQLite repositories already support it. Inventory SQLite-specific SQL
before conversion. Keep one authoritative production persistence path; do not
quietly place attempts in PostgreSQL while authorization remains in SQLite.

AI-55 owns durable attempts and logical effects. Extend/reuse the AI-56 journal
from PR58 instead of adding a competing journal in this checkout. That existing
journal is not a distributed lease or complete effect ledger. Required design:

| Identity | Meaning |
| --- | --- |
| execution/task | Logical requested work and recorded authorization context |
| attempt | One bounded execution attempt with immutable input/config binding |
| effect | One publication intent, stable across retries of that same intent |
| owner epoch | Monotonic ownership fence checked at the effect broker |
| recovery epoch | Invalidates surviving attempt authority after restore |

Intent is committed before dispatch; receipt is persisted after acknowledgement.
Changed payload with an existing effect ID conflicts. UNKNOWN effects cannot be
replayed just because a lease expired. Provider-specific idempotency/conditional
operations or explicit reconciliation are required. Local fencing cannot recall
an already dispatched request or force an arbitrary provider to reject it.
Execution result, effect result, artifact promotion and cleanup remain separate.

AI-56 owns infrastructure lifecycle and exact UID receipts. It consumes AI-52/55
contracts. Job absence and force deletion do not establish process termination.
No new Runner copy or active execution path is introduced by AI-51.

## Delivery gates

1. Freeze the first profile and unresolved targets below; finalize AI-52/55 schema.
2. Implement persistence/ownership with crash, tenant and migration coverage.
3. Verify one sandbox runtime/node/CNI/admission combination with AI-53/56.
4. Read-only vertical slice: authorized Git input, model, artifact, scoped logs,
   revocation and observed cleanup. Minimum packaging supports this slice.
5. AI-76 remote MCP with current per-call grants and schema drift handling;
   AI-77 private connectivity only where topology requires it.
6. AI-63 publication with genuine receipts and UNKNOWN reconciliation.
7. AI-66/69/75 installation, upgrade and restore acceptance in AI-74.
8. AI-67 offline bundle and separate Air-Gap acceptance in AI-74.

## Open operational decisions

Exact Kubernetes/runtime/CNI/storage versions, inference model/server and Git
product; capacity, latency and quality targets; availability topology and RPO/RTO;
support grant approvers/TTL; retention and backup encryption/key custody. No
numerical targets or vendor choice are invented here. Infrastructure/provider
acceptance still requires separately authorized real environments.

## Evidence

Source review only; no tests, imports, builds, startup, DB writes, provider calls
or deployment were executed. Contract test source is test_deployment_profile.py.

- Kubernetes Job duplicate starts: https://kubernetes.io/docs/concepts/workloads/controllers/job/
- Isolation boundaries: https://kubernetes.io/docs/concepts/security/multi-tenancy/
- SQLite suitability: https://www.sqlite.org/whentouse.html
- MCP security: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/docs/2026-07-28/tutorials/security/security_best_practices.mdx
