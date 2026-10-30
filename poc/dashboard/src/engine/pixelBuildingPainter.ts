import type { PixelSceneState } from './pixelSceneState';
import { P, BW, BH, ENT_Y, HCOR0_Y, ROW1_Y, HCOR1_Y, ROW2_Y, HCOR2_Y, ROW3_Y, COL1_X, VCOR1_X, COL2_X, VCOR2_X, COL3_X, VCOR3_X, COL4_X, ROOMS } from './pixelSceneLayout';
import { gs } from './pixelCoordinates';
import { getAgentDepartmentRoom } from './pixelDeskLayout';

export function renderBuildingShell(scene: PixelSceneState): void {
  const { x: bx, y: by } = gs(scene, 0, 0);
  const bw = BW * scene.T * scene.zoom;
  const bh = BH * scene.T * scene.zoom;
  // Outer shadow
  const ctx = scene.ctx;
  ctx.shadowColor = 'rgba(0,0,0,0.5)';
  ctx.shadowBlur = 16 * scene.zoom;
  ctx.fillStyle = P.WALL;
  ctx.fillRect(bx, by, bw, bh);
  ctx.shadowBlur = 0;
  // Outer border
  ctx.strokeStyle = P.WALL_OUTLINE;
  ctx.lineWidth = 2;
  ctx.strokeRect(bx, by, bw, bh);
}

// ─── 2. All floor tiles ───────────────────────────────────────────────

export function renderAllFloors(scene: PixelSceneState): void {
  // Entrance (wood)
  fillFloor(scene, ENT_Y.start, ENT_Y.end, 0, BW - 1, 'wood');

  // Horizontal corridors
  fillFloor(scene, HCOR0_Y.start, HCOR0_Y.end, 0, BW - 1, 'hall');
  fillFloor(scene, HCOR1_Y.start, HCOR1_Y.end, 0, BW - 1, 'hall');
  fillFloor(scene, HCOR2_Y.start, HCOR2_Y.end, 0, BW - 1, 'hall');

  // Vertical corridors
  fillFloor(scene, 0, BH - 1, VCOR1_X.start, VCOR1_X.end, 'hall');
  fillFloor(scene, 0, BH - 1, VCOR2_X.start, VCOR2_X.end, 'hall');
  fillFloor(scene, 0, BH - 1, VCOR3_X.start, VCOR3_X.end, 'hall');

  // Room floors
  ROOMS.forEach((room) => {
    fillFloor(scene, room.y, room.y + room.h - 1, room.x, room.x + room.w - 1, room.floor);
  });
}

export function fillFloor(scene: PixelSceneState, y1: number, y2: number, x1: number, x2: number, type: string): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const [c1, c2, cg] = floorColors(scene, type);

  for (let ty = y1; ty <= y2; ty++) {
    for (let tx = x1; tx <= x2; tx++) {
      const { x, y } = gs(scene, tx, ty);
      const isAlt = (tx + ty) % 2 === 0;
      ctx.fillStyle = isAlt ? c1 : c2;
      ctx.fillRect(x, y, T, T);
      // Grout lines / tile grid
      ctx.strokeStyle = cg;
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x + 0.5, y + 0.5, T - 1, T - 1);
    }
  }

  // Wood grain lines for wood floors
  if (type === 'wood') {
    ctx.strokeStyle = 'rgba(120,80,40,0.18)';
    ctx.lineWidth = 0.8;
    for (let ty = y1; ty <= y2; ty++) {
      const { y } = gs(scene, x1, ty);
      ctx.beginPath();
      ctx.moveTo(gs(scene, x1, ty).x, y + T * 0.33);
      ctx.lineTo(gs(scene, x2 + 1, ty).x, y + T * 0.33);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(gs(scene, x1, ty).x, y + T * 0.66);
      ctx.lineTo(gs(scene, x2 + 1, ty).x, y + T * 0.66);
      ctx.stroke();
    }
  }
}

