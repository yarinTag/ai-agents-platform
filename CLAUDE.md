# CLAUDE.md - AI Agents Platform Root Repository Guide

Welcome to the AI Agents Platform codebase. This repository contains an enterprise autonomous agent management and orchestration platform with a virtual pixel office, real-time collaboration war room, cron scheduler, and hierarchical delegation engine.

---

## 🧭 Monorepo Structure & Quick Navigation

* **Backend (`poc/backend/`)**: FastAPI, SQLite3 (WAL), Cron Scheduler Engine, Claude Code Subprocess Adapter, SSE EventBus. See [`poc/backend/CLAUDE.md`](poc/backend/CLAUDE.md).
* **Frontend (`poc/dashboard/`)**: React 18, Vite, Ant Design, TypeScript, Pixel Office Canvas Engine. See [`poc/dashboard/CLAUDE.md`](poc/dashboard/CLAUDE.md).
* **Orchestration (`poc/orchestration/`)**: Multi-agent task trees, hierarchy depth validation, and `SupervisorResolver`. See [`poc/orchestration/AGENTS.md`](poc/orchestration/AGENTS.md).
* **Runtime Execution (`poc/runtime/`)**: Claude CLI adapter, subprocess isolation, stream-json event reader, and `--resume` continuation. See [`poc/runtime/AGENTS.md`](poc/runtime/AGENTS.md).
* **Security & Auth (`poc/backend/security/`)**: Authentication, rate limiting, correlation IDs. See [`poc/backend/security/AGENTS.md`](poc/backend/security/AGENTS.md).
* **Multi-Agent Teams (`poc/backend/teams/`)**: Team coordination, roles, and mission dispatch. See [`poc/backend/teams/AGENTS.md`](poc/backend/teams/AGENTS.md).
* **Agent-to-Agent Messaging (`poc/backend/messages/`)**: Peer-to-peer and hierarchical A2A message exchange. See [`poc/backend/messages/AGENTS.md`](poc/backend/messages/AGENTS.md).

---

## ⚡ Primary Verification Workflows

Before committing any changes, run both verification suites:

```bash
# 1. Run all Backend tests (zero mocks, real SQLite)
pytest poc/tests/ -v

# 2. Build Frontend (strict TypeScript compilation & bundle verification)
cd poc/dashboard && npm run build
```

---

## 🛡️ Core System Invariants

1. **Zero Mocks Policy**: We do not use mock database or fake execution layers in tests. All tests run against SQLite and real API routers.
2. **Autonomous Execution**: Proactively implement and verify solutions without blocking or asking the user to manually run commands.
3. **Multi-Tier Clarification Protocol**: If an agent lacks information, it invokes `ask_supervisor`. The system auto-resolves from Project Shared Memory first, routes to the direct manager second, or escalates to the human operator third—never abruptly ending the task as `COMPLETED`.
4. **Resumable Execution**: All agent runs capture `session_id` to allow resuming paused tasks with `--resume <session_id>` without re-running from scratch.
