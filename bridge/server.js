'use strict';

const mineflayer = require('mineflayer');
const { pathfinder, Movements } = require('mineflayer-pathfinder');
const collectBlock = require('mineflayer-collectblock').plugin;
const { WebSocketServer } = require('ws');
const minecraftData = require('minecraft-data');
const { Vec3 } = require('vec3');
const { createActions, TIMEOUTS } = require('./actions');
const { setupEvents } = require('./events');

// Configuration — can be overridden via environment variables
const MC_HOST = process.env.MC_HOST || 'localhost';
const MC_PORT = parseInt(process.env.MC_PORT || '25565', 10);
const WS_PORT = parseInt(process.env.WS_PORT || '3001', 10);
const BOT_NAME = process.env.BOT_NAME || 'Golem';
const MC_VERSION = '1.20.4';

// State
let trackedPlayer = null;
let currentCommand = null; // { id, action, resolve }
let disconnectTimer = null;

function getTrackedPlayer() {
  return trackedPlayer;
}

// Create bot
console.log(`[bridge] Connecting bot "${BOT_NAME}" to ${MC_HOST}:${MC_PORT} (MC ${MC_VERSION})`);

const bot = mineflayer.createBot({
  host: MC_HOST,
  port: MC_PORT,
  username: BOT_NAME,
  version: MC_VERSION
});

// Attach vec3 helper to bot for convenience
bot.vec3 = (x, y, z) => new Vec3(x, y, z);

// Load plugins
bot.loadPlugin(pathfinder);
bot.loadPlugin(collectBlock);

// Cancellation support
bot._cancelledCommand = null;

const mcData = minecraftData(MC_VERSION);

// Set up pathfinder defaults once spawned
bot.once('spawn', () => {
  const movements = new Movements(bot);
  movements.canDig = true;
  movements.allow1by1towers = true;
  bot.pathfinder.setMovements(movements);

  console.log(`[bridge] Bot spawned at ${Math.round(bot.entity.position.x)}, ${Math.round(bot.entity.position.y)}, ${Math.round(bot.entity.position.z)}`);

  startWebSocketServer();
});

bot.on('error', (err) => {
  console.error('[bridge] Bot error:', err.message);
});

bot.on('kicked', (reason) => {
  console.error('[bridge] Bot kicked:', reason);
  process.exit(1);
});

bot.on('end', () => {
  console.log('[bridge] Bot disconnected from MC server');
});

