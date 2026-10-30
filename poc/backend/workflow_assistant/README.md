# Workflow Assistant

Open /workflow-assistant, choose an authoring model and a department, and describe the desired workflow. You do not select an authoring agent. The platform uses the configured runtime provider's routing/credentials; execution agents remain per-step assignments from the approved department catalog.

The model uses an internal stdio MCP server to read the authorized catalog and native YAML schema and validate its generated workflow. Only those three authoring tools are exposed; the model cannot invoke GitHub/Telegram, grant permissions, activate triggers or save behind the user's back. The validation tool stores the canonical candidate and returns validation_id. The model’s final reply references that candidate instead of rewriting the YAML. The server resolves it only within the current generation, verifies its stored hash, and revalidates current permissions.

Review the proposal, questions, resource errors and YAML, then explicitly save a draft (or explicitly retain a blocked draft). Download workflow-draft.yaml if needed. Drafts retain revision history and protect against concurrent edits. YAML exports use the existing WorkflowParser syntax and the governed schema in [workflow-authoring.schema.yaml](../../workflows/workflow-authoring.schema.yaml). The full contract, limits and compatibility rules are in [AGENTS.md](AGENTS.md).

Missing connections in the catalog mean they are not currently approved/visible to the selected department. They may already be installed in the organization. An administrator must grant the department's tools and explicitly approve repositories/channels; providing internal IDs cannot grant access. No permissions are automatically changed by authoring.

The internal MCP server is process-bound to the signed-in user's current rights. An installable external MCP server with OAuth/login remains a separate delivery. This module does not publish executable workflows; native YAML is an inactive draft until an enforcement/publication path is provided.

Developer API:

- GET /api/v1/workflow-assistant/context supplies model/provider choices and permitted departments.
- GET /workflow-schema supplies native JSON Schema plus its YAML representation.
- POST /generations accepts model_id/provider_id, department_id and user/assistant messages; it returns 202. Poll GET /generations/{id}; cancel with POST /generations/{id}/cancel.
- POST /validate-yaml accepts department_id/yaml_content and returns canonical YAML plus current policy validation.
- POST /generations/{id}/save-draft explicitly saves authoritative output. Its optional save_blocked flag is false by default.
- Existing structured proposal/draft endpoints remain compatible. Saved drafts and new revision snapshots also expose definition_yaml/definition_json/workflow_schema_version/yaml_error. A malformed/incomplete legacy proposal cannot be exported silently.

New requests reject planner_agent_id and unknown model/provider values. Old chats/drafts remain readable, but old queued jobs cannot restart with inherited agent authority.

Tests use real SQLite, FastAPI, subprocesses and SDK client/server stdio, with --noconftest. Live inference is verified separately and must not be inferred from stored-reply fixtures. No browser visual validation is claimed by those tests.
