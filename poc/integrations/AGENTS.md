# Optional external adapters

`channels.py` contains the single Telegram/Slack message delivery implementation used by MCP verification and workflow notifications. It has no startup/container imports. `find_channel_connector(database, provider, organization_id)` selects a connector only from the supplied tenant's catalog. `resolve_telegram_target` retains configured-chat placeholder resolution. `deliver_channel_message` accepts a configured connector, target and text, sends once with a five-second timeout, and succeeds only after HTTP 200 and provider `ok=true`.

Telegram uses bot_token and chat_id/allowed_channels; Slack uses bot_token and the selected channel through chat.postMessage. Missing credentials/connectors or unsupported providers raise ChannelDeliveryError. Exceptions shown to users omit credential-bearing URLs and provider bodies. There are no automatic retries or simulated successes.

MCP POST `/api/v1/mcp/test-channel-message` returns 503 for an absent connector, 400 for delivery/configuration rejection, and the existing success envelope with delivery=delivered only on acknowledgement. If an audit actor exists, mcp_tool_calls progresses STARTED → COMPLETED or FAILED. No new schema columns are introduced.

WorkflowNotifier is an optional composed adapter; notification exceptions never change workflow execution outcome. Audit IDs use call_notify_{execution_id}; an existing call is not automatically resent. Unconfigured connectors/no audit actors are logged as unavailable without claiming delivery. Delivery acknowledgement/audit are not a transactional exactly-once guarantee; no outbox or retry worker is introduced. All source files stay at most 500 physical lines. No messages were sent and no runtime checks were performed in this task.
