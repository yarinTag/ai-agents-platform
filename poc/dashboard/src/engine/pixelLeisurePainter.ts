import type { PixelSceneState } from './pixelSceneState';
import { gs } from './pixelCoordinates';

export function drawCouch(scene: PixelSceneState, tx: number, ty: number, wTiles: number, hTiles: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const w = T * wTiles, h = T * hTiles;
  // Shadow
  ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.fillRect(x + 3 * z, y + 3 * z, w, h);
  // Body
  ctx.fillStyle = '#8b7b9e'; ctx.fillRect(x, y, w, h);
  // Backrest
  ctx.fillStyle = '#7a6a8e'; ctx.fillRect(x, y, w, h * 0.35);
  // Cushions
  ctx.fillStyle = '#9e8eb2';
  for (let i = 0; i < wTiles; i++) {
    ctx.fillRect(x + i * T + 3 * z, y + h * 0.38, T - 6 * z, h * 0.55);
  }
  ctx.strokeStyle = '#5a4a6e'; ctx.lineWidth = 1; ctx.strokeRect(x, y, w, h);
  // Armrests
  ctx.fillStyle = '#6a5a7e';
  ctx.fillRect(x, y, 5 * z, h);
  ctx.fillRect(x + w - 5 * z, y, 5 * z, h);
}

// ─── Armchair ────────────────────────────────────────────────────────

export function drawArmchair(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(x + 2 * z, y + 2 * z, T * 0.9, T * 0.9);
  ctx.fillStyle = '#9e8eb2'; ctx.fillRect(x, y, T * 0.9, T * 0.9);
  ctx.fillStyle = '#7a6a8e'; ctx.fillRect(x, y, T * 0.9, T * 0.25);
  ctx.fillStyle = '#b0a0c8'; ctx.fillRect(x + 4 * z, y + T * 0.28, T * 0.9 - 8 * z, T * 0.55);
  ctx.fillStyle = '#6a5a7e';
  ctx.fillRect(x, y, 4 * z, T * 0.9);
  ctx.fillRect(x + T * 0.9 - 4 * z, y, 4 * z, T * 0.9);
  ctx.strokeStyle = '#5a4a6e'; ctx.lineWidth = 1; ctx.strokeRect(x, y, T * 0.9, T * 0.9);
}

// ─── Coffee table ─────────────────────────────────────────────────────

export function drawCoffeeTable(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = 'rgba(0,0,0,0.15)'; ctx.fillRect(x + 2 * z, y + 2 * z, T * 2, T * 0.7);
  ctx.fillStyle = '#c4a870'; ctx.fillRect(x, y, T * 2, T * 0.7);
  ctx.strokeStyle = '#8a6a38'; ctx.lineWidth = 1.2; ctx.strokeRect(x, y, T * 2, T * 0.7);
  // Items on table
  ctx.fillStyle = '#a0784a'; ctx.fillRect(x + 4 * z, y + 3 * z, 10 * z, 6 * z); // book
  ctx.fillStyle = '#5a98c8';
  ctx.beginPath(); ctx.arc(x + T - 4 * z, y + T * 0.35, 5 * z, 0, Math.PI * 2); ctx.fill(); // mug
  ctx.fillStyle = '#3a7898';
  ctx.beginPath(); ctx.arc(x + T - 4 * z, y + T * 0.35, 3 * z, 0, Math.PI * 2); ctx.fill();
}

// ─── Wall TV ──────────────────────────────────────────────────────────

export function drawWallTV(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const tvW = T * 2, tvH = T * 0.7;
  ctx.fillStyle = '#111827'; ctx.fillRect(x, y + T * 0.15, tvW, tvH);
  ctx.strokeStyle = '#374151'; ctx.lineWidth = 1; ctx.strokeRect(x, y + T * 0.15, tvW, tvH);
  const screenHue = (scene.tick * 2) % 360;
  ctx.fillStyle = `hsl(${screenHue}, 50%, 20%)`;
  ctx.fillRect(x + 2 * z, y + T * 0.15 + 2 * z, tvW - 4 * z, tvH - 4 * z);
  // Screen glow lines
  ctx.fillStyle = 'rgba(255,255,255,0.1)';
  for (let i = 0; i < 3; i++) {
    ctx.fillRect(x + 3 * z, y + T * 0.2 + i * 5 * z, tvW - 6 * z, 1.5 * z);
  }
  // Stand
  ctx.fillStyle = '#374151'; ctx.fillRect(x + tvW / 2 - 4 * z, y + T * 0.85, 8 * z, 4 * z);
  ctx.fillRect(x + tvW / 2 - 8 * z, y + T * 0.89, 16 * z, 2 * z);
}

