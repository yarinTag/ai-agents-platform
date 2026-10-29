import type { PixelSceneState } from './pixelSceneState';
import type { Agent } from '../types/agent';
import { P, BW, ENT_Y, HCOR0_Y, ROW1_Y, HCOR1_Y, ROW2_Y, HCOR2_Y, ROW3_Y, COL1_X, VCOR1_X, COL2_X, VCOR2_X, COL3_X, VCOR3_X, COL4_X, ROOMS } from './pixelSceneLayout';
import { tickWalkAnims } from './pixelAgentActivity';
import { gs } from './pixelCoordinates';
import { getRoomDesks } from './pixelDeskLayout';
import { renderAllFloors, renderBuildingShell, renderDoors, renderRoomLabels, renderWallLines } from './pixelBuildingPainter';
import { drawCharacter, drawCharacterSeated } from './pixelCharacterPainter';
import { renderActiveConnections } from './pixelConnectionPainter';
import { drawDesk, drawOfficeChair } from './pixelDeskPainter';
import { drawArcadeMachine, drawArmchair, drawBeanBag, drawCoffeeTable, drawCouch, drawPingPongTable, drawPlant, drawSnackTable, drawWallClock, drawWallTV } from './pixelLeisurePainter';
import { drawBarStool, drawCoffeeMachine, drawConferenceTable, drawCorridorArrow, drawCorridorRug, drawCounter, drawFridge, drawGlassDoors, drawKitchenIsland, drawMicrowave, drawSink, drawWhiteboardWall } from './pixelRoomFurniturePainter';

export function render(scene: PixelSceneState): void {
  const ctx = scene.ctx;
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = P.EXTERIOR;
  ctx.fillRect(0, 0, scene.canvas.width, scene.canvas.height);

  tickWalkAnims(scene);

  renderBuildingShell(scene);    // 1. Cream wall fill for whole building
  renderAllFloors(scene);        // 2. Floor tiles per zone
  renderWallLines(scene);        // 3. Outlines / wall shadows
  renderDoors(scene);            // 4. Door sprites in walls
  renderSpecialFurniture(scene); // 5. Special rooms: lounge, break, etc.
  renderEntranceArea(scene);     // 6. Entrance zone (glass doors, clock, TV)
  renderCorridorDecor(scene);    // 7. Plants, rugs in corridors
  renderChairs(scene);           // 8. Office chairs — behind desks
  renderSeatedAgents(scene);     // 9. Seated characters BEFORE desks (desks cover legs)
  renderDesks(scene);            // 10. Desks on top → agent legs hidden = sitting look
  renderWalkingAgents(scene);    // 11. Walking delivery animations (on top)
  renderActiveConnections(scene); // 12. Active visual connection paths (Agent<->Agent, MCP, Super Agent)
  renderHUD(scene);              // 13. Hover tooltip
  renderRoomLabels(scene);       // 14. Room name badges — LAST so always on top of everything
}


// ─── 1. Building shell (cream wall fill) ──────────────────────────────

export function renderSpecialFurniture(scene: PixelSceneState): void {
  renderLoungeFurniture(scene);
  renderBreakRoomFurniture(scene);
  renderConferenceFurniture(scene);
  renderKitchenFurniture(scene);
}

export function renderLoungeFurniture(scene: PixelSceneState): void {
  const r = ROOMS.find((r) => r.key === 'Lounge')!;
  if (!r) return;
  const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
  // Couch (3 tiles wide, left of center)
  drawCouch(scene, r.x + 1, r.y + 1, 3, 2);
  // Coffee table (2×1 centered)
  drawCoffeeTable(scene, r.x + 2, r.y + 4);
  // Chair on other side
  drawArmchair(scene, r.x + 5, r.y + 1);
  drawArmchair(scene, r.x + 8, r.y + 1);
  // Plants in corners
  drawPlant(scene, r.x + 0, r.y + 0);
  drawPlant(scene, r.x + r.w - 1, r.y + 0);
  drawPlant(scene, r.x + 0, r.y + r.h - 1);
  drawPlant(scene, r.x + r.w - 1, r.y + r.h - 1);
  // Wall TV (on north wall)
  drawWallTV(scene, r.x + 3, r.y);
}

export function renderBreakRoomFurniture(scene: PixelSceneState): void {
  const r = ROOMS.find((r) => r.key === 'Break Room')!;
  if (!r) return;
  drawPingPongTable(scene, r.x + 1, r.y + 1);
  drawArcadeMachine(scene, r.x + 9, r.y + 1);
  drawArcadeMachine(scene, r.x + 11, r.y + 1);
  drawPlant(scene, r.x, r.y);
  drawPlant(scene, r.x + r.w - 1, r.y);
  drawBeanBag(scene, r.x + 1, r.y + 6);
  drawBeanBag(scene, r.x + 3, r.y + 6);
  drawBeanBag(scene, r.x + 10, r.y + 6);
  drawSnackTable(scene, r.x + 9, r.y + 5);
}

