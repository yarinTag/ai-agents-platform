# Dashboard React hooks

This directory owns reusable React state/lifecycle hooks. Feature-specific hooks remain beside their owning pages or components; avoid importing page implementations into reusable hooks. Keep source files at most 500 physical lines.

## Obsolete request containment

useRequestGeneration provides stable begin/invalidate functions. A request generation remains current only while mounted and while no later request/context invalidation has superseded it. MCP and Calendar loading callbacks use it to ignore stale responses after refresh, context change or unmount. It performs no HTTP calls and does not replace server authorization. No build or runtime checks were run.

WorkflowHistoryDrawer also invalidates requests when workflow identity changes, clearing old revision rows before reading the selected history. Pagination and retries share the same generation owner.

Update this guide whenever reusable hook behavior changes. Existing useOfficeEvents remains the live Office/task event integration; its existing public behavior was not rewritten by the request-generation addition.


## useOfficeEvents
`useOfficeEvents(executionScope: 'all' | 'office' = 'all')` manages initial agent/task snapshots and the shared SSE subscription. Office and Live Flow pass office; Tasks uses all. Office snapshots request execution_scope=office, exclude dedicated workflow agents and their tasks, and derive running status from visible office tasks. Live task/agent subscriptions ignore workflow_execution_id payloads and workflow/playground task IDs, including background runner agents. Backend SSE origin enrichment covers legacy step IDs and recursive descendants. Subscription cleanup runs on scope changes/unmount; the global event stream is not disconnected for other consumers. New task/agent events remain reactive without a polling loop.


usePermissions reads AuthContext and services/accessPermissions.effectivePermissions to return
isAdmin,rank,canRead,canOperate,canManage. A non-admin gets min(account rank,current department
membership rank); missing/unknown membership gives0. ORG_ADMIN gets4 inside its own authenticated
organization. Flags control UI only; backend policy independently enforces each request. No tests
or hook execution performed locally.
