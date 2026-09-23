/**
 * PixelRenderer — Top-Down 2D RPG Office Engine (v4)
 *
 * Rendering style: flat top-down pixel-art (RPG Maker interior style).
 * No isometric projection. Straight overhead view.
 *
 * Layout (in tile units, T=18px):
 *
 *   ┌────────────────────────────────────────────────────┐
 *   │           RECEPTION / ENTRANCE  (wood floor)        │
 *   ├──────┬───┬──────┬───┬──────┬───┬──────────────────┤
 *   │MKTG  │ c │EXEC  │ c │ENG   │ c │  RECEPTION/LOBBY │
 *   ├──────┤ o ├──────┤ o ├──────┤ o ├──────────────────┤
 *   │EMAIL │ r │LOUNGE│ r │DELVRY│ r │   BREAK ROOM     │
 *   ├──────┤ r ├──────┤ r ├──────┤ r ├──────────────────┤
 *   │OPS   │ i │SALES │ i │CONF  │ i │   KITCHEN        │
 *   └──────┴───┴──────┴───┴──────┴───┴──────────────────┘
 *
 * Building size: 56w × 46h tiles
 */

import { Agent } from '../types/agent';
import { Task } from '../types/task';

// ─── Palette ──────────────────────────────────────────────────────────────────
const P = {
  EXTERIOR:     '#1a1f2e',  // dark outside
  WALL:         '#d4c9a8',  // cream/tan wall fill
  WALL_DARK:    '#a89878',  // wall shadow (south edge of wall rows)
  WALL_OUTLINE: '#6b5c3e',  // dark outline around walls/rooms
  FLOOR_GRAY1:  '#c5c5bd',  // main office floor tile (even)
  FLOOR_GRAY2:  '#bdbdb5',  // main office floor tile (odd)
  FLOOR_WOOD1:  '#c4936a',  // warm wood floor (even)
  FLOOR_WOOD2:  '#b7845d',  // warm wood floor (odd)
  FLOOR_HALL1:  '#b8b8b0',  // corridor tile (even)
  FLOOR_HALL2:  '#b0b0a8',  // corridor tile (odd)
  FLOOR_CARPET1:'#c6b89a',  // lounge carpet (even)
  FLOOR_CARPET2:'#baaD8e',  // lounge carpet (odd)
  FLOOR_TILE1:  '#e0ddd6',  // kitchen tile (even)
  FLOOR_TILE2:  '#d4d1ca',  // kitchen tile (odd)
  FLOOR_BLUE1:  '#c0ccd8',  // conference (even)
  FLOOR_BLUE2:  '#b8c4d0',  // conference (odd)
  DOOR:         '#7a5230',  // door frame
  DOOR_FILL:    '#5c3d20',  // door
  GLASS:        '#a8c8e8',  // glass (entrance doors)
  GROUT:        '#989890',  // floor tile grout line
};

// ─── Grid layout constants ────────────────────────────────────────────────────
// Building: 56 tiles wide × 46 tiles tall

// Horizontal Y positions:
// 0: Top wall
// 1..5: Entrance (wood)
// 6: H-wall (with door openings)
// 7..9: H-Corridor 0
// 10: H-wall (with room doors)
// 11..18: Room Row 1
// 19: H-wall
// 20..22: H-Corridor 1
// 23: H-wall
// 24..31: Room Row 2
// 32: H-wall
// 33..35: H-Corridor 2
// 36: H-wall
// 37..44: Room Row 3
// 45: Bottom wall

// Vertical X positions:
// 0: Left outer wall
// 1..10: Col1 rooms (10 wide)
// 11: V-wall
// 12..13: V-Corridor 1 (2 wide)
// 14: V-wall
// 15..24: Col2 rooms (10 wide)
// 25: V-wall
// 26..27: V-Corridor 2 (2 wide)
// 28: V-wall
// 29..38: Col3 rooms (10 wide)
// 39: V-wall
// 40..41: V-Corridor 3 (2 wide)
// 42: V-wall
// 43..55: Col4 rooms (13 wide)

const BW = 56; // building width in tiles
const BH = 46; // building height in tiles

// Y zones
const ENT_Y   = { start: 1,  end: 5  }; // entrance
const HCOR0_Y = { start: 7,  end: 9  }; // h-corridor 0
const ROW1_Y  = { start: 11, end: 18 }; // room row 1
const HCOR1_Y = { start: 20, end: 22 }; // h-corridor 1
const ROW2_Y  = { start: 24, end: 31 }; // room row 2
const HCOR2_Y = { start: 33, end: 35 }; // h-corridor 2
const ROW3_Y  = { start: 37, end: 44 }; // room row 3

// X zones
const COL1_X  = { start: 1,  end: 10 };
const VCOR1_X = { start: 12, end: 13 };
const COL2_X  = { start: 15, end: 24 };
const VCOR2_X = { start: 26, end: 27 };
const COL3_X  = { start: 29, end: 38 };
const VCOR3_X = { start: 40, end: 41 };
const COL4_X  = { start: 43, end: 55 };

// Room definitions [label, xStart, xEnd, yStart, yEnd, floorType, accentColor]
interface RoomDef {
  key: string; label: string; icon: string; accent: string;
  x: number; y: number; w: number; h: number;
  floor: 'gray' | 'wood' | 'hall' | 'carpet' | 'tile' | 'blue';
  // Desk positions (relative to room top-left tile)
  desks: Array<{ dx: number; dy: number; dir: 'up' | 'down' | 'left' | 'right' }>;
}

// Standard 6-desk layout: 3 columns × 2 rows
// Col positions: dx = 1, 4, 7 (evenly spaced in 10-tile wide rooms)
// Row 1 (dy=1): near north wall, agent sits south → dir='down'
// Row 2 (dy=5): near center, agent sits north → dir='up'
const D6: RoomDef['desks'] = [
  { dx: 1, dy: 1, dir: 'down' }, { dx: 4, dy: 1, dir: 'down' }, { dx: 7, dy: 1, dir: 'down' },
  { dx: 1, dy: 5, dir: 'up'   }, { dx: 4, dy: 5, dir: 'up'   }, { dx: 7, dy: 5, dir: 'up'   },
];

