# Friendly workflow creation chat

Open **Workflows → Create with AI**, describe the outcome and answer the assistant's
questions. The chat uses the model selected in Runtime settings. Its preview
shows the steps, execution agents and delivery destination; **Create workflow**
saves the reviewed workflow inactive. Activate it separately after review.

This is a new implementation. The removed Workflow Assistant, its standalone
page, old schema and internal MCP authoring service are not restored.

## Repositories, channels and permissions

The backend supplies only the current organization/department's permitted
execution agents and connected integrations with active department grants.
The catalog includes explicitly configured repository names, exact channel IDs
and tools allowed by the department whitelist. It excludes connector credentials
and raw configuration. Expand **Resources the assistant can use** to inspect it.

Remote discovery is not an access grant. An empty explicit allowlist stays empty;
legacy single defaults are used only when no corresponding allowlist exists.
If a repository/channel is missing, an administrator must configure or grant it.
The model is told to ask questions rather than invent resources.

Structured references are validated after generation and again before creation.
The server also checks native workflow dependencies/cycles and cron syntax.
Exact resource references are carried into execution instructions and step
parameters. This validates the declared resource contract, not arbitrary natural
language inside a prompt; execution-time governance remains necessary.

## Jobs, recovery and creation

Chat requests are private, persisted jobs. The browser receives an ID immediately
and polls while a bounded, tool-free model call runs. The model cannot invoke
integrations, write files or create workflows during planning. No Office task is
created. Subscription/API routing follows existing runtime configuration.

The URL's `workflowChat` parameter preserves the current request ID through a
refresh. Opening `/workflows?workflowChat=<request-id>` recovers its authorized
conversation and reply. Reads still require the original creator's current
organization/department access. The URL contains no credentials or conversation
content. Conversations/catalogs are not saved in browser storage.

Repeated submission of an accepted request ID is idempotent. Explicit creation
uses the server-stored preview, revalidates resources and reserves one stable
workflow ID, so retrying creation returns the same workflow. The shared creation
path provisions the dedicated runner and writes the first revision as inactive;
webhooks/channel triggers are disabled. Nothing is run automatically.

Jobs are process-local background work, not durable queued executions. A server
restart can interrupt generation; unfinished jobs expire after 180 seconds rather
than automatically triggering another paid call. Completed replies survive.
Generation has a 120-second timeout and one active request per department.
API costs reported by the runtime contribute to department spend; existing
provider pricing configuration determines the accounting estimate.

## Errors and development reloads

HTTP `200` from polling means the job record was read successfully; inspect its
`status`, `result` and `error` for generation outcome. A clarification-only reply
is `READY` with `ready=false` until enough information exists for a workflow.

Connection loss, timeout, HTTP errors, request validation and model failures have
separate messages. Successful polling/reconnection clears transient connection
errors. A development reload does not turn a saved successful reply into a model
failure. Use the saved request URL to recover after refresh; no model retry is
needed to read an existing reply.

## Source and verification

- API and policy: `poc/backend/api/workflow_chat*.py`.
- Tool-free runtime bridge: `poc/runtime/workflow_chat.py`.
- UI: `WorkflowChatModal.tsx` and `useWorkflowChat.ts`.
- Real SQLite/FastAPI policy/creation cases: `poc/tests/test_workflow_chat.py`.

Source/whitespace review was performed. Tests, builds, type checking, application
startup and live inference were not run by the agent under the repository's
verification restriction. An existing user-triggered job was inspected through a
read-only SQLite connection to diagnose its successful reply and misleading UI
banner; that inspection did not run another inference.

Workflow chat catalog now includes organization-scoped configured plugin skills
(id = canonical source path/URI, key, name, plugin, bounded description). ChatStep
adds skills:string[] (default [], max20). Validation checks all IDs against the
current plugin catalog during generation and confirmed creation; native conversion
preserves per-step skills. Server-only channel actions reject analysis skills.
No skill contents or credentials are included in the model's authoring catalog.

