# Capability governance

## AI-53 offline sandbox policy foundation

`sandbox_profile.py` owns strict frozen SandboxProfile/SandboxAttempt v1 contracts.
Profiles are server/operator owned, digest pinned, bounded and fingerprinted with
canonical JSON SHA-256; no approved defaults or HTTP/workflow fields are added.
`sandbox_manifests.py::build_sandbox_bundle` revalidates models and exact fingerprint
binding, then returns a per-tenant/attempt Namespace, token-free ServiceAccount,
deny-all ingress/egress NetworkPolicy, one-Pod ResourceQuota and bounded single Job.
No caller PodSpec, command, credential, persistent/host mount or network extension
is accepted. This is offline source only, with no active execution import/apply
path, cluster admission controller or claim of VM runtime verification. AI-51
decisions and cluster enforcement remain gates. Exact controls, limitations and
implementation sequence: [AI-53 design](../../docs/architecture/ai-53-sandbox-isolation.md).
No tests/imports/build/cluster or other runtime verification was performed.
Reviewed VM runtime CPU/memory overhead is a required profile field and included
in namespace quota without enlarging container limits. Actual RuntimeClass
overhead equality remains a mandatory pre-dispatch deployment check.


AI-16 introduces one shared provider-neutral policy evaluator. Exact HTTP/models,
storage, role and compatibility contracts: [capability policy v1](../../docs/architecture/capability-policy-v1.md).

- models.py: strict version1 policy/update/decision contracts, bounded exact selectors.
- registry.py: trusted immutable capability descriptors wrapping implemented adapters;
  unknown metadata cannot register execution. Unsupported roadmap operations stay blocked.
- store.py: additive SQLite policy/history, transactional compare-and-swap, atomic
  organization/department execution snapshots; revision0 means virtual inherit.
  Current policy and history reads validate stored documents and return schema
  defaults for omitted optional selectors and validity bounds.
- validation.py: personal current admin writes; department managers append restrictions
  only, validated against locked current policy; exact configured tenant resources.
- policy.py: legacy/current/frozen/identity/agent/workflow/budget intersection;
  deny wins, approval never grants. Missing context cannot evade restrictions.
- enforcement.py: actual execution admission, persisted workflow/revision/context;
  approval_path is internal-only and existing merge authorization remains mandatory.
- catalog.py: per-operation/resource/agent authoring projection; never an execution grant.

No FE, provider discovery, channel trust, callbacks, arbitrary registry installs or
generic approval continuation is introduced. Branch constraints apply only to
workspace clone/open-PR; missing branch discovery is conservative. Every owned source
must stay <=500 lines. Tests use the isolated real-HTTP API audit with external network,
subprocess and runtime disabled; no local worker/agent/model verification is authorized.

## AI-18 exact algebra
Authoritative semantics: ../../docs/architecture/p01-policy-algebra.md; exact models/API/storage: ../../docs/architecture/p01-governance-api.md. Order is denied < requires_approval < allowed; default-deny needs a matching allow, deny overrides, and every current/captured layer intersects. Captured rule times use captured_at; current times are freshly captured. Missing selectors cannot evade restrictions. Generic decide is explanatory and does not replace declared step scopes/lifetime/adapter/approval/receipt checks. Never expose approval_path or server-owned snapshots/identity as client authority. The guide documents existing source, not a new runtime prompt or generic approval continuation.

## AI-19 descriptor dependencies and effects
registry.public adds requires_capabilities from trusted operation_requirements; new GitHub comment/review effects are write. policy.decide recursively intersects required narrower reads using the same subject/resource/current/frozen gates and returns DEPENDENT_CAPABILITY_DENIED when needed. Existing explicit aggregate grants require reviewed read dependencies; no grant is backfilled. See ../../docs/github-pr-governance.md.

The Workflow Chat catalog exposes conditional GitHub comment/review capabilities only as exact_approval_tools. Catalog availability never authorizes a runtime call.

## Review: memory-backed scratch relation
SandboxProfile requires scratch_mib < memory_mib, including boundary revalidation.
This is configuration headroom, not an OOM guarantee; VM runtime overhead fields
and quota accounting remain intact. No cluster or runtime verification performed.
