import type { PixelSceneState } from './pixelSceneState';
import { gs } from './pixelCoordinates';
import { fillFloor } from './pixelBuildingPainter';

export function drawConferenceTable(scene: PixelSceneState, tx: number, ty: number, wTiles: number, hTiles: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const w = T * wTiles, h = T * hTiles;
  const cx = x + w / 2, cy = y + h / 2;
  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.22)'; ctx.beginPath(); ctx.ellipse(cx + 3 * z, cy + 3 * z, w / 2, h / 2, 0, 0, Math.PI * 2); ctx.fill();
  // Table top (oval)
  ctx.fillStyle = '#c4a870'; ctx.beginPath(); ctx.ellipse(cx, cy, w / 2, h / 2, 0, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#8a6a38'; ctx.lineWidth = 2; ctx.stroke();
  // Gold ring inlay
  ctx.strokeStyle = '#d4b850'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.ellipse(cx, cy, w / 2 - 5 * z, h / 2 - 5 * z, 0, 0, Math.PI * 2); ctx.stroke();
  // Laptops/papers around table
  for (let i = 0; i < 8; i++) {
    const ang = (i / 8) * Math.PI * 2;
    const lapX = cx + Math.cos(ang) * (w / 2 - 12 * z);
    const lapY = cy + Math.sin(ang) * (h / 2 - 8 * z);
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(lapX - 5 * z, lapY - 4 * z, 10 * z, 7 * z);
    ctx.fillStyle = Math.sin(scene.tick * 0.05 + i) > 0 ? '#1e3a5a' : '#3b82f6';
    ctx.fillRect(lapX - 4 * z, lapY - 3 * z, 8 * z, 5 * z);
  }
  // Coffee cups
  ctx.fillStyle = '#d4c5a0';
  ctx.beginPath(); ctx.ellipse(cx - 15 * z, cy, 4 * z, 4 * z, 0, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(cx + 15 * z, cy, 4 * z, 4 * z, 0, 0, Math.PI * 2); ctx.fill();
}

// ─── Whiteboard ──────────────────────────────────────────────────────

export function drawWhiteboardWall(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const w = T * 1.5, h = T * 3;
  ctx.fillStyle = '#f5f5ee'; ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = '#9a9090'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, w, h);
  // Frame
  ctx.fillStyle = '#8a7060'; ctx.fillRect(x, y, w, 4 * z);
  ctx.fillRect(x, y + h - 4 * z, w, 4 * z);
  // Content
  ctx.strokeStyle = '#2060a0'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(x + 5 * z, y + 15 * z); ctx.lineTo(x + w * 0.6, y + 25 * z); ctx.lineTo(x + w - 5 * z, y + 18 * z); ctx.stroke();
  ctx.fillStyle = '#e04040'; ctx.fillRect(x + 5 * z, y + h - 15 * z, 12 * z, 2 * z);
  ctx.fillRect(x + 5 * z, y + h - 11 * z, 8 * z, 2 * z);
  ctx.fillStyle = '#2060a0'; ctx.fillRect(x + 5 * z, y + h - 7 * z, 10 * z, 2 * z);
  ctx.font = `${Math.max(6, 6 * z)}px sans-serif`; ctx.fillStyle = '#404050';
  ctx.fillText('ROADMAP', x + 4 * z, y + 12 * z);
}

// ─── Kitchen counter ─────────────────────────────────────────────────

export function drawCounter(scene: PixelSceneState, tx: number, ty: number, wTiles: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const w = T * wTiles, h = T * 0.8;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(x + 2 * z, y + 2 * z, w, h);
  ctx.fillStyle = '#e0ddd6'; ctx.fillRect(x, y, w, h);
  // Marble veins
  ctx.strokeStyle = 'rgba(160,155,145,0.4)'; ctx.lineWidth = 0.5;
  for (let i = 0; i < 3; i++) {
    ctx.beginPath();
    ctx.moveTo(x + i * T * 3, y);
    ctx.quadraticCurveTo(x + i * T * 3 + T, y + h / 2, x + i * T * 3 + T * 1.5, y + h);
    ctx.stroke();
  }
  ctx.fillStyle = '#a0978a'; ctx.fillRect(x, y + h - 4 * z, w, 4 * z);
  ctx.strokeStyle = '#8c8278'; ctx.lineWidth = 1; ctx.strokeRect(x, y, w, h);
}

