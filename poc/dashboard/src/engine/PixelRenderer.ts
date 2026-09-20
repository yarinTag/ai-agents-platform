/**
 * PixelRenderer: 60 FPS HTML5 Canvas Pixel Art Engine for Virtual AI Agents Office.
 * Handles isometric projection, procedural pixel sprites, animation loops,
 * hierarchy connection links, delegation particle beams, and hit testing.
 * ZERO MOCKS: Driven directly by live Agent and Task models.
 */

import { Agent } from '../types/agent';
import { Task } from '../types/task';

export interface ViewportState {
  panX: number;
  panY: number;
  zoom: number;
}

export interface DeskPosition {
  agentId?: string;
  gridX: number;
  gridY: number;
  department: string;
  label: string;
}

export class PixelRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private animFrameId: number | null = null;
  private tick: number = 0;

  // Viewport
  public panX: number = 0;
  public panY: number = 0;
  public zoom: number = 1.0;

  // Data
  private agents: Agent[] = [];
  private tasks: Task[] = [];
  private hoveredAgentId: string | null = null;
  private selectedAgentId: string | null = null;
  private onSelectAgentCallback?: (agent: Agent) => void;

  // Isometric tile geometry
  private readonly tileW = 64;
  private readonly tileH = 32;

  // Dynamic desk assignments
  private deskMap: Map<string, { x: number; y: number }> = new Map();

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Could not get 2D canvas context');
    this.ctx = ctx;
    this.panX = canvas.width / 2;
    this.panY = 160;
  }

  public updateData(agents: Agent[], tasks: Task[]): void {
    this.agents = agents;
    this.tasks = tasks;
    this.recomputeDeskPositions();
  }

  public setOnSelectAgent(cb: (agent: Agent) => void): void {
    this.onSelectAgentCallback = cb;
  }

  public setSelectedAgent(agentId: string | null): void {
    this.selectedAgentId = agentId;
  }

  public resize(width: number, height: number): void {
    this.canvas.width = width;
    this.canvas.height = height;
  }

  public start(): void {
    if (this.animFrameId !== null) return;
    const loop = () => {
      this.tick++;
      this.render();
      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  public stop(): void {
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  // Convert isometric grid coordinates to screen pixel coordinates
  private gridToScreen(gx: number, gy: number): { x: number; y: number } {
    const sx = (gx - gy) * (this.tileW / 2) * this.zoom + this.panX;
    const sy = (gx + gy) * (this.tileH / 2) * this.zoom + this.panY;
    return { x: sx, y: sy };
  }

  // Convert screen coordinates back to grid coordinates (for hit testing)
  private screenToGrid(sx: number, sy: number): { gx: number; gy: number } {
    const adjX = (sx - this.panX) / (this.tileW / 2) / this.zoom;
    const adjY = (sy - this.panY) / (this.tileH / 2) / this.zoom;
    const gx = (adjX + adjY) / 2;
    const gy = (adjY - adjX) / 2;
    return { gx, gy };
  }

  private recomputeDeskPositions(): void {
    this.deskMap.clear();

    // Group agents by department or manager
    const managers = this.agents.filter(
      (a) =>
        (a.role_type || '').toUpperCase() === 'MANAGER' ||
        (a.role_type || '').toUpperCase() === 'ROOT_ORCHESTRATOR'
    );
    const workers = this.agents.filter(
      (a) =>
        (a.role_type || '').toUpperCase() !== 'MANAGER' &&
        (a.role_type || '').toUpperCase() !== 'ROOT_ORCHESTRATOR'
    );

    // Layout configuration:
    // Department pods in an isometric campus
    const pods: Record<string, { startGx: number; startGy: number }> = {
      Engineering: { startGx: 2, startGy: 2 },
      Architecture: { startGx: 8, startGy: 2 },
      'QA & Testing': { startGx: 2, startGy: 8 },
      'Research & Ops': { startGx: 8, startGy: 8 },
      General: { startGx: 5, startGy: 5 },
    };

    // 1. Position managers at pod center/head
    managers.forEach((m, idx) => {
      const dept = m.department || 'General';
      const pod = pods[dept] || { startGx: 5 + (idx % 3) * 3, startGy: 5 + Math.floor(idx / 3) * 3 };
      this.deskMap.set(m.id, { x: pod.startGx, y: pod.startGy });
    });

    // 2. Position workers around their respective managers or in their department pod
    const deptWorkerCounters: Record<string, number> = {};
    workers.forEach((w) => {
      let gx = 0;
      let gy = 0;

      if (w.parent_id && this.deskMap.has(w.parent_id)) {
        const parentPos = this.deskMap.get(w.parent_id)!;
        const count = deptWorkerCounters[w.parent_id] || 0;
        deptWorkerCounters[w.parent_id] = count + 1;

        // Position cluster: surrounding parent desk
        const offsets = [
          { dx: 1, dy: 0 },
          { dx: 0, dy: 1 },
          { dx: -1, dy: 0 },
          { dx: 0, dy: -1 },
          { dx: 1, dy: 1 },
          { dx: -1, dy: 1 },
        ];
        const off = offsets[count % offsets.length];
        gx = parentPos.x + off.dx;
        gy = parentPos.y + off.dy;
      } else {
        const dept = w.department || 'General';
        const pod = pods[dept] || pods.General;
        const count = deptWorkerCounters[dept] || 0;
        deptWorkerCounters[dept] = count + 1;

        gx = pod.startGx + 1 + (count % 3);
        gy = pod.startGy + 1 + Math.floor(count / 3);
      }

      this.deskMap.set(w.id, { x: gx, y: gy });
    });
  }

  public render(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    // Crisp pixel rendering settings
    ctx.imageSmoothingEnabled = false;

    // Clear background with soft office ambient color
    ctx.fillStyle = '#1e293b';
    ctx.fillRect(0, 0, w, h);

    // 1. Draw Isometric Floor Grid (12x12 Office Tiles)
    this.renderFloorGrid(12, 12);

    // 2. Draw Hierarchy Connections (Beams between managers & workers)
    this.renderHierarchyLinks();

    // 3. Draw Desks & Pixel Agents (Depth sorted back-to-front by gx + gy)
    this.renderDesksAndAgents();

    // 4. Draw HUD / Active Task Indicators
    this.renderOverlayHUD();
  }

  private renderFloorGrid(gridWidth: number, gridHeight: number): void {
    const ctx = this.ctx;

    for (let gx = 0; gx < gridWidth; gx++) {
      for (let gy = 0; gy < gridHeight; gy++) {
        const pt = this.gridToScreen(gx, gy);
        const w2 = (this.tileW / 2) * this.zoom;
        const h2 = (this.tileH / 2) * this.zoom;

        ctx.beginPath();
        ctx.moveTo(pt.x, pt.y);
        ctx.lineTo(pt.x + w2, pt.y + h2);
        ctx.lineTo(pt.x, pt.y + h2 * 2);
        ctx.lineTo(pt.x - w2, pt.y + h2);
        ctx.closePath();

        // Parquet checkerboard pattern
        const isAlternate = (gx + gy) % 2 === 0;
        ctx.fillStyle = isAlternate ? '#334155' : '#283548';
        ctx.fill();

        ctx.strokeStyle = '#1e293b';
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }
  }

  private renderHierarchyLinks(): void {
    const ctx = this.ctx;

    this.agents.forEach((agent) => {
      if (!agent.parent_id || !this.deskMap.has(agent.parent_id) || !this.deskMap.has(agent.id)) {
        return;
      }

      const pPos = this.deskMap.get(agent.parent_id)!;
      const cPos = this.deskMap.get(agent.id)!;

      const pScreen = this.gridToScreen(pPos.x, pPos.y);
      const cScreen = this.gridToScreen(cPos.x, cPos.y);

      // Check if there is an active subtask between parent and child
      const activeSubtask = this.tasks.find(
        (t) =>
          String(t.agent_id) === String(agent.id) &&
          t.assigned_by === agent.parent_id &&
          (t.status === 'running' || t.status === 'queued')
      );

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(pScreen.x, pScreen.y + 10 * this.zoom);
      ctx.lineTo(cScreen.x, cScreen.y + 10 * this.zoom);

      if (activeSubtask) {
        // Glowing active delegation line
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2 * this.zoom;
        ctx.setLineDash([4 * this.zoom, 4 * this.zoom]);
        ctx.lineDashOffset = -(this.tick % 30);
        ctx.stroke();

        // Animate traveling packet particle
        const t = (this.tick % 60) / 60;
        const particleX = pScreen.x + (cScreen.x - pScreen.x) * t;
        const particleY = pScreen.y + (cScreen.y - pScreen.y) * t + 10 * this.zoom;

        ctx.fillStyle = '#6ee7b7';
        ctx.beginPath();
        ctx.arc(particleX, particleY, 3 * this.zoom, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // Subtle dotted hierarchy link
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1 * this.zoom;
        ctx.setLineDash([3 * this.zoom, 3 * this.zoom]);
        ctx.stroke();
      }
      ctx.restore();
    });
  }

  private renderDesksAndAgents(): void {
    // Collect all renderables and sort by depth (gx + gy)
    const items: Array<{ agent: Agent; gx: number; gy: number }> = [];

    this.agents.forEach((agent) => {
      const pos = this.deskMap.get(agent.id);
      if (pos) {
        items.push({ agent, gx: pos.x, gy: pos.y });
      }
    });

    items.sort((a, b) => a.gx + a.gy - (b.gx + b.gy));

    items.forEach((item) => {
      this.drawDeskAndAgent(item.agent, item.gx, item.gy);
    });
  }

  private drawDeskAndAgent(agent: Agent, gx: number, gy: number): void {
    const ctx = this.ctx;
    const pt = this.gridToScreen(gx, gy);
    const z = this.zoom;

    const isHovered = this.hoveredAgentId === agent.id;
    const isSelected = this.selectedAgentId === agent.id;

    // Active task check
    const activeTask = this.tasks.find(
      (t) => String(t.agent_id) === String(agent.id) && (t.status === 'running' || t.status === 'queued')
    );
    const isWorking = !!activeTask;
    const role = (agent.role_type || 'WORKER').toUpperCase();
    const isManager = role === 'MANAGER' || role === 'ROOT_ORCHESTRATOR';

    ctx.save();
    ctx.translate(pt.x, pt.y);

    // 1. Draw Isometric Pixel Desk
    const deskW = 28 * z;
    const deskH = 14 * z;
    const deskDepth = 8 * z;

    // Desk shadow
    ctx.fillStyle = 'rgba(0, 0, 0, 0.25)';
    ctx.beginPath();
    ctx.ellipse(0, 8 * z, deskW * 0.7, deskH * 0.5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Desk base
    ctx.fillStyle = isWorking ? '#0f766e' : '#475569';
    ctx.fillRect(-deskW / 2, -deskH / 2, deskW, deskH);

    // Desk side shading
    ctx.fillStyle = '#334155';
    ctx.fillRect(-deskW / 2, deskH / 2, deskW, deskDepth);

    // Desk border
    ctx.strokeStyle = isSelected ? '#38bdf8' : isWorking ? '#10b981' : '#1e293b';
    ctx.lineWidth = isSelected ? 2 : 1;
    ctx.strokeRect(-deskW / 2, -deskH / 2, deskW, deskH + deskDepth);

    // 2. Laptop Monitor
    const monW = 12 * z;
    const monH = 9 * z;
    const monX = -monW / 2;
    const monY = -deskH / 2 - monH + 2 * z;

    ctx.fillStyle = '#0f172a';
    ctx.fillRect(monX, monY, monW, monH);

    // Glowing screen pixels
    if (isWorking) {
      ctx.fillStyle = '#10b981';
      ctx.fillRect(monX + 1 * z, monY + 1 * z, monW - 2 * z, monH - 2 * z);

      // Flickering code lines
      ctx.fillStyle = '#ecfdf5';
      const lineY = monY + 2 * z + (this.tick % 4);
      ctx.fillRect(monX + 2 * z, lineY, monW - 4 * z, 1 * z);

      // Rising code particles
      const pY = monY - ((this.tick * 0.8) % (15 * z));
      ctx.fillStyle = '#34d399';
      ctx.font = `${Math.max(6 * z, 8)}px monospace`;
      ctx.fillText('{ }', monX - 2 * z, pY);
    } else {
      // Idle screen
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(monX + 1 * z, monY + 1 * z, monW - 2 * z, monH - 2 * z);
      if (this.tick % 60 < 30) {
        ctx.fillStyle = '#64748b';
        ctx.fillRect(monX + 3 * z, monY + 4 * z, 2 * z, 1 * z);
      }
    }

    // 3. Pixel Agent Character
    // Subtle idle breathing animation
    const breath = Math.sin((this.tick + gx * 10) * 0.08) * 1.5 * z;
    const charY = -deskH / 2 - 12 * z + breath;

    // Body / Shirt
    let shirtColor = '#3b82f6'; // Worker default blue
    if (role === 'ROOT_ORCHESTRATOR') shirtColor = '#8b5cf6';
    else if (role === 'MANAGER') shirtColor = '#f59e0b';
    else if (role === 'SPECIALIST') shirtColor = '#ec4899';

    ctx.fillStyle = shirtColor;
    ctx.fillRect(-5 * z, charY + 5 * z, 10 * z, 7 * z);

    // Head
    ctx.fillStyle = '#fde047'; // Skin tone pixel
    ctx.fillRect(-4 * z, charY, 8 * z, 6 * z);

    // Eyes
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(-2 * z, charY + 2 * z, 1.5 * z, 1.5 * z);
    ctx.fillRect(1 * z, charY + 2 * z, 1.5 * z, 1.5 * z);

    // Manager / Root Crown or Badge
    if (role === 'ROOT_ORCHESTRATOR') {
      ctx.fillStyle = '#fbbf24';
      ctx.fillRect(-4 * z, charY - 3 * z, 8 * z, 2 * z);
      ctx.fillRect(-4 * z, charY - 4 * z, 2 * z, 1 * z);
      ctx.fillRect(-1 * z, charY - 5 * z, 2 * z, 2 * z);
      ctx.fillRect(2 * z, charY - 4 * z, 2 * z, 1 * z);
    } else if (role === 'MANAGER') {
      ctx.fillStyle = '#f59e0b';
      ctx.font = `${Math.max(7 * z, 9)}px sans-serif`;
      ctx.fillText('★', -3 * z, charY - 2 * z);
    }

    // Hands typing if working
    if (isWorking) {
      const handOff = (this.tick % 6 < 3 ? 1 : -1) * z;
      ctx.fillStyle = '#fde047';
      ctx.fillRect(-4 * z + handOff, -deskH / 2, 2 * z, 2 * z);
      ctx.fillRect(2 * z - handOff, -deskH / 2, 2 * z, 2 * z);
    }

    // 4. Name Tag & Status Bubble
    const label = agent.name.split(' ')[0];
    ctx.font = `bold ${Math.max(9 * z, 10)}px sans-serif`;
    const labelW = ctx.measureText(label).width;

    ctx.fillStyle = isSelected ? '#0284c7' : isWorking ? '#065f46' : 'rgba(15, 23, 42, 0.85)';
    ctx.strokeStyle = isSelected ? '#38bdf8' : isWorking ? '#34d399' : '#334155';
    ctx.lineWidth = 1;

    const bubbleX = -labelW / 2 - 4 * z;
    const bubbleY = charY - 14 * z;
    ctx.fillRect(bubbleX, bubbleY, labelW + 8 * z, 11 * z);
    ctx.strokeRect(bubbleX, bubbleY, labelW + 8 * z, 11 * z);

    ctx.fillStyle = '#ffffff';
    ctx.fillText(label, -labelW / 2, bubbleY + 8 * z);

    // Active Task Tag
    if (isWorking && activeTask) {
      ctx.fillStyle = '#10b981';
      ctx.beginPath();
      ctx.arc(bubbleX + labelW + 8 * z, bubbleY + 2 * z, 3 * z, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }

  private renderOverlayHUD(): void {
    const ctx = this.ctx;

    // Hover tooltip if hovering over an agent
    if (this.hoveredAgentId) {
      const agent = this.agents.find((a) => a.id === this.hoveredAgentId);
      const pos = this.deskMap.get(this.hoveredAgentId);
      if (agent && pos) {
        const pt = this.gridToScreen(pos.x, pos.y);
        const task = this.tasks.find(
          (t) => String(t.agent_id) === String(agent.id) && (t.status === 'running' || t.status === 'queued')
        );

        ctx.save();
        ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 1.5;

        const tipW = 200;
        const tipH = task ? 68 : 50;
        const tipX = Math.min(Math.max(pt.x - tipW / 2, 10), this.canvas.width - tipW - 10);
        const tipY = pt.y - 75 * this.zoom;

        ctx.fillRect(tipX, tipY, tipW, tipH);
        ctx.strokeRect(tipX, tipY, tipW, tipH);

        ctx.fillStyle = '#f8fafc';
        ctx.font = 'bold 12px sans-serif';
        ctx.fillText(agent.name, tipX + 10, tipY + 18);

        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px sans-serif';
        ctx.fillText(`Role: ${agent.role_type || 'WORKER'} | Dept: ${agent.department || 'Engineering'}`, tipX + 10, tipY + 34);

        if (task) {
          ctx.fillStyle = '#34d399';
          ctx.font = 'bold 10px sans-serif';
          const promptShort = task.prompt.length > 25 ? `${task.prompt.slice(0, 25)}...` : task.prompt;
          ctx.fillText(`⚡ Task: ${promptShort}`, tipX + 10, tipY + 52);
        } else {
          ctx.fillStyle = '#38bdf8';
          ctx.font = '10px sans-serif';
          ctx.fillText('Status: IDLE (Awaiting assignment)', tipX + 10, tipY + 46);
        }

        ctx.restore();
      }
    }
  }

  // Hit test on click
  public handleCanvasClick(screenX: number, screenY: number): void {
    const clickedAgent = this.findAgentAtScreen(screenX, screenY);
    if (clickedAgent) {
      this.selectedAgentId = clickedAgent.id;
      if (this.onSelectAgentCallback) {
        this.onSelectAgentCallback(clickedAgent);
      }
    }
  }

  public handleCanvasMouseMove(screenX: number, screenY: number): void {
    const hovered = this.findAgentAtScreen(screenX, screenY);
    this.hoveredAgentId = hovered ? hovered.id : null;
  }

  private findAgentAtScreen(sx: number, sy: number): Agent | null {
    // Check in reverse order (front-to-back visually)
    for (const agent of this.agents) {
      const pos = this.deskMap.get(agent.id);
      if (!pos) continue;

      const pt = this.gridToScreen(pos.x, pos.y);
      const radius = 24 * this.zoom;

      const dx = sx - pt.x;
      const dy = sy - (pt.y - 10 * this.zoom);

      if (dx * dx + dy * dy <= radius * radius) {
        return agent;
      }
    }
    return null;
  }
}
