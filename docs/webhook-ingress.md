# AI-30 · Webhook deployment and incident response

Use this runbook to deploy the receiver introduced in AI-28 and diagnose it in the AI-29 MCP Hub. The [ingress contract](channel-ingress.md) defines the HTTP and storage interfaces.

## Shared contract and provider adapters

Each organization can configure its own connectors and providers. The receiver resolves the adapter from the stored connector, never from a request field. The adapter verifies its provider's transport and maps supported requests into a bounded event with a canonical event ID, event type, channel ID, message ID and optional candidate sender. The API, inbox, deduplication, outbox, diagnostics and action authorization use the shared contract.

Adding a provider such as Discord requires its own channel ID rules, credential and installation configuration, request verifier, event mapping, and setup diagnostics. Register each supported capability in code and verify it with provider-specific contract cases. Keep handshake and identity-proof requests out of the event queue. Do not assume a new provider exposes the same message events or sender proof as Telegram or Slack. Deployment constraints belong in the provider's setup instructions. Discord is a future adapter.

## Network and reverse proxy

```text
Telegram / Slack → public DNS and HTTPS edge → private API listener → SQLite inbox + outbox
Organization admin → authenticated MCP Hub → connector-scoped diagnostics and test routes
```

1. Set `PLATFORM_INGRESS_PUBLIC_URL` to the public API HTTPS origin, for example `https://hooks.example.com`. Use a publicly trusted certificate with the hostname and full chain. The value is used to derive the displayed webhook URL and the TLS probe target. The setting does not register anything with the provider.
2. Route public `POST /api/v1/channel-ingress/{connector_id}` directly to the API with no redirect or body transformation. Preserve the original body bytes, content type, and Telegram or Slack verification headers. Do not cache responses. Leave the API listener private and keep administrator diagnostics behind application authentication.
3. Apply a 64 KiB request-body limit at the edge and bound request time and concurrent connections. At the first trusted ingress hop, replace untrusted forwarding headers with the observed client information. The API must trust forwarding headers only from known proxies. Set the edge rate policy for actual provider traffic and watch for shared proxy addresses collapsing legitimate traffic into one IP bucket.
4. Keep host clocks synchronized and monitor acknowledgment latency. Slack expects a response within three seconds. The API acknowledges a new event only after the SQLite transaction commits. Route all traffic for a connector to the same authoritative database. Independent SQLite copies cannot deduplicate each other's events. [Slack Events API](https://docs.slack.dev/apis/events-api/)

For hosted Telegram Bot API delivery, use IPv4 and preferably HTTPS on port 443. Telegram also documents ports 80, 88 and 8443 with TLS, and currently lists `149.154.160.0/20` and `91.108.4.0/22` as source networks. If you add a Telegram-only edge allowlist, confirm the ranges at deployment and match the source at the trusted edge. Slack's documented IP restrictions for OAuth tokens do not apply to incoming webhooks. Keep a Telegram-only IP rule off Slack routes. Both providers still require application verification. [Telegram webhook guide](https://core.telegram.org/bots/webhooks) · [Slack security guidance](https://docs.slack.dev/concepts/security/)

## Provider setup and verification

| Provider | Configuration | Verification |
| --- | --- | --- |
| Telegram | Configure the exact connector's bot token and a distinct webhook secret through the [identity secret endpoint](external-identities.md). Register the derived URL and matching `secret_token` through the provider. One bot has one webhook. Use the unified receiver for events and private linking messages. | Compare `X-Telegram-Bot-Api-Secret-Token` to the configured secret in constant time before parsing. This is a shared-secret check. The bot account scope comes from the configured token. Message events must have valid IDs and a timestamp no more than 24 hours old or five minutes in the future. Private linking has its own stricter checks. |
| Slack | Configure the app's signing secret, workspace ID and app ID on the exact connector. Set the app's Events API Request URL. Subscribe only to message events needed for the intended test or operation. Route `/platform-link` to the same receiver if linking is required. | Check the timestamp within ±300 seconds, then compare `v0=` plus HMAC-SHA256 of `v0:<timestamp>:<raw body>` in constant time. Require exact configured workspace and app IDs for event callbacks and linking commands. A signed URL verification handshake echoes the bounded challenge and stages no event. |

