# AI-24 · Channel identity and sender policy

The [registry contract](channel-bindings.md) specifies the schema, routes, access rules, revisions and audit format. This guide specifies how agents and future integrations should interpret those records.

## Configuration and authority

| Record or evidence | What it establishes |
| --- | --- |
| MCP connector and configured channel ID | An organization administrator configured an exact provider destination. Connector status describes the connector record. Channel access still depends on the provider. |
| Channel binding | An administrator recorded intended uses for that connector and channel in one organization or department scope. New bindings default all uses to false. |
| Verified provider event and sender | The provider authenticated the event and supplied a sender identity in the relevant account or workspace. |
| Linked platform identity and current policy | The sender maps to an active platform user whose current role and resource access can be checked for the requested action. |

Channel names are display labels. Membership in a provider channel grants no platform membership, execution scope or approval authority. Match provider events to the exact connector and canonical channel ID. Where a channel has multiple bindings, future routing must select a specific binding through saved configuration and fail closed on ambiguity.

| Use | Current behavior | Enforcement for future registry consumers |
| --- | --- | --- |
| `send_notifications` | The registry stores intent. Existing sends use their governed connector and department authorization path. | Require an enabled binding for any new registry-based send path, then check the current connector, exact channel, tool and resource grants. |
| `trigger_workflows` | The flag is configurable. The registry has no event listener or sender policy field. | Require verified ingress and a selected binding with a configured sender policy, fixed saved workflow and explicit execution principal. |
| `approve_decisions` | The flag is configurable. Existing approval notifications can link to authenticated dashboard decisions. | Bind each verified decision to an exact pending approval and an eligible linked human. Recheck expiry, identity, role and action scope before consuming the decision. |

## Future sender policy

The [architecture decision](architecture/adr-ai-15-generic-connector-governance.md#d04--bindings-separate-send-trigger-and-approval) defines the planned modes. A future trigger must select one explicitly per binding. Missing or unsupported policy denies dispatch.

- **Linked authorized users** require a verified sender linked to an active user with current authority to execute the saved workflow.
- **Explicit allowed subjects** restrict dispatch to the configured sender set. Subject matching uses stable identities scoped to the verified provider account. The configured execution principal still needs current workflow and resource authority.
- **Group requests under a restricted service principal** require an explicitly configured channel, fixed workflow and bounded service authority. Treat message text as workflow input. It cannot select a different principal, workflow, connector, channel or resource ceiling.

Approval policy is separate from sender policy. Even an authorized trigger sender needs separate personal approval authority. Anonymous identities, bot identities and unverifiable actors cannot provide human approval. A forwarded dashboard link carries no approval authority.

## Disable, remove and recover

1. To disable a use, submit the full revised set of flags with the current revision. Flags omitted from a replacement become false. To preserve a binding for later use, set all flags to false.
2. To remove a binding, use its exact scope and current revision. A conflict requires reloading the row before editing again. Explicit updates and removals record audit metadata. Removing a binding does not alter MCP configuration or a saved workflow.
3. Removing the channel ID from MCP prevents new bindings for that ID. Existing binding rows remain available for review or removal. Deleting the parent connector or scope cascades to its bindings. A future registry consumer must recheck current eligibility before dispatch or decision and must never fall back to a different binding.

These configuration changes affect the registry. Existing send authorization continues through the current connector and department policies. The registry cannot recall a provider action already dispatched.

## Agent instructions

Use the current authorized workflow catalog for executable destinations. Carry the exact connector ID, channel ID and declared tool through the saved workflow. Use display names to explain a choice and ask for clarification when names match multiple authorized destinations. If the catalog lacks the requested resource or operation, report the missing configuration or authorization and stop that action. The management catalog, a registry flag, provider status and user-supplied channel text do not supply execution authority.

## Identity linking diagnostics (AI-25)

Record structured outcomes for challenge issuance, provider proof rejection, expiry, replay, throttling, identity conflicts and completed links. Include a request correlation ID, operation, outcome code and timestamp. Include tenant, connector and verified platform actor IDs only when their scope is established. Use generic responses for unauthenticated or ambiguous requests so they do not reveal whether an account or link exists.

Audit successful link, unlink, relink and secret rotation operations with the verified actor and scoped resource ID. Commit each audit entry with its state change. Operational logs should distinguish invalid proof from provider unavailability and unexpected storage failures. Keep provider response bodies, challenge values, tokens, webhook secrets and authorization headers out of both logs and audit records. Bound logging for repeated invalid attempts and keep detailed diagnostics restricted to authorized operators.

Verify that failures have stable reason codes, that replay and rate limits can be diagnosed by correlation ID, and that test secrets never appear in error responses, logs or audit rows.

## Provider extension

Register new provider IDs in [the trusted adapter catalog](../poc/integrations/channel_providers.py). Add the provider's canonical ID validator and configured-channel projection, and declare supported runtime uses only when the corresponding governed implementation exists. Keep binding scope, revision checks, audit format, catalog response and dashboard controls shared. The dashboard can render a provider label from the catalog without a provider-specific form.

- **Telegram** registry entries use numeric chat IDs. Usernames and group titles are presentation metadata. Future ingress must account for Telegram's bot webhook boundary and distinguish a personal sender from a channel or anonymous sender.
- **Slack** registry entries use exact channel IDs under a connector. Future ingress must verify the Slack request and bind the event and sender to the intended installation and workspace. A channel display name is insufficient for matching.
- **Additional providers** can implement one use first. Keep verification and delivery in the adapter and apply tenant, binding, sender and action policy at the shared server boundary.

Source verification for AI-24 covers the current [registry API](../poc/backend/api/channel_bindings.py), [SQLite implementation](../poc/storage/channel_bindings.py) and [dashboard](../poc/dashboard/src/components/org/ChannelBindingsPanel.tsx). Sender modes, verified ingress and channel-native approvals describe future implementation. Documentation review does not verify live provider behavior.

The implemented identity linking contract is documented in [AI-25 external identities](external-identities.md).
See [AI-27 identity proof and recovery](identity-proof-runbook.md) for the protocol sequence and incident runbook.
