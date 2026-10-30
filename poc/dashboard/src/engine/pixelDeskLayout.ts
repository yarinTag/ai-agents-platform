import type { PixelSceneState } from './pixelSceneState';
import type { Agent } from '../types/agent';
import type { Task } from '../types/task';
import { RoomDef, ROOMS, SHIRT_COLORS, HAIR_COLORS, SKIN_TONES } from './pixelSceneLayout';
import { isAgentWorking } from './pixelAgentActivity';

export function clampToRoom(scene: PixelSceneState, room: RoomDef, tx: number, ty: number): { tx: number; ty: number } {
  const minX = room.x + 1;
  const maxX = room.x + room.w - 2;
  const minY = room.y + 2;
  const maxY = room.y + room.h - 2;
  return {
    tx: Math.max(minX, Math.min(maxX, tx)),
    ty: Math.max(minY, Math.min(maxY, ty)),
  };
}

export function getExtraDeskPosition(scene: PixelSceneState, room: RoomDef, extraIdx: number): { dx: number; dy: number; dir: 'up' | 'down' } {
  const colIdx = extraIdx % 3;
  const rowIdx = Math.floor(extraIdx / 3);
  const rawDx = colIdx === 0 ? 1 : colIdx === 1 ? 4 : 7;
  const rawDy = 3.5 + (rowIdx % 2) * 0.5;
  const clamped = clampToRoom(scene, room, room.x + rawDx, room.y + rawDy);
  return {
    dx: clamped.tx - room.x,
    dy: clamped.ty - room.y,
    dir: extraIdx % 2 === 0 ? 'down' : 'up',
  };
}

export function getAgentDepartmentRoom(scene: PixelSceneState, agent: Agent): string {
  const dept = (agent.department || '').toLowerCase().trim();
  const role = (agent.role_type || '').toUpperCase().trim();
  const id = (agent.id || '').toLowerCase();
  const name = (agent.name || '').toLowerCase();

  // 1. Executive / Leadership / Orchestrators
  if (
    dept.includes('exec') || dept.includes('hq') || dept.includes('lead') ||
    dept.includes('management') || dept.includes('board') ||
    id === 'chief-orchestrator' || id.includes('orchestrator') ||
    role === 'ROOT_ORCHESTRATOR' || name.includes('chief')
  ) {
    return 'Executive HQ';
  }

  // 2. Direct matches against valid department rooms with desks
  const validDepts = ['Executive HQ', 'Engineering', 'Marketing', 'Emails', 'Delivery', 'Operations', 'Sales'];
  for (const valid of validDepts) {
    const vk = valid.toLowerCase();
    if (dept === vk || dept.includes(vk) || vk.includes(dept)) {
      return valid;
    }
  }

  // 3. Keyword / semantic mapping
  if (dept.includes('market') || dept.includes('growth') || dept.includes('social') || dept.includes('seo') || dept.includes('content') || dept.includes('brand')) {
    return 'Marketing';
  }
  if (dept.includes('email') || dept.includes('mail') || dept.includes('campaign') || dept.includes('outreach') || dept.includes('newsletter')) {
    return 'Emails';
  }
  if (dept.includes('deliver') || dept.includes('qa') || dept.includes('test') || dept.includes('quality') || dept.includes('release') || dept.includes('ci/cd') || dept.includes('devops') || dept.includes('sre') || dept.includes('infra')) {
    return 'Delivery';
  }
  if (dept.includes('sale') || dept.includes('deal') || dept.includes('crm') || dept.includes('revenue') || dept.includes('biz') || dept.includes('business')) {
    return 'Sales';
  }
  if (dept.includes('op') || dept.includes('finance') || dept.includes('hr') || dept.includes('legal') || dept.includes('account') || dept.includes('billing') || dept.includes('admin') || dept.includes('support') || dept.includes('people')) {
    return 'Operations';
  }
  if (dept.includes('eng') || dept.includes('dev') || dept.includes('code') || dept.includes('tech') || dept.includes('software') || dept.includes('data') || dept.includes('ai') || dept.includes('product') || dept.includes('architect')) {
    return 'Engineering';
  }

  // Dynamic slot allocation for any custom department
  const hash = dept.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return validDepts[hash % validDepts.length];
}

