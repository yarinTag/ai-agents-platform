# Anthropic Message Threads

Source integration for PR #18. No tests, builds, type checks, server startup or provider calls performed.

## Enablement
Organization admins may enable **Anthropic Message Threads (beta)** under API provider settings with Anthropic selected. Disabled by default; stored in existing organization_runtime_settings. Requires an organization Anthropic credential. NVIDIA, OpenRouter, OpenAI and the hosted Claude SDK path are unchanged. No settings or credentials are migrated or enabled by this change.

## Transport and durable sessions
Create includes full history/system/tools. Continue includes only messages after the last acknowledged assistant response and its provider ID. Local history remains the source of truth; thread IDs are private transport cursors, never the platform session ID. Fixed configuration is fingerprinted. Resume loads the cursor if safe; fork always starts a new server thread and a new spend ledger. New fields are backward compatible and use existing private atomic JSON persistence, with no SQL schema change.

Nonblocking POSIX advisory locks serialize active sessions and source reads before resume/fork loading. These are same-host filesystem leases, not distributed locks across independent stores. Pending requests invalidate predecessor reuse after interruption. Changed settings/tools/credential bindings, expired cursors or edited prefixes start a new thread. Tool changes include the connector formatting-only recovery inventory. Old thinking blocks are removed only from the outbound full-history copy after a configuration change, not from logs or the durable transcript.

## Recovery
One replay is allowed only for recognized pre-inference thread errors: thread_not_found, thread_already_continued, thread_continue_in_flight. Check error.details.error_code; an unrelated 404 never triggers replay. A recognized thread_unsupported_request causes one ordinary full-history request and disables threading for the rest of that worker. A failed recovery terminates normally; no infinite fallback loop. Before each attempt current connector authority and organization credential version are checked. Existing full-history budget upper bounds are retained. Replay never invokes local tools or connector actions again. Timeout, 5xx, authentication and quota errors do not retry automatically.

A refusal or truncated/paused response is accounted and stops; it cannot supply a continuation cursor. Automatic pause_turn resumption is outside this slice. This implementation does not adopt the SDK helper's automatic removal of refused user turns: local history is retained and future retries require an explicit new run.

## Logging and accounting
conversation_transport success events expose create/continue/replay/unthreaded, allowlisted recovery reason, message count and serialized-body bytes; response IDs/fingerprints/bodies are excluded. Existing reasoning and usage events remain separate. Events checkpoint immediately into the existing scoped Workflow Logs timeline. Byte count excludes headers/framing and is not a token count. Failed HTTP requests still use existing sanitized failure output; they do not produce success transport events. No TTFT claim: requests remain non-streaming. HTTP failures after an uncertain provider response retain the existing accounting uncertainty; this feature cannot recover missing provider usage.

Prompt caching is not enabled. Pricing and full-context budget bounds are unchanged; cache-read/write billing requires a separate implementation before adding cache_control. The thread cursor does not reduce the model context window or charged input.

## Retention and references
Opt-in allows Anthropic to hold conversation state temporarily; not suitable for ZDR or HIPAA. Durable local retention is unchanged. No API exists to list/read/delete a server thread.

- Official contracts: https://platform.claude.com/docs/en/build-with-claude/message-threads
- Announcement: https://claude.com/resources/articles/message-threads

## Deferred verification
Unexecuted source contracts cover deterministic create/continue state, replay prerequisites, private persistence, fork, rotation, expiry, reasoning sanitization and real file leases. HTTP recovery, provider compatibility and full workflow behavior require later authorized verification. No performance gain was measured. Owned source files remain below 500 physical lines.