// WebSocket server
function startWebSocketServer() {
  const wss = new WebSocketServer({ port: WS_PORT });
  console.log(`[bridge] WebSocket server listening on port ${WS_PORT}`);

  function broadcast(msg) {
    const data = JSON.stringify(msg);
    for (const client of wss.clients) {
      if (client.readyState === 1) { // OPEN
        client.send(data);
      }
    }
  }

  function sendProgress(cmdId, progressData) {
    broadcast({
      type: 'progress',
      id: cmdId,
      data: progressData
    });
  }

  // Set up event streaming
  const { setBotActing } = setupEvents(bot, broadcast, getTrackedPlayer);

  // Create action handlers
  const actions = createActions(bot, mcData, sendProgress, setBotActing);

  // Heartbeat — every 10 seconds
  const heartbeatInterval = setInterval(() => {
    const trackedPos = trackedPlayer && bot.players[trackedPlayer] && bot.players[trackedPlayer].entity
      ? {
          x: Math.round(bot.players[trackedPlayer].entity.position.x),
          y: Math.round(bot.players[trackedPlayer].entity.position.y),
          z: Math.round(bot.players[trackedPlayer].entity.position.z)
        }
      : null;

    broadcast({
      type: 'event',
      event: 'heartbeat',
      data: {
        uptime_seconds: Math.round(process.uptime()),
        bot_position: {
          x: Math.round(bot.entity.position.x),
          y: Math.round(bot.entity.position.y),
          z: Math.round(bot.entity.position.z)
        },
        tracked_player_position: trackedPos
      }
    });
  }, 10000);

  wss.on('connection', (ws) => {
    console.log('[bridge] Client connected');

    // Clear disconnect timer if reconnecting
    if (disconnectTimer) {
      clearTimeout(disconnectTimer);
      disconnectTimer = null;
      console.log('[bridge] Reconnect — cleared disconnect timer');
    }

    // Send ready event
    ws.send(JSON.stringify({
      type: 'event',
      event: 'ready',
      data: {
        bot_name: BOT_NAME,
        mc_version: MC_VERSION,
        server: `${MC_HOST}:${MC_PORT}`
      }
    }));

    ws.on('message', async (raw) => {
      let msg;
      try {
        msg = JSON.parse(raw.toString());
      } catch {
        ws.send(JSON.stringify({
          type: 'response',
          id: null,
          success: false,
          data: null,
          error: { code: 'INVALID_MESSAGE', message: 'Could not parse JSON', details: {} }
        }));
        return;
      }

      if (msg.type !== 'command') {
        // Relay code panel events from web UI through to all clients
        if (msg.type === 'event' && ['code_panel_edit', 'code_panel_run', 'code_panel_scroll'].includes(msg.event)) {
          broadcast(msg);
        }
        return;
      }

      const { id, action, args = {} } = msg;

      // Handle cancel
      if (action === 'cancel') {
        if (currentCommand) {
          bot._cancelledCommand = currentCommand.id;
          bot.pathfinder.stop();
          // The original command will detect cancellation and respond
          ws.send(JSON.stringify({
            type: 'response',
            id,
            success: true,
            data: { cancelling: currentCommand.id },
            error: null
          }));
        } else {
          ws.send(JSON.stringify({
            type: 'response',
            id,
            success: true,
            data: { cancelling: null },
            error: null
          }));
        }
        return;
      }

      // Handle configure
      if (action === 'configure') {
        trackedPlayer = args.track_player || null;
        const found = trackedPlayer && bot.players[trackedPlayer] && bot.players[trackedPlayer].entity;
        ws.send(JSON.stringify({
          type: 'response',
          id,
          success: true,
          data: { configured: true, tracked_player_found: !!found },
          error: null
        }));
        console.log(`[bridge] Configured: tracking player "${trackedPlayer}" (found: ${!!found})`);
        return;
      }

      // Handle disconnect
      if (action === 'disconnect') {
        ws.send(JSON.stringify({
          type: 'response',
          id,
          success: true,
          data: { disconnected: true },
          error: null
        }));
        console.log(`[bridge] Disconnect requested: ${args.reason || 'no reason'}`);
        setTimeout(() => {
          bot.quit();
          process.exit(0);
        }, 500);
        return;
      }

      // BUSY check — one command at a time
      if (currentCommand) {
        ws.send(JSON.stringify({
          type: 'response',
          id,
          success: false,
          data: null,
          error: { code: 'BUSY', message: `Already executing command '${currentCommand.action}'`, details: { busy_with: currentCommand.id } }
        }));
        return;
      }

      // Look up action handler
      const handler = actions[action];
      if (!handler) {
        ws.send(JSON.stringify({
          type: 'response',
          id,
          success: false,
          data: null,
          error: { code: 'UNKNOWN_ACTION', message: `Unknown action '${action}'`, details: {} }
        }));
        return;
      }

      // Execute with timeout
      currentCommand = { id, action };
      bot._cancelledCommand = null;
      const timeout = TIMEOUTS[action] || 30000;

      try {
        const resultPromise = handler(args, id);
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => reject(new Error('COMMAND_TIMEOUT')), timeout);
        });

        const result = await Promise.race([resultPromise, timeoutPromise]);

        ws.send(JSON.stringify({
          type: 'response',
          id,
          success: result.success,
          data: result.data,
          error: result.error || null
        }));
      } catch (err) {
        if (err.message === 'COMMAND_TIMEOUT') {
          bot.pathfinder.stop();
          ws.send(JSON.stringify({
            type: 'response',
            id,
            success: false,
            data: null,
            error: { code: 'CANCELLED', message: `Command '${action}' timed out`, details: {} }
          }));
        } else {
          ws.send(JSON.stringify({
            type: 'response',
            id,
            success: false,
            data: null,
            error: { code: 'INTERNAL_ERROR', message: err.message, details: {} }
          }));
        }
      } finally {
        currentCommand = null;
      }
    });

    ws.on('close', () => {
      console.log('[bridge] Client disconnected');
      // Keep bot in-world for 60 seconds in case of reconnect
      disconnectTimer = setTimeout(() => {
        console.log('[bridge] No reconnect after 60 seconds — disconnecting bot');
        bot.quit();
        process.exit(0);
      }, 60000);
    });

    ws.on('error', (err) => {
      console.error('[bridge] WebSocket error:', err.message);
    });
  });

  // Clean up on process exit
  process.on('SIGINT', () => {
    console.log('[bridge] Shutting down...');
    clearInterval(heartbeatInterval);
    wss.close();
    bot.quit();
    process.exit(0);
  });
}