workflow_skills.py projects only the organization's explicit configured plugin
source into id/name/key/plugin/description metadata. Git mode uses the existing
in-memory scanner and exact-tenant GitHub connector credentials; local mode has
no fallback roots. Context resolution revalidates current catalog membership,
fetches remote full Markdown via bounded fixed-host GitHub API, or reads a local
file inside the configured root. Unique legacy keys/relative suffixes resolve
only within that catalog; unavailable/ambiguous references fail. No global skill
content cache supplies workflow instructions. Combined content is <=120000 chars,
local files <=100000 bytes; empty/missing content fails. No clone, tool grant or
script execution is implied. Runtime verification was not performed.

The last PR-review workflow had omitted the requested tech-backend/skills/senior-architect/SKILL.md reference. It was restored on fetch_open_prs in revision3. Its remote availability/content has not been verified; execution must resolve it uniquely against the current configured source before use. No workflow was run.

Workflow chat adds ChatWorkflow.skills:string[] (default[], max20), the shared
selection for every AI step. ChatStep.skills remains accepted solely for existing
jobs/clients. Validation checks both against the current plugin catalog. Native
conversion deduplicates/promotes all legacy step skills into root skills and omits
per-step skills. Global skills are allowed alongside channel delivery actions,
which do not use a model or load these instructions.

## Shared workflow skills (supersedes per-step selection UI)
All AI steps inherit the deduplicated union of definition.skills and legacy
steps[*].skills, normalized by skill_inheritance.workflow_skill_ids. Supported
native entries are string IDs or attached-skill objects with id/location. Missing
IDs fail explicitly. WorkflowStepRunner resolves these through the organization
plugin source before model invocation; server channel_action steps skip skill
loading entirely. Legacy step assignments remain readable but are now shared.
New authoring writes only workflow-level skills. No execution/tests were run.

## Explicit planned workflow runner
Workflow chat catalog agents includes reserved `__workflow_runner__`, named
Dedicated workflow runner, with provision_on_create=true. This is a provisioning
option, not a persisted/executing agent. Its connector_tools are exactly the current
department's catalog tool grants; it grants no new connector/resource access.
Ordinary same-org/department agents remain selectable; other workflow runners
remain excluded. Unknown model-generated IDs continue to fail validation.
On confirmed /ai/chat/{job_id}/create, native_definition maps only this reserved
ID to wf-agent-{new_workflow_id}; shared persist_workflow creates that real scoped
runner before saving the inactive workflow. Provisioning failure now returns503
instead of saving a workflow without its runner. Existing user/grant/resource
revalidation and idempotency checks remain. Generation with validation errors uses
a server-owned corrective message instead of a model's misleading ready claim.

Existing invalid drafts keep their original errors; send a follow-up selecting the dedicated workflow runner to generate an updated proposal. No saved draft is automatically marked valid or created by this correction. No tests/build/app startup/live inference was run.

## Progress notification configuration
AI workflow creation writes progress updates to `destination.notify_mode` and native `metadata.channel_binding`, not to notify_start/middle/done DAG stages. Set EACH_STEP for start, each executed step outcome and terminal completion; START_AND_COMPLETE for just the start and terminal report; COMPLETION_ONLY for a terminal report only; NONE for no lifecycle messages. Terminal reports cover success, failure and cancellation. The existing visual Channel Binding → Notification Mode control edits the same configuration. ON_COMPLETE/ON_FAILURE/ALWAYS remain supported for legacy definitions.

The engine sends these messages directly through governed Telegram/Slack delivery, with no LLM or agent task. Step progress is factual status/error, and final reports use existing output/template semantics with actual PR receipts in step output. A notification failure is surfaced separately and cannot turn successful code work into a failed workflow. Each run/event has its own atomic audit claim, with no automatic resend; a failed progress update does not prevent a later independent terminal report. Explicit business message-delivery tasks remain valid, separate from progress. No live messages or tests were performed during implementation.