export function getRoomDesks(scene: PixelSceneState, room: RoomDef): Array<{ dx: number; dy: number; dir: 'up' | 'down' | 'left' | 'right'; isManager: boolean }> {
  const list: Array<{ dx: number; dy: number; dir: 'up' | 'down' | 'left' | 'right'; isManager: boolean }> =
    room.desks.map((d, idx) => {
      const clamped = clampToRoom(scene, room, room.x + d.dx, room.y + d.dy);
      return {
        dx: clamped.tx - room.x,
        dy: clamped.ty - room.y,
        dir: d.dir,
        isManager: idx === 0,
      };
    });

  let agentsInRoom = 0;
  scene.deskMap.forEach((pos) => {
    if (pos.roomKey === room.key && pos.isAtDesk) {
      agentsInRoom++;
    }
  });

  if (agentsInRoom > room.desks.length) {
    for (let i = room.desks.length; i < agentsInRoom; i++) {
      const extraIdx = i - room.desks.length;
      const extra = getExtraDeskPosition(scene, room, extraIdx);
      list.push({
        dx: extra.dx,
        dy: extra.dy,
        dir: extra.dir,
        isManager: false,
      });
    }
  }
  return list;
}

export function assignDeskPositions(scene: PixelSceneState): void {
  scene.deskMap.clear();

  const deptCounts: Record<string, number> = {};

  scene.agents.forEach((agent) => {
    const working = isAgentWorking(scene, agent);
    const deptKey = getAgentDepartmentRoom(scene, agent);
    const room = ROOMS.find((r) => r.key === deptKey) || ROOMS.find((r) => r.key === 'Engineering')!;
    const count = deptCounts[deptKey] || 0;
    deptCounts[deptKey] = count + 1;

    let dx: number;
    let dy: number;
    let dir: 'up' | 'down' | 'left' | 'right';

    if (count < room.desks.length) {
      const desk = room.desks[count];
      dx = desk.dx;
      dy = desk.dy;
      dir = desk.dir;
    } else {
      const extraIdx = count - room.desks.length;
      const extra = getExtraDeskPosition(scene, room, extraIdx);
      dx = extra.dx;
      dy = extra.dy;
      dir = extra.dir;
    }

    // Strictly clamp desk position inside the room square bounds (never walls or corridors)
    const { tx, ty } = clampToRoom(scene, room, room.x + dx, room.y + dy);

    // Determine visual activity
    let activity: string | undefined;
    if (!working) {
      const IDLE_ACTIVITIES = [
        '☕ Coffee at Desk',
        '📖 Reading Docs',
        '💭 Ideating',
        '🎧 Listening to Music',
        '⚡ Ready for Task',
        '📝 Reviewing Architecture',
      ];
      const hash = (agent.name || agent.id).split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
      activity = IDLE_ACTIVITIES[(hash + count) % IDLE_ACTIVITIES.length];
    }

    scene.deskMap.set(agent.id, {
      tx,
      ty,
      deskIdx: count,
      roomKey: room.key,
      dir,
      isAtDesk: true,
      activity,
    });
  });
}

export function assignCharColors(scene: PixelSceneState): void {
  scene.agents.forEach((a, i) => {
    if (!scene.charColors.has(a.id)) {
      scene.charColors.set(a.id, {
        shirt: SHIRT_COLORS[i % SHIRT_COLORS.length],
        hair:  HAIR_COLORS[i % HAIR_COLORS.length],
        skin:  SKIN_TONES[i % SKIN_TONES.length],
      });
    }
  });
}

// ════════════════════════════════════════════════════════════════════════
//  MAIN RENDER PIPELINE
// ════════════════════════════════════════════════════════════════════════
