import { test } from 'node:test';
import assert from 'node:assert/strict';
import { gs, px } from '../src/engine/pixelCoordinates.ts';

for (const [zoom, panX, panY, tx, ty, expected] of [
  [1, 0, 0, 2, 3, { x: 32, y: 48 }], [2, 10, -10, 2, 3, { x: 74, y: 86 }],
  [0.5, -8, 12, -1, 2, { x: -16, y: 28 }], [1, 5, 6, 0, 0, { x: 5, y: 6 }],
]) {
  test(`grid projection zoom=${zoom}, pan=(${panX},${panY})`, () => {
    const scene = Object.freeze({ T: 16, zoom, panX, panY });
    assert.deepEqual(gs(scene, tx, ty), expected);
    assert.equal(px(scene, 10), 10 * zoom);
  });
}
