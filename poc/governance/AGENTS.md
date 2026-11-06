# Capability governance

AI-16 introduces one shared provider-neutral policy evaluator. Exact HTTP/models,
storage, role and compatibility contracts: [capability policy v1](../../docs/architecture/capability-policy-v1.md).

- models.py: strict version1 policy/update/decision contracts, bounded exact selectors.
- registry.py: trusted immutable capability descriptors wrapping implemented adapters;
  unknown metadata cannot register execution. Unsupported roadmap operations stay blocked.
- store.py: additive SQLite policy/history, transactional compare-and-swap, atomic
  organization/department execution snapshots; revision0 means virtual inherit.
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
