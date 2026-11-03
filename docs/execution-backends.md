> Superseded status (2026-11-03): the opt-in Claude read-only hosted SDK slice is now implemented in source. See [current hosting contracts and limitations](claude-hosted.md). It is disabled by default, native Linux only, and unverified. The foundation/history below does not describe a deployed or tested runtime.

# Execution backends: incremental implementation

## Implemented foundation (2026-11-03)

The model provider and execution engine are different concepts. runtime/execution_backends.py owns the immutable ExecutionBackend inventory and capability/admission contract. It does not replace the existing RuntimeAdapter registry, which still owns application-level task lifecycle. No SDK or CLI is installed, invoked or made executable by this change.

IDs:

| ID | Transport | Implemented platform integration |
| --- | --- | --- |
| direct_api | platform_worker | Existing Direct HTTP worker |
| claude_code | claude_agent_sdk | Pending isolated hosting integration |
| codex_cli | codex_exec | Pending isolated hosting integration |
| antigravity_cli | agy_headless | Pending isolated hosting/authentication integration |

Claude Agent SDK is selected as the planned Claude Code transport, rather than manually maintaining raw CLI process protocol. Its Python SDK manages a Claude CLI subprocess; the whole SDK and child process must run inside the isolation boundary. SDK installation is not an isolation control. ant CLI is an API client, not an execution backend.

Reference: https://code.claude.com/docs/en/agent-sdk/hosting and https://code.claude.com/docs/en/agent-sdk/secure-deployment . Source was read; no hosting claims were dynamically verified.

## Persisted contract and compatibility

Workflow definition.settings.execution_backend accepts direct_api, claude_code, codex_cli, antigravity_cli. Omission defaults to direct_api. No database migration is needed: settings remain revisioned definition JSON. params.execution_backend on an individual step overrides the workflow default; missing/null step values inherit. Empty, unknown or provider IDs such as direct_openai are errors, not defaults. Provider credentials and models retain their separate existing contracts.

Known pending engines can be saved through YAML/API for authoring but cannot execute. The settings UI displays them disabled with a pending label, preserves a pending saved selection, and explains that it blocks execution. Returning to Direct API is an explicit user choice. Per-agent/organization engine defaults and native AI-chat engine proposal fields are not yet implemented.

GET /api/v1/workflows/{id}/settings adds settings.execution_backend and execution_backends. Each descriptor contains id, name, transport, implemented, requires_container, supports_playground, supports_governed_connectors, credential_provider, unavailable_reason, verification=source_contract_only. implemented describes source integration only; it never claims installed, authenticated, verified or production-ready. Claude's intended credential provider is direct_anthropic, Codex's direct_openai; Antigravity is null until its authentication contract is established.

PUT settings uses existing current-DB manager authorization, expected_revision, full definition validation and revision/audit path. Workflow settings audit includes execution_backend. Workflow JSON/YAML round trips preserve root settings and step params.

## Admission

workflows/backend_policy.py owns definition inheritance, whole-DAG preflight and persisted task lookup. Engine preflight runs after parsing, before preparing connector contexts, start notifications and executing any steps. A pending engine in any AI step fails the execution before earlier steps perform work. Deterministic channel_action steps do not start model runtimes, so engine admission does not apply to them; their separate governed-action validation remains mandatory.

TaskExecutor also gates the persisted task's backend before subprocess launch, independently of engine preflight. Workflow/Playground task IDs with missing lineage fail closed. Reviews inherit the workflow parent backend when present; ordinary non-workflow tasks retain Direct API. Missing saved workflows or steps fail instead of defaulting. This foundation does not add durable definition snapshots for active runs; existing revision/deduplication semantics remain and current settings are rechecked at task admission.

Accepted tasks record an execution_backend runtime event with backend and transport; StepEventTimeline gives it an Execution engine row. No hidden reasoning is exposed and no new CLI tool logs are claimed.

## Next implementation milestones

1. Claude hosted worker: pin an audited SDK version and container digest, compile a server-owned launch plan, run Python SDK and bundled Claude process as non-root in the container. Mount only the approved checkout plus isolated writable session/temp state, no host home or Docker socket. Define resume and restart storage semantics before advertising support.
2. Credential/model-request proxy outside the agent container: exact run/org binding, fixed upstream endpoint, current user/department policy, key version/revocation and budget reservation/settlement per call. Never inject organization model keys into model-directed shell environments. Keep model API egress separate from user-configured tool egress; prompts cannot select an upstream URL or organization.
3. SDK permissions and hooks: explicit built-in tool inventory, repository instruction policy, no ambient plugins/MCP/hooks, governed callback protocol for approvals and external effects. Receipts remain required for PR/channel actions. SDK subagents must not create unaccounted grants, runtimes or spending paths.
4. Normalize SDK messages and hook events into existing runtime activity/result/usage contracts; redact secret material and opaque continuation. Bound output, tool-call duration, total lifetime and process trees. Cancel the container, not only docker exec. Distinguish provider finish from workflow business completion.
5. Connect the hosted worker to workspace preparation/cleanup and execution admission. Only then change Claude's implemented flag and capabilities, supported by integration evidence. Add organization defaults, step UI and authoring catalog selection without silently changing existing definitions.
6. Add Codex through the same hosting/policy contracts, with its own event/session/auth adapter. Add Antigravity only after headless authentication, model capabilities and container behavior are established. Unsupported capabilities remain explicit errors.

## Deferred verification

No tests, builds, lint/type checking, imports, startup, Docker, installation or provider calls were executed. test_execution_backends.py supplies unexecuted policy and real-SQLite contracts for default compatibility, strict IDs, round trips, inheritance, whole-DAG blocking and persisted task identity. Pending: real FastAPI settings authorization/revision regression, workflow fail-before-side-effects integration, rendered UI and every hosted-engine test. A source-only descriptor is not evidence of successful hosting.