Keep secrets out of URLs, proxy access logs, request tracing, shell history, and incident notes. Signature validation establishes provider provenance. A downstream action must separately verify the linked sender, exact binding, current tenant policy, and action authority. [Telegram Bot API](https://core.telegram.org/bots/api#setwebhook) · [Slack request verification](https://docs.slack.dev/authentication/verifying-requests-from-slack/)

## Acceptance, retries, and recovery

| Result | Meaning and operator response |
| --- | --- |
| 202 | A supported event and its outbox job committed together. Look for a recent verified receipt in the MCP Hub. |
| 200 | Duplicate, ignored event, identity proof acknowledgment, or Slack handshake. A 200 alone does not prove an event was staged. |
| 400 or 413 | Rejected envelope or oversized body. Check provider event shape and edge limits. |
| 403 | Connector unavailable or verification rejected. Check the exact connector URL, active status, secret, clock, preserved body, and Slack app/workspace. |
| 429 | Capacity limit. Check edge limits and the connector's 120 new events per minute and 1,000 unfinished jobs. The connector-level response includes a 60-second Retry-After. |
| 503 | Storage unavailable. Check free disk, permissions, database health and write contention. Preserve the database and receipts. |

Deduplication uses the organization, connector, provider and account plus the provider event ID or channel/message pair. Duplicates do not consume new-event quota. Terminal receipts become eligible for cleanup after 48 hours, on later staging for that connector. Provider redelivery and internal retries are separate. Internal consumers use a 60-second lease with a fencing token. The four possible retry delays after failures are 10, 20, 40 and 80 seconds. The fifth unsuccessful attempt becomes `FAILED`. The current release starts no outbox consumer. Future consumers must make external effects idempotent by internal event ID.

In MCP Hub, run **Check configuration** for local URL, secret, connector and SQLite checks. **Check public TLS** tests the configured public hostname and certificate at that moment. To establish actual delivery, use the provider's setup console and a supported message in an authorized test channel, then verify a new staged receipt. A successful TLS probe or Slack handshake alone cannot establish delivery.

### Delivery flood or queue saturation

1. Record the connector, time window, status counts, and latency from the edge and the MCP Hub. Use bounded diagnostic summaries. Raw bodies and headers may contain credentials or message content.
2. Apply route-specific rate and connection limits at the trusted edge. If necessary, pause the affected provider subscription or webhook while preserving other connectors and the database. Keep request verification enabled. When repeated Slack delivery failures disable subscriptions, restore them in the app console after recovery.
3. Check that storage can commit, identify whether the backlog has a supported consumer, and resume delivery gradually. With no consumer deployed, reduce or pause subscriptions before the unfinished-job cap is reached. Preserve receipts when reconciling provider redeliveries.

### Leaked webhook secret or signing secret

1. Pause the affected provider delivery or block its receiver route at the trusted edge. Restrict access to incident evidence and preserve timestamps, connector IDs and audit records.
2. Rotate the proof secret at the platform and provider boundaries. Rotate a bot or OAuth token at its provider if that credential was exposed. Use the audited platform rotation endpoint. Rotation invalidates outstanding identity challenges. Review existing links separately.
3. Review links and staged events from the exposure window before allowing a downstream consumer to use them. Do not infer authenticity from an old accepted receipt after a secret compromise. For identity revocation and relinking, follow the [identity recovery runbook](identity-proof-runbook.md).
4. Restore delivery, verify a new staged receipt, and check that unexpected proof failures and event rates have subsided. Avoid deleting receipts as a way to recover delivery.

Implementation references are the [HTTP receiver](../poc/backend/api/channel_ingress.py), [provider verification](../poc/integrations/identity_proofs.py), [event projection](../poc/integrations/channel_ingress.py), [TLS probe](../poc/integrations/ingress_tls.py), and [SQLite inbox and outbox](../poc/storage/channel_ingress.py). This documentation was checked against source. Production proxy configuration, external TLS, and live provider delivery require verification in the deployment environment.
