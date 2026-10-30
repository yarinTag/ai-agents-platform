# Workflow Assistant: model-only authoring and governed YAML

## Scope and components

The /workflow-assistant page selects an authoring model, not an agent. The configured runtime provider supplies credentials/routing. Execution agents are selected by the model per workflow step from the authorized catalog; their prompts/skills/permissions are never inherited by the authoring model.

- models.py: strict versioned HTTP requests and structured model reply; resource reference types come from workflows.authoring_schema.
- service.py: current DB identity/membership, sanitized catalog, resource/graph/trigger validation, non-executable drafts and revision history.
- generation.py: asynchronous generation lifecycle, model/provider allowlist, bounded context/budgets, actual MCP-use checks, authoritative save linking.
- yaml_contract.py: strict YAML loader and semantic conversion to/from resource-bound proposals; canonical YAML export through the runtime parser.
- tools.py: common catalog/schema/YAML-validation service used by HTTP and internal MCP.
- mcp_server.py: SDK-based internal stdio MCP transport, bound to one live authenticated generation by a mode-0600 private context file. Not a publicly installable/OAuth server.

## Identity, permissions and privacy

Every operation reloads an ACTIVE database user whose organization matches verified claims. JWT role/department lists are not authority. Department membership or current ORG_ADMIN permits reads. Current organization ORG_ADMIN/MANAGER/OPERATOR or department MANAGER/OPERATOR permits draft/model writes; organization AUDITOR/VIEWER remains read-only. Draft reads are owner-only except current authorized organization/department reviewers. Private/foreign IDs return 404.

Optional workflow-assistant:read/write scopes only reduce DB rights. source=mcp requires explicit trusted scopes. Internal MCP receives only current sub/org_id/azp, delegated scopes, fixed database path, generation and department from its parent process; no model argument can select identity, database, workspace or permissions. External OAuth/audience verification is not shipped by this module.

Generation conversations are creator-only, including against other department reviewers. Every MCP tool checks live write rights and job RUNNING status/deadline. Cancellation, expiry, membership removal or write-scope revocation prevents further calls. Tool output does not expose the private context file or credentials.

## Catalog and resource authorization

Only org-owned connectors with an active same-org department grant are visible. Unowned/global/foreign connectors are excluded. Tools must be registered and department-allowed; execution-agent grants additionally constrain step assignment, including explicit tool-ID grants. Connector availability is stored CONNECTED, not a live network test.

Only explicit configuration.allowed_repos and allowed_channels are approvals. Defaults, discovery, wildcard entries, credential URLs and non-ID objects never count. Repositories must be canonical namespace/repository IDs. Catalog output includes sanitized IDs/names/provider/availability/tools/approved destinations; no secrets, schemas, system prompts or arbitrary configuration. Agents must belong to the selected org/department; workflow runners are excluded. Skills require an org-owned project and assignment to the selected execution agent.

An empty catalog means no visible/approved connectors in this department, not no organization installations. The model must resolve internal IDs itself and ask about ambiguity by approved names. normalize_resource_clarifications replaces technical connector-ID requests with EN/HE administrator setup guidance or visible named choices, preserves unrelated questions and marks setup unresolved. Never auto-grant access.

catalog_version is a SHA-256 fingerprint of the current authorized resource view excluding user_id/can_write_drafts. It is not proof of authorization; requests rebuild current policy without a permission cache.

## Native workflow schema and validation

The canonical authoring schema is workflows.authoring_schema.WorkflowDocument (SCHEMA_VERSION=1), with a generated matching workflow-authoring.schema.yaml. It is a strict governed subset of the existing WorkflowParser syntax, not a replacement for broader legacy workflow formats. Unknown fields are rejected rather than silently dropped.

Native fields: name, description, triggers (exactly one event), cron_expression, webhook_enabled, steps, flow, metadata.unresolved_requirements. Trigger events: manual/webhook/cron/channel_message/pull_request.opened/pull_request.updated/push. Connector/repository/channel bindings on a trigger map to policy validation; irrelevant fields fail. webhook_enabled must be true exactly for a webhook trigger. cron_expression is only meaningful for cron.

Steps use key/name/agent_id/prompt_template/depends_on/timeout_seconds (1..300)/skills/mcp_servers and params {tools,repositories,channels,requires_approval}. mcp_servers must exactly match the set of connectors in those params. params are declarative bindings, not runtime enforcement. flow uses from/to; the shared parser merges its dependencies. validate_workflow_definition in workflows.parser is also the validator used by the workflow CRUD/conversion API; it checks duplicate keys, unknown edges and cycles.

YAML is limited to 200000 UTF-8 bytes. Duplicate/non-string mapping keys, anchors/aliases, multiple documents and unsafe tags are rejected. Strict native Pydantic types prevent silent scalar coercion. Canonical export round-trips through WorkflowParser and the resource proposal without semantic loss; invalid/incomplete legacy proposals may have definition_yaml=null and yaml_error, never falsely ready.