export function renderConferenceFurniture(scene: PixelSceneState): void {
  const r = ROOMS.find((r) => r.key === 'Conference')!;
  if (!r) return;
  drawConferenceTable(scene, r.x + 1, r.y + 1, 8, 6);
  // Chairs around table (visual only)
  drawPlant(scene, r.x, r.y);
  drawPlant(scene, r.x + r.w - 1, r.y + r.h - 1);
  drawWhiteboardWall(scene, r.x, r.y + 2);
}

export function renderKitchenFurniture(scene: PixelSceneState): void {
  const r = ROOMS.find((r) => r.key === 'Kitchen')!;
  if (!r) return;
  // Counter run along top wall
  drawCounter(scene, r.x + 0, r.y + 0, 13);
  drawFridge(scene, r.x + 12, r.y + 0);
  drawMicrowave(scene, r.x + 9, r.y + 1);
  drawCoffeeMachine(scene, r.x + 7, r.y + 1);
  drawSink(scene, r.x + 5, r.y + 1);
  // Kitchen island / bar table
  drawKitchenIsland(scene, r.x + 2, r.y + 4, 8, 3);
  drawBarStool(scene, r.x + 3, r.y + 7);
  drawBarStool(scene, r.x + 5, r.y + 7);
  drawBarStool(scene, r.x + 8, r.y + 7);
  drawPlant(scene, r.x, r.y + r.h - 1);
  drawPlant(scene, r.x + r.w - 1, r.y + r.h - 1);
}

// ─── 7. Desks in department rooms ────────────────────────────────────

export function renderDesks(scene: PixelSceneState): void {
  ROOMS.forEach((room) => {
    if (room.desks.length === 0) return;
    const desks = getRoomDesks(scene, room);
    desks.forEach((desk) => {
      const tx = room.x + desk.dx;
      const ty = room.y + desk.dy;
      drawDesk(scene, tx, ty, desk.dir, desk.isManager);
    });
  });
}

// ─── 7. Entrance / reception area ────────────────────────────────────

export function renderEntranceArea(scene: PixelSceneState): void {
  // Glass double doors centered at bottom of entrance zone
  const doorX = Math.floor(BW / 2) - 2;
  const doorY = ENT_Y.end; // y=5
  drawGlassDoors(scene, doorX, doorY);

  // Wall clock on left wall
  drawWallClock(scene, COL1_X.start + 2, ENT_Y.start);

  // Wall-mounted TV / company display on right side
  drawWallTV(scene, COL3_X.start + 2, ENT_Y.start);

  // Plants along entrance
  drawPlant(scene, 1, ENT_Y.start);
  drawPlant(scene, BW - 2, ENT_Y.start);
  drawPlant(scene, doorX - 2, ENT_Y.end - 1);
  drawPlant(scene, doorX + 4, ENT_Y.end - 1);

  // Lounge / waiting chairs along sides of entrance
  drawArmchair(scene, COL1_X.start, ENT_Y.start + 2);
  drawArmchair(scene, COL1_X.start + 2, ENT_Y.start + 2);
  drawArmchair(scene, COL4_X.end - 2, ENT_Y.start + 2);
  drawArmchair(scene, COL4_X.end - 1, ENT_Y.start + 2);
}

// ─── 9. Corridor decor ────────────────────────────────────────────────

export function renderCorridorDecor(scene: PixelSceneState): void {
  // Plants at corridor intersections
  const intersX = [VCOR1_X.start, VCOR2_X.start, VCOR3_X.start];
  const intersY = [HCOR0_Y.start, HCOR1_Y.start, HCOR2_Y.start];
  intersX.forEach((x) => intersY.forEach((y) => {
    drawPlant(scene, x, y);
  }));

  // Small rugs / direction mats in corridors
  [HCOR0_Y.start + 1, HCOR1_Y.start + 1, HCOR2_Y.start + 1].forEach((y) => {
    drawCorridorRug(scene, COL1_X.start + 4, y);
    drawCorridorRug(scene, COL2_X.start + 4, y);
    drawCorridorRug(scene, COL3_X.start + 4, y);
  });

  // Arrows / direction markers in V-corridors (subtle)
  [VCOR1_X.start, VCOR2_X.start, VCOR3_X.start].forEach((x) => {
    [ROW1_Y.start + 3, ROW2_Y.start + 3, ROW3_Y.start + 3].forEach((y) => {
      drawCorridorArrow(scene, x, y);
    });
  });
}

// ─── 9. Office chairs behind every desk ──────────────────────────────

export function renderChairs(scene: PixelSceneState): void {
  ROOMS.forEach((room) => {
    if (room.desks.length === 0) return;
    const desks = getRoomDesks(scene, room);
    desks.forEach((desk) => {
      const tx = room.x + desk.dx;
      const ty = room.y + desk.dy;
      drawOfficeChair(scene, tx, ty, desk.dir, desk.isManager);
    });
  });
}

