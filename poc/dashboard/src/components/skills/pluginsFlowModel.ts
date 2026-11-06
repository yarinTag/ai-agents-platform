import type { PluginPackage, PluginSkill } from '../../types/skill';

export interface EnrichedPluginSkillFlow {
  skill: PluginSkill;
  stageIndex: number;
  stageLabel: string;
  connectedToIds: string[];
  connectedFromIds: string[];
}

/**
 * Classifies a skill into a logical pipeline stage (0..5) based on its role, domain, and ID.
 */
export function classifySkillStage(skill: PluginSkill, pluginName: string): { index: number; label: string } {
  const id = (skill.id || '').toLowerCase();
  const domain = (skill.domain || '').toLowerCase();
  const role = (skill.role || '').toLowerCase();

  // Stage 1: Routers & Entry Points
  if (
    role === 'router' ||
    domain.includes('routing') ||
    id.endsWith('-router') ||
    id.endsWith('-start') ||
    id.includes('context-router')
  ) {
    return { index: 0, label: '1. Entry & Routing' };
  }

  // Stage 2: Discovery, Ideation & Research
  if (
    domain.includes('discovery') ||
    domain.includes('research') ||
    id.includes('blueprint') ||
    id.includes('research') ||
    id.includes('competitor') ||
    id.includes('scout') ||
    id.includes('spike') ||
    id.includes('voice-analyst')
  ) {
    return { index: 1, label: '2. Discovery & Research' };
  }

  // Stage 3: Specification, PRD, Design & Publishing
  if (
    domain.includes('prd') ||
    domain.includes('design') ||
    domain.includes('publishing') ||
    domain === 'product.review' ||
    id.includes('prd-writer') ||
    id.includes('figma') ||
    id.includes('prd-auto-review') ||
    id.includes('devils-advocate') ||
    id.includes('publisher') ||
    id.includes('ui-ux')
  ) {
    return { index: 2, label: '3. Spec, PRD & Design' };
  }

  // Stage 4: Architecture, Engineering Review & Domain Core
  if (
    domain.includes('architecture') ||
    domain.includes('legal') ||
    domain.includes('devops') ||
    id.includes('architecture') ||
    id.includes('eng-review') ||
    id.includes('adr-') ||
    id.includes('drift-detector') ||
    id.includes('cost-estimator') ||
    id.includes('compliance')
  ) {
    return { index: 3, label: '4. Architecture & Eng' };
  }

  // Stage 5: Implementation, Prioritization & Domain Execution
  if (
    domain.includes('prioritization') ||
    domain.includes('implementation') ||
    id.includes('prioritizer') ||
    id.includes('implementation-planner')
  ) {
    return { index: 4, label: '5. Planning & Build' };
  }

  // Stage 6: Verification, QA, Security & Governance Gates
  if (
    domain.includes('coverage') ||
    domain.includes('governance') ||
    domain.includes('qa') ||
    domain.includes('debugging') ||
    domain.includes('incident') ||
    domain === 'meta.review' ||
    id.includes('-gate') ||
    id.includes('reviewer') ||
    id.includes('guardrail') ||
    id.includes('debugger') ||
    id.includes('postmortem') ||
    id.includes('testing') ||
    id.includes('security')
  ) {
    return { index: 5, label: '6. QA & Governance Gates' };
  }

  // Fallback for domain-specific plugins (e.g. tech-frontend, tech-backend, tech-ai-ml, shared)
  if (pluginName !== 'core') {
    if (id.includes('architect') || id.includes('design') || id.includes('schema') || id.includes('prompt')) {
      return { index: 1, label: '1. Architecture & Design' };
    }
    if (id.includes('test') || id.includes('eval') || id.includes('audit') || id.includes('security') || id.includes('observability')) {
      return { index: 3, label: '3. Verification & Ops' };
    }
    return { index: 2, label: '2. Implementation Skills' };
  }

  return { index: 3, label: '4. Core Skills' };
}

/**
 * Projects discovered directed skill references and presentation stages for a plugin package.
 */
export function buildPluginSkillFlow(
  plugin: PluginPackage,
  allPlugins: PluginPackage[]
): EnrichedPluginSkillFlow[] {
  const pkgSkills = Array.isArray(plugin?.skills) ? plugin.skills : [];
  if (pkgSkills.length === 0) return [];

  const allSkills = allPlugins.flatMap((pkg) => pkg.skills || []);
  const allSkillIds = new Set(allSkills.map((skill) => skill.id));

  const toMap = new Map<string, Set<string>>();
  const fromMap = new Map<string, Set<string>>();
  pkgSkills.forEach((s) => {
    toMap.set(s.id, new Set<string>());
    fromMap.set(s.id, new Set<string>());
  });

  const addEdge = (sourceId: string, targetId: string) => {
    if (!sourceId || !targetId || sourceId === targetId) return;
    if (!allSkillIds.has(targetId)) return;
    if (!toMap.has(sourceId)) toMap.set(sourceId, new Set());
    toMap.get(sourceId)!.add(targetId);
    if (!fromMap.has(targetId)) fromMap.set(targetId, new Set());
    fromMap.get(targetId)!.add(sourceId);
  };

  // Scan every package so incoming links include cross-plugin references.
  // Only evidence-backed handoffs/transitions count as flow. Legacy mentions stay references.
  allSkills.forEach((skill) => {
    (skill.skill_connections || []).forEach((connection) => {
      if (connection.source === skill.id && connection.kind !== 'reference') addEdge(skill.id, connection.target);
    });
  });

  return pkgSkills
    .map((sk) => {
      const stage = classifySkillStage(sk, plugin.name);
      return {
        skill: sk,
        stageIndex: stage.index,
        stageLabel: stage.label,
        connectedToIds: Array.from(toMap.get(sk.id) || []).sort(),
        connectedFromIds: Array.from(fromMap.get(sk.id) || []).sort(),
      };
    })
    .sort((a, b) => a.stageIndex - b.stageIndex || a.skill.name.localeCompare(b.skill.name));
}