const ROOMS: RoomDef[] = [
  // ROW 1
  {
    key: 'Marketing', label: 'MARKETING', icon: '📢', accent: '#e05070',
    x: COL1_X.start, y: ROW1_Y.start, w: COL1_X.end - COL1_X.start + 1, h: ROW1_Y.end - ROW1_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Executive HQ', label: 'EXEC HQ', icon: '⚡', accent: '#8b5cf6',
    x: COL2_X.start, y: ROW1_Y.start, w: COL2_X.end - COL2_X.start + 1, h: ROW1_Y.end - ROW1_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Engineering', label: 'ENGINEERING', icon: '💻', accent: '#3b82f6',
    x: COL3_X.start, y: ROW1_Y.start, w: COL3_X.end - COL3_X.start + 1, h: ROW1_Y.end - ROW1_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Reception', label: 'RECEPTION', icon: '🛎️', accent: '#f59e0b',
    x: COL4_X.start, y: ROW1_Y.start, w: COL4_X.end - COL4_X.start + 1, h: ROW1_Y.end - ROW1_Y.start + 1,
    floor: 'wood', desks: [],
  },
  // ROW 2
  {
    key: 'Emails', label: 'EMAILS', icon: '📬', accent: '#10b981',
    x: COL1_X.start, y: ROW2_Y.start, w: COL1_X.end - COL1_X.start + 1, h: ROW2_Y.end - ROW2_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Lounge', label: 'LOUNGE', icon: '🛋️', accent: '#7c3aed',
    x: COL2_X.start, y: ROW2_Y.start, w: COL2_X.end - COL2_X.start + 1, h: ROW2_Y.end - ROW2_Y.start + 1,
    floor: 'carpet', desks: [],
  },
  {
    key: 'Delivery', label: 'DELIVERY & QA', icon: '🚀', accent: '#0ea5e9',
    x: COL3_X.start, y: ROW2_Y.start, w: COL3_X.end - COL3_X.start + 1, h: ROW2_Y.end - ROW2_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Break Room', label: 'BREAK ROOM', icon: '🏓', accent: '#14b8a6',
    x: COL4_X.start, y: ROW2_Y.start, w: COL4_X.end - COL4_X.start + 1, h: ROW2_Y.end - ROW2_Y.start + 1,
    floor: 'gray', desks: [],
  },
  // ROW 3
  {
    key: 'Operations', label: 'OPERATIONS', icon: '⚙️', accent: '#6366f1',
    x: COL1_X.start, y: ROW3_Y.start, w: COL1_X.end - COL1_X.start + 1, h: ROW3_Y.end - ROW3_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Sales', label: 'SALES', icon: '💼', accent: '#f59e0b',
    x: COL2_X.start, y: ROW3_Y.start, w: COL2_X.end - COL2_X.start + 1, h: ROW3_Y.end - ROW3_Y.start + 1,
    floor: 'gray', desks: [...D6],
  },
  {
    key: 'Conference', label: 'CONFERENCE', icon: '📊', accent: '#6366f1',
    x: COL3_X.start, y: ROW3_Y.start, w: COL3_X.end - COL3_X.start + 1, h: ROW3_Y.end - ROW3_Y.start + 1,
    floor: 'blue', desks: [],
  },
  {
    key: 'Kitchen', label: 'KITCHEN', icon: '🍽️', accent: '#f97316',
    x: COL4_X.start, y: ROW3_Y.start, w: COL4_X.end - COL4_X.start + 1, h: ROW3_Y.end - ROW3_Y.start + 1,
    floor: 'tile', desks: [],
  },
];

// ─── Agent walk animation ─────────────────────────────────────────────────────
interface WalkAnim {
  agentId: string; managerId: string;
  fromX: number; fromY: number; toX: number; toY: number;
  progress: number; phase: 'walking' | 'delivering' | 'returning';
  deliverTick: number;
}

// ─── Character palette ────────────────────────────────────────────────────────
const SHIRT_COLORS = [
  '#e74c6a', '#3b82f6', '#10b981', '#f59e0b',
  '#8b5cf6', '#0ea5e9', '#ef4444', '#14b8a6',
];
const HAIR_COLORS = ['#2c1a0e', '#5c3a1e', '#c4a265', '#8b7355', '#1a1a1a', '#a0522d'];
const SKIN_TONES  = ['#f5cba7', '#e8a87c', '#d4845a', '#c46a3a'];

// ════════════════════════════════════════════════════════════════════════════
export class PixelRenderer {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private animFrameId: number | null = null;
  private tick: number = 0;

  public panX: number = 0;
  public panY: number = 0;
  public zoom: number = 1.0;

  private agents: Agent[] = [];
  private tasks: Task[] = [];
  private hoveredAgentId: string | null = null;
  private selectedAgentId: string | null = null;
  private onSelectAgentCallback?: (agent: Agent) => void;

  private readonly T = 18; // base tile size in pixels

  private deskMap: Map<string, {
    tx: number;
    ty: number;
    deskIdx: number;
    roomKey: string;
    dir: string;
    isAtDesk: boolean;
    activity?: string;
  }> = new Map();
  private walkAnims: Map<string, WalkAnim> = new Map();
  private prevTaskStatuses: Map<string, string> = new Map();

