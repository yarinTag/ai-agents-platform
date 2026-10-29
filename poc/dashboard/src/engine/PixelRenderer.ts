/** Public office renderer; scene state and drawing layers are composed internally. */
import type { Agent } from '../types/agent';
import type { Task } from '../types/task';
import type { VisualConnection } from './pixelSceneLayout';
import { PixelSceneState } from './pixelSceneState';
import * as lifecycle from './pixelSceneLifecycle';
import { render } from './pixelScenePainter';
export type { VisualConnection } from './pixelSceneLayout';

export class PixelRenderer {
  private readonly scene: PixelSceneState;
  constructor(canvas: HTMLCanvasElement) { this.scene = new PixelSceneState(canvas); }
  get panX(): number { return this.scene.panX; }
  set panX(value: number) { this.scene.panX = value; }
  get panY(): number { return this.scene.panY; }
  set panY(value: number) { this.scene.panY = value; }
  get zoom(): number { return this.scene.zoom; }
  set zoom(value: number) { this.scene.zoom = value; }
  updateData(agents: Agent[], tasks: Task[], connections?: VisualConnection[]): void {
    lifecycle.updateData(this.scene, agents, tasks, connections);
  }
  setConnections(connections: VisualConnection[]): void { lifecycle.setConnections(this.scene, connections); }
  setOnSelectAgent(callback: (agent: Agent) => void): void { lifecycle.setOnSelectAgent(this.scene, callback); }
  setSelectedAgent(id: string | null): void { lifecycle.setSelectedAgent(this.scene, id); }
  resize(width: number, height: number): void { lifecycle.resize(this.scene, width, height); }
  start(): void { lifecycle.start(this.scene, () => render(this.scene)); }
  stop(): void { lifecycle.stop(this.scene); }
  handleCanvasClick(x: number, y: number): void { lifecycle.handleCanvasClick(this.scene, x, y); }
  handleCanvasMouseMove(x: number, y: number): void { lifecycle.handleCanvasMouseMove(this.scene, x, y); }
  render(): void { render(this.scene); }
}
