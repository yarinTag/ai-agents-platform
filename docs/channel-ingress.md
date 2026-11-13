# AI-28 · Verified channel ingress

See the [AI-30 deployment and incident runbook](webhook-ingress.md) for network topology, provider setup, and recovery procedures.

Configure the provider to send requests to `POST /api/v1/channel-ingress/{connector_id}`. The connector determines the provider, organization, and expected installation. There is no client-supplied tenant selection. A Telegram connector uses the secret header and configured bot identity. Slack uses its timestamp and signature over the original request bytes. Slack event callbacks also require the configured workspace and app IDs. Signed Slack URL verification echoes only the bounded challenge. A handshake does not stage an event or establish observed event delivery.

Telegram sends private `/start CODE` messages to the same endpoint, so the bot needs only one webhook. Slack can also send the signed `/platform-link CODE` form to the endpoint. Link proofs use the existing identity proof verifier. They never enter the inbox or outbox. The older identity proof route remains available for compatibility.

## Admission and staging

Bodies are limited to 64 KiB. Telegram messages must have a valid update ID, message ID, chat ID and bounded timestamp. Slack callbacks must contain a valid event ID, channel ID and message timestamp. Unhandled event kinds and message subtypes receive 200. The supported event type is `MESSAGE`. Provider sender IDs are candidate identifiers. A downstream consumer must resolve linked identity and authorize the current action before any dispatch. Provider response URLs and raw bodies are discarded. Opted-in channel triggers can retain a separate bounded message projection as described below. Ingress itself does not execute workflows or consume approvals.

A newly staged event receives 202 after the inbox and outbox commit. Duplicates receive 200, including duplicates when the capacity limit is reached. Unverified requests receive 403, invalid envelopes 400 and oversized requests 413. New events are limited to 120 per connector per fixed minute and 1,000 unfinished jobs per connector. Capacity rejections return 429 with a 60-second Retry-After. Storage failures return 503. The storage transaction rechecks the verified configuration version before writing. The existing API IP rate limit applies alongside the connector limit.

## Storage contract

| Table | Columns and scope |
| --- | --- |
| `channel_ingress_events` | Internal ID, organization ID, connector ID, provider, provider account, event ID, event type, channel ID, message ID, optional candidate sender ID, Unix receipt time. Unique constraints cover the organization, connector, provider and account plus the event ID or channel and message IDs. |
| `channel_ingress_outbox` | Event row ID, status, attempts, Unix availability time, lease token and expiry, Unix finish time. The row commits with its inbox event. Parent deletion cascades. |
| `channel_ingress_limits` | Connector ID, current Unix minute and accepted event count. |
| `channel_ingress_failures` | Organization ID, connector ID, Unix minute, bounded reason code, last occurrence time and count. One bucket per scope, minute and reason, retained for up to 60 active minutes as new failures arrive. |

Trusted internal consumers may claim jobs with a 60-second lease. A claim increments attempts and yields a fencing token. Settlement requires the current unexpired lease. Retryable failures wait `5 × 2^attempts` seconds. Claims can recover expired leases, and the fifth unsuccessful attempt terminates as `FAILED`. Statuses are `QUEUED`, `PROCESSING`, `RETRY`, `COMPLETED`, and `FAILED`. A terminal row becomes eligible for deletion when the connector stages a new event after the 48-hour receipt retention window. Consumer effects must be idempotent by internal event ID. No consumer starts automatically in AI-28.

## Diagnostics and setup

Current organization administrators can read `GET /api/v1/governance/channel-ingress/{connector_id}/diagnostics`. The response exposes provider, derived webhook URL, HTTPS configuration, connector connection and secret configuration, last verified staged receipt, 25 recent events, 25 recent failure buckets, and the count of omitted or aggregated failures. Event rows expose internal ID, provider, event type, status, Unix receipt time and terminal processing duration in milliseconds. Raw event data, provider account, sender IDs, channel IDs and credentials stay out of diagnostics.

Set `PLATFORM_INGRESS_PUBLIC_URL` to the externally reachable HTTPS origin of the API. The endpoint includes the exact connector ID. Server-side URL configuration alone leaves `ssl_status: UNVERIFIED`. Use `POST /api/v1/governance/channel-ingress/{connector_id}/test` for a local configuration and rolled-back SQLite write check. With explicit `{"verify_tls":true}`, this endpoint may resolve and probe only the configured public host. It pins the resolved global address, checks the certificate for the configured hostname, and sends no HTTP request. The result reports `tls_status` as `VALID`, `INVALID` or `UNVERIFIED`. The probe status `READY` or `BLOCKED` describes local configuration and storage. A certificate check does not prove webhook reachability or provider delivery. Configure and test actual provider delivery through the provider's control panel.

Failure diagnostics use `INVALID_PROOF`, `INVALID_EVENT`, `RATE_LIMITED`, `BODY_TOO_LARGE`, `QUEUE_FULL` and `STORAGE_UNAVAILABLE`. Invalid proofs can populate bounded error counters but never stage an event. Look for a recent verified event after checking the public endpoint, provider secret, and exact Slack app and workspace settings.

AI-31 introduces a separate short-lived trigger input projection for opted-in workflows. Verified message text is bounded and sanitized, excluded from diagnostics, and eligible for deletion after five minutes. Outbox settlement clears terminal input.

See [channel trigger policy](channel-trigger-policy.md) for the opt-in AI-31 consumer and its distinct workflow authorization checks.
