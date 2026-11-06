# AI Agents Platform

An enterprise-grade, multi-tenant autonomous AI agent orchestration, workflow automation, and governance platform. It combines hierarchical agent teams, visual & YAML DAG workflow execution, governed Model Context Protocol (MCP) connectors, sandboxed repository workspaces, real-time war room deliberations, and an interactive pixel office canvas under strict per-department budget and tool-access controls.

---

## ✨ Key Capabilities

| Pillar | Highlights |
| :--- | :--- |
| **🏢 Multi-Tenant Governance** | Organization & Department isolation, 4-tier RBAC (`ORG_ADMIN`, `MANAGER`, `OPERATOR`, `MEMBER`), monthly department USD budgets, configurable alert thresholds, and `HARD_STOP` spending enforcement. |
| **🔄 Visual & AI Workflows** | Declarative YAML/JSON playbooks, visual DAG builder, AI-assisted workflow authoring ("Create with AI"), revision history with optimistic concurrency, tool-free Playground runs, and RabbitMQ or local background execution. |
| **🔌 Governed MCP & Connectors** | Built-in connector catalog (GitHub, GitLab, Telegram, Slack, Trello, PostgreSQL, Brave Search, Filesystem), live zero-clone repository discovery, department tool whitelisting, and audited channel delivery receipts. |
| **📦 Sandboxed Repo Workspaces** | Ephemeral host-cloned Git workspaces mounted into network-isolated Docker containers (`PLATFORM_SANDBOX_IMAGE`) with optional HTTPS egress proxy allowlists, AES-GCM encrypted secrets, and receipt-verified draft PR creation. |
| **🤖 Autonomous Agent Hierarchy** | Reporting chains (`parent_id`, `allowed_child_ids`), multi-tier supervisor escalation (`Shared Memory ➔ Manager Agent ➔ Human Operator`), Agent-to-Agent (A2A) messaging, dynamic squads, and War Room councils. |
| **⚡ Direct Multi-Provider Runtime** | Provider-agnostic execution across Anthropic Claude, OpenAI (Responses & Chat), NVIDIA NIM, OpenRouter, and CLI runtimes with per-call token pricing, session cost ledgers, and provider-visible reasoning summaries. |
| **🎮 Interactive Pixel Office & UI** | React 19 + Ant Design `Robotic` UI toolkit, live 2D pixel office canvas streaming real-time SSE agent states, full English (`en`) and Hebrew (`he` RTL) localization. |

---

## 🏛️ System Architecture

```mermaid
flowchart TB
    subgraph Client["Frontend Dashboard (React 19 + Vite + Ant Design)"]
        UI_Office["Pixel Office Canvas & Live Flow"]
        UI_WF["Workflows Hub (Visual DAG / YAML / AI Chat)"]
        UI_Gov["Organization, Budgets & MCP Governance"]
        UI_Collab["War Room, Teams & Agent Chat Drawer"]
    end

    subgraph API["FastAPI Backend & Security Layer"]
        Auth["HS256 JWT + RBAC + Rate Limiter + Tenant Guard"]
        Routers["REST API Routers (/api/v1/*) & SSE EventBus"]
    end

    subgraph Core["Orchestration & Execution Engines"]
        Orch["Hierarchy & Supervisor Resolver"]
        WFEngine["Workflow DAG Engine & Revision Manager"]
        Sched["Cron Scheduler & Queue Worker (RabbitMQ / Local)"]
        Runtime["Direct HTTP & CLI Runtime Adapters"]
    end

    subgraph Governance["Connectors, Skills & Sandboxes"]
        MCP["Governed MCP Connectors (GitHub / Slack / Telegram)"]
        Plugins["Zero-Clone Git & Local Skill Scanner"]
        Sandbox["Docker Repo Sandbox + Egress Proxy"]
    end

    subgraph Storage["Persistence & State"]
        SQLite[("SQLite WAL / Postgres RLS")]
        Vector[("Qdrant Shared Memory")]
    end

    Client <-->|"REST + Auth SSE"| Auth
    Auth --> Routers
    Routers --> Orch & WFEngine & Sched
    Orch & WFEngine --> Runtime
    WFEngine --> MCP & Plugins & Sandbox
    Orch & WFEngine & Routers --> SQLite
    Orch --> Vector
```

---

## 🔐 Multi-Tenant Hierarchy & Tool Governance

Organizations partition users, agents, budgets, and MCP connectors by department. Every tool call or repository action is verified against live database grants before execution.