// ─── Fridge ───────────────────────────────────────────────────────────

export function drawFridge(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = '#e8e8e0'; ctx.fillRect(x, y, T, T * 1.5);
  ctx.fillStyle = '#d8d8d0'; ctx.fillRect(x, y, T, T * 0.7);
  ctx.strokeStyle = '#9a9a90'; ctx.lineWidth = 1; ctx.strokeRect(x, y, T, T * 1.5);
  ctx.beginPath(); ctx.moveTo(x, y + T * 0.7); ctx.lineTo(x + T, y + T * 0.7); ctx.stroke();
  ctx.fillStyle = '#888880'; ctx.fillRect(x + T * 0.75, y + T * 0.25, 4 * z, 12 * z);
  ctx.fillRect(x + T * 0.75, y + T * 0.85, 4 * z, 10 * z);
  ctx.fillStyle = '#c0d8e8'; ctx.fillRect(x + 2 * z, y + 2 * z, T * 0.6, T * 0.55);
  ctx.font = `${Math.max(6, 6 * z)}px sans-serif`; ctx.fillStyle = '#606060';
  ctx.textAlign = 'center'; ctx.fillText('❄️', x + T / 2, y + T * 0.4); ctx.textAlign = 'left';
}

// ─── Microwave ────────────────────────────────────────────────────────