// ─── 10. Seated agents & resting agents ──────────────────────────────

export function renderSeatedAgents(scene: PixelSceneState): void {
  const items: Array<{ agent: Agent; tx: number; ty: number; dir: string; isAtDesk: boolean }> = [];
  scene.agents.forEach((a) => {
    const pos = scene.deskMap.get(a.id);
    if (pos && !scene.walkAnims.has(a.id)) {
      items.push({ agent: a, tx: pos.tx, ty: pos.ty, dir: pos.dir, isAtDesk: pos.isAtDesk });
    }
  });
  // Sort by Y so southern characters draw on top of northern ones
  items.sort((a, b) => a.ty - b.ty);
  items.forEach(({ agent, tx, ty, dir, isAtDesk }) => {
    if (isAtDesk) {
      drawCharacterSeated(scene, agent, tx, ty, dir);
    } else {
      drawCharacter(scene, agent, tx, ty, 'seated');
    }
  });
}

// ─── 11. Walking agents ──────────────────────────────────────────────

export function renderWalkingAgents(scene: PixelSceneState): void {
  scene.walkAnims.forEach((anim) => {
    const agent = scene.agents.find((a) => String(a.id) === anim.agentId);
    if (!agent) return;
    const t = anim.phase === 'returning' ? 1 - anim.progress : anim.progress;
    const cx = anim.fromX + (anim.toX - anim.fromX) * t;
    const cy = anim.fromY + (anim.toY - anim.fromY) * t;
    drawCharacter(scene, agent, cx, cy, 'walking', anim.phase === 'delivering');
  });
}

// ─── 12. HUD ────────────────────────────────────────────────────────

export function renderHUD(scene: PixelSceneState): void {
  if (!scene.hoveredAgentId) return;
  const agent = scene.agents.find((a) => a.id === scene.hoveredAgentId);
  const pos = scene.deskMap.get(scene.hoveredAgentId);
  if (!agent || !pos) return;

  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x: ax, y: ay } = gs(scene, pos.tx, pos.ty);
  const task = scene.tasks.find(
    (t) => String(t.agent_id) === String(agent.id) && (t.status === 'running' || t.status === 'queued')
  );
  const wk = scene.walkAnims.get(agent.id);

  const TW = 220, TH = task || wk ? 80 : 60;
  const tx = Math.min(Math.max(ax - TW / 2, 8), scene.canvas.width - TW - 8);
  const ty2 = Math.max(ay - TH - T * 1.5, 8);

  ctx.save();
  ctx.fillStyle = 'rgba(248,248,245,0.97)';
  ctx.strokeStyle = '#8c7a5e';
  ctx.lineWidth = 1.5;
  ctx.fillRect(tx, ty2, TW, TH);
  ctx.strokeRect(tx, ty2, TW, TH);

  // Left color bar
  const colors = scene.charColors.get(agent.id);
  ctx.fillStyle = colors?.shirt || '#3b82f6';
  ctx.fillRect(tx, ty2, 4, TH);

  ctx.fillStyle = '#1a1a2a';
  ctx.font = 'bold 12px sans-serif';
  ctx.fillText(agent.name, tx + 10, ty2 + 18);
  ctx.fillStyle = '#6b5c3e';
  ctx.font = '10px sans-serif';
  ctx.fillText(`${pos.roomKey} · ${agent.role_type || 'WORKER'}`, tx + 10, ty2 + 34);

  if (wk) {
    ctx.fillStyle = '#c46a2a';
    ctx.font = 'bold 10px sans-serif';
    ctx.fillText(wk.phase === 'walking' ? '🚶 Walking to manager...'
      : wk.phase === 'delivering' ? '📋 Delivering task!' : '↩️ Returning to desk...', tx + 10, ty2 + 52);
  } else if (task) {
    ctx.fillStyle = '#1a6b3a';
    ctx.font = 'bold 10px sans-serif';
    const raw = typeof task.input_data === 'string' ? task.input_data
      : ((task.input_data as any)?.prompt ?? (task.input_data as any)?.task ?? '');
    ctx.fillText(`⚡ ${raw.slice(0, 26)}${raw.length > 26 ? '...' : ''}`, tx + 10, ty2 + 52);
  } else if (pos.activity) {
    ctx.fillStyle = '#6366f1';
    ctx.font = 'bold 10px sans-serif';
    ctx.fillText(pos.activity, tx + 10, ty2 + 50);
  } else {
    ctx.fillStyle = '#888';
    ctx.fillText('Ready · waiting for task', tx + 10, ty2 + 48);
  }
  ctx.restore();
}

// ════════════════════════════════════════════════════════════════════════
//  CHARACTER DRAWING  (chibi top-down pixel art sprites)
// ════════════════════════════════════════════════════════════════════════