```mermaid
flowchart TD
    Org["Enterprise Organization"] --> DeptA["Department A (Monthly Budget Cap & HARD_STOP)"]
    Org --> DeptB["Department B (Monthly Budget Cap & HARD_STOP)"]

    DeptA --> RBAC["Members & RBAC Roles<br/>(ORG_ADMIN / MANAGER / OPERATOR / MEMBER)"]
    DeptA --> Agents["Department Agents & Dedicated Runners<br/>(Hierarchy Trees & wf-agent-{id})"]
    DeptA --> Grants["Department MCP Access Grants<br/>(Explicit Tool & Repo Whitelists)"]

    Agents --> Exec["Task / Workflow Step Execution"]
    Grants --> Exec
    Exec --> Policy{"Live Policy & Budget Gate"}
    Policy -->|"Authorized & Under Cap"| Connectors["GitHub Read/Write • Slack • Telegram"]
    Policy -->|"Unauthorized / Cap Exceeded"| Blocked["Fail Closed & Audit Log"]
```

---

## 🔄 Workflow Execution Lifecycle

Workflows support interactive AI authoring, visual step editing, tool-free Playground testing, and governed production execution with receipt-verified outcomes.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator / Trigger
    participant API as Workflows API
    participant Queue as RabbitMQ / Local Runner
    participant Engine as WorkflowEngine (DAG)
    participant Sandbox as Docker Workspace / Connectors
    participant Provider as AI Model Provider

    User->>API: Execute Workflow (Manual / Cron / Webhook)
    API->>API: Validate RBAC, Department Budget & SHA-256 Deduplication
    API->>Queue: Enqueue Execution (QUEUED)
    Queue->>Engine: Claim & Initialize Sandbox / Step Lineage
    loop Topological DAG Stages (Parallel & Conditional)
        Engine->>Sandbox: Preflight Check (Pinned Image, Egress Proxy, Grants)
        Engine->>Provider: Direct API Inference (with Shared Skills & Step Context)
        Provider-->>Engine: Reasoning Summary + Tool Calls + Token Usage
        Engine->>Sandbox: Execute Governed Tool / Repo Workspace Action
        Sandbox-->>Engine: Audited Execution Receipt (e.g., Draft PR / Channel Message)
    end
    Engine->>API: Persist Step Logs, Cost Ledger & Final Status
    API-->>User: Stream Live SSE Updates & Optional Completion Notification
```

---

## 🧠 Multi-Tier Agent Clarification Flow

When an autonomous agent encounters missing requirements or ambiguity, it never guesses or falsely marks work as complete—it escalates through a structured 3-tier resolution protocol:

```mermaid
stateDiagram-v2
    [*] --> Running: Task Dispatched
    Running --> AskSupervisor: Agent Calls ask_supervisor(question)
    AskSupervisor --> Tier1_Memory: Query Project Shared Memory (ADRs / Insights)
    Tier1_Memory --> Running: Auto-Resolved via High-Confidence Match
    Tier1_Memory --> Tier2_Manager: Unresolved -> Escalate to Parent Supervisor Agent
    Tier2_Manager --> Running: Manager Supplies Guidance
    Tier2_Manager --> Tier3_Human: Manager Unable to Resolve -> Escalate to Human
    Tier3_Human --> WaitingHuman: Task Paused (WAITING_FOR_HUMAN / ChatOps Alert)
    WaitingHuman --> Running: Operator Responds (Resumes Session ID)
    Running --> Completed: Audited Deliverable Produced
