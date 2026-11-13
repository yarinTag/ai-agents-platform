# AI-22 · Organization and department channel registry

See [channel identity and sender policy](channel-identity-policy.md) for agent instructions, the disable and removal lifecycle, and provider extension boundaries.

The registry stores an exact Slack channel or Telegram chat for an organization or one department. Each record independently configures notification delivery, workflow trigger eligibility, and approval channel eligibility. All three uses start disabled. AI-22 adds configuration and audit. Later stages supply verified identities, ingress, workflow dispatch, and interactive approval enforcement. Existing workflow delivery still uses its existing connector and department policy.

## HTTP contract

Base path is `/api/v1/governance/channel-bindings`. Tenant identity comes from the authenticated session. The organization scope is represented by a null or omitted department on creation and by an omitted department query on reads and changes. A department scope is exact and must agree with the selected department header when one is set. Organization and department rows are separate with no inheritance or fallback.

| Method and path | Request | Response and authorization |
| --- | --- | --- |
| GET base | Optional `department_id`, opaque `after` binding ID, `limit` from 1 to 100 (default 50) | `{bindings, next_after}` for the selected scope. Organization administrators can read organization rows. Authorized department members can read their selected department rows. |
| GET `/catalog` | Optional `department_id` | Provider descriptors and a scoped connector projection. Only organization administrators receive selectable channel IDs. |
| POST base | `{department_id?, connector_id, provider, channel_id, uses?}` | 201 with the new binding and revision 1. Signed-in organization administrator. |
| PUT `/{binding_id}/uses` | Optional `department_id` query. Body `{expected_revision, uses}` | 200 with updated binding. Replaces all three flags. Omitted flags are false. An identical replacement returns the current record. Signed-in organization administrator. |
| DELETE `/{binding_id}` | Optional `department_id` and required `expected_revision` query | 204 with no body. Signed-in organization administrator. |

`provider` must be registered in the server channel adapter catalog and match an existing connector in the same organization. The initial adapters are Telegram and Slack. Telegram accepts numeric chat IDs as strings. Slack accepts exact C/G channel IDs. Connector or channel display names and Telegram usernames are not registry identities. Registration checks syntax, tenant ownership, and current inclusion in the connector’s configured channels in one write transaction. It does not verify membership or channel reachability. The registry does not edit connector allowlists, department grants or saved workflows.

`uses` is a strict object with boolean `send_notifications`, `trigger_workflows`, and `approve_decisions`. They can be enabled independently. The API rejects unknown request fields and non-boolean flags. Binding responses contain `id`, `organization_id`, `department_id`, `connector_id`, `provider`, `channel_id`, `uses`, `revision`, `created_at`, and `updated_at`. Creation returns 409 for duplicate scope/connector/channel identity. Replacement and removal return 409 on stale revisions. Foreign resources and mismatched binding scopes return 404.

## Persistence and audit

The SQLite `channel_bindings` table stores the identity, three checked integer flags, positive revision and UTC timestamps. Identity is immutable through the API. The same connector/channel can be independently registered at organization scope and in different departments. Parent organization, department or connector deletion cascades to affected rows. The MCP connector remains the source of configured channel IDs and the existing runtime allowlist. A registry row references one of those IDs and stores only scope, uses, and revision metadata. Removing an ID in MCP prevents new bindings for it and preserves existing records for review or removal. Future runtime consumers must recheck current connector configuration and policy. Existing channel configuration is left in place without backfill.

Explicit mutations use a SQLite write transaction and recheck the current user's active organization-admin role before changing a row. Each effective mutation inserts an `audit_logs` row with entity type `channel_binding` and action `CHANNEL_BINDING_CREATED`, `CHANNEL_BINDING_UPDATED`, or `CHANNEL_BINDING_REMOVED`. It records the binding ID, verified actor, UTC timestamp, scope, connector, provider, exact channel ID, revision and resulting flags (last stored flags for removal). The projection contains no connector configuration, tokens, webhook secrets or provider response bodies. Parent deletion does not synthesize per-binding removal events.

The existing isolated API CI selection covers both providers, role and scope isolation, validation, optimistic revisions, pagination, independent flags, and audit projection. No live channel or provider calls are needed for those contracts.

## Dashboard

`/organization?tab=channels` shows the active department's bindings. Organization administrators can switch to the separate organization scope, register a channel, edit its uses, and remove it. Other department members have a read-only table. The form selects an existing MCP channel from the dedicated catalog. The catalog returns provider labels, configurable uses, runtime-supported uses, and a credential-free projection of connector IDs, names, providers, statuses and selectable channel IDs. The table labels missing connector status as unavailable. A connected badge describes the connector record; it does not verify access to a channel. The UI never receives connector configuration or callback URLs through the registry API. Trigger and approval uses are configurable with an unavailable runtime badge.

The channel selector shows the saved MCP channel name first, with the exact ID alongside it to distinguish duplicate names. It searches both and falls back to the ID when no name is configured. The catalog only returns labels for selectable IDs.

The bindings list adds nullable channel_name from the current MCP label for each visible binding. The table shows that name alongside the exact ID and falls back to the ID alone.