// ─── Wall clock ───────────────────────────────────────────────────────

export function drawWallClock(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const cx = x + T / 2, cy = y + T / 2, r = T * 0.42;
  ctx.fillStyle = '#f5f0e8'; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#5a4a3a'; ctx.lineWidth = 1.5; ctx.stroke();
  // Hour marks
  ctx.strokeStyle = '#2a1a0a'; ctx.lineWidth = 1;
  for (let i = 0; i < 12; i++) {
    const ang = (i / 12) * Math.PI * 2 - Math.PI / 2;
    const inner = r * 0.8, outer = r * 0.92;
    ctx.beginPath();
    ctx.moveTo(cx + Math.cos(ang) * inner, cy + Math.sin(ang) * inner);
    ctx.lineTo(cx + Math.cos(ang) * outer, cy + Math.sin(ang) * outer);
    ctx.stroke();
  }
  // Hands (animated)
  const now = new Date();
  const sec = now.getSeconds() + now.getMilliseconds() / 1000;
  const min = now.getMinutes() + sec / 60;
  const hr = (now.getHours() % 12) + min / 60;
  const handColor = '#1a0a0a';
  const drawHand = (angle: number, length: number, width: number) => {
    const a = angle - Math.PI / 2;
    ctx.strokeStyle = handColor; ctx.lineWidth = width;
    ctx.beginPath(); ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(a) * length, cy + Math.sin(a) * length);
    ctx.stroke();
  };
  drawHand((hr / 12) * Math.PI * 2, r * 0.55, 1.5);
  drawHand((min / 60) * Math.PI * 2, r * 0.72, 1);
  drawHand((sec / 60) * Math.PI * 2, r * 0.8, 0.5);
  // Center dot
  ctx.fillStyle = '#1a0a0a'; ctx.beginPath(); ctx.arc(cx, cy, 2 * z, 0, Math.PI * 2); ctx.fill();
}

// ─── Plant ────────────────────────────────────────────────────────────

