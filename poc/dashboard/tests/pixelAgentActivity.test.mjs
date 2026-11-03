import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectTaskCompletions, tickWalkAnims, isAgentWorking, isManagerOrLead } from '../src/engine/pixelAgentActivity.ts';

const scene = () => ({ tasks: [], agents: [{ id: 'worker', parent_id: 'manager' }, { id: 'manager' }],
  prevTaskStatuses: new Map(), walkAnims: new Map(), deskMap: new Map([
    ['worker', { tx: 1, ty: 2 }], ['manager', { tx: 8, ty: 9 }],
  ]), tick: 0 });

for (const status of ['running', 'queued', 'in_progress']) {
  test(`active task state marks its assigned agent busy: ${status}`, () => {
    const state = scene(); state.tasks = [{ agent_id: 'worker', status }];
    assert.equal(isAgentWorking(state, { id: 'worker' }), true);
    assert.equal(isAgentWorking(state, { id: 'other' }), false);
  });
}
for (const status of ['done', 'completed', 'failed', 'cancelled', 'pending_approval']) {
  test(`inactive task state does not imply model activity: ${status}`, () => {
    const state = scene(); state.tasks = [{ agent_id: 'worker', status }];
    assert.equal(isAgentWorking(state, { id: 'worker' }), false);
  });
}
for (const status of ['RUNNING', 'thinking', 'reviewing', 'active']) {
  test(`agent status fallback recognizes ${status}`, () => assert.equal(isAgentWorking(scene(), { id: 'worker', status }), true));
}

test('current-task text indicates activity while blank text does not', () => {
  assert.equal(isAgentWorking(scene(), { id: 'worker', current_task: 'Analyze' }), true);
  assert.equal(isAgentWorking(scene(), { id: 'worker', current_task: '   ' }), false);
  const state = scene(); state.tasks = [{ agent_id: 42, status: 'running' }];
  assert.equal(isAgentWorking(state, { id: '42' }), true);
});

for (const previous of ['running', 'queued']) {
  for (const current of ['done', 'completed', 'success', 'finished']) {
    test(`completion transition ${previous} -> ${current} delivers to the manager once`, () => {
      const state = scene(); state.prevTaskStatuses.set('task', previous);
      state.tasks = [{ id: 'task', agent_id: 'worker', status: current }];
      detectTaskCompletions(state);
      assert.deepEqual(state.walkAnims.get('worker'), { agentId: 'worker', managerId: 'manager',
        fromX: 1, fromY: 2, toX: 8, toY: 9, progress: 0, phase: 'walking', deliverTick: 0 });
      const animation = state.walkAnims.get('worker');
      animation.progress = 0.5;
      detectTaskCompletions(state);
      assert.equal(state.walkAnims.get('worker').progress, 0.5);
      assert.equal(state.prevTaskStatuses.get('task'), current);
    });
  }
}

for (const current of ['failed', 'cancelled', 'running']) {
  test(`non-success transition never creates a delivery animation: ${current}`, () => {
    const state = scene(); state.prevTaskStatuses.set('task', 'running');
    state.tasks = [{ id: 'task', agent_id: 'worker', status: current }];
    detectTaskCompletions(state);
    assert.equal(state.walkAnims.size, 0);
  });
}

test('historical successes and missing managers/desks do not fabricate deliveries', () => {
  for (const variation of ['no-history', 'no-parent', 'no-worker', 'no-desk']) {
    const state = scene(); state.prevTaskStatuses.set('task', 'running');
    state.tasks = [{ id: 'task', agent_id: 'worker', status: 'completed' }];
    if (variation === 'no-history') state.prevTaskStatuses.clear();
    if (variation === 'no-parent') state.agents[0].parent_id = null;
    if (variation === 'no-worker') state.agents = [];
    if (variation === 'no-desk') state.deskMap.delete('manager');
    detectTaskCompletions(state);
    assert.equal(state.walkAnims.size, 0);
    assert.equal(state.prevTaskStatuses.get('task'), 'completed');
  }
});

test('delivery animation walks, waits, returns and is removed without affecting other animations', () => {
  const state = scene();
  state.walkAnims.set('worker', { agentId: 'worker', progress: 0.995, phase: 'walking', deliverTick: 0 });
  tickWalkAnims(state);
  assert.equal(state.walkAnims.get('worker').phase, 'delivering');
  assert.equal(state.walkAnims.get('worker').progress, 1);
  state.tick = 100; tickWalkAnims(state);
  assert.equal(state.walkAnims.get('worker').phase, 'delivering');
  state.tick = 101; tickWalkAnims(state);
  assert.equal(state.walkAnims.get('worker').phase, 'returning');
  state.walkAnims.get('worker').progress = 0.01;
  state.walkAnims.set('other', { agentId: 'other', progress: 0.1, phase: 'walking' });
  tickWalkAnims(state);
  assert.equal(state.walkAnims.has('worker'), false);
  assert.equal(state.walkAnims.get('other').phase, 'walking');
});

for (const role of ['ROOT_ORCHESTRATOR', 'manager', 'LEAD']) {
  test(`leadership detection supports explicit role ${role}`, () => assert.equal(isManagerOrLead(scene(), { id: 'agent', role_type: role }), true));
}

test('leadership naming fallbacks preserve ordinary worker classification', () => {
  assert.equal(isManagerOrLead(scene(), { id: 'chief-orchestrator' }), true);
  assert.equal(isManagerOrLead(scene(), { id: 'agent', name: 'Team Lead' }), true);
  assert.equal(isManagerOrLead(scene(), { id: 'worker', name: 'Engineer', role_type: 'WORKER' }), false);
});
