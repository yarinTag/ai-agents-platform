import type { AttachedSkill } from './workflowBuilderTypes';

/** Promote legacy step assignments into the single workflow-wide selection. */
export function collectWorkflowSkills(definition: {
  skills?: Array<AttachedSkill | string>;
  steps?: Array<{ skills?: string[] }>;
}): AttachedSkill[] {
  const values = [...(definition.skills || []), ...(definition.steps || []).flatMap(step => step.skills || [])];
  const selected = new Map<string, AttachedSkill>();
  for (const value of values) {
    const skill = typeof value === 'string' ? { id: value, name: value, source: 'builtin' as const } : value;
    if (!selected.has(skill.id)) selected.set(skill.id, skill);
  }
  return [...selected.values()];
}
