import type { PixelSceneState } from './pixelSceneState';
import { gs } from './pixelCoordinates';

export function renderActiveConnections(scene: PixelSceneState): void {
  const ctx = scene.ctx;
  const z = scene.zoom;
  const T = scene.T * z;

  scene.connections.forEach((conn) => {
    const fromDesk = scene.deskMap.get(conn.fromAgentId);
    if (!fromDesk) return;

    let toTx = 48, toTy = 3; // Default MCP Station in Entrance / Hub
    if (conn.targetType === 'super_agent') {
      toTx = 18; toTy = 13; // Executive HQ Lead desk
    } else if (conn.targetType === 'agent' && conn.toAgentId) {
      const toDesk = scene.deskMap.get(conn.toAgentId);
      if (toDesk) {
        toTx = toDesk.tx;
        toTy = toDesk.ty;
      }
    }

    const p1 = gs(scene, fromDesk.tx, fromDesk.ty);
    const p2 = gs(scene, toTx, toTy);

    const x1 = p1.x + T / 2;
    const y1 = p1.y + T / 2;
    const x2 = p2.x + T / 2;
    const y2 = p2.y + T / 2;

    ctx.save();
    ctx.strokeStyle = conn.color;
    ctx.lineWidth = Math.max(1.5, 2 * z);
    ctx.setLineDash([6 * z, 5 * z]);
    ctx.lineDashOffset = -scene.tick * 0.7;

    const midX = (x1 + x2) / 2;
    const midY = (y1 + y2) / 2 - 25 * z;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.quadraticCurveTo(midX, midY, x2, y2);
    ctx.stroke();

    // Traveling glowing particle
    const t = (scene.tick % 60) / 60;
    const qx = (1 - t) * (1 - t) * x1 + 2 * (1 - t) * t * midX + t * t * x2;
    const qy = (1 - t) * (1 - t) * y1 + 2 * (1 - t) * t * midY + t * t * y2;

    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.arc(qx, qy, 3.5 * z, 0, Math.PI * 2);
    ctx.fill();

    // Label badge
    if (conn.label) {
      ctx.setLineDash([]);
      ctx.font = `bold ${Math.max(8, 8 * z)}px sans-serif`;
      const tw = ctx.measureText(conn.label).width;
      const lx = midX - tw / 2 - 4 * z;
      const ly = midY - 6 * z;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.88)';
      ctx.strokeStyle = conn.color;
      ctx.lineWidth = 1;
      ctx.fillRect(lx, ly, tw + 8 * z, 12 * z);
      ctx.strokeRect(lx, ly, tw + 8 * z, 12 * z);
      ctx.fillStyle = '#f8fafc';
      ctx.fillText(conn.label, lx + 4 * z, ly + 9 * z);
    }
    ctx.restore();
  });
}


// ─── Office chair sprite ──────────────────────────────────────────────
// For dir='down': chair appears at bottom (south) of desk tile
// For dir='up':   chair appears at top (north) of desk tile
