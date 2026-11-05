import { Department } from '../../types/auth';
import { PlatformWorkflow } from '../../types/mcp';
import { WorkflowCanvasStep } from '../workflows/WorkflowCanvasGraph';

export interface ParsedWorkflowTrigger {
  type: 'cron' | 'webhook' | 'channel' | 'manual';
  label: string;
  provider?: string;
}

export interface ParsedWorkflowChannel {
  provider: string;
  channelId: string;
  channelName?: string;
  source: 'binding' | 'step_action';
  stepKey?: string;
}

export interface EnrichedWorkflowNode {
  workflow: PlatformWorkflow;
  departmentId: string;
  runnerAgentId: string;
  triggers: ParsedWorkflowTrigger[];
  steps: WorkflowCanvasStep[];
  dagStages: WorkflowCanvasStep[][];
  mcpServers: string[];
  repositories: string[];
  skills: string[];
  channels: ParsedWorkflowChannel[];
}

export interface DepartmentWorkflowGroup {
  department: Department;
  isUnassigned?: boolean;
  workflows: EnrichedWorkflowNode[];
  activeCount: number;
  totalSteps: number;
}

export interface OrgWorkflowsTopology {
  groups: DepartmentWorkflowGroup[];
  totalDepartments: number;
  totalWorkflows: number;
  activeWorkflows: number;
  totalSteps: number;
  uniqueChannelsAndMcps: number;
}

export const UNASSIGNED_DEPT_ID = '__unassigned__';

function computeDagStages(steps: WorkflowCanvasStep[]): WorkflowCanvasStep[][] {
  if (steps.length === 0) return [];
  const depths: Record<string, number> = {};

  const getDepth = (key: string, visited = new Set<string>()): number => {
    if (visited.has(key)) return 0;
    visited.add(key);
    const step = steps.find((s) => s.key === key);
    if (!step || !step.depends_on || step.depends_on.length === 0) return 0;
    let maxParent = 0;
    for (const parentKey of step.depends_on) {
      maxParent = Math.max(maxParent, getDepth(parentKey, new Set(visited)) + 1);
    }
    return maxParent;
  };

  steps.forEach((s) => {
    depths[s.key] = getDepth(s.key);
  });

  const maxDepth = Math.max(0, ...Object.values(depths));
  const stages: WorkflowCanvasStep[][] = [];
  for (let i = 0; i <= maxDepth; i++) {
    stages.push(steps.filter((s) => (depths[s.key] ?? 0) === i));
  }
  return stages;
}

