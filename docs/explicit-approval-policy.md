# Explicit checkpoint approval policy

Every new DAG checkpoint can select params.dag_approval.mode:

| Mode | Who may decide? |
| --- | --- |
| INDEPENDENT (default) | An eligible person other than the execution initiator and saved workflow-revision author |
| CONTINUATION | Any eligible person, including the initiator or revision author |

Eligibility still requires a current active account, organization/department scope,
a configured approver role, and a verified personal identity for provider decisions.
Continuation is a personal confirmation/pause, not permission to execute tools.
Quorum counts distinct currently eligible people; mode never turns one vote into
multiple approvals. Current initiator authority and counted voters are rechecked
before the one-time continuation claim. Expiry, changed workflow revision, revoked
access and duplicate decisions retain their existing denial behavior.

Example native configuration:

```yaml
params:
  dag_approval:
    mode: CONTINUATION
    approver_roles: [MANAGER, ORG_ADMIN]
    quorum: 1
    timeout_seconds: 86400
```

The visual builder exposes Approval policy. Create with AI proposals preserve and
show approval_checkpoint.mode; model instructions choose Continuation only for an
explicitly requested personal confirmation. Proposal confirmation still validates
current resources and the native definition. Pending/history details and Telegram/
Slack checkpoint cards display the frozen mode. The decision request is unchanged
({approve:boolean}); there is no mode override on a click.

## Server-owned protected action boundary

An exact governed GitHub comment/review step (pr_write_approval) cannot use a
Continuation checkpoint. Validation rejects it even through direct YAML/JSON/API;
suspension also rejects a protected manifest with that mode. Actual write admission
rechecks the frozen mode and current independent quorum before preparing any tool
scope. Neither editor nor model can waive that requirement. Tenant/tool/resource
capabilities and provider receipts remain independently mandatory.

This change applies to DAG approval checkpoints. The separate terminal
human_approval PR/merge protocol keeps its existing grants, pinned evidence,
authority checks and receipts; the new mode does not alter or relax that protocol.
This is not a universal risk classifier for arbitrary model text, filesystem work
or every external effect. Adding another action that requires independent approval
must connect it to the server-owned protected-action contract, not trust a label.

## Compatibility and saved requests

Omitted mode means INDEPENDENT for old definitions and frozen policy_json. Legacy
separate_initiator:true remains accepted as an independent constraint; false is not
an alternate opt-out. Combining that legacy constraint with CONTINUATION is rejected.
The visual editor removes the legacy flag when saving an explicit mode.

The policy is frozen when a request is created. No database column/migration or
retroactive rewriting is performed. Existing pending cards, including earlier test
requests, retain their old independent policy. To use Continuation, save that mode
in the workflow and start a new run; editing does not reauthorize an older request.
No active workflow, grant, identity link, pending decision or provider message was
changed during this implementation.

Verification uses guarded real SQLite/FastAPI/engine and signed provider fixtures,
plus dashboard typecheck/unit/build. Fixture callbacks prove server behavior, not
a new live Telegram decision or a deployed application restart.

## Verification record

22 new policy cases passed against actual SQLite/FastAPI/engine and signed callback
fixtures; 67 existing Telegram/ingress/chat/PR regression cases passed. Network/DNS
and child processes were blocked during backend verification. Frontend167 tests,
TypeScript and production build passed; lint reported existing warnings. A Chrome
component harness verified English/Hebrew policy selection, keyboard activation
and removal of the legacy flag from the serialized CONTINUATION configuration.
It used the actual component/I18n provider, with no API/credentials/execution; this
is not a claim that a full live workflow or new Telegram card was exercised.
