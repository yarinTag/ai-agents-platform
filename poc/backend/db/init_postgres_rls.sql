-- ============================================================================
-- Enterprise Multi-Tenant PostgreSQL Schema with Row-Level Security (RLS)
-- AI Agents Platform Control Plane (Production DDL)
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1. Organizations (Root Tenant Domain)
CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}'::jsonb,
    plugins_source_mode VARCHAR(32) DEFAULT 'LOCAL',
    plugins_local_path TEXT,
    plugins_git_repo TEXT
);

-- 2. Departments (Budget Cap & MCP Isolation Scope)
CREATE TABLE IF NOT EXISTS departments (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    monthly_budget_usd NUMERIC(12, 2) DEFAULT 500.00,
    alert_threshold_pct INTEGER DEFAULT 80,
    budget_action VARCHAR(32) DEFAULT 'HARD_STOP',
    current_month_spend_usd NUMERIC(12, 2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_departments_org ON departments(organization_id);

-- 3. Users & RBAC
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(32) DEFAULT 'MEMBER', -- ORG_ADMIN, MANAGER, OPERATOR, MEMBER
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id);

-- 4. Department Members Junction
CREATE TABLE IF NOT EXISTS department_members (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id VARCHAR(64) NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    user_id VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(32) DEFAULT 'MEMBER',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(department_id, user_id)
);

-- 5. Autonomous Agents
CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id VARCHAR(64) REFERENCES departments(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL,
    model VARCHAR(128) NOT NULL,
    system_prompt TEXT,
    parent_id VARCHAR(64) REFERENCES agents(id) ON DELETE SET NULL,
    allowed_child_ids JSONB DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agents_org ON agents(organization_id);
CREATE INDEX IF NOT EXISTS idx_agents_dept ON agents(department_id);

-- 6. Task Runs & State Tracking
CREATE TABLE IF NOT EXISTS task_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) REFERENCES organizations(id) ON DELETE CASCADE,
    department_id VARCHAR(64) REFERENCES departments(id) ON DELETE SET NULL,
    agent_id VARCHAR(64) NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    project_id VARCHAR(64) DEFAULT 'default',
    prompt TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'PENDING',
    priority INTEGER DEFAULT 5,
    result TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 5) DEFAULT 0.00
);
CREATE INDEX IF NOT EXISTS idx_task_runs_org ON task_runs(organization_id);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status);

-- 7. Supervisor & HITL Interactions
CREATE TABLE IF NOT EXISTS interactions (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) REFERENCES organizations(id) ON DELETE CASCADE,
    task_id VARCHAR(64) NOT NULL REFERENCES task_runs(run_id) ON DELETE CASCADE,
    requester_agent_id VARCHAR(64) NOT NULL,
    target_approver_id VARCHAR(64) DEFAULT 'HUMAN_OPERATOR',
    interaction_type VARCHAR(32) DEFAULT 'QUESTION',
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(32) DEFAULT 'PENDING',
    decision VARCHAR(32),
    resolution_response TEXT,
    resolved_by VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS idx_interactions_org ON interactions(organization_id);
CREATE INDEX IF NOT EXISTS idx_interactions_task ON interactions(task_id);

-- 8. Model Context Protocol (MCP) Connectors & Tool Governance
CREATE TABLE IF NOT EXISTS mcp_connectors (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(64) NOT NULL,
    status VARCHAR(32) DEFAULT 'ACTIVE',
    config JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS department_mcp_access (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id VARCHAR(64) NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    connector_id VARCHAR(64) NOT NULL REFERENCES mcp_connectors(id) ON DELETE CASCADE,
    is_enabled BOOLEAN DEFAULT TRUE,
    allowed_tools JSONB DEFAULT '["*"]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(department_id, connector_id)
);

-- 9. Workflows & Declarative DAG Playbooks
CREATE TABLE IF NOT EXISTS workflows (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    department_id VARCHAR(64) REFERENCES departments(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    yaml_definition TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    workflow_id VARCHAR(64) NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status VARCHAR(32) DEFAULT 'RUNNING',
    step_results JSONB DEFAULT '{}'::jsonb,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10, 5) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP WITH TIME ZONE
);

-- 10. Audit Trail (Immutable SOC2 Log)
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    action VARCHAR(128) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(64),
    payload JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_logs(organization_id, created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- Enforces tenant isolation at the database kernel level
-- ============================================================================

ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE department_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE task_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE interactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mcp_connectors ENABLE ROW LEVEL SECURITY;
ALTER TABLE department_mcp_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Macro Policy: Users can only see data belonging to their current organization
CREATE POLICY tenant_isolation_departments ON departments
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));

CREATE POLICY tenant_isolation_users ON users
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));

CREATE POLICY tenant_isolation_agents ON agents
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));

CREATE POLICY tenant_isolation_task_runs ON task_runs
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));

CREATE POLICY tenant_isolation_interactions ON interactions
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));

CREATE POLICY tenant_isolation_workflows ON workflows
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    FOR ALL USING (organization_id = NULLIF(current_setting('app.current_org_id', true), ''));
