# Governed connector completion contract

## Failure addressed

The user-requested log inspection of wf_exec_0a06eccd9997 found successful GitHub tool results followed by a final answer in ordinary prose. The private session retained that candidate (1004 characters); it was not a JSON document or whole JSON fence. No raw private answer was copied into this document. The historical failed execution is unchanged and was not retried.

Previously the Direct worker only prompted for a JSON outcome and discarded rejected prose behind a generic error. This change supplies a schema-backed internal finalization tool and bounded format recovery without retrying external operations.

## Outcome schema

runtime.direct_outcomes.WorkflowOutcome is a strict Pydantic model with exactly these required fields:

- status: completed or blocked.
- output: string, 1..60000 characters, non-whitespace.
- blocker: null or string up to 8000 characters. The field is required even when null.

Unknown fields, coercion, missing fields, malformed JSON, duplicate text-JSON or chat/Responses finish-argument object keys and surrounding prose are rejected. One whole fenced JSON document is allowed as a lexical wrapper, without scanning arbitrary prose for a successful embedded object. completed with any non-null blocker is blocked, including an empty blocker string. Valid blocked outcomes fail without an extra formatting call. final_outcome retains its (output,error) return contract for existing consumers, including hosted SDK validation.

## Internal finalization tool and state

runtime.completion_validation.ConnectorFinalizer advertises platform_workflow_finish alongside the existing frozen connector tool inventory. Its input_schema comes from WorkflowOutcome. It is a server-owned validation operation, not an MCP connector, grant, external RPC or receipt. It cannot satisfy required connector work and is never dispatched to DirectTools.call or WorkflowToolExecutor.call.

A finalization call must be alone. Mixing it with external tool calls fails without executing any of those calls; this is not automatically repaired. Strict legacy JSON finals remain valid. Server validation remains authoritative even if a provider ignores tool-schema guidance; no universal provider-native constrained-decoding guarantee is claimed.

For a malformed lone finish input or prose-only final answer, one completion_validation rejection diagnostic is emitted. The worker rechecks current policy and required successful receipts before attempting recovery. If those checks pass, it appends one server-owned formatting instruction and issues another ordinary model request with **only platform_workflow_finish** in the inventory. That pass has no connector tools and any returned external call is rejected before dispatch. It preserves known blockers and cannot claim success without the same receipt/current-policy checks afterward. It never regenerates/reexecutes the workflow, sends a message, replays reads or retries a provider transport failure.

This optional additional model call remains within the existing 40-call loop, usage ledger, max-budget preflight and live connector permission/deadline checks. It can incur model usage on a future run and is accounted for as such. A second malformed final fails closed. No automatic provider retry/fallback is introduced. Session tool calls are closed with internal validation-only acknowledgements to retain valid transcript history.

Non-connector Direct API tasks and tool-free workflow chat do not receive the synthetic finalization tool or recovery pass. The existing connector verify_completion checks remain mandatory for every accepted completed answer; internal finalization does not add a connector receipt.

## Rejected-response diagnostics

completion_validation events contain status=rejected, error_code, message, attempt (1/2), recovery_action (formatting_only/fail_closed), candidate_preview (max 4000 characters), candidate_truncated, candidate_characters and candidate_sha256. The source is only the final answer text or the internal finish arguments, never the entire provider response, HTTP headers or private reasoning/continuation fields.

Preview redaction removes known credential environment values, common credential assignments/prefixes, bearer values, URL credentials, Telegram-style bot tokens and control characters. This is best-effort redaction, not a guarantee to detect arbitrary secrets. Original full transcripts remain private; the preview is still governed by existing task/workflow log authorization.

The runtime checkpoints this event immediately and StepEventTimeline renders it as Completion validation, with expansion and JSON details. Provider usage remains separate. No historical logs or stored workflow definitions were changed by this fix.

## Verification boundary

Added test_completion_validation.py source contracts for strict schemas, whole fences, surrounding prose/duplicates, valid blockers, single formatting-only transition, connector-tool exclusion, mixed-finalization refusal, bounded retries and preview redaction. No tests, build, lint/typecheck, model calls, workflow runs, PRs or messages were executed. Previous read-only Docker/sleep-only permission exceptions do not authorize inference verification of this change.
