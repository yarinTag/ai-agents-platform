import { PluginPackage, PluginSkill } from '../../types/skill';

export interface EnrichedPluginSkillFlow {
  skill: PluginSkill;
  stageIndex: number;
  stageLabel: string;
  connectedToIds: string[];
  connectedFromIds: string[];
}

/**
 * Canonical lifecycle edges defined in the `core` plugin (e.g. `product-prd-start` & `meta-repo-context-router`).
 * Used alongside dynamic `connected_skills` and text-extracted references so the skill flow graph is always complete.
 */
const CANONICAL_SKILL_FLOW_EDGES: Record<string, string[]> = {
  'meta-repo-context-router': [
    'product-prd-start',
    'meta-systematic-debugger',
    'meta-adversarial-code-reviewer',
    'meta-skill-qa-gate',
  ],
  'product-prd-start': [
    'product-idea-to-blueprint',
    'product-deep-researcher',
    'product-competitor-benchmark-analyst',
    'product-user-voice-analyst',
    'product-opensource-scout',
    'product-tech-spike-evaluator',
    'product-prd-writer',
  ],
  'product-idea-to-blueprint': [
    'product-deep-researcher',
    'product-competitor-benchmark-analyst',
    'product-user-voice-analyst',
    'product-prd-writer',
  ],
  'product-deep-researcher': ['product-prd-writer', 'product-tech-spike-evaluator'],
  'product-competitor-benchmark-analyst': ['product-prd-writer', 'product-feature-prioritizer'],
  'product-user-voice-analyst': ['product-prd-writer', 'product-feature-prioritizer'],
  'product-opensource-scout': ['product-tech-spike-evaluator', 'product-architecture-designer'],
  'product-tech-spike-evaluator': ['product-prd-writer', 'product-architecture-designer'],
  'product-prd-writer': [
    'product-figma-alignment',
    'product-prd-auto-review',
    'product-devils-advocate',
    'product-google-docs-prd-publisher',
    'product-eng-review',
    'product-architecture-designer',
  ],
  'product-figma-alignment': ['product-prd-auto-review', 'product-eng-review'],
  'product-prd-auto-review': ['product-devils-advocate', 'product-google-docs-prd-publisher', 'product-eng-review'],
  'product-devils-advocate': ['product-eng-review', 'product-architecture-designer'],
  'product-google-docs-prd-publisher': ['product-eng-review', 'product-feature-prioritizer'],
  'product-eng-review': [
    'product-architecture-designer',
    'product-adr-decision-maker',
    'product-spec-drift-detector',
    'product-implementation-planner',
  ],
  'product-architecture-designer': [
    'product-adr-decision-maker',
    'tech-infra-cost-estimator',
    'business-regulatory-compliance',
    'product-implementation-planner',
  ],
  'product-adr-decision-maker': ['product-implementation-planner', 'product-spec-drift-detector'],
  'product-spec-drift-detector': ['product-implementation-planner', 'product-coverage-gate'],
  'tech-infra-cost-estimator': ['product-implementation-planner', 'meta-budget-guardrail'],
  'business-regulatory-compliance': ['product-implementation-planner', 'product-signoff-gate'],
  'product-feature-prioritizer': ['product-implementation-planner'],
  'product-implementation-planner': [
    'product-coverage-gate',
    'product-signoff-gate',
    'meta-adversarial-code-reviewer',
  ],
  'product-coverage-gate': ['product-signoff-gate', 'meta-adversarial-code-reviewer'],
  'meta-adversarial-code-reviewer': ['product-signoff-gate', 'meta-skill-qa-gate'],
};

function stripCategoryPrefix(skillId: string): string {
  for (const prefix of ['product-', 'meta-', 'tech-', 'business-', 'shared-']) {
    if (skillId.startsWith(prefix) && skillId.length > prefix.length + 3) {
      return skillId.slice(prefix.length);
    }
  }
  return skillId;
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
 * Computes the complete directed skill-to-skill connection graph and pipeline stages for a plugin package.
 */
export function buildPluginSkillFlow(
  plugin: PluginPackage,
  allPlugins: PluginPackage[]
): EnrichedPluginSkillFlow[] {
  const pkgSkills = Array.isArray(plugin?.skills) ? plugin.skills : [];
  if (pkgSkills.length === 0) return [];

  // Build lookup of all known skill IDs and short aliases across the ecosystem
  const allSkillIds = new Set<string>();
  const aliasToFullId = new Map<string, string>();

  allPlugins.forEach((p) => {
    (p?.skills || []).forEach((s) => {
      if (!s?.id) return;
      allSkillIds.add(s.id);
      aliasToFullId.set(s.id.toLowerCase(), s.id);
      const shortAlias = stripCategoryPrefix(s.id.toLowerCase());
      if (shortAlias.length >= 6 && !aliasToFullId.has(shortAlias)) {
        aliasToFullId.set(shortAlias, s.id);
      }
    });
  });

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

  pkgSkills.forEach((sk) => {
    // 1. Backend-extracted connected_skills
    (sk.connected_skills || []).forEach((targetId) => addEdge(sk.id, targetId));

    // 2. Canonical lifecycle edges for core/router skills
    (CANONICAL_SKILL_FLOW_EDGES[sk.id] || []).forEach((targetId) => addEdge(sk.id, targetId));

    // 3. Frontend text scan across description + content_preview
    const hay = `${sk.description || ''} ${sk.content_preview || ''}`.toLowerCase();
    if (hay.trim()) {
      aliasToFullId.forEach((fullTargetId, alias) => {
        if (fullTargetId !== sk.id && hay.includes(alias)) {
          addEdge(sk.id, fullTargetId);
        }
      });
    }
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
