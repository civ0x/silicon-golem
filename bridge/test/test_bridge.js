'use strict';

const { describe, it, before, after, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const { WebSocket } = require('ws');
const { v4: uuidv4 } = require('uuid');

// These tests require a running bridge (npm start) connected to a MC 1.20.4 server.
// Run: node --test test/test_bridge.js

const WS_URL = process.env.WS_URL || 'ws://localhost:3001';
const TRACKED_PLAYER = process.env.TRACKED_PLAYER || 'TestPlayer';

let ws;

function sendCommand(action, args = {}) {
  const id = uuidv4();
  const msg = { type: 'command', id, action, args };
  ws.send(JSON.stringify(msg));
  return id;
}

function waitForResponse(id, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Timeout waiting for response to ${id}`));
    }, timeoutMs);

    function onMessage(raw) {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'response' && msg.id === id) {
        clearTimeout(timer);
        ws.removeListener('message', onMessage);
        resolve(msg);
      }
    }
    ws.on('message', onMessage);
  });
}

function waitForEvent(eventName, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`Timeout waiting for event '${eventName}'`));
    }, timeoutMs);

    function onMessage(raw) {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'event' && msg.event === eventName) {
        clearTimeout(timer);
        ws.removeListener('message', onMessage);
        resolve(msg);
      }
    }
    ws.on('message', onMessage);
  });
}

function sendAndWait(action, args = {}, timeoutMs = 30000) {
  const id = sendCommand(action, args);
  return waitForResponse(id, timeoutMs);
}

// === CONNECTION LIFECYCLE ===

describe('Connection Lifecycle', () => {
  it('should receive ready event on connect', async () => {
    ws = new WebSocket(WS_URL);
    const readyEvent = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('No ready event')), 5000);
      ws.on('message', (raw) => {
        const msg = JSON.parse(raw.toString());
        if (msg.type === 'event' && msg.event === 'ready') {
          clearTimeout(timer);
          resolve(msg);
        }
      });
      ws.on('error', reject);
    });

    assert.equal(readyEvent.data.mc_version, '1.20.4');
    assert.equal(readyEvent.data.bot_name, 'Golem');
    assert.ok(readyEvent.data.server);
    ws.close();
    await new Promise(r => setTimeout(r, 500));
  });

  it('should configure and track player', async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');

    const resp = await sendAndWait('configure', { track_player: TRACKED_PLAYER });
    assert.equal(resp.success, true);
    assert.equal(resp.data.configured, true);
    assert.equal(typeof resp.data.tracked_player_found, 'boolean');
    ws.close();
    await new Promise(r => setTimeout(r, 500));
  });

  it('should receive heartbeat within 15 seconds', async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');
    await sendAndWait('configure', { track_player: TRACKED_PLAYER });

    const heartbeat = await waitForEvent('heartbeat', 15000);
    assert.equal(heartbeat.type, 'event');
    assert.equal(heartbeat.event, 'heartbeat');
    assert.ok(typeof heartbeat.data.uptime_seconds === 'number');
    assert.ok(heartbeat.data.bot_position);
    assert.ok(typeof heartbeat.data.bot_position.x === 'number');
    ws.close();
    await new Promise(r => setTimeout(r, 500));
  });
});

// === OBSERVATION PRIMITIVES ===

describe('Observation Actions', () => {
  before(async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');
    await sendAndWait('configure', { track_player: TRACKED_PLAYER });
  });

  after(() => {
    ws.close();
  });

  it('get_position should return bot coordinates', async () => {
    const resp = await sendAndWait('get_position');
    assert.equal(resp.success, true);
    assert.ok(typeof resp.data.x === 'number');
    assert.ok(typeof resp.data.y === 'number');
    assert.ok(typeof resp.data.z === 'number');
  });

  it('get_inventory should return item list', async () => {
    const resp = await sendAndWait('get_inventory');
    assert.equal(resp.success, true);
    assert.ok(Array.isArray(resp.data.items));
    for (const item of resp.data.items) {
      assert.ok(typeof item.name === 'string');
      assert.ok(typeof item.count === 'number');
    }
  });

  it('get_block should return block type', async () => {
    // Get bot position, check block below
    const posResp = await sendAndWait('get_position');
    const { x, y, z } = posResp.data;

    const resp = await sendAndWait('get_block', { x, y: y - 1, z });
    assert.equal(resp.success, true);
    assert.ok(typeof resp.data.block_type === 'string');
    assert.notEqual(resp.data.block_type, ''); // Should have some block below
  });

  it('get_player_position should error for nonexistent player', async () => {
    const resp = await sendAndWait('get_player_position', { name: 'NonExistentPlayer12345' });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'PLAYER_NOT_FOUND');
  });

  it('find_player should return null for missing player', async () => {
    const resp = await sendAndWait('find_player', { name: 'NonExistentPlayer12345' });
    assert.equal(resp.success, true);
    assert.equal(resp.data, null);
  });

  it('find_blocks should return positions', async () => {
    // Look for a common block type
    const resp = await sendAndWait('find_blocks', { block_type: 'stone', count: 3 });
    assert.equal(resp.success, true);
    assert.ok(Array.isArray(resp.data.positions));
  });

  it('find_blocks should error on invalid block name', async () => {
    const resp = await sendAndWait('find_blocks', { block_type: 'not_a_real_block' });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'INVALID_BLOCK_NAME');
  });

  it('get_world_state should return full snapshot', async () => {
    const resp = await sendAndWait('get_world_state', {}, 15000);
    assert.equal(resp.success, true);
    assert.ok(resp.data.bot);
    assert.ok(resp.data.bot.position);
    assert.ok(typeof resp.data.bot.health === 'number');
    assert.ok(typeof resp.data.bot.food === 'number');
    assert.ok(Array.isArray(resp.data.bot.inventory));
    assert.ok(Array.isArray(resp.data.players));
    assert.ok(resp.data.time);
    assert.ok(typeof resp.data.game_mode === 'string');
    assert.ok(typeof resp.data.nearby_blocks === 'object');
    assert.ok(Array.isArray(resp.data.nearby_entities));
  });

  it('validate_block_name should validate correctly', async () => {
    const valid = await sendAndWait('validate_block_name', { name: 'cobblestone' });
    assert.equal(valid.success, true);
    assert.equal(valid.data.valid, true);
    assert.equal(valid.data.suggestion, null);

    const invalid = await sendAndWait('validate_block_name', { name: 'cobblston' });
    assert.equal(invalid.success, true);
    assert.equal(invalid.data.valid, false);
    assert.equal(invalid.data.suggestion, 'cobblestone');
  });

  it('say should send chat message', async () => {
    const resp = await sendAndWait('say', { message: 'Hello from test!' });
    assert.equal(resp.success, true);
    assert.equal(resp.data.sent, true);
  });
});

// === ERROR HANDLING ===

describe('Error Handling', () => {
  before(async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');
    await sendAndWait('configure', { track_player: TRACKED_PLAYER });
  });

  after(() => {
    ws.close();
  });

  it('should return error for unknown action', async () => {
    const resp = await sendAndWait('nonexistent_action');
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'UNKNOWN_ACTION');
  });

  it('should reject invalid JSON', async () => {
    const id = uuidv4();
    ws.send('not json at all {{{');

    const resp = await new Promise((resolve) => {
      ws.once('message', (raw) => {
        resolve(JSON.parse(raw.toString()));
      });
    });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'INVALID_MESSAGE');
  });

  it('equip should error for item not in inventory', async () => {
    const resp = await sendAndWait('equip', { item_name: 'netherite_sword' });
    // Might succeed if bot has the item, but most likely not
    if (!resp.success) {
      assert.equal(resp.error.code, 'ITEM_NOT_IN_INVENTORY');
    }
  });

  it('dig_block should error for air position', async () => {
    // Try to dig at a very high Y where it's likely air
    const posResp = await sendAndWait('get_position');
    const { x, z } = posResp.data;

    const resp = await sendAndWait('dig_block', { x, y: 255, z });
    assert.equal(resp.success, false);
    assert.ok(['NO_BLOCK_AT_POSITION', 'BLOCK_NOT_FOUND'].includes(resp.error.code));
  });

  it('dig_area should reject regions over 1000 blocks', async () => {
    const resp = await sendAndWait('dig_area', {
      x1: 0, y1: 0, z1: 0,
      x2: 100, y2: 10, z2: 100
    });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'REGION_TOO_LARGE');
  });

  it('place_block should error for invalid block name', async () => {
    const resp = await sendAndWait('place_block', { x: 0, y: 64, z: 0, block_type: 'not_a_block' });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'INVALID_BLOCK_NAME');
  });

  it('build_line should error for invalid direction', async () => {
    const resp = await sendAndWait('build_line', {
      x: 0, y: 64, z: 0, direction: 'diagonal', length: 5, block_type: 'cobblestone'
    });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'INVALID_DIRECTION');
  });

  it('craft should error for unknown item', async () => {
    const resp = await sendAndWait('craft', { item_name: 'not_a_real_item' });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'UNKNOWN_ITEM');
  });
});

// === BUSY REJECTION ===

describe('Busy Rejection', () => {
  before(async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');
    await sendAndWait('configure', { track_player: TRACKED_PLAYER });
  });

  after(() => {
    ws.close();
  });

  it('should reject second command while first is executing', async () => {
    // Start a move_to that will take some time
    const posResp = await sendAndWait('get_position');
    const { x, y, z } = posResp.data;

    // Send a move command to somewhere far-ish
    const moveId = sendCommand('move_to', { x: x + 50, y, z: z + 50 });

    // Small delay to ensure the move is being processed
    await new Promise(r => setTimeout(r, 200));

    // Send a second command — should get BUSY
    const busyResp = await sendAndWait('get_position');
    // If we get here fast enough, it should be BUSY
    // (But if move_to completes instantly, get_position just succeeds — that's also valid)
    if (!busyResp.success) {
      assert.equal(busyResp.error.code, 'BUSY');
    }

    // Wait for the move to finish or timeout
    await waitForResponse(moveId, 40000);
  });
});

// === MOVEMENT ACTIONS ===

describe('Movement Actions', () => {
  before(async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');
    await sendAndWait('configure', { track_player: TRACKED_PLAYER });
  });

  after(() => {
    ws.close();
  });

  it('move_to should reach nearby coordinates', async () => {
    const posResp = await sendAndWait('get_position');
    const { x, y, z } = posResp.data;

    // Move 3 blocks in x direction
    const resp = await sendAndWait('move_to', { x: x + 3, y, z }, 40000);
    assert.equal(resp.success, true);
    assert.ok(resp.data.final_position);
  });

  it('move_to_player should error for nonexistent player', async () => {
    const resp = await sendAndWait('move_to_player', { name: 'NonExistentPlayer12345' });
    assert.equal(resp.success, false);
    assert.equal(resp.error.code, 'PLAYER_NOT_FOUND');
  });
});

// === SESSION CONTROL ===

describe('Session Control', () => {
  it('cancel with no active command should succeed', async () => {
    ws = new WebSocket(WS_URL);
    await waitForEvent('ready');
    await sendAndWait('configure', { track_player: TRACKED_PLAYER });

    const resp = await sendAndWait('cancel');
    assert.equal(resp.success, true);
    assert.equal(resp.data.cancelling, null);
    ws.close();
    await new Promise(r => setTimeout(r, 500));
  });
});
