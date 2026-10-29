import type { PixelSceneState } from './pixelSceneState';
import { gs } from './pixelCoordinates';

export function drawOfficeChair(scene: PixelSceneState, tx: number, ty: number, dir: string, isManager = false): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;

  const seatW = T * 0.75;
  const seatH = T * 0.42;
  const backH = T * 0.18;
  const cx = x + T * 0.5 - seatW / 2; // left edge of chair

  // Chair Y position: near the character side of the desk
  // dir='down': character at bottom of tile, chair at ~60% of tile height
  // dir='up':   character at top of tile, chair at ~10% from top (backrest visible above desk)
  const chairTop = dir === 'up'
    ? y + T * 0.02           // above the desk (overlaps slightly)
    : y + T * 0.5;           // below desk center

  // Chair color: blue-gray, manager gets darker
  const backColor = isManager ? '#3a5a8a' : '#4a6a9a';
  const seatColor = isManager ? '#5a7ab8' : '#6a8acc';
  const armColor  = '#3a4a5a';

  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  ctx.fillRect(cx + 2 * z, chairTop + backH + 2 * z, seatW, seatH);

  // Backrest
  ctx.fillStyle = backColor;
  ctx.fillRect(cx, chairTop, seatW, backH);
  ctx.strokeStyle = 'rgba(0,0,0,0.4)'; ctx.lineWidth = 0.7;
  ctx.strokeRect(cx, chairTop, seatW, backH);

  // Backrest highlight
  ctx.fillStyle = 'rgba(255,255,255,0.15)';
  ctx.fillRect(cx + 2 * z, chairTop + 1 * z, seatW - 4 * z, backH * 0.4);

  // Seat cushion
  ctx.fillStyle = seatColor;
  ctx.fillRect(cx, chairTop + backH, seatW, seatH);
  ctx.strokeStyle = 'rgba(0,0,0,0.3)'; ctx.lineWidth = 0.7;
  ctx.strokeRect(cx, chairTop + backH, seatW, seatH);

  // Seat seam line (divides cushion)
  ctx.strokeStyle = 'rgba(0,0,0,0.2)'; ctx.lineWidth = 0.5;
  ctx.beginPath();
  ctx.moveTo(cx, chairTop + backH + seatH * 0.5);
  ctx.lineTo(cx + seatW, chairTop + backH + seatH * 0.5);
  ctx.stroke();

  // Armrests
  ctx.fillStyle = armColor;
  ctx.fillRect(cx - 2.5 * z, chairTop, 2.5 * z, backH + seatH);
  ctx.fillRect(cx + seatW, chairTop, 2.5 * z, backH + seatH);

  // Chair legs (4 small squares at corners)
  const legY = chairTop + backH + seatH;
  ctx.fillStyle = '#2a3a4a';
  ctx.fillRect(cx + 2 * z, legY, 3 * z, 4 * z);
  ctx.fillRect(cx + seatW - 5 * z, legY, 3 * z, 4 * z);
}

// ════════════════════════════════════════════════════════════════════════
//  FURNITURE DRAWING PRIMITIVES  (all in tile coordinates)
// ════════════════════════════════════════════════════════════════════════

export function drawDesk(scene: PixelSceneState, tx: number, ty: number, dir: 'up' | 'down' | 'left' | 'right', isManager = false): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;

  const dw = isManager ? T * 2.0 : T * 1.8;
  const dh = isManager ? T * 1.1 : T * 0.9;

  // Desk shadow
  ctx.fillStyle = 'rgba(0,0,0,0.18)';
  ctx.fillRect(x + 2 * z, y + 2 * z, dw, dh);

  // Desk surface
  ctx.fillStyle = isManager ? '#d8cdb8' : '#ddd8cc';
  ctx.fillRect(x, y, dw, dh);
  ctx.strokeStyle = '#9a8c78'; ctx.lineWidth = 1;
  ctx.strokeRect(x, y, dw, dh);

  // Desk edge (darker front edge)
  ctx.fillStyle = isManager ? '#b8a898' : '#c8c0b0';
  ctx.fillRect(x, y + dh - 3 * z, dw, 3 * z);

  // Monitor on desk
  const mx = x + (isManager ? dw / 2 - 10 * z : dw / 2 - 8 * z);
  const my = y + 2 * z;
  const mw = isManager ? 20 * z : 15 * z;
  const mh = isManager ? 13 * z : 10 * z;

  // Monitor screen
  ctx.fillStyle = '#0f172a';
  ctx.fillRect(mx, my, mw, mh);
  // Screen glow
  const hasTask = false; // will be colored when agents are present
  ctx.fillStyle = '#1e3a5a';
  ctx.fillRect(mx + 1 * z, my + 1 * z, mw - 2 * z, mh - 2 * z);
  // Screen content lines
  ctx.fillStyle = 'rgba(100,180,255,0.5)';
  ctx.fillRect(mx + 2 * z, my + 2 * z, mw - 4 * z, 1 * z);
  ctx.fillStyle = 'rgba(100,180,255,0.3)';
  ctx.fillRect(mx + 2 * z, my + 4 * z, mw - 6 * z, 1 * z);
  ctx.fillRect(mx + 2 * z, my + 6 * z, mw - 8 * z, 1 * z);
  // Monitor stand
  ctx.fillStyle = '#6b7280';
  ctx.fillRect(mx + mw / 2 - 2 * z, my + mh, 4 * z, 3 * z);
  ctx.fillRect(mx + mw / 2 - 5 * z, my + mh + 3 * z, 10 * z, 1.5 * z);

  // Keyboard (tiny strip)
  ctx.fillStyle = '#e8e8e0';
  ctx.fillRect(x + dw * 0.1, y + dh * 0.55, dw * 0.5, 3 * z);
  ctx.strokeStyle = '#c0c0b0'; ctx.lineWidth = 0.5;
  ctx.strokeRect(x + dw * 0.1, y + dh * 0.55, dw * 0.5, 3 * z);

  // Manager has a paper stack
  if (isManager) {
    ctx.fillStyle = '#fef9e7';
    ctx.fillRect(x + dw * 0.7, y + 3 * z, 12 * z, 8 * z);
    ctx.fillStyle = '#fef0c0';
    ctx.fillRect(x + dw * 0.7 + 2 * z, y + 1 * z, 12 * z, 8 * z);
    ctx.strokeStyle = '#d4b066'; ctx.lineWidth = 0.5;
    ctx.strokeRect(x + dw * 0.7 + 2 * z, y + 1 * z, 12 * z, 8 * z);
  }
}

// ─── Couch ──────────────────────────────────────────────────────────
