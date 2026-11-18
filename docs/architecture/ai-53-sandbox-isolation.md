# AI-53: isolated agent execution security contract

Status: design and offline manifest foundation only. Ticket: https://trello.com/c/4vFkfkOy.
AI-51 product decisions remain open. No runtime, Kubernetes API, Docker, model,
deployment or tests were executed. Nothing in this document approves a cluster.

## Threat model and proposed first boundary

Treat repository content, instructions, plugins, build scripts, model output,
dependencies and generated artifacts as potentially hostile. Assume the agent
can execute arbitrary code and fork subprocesses. Protect other attempts and
tenants, host files and kernel, platform database, credentials, orchestration
authority, artifact integrity and cluster capacity. A prompt is not a security
boundary. The API/Runner control plane, admission configuration, internal brokers,
approved image registry and cluster operators are trusted infrastructure.

Proposed first profile: one Linux VM-isolated runtime sandbox per attempt, one
namespace per attempt and a tenant-dedicated node pool. Ordinary shared-kernel
containers are insufficient for this proposed hostile-code profile. No particular
runtime vendor or Kubernetes release is approved here. Security/infra must choose
and verify the RuntimeClass implementation, node scheduling constraints and
supported release before enabling a Runner. A RuntimeClass name alone proves
nothing about its handler, kernel boundary or placement. Hardware side channels,
malicious cluster administrators and host compromise require separate controls;
this profile makes no claim to solve them.

## Current source evidence

- `poc/workflows/repo_sandbox.py`: Docker repository container, non-root,
  read-only root, dropped capabilities, limits, isolated network/optional proxy;
  checkout is host-cloned, separate from host Git metadata. No Kubernetes adapter.
- `poc/runtime/claude_hosted/containers.py`: separate worker/relay, read-only
  checkout, private network and broker capability; Docker lifecycle only.
- `poc/governance/policy.py` and `enforcement.py`: current/frozen capability
  intersection remains authoritative. Sandbox construction grants no tool access.

Existing Docker execution is unchanged. It is not silently promoted to this
profile or represented as VM isolation. AI-56 owns the eventual Runner lifecycle;
AI-52/55 own durable identity/state/fencing. AI-59/60 own broker and network IO.

## Initial source contracts