Policy validation separately checks tools, destinations, execution agents, skills, cron/events, graph and unresolved requirements. Error entries have code/path/message. No errors -> READY_FOR_REVIEW; missing inputs/unresolved requirements only -> NEEDS_CLARIFICATION; others -> BLOCKED. Unsupported approval gates remain explicit APPROVAL_GATE_NOT_SUPPORTED blockers. Questions are copied into unresolved requirements. READY_FOR_REVIEW does not activate or authorize execution; prompt semantics and actual tool calls require a future enforcement/publication gateway.

## HTTP contracts

All routes are under /api/v1/workflow-assistant and use existing platform authentication.

- GET /context: current user/org/departments/write rights, supports_generation, authoring_models [{model_id,provider_id,name}], supports_activation=false.
- GET /catalog?department_id=...: sanitized resources and fingerprint.
- GET /proposal-schema: compatibility JSON Schema for ValidationRequest, proposal_schema_version=1.
- GET /workflow-schema: workflow_schema_version=1, native JSON Schema and yaml_schema text.
- POST /validate: {department_id,proposal}; current resource policy validation.
- POST /validate-yaml: {department_id,yaml_content}; returns canonical proposal, validation and YAML artifact. Syntax/schema/graph errors return 422 WORKFLOW_YAML_INVALID; workspace failures retain 403/404. Forbidden resources return structured validation errors without executing tools.
- POST /drafts (201): {department_id,proposal,intent_text?,save_blocked=false}; optional Idempotency-Key, ASCII letters/digits/._:- up to 128. Invalid proposals need explicit save_blocked=true.
- GET /drafts?department_id=...&limit=50&offset=0: limit 1..100; current-policy status.
- GET /drafts/{id}: proposal, saved/current validation/status, catalog_changed, revision, artifact fields, executable=false.
- PUT /drafts/{id}: {expected_revision,proposal,intent_text?,save_blocked=false}. Full proposal replacement; omitted intent preserves it, empty clears it. No-op does not append history; stale revision ->409.
- GET /drafts/{id}/revisions?limit=50&before_revision=N: newest-first snapshots with actor/source/client/time, including canonical YAML for new revisions.
- POST /generations (202): {department_id,model_id,provider_id,locale=en|he,intent_text?,messages,previous_proposal?,draft_id?,expected_draft_revision?}. Model/provider must be in current runtime options; planner_agent_id is rejected. Messages: 1..20 user/assistant, each 1..8000 chars, total <=40000, last user. Original intent <=16000 chars. Draft ID and expected revision are paired. Optional Idempotency-Key as above.
- GET /generations/{id}: creator-only job/request/result, reported usage/model/cost, tool_calls [{tool_name,created_at}], and current proposal validation/artifact.
- POST /generations/{id}/cancel: terminal CANCELLED for active jobs; stopping own authorized job does not require additional write scope.
- POST /generations/{id}/save-draft: {save_blocked=false}; saves the authoritative model proposal, never arbitrary client output. Source revision CAS and generation-to-draft link are atomic.

Runtime containment: `/context` uses an optional adapter; when runtime or authoring-model inventory is unavailable, it still returns the authorized persisted workspace with `supports_generation=false` and `authoring_models=[]`. Model metadata errors do not become authorization or fabricated model data. GET generation, cancellation and saving a completed generation construct `AuthoringGenerationService` without a runtime dependency; their existing identity, membership, current-policy, status and revision checks remain authoritative. POST `/generations` alone resolves the required runtime adapter before scheduling background work. Direct service creation without a runtime raises structured `AUTHORING_UNAVAILABLE` (503) before persisting a queued generation; direct background `run` without one records an explicit failed generation through the existing error lifecycle. No successful inference is synthesized.

HTTP errors use detail={code,message,...}; strict request errors use standard FastAPI 422. Codes include USER_LOGIN_REQUIRED (401), CLIENT_SCOPE_DENIED/DRAFT_WRITE_DENIED (403), private IDs (404), PROPOSAL_INVALID/WORKFLOW_YAML_INVALID (422), IDEMPOTENCY_CONFLICT/REVISION_CONFLICT/AUTHORING_MODEL_NOT_ALLOWED (409), BUDGET_EXHAUSTED (402). Runtime errors include MODEL_TIMEOUT/MODEL_OUTPUT_INVALID/AUTHORING_TOOLS_NOT_USED/AUTHORING_CANDIDATE_NOT_FOUND/AUTHORING_CANDIDATE_INVALID. No synthetic successful reply is substituted.

## Runtime and actual MCP path

AuthoringModelSelection contains only model_id/provider_id. Runtime options reuse the existing curated model catalog and standard aliases for the configured provider; other vendor models require a compatible configured gateway. This is routing compatibility, not a live guarantee each upstream model is deployed. Provider changes between queue/start are rechecked; unknown models, unconfigured providers and permission flags cannot be supplied as model IDs.

