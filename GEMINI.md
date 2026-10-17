# Agent Execution Guidelines

- **Autonomous Execution**: Always execute necessary commands, file edits, and tools autonomously without hesitation or asking for confirmation.
- **Direct Action**: Do not ask the user to manually run commands that can be executed directly via available tools.
- **Non-blocking**: When proposing solutions, implement them immediately and verify results.
- **No Automated Tests**: Do NOT run `pytest` or automated test suites unless the user explicitly asks to run tests.
- **Context Optimization & Subagent Delegation**:
  - Keep the main orchestrator context lean and focused by delegating file exploration and focused implementation tasks to subagents (`code-scout`, `frontend-builder`, `backend-builder`, `quick-fixer`).
  - Select the appropriate model tier per task when invoking subagents:
    - `flash_lite`: Very simple lookups, tiny 1-file edits, imports, or text/translation tweaks (`quick-fixer`, simple `code-scout`).
    - `flash`: Standard codebase scouting, focused React components, API wiring, or standard FastAPI endpoint additions (`code-scout`, `frontend-builder`, `backend-builder`).
    - `pro`: Complex multi-file architecture, intricate state/security logic, or deep refactoring.