export function drawMicrowave(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = '#3a3a3a'; ctx.fillRect(x, y + T * 0.2, T * 1.2, T * 0.6);
  ctx.strokeStyle = '#555'; ctx.lineWidth = 0.8; ctx.strokeRect(x, y + T * 0.2, T * 1.2, T * 0.6);
  const on = (scene.tick % 180) < 90;
  ctx.fillStyle = on ? '#1a2a1a' : '#111'; ctx.fillRect(x + 2 * z, y + T * 0.22, T * 0.75, T * 0.56);
  if (on) { ctx.font = `${Math.max(8, 8 * z)}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText('🍕', x + T * 0.35, y + T * 0.6); ctx.textAlign = 'left'; }
  ctx.fillStyle = '#555'; ctx.fillRect(x + T * 0.9, y + T * 0.22, T * 0.28, T * 0.56);
  ctx.fillStyle = on ? '#22c55e' : '#555'; ctx.fillRect(x + T * 0.92, y + T * 0.3, T * 0.08, T * 0.1);
}

// ─── Coffee machine ───────────────────────────────────────────────────

export function drawCoffeeMachine(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = '#2a2a2a'; ctx.fillRect(x, y, T * 0.9, T);
  ctx.strokeStyle = '#444'; ctx.lineWidth = 0.8; ctx.strokeRect(x, y, T * 0.9, T);
  ctx.fillStyle = 'rgba(168,212,240,0.35)'; ctx.fillRect(x + 2 * z, y + 2 * z, T * 0.5, T * 0.45);
  ctx.strokeStyle = '#5a9abe'; ctx.lineWidth = 0.5; ctx.strokeRect(x + 2 * z, y + 2 * z, T * 0.5, T * 0.45);
  ctx.fillStyle = '#4a3020'; ctx.fillRect(x + 2 * z, y + T * 0.6, T * 0.7, T * 0.35);
  ctx.fillStyle = '#c8b848';
  ctx.beginPath(); ctx.arc(x + T * 0.45, y + T * 0.75, 3 * z, 0, Math.PI * 2); ctx.fill();
  ctx.font = `${Math.max(7, 7 * z)}px sans-serif`; ctx.fillStyle = '#c8a050';
  ctx.textAlign = 'center'; ctx.fillText('☕', x + T * 0.45, y + T * 1.1); ctx.textAlign = 'left';
}

// ─── Sink ────────────────────────────────────────────────────────────

export function drawSink(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = '#b0b8c0'; ctx.fillRect(x, y, T, T * 0.8);
  ctx.fillStyle = '#8a9298'; ctx.fillRect(x + 3 * z, y + 3 * z, T - 6 * z, T * 0.65);
  const run = (scene.tick % 240) < 120;
  if (run) { ctx.fillStyle = 'rgba(147,197,253,0.5)'; ctx.fillRect(x + 4 * z, y + 4 * z, T - 8 * z, T * 0.55); }
  ctx.fillStyle = '#9098a0'; ctx.fillRect(x + T / 2 - 2 * z, y, 4 * z, 8 * z);
  ctx.fillRect(x + T / 2 - 8 * z, y + 1 * z, 16 * z, 3 * z);
  ctx.fillStyle = '#606870'; ctx.beginPath(); ctx.arc(x + T / 2, y + T * 0.6, 3 * z, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#707880'; ctx.lineWidth = 0.8; ctx.strokeRect(x, y, T, T * 0.8);
}

// ─── Kitchen island ───────────────────────────────────────────────────

export function drawKitchenIsland(scene: PixelSceneState, tx: number, ty: number, wTiles: number, hTiles: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const w = T * wTiles, h = T * hTiles;
  ctx.fillStyle = 'rgba(0,0,0,0.18)'; ctx.fillRect(x + 3 * z, y + 3 * z, w, h);
  ctx.fillStyle = '#d8cdb8'; ctx.fillRect(x, y, w, h);
  // Marble
  ctx.strokeStyle = 'rgba(160,150,130,0.35)'; ctx.lineWidth = 0.5;
  ctx.beginPath(); ctx.moveTo(x + T * 1.5, y); ctx.lineTo(x + T * 2, y + h); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x + T * 4, y); ctx.lineTo(x + T * 4.5, y + h); ctx.stroke();
  ctx.fillStyle = '#b8a898'; ctx.fillRect(x, y + h - 4 * z, w, 4 * z);
  ctx.strokeStyle = '#9a8878'; ctx.lineWidth = 1.2; ctx.strokeRect(x, y, w, h);
  // Food items
  ctx.font = `${Math.max(9, 9 * z)}px sans-serif`; ctx.textAlign = 'center';
  ctx.fillText('🍎', x + T * 0.8, y + h / 2 + 5 * z);
  ctx.fillText('🥗', x + T * 2.5, y + h / 2 + 5 * z);
  ctx.fillText('☕', x + T * 4.5, y + h / 2 + 5 * z);
  ctx.textAlign = 'left';
}

// ─── Bar stool ───────────────────────────────────────────────────────

export function drawBarStool(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const cx = x + T / 2, cy = y + T / 2;
  ctx.fillStyle = 'rgba(0,0,0,0.18)'; ctx.beginPath(); ctx.ellipse(cx + 1 * z, cy + 1 * z, 7 * z, 5 * z, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#5a4a3a'; ctx.beginPath(); ctx.ellipse(cx, cy, 7 * z, 5 * z, 0, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#3a2a1a'; ctx.lineWidth = 0.8; ctx.stroke();
  ctx.strokeStyle = '#6a5a4a'; ctx.lineWidth = 1.5;
  ctx.beginPath(); ctx.moveTo(cx, cy + 5 * z); ctx.lineTo(cx, cy + T * 0.35); ctx.stroke();
}

// ─── Corridor rug ─────────────────────────────────────────────────────

export function drawCorridorRug(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = 'rgba(120,100,80,0.3)';
  ctx.fillRect(x - T * 0.3, y + 2 * z, T * 2.6, T - 4 * z);
  ctx.strokeStyle = 'rgba(120,100,80,0.5)'; ctx.lineWidth = 1;
  ctx.strokeRect(x - T * 0.3 + 2 * z, y + 4 * z, T * 2.6 - 4 * z, T - 8 * z);
}

// ─── Corridor arrow ───────────────────────────────────────────────────

export function drawCorridorArrow(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const cx = x + T, cy = y + T / 2;
  ctx.fillStyle = 'rgba(100,120,180,0.25)';
  ctx.beginPath();
  ctx.moveTo(cx, cy - 4 * z);
  ctx.lineTo(cx + 4 * z, cy);
  ctx.lineTo(cx, cy + 4 * z);
  ctx.closePath();
  ctx.fill();
}

// ─── Reception desk ───────────────────────────────────────────────────

export function drawReceptionDesk(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const w = T * 8, h = T * 1.5;
  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.fillRect(x + 3 * z, y + 3 * z, w, h);
  // Desk surface
  ctx.fillStyle = '#d8cdb8'; ctx.fillRect(x, y, w, h);
  ctx.fillStyle = '#b8a898'; ctx.fillRect(x, y + h - 4 * z, w, 4 * z);
  ctx.strokeStyle = '#8a7a60'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y, w, h);
  // Monitors
  for (let i = 0; i < 3; i++) {
    const mx = x + T + i * T * 2.2;
    ctx.fillStyle = '#0f172a'; ctx.fillRect(mx, y + 3 * z, T * 1.1, T * 0.75);
    ctx.fillStyle = '#1e3a5a'; ctx.fillRect(mx + 2 * z, y + 5 * z, T * 1.1 - 4 * z, T * 0.75 - 4 * z);
    ctx.fillStyle = 'rgba(100,180,255,0.4)';
    ctx.fillRect(mx + 3 * z, y + 7 * z, T * 0.7, 1.5 * z);
    ctx.fillRect(mx + 3 * z, y + 10 * z, T * 0.5, 1.5 * z);
  }
  // Nameplate
  ctx.fillStyle = '#c8a050'; ctx.fillRect(x + T * 3, y + h * 0.6, T * 2, 6 * z);
  ctx.fillStyle = '#f5f0e0'; ctx.font = `bold ${Math.max(8, 8 * z)}px sans-serif`;
  ctx.textAlign = 'center'; ctx.fillText('RECEPTION', x + T * 4, y + h * 0.6 + 5 * z); ctx.textAlign = 'left';
  // Bell
  ctx.font = `${Math.max(10, 10 * z)}px sans-serif`;
  ctx.fillText('🛎️', x + T * 6.5, y + h * 0.5);
}

// ─── Glass entrance doors ─────────────────────────────────────────────

export function drawGlassDoors(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const dw = T * 4, dh = T;
  // Opening (floor shows through)
  fillFloor(scene, ty, ty, tx, tx + 3, 'wood');
  // Door frame
  ctx.fillStyle = '#6a7a5a';
  ctx.fillRect(x, y, dw, 3 * z);
  ctx.fillRect(x, y + dh - 3 * z, dw, 3 * z);
  ctx.fillRect(x, y, 3 * z, dh);
  ctx.fillRect(x + dw - 3 * z, y, 3 * z, dh);
  ctx.fillRect(x + dw / 2 - 1.5 * z, y, 3 * z, dh);
  // Left door glass
  ctx.fillStyle = 'rgba(180,220,255,0.55)'; ctx.fillRect(x + 4 * z, y + 4 * z, dw / 2 - 7 * z, dh - 8 * z);
  // Right door glass
  ctx.fillRect(x + dw / 2 + 3 * z, y + 4 * z, dw / 2 - 7 * z, dh - 8 * z);
  // Reflection
  ctx.fillStyle = 'rgba(255,255,255,0.25)';
  ctx.fillRect(x + 5 * z, y + 5 * z, 4 * z, dh - 12 * z);
  ctx.fillRect(x + dw / 2 + 4 * z, y + 5 * z, 4 * z, dh - 12 * z);
  // Handle
  ctx.fillStyle = '#c8a850';
  ctx.fillRect(x + dw / 2 - 8 * z, y + dh / 2 - 2 * z, 5 * z, 4 * z);
  ctx.fillRect(x + dw / 2 + 3 * z, y + dh / 2 - 2 * z, 5 * z, 4 * z);
  // Label
  ctx.font = `bold ${Math.max(8, 8 * z)}px sans-serif`; ctx.fillStyle = '#4a5a3a';
  ctx.textAlign = 'center'; ctx.fillText('🚪 ENTRANCE', x + dw / 2, y - 6 * z); ctx.textAlign = 'left';
}

// ─── Reception lobby sofas/chairs in reception room ───────────────────
// (rendered via renderSpecialFurniture → Reception)
// We set Reception room floor to 'wood', draw reception desk in entrance,
// and add lobby chairs/plants in the Reception special room:
// This is handled by renderEntranceArea() + the Reception room furniture below.
