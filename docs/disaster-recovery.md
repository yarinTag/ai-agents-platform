# Credential and state recovery

Use this guide with the [operations runbook](operations-runbook.md).

1. Scope the incident by organization, connector, account, binding and time window. Pause affected ingress or channel actions. Preserve a consistent database backup and relevant receipt metadata in restricted storage.
2. If a person was compromised, revoke the affected provider link and remove or suspend the platform access that granted authority. If a bot or grant was compromised, disable the affected channel uses or revoke the exact department grant. Verify current authority and review outstanding and already-claimed decisions separately.
3. Assign owners for provider rotation, platform updates and restoration. Rotate during the same containment window so active receivers and senders have consistent credentials.

| Provider | Provider boundary | Platform boundary |
| --- | --- | --- |
| Telegram | Replace an exposed bot credential through the authorized bot owner. Configure the intended receiver URL, secret and required events for the connector mode. | Update the exact bot connector and rotate its webhook proof secret through the audited identity-secret endpoint. Verify account and ingress mode. Review existing links and cards issued under the old configuration. |
| Slack | Replace the exposed signing secret or installation credential through the app owner. Check Events API subscriptions and any linking slash-command endpoint. | Update the exact connector and rotate signing configuration with the expected workspace and app IDs. Verify the signed handshake and a new allowed event separately. Interactive Slack approval cards remain unsupported. |
| GitHub | Revoke the exposed credential and issue a replacement scoped to required repositories and operations. | Update the exact connector and recheck repository and department grants. Verify an authorized read before restoring writes. Reconcile pending receipts and refresh review evidence and approvals before new merge attempts. |

Proof rotation invalidates outstanding challenges. Existing links require separate review. Re-linking cannot restore the exact Telegram link tied to a consumed final claim. See [identity recovery](identity-proof-runbook.md), [webhook setup](webhook-ingress.md) and [GitHub governance](github-pr-governance.md).

## Restore a backup

1. Fence all affected writers and validate the backup against the deployment version. Identify its cutoff relative to provider deliveries, dispatches and approval claims.
2. Compare provider effects against surviving receipts. A backup taken before a side effect cannot establish that replay is safe. Keep workers isolated while reconciling unclear outcomes.
3. Reapply required revocations and rotations through authorized admin controls. Restore one database and receiver, then follow a newly authorized event to its run before reopening the remaining routes.

Procedures were checked against repository source. Provider rotation, restores and delivery require a separately authorized deployment exercise.