export function parseWorkflowNode(wf: PlatformWorkflow): EnrichedWorkflowNode {
  let def: Record<string, any> = {};
  try {
    def = wf.definition_json ? JSON.parse(wf.definition_json) : {};
  } catch {
    def = {};
  }

  const rawSteps: any[] = Array.isArray(def.steps) ? def.steps : [];
  const steps: WorkflowCanvasStep[] = rawSteps.map((s: any, idx: number) => ({
    key: String(s.key || s.id || `step_${idx + 1}`),
    name: String(s.name || s.key || s.id || `Step ${idx + 1}`),
    agent_id: String(s.agent_id || s.agentId || def.runner_agent_id || `wf-agent-${wf.id}`),
    prompt_template: String(s.prompt_template || s.prompt || ''),
    depends_on: Array.isArray(s.depends_on || s.dependsOn) ? (s.depends_on || s.dependsOn).map(String) : [],
    timeout_seconds: Number(s.timeout_seconds || 300),
    skills: Array.isArray(s.skills)
      ? s.skills.map((sk: any) => (typeof sk === 'object' ? String(sk.name || sk.id) : String(sk)))
      : [],
    mcp_servers: Array.isArray(s.mcp_servers || s.mcpServers)
      ? (s.mcp_servers || s.mcpServers).map(String)
      : [],
  }));

  // Extract MCP servers (root + per-step)
  const mcpSet = new Set<string>();
  if (Array.isArray(def.mcp_servers)) {
    def.mcp_servers.forEach((m: any) => mcpSet.add(String(m)));
  }
  steps.forEach((st) => {
    (st.mcp_servers || []).forEach((m) => mcpSet.add(m));
  });

  // Extract repositories (root metadata/workspace + per-step params/workspace)
  const repoSet = new Set<string>();
  const meta = def.metadata || {};
  if (typeof meta.target_repo === 'string' && meta.target_repo.trim()) {
    repoSet.add(meta.target_repo.trim());
  }
  if (typeof def.target_repo === 'string' && def.target_repo.trim()) {
    repoSet.add(def.target_repo.trim());
  }
  if (def.workspace && typeof def.workspace.repository === 'string' && def.workspace.repository.trim()) {
    repoSet.add(def.workspace.repository.trim());
  }
  rawSteps.forEach((s: any) => {
    const stepRepo =
      s?.workspace?.repository ||
      s?.params?.repository ||
      s?.params?.repo ||
      s?.repository;
    if (typeof stepRepo === 'string' && stepRepo.trim()) {
      repoSet.add(stepRepo.trim());
    }
    if (Array.isArray(s?.allowed_repos)) {
      s.allowed_repos.forEach((r: any) => {
        if (typeof r === 'string' && r.trim()) repoSet.add(r.trim());
      });
    }
  });

  // Extract shared skills (root + per-step)
  const skillSet = new Set<string>();
  if (Array.isArray(def.skills)) {
    def.skills.forEach((sk: any) => {
      const label = typeof sk === 'object' ? String(sk.name || sk.id || '') : String(sk || '');
      if (label.trim()) skillSet.add(label.trim());
    });
  }
  steps.forEach((st) => {
    (st.skills || []).forEach((sk) => {
      if (sk.trim()) skillSet.add(sk.trim());
    });
  });

  // Extract channels (binding + explicit step channel_action)
  const channels: ParsedWorkflowChannel[] = [];
  const cb = wf.channel_binding || meta.channel_binding;
  if (cb && cb.channel_id) {
    channels.push({
      provider: String(cb.provider || 'telegram').toLowerCase(),
      channelId: String(cb.channel_id),
      channelName: cb.channel_name ? String(cb.channel_name) : undefined,
      source: 'binding',
    });
  }
  rawSteps.forEach((s: any) => {
    const ca = s?.params?.channel_action || s?.channel_action;
    if (ca && ca.channel_id) {
      const provider = String(ca.connector_id || ca.provider || 'channel').toLowerCase();
      const channelId = String(ca.channel_id);
      const exists = channels.some((c) => c.provider === provider && c.channelId === channelId);
      if (!exists) {
        channels.push({
          provider,
          channelId,
          source: 'step_action',
          stepKey: String(s.key || s.id || ''),
        });
      }
    }
  });

  // Extract triggers
  const triggers: ParsedWorkflowTrigger[] = [];
  const cronExpr =
    wf.cron_expression ||
    def?.trigger?.cron_expression ||
    def?.trigger?.cron;
  if (typeof cronExpr === 'string' && cronExpr.trim() && cronExpr.trim().toLowerCase() !== 'none') {
    triggers.push({ type: 'cron', label: cronExpr.trim() });
  }
  if (wf.webhook_enabled || def?.trigger?.webhook_enabled) {
    triggers.push({ type: 'webhook', label: 'Webhook' });
  }
  if (cb && cb.channel_id && cb.trigger_enabled) {
    triggers.push({
      type: 'channel',
      provider: String(cb.provider || 'channel').toUpperCase(),
      label: `${String(cb.provider || 'CH').toUpperCase()} #${cb.channel_name || cb.channel_id}`,
    });
  }
  if (triggers.length === 0) {
    triggers.push({ type: 'manual', label: 'Manual / API' });
  }

  return {
    workflow: wf,
    departmentId: wf.department_id || UNASSIGNED_DEPT_ID,
    runnerAgentId: String(def.runner_agent_id || `wf-agent-${wf.id}`),
    triggers,
    steps,
    dagStages: computeDagStages(steps),
    mcpServers: Array.from(mcpSet),
    repositories: Array.from(repoSet),
    skills: Array.from(skillSet),
    channels,
  };
}

export function buildOrgWorkflowsTopology(
  departments: Department[],
  workflows: PlatformWorkflow[],
  unassignedLabel: string,
  unassignedDesc: string,
  organizationId?: string
): OrgWorkflowsTopology {
  const parsedNodes = workflows.map(parseWorkflowNode);
  const deptMap = new Map<string, Department>();
  departments.forEach((d) => deptMap.set(d.id, d));

  const groups: DepartmentWorkflowGroup[] = departments.map((dept) => {
    const deptWfs = parsedNodes.filter((n) => n.departmentId === dept.id);
    return {
      department: dept,
      workflows: deptWfs,
      activeCount: deptWfs.filter((n) => n.workflow.is_active).length,
      totalSteps: deptWfs.reduce((sum, n) => sum + n.steps.length, 0),
    };
  });

  // Bucket any workflows without a department_id or whose department_id is not in departments list
  const unassignedWfs = parsedNodes.filter(
    (n) => !n.workflow.department_id || !deptMap.has(n.workflow.department_id)
  );
  if (unassignedWfs.length > 0 || departments.length === 0) {
    groups.push({
      department: {
        id: UNASSIGNED_DEPT_ID,
        organization_id: organizationId || '',
        name: unassignedLabel,
        description: unassignedDesc,
        monthly_budget_usd: 0,
        current_spend_usd: 0,
        budget_action: 'HARD_STOP',
        alert_threshold_pct: 80,
      },
      isUnassigned: true,
      workflows: unassignedWfs,
      activeCount: unassignedWfs.filter((n) => n.workflow.is_active).length,
      totalSteps: unassignedWfs.reduce((sum, n) => sum + n.steps.length, 0),
    });
  }

  const externalEndpoints = new Set<string>();
  parsedNodes.forEach((n) => {
    n.mcpServers.forEach((m) => externalEndpoints.add(`mcp:${m}`));
    n.repositories.forEach((r) => externalEndpoints.add(`repo:${r}`));
    n.channels.forEach((c) => externalEndpoints.add(`ch:${c.provider}:${c.channelId}`));
  });

  return {
    groups,
    totalDepartments: departments.length,
    totalWorkflows: parsedNodes.length,
    activeWorkflows: parsedNodes.filter((n) => n.workflow.is_active).length,
    totalSteps: parsedNodes.reduce((sum, n) => sum + n.steps.length, 0),
    uniqueChannelsAndMcps: externalEndpoints.size,
  };
}
