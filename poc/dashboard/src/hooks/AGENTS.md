# Dashboard hooks

## useOfficeEvents
`useOfficeEvents(executionScope: 'all' | 'office' = 'all')` manages initial agent/task snapshots and the shared SSE subscription. Office and Live Flow pass office; Tasks uses all. Office snapshots request execution_scope=office, exclude dedicated workflow agents and their tasks, and derive running status from visible office tasks. Live task/agent subscriptions ignore workflow_execution_id payloads and workflow/playground task IDs, including background runner agents. Backend SSE origin enrichment covers legacy step IDs and recursive descendants. Subscription cleanup runs on scope changes/unmount; the global event stream is not disconnected for other consumers. New task/agent events remain reactive without a polling loop.
