import type { PixelSceneState } from './pixelSceneState';
import type { Agent } from '../types/agent';
import type { Task } from '../types/task';
import { VisualConnection } from './pixelSceneLayout';
import { assignCharColors, assignDeskPositions } from './pixelDeskLayout';
import { gs } from './pixelCoordinates';
import { detectTaskCompletions } from './pixelAgentActivity';

export function updateData(scene: PixelSceneState, agents: Agent[], tasks: Task[], connections?: VisualConnection[]): void {
  // Strictly isolate office desks: Workflow automation agents are background runners detached from office floor
  scene.agents = (agents || []).filter(
    (a) =>
      a.role_type !== 'WORKFLOW_AUTOMATION' &&
      !a.is_workflow_agent &&
      a.department !== 'Workflow Automations'
  );
  scene.tasks = tasks;
  if (connections) {
    scene.connections = connections;
  } else {
    deriveActiveConnections(scene);
  }
  assignDeskPositions(scene);
  detectTaskCompletions(scene);
  assignCharColors(scene);
}

export function setConnections(scene: PixelSceneState, conns: VisualConnection[]): void {
  scene.connections = conns;
}

export function deriveActiveConnections(scene: PixelSceneState): void {
  const list: VisualConnection[] = [];
  scene.tasks.forEach((t) => {
    const st = String(t.status).toLowerCase();
    const aid = String(t.agent_id);
    if (st === 'waiting_input') {
      list.push({
        id: `conn-super-${t.id}`,
        fromAgentId: aid,
        targetType: 'super_agent',
        color: '#38bdf8',
        label: 'Super Agent Query',
      });
    }
  });

  scene.agents.forEach((a) => {
    const ast = (a.status || '').toUpperCase();
    if (ast === 'COMMUNICATING' && a.parent_id) {
      list.push({
        id: `conn-comm-${a.id}`,
        fromAgentId: a.id,
        toAgentId: a.parent_id,
        targetType: 'agent',
        color: '#a855f7',
        label: 'Peer Message',
      });
    }
  });
  scene.connections = list;
}

export function setOnSelectAgent(scene: PixelSceneState, cb: (a: Agent) => void): void { scene.onSelectAgentCallback = cb; }

export function setSelectedAgent(scene: PixelSceneState, id: string | null): void { scene.selectedAgentId = id; }

export function resize(scene: PixelSceneState, w: number, h: number): void { scene.canvas.width = w; scene.canvas.height = h; }

export function start(scene: PixelSceneState, renderFrame: () => void): void {
  if (scene.animFrameId !== null) return;
  const loop = () => { scene.tick++; renderFrame(); scene.animFrameId = requestAnimationFrame(loop); };
  scene.animFrameId = requestAnimationFrame(loop);
}

export function stop(scene: PixelSceneState): void {
  if (scene.animFrameId !== null) { cancelAnimationFrame(scene.animFrameId); scene.animFrameId = null; }
}

// ─── Coordinate helpers ──────────────────────────────────────────────────



export function handleCanvasClick(scene: PixelSceneState, sx: number, sy: number): void {
  const a = findAgentAt(scene, sx, sy);
  if (a) { scene.selectedAgentId = a.id; scene.onSelectAgentCallback?.(a); }
}

export function handleCanvasMouseMove(scene: PixelSceneState, sx: number, sy: number): void {
  const h = findAgentAt(scene, sx, sy);
  scene.hoveredAgentId = h ? h.id : null;
}

export function findAgentAt(scene: PixelSceneState, sx: number, sy: number): Agent | null {
  const T = scene.T * scene.zoom;
  for (const a of scene.agents) {
    const pos = scene.deskMap.get(a.id);
    if (!pos) continue;
    const pt = gs(scene, pos.tx, pos.ty);
    const cw = T * 0.9;
    if (
      sx >= pt.x + T / 2 - cw / 2 &&
      sx <= pt.x + T / 2 + cw / 2 &&
      sy >= pt.y - T * 1.3 &&
      sy <= pt.y + T * 1.1
    ) {
      return a;
    }
  }
  return null;
}

// ─── Task completion → walk animation ──────────────────────────────────




