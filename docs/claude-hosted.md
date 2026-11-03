# Claude Agent SDK: hosted read-only workflow backend

## Status

Source implementation of the first vertical slice: **read-only repository analysis** through the Claude Agent SDK. Disabled by default and **not runtime verified**. No image, SDK, container, application or model was run. Existing Direct API execution remains available. Codex and Antigravity are still not implemented.

The design follows the official hosting and secure-deployment guidance:

- https://code.claude.com/docs/en/agent-sdk/hosting
- https://code.claude.com/docs/en/agent-sdk/secure-deployment
- https://code.claude.com/docs/en/agent-sdk/python
- SDK version pinned to the observed release https://github.com/anthropics/claude-agent-sdk-python/releases/tag/v0.2.177

## Architecture

Workflow engine -> hosted task runner -> SDK worker container -> HTTP relay container -> private Unix socket -> host credential/policy/budget broker -> fixed Anthropic Messages endpoint.

Only the host broker decrypts the organization's Anthropic key. The worker sees an expiring, run-bound broker capability; it has no database or provider secret. The relay has no repository, secrets or external network. No host TCP listener or host-gateway mapping is used. A separate internal Docker network is created per hosted run. Repository data still goes to the organization's selected Anthropic model by design.

The SDK and its bundled Claude process both run inside the container. Permission hooks complement the read-only mount, non-root process, read-only root, restricted network and resource limits. The first release does not expose Bash, file writes, agents, browser tools, external MCP, user plugins, hooks from the repository, workflow secrets or tool-network egress. Existing repository clone authorization is retained. Publication/draft PR workflows must continue using Direct API for now.

## Configuration (not executed)

Supported host: native Linux Docker. This Unix-socket bridge is not claimed to work through Docker Desktop on macOS/Windows or a remote Docker daemon. Host and Docker daemon must see the same local paths. The server must retain Docker daemon control; it is never given to the agent container.

1. Prepare a trusted Debian Python 3.12+ base image pinned by digest. Build the template at poc/runtime/claude_hosted/Dockerfile only when deployment execution is authorized. It pins SDK 0.2.177; the worker independently checks that installed version. Review/lock transitive dependencies and scan the final image before deployment. Store the final image by digest.
2. Set PLATFORM_CLAUDE_SDK_IMAGE to that final name@sha256:... and PLATFORM_ENABLE_CLAUDE_SDK=true only after acceptance. No actual flag/environment change was made in this task.
3. Configure PLATFORM_SECRETS_KEY and the organization's own direct_anthropic API key in Runtime settings. Configure the exact Anthropic default/model and explicit finite non-negative token prices through the existing pricing configuration. No environment/global API-key fallback.
4. Use an organization/department-bound workflow agent with Read/Glob/Grep grants and an authorized GitHub clone_repository grant. Organization Anthropic credentials are independent of GitHub connector credentials. Hosted agent provider overrides must be absent or compatible with Anthropic.
5. Set workflow settings.execution_backend=claude_code, or override one step with params.execution_backend=claude_code. That step must declare params.workspace.mode=read and no connector mcp_servers. No secrets, network allowlist or reviewerAgentId. Choose a Claude model or inherit the organization's Anthropic default. Unknown model/provider combinations fail preflight rather than substituting providers.

Example native definition fragment:

```yaml
settings:
  execution_backend: claude_code
  model: claude-sonnet-4-20250514
steps:
  - key: inspect
    name: Repository analysis
    agent_id: existing-department-agent
    prompt_template: Inspect the repository and explain the authentication flow, citing actual files.
    params:
      workspace:
        connector_id: existing-github-connector
        repository: approved-owner/approved-repo
        mode: read
```

IDs and model are illustrative. They must exist and be currently authorized. Merely saving this definition does not create grants or prove readiness.

## Lifecycle and visibility

Whole-DAG preflight checks the hosted step shape, current agent/tool grants, key/pricing configuration and static feature/image requirements before earlier steps execute. Existing integration preflight checks repository policy and rejects workflow secrets. Runtime rechecks policy on each model and tool authorization request. The host enforces timeout/cancel/shutdown, removes containers and checks actual process exit plus SDK result and completed tool activity. Failures never automatically switch backends or retry paid work. Final model answers must satisfy the existing completed/blocked envelope; missing input, unsupported deliverables or malformed outcomes fail rather than appear completed.

Workflow Logs uses existing events: execution_backend, system, assistant, tool_use (phase started/denied), tool_result, usage and result. Tool events are checkpointed about once per second; the page polls every five seconds. Model SSE is bounded/buffered at the broker, so this is not live token streaming. Thinking blocks and encrypted continuations are not exported. Session IDs are retained as tagged diagnostics, but sessions/files are ephemeral: **resume/fork is explicitly unsupported** and starting a fresh execution is required. This is not durable platform replay.

## Budget semantics

hosted_model_requests records each reservation/usage with organization, department, execution and task identity; schema/state contracts are in runtime/claude_hosted/AGENTS.md. Reservations are serialized in SQLite using BEGIN IMMEDIATE. Standard text-only request size is capped at 80000 serialized bytes, output at min(agent limit,32000), successful model calls at 40. The broker reserves a conservative text/framing/cache-write estimate based on configured rates, then settles using returned token counts with conservative cache rates. It does not certify provider invoice prices. Missing or unsupported prices fail before dispatch.

Ambiguous dispatched calls retain the whole reservation as UNKNOWN; a crash can leave RESERVED with the same protective effect. They do not auto-expire or become zero-cost. Known-not-dispatched calls settle at zero. Usage summaries mark uncertainty and show reserved_budget_usd separately from known spend. Existing department budget checks include outstanding hosted holds; finalized workflow totals are not counted again. Operator reconciliation/release tooling is deferred, so ambiguous holds currently need an explicitly reviewed administrative correction.

This change does **not** implement atomic per-call reservation for legacy Direct API workers. Concurrent already-running Direct API work remains a limitation of a shared hard budget. Do not claim a globally race-free spending cap across both backends before those workers are migrated to the same ledger.

## Acceptance still required

No tests/build/lint/typecheck/imports, Docker builds/runs, SDK execution, server startup, provider calls or channel messages were performed, per project restriction. Source tests are added, not executed.

Before enabling: validate image/package compatibility, Unix socket UID permissions and relay readiness, SDK exact routes/headers and SSE parsing, fail-before-side-effects preflight, live revocation, concurrent reservations and reconciliation, all cancellation/timeout/shutdown/crash paths, secret absence from worker/container/logs, filesystem/symlink/network denial, tool/output bounds, usage pricing and rendered UI. A successful real read-only workflow must precede advertising verified readiness. Unsupported SDK auxiliary routes currently fail closed; compatibility issues may require a reviewed extension, never unrestricted API forwarding.