export function drawPlant(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const cx = x + T / 2, cy = y + T * 0.55;
  // Pot
  ctx.fillStyle = '#b85a30'; ctx.fillRect(cx - 6 * z, cy - 2 * z, 12 * z, 10 * z);
  ctx.fillStyle = '#8a3a18'; ctx.fillRect(cx - 7 * z, cy - 4 * z, 14 * z, 3 * z);
  ctx.strokeStyle = '#6a2a10'; ctx.lineWidth = 0.8; ctx.strokeRect(cx - 6 * z, cy - 2 * z, 12 * z, 10 * z);
  // Soil
  ctx.fillStyle = '#4a3020'; ctx.fillRect(cx - 5 * z, cy - 1 * z, 10 * z, 3 * z);
  // Leaves
  ctx.fillStyle = '#2d8a40';
  ctx.beginPath(); ctx.arc(cx, cy - 10 * z, 8 * z, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#248a38';
  ctx.beginPath(); ctx.arc(cx - 5 * z, cy - 7 * z, 5 * z, 0, Math.PI * 2); ctx.fill();
  ctx.beginPath(); ctx.arc(cx + 5 * z, cy - 7 * z, 5 * z, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,0.12)';
  ctx.beginPath(); ctx.arc(cx - 2 * z, cy - 12 * z, 3 * z, 0, Math.PI * 2); ctx.fill();
}

// ─── Ping pong table ──────────────────────────────────────────────────

export function drawPingPongTable(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const tw = T * 6, th = T * 3;
  ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.fillRect(x + 3 * z, y + 3 * z, tw, th);
  ctx.fillStyle = '#228b55'; ctx.fillRect(x, y, tw, th);
  ctx.strokeStyle = '#0f5c32'; ctx.lineWidth = 1; ctx.strokeRect(x, y, tw, th);
  // White lines
  ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5;
  ctx.strokeRect(x + 2 * z, y + 2 * z, tw - 4 * z, th - 4 * z);
  ctx.beginPath(); ctx.moveTo(x + tw / 2, y); ctx.lineTo(x + tw / 2, y + th); ctx.stroke();
  // Net
  ctx.fillStyle = '#eee'; ctx.fillRect(x + tw / 2 - 1 * z, y - 4 * z, 2 * z, th + 8 * z);
  // Paddles
  ctx.fillStyle = '#e04040'; ctx.beginPath(); ctx.ellipse(x + 8 * z, y + th / 2, 5 * z, 4 * z, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#4040e0'; ctx.beginPath(); ctx.ellipse(x + tw - 8 * z, y + th / 2, 5 * z, 4 * z, 0, 0, Math.PI * 2); ctx.fill();
  // Animated ball
  const bt = (scene.tick % 80) / 80;
  const bx = x + 8 * z + (tw - 16 * z) * bt;
  const barc = -Math.abs(Math.sin(bt * Math.PI)) * 10 * z;
  ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(bx, y + th / 2 + barc, 3 * z, 0, Math.PI * 2); ctx.fill();
}

// ─── Arcade machine ───────────────────────────────────────────────────

export function drawArcadeMachine(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = '#1a1a2e'; ctx.fillRect(x, y, T * 0.85, T);
  ctx.strokeStyle = '#e91e63'; ctx.lineWidth = 1; ctx.strokeRect(x, y, T * 0.85, T);
  ctx.fillStyle = '#000'; ctx.fillRect(x + 2 * z, y + 4 * z, T * 0.85 - 4 * z, T * 0.45);
  const gh = (scene.tick * 4) % 360;
  ctx.fillStyle = `hsl(${gh},80%,45%)`; ctx.fillRect(x + 3 * z, y + 5 * z, T * 0.85 - 6 * z, T * 0.45 - 2 * z);
  ctx.fillStyle = '#4a4a4a'; ctx.beginPath(); ctx.arc(x + T * 0.35, y + T * 0.7, 4 * z, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#dc2626'; ctx.beginPath(); ctx.arc(x + T * 0.65, y + T * 0.75, 3 * z, 0, Math.PI * 2); ctx.fill();
}

// ─── Bean bag ─────────────────────────────────────────────────────────

export function drawBeanBag(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  const colors = ['#7c3aed','#0ea5e9','#ef4444','#10b981','#f59e0b'];
  const c = colors[(tx + ty) % 5];
  ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.beginPath(); ctx.ellipse(x + T / 2 + 2 * z, y + T / 2 + 2 * z, T * 0.42, T * 0.35, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = c; ctx.beginPath(); ctx.ellipse(x + T / 2, y + T / 2, T * 0.42, T * 0.35, 0, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = 'rgba(0,0,0,0.2)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.18)';
  ctx.beginPath(); ctx.ellipse(x + T / 2 - 4 * z, y + T / 2 - 5 * z, T * 0.15, T * 0.12, -0.5, 0, Math.PI * 2); ctx.fill();
}

// ─── Snack/drink table ───────────────────────────────────────────────

export function drawSnackTable(scene: PixelSceneState, tx: number, ty: number): void {
  const ctx = scene.ctx;
  const T = scene.T * scene.zoom;
  const { x, y } = gs(scene, tx, ty);
  const z = scene.zoom;
  ctx.fillStyle = '#d4c5a0'; ctx.fillRect(x, y, T * 2, T * 0.8);
  ctx.strokeStyle = '#8c7a5a'; ctx.lineWidth = 1; ctx.strokeRect(x, y, T * 2, T * 0.8);
  // Bottles / cans
  ctx.fillStyle = '#e84040'; ctx.beginPath(); ctx.ellipse(x + T * 0.35, y + T * 0.4, 4 * z, 6 * z, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#40a0e8'; ctx.beginPath(); ctx.ellipse(x + T * 0.8, y + T * 0.4, 4 * z, 6 * z, 0, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = '#48c854'; ctx.beginPath(); ctx.ellipse(x + T * 1.4, y + T * 0.4, 4 * z, 6 * z, 0, 0, Math.PI * 2); ctx.fill();
}

// ─── Conference table ─────────────────────────────────────────────────
