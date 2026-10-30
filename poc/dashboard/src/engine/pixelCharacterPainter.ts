import type { PixelSceneState } from './pixelSceneState';
import type { Agent } from '../types/agent';
import { gs } from './pixelCoordinates';

export function drawCharacter(scene: PixelSceneState, 
  agent: Agent, tx: number, ty: number,
  state: 'seated' | 'walking',
  delivering = false
): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;

  const colors = scene.charColors.get(agent.id) || { shirt: '#3b82f6', hair: '#2c1a0e', skin: '#f5cba7' };
  const isSelected = scene.selectedAgentId === agent.id;
  const isHovered  = scene.hoveredAgentId === agent.id;
  const role = (agent.role_type || 'WORKER').toUpperCase();
  const isManager = role === 'ROOT_ORCHESTRATOR' || role === 'MANAGER';

  // Position: centered on tile, bottom of sprite at y+T
  const cx = x + T / 2;
  const cy = y + T * 0.85;

  // Walking leg bob
  const leg = state === 'walking' ? Math.floor(scene.tick / 7) % 2 : 0;

  ctx.save();

  // Selection ring
  if (isSelected || isHovered) {
    ctx.strokeStyle = isSelected ? '#3b82f6' : '#f59e0b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(cx, cy + 2 * z, 8 * z, 3 * z, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Shadow ellipse
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  ctx.beginPath();
  ctx.ellipse(cx, cy + 1 * z, 6 * z, 2.5 * z, 0, 0, Math.PI * 2);
  ctx.fill();

  // LEGS
  ctx.fillStyle = '#2c3e6e';
  if (state === 'walking') {
    ctx.fillRect(cx - 5 * z, cy - 6 * z + (leg ? 2 * z : 0), 4 * z, 6 * z - (leg ? 2 * z : 0));
    ctx.fillRect(cx + 1 * z, cy - 6 * z + (leg ? 0 : 2 * z), 4 * z, 6 * z - (leg ? 0 : 2 * z));
  } else {
    ctx.fillRect(cx - 5 * z, cy - 5 * z, 4 * z, 5 * z);
    ctx.fillRect(cx + 1 * z, cy - 5 * z, 4 * z, 5 * z);
  }
  // Shoes
  ctx.fillStyle = '#1a1a2a';
  ctx.fillRect(cx - 5.5 * z, cy - 1 * z, 4.5 * z, 2 * z);
  ctx.fillRect(cx + 1 * z, cy - 1 * z, 4.5 * z, 2 * z);

  // BODY (shirt)
  ctx.fillStyle = colors.shirt;
  ctx.fillRect(cx - 6 * z, cy - 16 * z, 12 * z, 10 * z);
  // Shirt detail (collar)
  ctx.fillStyle = 'rgba(255,255,255,0.25)';
  ctx.fillRect(cx - 2 * z, cy - 16 * z, 4 * z, 3 * z);

  // ARMS
  ctx.fillStyle = colors.shirt;
  if (state === 'walking') {
    ctx.fillRect(cx - 9 * z, cy - 15 * z + (leg ? 2 * z : -2 * z), 3 * z, 6 * z);
    ctx.fillRect(cx + 6 * z, cy - 15 * z + (leg ? -2 * z : 2 * z), 3 * z, 6 * z);
  } else {
    ctx.fillRect(cx - 9 * z, cy - 15 * z, 3 * z, 6 * z);
    ctx.fillRect(cx + 6 * z, cy - 15 * z, 3 * z, 6 * z);
  }

  // Delivery paper
  if (delivering) {
    ctx.fillStyle = '#fef9e7';
    ctx.fillRect(cx + 6 * z, cy - 18 * z, 10 * z, 8 * z);
    ctx.strokeStyle = '#c8a050'; ctx.lineWidth = 0.8;
    ctx.strokeRect(cx + 6 * z, cy - 18 * z, 10 * z, 8 * z);
    ctx.fillStyle = '#aaa'; ctx.lineWidth = 0.5;
    ctx.fillRect(cx + 7 * z, cy - 16 * z, 7 * z, 1 * z);
    ctx.fillRect(cx + 7 * z, cy - 14 * z, 5 * z, 1 * z);
  }

  // HEAD
  ctx.fillStyle = colors.skin;
  ctx.fillRect(cx - 5 * z, cy - 24 * z, 10 * z, 8 * z);
  // Outline
  ctx.strokeStyle = 'rgba(0,0,0,0.3)';
  ctx.lineWidth = 0.8;
  ctx.strokeRect(cx - 5 * z, cy - 24 * z, 10 * z, 8 * z);

  // Eyes (2 tiny squares)
  ctx.fillStyle = '#1a1a2a';
  ctx.fillRect(cx - 3 * z, cy - 21 * z, 1.5 * z, 1.5 * z);
  ctx.fillRect(cx + 1.5 * z, cy - 21 * z, 1.5 * z, 1.5 * z);
  // Mouth
  ctx.fillStyle = 'rgba(0,0,0,0.4)';
  ctx.fillRect(cx - 1 * z, cy - 18 * z, 2 * z, 1 * z);

  // HAIR
  ctx.fillStyle = colors.hair;
  ctx.fillRect(cx - 5 * z, cy - 24 * z, 10 * z, 3 * z); // top
  ctx.fillRect(cx - 5 * z, cy - 24 * z, 2 * z, 7 * z);  // left side
  ctx.fillRect(cx + 3 * z, cy - 24 * z, 2 * z, 7 * z);  // right side

  // Crown/Star for manager/root
  if (isManager) {
    ctx.fillStyle = '#fbbf24';
    ctx.font = `${Math.max(8, 8 * z)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText('★', cx, cy - 26 * z);
    ctx.textAlign = 'left';
  }

  // Name tag
  const label = agent.name.split(' ')[0].slice(0, 8);
  ctx.save();
  ctx.font = `${Math.max(8, 8 * z)}px sans-serif`;
  const lw = ctx.measureText(label).width;
  const tagX = cx - lw / 2 - 3, tagY = cy - 30 * z - 12 * z;
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.fillRect(tagX, tagY, lw + 6, 12 * z);
  ctx.strokeStyle = colors.shirt; ctx.lineWidth = 1;
  ctx.strokeRect(tagX, tagY, lw + 6, 12 * z);
  ctx.fillStyle = '#1a1a2a';
  ctx.fillText(label, tagX + 3, tagY + 9 * z);
  ctx.restore();

  // Agent visual runtime state badge (IDLE, THINKING, WORKING, WAITING, BLOCKED, COMMUNICATING, USING_MCP, COMPLETED, FAILED)
  drawAgentStatusBubble(scene, agent, cx, cy, z);


  ctx.restore();
}

// ─── Seated character — positioned so the desk covers their lower body ───
// For dir='down': agent faces north, desk is at back, chair at south edge of desk tile.
// For dir='up':  agent faces south, desk at back, chair at north edge of desk tile.

export function drawCharacterSeated(scene: PixelSceneState, agent: Agent, tx: number, ty: number, dir: string): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;

  const colors = scene.charColors.get(agent.id) || { shirt: '#3b82f6', hair: '#2c1a0e', skin: '#f5cba7' };
  const isSelected = scene.selectedAgentId === agent.id;
  const isHovered  = scene.hoveredAgentId === agent.id;
  const role = (agent.role_type || 'WORKER').toUpperCase();
  const isManager = role === 'ROOT_ORCHESTRATOR' || role === 'MANAGER';

  // For 'down': character sits at ~75% of tile height (the desk will cover legs)
  // For 'up':  character sits at ~25% of tile (desk below them covers legs)
  const cx = x + T * 0.5;
  const cy = dir === 'up' ? y + T * 0.3 : y + T * 0.75;

  ctx.save();

  // Selection ring
  if (isSelected || isHovered) {
    ctx.strokeStyle = isSelected ? '#3b82f6' : '#f59e0b';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.ellipse(cx, cy + 2 * z, 8 * z, 2.5 * z, 0, 0, Math.PI * 2);
    ctx.stroke();
  }

  // LEGS (will be hidden by desk drawn on top)
  ctx.fillStyle = '#2c3e6e';
  ctx.fillRect(cx - 4 * z, cy - 4 * z, 3.5 * z, 5 * z);
  ctx.fillRect(cx + 0.5 * z, cy - 4 * z, 3.5 * z, 5 * z);
  // Shoes
  ctx.fillStyle = '#1a1a2a';
  ctx.fillRect(cx - 5 * z, cy, 4 * z, 2 * z);
  ctx.fillRect(cx + 1 * z, cy, 4 * z, 2 * z);

  // BODY (shirt)
  ctx.fillStyle = colors.shirt;
  ctx.fillRect(cx - 5.5 * z, cy - 13 * z, 11 * z, 9 * z);
  // Collar
  ctx.fillStyle = 'rgba(255,255,255,0.28)';
  ctx.fillRect(cx - 2 * z, cy - 13 * z, 4 * z, 3 * z);

  // ARMS (resting on desk)
  ctx.fillStyle = colors.shirt;
  ctx.fillRect(cx - 8.5 * z, cy - 12 * z, 3 * z, 5 * z);
  ctx.fillRect(cx + 5.5 * z, cy - 12 * z, 3 * z, 5 * z);

  // HEAD
  ctx.fillStyle = colors.skin;
  ctx.fillRect(cx - 5 * z, cy - 22 * z, 10 * z, 9 * z);
  ctx.strokeStyle = 'rgba(0,0,0,0.25)';
  ctx.lineWidth = 0.8;
  ctx.strokeRect(cx - 5 * z, cy - 22 * z, 10 * z, 9 * z);

  // Eyes
  ctx.fillStyle = '#1a1a2a';
  ctx.fillRect(cx - 3 * z, cy - 19 * z, 1.5 * z, 1.5 * z);
  ctx.fillRect(cx + 1.5 * z, cy - 19 * z, 1.5 * z, 1.5 * z);
  // Mouth
  ctx.fillStyle = 'rgba(0,0,0,0.35)';
  ctx.fillRect(cx - 1 * z, cy - 16 * z, 2 * z, 1 * z);

  // HAIR
  ctx.fillStyle = colors.hair;
  ctx.fillRect(cx - 5 * z, cy - 22 * z, 10 * z, 3 * z);
  ctx.fillRect(cx - 5 * z, cy - 22 * z, 2 * z, 7 * z);
  ctx.fillRect(cx + 3 * z, cy - 22 * z, 2 * z, 7 * z);

  // Manager crown
  if (isManager) {
    ctx.fillStyle = '#fbbf24';
    ctx.font = `${Math.max(8, 8 * z)}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText('★', cx, cy - 24 * z);
    ctx.textAlign = 'left';
  }

  // Name tag above head
  const label = agent.name.split(' ')[0].slice(0, 8);
  ctx.save();
  ctx.font = `${Math.max(7, 7 * z)}px sans-serif`;
  const lw = ctx.measureText(label).width;
  const tagX = cx - lw / 2 - 3;
  const tagY = cy - 29 * z - 11 * z;
  ctx.fillStyle = 'rgba(255,255,255,0.92)';
  ctx.fillRect(tagX, tagY, lw + 6, 11 * z);
  ctx.strokeStyle = colors.shirt; ctx.lineWidth = 1;
  ctx.strokeRect(tagX, tagY, lw + 6, 11 * z);
  ctx.fillStyle = '#1a1a2a';
  ctx.fillText(label, tagX + 3, tagY + 8 * z);
  ctx.restore();

  // Agent visual runtime state badge (IDLE, THINKING, WORKING, WAITING, BLOCKED, COMMUNICATING, USING_MCP, COMPLETED, FAILED)
  drawAgentStatusBubble(scene, agent, cx, cy, z, tx);


  ctx.restore();
}

