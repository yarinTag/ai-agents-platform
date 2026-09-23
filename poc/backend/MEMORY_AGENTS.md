# AGENTS.md - Project Shared Memory & Knowledge Base Service

## 1. Service Identity & Mission
The **Project Shared Memory & Knowledge Base Service** (`poc/backend/api/memories.py`) is the persistent institutional brain of the platform. It prevents redundant discovery by enabling agents to persist architectural decision records (ADRs), coding conventions, operational insights, and post-mortem lessons that are immediately shared across all agents in the workspace.

---

## 2. Core Capabilities & Specializations
* **Taxonomy of Shared Knowledge**:
  * `🏛️ ADR`: Architecture Decision Records (e.g., "Use SQLite with WAL mode for concurrency").
  * `📏 CONVENTION`: Code standards & style invariants (e.g., "Pydantic v2 requires .model_dump()").
  * `💡 INSIGHT`: Technical findings discovered during execution (e.g., "Proxy port is 8082").
  * `📝 LESSON`: Post-mortem learning from failures or debugging sessions.
* **LLM System Prompt Injection (`/context-prompt`)**:
  * Automatically compiles all active memories for a project into a clean Markdown block:
    ```markdown
    # 🧠 PROJECT SHARED KNOWLEDGE & ACTIVE CONVENTIONS
    ### [ADR] Use FastAPI for Microservices
    All internal agent services must use FastAPI with Pydantic v2 schemas.
    *Tags: architecture, fastapi, python*
    ```
  * Injected directly into the system prompts of agents running tasks within that project.
* **Autonomous Resolution Integration**:
  * Queried in Tier 1 by the `SupervisorResolver` to immediately answer worker clarification questions without human intervention.

---

## 3. Interfaces & REST Endpoints

### API Endpoints
* `GET /api/v1/projects/{project_id}/memories` - List shared memories for a project (filterable by `category`).
* `POST /api/v1/projects/{project_id}/memories` - Save a new memory item, ADR, or convention.
* `DELETE /api/v1/projects/{project_id}/memories/{memory_id}` - Delete a memory item.
* `GET /api/v1/projects/{project_id}/context-prompt` - Retrieve formatted Markdown block for prompt injection.

---

## 4. Invariant Rules & Guardrails
1. **Category Enforcement**: Category must strictly be one of `ADR`, `CONVENTION`, `INSIGHT`, or `LESSON`.
2. **Project Scoping**: Memories must always be scoped to a valid `project_id`. Deleting a project cascades deletion to its associated memory pool.
3. **Prompt Injection Freshness**: Prompt compilation must be fast (<10ms) and dynamic, reflecting the latest state of memories upon every invocation.