export function floorColors(scene: PixelSceneState, type: string): [string, string, string] {
  switch (type) {
    case 'wood':   return [P.FLOOR_WOOD1, P.FLOOR_WOOD2, 'rgba(100,60,20,0.2)'];
    case 'hall':   return [P.FLOOR_HALL1, P.FLOOR_HALL2, P.GROUT];
    case 'carpet': return [P.FLOOR_CARPET1, P.FLOOR_CARPET2, 'rgba(140,100,60,0.2)'];
    case 'tile':   return [P.FLOOR_TILE1, P.FLOOR_TILE2, 'rgba(150,150,140,0.4)'];
    case 'blue':   return [P.FLOOR_BLUE1, P.FLOOR_BLUE2, 'rgba(100,120,160,0.25)'];
    default:       return [P.FLOOR_GRAY1, P.FLOOR_GRAY2, P.GROUT];
  }
}

// ─── 3. Wall lines (outlines between zones) ───────────────────────────

export function renderWallLines(scene: PixelSceneState): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;

  // Helper: draw a horizontal wall line
  const hLine = (ty: number, x1: number, x2: number, thick = 2) => {
    const p1 = gs(scene, x1, ty);
    const p2 = gs(scene, x2 + 1, ty);
    ctx.strokeStyle = P.WALL_OUTLINE;
    ctx.lineWidth = thick;
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p1.y); ctx.stroke();
  };

  // Helper: draw a vertical wall line
  const vLine = (tx: number, y1: number, y2: number, thick = 2) => {
    const p1 = gs(scene, tx, y1);
    const p2 = gs(scene, tx, y2 + 1);
    ctx.strokeStyle = P.WALL_OUTLINE;
    ctx.lineWidth = thick;
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p1.x, p2.y); ctx.stroke();
  };

  // Outer building outline (drawn over shell)
  const bp = gs(scene, 0, 0);
  ctx.strokeStyle = P.WALL_OUTLINE; ctx.lineWidth = 2;
  ctx.strokeRect(bp.x, bp.y, BW * T, BH * T);

  // Horizontal wall separators
  hLine(0, 0, BW - 1);       // top outer
  hLine(BH, 0, BW - 1);      // bottom outer
  hLine(ENT_Y.end + 1, 0, BW - 1);    // south of entrance (y=6)
  hLine(HCOR0_Y.end + 1, 0, BW - 1); // y=10
  hLine(ROW1_Y.end + 1, 0, BW - 1);  // y=19
  hLine(HCOR1_Y.end + 1, 0, BW - 1); // y=23
  hLine(ROW2_Y.end + 1, 0, BW - 1);  // y=32
  hLine(HCOR2_Y.end + 1, 0, BW - 1); // y=36
  hLine(ROW3_Y.end + 1, 0, BW - 1);  // y=45

  // Vertical wall separators
  vLine(0, 0, BH - 1);
  vLine(BW, 0, BH - 1);
  vLine(COL1_X.end + 1, 0, BH - 1); // x=11
  vLine(VCOR1_X.end + 1, 0, BH - 1); // x=14
  vLine(COL2_X.end + 1, 0, BH - 1); // x=25
  vLine(VCOR2_X.end + 1, 0, BH - 1); // x=28
  vLine(COL3_X.end + 1, 0, BH - 1); // x=39
  vLine(VCOR3_X.end + 1, 0, BH - 1); // x=42

  // Subtle south shadow on horizontal walls (RPG depth effect)
  const shadowH = (ty: number, x1: number, x2: number) => {
    const { x: px, y: py } = gs(scene, x1, ty);
    const pw = (x2 - x1 + 1) * T;
    ctx.fillStyle = 'rgba(0,0,0,0.15)';
    ctx.fillRect(px, py, pw, Math.max(2, 3 * scene.zoom));
  };
  [ENT_Y.end + 1, HCOR0_Y.end + 1, ROW1_Y.end + 1, HCOR1_Y.end + 1, ROW2_Y.end + 1, HCOR2_Y.end + 1, ROW3_Y.end + 1].forEach((y) => {
    shadowH(y, 0, BW - 1);
  });
}

// ─── 4. Door sprites ─────────────────────────────────────────────────

