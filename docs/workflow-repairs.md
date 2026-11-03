# Saved workflow repair ledger — 2026-11-03

The user requested repair after inspecting the latest failed workflows. Direct SQLite data maintenance was used, without importing/starting the application or retrying any execution. Both repairs committed in one BEGIN IMMEDIATE transaction, checked organization/department ownership and expected revision, appended complete workflow_revisions snapshots using the existing version-field contract, and wrote workflow.configuration.repair audit entries. Actor label: Codex — user-requested repair; actor_id intentionally null rather than impersonating a database user.

| Workflow | Before | After | Repair |
| --- | --- | --- | --- |
| wf_3709225097e34dcf95af90af64b80596 — Summarize t-skills repository activity | Revision 6 referenced deleted product-manager | Revision 7 | Step now references the existing workflow-owned wf-agent-wf_3709225097e34dcf95af90af64b80596. Its org/department/workflow ownership was checked. No agent was created and no grants expanded. |
| wf_fef85e5ae4234c75b11891512b4f6bda — Open PR Senior Architect Review & Telegram Summary | Revision 3 omitted Telegram tool_name | Revision 4 | send_telegram_summary authorized_resources adds tool_name=send_message on its existing connector/channel. Existing channel allowlist, department grant and source dependency were checked. No destination, permissions or delivery was changed. |

Both definitions remain inactive with no cron schedule. Historical FAILED executions, receipts and task records are unchanged. No model calls, PRs or messages were executed. These are configuration repairs, not successful end-to-end runtime verification.

The Core plugin patch PR workflow was not rewritten or retried. Its two stored failures contain only the generic sandbox startup error, with zero model usage and no runtime events. Source now provides sanitized Docker startup categories for future failures, but historical logs do not reveal the original Docker cause. Existing backend stdout/stderr points to the interactive terminal, not a retained file. Persisted Docker Desktop logs were inspected without running Docker commands and did not establish the failed startup cause. Read-only Docker status/image inspection was separately requested because the project prohibits runtime verification by default.

## Authorized read-only Docker inspection
The user explicitly allowed read-only Docker diagnostics. Sandbox socket access was denied, so the same read-only queries were run with tool escalation; this tool sandbox denial is not evidence of the backend failure. Docker reports server 27.3.1, Linux/aarch64, 8 CPUs and 8218251264 memory bytes. The configured debian@sha256:99c0b25c46d0214d5a2091092e7908907dcaecd6a962cde0ac700acee222b6f3 exists locally as Linux/arm64. Both backend worker processes have that same PLATFORM_SANDBOX_IMAGE value. No running sandbox containers remained. These checks do not reproduce the historical startup failure.

No image was pulled, no container started, and no workflow/model/message was run. A separate permission request was made for one disposable network-disabled, read-only diagnostic container running only sleep 0 with the sandbox resource settings. That exception is still pending; read-only inspection approval was not treated as authorization to start it.

## Explicitly authorized one-container startup probe
The user separately authorized exactly one disposable diagnostic container. It used the cached configured Debian digest, --pull=never, no network, no capabilities, no-new-privileges, read-only root, 512 MiB tmpfs, 256 PIDs, 4 GiB memory, 2 CPUs, the current numeric UID/GID, and a read-only bind of an empty temporary directory at /workspace/repo. The only container command was sleep 0. Result: exit code 0, empty stdout/stderr. --rm plus explicit cleanup was used and the temporary directory was removed.

This verifies that these minimal startup settings work now. It does not establish the historical failure cause, writable repository mount behavior, model tools, inference, PR publication or Telegram delivery. No workflow was retried and no paid model call, test suite or message send occurred. Saved repairs remain revisions7/4, inactive; historical failed executions remain unchanged.