// ─── 9 Agent Runtime Visual States Status Bubble ────────────────────────

export function drawAgentStatusBubble(scene: PixelSceneState, agent: Agent, cx: number, cy: number, z: number, tx: number = 0): void {
  const ctx = scene.ctx;
  const activeTask = scene.tasks.find(
    (t) => String(t.agent_id) === String(agent.id) &&
      ['running', 'queued', 'waiting_input', 'pending_approval', 'scheduled', 'completed', 'failed'].includes(String(t.status).toLowerCase())
  );

  let state: 'IDLE' | 'THINKING' | 'WORKING' | 'WAITING' | 'BLOCKED' | 'COMMUNICATING' | 'USING_MCP' | 'COMPLETED' | 'FAILED' = 'IDLE';
  const rawAgentStatus = (agent.status || '').toUpperCase();
  if (rawAgentStatus === 'COMMUNICATING') state = 'COMMUNICATING';
  else if (rawAgentStatus === 'USING_MCP') state = 'USING_MCP';
  else if (rawAgentStatus === 'THINKING') state = 'THINKING';
  else if (rawAgentStatus === 'BLOCKED') state = 'BLOCKED';

  if (activeTask) {
    const st = String(activeTask.status).toLowerCase();
    if (st === 'waiting_input' || st === 'pending_approval') {
      state = 'BLOCKED';
    } else if (st === 'scheduled') {
      state = 'WAITING';
    } else if (st === 'running' || st === 'queued') {
      if (state === 'IDLE') {
        if ((agent.status || '').toLowerCase() === 'thinking') {
          state = 'THINKING';
        } else {
          state = 'WORKING';
        }
      }
    } else if (st === 'completed') {
      state = 'COMPLETED';
    } else if (st === 'failed') {
      state = 'FAILED';
    }
  }

  if (state === 'IDLE') {
    const pos = scene.deskMap.get(agent.id);
    const idleBob = Math.sin(scene.tick * 0.06 + tx) * 1.5 * z;
    ctx.save();
    ctx.font = `${Math.max(7, 7 * z)}px sans-serif`;
    ctx.textAlign = 'center';
    const idleIcon = pos?.activity?.includes('Coffee') ? '☕'
      : pos?.activity?.includes('Docs') ? '📖'
      : pos?.activity?.includes('Music') ? '🎧'
      : pos?.activity?.includes('Ideating') ? '💭'
      : '☕';
    ctx.fillText(idleIcon, cx + 7 * z, cy - 24 * z + idleBob);
    ctx.restore();
    return;
  }

  ctx.save();
  const bob = Math.sin(scene.tick * 0.12) * 2.5 * z;
  const bx = cx - 12 * z;
  const by = cy - 46 * z - 11 * z + bob;

  let bg = '#dbeafe';
  let border = '#2563eb';
  let icon = '⚡';

  switch (state) {
    case 'THINKING':
      bg = '#ede9fe';
      border = '#7c3aed';
      icon = '💭';
      break;
    case 'WORKING':
      bg = '#d1fae5';
      border = '#059669';
      icon = '⚡';
      break;
    case 'WAITING':
      bg = '#fef3c7';
      border = '#d97706';
      icon = '⏳';
      break;
    case 'BLOCKED':
      bg = '#fee2e2';
      border = '#dc2626';
      icon = '❓';
      break;
    case 'COMMUNICATING':
      bg = '#cffafe';
      border = '#0891b2';
      icon = '💬';
      break;
    case 'USING_MCP':
      bg = '#fef3c7';
      border = '#b45309';
      icon = '🔌';
      break;
    case 'COMPLETED':
      bg = '#dcfce7';
      border = '#16a34a';
      icon = '✅';
      break;
    case 'FAILED':
      bg = '#fee2e2';
      border = '#b91c1c';
      icon = '❌';
      break;
  }

  ctx.fillStyle = bg;
  ctx.strokeStyle = border;
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.rect(bx, by, 24 * z, 13 * z);
  ctx.fill();
  ctx.stroke();

  // Bubble pointer down
  ctx.beginPath();
  ctx.moveTo(cx - 3 * z, by + 13 * z);
  ctx.lineTo(cx, by + 17 * z);
  ctx.lineTo(cx + 3 * z, by + 13 * z);
  ctx.fillStyle = bg;
  ctx.fill();
  ctx.stroke();

  ctx.font = `${Math.max(9, 9 * z)}px sans-serif`;
  ctx.textAlign = 'center';
  ctx.fillText(icon, cx, by + 10 * z);
  ctx.restore();
}

// ─── Active Visual Connections (Agent<->Agent, MCP, Super Agent) ──────
