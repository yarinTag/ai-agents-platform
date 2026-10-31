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
