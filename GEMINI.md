# Agent Execution Guidelines

- **Autonomous Execution**: Always execute necessary commands, file edits, and tools autonomously without hesitation or asking for confirmation.
- **Direct Action**: Do not ask the user to manually run commands that can be executed directly via available tools.
- **Non-blocking**: When proposing solutions, implement them immediately and verify results.
- **No Automated Tests**: Do NOT run `pytest` or automated test suites unless the user explicitly asks to run tests.
- **Mandatory `AGENTS.md` & Documentation Synchronization (Backend & UI)**:
  - **Backend Logic Changes**: Every time backend logic, API endpoints (`poc/backend/api/`), database schemas (`poc/persistence.py`), security/auth (`poc/backend/security/`), runtime (`poc/runtime/`), orchestration (`poc/orchestration/`), or workflows (`poc/workflows/`) are modified, you **MUST** update the corresponding `AGENTS.md` (and `CLAUDE.md` if applicable) in that directory as part of the same task.
  - **UI / Frontend Changes**: Every time UI pages (`poc/dashboard/src/pages/`), components (`poc/dashboard/src/components/`), contexts (`poc/dashboard/src/context/`), i18n dictionaries (`poc/dashboard/src/i18n/`), API services (`poc/dashboard/src/services/`), or canvas engine (`poc/dashboard/src/engine/`) are modified, you **MUST** update the corresponding `AGENTS.md` (and `poc/dashboard/CLAUDE.md` / `poc/dashboard/AGENTS.md`) in the same task.
  - **Subagent Enforcement**: Whenever delegating implementation tasks to `backend-builder`, `frontend-builder`, or `quick-fixer`, instruct them to update the relevant `AGENTS.md` files alongside their code changes.
- **Context Optimization & Subagent Delegation**:
  - Keep the main orchestrator context lean and focused by delegating file exploration and focused implementation tasks to subagents (`code-scout`, `frontend-builder`, `backend-builder`, `quick-fixer`).
  - Select the appropriate model tier per task when invoking subagents:
    - `flash_lite`: Very simple lookups, tiny 1-file edits, imports, or text/translation tweaks (`quick-fixer`, simple `code-scout`).
    - `flash`: Standard codebase scouting, focused React components, API wiring, or standard FastAPI endpoint additions (`code-scout`, `frontend-builder`, `backend-builder`).
    - `pro`: Complex multi-file architecture, intricate state/security logic, or deep refactoring.
