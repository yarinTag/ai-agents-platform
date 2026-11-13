# AI-25 · External identity linking

See [the identity proof and recovery runbook](identity-proof-runbook.md) for the full sequence, approval trust boundaries, and credential compromise response.

An active platform user starts a link, demonstrates control of a Telegram or Slack account, and confirms the observed subject while signed in. The link is identity evidence. Actions still require current membership, role, and resource authorization. The proof endpoint has no workflow or approval dispatch.

| Method | Path relative to `/api/v1/governance/external-identities` | Contract |
| --- | --- | --- |
| GET | Base | Lists the signed-in user's links in the current organization. |
| PUT | `/connectors/{connector_id}/secret` | Personal organization admin only. Accepts `secret` and, for Slack, `team_id` and `app_id`. Returns 204 and invalidates outstanding connector challenges. |
| POST | `/connectors/{connector_id}/challenges` | Returns 201 with `id`, `code`, `provider` and Unix `expires_at`. Five-minute lifetime, at most five issues per user in ten minutes, and one current challenge per user and connector. |
| GET | `/challenges/{challenge_id}` | Returns `id`, `subject` (null until verified), and `expires_at` to the initiating user. |
| POST | `/challenges/{challenge_id}/confirm` | Accepts the observed `subject`. Returns 201 with the link identity. Duplicate subjects or users within the same organization and provider account conflict. |
| DELETE | `/{link_id}` | The owner unlinks and invalidates their outstanding challenges for that connector. Returns 204. Relink through a new challenge. |
| GET | `/connectors` | Lists currently configured connectors available to the signed-in user with ID, name and provider. |
| GET | `/departments/{department_id}/links` | Lists the selected department's visible links for managers and organization admins. Supports `after` and `limit`. |
| DELETE | `/departments/{department_id}/links/{link_id}` | Revokes a visible link when the current actor has authority to remove the organization-wide mapping. Returns 204. |

For Telegram, configure the connector bot's webhook at `POST /api/v1/channel-ingress/{connector_id}` with its own secret. The unified receiver accepts identity proof and channel events. The legacy proof-only endpoint remains available for existing installations. The user sends `/start CODE` in a private conversation with that bot. The verifier requires Telegram's secret header and rejects group, bot, forwarded and anonymous senders. Telegram has one webhook per bot. Coordinate this endpoint with any existing receiver before configuring the provider.

For Slack, configure a `/platform-link` slash command at the same connector-specific route. Use the proof-only route for installations that only need linking. Verification uses the raw form body, timestamp, Slack app signing secret and the configured app and workspace IDs. A person runs `/platform-link CODE` and confirms the returned subject in the platform. Provider endpoint setup is an operator action. Store separate secrets per installation. See [Telegram webhook documentation](https://core.telegram.org/bots/api#setwebhook) and [Slack request verification](https://docs.slack.dev/authentication/verifying-requests-from-slack/).

Only SHA-256 digests of high-entropy challenge codes are persisted. Proof receipt and final confirmation use atomic writes. Credential changes invalidate pending proof. Rotation through the dedicated endpoint stores the secret in the existing MCP connector configuration, writes an audit row in the same transaction, and does not unlink existing subjects. Existing connector read redaction applies. Provider bot or workspace account changes prevent previous links from resolving under the new account.

Operations log the outcome code and correlation ID. Invalid public proofs use debug-level diagnostics and have a generic response. Database failures have sanitized responses and error logs. Audit events are `EXTERNAL_IDENTITY_LINKED`, `EXTERNAL_IDENTITY_UNLINKED`, and `EXTERNAL_IDENTITY_SECRET_ROTATED`. Audit details retain only tenant and connector metadata alongside the actor and affected resource ID. Never log codes, raw provider requests or secrets. The proof endpoint caps bodies at 16 KiB and runs under the API rate limiter.

Future consumers must pass a verified subject to `storage.external_identities.resolve_user` and then apply current authorization for the specific workflow or approval. AI-26 exposes the personal linking flow and department management in the dashboard. Manager revocation of an organization admin's link or a link shared across departments requires an organization administrator. Manager revocations record `EXTERNAL_IDENTITY_REVOKED`.
