import type { Agent } from '../types/agent';
import type { Task } from '../types/task';
import type { WalkAnim, VisualConnection } from './pixelSceneLayout';

export class PixelSceneState {
  public canvas: HTMLCanvasElement;
  public ctx: CanvasRenderingContext2D;
  public animFrameId: number | null = null;
  public tick: number = 0;

  public panX: number = 0;
  public panY: number = 0;
  public zoom: number = 1.0;

  public agents: Agent[] = [];
  public tasks: Task[] = [];
  public hoveredAgentId: string | null = null;
  public selectedAgentId: string | null = null;
  public onSelectAgentCallback?: (agent: Agent) => void;

  public readonly T = 18; // base tile size in pixels

  public deskMap: Map<string, {
    tx: number;
    ty: number;
    deskIdx: number;
    roomKey: string;
    dir: string;
    isAtDesk: boolean;
    activity?: string;
  }> = new Map();
  public walkAnims: Map<string, WalkAnim> = new Map();
  public prevTaskStatuses: Map<string, string> = new Map();
  public connections: VisualConnection[] = [];

  // Character visual stable assignments
  public charColors: Map<string, { shirt: string; hair: string; skin: string }> = new Map();

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('No 2D context');
    this.ctx = ctx;
    ctx.imageSmoothingEnabled = false;
    this.panX = 30;
    this.panY = 30;
  }
}