`governance.sandbox_profile.SandboxProfile` is strict, frozen operator-owned
configuration. It binds schema version 1, profile ID/revision, proposed
`vm-isolated` isolation, explicit runtime class/Kubernetes minor, image digest,
non-root IDs, bounded CPU/memory/scratch and deadline. Unknown keys, implicit type
coercion and unpinned images are rejected. No default approved profile exists.
RuntimeClass configuration intentionally accepts the lowercase DNS-label subset
(including one-character names). Images require an explicit DNS registry, optional
numeric port and simple lowercase repository components; tags, implicit registries,
IPv6 registry literals and empty path components are outside this initial contract.
CPU/memory RuntimeClass overhead is explicitly recorded and fingerprinted. Namespace
quota includes it while container limits remain unchanged. Deployment must compare
the approved overhead to the actual RuntimeClass before creating a Pod; zero is an
explicit operator assertion, not evidence of a free runtime. See
[Pod overhead](https://kubernetes.io/docs/concepts/scheduling-eviction/pod-overhead/).
SHA-256 of canonical JSON binds every profile field; it is an integrity identifier,
not a signature or approval. Images still require provenance, scan and explicit
operator approval before a profile is registered.

`SandboxAttempt` contains server-derived organization ID, a fresh 32-character
hex attempt ID and exact profile SHA-256. It carries no secrets. These classes
are internal source contracts, not new API endpoints or workflow fields. A future
server registry must resolve current approved profiles; workflow/model input must
never construct an authoritative profile or attempt. Recheck live tenant/user,
budget, expiry, revocation and fencing before dispatch and broker effects.

`build_sandbox_bundle` revalidates both objects and rejects mismatched profiles.
It returns Namespace, ServiceAccount, deny-all NetworkPolicy, ResourceQuota and
single Job dictionaries. Namespace uses a tenant hash and attempt ID (61 chars).
The Job records the profile fingerprint on Job and Pod-template annotations.
It has no retries, one Pod, a deadline and an approved image entrypoint. There is
no caller command, PodSpec, environment extension, image override or host mount.
No service-account token, RBAC binding, secret, PVC, init container, sidecar,
host namespace, provider key or network exception is emitted. Root is read-only;
only a bounded memory-backed `/tmp` is writable. All capabilities are dropped,
privilege escalation disabled, non-root IDs and RuntimeDefault seccomp required.
Memory-backed scratch also consumes the container memory budget.

This first bundle has no input staging, model connection or artifact export.
It is deliberately an offline policy foundation, not a usable inference Runner.
No code imports it from an active execution path. No apply helper is supplied.

## Mandatory cluster gates before any Job creation

1. AI-51: freeze threat model, tenant topology, runtime and supported Kubernetes
   release, continuity semantics, capacity and cancellation objectives in an ADR.
2. Prove runtime handler is VM-isolated and uses the approved dedicated nodes.
   Enforce scheduling with protected node labels, admission-owned selectors and
   taints/tolerations; agents cannot choose nodes, scheduler or RuntimeClass.
3. Configure kubelet `podPidsLimit`, node PID reservation and eviction limits.
   Kubernetes has no portable per-Pod PID resource field; the renderer does not
   invent one. Prove subprocess limits and total process-tree cancellation.
4. Install and test CNI enforcement for IPv4/IPv6, metadata, node-local services,
   control plane, cross-attempt/tenant traffic and DNS. Default deny includes DNS;
   no cluster/model/Git destination is implicitly trusted. NetworkPolicy rules
   are additive: another allow policy can reopen access and must be rejected.
5. Enforce pinned-version Restricted Pod Security without exemptions. Add
   fail-closed admission for exact profile/image, VM runtime, nodes, token denial,
   mounts, resources, immutable bindings and prohibited mutations/subresources.
   Restricted alone does not enforce the full platform profile. Cover direct
   Pods, controller templates, updates, ephemeral containers and injected sidecars.
6. Restrict Runner RBAC to necessary managed resources. Workers get no Role or
   RoleBinding. Constrain exec/attach/debug/token/impersonation and policy changes
   to infrastructure principals. A no-token setting does not revoke existing RBAC.
7. AI-56 applies and observes namespace, quota, SA, PSA/admission/network gates
   before creating a Job. Reconcile object ownership/UIDs on retry; never adopt a
   pre-existing namespace based on a name or label alone. Current-policy failure
   aborts before scheduling. No fallback to host or weaker Docker execution.
8. Cancellation revokes broker authority and deletes the whole workload;
   Released requires observed cleanup. A Job deadline is not a cleanup receipt.
   No TTL deletion in this slice: preserve objects for reconciled audit/cleanup.

## Staged implementation and acceptance

| Stage | Deliverable | Required evidence |
| --- | --- | --- |
| Initial source (this change) | Strict profile/attempt, offline closed bundle, denial test source | Source review only; tests unexecuted |
| Product/security decision | AI-51 ADR and approved profile registry | Reviewed versioned policy and selected runtime/node boundary |
| Cluster admission | Fail-closed policy and minimal Runner permissions | Rejection of hostile Pods/templates, sidecars and updates on real cluster |
| Runner integration (AI-56) | Durable prepare/start/stop/reconcile protocol | Restart, deadline, cancellation and verified cleanup |
| Broker/IO integration | Scoped input/model/artifact paths with independent current authorization | Revocation and destination substitution denial; no raw credentials |
| Security acceptance | Hostile agent plus subprocess tests | Isolation, resource and network evidence tied to runtime/CNI/node versions |

Negative test matrix must cover hostPath/socket/proc access; symlink traversal;
privileged/root/capability escalation; token/metadata/control-plane access;
cross-tenant/attempt reads and packets; DNS/IPv6/proxy bypass; fork/storage/memory
bombs; admission outage; mutated or unapproved image/runtime; additional network
allow rules; unauthorized debug containers; cancelled/stale attempt broker calls;
node loss; cleanup failure; compromised artifact and snapshot import. Test against
actual isolated infrastructure when authorized, with no simulated success.

AI-53 is not Done until those cluster checks and an approved boundary exist.
Local runtime verification remains prohibited by repository instructions.

## Upstream basis

- [Kubernetes application security checklist](https://kubernetes.io/docs/concepts/security/application-security-checklist/)
  for service-account token denial and enforced network policy.
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
  for Restricted controls; platform-specific admission is still required.
- [PID limits](https://kubernetes.io/docs/concepts/policy/pid-limiting/)
  for node/kubelet limits rather than a fictitious Pod resource.
