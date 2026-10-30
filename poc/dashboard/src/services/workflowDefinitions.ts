/** Preserve unknown workflow fields while removing a stage and its graph edges. */
export const removeWorkflowStep = (definitionJson: string, stepKey: string) => {
  const definition = JSON.parse(definitionJson);
  const steps: any[] = definition.steps || [];
  if (!Array.isArray(steps)) throw new Error('Workflow steps must be an array');
  const deleted = steps.find(step => (step.key || step.id) === stepKey);
  const parents: string[] = deleted?.depends_on || [];
  const updatedSteps = steps
    .filter(step => (step.key || step.id) !== stepKey)
    .map(step => {
      const dependencies: string[] = step.depends_on || [];
      if (!dependencies.includes(stepKey)) return step;
      return { ...step, depends_on: Array.from(new Set([
        ...dependencies.filter(key => key !== stepKey),
        ...parents.filter(key => key !== (step.key || step.id)),
      ])) };
    });
  const remainingKeys = new Set(updatedSteps.map(step => step.key || step.id));
  const updated = {
    ...definition,
    steps: updatedSteps,
    ...(definition.flow ? { flow: definition.flow.filter((edge: { from: string; to: string }) =>
      remainingKeys.has(edge.to) && (!edge.from || remainingKeys.has(edge.from))) } : {}),
  };
  return {
    definitionJson: JSON.stringify(updated, null, 2),
    deletedName: deleted?.name || stepKey,
  };
};
