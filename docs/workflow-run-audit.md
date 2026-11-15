# Workflow run audit and recovery

The execution ID correlates the persisted event dispatch, exact workflow revision and principal, step and task records, approval decisions and connector receipts. Channel dispatches retain the sender and principal separately. When ingress retention has removed the dispatch, the projection uses the captured execution context where available. It does not reconstruct missing facts.

The execution detail API returns a read projection under the same current execution scope as logs. Approval summaries include the actor, source when recorded, decisions and last delivery status. Connector receipts show the last 100 matching GitHub or Telegram/Slack sends and selected provider identifiers. Request arguments, message bodies, callback tokens and credentials are excluded. Existing provider receipts and step evidence remain separate from execution success.

The ingress worker already reclaims expired processing leases. The card worker additionally transitions a stale SENDING claim to UNCONFIRMED after five minutes. Initial sends with unknown outcomes require channel inspection. Use the dashboard for any still-pending approval. Never replay a decision or a side-effecting provider call merely because its receipt is absent. Existing message edits can reconcile toward the persisted state.

This first slice uses the existing operational records. External tamper-evident storage and non-repudiation, broader recovery tooling and post-retention provenance are outstanding. The UI provides review and connector-inspection links. It does not offer a replay or re-request action.