The runtime creates an ephemeral internal config object only to drive the existing CLI; no agent is read, created, saved or dispatched. Built-in tools are empty, settings sources/skills/Chrome/hooks disabled, strict MCP config includes only the internal server, restricted mode and exact MCP allowedTools are used. safe-mode is omitted for this path because it also suppresses explicit MCP servers. OS network isolation of the provider client is not claimed. A dedicated POSIX process group covers CLI/MCP descendants and is terminated on success, cancellation and timeout. Context files are removed with the temporary directory.

Only workflow_catalog, workflow_schema and validate_workflow_yaml are exposed. No external connector invocation, file/shell tool, save, trigger activation or workflow execution is available to the model. The structured model reply is ModelAuthoringReply {assistant_message,questions,validation_id?}. The model submits native YAML only to validate_workflow_yaml, which returns an opaque wfc_ UUID reference to the exact canonical proposal stored by the server. Catalog/schema must be read through MCP; the reference must belong to that same generation. The model cannot replace the validated document in its final reply. The parent verifies the stored proposal hash and independently revalidates it against current permissions. MCP tools are not a substitute for final validation.

## Persistence, compatibility and lifecycle

SQLite schema lives in `storage/workflow_schema.py`, initialized through the `persistence.py` compatibility facade (not a PostgreSQL/RLS claim):
- workflow_assistant_drafts: id,organization_id,department_id,created_by,intent_text,proposal_json,validation_json,status,revision,created_at,updated_at,idempotency_key,request_hash. Unique org/creator/idempotency key; revision>=1; status READY_FOR_REVIEW/BLOCKED/NEEDS_CLARIFICATION. Org/department deletes cascade.
- workflow_assistant_draft_revisions: PK(draft_id,revision),snapshot_json,actor_id,actor_label,source,client_id,created_at; draft delete cascades. Snapshot contains proposal/intent/validation/status plus canonical artifact and trusted generation_id when applicable. Application history, not a tamper-proof audit archive.
- workflow_assistant_generations: id,organization_id,department_id,created_by,planner_agent_id (reserved legacy column, empty for new jobs),request_json,request_hash,idempotency_key,status,result_json,saved_draft_id,saved_draft_revision,error_code,error_message,input_tokens,output_tokens,cost_usd,cost_source,model,created_at,started_at,completed_at,deadline_at. Model/provider selection lives in request_json; model may later hold the reported upstream name. Unique org/creator/idempotency key.
- workflow_assistant_tool_calls: id INTEGER PK,generation_id FK cascade,tool_name (workflow_catalog/workflow_schema/validate_workflow_yaml),nullable proposal_hash, nullable validation_id (unique wfc_ UUID), nullable proposal_json (canonical validated candidate),created_at. Candidate workflow content is stored for YAML validation; no raw YAML arguments, connector credentials or identity context files are recorded. Candidate lookups are scoped to the current authenticated generation. Indexed by generation_id/id and unique validation_id.

Jobs transition QUEUED -> RUNNING -> COMPLETED/FAILED; active jobs can become CANCELLED or expired FAILED. Cancellation/expiry wins completion races. One active generation per department. Inference timeout=240s, deadline=300s, prompt <=180000 chars and authorized catalog <=120000 chars. Process-local BackgroundTasks are not durable workers; stale work expires after restart without a paid automatic retry. Permissions and budget are checked before queue/start/during waiting/after inference. Known legacy jobs remain readable with provider_id=legacy, but cannot restart through the former agent-authority path. Existing source draft/history data is preserved.

Draft create/update use BEGIN IMMEDIATE, fresh validation, revision CAS and atomic history/link writes. Idempotent generation saves return the linked draft; a different proposal cannot attach trusted generation provenance. No authoring request inserts workflows/executions/agents/connectors/grants/cron jobs or Office events. Reported API_KEY cost contributes to department monthly spend; unknown cost stays null and subscription usage is not billed into API spend. Zero budget remains zero. Provider caps are not cross-platform spending reservations.

## Verification

Use .venv/bin/python -m pytest --noconftest with test_workflow_assistant.py, test_workflow_assistant_generation.py, test_workflow_assistant_yaml.py, test_workflow_assistant_mcp.py and workflow revision/origin/playground suites. They use real SQLite/FastAPI, signed JWTs and real subprocesses. MCP tests use the official SDK client/server over stdio, including revocation/cancellation and forged destinations. Recorded model replies test persistence, not actual inference. Live model+MCP+YAML+save is a separate smoke test against an isolated database. Never load the destructive shared conftest for these tests.

MCP responses avoid duplicated representations: schema tools return JSON Schema/version (HTTP additionally supplies YAML schema text); validation tools return validation_id/validation/hash/schema version, not duplicate full documents. The parent resolves the authoritative candidate by validation_id and produces the canonical export.

Candidate persistence rechecks live job/rights under BEGIN IMMEDIATE after tool execution and before recording/returning a candidate. Result JSON retains the selected validation_id. Final changes after the latest user request were inspected statically only; tests and live inference were not rerun at the user’s request.
