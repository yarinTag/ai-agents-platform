export interface VisualConnection {
  id: string;
  fromAgentId: string;
  toAgentId?: string;
  targetType: 'agent' | 'super_agent' | 'mcp';
  color: string;
  label?: string;
}


// ─── Palette ──────────────────────────────────────────────────────────────────
export const P = {
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

export const BW = 56; // building width in tiles
export const BH = 46; // building height in tiles

// Y zones
export const ENT_Y   = { start: 1,  end: 5  }; // entrance
export const HCOR0_Y = { start: 7,  end: 9  }; // h-corridor 0
export const ROW1_Y  = { start: 11, end: 18 }; // room row 1
export const HCOR1_Y = { start: 20, end: 22 }; // h-corridor 1
export const ROW2_Y  = { start: 24, end: 31 }; // room row 2
export const HCOR2_Y = { start: 33, end: 35 }; // h-corridor 2
export const ROW3_Y  = { start: 37, end: 44 }; // room row 3

// X zones
export const COL1_X  = { start: 1,  end: 10 };
export const VCOR1_X = { start: 12, end: 13 };
export const COL2_X  = { start: 15, end: 24 };
export const VCOR2_X = { start: 26, end: 27 };
export const COL3_X  = { start: 29, end: 38 };
export const VCOR3_X = { start: 40, end: 41 };
export const COL4_X  = { start: 43, end: 55 };

// Room definitions [label, xStart, xEnd, yStart, yEnd, floorType, accentColor]
export interface RoomDef {
  key: string; label: string; icon: string; accent: string;
  x: number; y: number; w: number; h: number;
  floor: 'gray' | 'wood' | 'hall' | 'carpet' | 'tile' | 'blue';
  // Desk positions (relative to room top-left tile)
  desks: Array<{ dx: number; dy: number; dir: 'up' | 'down' | 'left' | 'right' }>;
}

// Standard 6-desk layout: 3 columns × 2 rows
// Col positions: dx = 1, 4, 7 (evenly spaced in 10-tile wide rooms)
// Row 1 (dy=2): clamped away from north wall/doors, agent sits south → dir='down'
// Row 2 (dy=5): near center, agent sits north → dir='up'
export const D6: RoomDef['desks'] = [
  { dx: 1, dy: 2, dir: 'down' }, { dx: 4, dy: 2, dir: 'down' }, { dx: 7, dy: 2, dir: 'down' },
  { dx: 1, dy: 5, dir: 'up'   }, { dx: 4, dy: 5, dir: 'up'   }, { dx: 7, dy: 5, dir: 'up'   },
];

export const ROOMS: RoomDef[] = [
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
export interface WalkAnim {
  agentId: string; managerId: string;
  fromX: number; fromY: number; toX: number; toY: number;
  progress: number; phase: 'walking' | 'delivering' | 'returning';
  deliverTick: number;
}

// ─── Character palette ────────────────────────────────────────────────────────
export const SHIRT_COLORS = [
  '#e74c6a', '#3b82f6', '#10b981', '#f59e0b',
  '#8b5cf6', '#0ea5e9', '#ef4444', '#14b8a6',
];
export const HAIR_COLORS = ['#2c1a0e', '#5c3a1e', '#c4a265', '#8b7355', '#1a1a1a', '#a0522d'];
export const SKIN_TONES  = ['#f5cba7', '#e8a87c', '#d4845a', '#c46a3a'];