export function renderDoors(scene: PixelSceneState): void {
  // H-wall door positions (on H-walls between corridors and rooms)
  const hDoors: Array<{ tx: number; ty: number }> = [
    // Wall at y=10 (between H-corr0 and room row 1) — one door per room column, +V-corr openings
    { tx: COL1_X.start + 4, ty: HCOR0_Y.end + 1 }, // Marketing
    { tx: COL2_X.start + 4, ty: HCOR0_Y.end + 1 }, // Exec HQ
    { tx: COL3_X.start + 4, ty: HCOR0_Y.end + 1 }, // Engineering
    { tx: COL4_X.start + 5, ty: HCOR0_Y.end + 1 }, // Reception

    // Wall at y=23 (H-corr1 → row2)
    { tx: COL1_X.start + 4, ty: HCOR1_Y.end + 1 },
    { tx: COL2_X.start + 4, ty: HCOR1_Y.end + 1 },
    { tx: COL3_X.start + 4, ty: HCOR1_Y.end + 1 },
    { tx: COL4_X.start + 5, ty: HCOR1_Y.end + 1 },

    // Wall at y=36 (H-corr2 → row3)
    { tx: COL1_X.start + 4, ty: HCOR2_Y.end + 1 },
    { tx: COL2_X.start + 4, ty: HCOR2_Y.end + 1 },
    { tx: COL3_X.start + 4, ty: HCOR2_Y.end + 1 },
    { tx: COL4_X.start + 5, ty: HCOR2_Y.end + 1 },
  ];

  // V-wall door positions (in V-walls between V-corridors and room columns)
  const vDoors: Array<{ tx: number; ty: number }> = [
    // Wall at x=11 (Col1 → V-corr1) — one per row
    { tx: COL1_X.end + 1, ty: ROW1_Y.start + 3 },
    { tx: COL1_X.end + 1, ty: ROW2_Y.start + 3 },
    { tx: COL1_X.end + 1, ty: ROW3_Y.start + 3 },
    // Wall at x=14 (V-corr1 → Col2)
    { tx: VCOR1_X.end + 1, ty: ROW1_Y.start + 3 },
    { tx: VCOR1_X.end + 1, ty: ROW2_Y.start + 3 },
    { tx: VCOR1_X.end + 1, ty: ROW3_Y.start + 3 },
    // Wall at x=25 (Col2 → V-corr2)
    { tx: COL2_X.end + 1, ty: ROW1_Y.start + 3 },
    { tx: COL2_X.end + 1, ty: ROW2_Y.start + 3 },
    { tx: COL2_X.end + 1, ty: ROW3_Y.start + 3 },
    // Wall at x=28 (V-corr2 → Col3)
    { tx: VCOR2_X.end + 1, ty: ROW1_Y.start + 3 },
    { tx: VCOR2_X.end + 1, ty: ROW2_Y.start + 3 },
    { tx: VCOR2_X.end + 1, ty: ROW3_Y.start + 3 },
    // Wall at x=39 (Col3 → V-corr3)
    { tx: COL3_X.end + 1, ty: ROW1_Y.start + 3 },
    { tx: COL3_X.end + 1, ty: ROW2_Y.start + 3 },
    { tx: COL3_X.end + 1, ty: ROW3_Y.start + 3 },
    // Wall at x=42 (V-corr3 → Col4)
    { tx: VCOR3_X.end + 1, ty: ROW1_Y.start + 3 },
    { tx: VCOR3_X.end + 1, ty: ROW2_Y.start + 3 },
    { tx: VCOR3_X.end + 1, ty: ROW3_Y.start + 3 },
  ];

  hDoors.forEach((d) => drawHDoor(scene, d.tx, d.ty));
  vDoors.forEach((d) => drawVDoor(scene, d.tx, d.ty));
}

