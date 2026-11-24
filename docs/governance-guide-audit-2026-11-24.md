# AI-48 guide and release evidence audit — 2026-11-24

Source baseline: master `fe796b7b88d37ca9f4cdaebc470d94e7f17e3afd` (PR67).
Its complete CI passed: [run45250585894](https://github.com/yarinTag/ai-agents-platform/actions/runs/45250585894).

## Corrections

- Root AGENTS/CLAUDE canvas index now points to the existing dashboard engine guide.
- Retired Workflow Assistant routes, draft tables and internal MCP descriptions in
  backend/API guides are explicitly retired rather than presenting removed modules
  as callable APIs. Current authoring points to Workflows chat.
- The historical root schema reference is marked removed; no deleted schema was restored.
- Runtime relevance output cap agrees with source:1,024 tokens, ten-second deadline.
- Root sandbox planning distinguishes the recorded AI-51 pilot decision from still
  outstanding cluster acceptance; no infrastructure ticket is declared complete.
- The release table now incorporates actual Chrome/model results through PR67,
  the user-deferred Firefox/Slack limits, and the current live connector blocker.

- Frontend framework declarations now match package.json: React19, Ant Design6 and React Router7. Vite build is distinguished from the separate TypeScript check.

## Verification and limits

All38 tracked AGENTS.md/CLAUDE.md files were inventoried; all171 local Markdown
link targets resolve after correction. `git diff --check` passed. The changed
runtime, storage, worker and UI contracts were compared with their implementation
and the PR65–67 acceptance records. This is a documentation/index audit; structural
link checks do not establish semantic correctness of every historical capability
or runtime/provider readiness. No build, model, provider, migration, deployment or
production mutation was run for these documentation-only corrections.

The [release checklist](governed-workflow-release.md) remains the sign-off record.
AI-46 migration/tenant evidence is complete. Core Chrome observations and eight
live classifier smoke cases are recorded separately from provider transport tests.
The latest combined Telegram attempt admitted no execution and was cleaned exactly.
Persistent proof/polling setup still requires the pending specific approval.
AI-47/49 and final AI-48/AI-12 sign-off remain open; no Done move is implied by this audit.
