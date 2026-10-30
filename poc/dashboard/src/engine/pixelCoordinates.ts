import type { PixelSceneState } from './pixelSceneState';

export function gs(scene: PixelSceneState, tx: number, ty: number): { x: number; y: number } {
  return { x: tx * scene.T * scene.zoom + scene.panX, y: ty * scene.T * scene.zoom + scene.panY };
}

export function px(scene: PixelSceneState, n: number): number { return n * scene.zoom; }  // scale a pixel value by zoom
