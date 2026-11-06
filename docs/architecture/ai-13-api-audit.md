# AI-13 API audit evidence — 2026-11-06

[Ticket AI-13](https://trello.com/c/SZTb19BB) ·
[Generic contract / source matrix](connector-governance-contract.md)

## Authorized scope and result

The user explicitly authorized local API-only tests going forward, using real APIs/storage,
without agents. This supersedes the earlier blanket local-test restriction only for that
scope. No model/provider call, live message/merge, application startup or deployment occurred.
No new production endpoint or policy change is introduced by AI-13.

Final local run: **39 passed, 0 failed, 6 deprecation warnings, 13.77 seconds** on Python3.11.
The earlier baseline had36 cases; the final version adds unassigned/disabled accounts and
mixed global-manager/department-member HTTP cases. Only the final result is acceptance evidence.

Command:

```sh
rtk proxy python3 poc/tests/run_api_audit.py \
  --report-dir /private/tmp/ai13-api-audit-2026-11-06-final
```

Local artifacts (outside Git):

- `/private/tmp/ai13-api-audit-2026-11-06-final/api-audit.xml`
- `/private/tmp/ai13-api-audit-2026-11-06-final/api-audit.log`
- `/private/tmp/ai13-api-audit-2026-11-06-final/api-audit-summary.json`

The six warnings concern existing FastAPI/Starlette TestClient httpx deprecation and five
existing Pydantic class-based Config declarations. No checks were disabled to suppress them.

## Isolation and reproducibility

The runner copies tracked source plus three explicitly named audit files to a disposable
source directory. It excludes working data, workspaces, env files and symlinks; provider
credentials/DB URLs are not inherited by the pytest child. Legacy persistence/config
singletons therefore initialize under that copy, not the user's application checkout.
Each API fixture uses its own temporary SQLite DB and the real dependency injection seam.

The app is a real FastAPI instance using the production router registry, identity/resource
policy and JSON projection. Its application lifespan is not started. Runtime capability is
actually disabled; the optional authoring selection returns null rather than a fake model.
An interpreter audit hook rejects network connections/DNS and child processes. This is a
fail-closed test I/O policy, not a mock provider returning synthetic success.

Static agent definitions are stored only where the current API requires ownership/assignment
records. No start_task/resume/inference runs. Two existing report-approval HTTP tests exercise
actual DB decision transitions without PR subjects, so no merge/provider call is possible.

## HTTP coverage

| Area | Evidence |
|---|---|
| Connector read matrix | GitHub/Telegram/Slack × admin/manager/operator/member; redaction and foreign-tenant404. |
| Connector mutation boundary | Non-admin install/update denied; persisted name remains unchanged. |
| Effective authoring catalog | Known executable tools versus descriptive-only Postgres metadata; no credentials; no live runtime/model selected. |
| Department grants | Admin grant actor stamped from current identity; exact merge server operation appears only with explicit grant; no model merge tool. |
| Revocation/current policy | Same token observes removed connector access immediately; record is retained rather than deleted. |
| Scope isolation | Empty-grant department has no connector capabilities; unauthorized dept/foreign tenant requests denied. |
| Unknown grants | Legacy unknown names may be stored but never create an executable capability. |
| Write wildcard | Read wildcard can reveal implemented reads; it never authorizes merge server operation. |
| Workflow authoring | Member saves an inactive plan; activation/execution denied; no execution/task/tool-call record created. |
| Account edge cases | Unassigned and disabled accounts denied; global manager capped by MEMBER department cannot activate its authored plan. |
| Current identity/roles | Selected existing HTTP tests cover stale role claims, current membership, own-org admin, crossrefs and department transfer409. |
| Human gate APIs | Selected existing HTTP tests cover ownership/current manager, actual actor stamping, duplicate decision409 and expiry. |
| Callback boundary | Unauthenticated legacy Telegram/Slack callbacks remain denied and create no task. |

Source inventory: `poc/tests/run_api_audit.py:API_CONTRACTS`; new coverage:
`poc/tests/test_generic_governance_api.py`. CI adds backend matrix suite `api` and uploads
JUnit/summary artifacts; its required gate includes this matrix result.

## Material findings and acceptance limits

1. **No generic adapter descriptor/action IR yet.** Current executable dispatch remains
   GitHub/Telegram/Slack-specific; metadata records for other providers are not integrations.
2. **Readiness is overstated by legacy terminology.** CONNECTED/test_connector do not prove
   a provider handshake, and execution_supported is configuration-only. P02/P03/P05 must
   separate configured, implementation-supported, authorized and provider-verified states.
3. **Channel trigger metadata is not event delivery.** No verified listener/router implementing
   trigger_enabled was found. P04–P06 own identities/ingress/trigger principals.
4. **Approval is a terminal slice.** Dashboard decision is implemented; arbitrary DAG resume,
   quorum and verified channel-native decisions remain P07/P08 work.
5. **Existing grant representation is legacy.** Unknown names and absent-department low-level
   semantics must not become authority in new generic APIs; P01 owns typed/versioned policy.

These are source-backed gaps, not fixes silently included in an audit ticket. Later tickets
must reuse the existing guarded components and record their own API evidence. This audit does
not prove live connectivity, model planning, provider-side authorization/branch protection,
real CI rerun, real merge/send, browser flows, webhook authenticity or crash-safe DAG resume.
