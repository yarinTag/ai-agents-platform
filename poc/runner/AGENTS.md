# Isolated Runner foundation (AI-56)

This package is inactive: no startup registration, execution backend, Kubernetes
credentials, HTTP endpoint, mutation transport, workflow dispatch or host fallback.
AI-52/53/55 remain prerequisite gates, not implicitly completed dependencies.

- `models.py`: strict frozen RunnerPlan v1 binds SandboxAttempt, full profile,
  initiator/agent/environment/domain, base_version, config_revision, input digest
  and requested_at/deadline_at Unix seconds. Preparation consumes the same bounded
  lifetime as execution. Canonical JSON SHA-256 identifies the immutable plan.
  OwnedResource records kind/name/cluster-returned UID after acknowledged create.
- `kubernetes_inspect.py`: injected read-only ClusterReader protocol. No concrete
  client or credentials are provided. inspect_job requires namespace and Job UID
  receipts, exact profile/template, checks namespace first, and returns UNKNOWN
  on mismatches, defaulting or API errors. Authenticated 404 yields ABSENT only;
  it never proves process termination, authorizes replay or advances Released.
  Job completion/failure is separate from cleanup and agent output acceptance.
- Durable SQLite journal belongs to `storage/sandbox_runner.py`; see its guide.

Exact source scope, state/claim rules, integration gates and remaining work:
[AI-56 lifecycle design](../../docs/architecture/ai-56-runner-lifecycle.md).
No tests/imports/build/cluster/agent execution or other runtime verification run.