  // Character visual stable assignments
  private charColors: Map<string, { shirt: string; hair: string; skin: string }> = new Map();

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('No 2D context');
    this.ctx = ctx;
    ctx.imageSmoothingEnabled = false;
    this.panX = 30;
    this.panY = 30;
  }

  public updateData(agents: Agent[], tasks: Task[]): void {
    this.agents = agents;
    this.tasks = tasks;
    this.assignDeskPositions();
    this.detectTaskCompletions();
    this.assignCharColors();
  }
  public setOnSelectAgent(cb: (a: Agent) => void): void { this.onSelectAgentCallback = cb; }
  public setSelectedAgent(id: string | null): void { this.selectedAgentId = id; }
  public resize(w: number, h: number): void { this.canvas.width = w; this.canvas.height = h; }

  public start(): void {
    if (this.animFrameId !== null) return;
    const loop = () => { this.tick++; this.render(); this.animFrameId = requestAnimationFrame(loop); };
    this.animFrameId = requestAnimationFrame(loop);
  }
  public stop(): void {
    if (this.animFrameId !== null) { cancelAnimationFrame(this.animFrameId); this.animFrameId = null; }
  }

  // ─── Coordinate helpers ──────────────────────────────────────────────────
  private gs(tx: number, ty: number): { x: number; y: number } {
    return { x: tx * this.T * this.zoom + this.panX, y: ty * this.T * this.zoom + this.panY };
  }

  private px(n: number): number { return n * this.zoom; }  // scale a pixel value by zoom

  public handleCanvasClick(sx: number, sy: number): void {
    const a = this.findAgentAt(sx, sy);
    if (a) { this.selectedAgentId = a.id; this.onSelectAgentCallback?.(a); }
  }
  public handleCanvasMouseMove(sx: number, sy: number): void {
    const h = this.findAgentAt(sx, sy);
    this.hoveredAgentId = h ? h.id : null;
  }

  private findAgentAt(sx: number, sy: number): Agent | null {
    const T = this.T * this.zoom;
    for (const a of this.agents) {
      const pos = this.deskMap.get(a.id);
      if (!pos) continue;
      const pt = this.gs(pos.tx, pos.ty);
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
  private detectTaskCompletions(): void {
    this.tasks.forEach((task) => {
      const prev = this.prevTaskStatuses.get(String(task.id));
      const curr = task.status;
      if ((prev === 'running' || prev === 'queued') &&
          ['done', 'completed', 'success', 'finished'].includes(curr)) {
        const agentId = String(task.agent_id);
        const agent = this.agents.find((a) => String(a.id) === agentId);
        if (agent && agent.parent_id && !this.walkAnims.has(agentId)) {
          const aPos = this.deskMap.get(agentId);
          const mPos = this.deskMap.get(String(agent.parent_id));
          if (aPos && mPos) {
            this.walkAnims.set(agentId, {
              agentId, managerId: String(agent.parent_id),
              fromX: aPos.tx, fromY: aPos.ty, toX: mPos.tx, toY: mPos.ty,
              progress: 0, phase: 'walking', deliverTick: 0,
            });
          }
        }
      }
      this.prevTaskStatuses.set(String(task.id), curr);
    });
  }

  private tickWalkAnims(): void {
    const del: string[] = [];
    this.walkAnims.forEach((a) => {
      if (a.phase === 'walking') {
        a.progress += 0.01;
        if (a.progress >= 1) { a.progress = 1; a.phase = 'delivering'; a.deliverTick = this.tick; }
      } else if (a.phase === 'delivering') {
        if (this.tick - a.deliverTick > 100) { a.phase = 'returning'; a.progress = 1; }
      } else {
        a.progress -= 0.015;
        if (a.progress <= 0) del.push(a.agentId);
      }
    });
    del.forEach((id) => this.walkAnims.delete(id));
  }

  private isAgentWorking(agent: Agent): boolean {
    const hasActiveTask = this.tasks.some(
      (t) => String(t.agent_id) === String(agent.id) &&
        (t.status === 'running' || t.status === 'queued' || t.status === 'in_progress')
    );
    if (hasActiveTask) return true;

    const st = (agent.status || '').toLowerCase();
    if (st === 'running' || st === 'thinking' || st === 'reviewing' || st === 'active') {
      return true;
    }

    if (agent.current_task && agent.current_task.trim() !== '') {
      return true;
    }

    return false;
  }

  private isManagerOrLead(agent: Agent): boolean {
    const r = (agent.role_type || '').toUpperCase();
    if (r === 'ROOT_ORCHESTRATOR' || r === 'MANAGER' || r === 'LEAD') return true;
    const id = agent.id.toLowerCase();
    if (id.includes('chief') || id.includes('lead') || id.includes('manager') || id.includes('orchestrator')) return true;
    const name = (agent.name || '').toLowerCase();
    if (name.includes('lead') || name.includes('manager') || name.includes('chief')) return true;
    return false;
  }

  private getAgentDepartmentRoom(agent: Agent): string {
    const dept = (agent.department || '').toLowerCase();
    const role = (agent.role_type || '').toUpperCase();
    const id = agent.id.toLowerCase();

    if (dept.includes('exec') || dept.includes('hq') || id === 'chief-orchestrator' || role === 'ROOT_ORCHESTRATOR') {
      return 'Executive HQ';
    }
    for (const r of ROOMS) {
      if (['Lounge', 'Break Room', 'Conference', 'Kitchen', 'Reception'].includes(r.key)) continue;
      const rk = r.key.toLowerCase();
      if (dept.includes(rk) || rk.includes(dept)) return r.key;
    }
    if (dept.includes('finance')) return 'Operations';
    if (dept.includes('qa') || dept.includes('testing')) return 'Delivery';
    return 'Engineering';
  }

  private getRoomDesks(room: RoomDef): Array<{ dx: number; dy: number; dir: 'up' | 'down' | 'left' | 'right'; isManager: boolean }> {
    const list: Array<{ dx: number; dy: number; dir: 'up' | 'down' | 'left' | 'right'; isManager: boolean }> =
      room.desks.map((d, idx) => ({ ...d, isManager: idx === 0 }));

    let workingInRoom = 0;
    this.deskMap.forEach((pos) => {
      if (pos.roomKey === room.key && pos.isAtDesk) {
        workingInRoom++;
      }
    });

    if (workingInRoom > room.desks.length) {
      for (let i = room.desks.length; i < workingInRoom; i++) {
        const extraIdx = i - room.desks.length;
        const colIdx = extraIdx % 3;
        const rowIdx = Math.floor(extraIdx / 3);
        const dx = colIdx === 0 ? 1 : colIdx === 1 ? 4 : 7;
        const dy = 3 + rowIdx * 2;
        list.push({ dx, dy, dir: 'down', isManager: false });
      }
    }
    return list;
  }

  private assignDeskPositions(): void {
    this.deskMap.clear();

    const loungeRoom = ROOMS.find((r) => r.key === 'Lounge')!;
    const breakRoom  = ROOMS.find((r) => r.key === 'Break Room')!;
    const confRoom   = ROOMS.find((r) => r.key === 'Conference')!;

    // Spots around Conference Table for non-working managers and leads
    const confSpots: Array<{ dx: number; dy: number; dir: 'up' | 'down'; activity: string }> = [
      { dx: 2,   dy: 1.2, dir: 'down', activity: '📊 Strategy Meeting' },
      { dx: 5,   dy: 1.2, dir: 'down', activity: '📊 Leadership Alignment' },
      { dx: 8,   dy: 1.2, dir: 'down', activity: '📊 Roadmap Planning' },
      { dx: 2,   dy: 6.2, dir: 'up',   activity: '📊 Performance Review' },
      { dx: 5,   dy: 6.2, dir: 'up',   activity: '📊 Executive Sync' },
      { dx: 8,   dy: 6.2, dir: 'up',   activity: '📊 Architecture Discussion' },
      { dx: 1,   dy: 3.5, dir: 'down', activity: '📊 Resource Planning' },
      { dx: 8.8, dy: 3.5, dir: 'down', activity: '📊 Sprint Goals' },
    ];

    // Spots in Lounge for non-working workers
    const loungeSpots: Array<{ dx: number; dy: number; dir: 'up' | 'down'; activity: string }> = [
      { dx: 2,   dy: 1.5, dir: 'down', activity: '🛋️ Resting on Couch' },
      { dx: 3.5, dy: 1.5, dir: 'down', activity: '🛋️ Resting on Couch' },
      { dx: 5.5, dy: 1.5, dir: 'down', activity: '☕ In Armchair' },
      { dx: 8,   dy: 1.5, dir: 'down', activity: '☕ In Armchair' },
      { dx: 3,   dy: 5,   dir: 'up',   activity: '📖 Coffee Table' },
      { dx: 6,   dy: 5,   dir: 'up',   activity: '📺 Watching Tech News' },
      { dx: 8,   dy: 5,   dir: 'up',   activity: '🌿 Relaxing by Plant' },
      { dx: 5,   dy: 6.5, dir: 'up',   activity: '💬 Team Chat' },
    ];

    // Spots in Break Room for non-working workers
    const breakSpots: Array<{ dx: number; dy: number; dir: 'up' | 'down'; activity: string }> = [
      { dx: 1.5, dy: 2.2, dir: 'down', activity: '🏓 Playing Ping Pong' },
      { dx: 6.5, dy: 2.2, dir: 'down', activity: '🏓 Playing Ping Pong' },
      { dx: 9,   dy: 2.2, dir: 'up',   activity: '🕹️ Arcade High Score' },
      { dx: 11,  dy: 2.2, dir: 'up',   activity: '🕹️ Retro Gaming' },
      { dx: 1.5, dy: 6,   dir: 'up',   activity: '🛋️ Bean Bag Chill' },
      { dx: 3.5, dy: 6,   dir: 'up',   activity: '🛋️ Bean Bag Chill' },
      { dx: 10,  dy: 6,   dir: 'up',   activity: '🛋️ Bean Bag Chill' },
      { dx: 8.5, dy: 5,   dir: 'down', activity: '🥤 Coffee & Snack' },
      { dx: 4,   dy: 4.5, dir: 'up',   activity: '👀 Watching Ping Pong' },
      { dx: 11.5,dy: 5,   dir: 'down', activity: '🍿 Break Room Snacks' },
    ];

    let confIdx = 0;
    let loungeIdx = 0;
    let breakIdx = 0;

    const deptWorkingCounts: Record<string, number> = {};

    this.agents.forEach((agent) => {
      const working = this.isAgentWorking(agent);

      if (!working) {
        // NON-WORKING AGENT
        if (this.isManagerOrLead(agent)) {
          // Managers & Leads -> Conference Room
          const spot = confSpots[confIdx % confSpots.length];
          const extraOffset = Math.floor(confIdx / confSpots.length) * 0.5;
          this.deskMap.set(agent.id, {
            tx: confRoom.x + spot.dx + extraOffset,
            ty: confRoom.y + spot.dy,
            deskIdx: confIdx,
            roomKey: 'Conference',
            dir: spot.dir,
            isAtDesk: false,
            activity: spot.activity,
          });
          confIdx++;
        } else {
          // Regular Agents -> Break Room or Lounge (alternating)
          if ((loungeIdx + breakIdx) % 2 === 0) {
            // Lounge
            const spot = loungeSpots[loungeIdx % loungeSpots.length];
            const extraOffset = Math.floor(loungeIdx / loungeSpots.length) * 0.5;
            this.deskMap.set(agent.id, {
              tx: loungeRoom.x + spot.dx + extraOffset,
              ty: loungeRoom.y + spot.dy,
              deskIdx: loungeIdx,
              roomKey: 'Lounge',
              dir: spot.dir,
              isAtDesk: false,
              activity: spot.activity,
            });
            loungeIdx++;
          } else {
            // Break Room
            const spot = breakSpots[breakIdx % breakSpots.length];
            const extraOffset = Math.floor(breakIdx / breakSpots.length) * 0.5;
            this.deskMap.set(agent.id, {
              tx: breakRoom.x + spot.dx + extraOffset,
              ty: breakRoom.y + spot.dy,
              deskIdx: breakIdx,
              roomKey: 'Break Room',
              dir: spot.dir,
              isAtDesk: false,
              activity: spot.activity,
            });
            breakIdx++;
          }
        }
      } else {
        // WORKING AGENT -> Desk in their department room
        const deptKey = this.getAgentDepartmentRoom(agent);
        const room = ROOMS.find((r) => r.key === deptKey) || ROOMS.find((r) => r.key === 'Engineering')!;
        const count = deptWorkingCounts[deptKey] || 0;
        deptWorkingCounts[deptKey] = count + 1;

        if (count < room.desks.length) {
          const desk = room.desks[count];
          this.deskMap.set(agent.id, {
            tx: room.x + desk.dx,
            ty: room.y + desk.dy,
            deskIdx: count,
            roomKey: room.key,
            dir: desk.dir,
            isAtDesk: true,
          });
        } else {
          // Dynamically add extra desk position in row 3
          const extraIdx = count - room.desks.length;
          const colIdx = extraIdx % 3;
          const rowIdx = Math.floor(extraIdx / 3);
          const dx = colIdx === 0 ? 1 : colIdx === 1 ? 4 : 7;
          const dy = 3 + rowIdx * 2;
          this.deskMap.set(agent.id, {
            tx: room.x + dx,
            ty: room.y + dy,
            deskIdx: count,
            roomKey: room.key,
            dir: 'down',
            isAtDesk: true,
          });
        }
      }
    });
  }

  private assignCharColors(): void {
    this.agents.forEach((a, i) => {
      if (!this.charColors.has(a.id)) {
        this.charColors.set(a.id, {
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
  public render(): void {
    const ctx = this.ctx;
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = P.EXTERIOR;
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    this.tickWalkAnims();

    this.renderBuildingShell();    // 1. Cream wall fill for whole building
    this.renderAllFloors();        // 2. Floor tiles per zone
    this.renderWallLines();        // 3. Outlines / wall shadows
    this.renderDoors();            // 4. Door sprites in walls
    this.renderSpecialFurniture(); // 5. Special rooms: lounge, break, etc.
    this.renderEntranceArea();     // 6. Entrance zone (glass doors, clock, TV)
    this.renderCorridorDecor();    // 7. Plants, rugs in corridors
    this.renderChairs();           // 8. Office chairs — behind desks
    this.renderSeatedAgents();     // 9. Seated characters BEFORE desks (desks cover legs)
    this.renderDesks();            // 10. Desks on top → agent legs hidden = sitting look
    this.renderWalkingAgents();    // 11. Walking delivery animations (on top)
    this.renderHUD();              // 12. Hover tooltip
    this.renderRoomLabels();       // 13. Room name badges — LAST so always on top of everything
  }

  // ─── 1. Building shell (cream wall fill) ──────────────────────────────
  private renderBuildingShell(): void {
    const { x: bx, y: by } = this.gs(0, 0);
    const bw = BW * this.T * this.zoom;
    const bh = BH * this.T * this.zoom;
    // Outer shadow
    const ctx = this.ctx;
    ctx.shadowColor = 'rgba(0,0,0,0.5)';
    ctx.shadowBlur = 16 * this.zoom;
    ctx.fillStyle = P.WALL;
    ctx.fillRect(bx, by, bw, bh);
    ctx.shadowBlur = 0;
    // Outer border
    ctx.strokeStyle = P.WALL_OUTLINE;
    ctx.lineWidth = 2;
    ctx.strokeRect(bx, by, bw, bh);
  }

  // ─── 2. All floor tiles ───────────────────────────────────────────────
  private renderAllFloors(): void {
    // Entrance (wood)
    this.fillFloor(ENT_Y.start, ENT_Y.end, 0, BW - 1, 'wood');

    // Horizontal corridors
    this.fillFloor(HCOR0_Y.start, HCOR0_Y.end, 0, BW - 1, 'hall');
    this.fillFloor(HCOR1_Y.start, HCOR1_Y.end, 0, BW - 1, 'hall');
    this.fillFloor(HCOR2_Y.start, HCOR2_Y.end, 0, BW - 1, 'hall');

    // Vertical corridors
    this.fillFloor(0, BH - 1, VCOR1_X.start, VCOR1_X.end, 'hall');
    this.fillFloor(0, BH - 1, VCOR2_X.start, VCOR2_X.end, 'hall');
    this.fillFloor(0, BH - 1, VCOR3_X.start, VCOR3_X.end, 'hall');

    // Room floors
    ROOMS.forEach((room) => {
      this.fillFloor(room.y, room.y + room.h - 1, room.x, room.x + room.w - 1, room.floor);
    });
  }

  private fillFloor(y1: number, y2: number, x1: number, x2: number, type: string): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const [c1, c2, cg] = this.floorColors(type);

    for (let ty = y1; ty <= y2; ty++) {
      for (let tx = x1; tx <= x2; tx++) {
        const { x, y } = this.gs(tx, ty);
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
        const { y } = this.gs(x1, ty);
        ctx.beginPath();
        ctx.moveTo(this.gs(x1, ty).x, y + T * 0.33);
        ctx.lineTo(this.gs(x2 + 1, ty).x, y + T * 0.33);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(this.gs(x1, ty).x, y + T * 0.66);
        ctx.lineTo(this.gs(x2 + 1, ty).x, y + T * 0.66);
        ctx.stroke();
      }
    }
  }

  private floorColors(type: string): [string, string, string] {
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
  private renderWallLines(): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;

    // Helper: draw a horizontal wall line
    const hLine = (ty: number, x1: number, x2: number, thick = 2) => {
      const p1 = this.gs(x1, ty);
      const p2 = this.gs(x2 + 1, ty);
      ctx.strokeStyle = P.WALL_OUTLINE;
      ctx.lineWidth = thick;
      ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p1.y); ctx.stroke();
    };

    // Helper: draw a vertical wall line
    const vLine = (tx: number, y1: number, y2: number, thick = 2) => {
      const p1 = this.gs(tx, y1);
      const p2 = this.gs(tx, y2 + 1);
      ctx.strokeStyle = P.WALL_OUTLINE;
      ctx.lineWidth = thick;
      ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p1.x, p2.y); ctx.stroke();
    };

    // Outer building outline (drawn over shell)
    const bp = this.gs(0, 0);
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
      const { x: px, y: py } = this.gs(x1, ty);
      const pw = (x2 - x1 + 1) * T;
      ctx.fillStyle = 'rgba(0,0,0,0.15)';
      ctx.fillRect(px, py, pw, Math.max(2, 3 * this.zoom));
    };
    [ENT_Y.end + 1, HCOR0_Y.end + 1, ROW1_Y.end + 1, HCOR1_Y.end + 1, ROW2_Y.end + 1, HCOR2_Y.end + 1, ROW3_Y.end + 1].forEach((y) => {
      shadowH(y, 0, BW - 1);
    });
  }

  // ─── 4. Door sprites ─────────────────────────────────────────────────
  private renderDoors(): void {
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

    hDoors.forEach((d) => this.drawHDoor(d.tx, d.ty));
    vDoors.forEach((d) => this.drawVDoor(d.tx, d.ty));
  }

  private drawHDoor(tx: number, ty: number): void {
    // A horizontal door: 2 tiles wide, 1 tile tall, drawn ON the wall tile
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    // Floor background showing through
    ctx.fillStyle = P.FLOOR_HALL1;
    ctx.fillRect(x, y, T * 2, T);
    // Door frame
    ctx.fillStyle = P.DOOR;
    ctx.fillRect(x, y, T * 2, Math.max(2, 3 * this.zoom));
    ctx.fillRect(x, y, Math.max(2, 2 * this.zoom), T);
    ctx.fillRect(x + T * 2 - Math.max(2, 2 * this.zoom), y, Math.max(2, 2 * this.zoom), T);
    // Door fill
    ctx.fillStyle = P.DOOR_FILL;
    ctx.fillRect(x + Math.max(2, 2 * this.zoom), y + Math.max(2, 3 * this.zoom), T * 2 - Math.max(4, 4 * this.zoom), T - Math.max(2, 3 * this.zoom));
    // Door knob
    ctx.fillStyle = '#c8a050';
    ctx.beginPath(); ctx.arc(x + T * 1.5, y + T * 0.55, Math.max(2, 2 * this.zoom), 0, Math.PI * 2); ctx.fill();
  }

  private drawVDoor(tx: number, ty: number): void {
    // A vertical door: 1 tile wide, 2 tiles tall
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    ctx.fillStyle = P.FLOOR_HALL1;
    ctx.fillRect(x, y, T, T * 2);
    ctx.fillStyle = P.DOOR;
    ctx.fillRect(x, y, T, Math.max(2, 2 * this.zoom));
    ctx.fillRect(x, y + T * 2 - Math.max(2, 2 * this.zoom), T, Math.max(2, 2 * this.zoom));
    ctx.fillRect(x, y, Math.max(2, 3 * this.zoom), T * 2);
    ctx.fillStyle = P.DOOR_FILL;
    ctx.fillRect(x + Math.max(2, 3 * this.zoom), y + Math.max(2, 2 * this.zoom), T - Math.max(2, 3 * this.zoom), T * 2 - Math.max(4, 4 * this.zoom));
    ctx.fillStyle = '#c8a050';
    ctx.beginPath(); ctx.arc(x + T * 0.55, y + T * 1.5, Math.max(2, 2 * this.zoom), 0, Math.PI * 2); ctx.fill();
  }

  // ─── Room name labels — rendered LAST so always on top ──────────────
  private renderRoomLabels(): void {
    const ctx = this.ctx;

    ROOMS.forEach((room) => {
      const text = `${room.icon} ${room.label}`;
      ctx.save();
      ctx.font = `bold ${Math.max(8.5, 8.5 * this.zoom)}px sans-serif`;
      const tw = ctx.measureText(text).width;
      const bw = tw + 16, bh = 15 * this.zoom;

      // Position: More on top, centered horizontally in the corridor between the rooms
      const centerScreen = this.gs(room.x + room.w / 2, room.y - 2.5);
      const lx = centerScreen.x - bw / 2;
      const ly = centerScreen.y - bh / 2;

      // Drop shadow
      ctx.fillStyle = 'rgba(0,0,0,0.25)';
      ctx.fillRect(lx + 2, ly + 2, bw, bh);

      // White background pill
      ctx.fillStyle = 'rgba(255,255,255,0.97)';
      ctx.fillRect(lx, ly, bw, bh);
      ctx.strokeStyle = room.accent;
      ctx.lineWidth = 1.5;
      ctx.strokeRect(lx, ly, bw, bh);

      // Left accent bar
      ctx.fillStyle = room.accent;
      ctx.fillRect(lx, ly, 3.5, bh);

      ctx.fillStyle = '#1a1a2a';
      ctx.fillText(text, lx + 8, ly + bh * 0.74);
      ctx.restore();
    });
  }

  // ─── 6. Special room furniture ───────────────────────────────────────
  private renderSpecialFurniture(): void {
    this.renderLoungeFurniture();
    this.renderBreakRoomFurniture();
    this.renderConferenceFurniture();
    this.renderKitchenFurniture();
  }

  private renderLoungeFurniture(): void {
    const r = ROOMS.find((r) => r.key === 'Lounge')!;
    if (!r) return;
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2;
    // Couch (3 tiles wide, left of center)
    this.drawCouch(r.x + 1, r.y + 1, 3, 2);
    // Coffee table (2×1 centered)
    this.drawCoffeeTable(r.x + 2, r.y + 4);
    // Chair on other side
    this.drawArmchair(r.x + 5, r.y + 1);
    this.drawArmchair(r.x + 8, r.y + 1);
    // Plants in corners
    this.drawPlant(r.x + 0, r.y + 0);
    this.drawPlant(r.x + r.w - 1, r.y + 0);
    this.drawPlant(r.x + 0, r.y + r.h - 1);
    this.drawPlant(r.x + r.w - 1, r.y + r.h - 1);
    // Wall TV (on north wall)
    this.drawWallTV(r.x + 3, r.y);
  }

  private renderBreakRoomFurniture(): void {
    const r = ROOMS.find((r) => r.key === 'Break Room')!;
    if (!r) return;
    this.drawPingPongTable(r.x + 1, r.y + 1);
    this.drawArcadeMachine(r.x + 9, r.y + 1);
    this.drawArcadeMachine(r.x + 11, r.y + 1);
    this.drawPlant(r.x, r.y);
    this.drawPlant(r.x + r.w - 1, r.y);
    this.drawBeanBag(r.x + 1, r.y + 6);
    this.drawBeanBag(r.x + 3, r.y + 6);
    this.drawBeanBag(r.x + 10, r.y + 6);
    this.drawSnackTable(r.x + 9, r.y + 5);
  }

  private renderConferenceFurniture(): void {
    const r = ROOMS.find((r) => r.key === 'Conference')!;
    if (!r) return;
    this.drawConferenceTable(r.x + 1, r.y + 1, 8, 6);
    // Chairs around table (visual only)
    this.drawPlant(r.x, r.y);
    this.drawPlant(r.x + r.w - 1, r.y + r.h - 1);
    this.drawWhiteboardWall(r.x, r.y + 2);
  }

  private renderKitchenFurniture(): void {
    const r = ROOMS.find((r) => r.key === 'Kitchen')!;
    if (!r) return;
    // Counter run along top wall
    this.drawCounter(r.x + 0, r.y + 0, 13);
    this.drawFridge(r.x + 12, r.y + 0);
    this.drawMicrowave(r.x + 9, r.y + 1);
    this.drawCoffeeMachine(r.x + 7, r.y + 1);
    this.drawSink(r.x + 5, r.y + 1);
    // Kitchen island / bar table
    this.drawKitchenIsland(r.x + 2, r.y + 4, 8, 3);
    this.drawBarStool(r.x + 3, r.y + 7);
    this.drawBarStool(r.x + 5, r.y + 7);
    this.drawBarStool(r.x + 8, r.y + 7);
    this.drawPlant(r.x, r.y + r.h - 1);
    this.drawPlant(r.x + r.w - 1, r.y + r.h - 1);
  }

  // ─── 7. Desks in department rooms ────────────────────────────────────
  private renderDesks(): void {
    ROOMS.forEach((room) => {
      if (room.desks.length === 0) return;
      const desks = this.getRoomDesks(room);
      desks.forEach((desk) => {
        const tx = room.x + desk.dx;
        const ty = room.y + desk.dy;
        this.drawDesk(tx, ty, desk.dir, desk.isManager);
      });
    });
  }

  // ─── 7. Entrance / reception area ────────────────────────────────────
  private renderEntranceArea(): void {
    // Glass double doors centered at bottom of entrance zone
    const doorX = Math.floor(BW / 2) - 2;
    const doorY = ENT_Y.end; // y=5
    this.drawGlassDoors(doorX, doorY);

    // Wall clock on left wall
    this.drawWallClock(COL1_X.start + 2, ENT_Y.start);

    // Wall-mounted TV / company display on right side
    this.drawWallTV(COL3_X.start + 2, ENT_Y.start);

    // Plants along entrance
    this.drawPlant(1, ENT_Y.start);
    this.drawPlant(BW - 2, ENT_Y.start);
    this.drawPlant(doorX - 2, ENT_Y.end - 1);
    this.drawPlant(doorX + 4, ENT_Y.end - 1);

    // Lounge / waiting chairs along sides of entrance
    this.drawArmchair(COL1_X.start, ENT_Y.start + 2);
    this.drawArmchair(COL1_X.start + 2, ENT_Y.start + 2);
    this.drawArmchair(COL4_X.end - 2, ENT_Y.start + 2);
    this.drawArmchair(COL4_X.end - 1, ENT_Y.start + 2);
  }

  // ─── 9. Corridor decor ────────────────────────────────────────────────
  private renderCorridorDecor(): void {
    // Plants at corridor intersections
    const intersX = [VCOR1_X.start, VCOR2_X.start, VCOR3_X.start];
    const intersY = [HCOR0_Y.start, HCOR1_Y.start, HCOR2_Y.start];
    intersX.forEach((x) => intersY.forEach((y) => {
      this.drawPlant(x, y);
    }));

    // Small rugs / direction mats in corridors
    [HCOR0_Y.start + 1, HCOR1_Y.start + 1, HCOR2_Y.start + 1].forEach((y) => {
      this.drawCorridorRug(COL1_X.start + 4, y);
      this.drawCorridorRug(COL2_X.start + 4, y);
      this.drawCorridorRug(COL3_X.start + 4, y);
    });

    // Arrows / direction markers in V-corridors (subtle)
    [VCOR1_X.start, VCOR2_X.start, VCOR3_X.start].forEach((x) => {
      [ROW1_Y.start + 3, ROW2_Y.start + 3, ROW3_Y.start + 3].forEach((y) => {
        this.drawCorridorArrow(x, y);
      });
    });
  }

  // ─── 9. Office chairs behind every desk ──────────────────────────────
  private renderChairs(): void {
    ROOMS.forEach((room) => {
      if (room.desks.length === 0) return;
      const desks = this.getRoomDesks(room);
      desks.forEach((desk) => {
        const tx = room.x + desk.dx;
        const ty = room.y + desk.dy;
        this.drawOfficeChair(tx, ty, desk.dir, desk.isManager);
      });
    });
  }

  // ─── 10. Seated agents & resting agents ──────────────────────────────
  private renderSeatedAgents(): void {
    const items: Array<{ agent: Agent; tx: number; ty: number; dir: string; isAtDesk: boolean }> = [];
    this.agents.forEach((a) => {
      const pos = this.deskMap.get(a.id);
      if (pos && !this.walkAnims.has(a.id)) {
        items.push({ agent: a, tx: pos.tx, ty: pos.ty, dir: pos.dir, isAtDesk: pos.isAtDesk });
      }
    });
    // Sort by Y so southern characters draw on top of northern ones
    items.sort((a, b) => a.ty - b.ty);
    items.forEach(({ agent, tx, ty, dir, isAtDesk }) => {
      if (isAtDesk) {
        this.drawCharacterSeated(agent, tx, ty, dir);
      } else {
        this.drawCharacter(agent, tx, ty, 'seated');
      }
    });
  }

  // ─── 11. Walking agents ──────────────────────────────────────────────
  private renderWalkingAgents(): void {
    this.walkAnims.forEach((anim) => {
      const agent = this.agents.find((a) => String(a.id) === anim.agentId);
      if (!agent) return;
      const t = anim.phase === 'returning' ? 1 - anim.progress : anim.progress;
      const cx = anim.fromX + (anim.toX - anim.fromX) * t;
      const cy = anim.fromY + (anim.toY - anim.fromY) * t;
      this.drawCharacter(agent, cx, cy, 'walking', anim.phase === 'delivering');
    });
  }

  // ─── 12. HUD ────────────────────────────────────────────────────────
  private renderHUD(): void {
    if (!this.hoveredAgentId) return;
    const agent = this.agents.find((a) => a.id === this.hoveredAgentId);
    const pos = this.deskMap.get(this.hoveredAgentId);
    if (!agent || !pos) return;

    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x: ax, y: ay } = this.gs(pos.tx, pos.ty);
    const task = this.tasks.find(
      (t) => String(t.agent_id) === String(agent.id) && (t.status === 'running' || t.status === 'queued')
    );
    const wk = this.walkAnims.get(agent.id);

    const TW = 220, TH = task || wk ? 80 : 60;
    const tx = Math.min(Math.max(ax - TW / 2, 8), this.canvas.width - TW - 8);
    const ty2 = Math.max(ay - TH - T * 1.5, 8);

    ctx.save();
    ctx.fillStyle = 'rgba(248,248,245,0.97)';
    ctx.strokeStyle = '#8c7a5e';
    ctx.lineWidth = 1.5;
    ctx.fillRect(tx, ty2, TW, TH);
    ctx.strokeRect(tx, ty2, TW, TH);

    // Left color bar
    const colors = this.charColors.get(agent.id);
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
  private drawCharacter(
    agent: Agent, tx: number, ty: number,
    state: 'seated' | 'walking',
    delivering = false
  ): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;

    const colors = this.charColors.get(agent.id) || { shirt: '#3b82f6', hair: '#2c1a0e', skin: '#f5cba7' };
    const isSelected = this.selectedAgentId === agent.id;
    const isHovered  = this.hoveredAgentId === agent.id;
    const role = (agent.role_type || 'WORKER').toUpperCase();
    const isManager = role === 'ROOT_ORCHESTRATOR' || role === 'MANAGER';

    // Position: centered on tile, bottom of sprite at y+T
    const cx = x + T / 2;
    const cy = y + T * 0.85;

    // Walking leg bob
    const leg = state === 'walking' ? Math.floor(this.tick / 7) % 2 : 0;

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

    // Active task indicator (pulsing dot)
    const activeTask = this.tasks.find(
      (t) => String(t.agent_id) === String(agent.id) && (t.status === 'running' || t.status === 'queued')
    );
    if (activeTask) {
      const pulse = 0.6 + Math.abs(Math.sin(this.tick * 0.08)) * 0.4;
      ctx.fillStyle = `rgba(16,185,129,${pulse})`;
      ctx.beginPath();
      ctx.arc(cx + 6 * z, cy - 26 * z, 3 * z, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    ctx.restore();
  }

  // ─── Seated character — positioned so the desk covers their lower body ───
  // For dir='down': agent faces north, desk is at back, chair at south edge of desk tile.
  // For dir='up':  agent faces south, desk at back, chair at north edge of desk tile.
  private drawCharacterSeated(agent: Agent, tx: number, ty: number, dir: string): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;

    const colors = this.charColors.get(agent.id) || { shirt: '#3b82f6', hair: '#2c1a0e', skin: '#f5cba7' };
    const isSelected = this.selectedAgentId === agent.id;
    const isHovered  = this.hoveredAgentId === agent.id;
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

    // Active task pulsing dot
    const activeTask = this.tasks.find(
      (t) => String(t.agent_id) === String(agent.id) && (t.status === 'running' || t.status === 'queued')
    );
    if (activeTask) {
      const pulse = 0.6 + Math.abs(Math.sin(this.tick * 0.08)) * 0.4;
      ctx.fillStyle = `rgba(16,185,129,${pulse})`;
      ctx.beginPath();
      ctx.arc(cx + 6 * z, cy - 24 * z, 3 * z, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 0.5;
      ctx.stroke();
    }

    ctx.restore();
  }

  // ─── Office chair sprite ──────────────────────────────────────────────
  // For dir='down': chair appears at bottom (south) of desk tile
  // For dir='up':   chair appears at top (north) of desk tile
  private drawOfficeChair(tx: number, ty: number, dir: string, isManager = false): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;

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
  private drawDesk(tx: number, ty: number, dir: 'up' | 'down' | 'left' | 'right', isManager = false): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;

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
  private drawCouch(tx: number, ty: number, wTiles: number, hTiles: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawArmchair(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawCoffeeTable(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawWallTV(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    const tvW = T * 2, tvH = T * 0.7;
    ctx.fillStyle = '#111827'; ctx.fillRect(x, y + T * 0.15, tvW, tvH);
    ctx.strokeStyle = '#374151'; ctx.lineWidth = 1; ctx.strokeRect(x, y + T * 0.15, tvW, tvH);
    const screenHue = (this.tick * 2) % 360;
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
  private drawWallClock(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawPlant(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawPingPongTable(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
    const bt = (this.tick % 80) / 80;
    const bx = x + 8 * z + (tw - 16 * z) * bt;
    const barc = -Math.abs(Math.sin(bt * Math.PI)) * 10 * z;
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(bx, y + th / 2 + barc, 3 * z, 0, Math.PI * 2); ctx.fill();
  }

  // ─── Arcade machine ───────────────────────────────────────────────────
  private drawArcadeMachine(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    ctx.fillStyle = '#1a1a2e'; ctx.fillRect(x, y, T * 0.85, T);
    ctx.strokeStyle = '#e91e63'; ctx.lineWidth = 1; ctx.strokeRect(x, y, T * 0.85, T);
    ctx.fillStyle = '#000'; ctx.fillRect(x + 2 * z, y + 4 * z, T * 0.85 - 4 * z, T * 0.45);
    const gh = (this.tick * 4) % 360;
    ctx.fillStyle = `hsl(${gh},80%,45%)`; ctx.fillRect(x + 3 * z, y + 5 * z, T * 0.85 - 6 * z, T * 0.45 - 2 * z);
    ctx.fillStyle = '#4a4a4a'; ctx.beginPath(); ctx.arc(x + T * 0.35, y + T * 0.7, 4 * z, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#dc2626'; ctx.beginPath(); ctx.arc(x + T * 0.65, y + T * 0.75, 3 * z, 0, Math.PI * 2); ctx.fill();
  }

  // ─── Bean bag ─────────────────────────────────────────────────────────
  private drawBeanBag(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    const colors = ['#7c3aed','#0ea5e9','#ef4444','#10b981','#f59e0b'];
    const c = colors[(tx + ty) % 5];
    ctx.fillStyle = 'rgba(0,0,0,0.2)'; ctx.beginPath(); ctx.ellipse(x + T / 2 + 2 * z, y + T / 2 + 2 * z, T * 0.42, T * 0.35, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = c; ctx.beginPath(); ctx.ellipse(x + T / 2, y + T / 2, T * 0.42, T * 0.35, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.2)'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = 'rgba(255,255,255,0.18)';
    ctx.beginPath(); ctx.ellipse(x + T / 2 - 4 * z, y + T / 2 - 5 * z, T * 0.15, T * 0.12, -0.5, 0, Math.PI * 2); ctx.fill();
  }

  // ─── Snack/drink table ───────────────────────────────────────────────
  private drawSnackTable(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    ctx.fillStyle = '#d4c5a0'; ctx.fillRect(x, y, T * 2, T * 0.8);
    ctx.strokeStyle = '#8c7a5a'; ctx.lineWidth = 1; ctx.strokeRect(x, y, T * 2, T * 0.8);
    // Bottles / cans
    ctx.fillStyle = '#e84040'; ctx.beginPath(); ctx.ellipse(x + T * 0.35, y + T * 0.4, 4 * z, 6 * z, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#40a0e8'; ctx.beginPath(); ctx.ellipse(x + T * 0.8, y + T * 0.4, 4 * z, 6 * z, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#48c854'; ctx.beginPath(); ctx.ellipse(x + T * 1.4, y + T * 0.4, 4 * z, 6 * z, 0, 0, Math.PI * 2); ctx.fill();
  }

  // ─── Conference table ─────────────────────────────────────────────────
  private drawConferenceTable(tx: number, ty: number, wTiles: number, hTiles: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
      ctx.fillStyle = Math.sin(this.tick * 0.05 + i) > 0 ? '#1e3a5a' : '#3b82f6';
      ctx.fillRect(lapX - 4 * z, lapY - 3 * z, 8 * z, 5 * z);
    }
    // Coffee cups
    ctx.fillStyle = '#d4c5a0';
    ctx.beginPath(); ctx.ellipse(cx - 15 * z, cy, 4 * z, 4 * z, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.ellipse(cx + 15 * z, cy, 4 * z, 4 * z, 0, 0, Math.PI * 2); ctx.fill();
  }

  // ─── Whiteboard ──────────────────────────────────────────────────────
  private drawWhiteboardWall(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawCounter(tx: number, ty: number, wTiles: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawFridge(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawMicrowave(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    ctx.fillStyle = '#3a3a3a'; ctx.fillRect(x, y + T * 0.2, T * 1.2, T * 0.6);
    ctx.strokeStyle = '#555'; ctx.lineWidth = 0.8; ctx.strokeRect(x, y + T * 0.2, T * 1.2, T * 0.6);
    const on = (this.tick % 180) < 90;
    ctx.fillStyle = on ? '#1a2a1a' : '#111'; ctx.fillRect(x + 2 * z, y + T * 0.22, T * 0.75, T * 0.56);
    if (on) { ctx.font = `${Math.max(8, 8 * z)}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText('🍕', x + T * 0.35, y + T * 0.6); ctx.textAlign = 'left'; }
    ctx.fillStyle = '#555'; ctx.fillRect(x + T * 0.9, y + T * 0.22, T * 0.28, T * 0.56);
    ctx.fillStyle = on ? '#22c55e' : '#555'; ctx.fillRect(x + T * 0.92, y + T * 0.3, T * 0.08, T * 0.1);
  }

  // ─── Coffee machine ───────────────────────────────────────────────────
  private drawCoffeeMachine(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawSink(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    ctx.fillStyle = '#b0b8c0'; ctx.fillRect(x, y, T, T * 0.8);
    ctx.fillStyle = '#8a9298'; ctx.fillRect(x + 3 * z, y + 3 * z, T - 6 * z, T * 0.65);
    const run = (this.tick % 240) < 120;
    if (run) { ctx.fillStyle = 'rgba(147,197,253,0.5)'; ctx.fillRect(x + 4 * z, y + 4 * z, T - 8 * z, T * 0.55); }
    ctx.fillStyle = '#9098a0'; ctx.fillRect(x + T / 2 - 2 * z, y, 4 * z, 8 * z);
    ctx.fillRect(x + T / 2 - 8 * z, y + 1 * z, 16 * z, 3 * z);
    ctx.fillStyle = '#606870'; ctx.beginPath(); ctx.arc(x + T / 2, y + T * 0.6, 3 * z, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#707880'; ctx.lineWidth = 0.8; ctx.strokeRect(x, y, T, T * 0.8);
  }

  // ─── Kitchen island ───────────────────────────────────────────────────
  private drawKitchenIsland(tx: number, ty: number, wTiles: number, hTiles: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawBarStool(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    const cx = x + T / 2, cy = y + T / 2;
    ctx.fillStyle = 'rgba(0,0,0,0.18)'; ctx.beginPath(); ctx.ellipse(cx + 1 * z, cy + 1 * z, 7 * z, 5 * z, 0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#5a4a3a'; ctx.beginPath(); ctx.ellipse(cx, cy, 7 * z, 5 * z, 0, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#3a2a1a'; ctx.lineWidth = 0.8; ctx.stroke();
    ctx.strokeStyle = '#6a5a4a'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(cx, cy + 5 * z); ctx.lineTo(cx, cy + T * 0.35); ctx.stroke();
  }

  // ─── Corridor rug ─────────────────────────────────────────────────────
  private drawCorridorRug(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    ctx.fillStyle = 'rgba(120,100,80,0.3)';
    ctx.fillRect(x - T * 0.3, y + 2 * z, T * 2.6, T - 4 * z);
    ctx.strokeStyle = 'rgba(120,100,80,0.5)'; ctx.lineWidth = 1;
    ctx.strokeRect(x - T * 0.3 + 2 * z, y + 4 * z, T * 2.6 - 4 * z, T - 8 * z);
  }

  // ─── Corridor arrow ───────────────────────────────────────────────────
  private drawCorridorArrow(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawReceptionDesk(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
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
  private drawGlassDoors(tx: number, ty: number): void {
    const ctx = this.ctx;
    const T = this.T * this.zoom;
    const { x, y } = this.gs(tx, ty);
    const z = this.zoom;
    const dw = T * 4, dh = T;
    // Opening (floor shows through)
    this.fillFloor(ty, ty, tx, tx + 3, 'wood');
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
}