```

---

## 📂 Repository Structure

```text
ai-agents-platform/
├── poc/
│   ├── backend/                # FastAPI application, lifespan, middleware & domain modules
│   │   ├── api/                # REST routers (workflows, organizations, mcp, agents, tasks, etc.)
│   │   ├── approvals/          # Human-in-the-loop (HITL) approvals & Slack/Telegram callbacks
│   │   ├── chat/               # Interactive agent mini-chat & blocker resolution
│   │   ├── db/                 # Enterprise PostgreSQL RLS schema definitions
│   │   ├── events/             # In-memory pub/sub EventBus & persistent SSE streaming
│   │   ├── memory/             # Project shared memory (ADRs, conventions, Qdrant indexing)
│   │   ├── messages/           # Agent-to-Agent (A2A) structured messaging
│   │   ├── queue/              # RabbitMQ priority queues & dead-letter exchanges
│   │   ├── scheduler/          # Background cron polling & croniter forecasting
│   │   ├── security/           # HS256 JWT, PBKDF2 hashing, rate limiting, tenant guards
│   │   ├── teams/              # Multi-agent squads & deliverable synthesis
│   │   └── war_room/           # Multi-agent debate rounds & consensus synthesis
│   ├── workflows/              # DAG parser, execution engine, sandboxes & preflight checks
│   ├── runtime/                # Direct HTTP providers (Anthropic, OpenAI, NVIDIA, OpenRouter), pricing & CLI adapters
│   ├── orchestration/          # Hierarchy validation, supervisor chain & delegation service
│   ├── integrations/           # Governed GitHub, Telegram & Slack execution adapters
│   ├── plugins/                # Local filesystem & zero-clone GitHub API skill scanners
│   ├── storage/                # Composed SQLite repositories, records & connection management
│   ├── dashboard/              # React 19 + TypeScript + Vite + Ant Design frontend
│   │   └── src/
│   │       ├── canvas/         # 2D virtual pixel office engine & sprite animation
│   │       ├── components/     # Reusable `Robotic` UI component library & step editors
│   │       ├── context/        # Auth, Office SSE, and Notification state providers
│   │       ├── hooks/          # Custom hooks (permissions, SSE events, caching)
│   │       ├── i18n/           # Full English (en.ts) & Hebrew (he.ts) translations
│   │       ├── pages/          # Route views (Office, Workflows, Organization, MCP, War Room)
│   │       └── services/       # Typed HTTP client & domain API wrappers
│   ├── tests/                  # Real-SQLite, zero-mock integration & contract test suites
│   └── start_api.py            # Environment-aware Uvicorn launcher
├── docs/                       # Detailed architecture, security, runtime & workflow guides
├── AGENTS.md                   # Root architectural invariants & documentation index
├── CLAUDE.md                   # Developer guide & verification workflows
└── pyproject.toml              # Python dependencies & project metadata
```

---

## 🚀 Getting Started

### Prerequisites
* **Python**: `>= 3.11` (managed via `uv` or standard `venv`)
* **Node.js**: `>= 20.x` & `npm`
* **Optional Services**:
  * **Docker**: Required only for isolated repository workspace steps (`PLATFORM_SANDBOX_IMAGE`).
  * **RabbitMQ**: Optional distributed broker (`AMQP_URL`); falls back cleanly to local background execution.

### 1. Backend Setup

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

Create a `.env` file in the repository root with a strong JWT secret (at least 32 characters):

```env
# Required security secret (>= 32 characters)
JWT_SECRET_KEY=replace-with-a-random-32-byte-minimum-secret-key

# Optional: Encryption key for workflow secrets (32-byte base64 or hex)
# PLATFORM_SECRETS_KEY=...

# Optional: AI Provider API Keys
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# NVIDIA_API_KEY=nvapi-...
```

Launch the FastAPI server (automatically loads `.env` from the repository root):

```bash
uv run python poc/start_api.py
```
The API will be available at `http://localhost:8000` (health check at `GET /health` and readiness at `GET /health/ready`).

### 2. Frontend Setup

```bash
cd poc/dashboard
npm install
npm run dev
```
Open `http://localhost:5173` in your browser to access the platform dashboard.

---

## 🛡️ Security & Operational Principles

* **Fail-Closed Startup & Execution**: Requires a valid `JWT_SECRET_KEY` (`>= 32` characters) outside explicit dev mode (`PLATFORM_DEV_MODE=1`). Workflow steps fail closed if required connector grants, budget allowances, or sandbox prerequisites are missing.
* **Receipt-Backed Outcomes**: Channel notifications and draft Pull Requests require verified backend execution receipts—never trusting unverified model text claims.
* **Write-Only Encrypted Secrets**: Workflow secrets are encrypted at rest via AES-GCM (`PLATFORM_SECRETS_KEY`) or referenced via allowlisted AWS Secrets Manager ARNs, injected exclusively into container sandboxes, and automatically redacted from logs.
* **Zero-Mock Testing Philosophy**: Contract and integration tests run against real SQLite databases and real FastAPI routers rather than mocked persistence layers.

---

## 📚 Documentation Map

Detailed technical contracts and module guides are maintained across the repository:

* **Architecture & Root Guides**: [`AGENTS.md`](AGENTS.md) • [`CLAUDE.md`](CLAUDE.md)
* **Feature & Operations Guides**:
  * [Runtime Provider Setup](docs/runtime-provider-setup.md)
  * [Security Configuration](docs/security-configuration.md)
  * [Governed Connector Execution](docs/connector-execution.md)
  * [Capability Policy Configuration & Rollout (P01)](docs/governance-policy-guide.md)
  * [Policy Algebra, Roles & Agent Authority](docs/architecture/p01-policy-algebra.md)
  * [Governance API & Schema](docs/architecture/p01-governance-api.md)
  * [Sandboxed Repository Workspaces](docs/repo-workspaces.md)
  * [Workflow Settings & Secrets](docs/workflow-settings.md)
  * [AI Workflow Creation Chat](docs/workflow-chat.md)
* **Module Contracts**:
  * [Backend Core](poc/backend/AGENTS.md) & [REST API Routers](poc/backend/api/AGENTS.md)
  * [Workflows Engine](poc/workflows/AGENTS.md) & [Runtime Abstraction](poc/runtime/AGENTS.md)
  * [Orchestration & Hierarchy](poc/orchestration/AGENTS.md) & [SQLite Storage](poc/storage/AGENTS.md)
  * [Frontend Dashboard](poc/dashboard/AGENTS.md) & [UI Component Library](poc/dashboard/src/components/AGENTS.md)