export function drawHDoor(scene: PixelSceneState, tx: number, ty: number): void {
  // A horizontal door: 2 tiles wide, 1 tile tall, drawn ON the wall tile
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  // Floor background showing through
  ctx.fillStyle = P.FLOOR_HALL1;
  ctx.fillRect(x, y, T * 2, T);
  // Door frame
  ctx.fillStyle = P.DOOR;
  ctx.fillRect(x, y, T * 2, Math.max(2, 3 * scene.zoom));
  ctx.fillRect(x, y, Math.max(2, 2 * scene.zoom), T);
  ctx.fillRect(x + T * 2 - Math.max(2, 2 * scene.zoom), y, Math.max(2, 2 * scene.zoom), T);
  // Door fill
  ctx.fillStyle = P.DOOR_FILL;
  ctx.fillRect(x + Math.max(2, 2 * scene.zoom), y + Math.max(2, 3 * scene.zoom), T * 2 - Math.max(4, 4 * scene.zoom), T - Math.max(2, 3 * scene.zoom));
  // Door knob
  ctx.fillStyle = '#c8a050';
  ctx.beginPath(); ctx.arc(x + T * 1.5, y + T * 0.55, Math.max(2, 2 * scene.zoom), 0, Math.PI * 2); ctx.fill();
}

export function drawVDoor(scene: PixelSceneState, tx: number, ty: number): void {
  // A vertical door: 1 tile wide, 2 tiles tall
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  ctx.fillStyle = P.FLOOR_HALL1;
  ctx.fillRect(x, y, T, T * 2);
  ctx.fillStyle = P.DOOR;
  ctx.fillRect(x, y, T, Math.max(2, 2 * scene.zoom));
  ctx.fillRect(x, y + T * 2 - Math.max(2, 2 * scene.zoom), T, Math.max(2, 2 * scene.zoom));
  ctx.fillRect(x, y, Math.max(2, 3 * scene.zoom), T * 2);
  ctx.fillStyle = P.DOOR_FILL;
  ctx.fillRect(x + Math.max(2, 3 * scene.zoom), y + Math.max(2, 2 * scene.zoom), T - Math.max(2, 3 * scene.zoom), T * 2 - Math.max(4, 4 * scene.zoom));
  ctx.fillStyle = '#c8a050';
  ctx.beginPath(); ctx.arc(x + T * 0.55, y + T * 1.5, Math.max(2, 2 * scene.zoom), 0, Math.PI * 2); ctx.fill();
}

// ─── Room name labels — rendered LAST so always on top ──────────────

export function renderRoomLabels(scene: PixelSceneState): void {
  const ctx = scene.ctx;

  ROOMS.forEach((room) => {
    const isFacility = room.desks.length === 0;

    let label = room.label;
    let icon = room.icon;
    let accent = room.accent;

    if (!isFacility) {
      const roomAgents = scene.agents.filter((a) => getAgentDepartmentRoom(scene, a) === room.key);
      if (roomAgents.length > 0) {
        const firstAgentDept = (roomAgents[0].department || '').trim();
        if (firstAgentDept) {
          label = firstAgentDept.toUpperCase();
        }
      } else {
        label = 'AVAILABLE SUITE';
        icon = '🚪';
        accent = '#94a3b8';
      }
    }

    const text = `${icon} ${label}`;
    ctx.save();
    ctx.font = `bold ${Math.max(8.5, 8.5 * scene.zoom)}px sans-serif`;
    const tw = ctx.measureText(text).width;
    const bw = tw + 16, bh = 15 * scene.zoom;

    // Position: More on top, centered horizontally in the corridor between the rooms
    const centerScreen = gs(scene, room.x + room.w / 2, room.y - 2.5);
    const lx = centerScreen.x - bw / 2;
    const ly = centerScreen.y - bh / 2;

    // Drop shadow
    ctx.fillStyle = 'rgba(0,0,0,0.25)';
    ctx.fillRect(lx + 2, ly + 2, bw, bh);

    // White background pill
    ctx.fillStyle = 'rgba(255,255,255,0.97)';
    ctx.fillRect(lx, ly, bw, bh);
    ctx.strokeStyle = accent;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(lx, ly, bw, bh);

    // Left accent bar
    ctx.fillStyle = accent;
    ctx.fillRect(lx, ly, 3.5, bh);

    ctx.fillStyle = '#1a1a2a';
    ctx.fillText(text, lx + 8, ly + bh * 0.74);
    ctx.restore();
  });
}

// ─── 6. Special room furniture ───────────────────────────────────────
