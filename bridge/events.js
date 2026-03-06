'use strict';

const HOSTILE_MOBS = new Set([
  'zombie', 'skeleton', 'creeper', 'spider', 'cave_spider', 'enderman',
  'witch', 'slime', 'magma_cube', 'blaze', 'ghast', 'wither_skeleton',
  'phantom', 'drowned', 'husk', 'stray', 'pillager', 'vindicator',
  'evoker', 'ravager', 'vex', 'warden', 'piglin_brute', 'hoglin',
  'zoglin', 'guardian', 'elder_guardian', 'shulker', 'silverfish',
  'endermite'
]);

const TIME_THRESHOLDS = [
  { tick: 0, label: 'dawn' },
  { tick: 6000, label: 'noon' },
  { tick: 12000, label: 'dusk' },
  { tick: 18000, label: 'midnight' }
];

function getTimeLabel(ticks) {
  const normalized = ticks % 24000;
  if (normalized < 6000) return 'dawn';
  if (normalized < 12000) return 'noon';
  if (normalized < 18000) return 'dusk';
  return 'midnight';
}

function setupEvents(bot, broadcast, getTrackedPlayer) {
  let lastPlayerPositions = {};
  let lastTimeLabel = null;
  let nearbyEntities = new Map(); // entityId -> { type, reported }
  let playerMoveThrottle = {};

  // player_chat
  bot.on('chat', (username, message) => {
    if (username === bot.username) return;
    broadcast({
      type: 'event',
      event: 'player_chat',
      data: { name: username, message }
    });
  });

  // player_joined
  bot.on('playerJoined', (player) => {
    if (player.username === bot.username) return;
    broadcast({
      type: 'event',
      event: 'player_joined',
      data: { name: player.username }
    });
  });

  // player_left
  bot.on('playerLeft', (player) => {
    if (player.username === bot.username) return;
    broadcast({
      type: 'event',
      event: 'player_left',
      data: { name: player.username }
    });
  });

  // player_moved — >1 block displacement, 500ms throttle
  const PLAYER_MOVE_INTERVAL = 500;
  const PLAYER_MOVE_THRESHOLD = 1;

  setInterval(() => {
    const trackedName = getTrackedPlayer();
    if (!trackedName) return;

    const player = bot.players[trackedName];
    if (!player || !player.entity) return;

    const pos = player.entity.position;
    const last = lastPlayerPositions[trackedName];

    if (last) {
      const dx = pos.x - last.x;
      const dy = pos.y - last.y;
      const dz = pos.z - last.z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

      if (dist > PLAYER_MOVE_THRESHOLD) {
        const now = Date.now();
        const lastTime = playerMoveThrottle[trackedName] || 0;
        if (now - lastTime >= PLAYER_MOVE_INTERVAL) {
          playerMoveThrottle[trackedName] = now;
          lastPlayerPositions[trackedName] = { x: pos.x, y: pos.y, z: pos.z };
          broadcast({
            type: 'event',
            event: 'player_moved',
            data: {
              name: trackedName,
              position: {
                x: Math.round(pos.x),
                y: Math.round(pos.y),
                z: Math.round(pos.z)
              }
            }
          });
        }
      }
    } else {
      lastPlayerPositions[trackedName] = { x: pos.x, y: pos.y, z: pos.z };
    }
  }, 250);

  // time_changed — fire at dawn/noon/dusk/midnight crossings
  bot.on('time', () => {
    const ticks = bot.time.timeOfDay;
    const label = getTimeLabel(ticks);
    if (label !== lastTimeLabel) {
      lastTimeLabel = label;
      broadcast({
        type: 'event',
        event: 'time_changed',
        data: { time_of_day: label, ticks }
      });
    }
  });

  // block_placed / block_broken — track player block changes
  // Mineflayer doesn't directly distinguish player vs bot block changes,
  // so we use blockUpdate and correlate with tracked player proximity.
  // For now, we use the digging and placing events that Mineflayer provides.

  // Mineflayer doesn't have great player-specific block events.
  // We track via the protocol-level packet events if available,
  // or approximate with blockUpdate + player proximity.
  // For v1, we emit block_placed when we observe block changes near the tracked player
  // but NOT when the bot is the one doing the action.

  let botIsActing = false;

  function setBotActing(acting) {
    botIsActing = acting;
  }

  // Use blockUpdate to detect changes
  bot.on('blockUpdate', (oldBlock, newBlock) => {
    if (botIsActing) return;
    const trackedName = getTrackedPlayer();
    if (!trackedName) return;

    const player = bot.players[trackedName];
    if (!player || !player.entity) return;

    const pos = newBlock.position;
    const playerPos = player.entity.position;
    const dist = pos.distanceTo(playerPos);

    // Only attribute to player if within reasonable interaction range
    if (dist > 8) return;

    if (oldBlock.name === 'air' && newBlock.name !== 'air') {
      broadcast({
        type: 'event',
        event: 'block_placed',
        data: {
          position: { x: pos.x, y: pos.y, z: pos.z },
          block_type: newBlock.name,
          player: trackedName
        }
      });
    } else if (oldBlock.name !== 'air' && newBlock.name === 'air') {
      broadcast({
        type: 'event',
        event: 'block_broken',
        data: {
          position: { x: pos.x, y: pos.y, z: pos.z },
          block_type: oldBlock.name,
          player: trackedName
        }
      });
    }
  });

  // entity_nearby / entity_gone — 16-block radius
  const ENTITY_RADIUS = 16;
  const ENTITY_CHECK_INTERVAL = 1000;

  setInterval(() => {
    const trackedName = getTrackedPlayer();
    const checkPositions = [bot.entity.position];
    if (trackedName) {
      const player = bot.players[trackedName];
      if (player && player.entity) {
        checkPositions.push(player.entity.position);
      }
    }

    const currentNearby = new Set();

    for (const entity of Object.values(bot.entities)) {
      if (entity === bot.entity) continue;
      if (entity.type !== 'mob') continue;

      const entityName = entity.name || entity.displayName || 'unknown';
      let minDist = Infinity;
      for (const refPos of checkPositions) {
        const d = entity.position.distanceTo(refPos);
        if (d < minDist) minDist = d;
      }

      if (minDist <= ENTITY_RADIUS) {
        const key = entity.id;
        currentNearby.add(key);

        if (!nearbyEntities.has(key)) {
          nearbyEntities.set(key, { type: entityName, reported: true });
          broadcast({
            type: 'event',
            event: 'entity_nearby',
            data: {
              entity_type: entityName,
              position: {
                x: Math.round(entity.position.x),
                y: Math.round(entity.position.y),
                z: Math.round(entity.position.z)
              },
              distance: Math.round(minDist),
              hostile: HOSTILE_MOBS.has(entityName)
            }
          });
        }
      }
    }

    // Check for entities that left
    for (const [key, info] of nearbyEntities.entries()) {
      if (!currentNearby.has(key)) {
        nearbyEntities.delete(key);
        broadcast({
          type: 'event',
          event: 'entity_gone',
          data: { entity_type: info.type }
        });
      }
    }
  }, ENTITY_CHECK_INTERVAL);

  // health_changed — bot health
  bot.on('health', () => {
    broadcast({
      type: 'event',
      event: 'health_changed',
      data: {
        entity: 'bot',
        health: Math.round(bot.health),
        max_health: 20
      }
    });
  });

  // game_mode_changed
  bot.on('game', () => {
    const trackedName = getTrackedPlayer();
    if (!trackedName) return;
    const player = bot.players[trackedName];
    if (!player) return;

    const modes = ['survival', 'creative', 'adventure', 'spectator'];
    const mode = modes[player.gamemode] || 'unknown';
    broadcast({
      type: 'event',
      event: 'game_mode_changed',
      data: { player: trackedName, mode }
    });
  });

  return { setBotActing };
}

module.exports = { setupEvents, HOSTILE_MOBS };
