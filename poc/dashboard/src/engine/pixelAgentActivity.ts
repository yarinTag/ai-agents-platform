import type { PixelSceneState } from './pixelSceneState';
import type { Agent } from '../types/agent';

export function detectTaskCompletions(scene: PixelSceneState): void {
  scene.tasks.forEach((task) => {
    const prev = scene.prevTaskStatuses.get(String(task.id));
    const curr = task.status;
    if ((prev === 'running' || prev === 'queued') &&
        ['done', 'completed', 'success', 'finished'].includes(curr)) {
      const agentId = String(task.agent_id);
      const agent = scene.agents.find((a) => String(a.id) === agentId);
      if (agent && agent.parent_id && !scene.walkAnims.has(agentId)) {
        const aPos = scene.deskMap.get(agentId);
        const mPos = scene.deskMap.get(String(agent.parent_id));
        if (aPos && mPos) {
          scene.walkAnims.set(agentId, {
            agentId, managerId: String(agent.parent_id),
            fromX: aPos.tx, fromY: aPos.ty, toX: mPos.tx, toY: mPos.ty,
            progress: 0, phase: 'walking', deliverTick: 0,
          });
        }
      }
    }
    scene.prevTaskStatuses.set(String(task.id), curr);
  });
}

export function tickWalkAnims(scene: PixelSceneState): void {
  const del: string[] = [];
  scene.walkAnims.forEach((a) => {
    if (a.phase === 'walking') {
      a.progress += 0.01;
      if (a.progress >= 1) { a.progress = 1; a.phase = 'delivering'; a.deliverTick = scene.tick; }
    } else if (a.phase === 'delivering') {
      if (scene.tick - a.deliverTick > 100) { a.phase = 'returning'; a.progress = 1; }
    } else {
      a.progress -= 0.015;
      if (a.progress <= 0) del.push(a.agentId);
    }
  });
  del.forEach((id) => scene.walkAnims.delete(id));
}

export function isAgentWorking(scene: PixelSceneState, agent: Agent): boolean {
  const hasActiveTask = scene.tasks.some(
    (t) => String(t.agent_id) === String(agent.id) &&
      (t.status === 'running' || t.status === 'queued' || t.status === 'in_progress')
  );
  if (hasActiveTask) return true;

  const st = (agent.status || '').toLowerCase();
  if (st === 'running' || st === 'thinking' || st === 'reviewing' || st === 'active') {
    return true;
  }

  if (agent.current_task && agent.current_task.trim() !== '') {
    return true;
  }

  return false;
}

export function isManagerOrLead(scene: PixelSceneState, agent: Agent): boolean {
  const r = (agent.role_type || '').toUpperCase();
  if (r === 'ROOT_ORCHESTRATOR' || r === 'MANAGER' || r === 'LEAD') return true;
  const id = agent.id.toLowerCase();
  if (id.includes('chief') || id.includes('lead') || id.includes('manager') || id.includes('orchestrator')) return true;
  const name = (agent.name || '').toLowerCase();
  if (name.includes('lead') || name.includes('manager') || name.includes('chief')) return true;
  return false;
}
