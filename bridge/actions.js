'use strict';

const { goals } = require('mineflayer-pathfinder');

const DIRECTION_VECTORS = {
  north: { x: 0, y: 0, z: -1 },
  south: { x: 0, y: 0, z: 1 },
  east:  { x: 1, y: 0, z: 0 },
  west:  { x: -1, y: 0, z: 0 },
  up:    { x: 0, y: 1, z: 0 },
  down:  { x: 0, y: -1, z: 0 }
};

// Timeout table from BRIDGE_PROTOCOL.md
const TIMEOUTS = {
  move_to: 35000,
  move_to_player: 35000,
  place_block: 10000,
  dig_block: 10000,
  dig_area: 60000,
  craft: 15000,
  give: 10000,
  equip: 10000,
  get_position: 5000,
  get_player_position: 5000,
  find_blocks: 5000,
  find_player: 5000,
  get_inventory: 5000,
  get_block: 5000,
  say: 5000,
  collect: 120000,
  build_line: 60000,
  build_wall: 120000,
  get_world_state: 10000,
  validate_block_name: 5000,
  configure: 5000,
  cancel: 5000,
  disconnect: 5000
};

function withTimeout(promise, ms, label) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`TIMEOUT:${label}`));
    }, ms);
    promise
      .then((val) => { clearTimeout(timer); resolve(val); })
      .catch((err) => { clearTimeout(timer); reject(err); });
  });
}

function makeError(code, message, details = {}) {
  return { code, message, details };
}

function roundPos(pos) {
  return {
    x: Math.round(pos.x),
    y: Math.round(pos.y),
    z: Math.round(pos.z)
  };
}

function fuzzyMatch(name, validNames) {
  let best = null;
  let bestDist = Infinity;
  for (const valid of validNames) {
    const d = levenshtein(name.toLowerCase(), valid.toLowerCase());
    if (d < bestDist) {
      bestDist = d;
      best = valid;
    }
  }
  return bestDist <= 3 ? best : null;
}

function levenshtein(a, b) {
  const m = a.length, n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 0; i <= m; i++) dp[i][0] = i;
  for (let j = 0; j <= n; j++) dp[0][j] = j;
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }
  return dp[m][n];
}

function createActions(bot, mcData, sendProgress, setBotActingRaw) {
  const validBlockNames = new Set(
    Object.values(mcData.blocksByName).map(b => b.name)
  );
  const validItemNames = new Set(
    Object.values(mcData.itemsByName).map(i => i.name)
  );
  const allValidNames = new Set([...validBlockNames, ...validItemNames]);

  // Depth counter so compound actions can call primitive actions
  // without the inner finally block clearing the acting state.
  let actingDepth = 0;
  function setBotActing(acting) {
    if (acting) {
      actingDepth++;
      if (actingDepth === 1) setBotActingRaw(true);
    } else {
      actingDepth = Math.max(0, actingDepth - 1);
      if (actingDepth === 0) setBotActingRaw(false);
    }
  }

  function isValidBlockName(name) {
    return validBlockNames.has(name);
  }

  function isValidItemName(name) {
    return allValidNames.has(name);
  }

  async function navigateToRange(target, range = 4) {
    const goal = new goals.GoalNear(target.x, target.y, target.z, range);
    bot.pathfinder.setGoal(goal);
    return new Promise((resolve, reject) => {
      const onReached = () => {
        bot.removeListener('path_stop', onStopped);
        resolve();
      };
      const onStopped = (reason) => {
        bot.removeListener('goal_reached', onReached);
        if (reason === 'no_path') {
          reject(new Error('PATHFINDER_NO_PATH'));
        } else {
          reject(new Error('PATHFINDER_TIMEOUT'));
        }
      };
      bot.once('goal_reached', onReached);
      bot.once('path_stop', onStopped);
    });
  }

  const actions = {
    // === MOVEMENT ===

    async move_to(args) {
      const { x, y, z } = args;
      setBotActing(true);
      try {
        const goal = new goals.GoalBlock(x, y, z);
        bot.pathfinder.setGoal(goal);

        const result = await withTimeout(
          new Promise((resolve, reject) => {
            const onReached = () => {
              bot.removeListener('path_stop', onStopped);
              resolve(true);
            };
            const onStopped = (reason) => {
              bot.removeListener('goal_reached', onReached);
              if (reason === 'no_path') {
                reject(new Error('PATHFINDER_NO_PATH'));
              }
              resolve(false);
            };
            bot.once('goal_reached', onReached);
            bot.once('path_stop', onStopped);
          }),
          30000,
          'move_to'
        );

        return {
          success: true,
          data: { reached: result, final_position: roundPos(bot.entity.position) }
        };
      } catch (err) {
        bot.pathfinder.stop();
        if (err.message === 'PATHFINDER_NO_PATH') {
          return {
            success: false,
            data: null,
            error: makeError('PATHFINDER_NO_PATH', 'No path exists to the target', { target: { x, y, z } })
          };
        }
        return {
          success: false,
          data: null,
          error: makeError('PATHFINDER_TIMEOUT', `Could not find path to target within 30 seconds`, { target: { x, y, z } })
        };
      } finally {
        setBotActing(false);
      }
    },

    async move_to_player(args) {
      const { name, distance = 2 } = args;
      const player = bot.players[name];
      if (!player || !player.entity) {
        return {
          success: false,
          data: null,
          error: makeError('PLAYER_NOT_FOUND', `Player '${name}' not found in the world`)
        };
      }

      setBotActing(true);
      try {
        const goal = new goals.GoalFollow(player.entity, distance);
        bot.pathfinder.setGoal(goal, true); // dynamic

        const result = await withTimeout(
          new Promise((resolve, reject) => {
            const check = setInterval(() => {
              if (player.entity && bot.entity.position.distanceTo(player.entity.position) <= distance + 1) {
                clearInterval(check);
                bot.pathfinder.stop();
                resolve(true);
              }
            }, 500);
            const onStopped = (reason) => {
              clearInterval(check);
              if (reason === 'no_path') {
                reject(new Error('PATHFINDER_NO_PATH'));
              }
              resolve(false);
            };
            bot.once('path_stop', onStopped);
          }),
          30000,
          'move_to_player'
        );

        return {
          success: true,
          data: { reached: result, final_position: roundPos(bot.entity.position) }
        };
      } catch (err) {
        bot.pathfinder.stop();
        return {
          success: false,
          data: null,
          error: makeError('PATHFINDER_TIMEOUT', `Could not reach player '${name}' within 30 seconds`, { player: name })
        };
      } finally {
        setBotActing(false);
      }
    },

    // === BLOCK INTERACTION ===

    async place_block(args) {
      const { x, y, z, block_type } = args;
      if (!isValidBlockName(block_type) && !isValidItemName(block_type)) {
        const suggestion = fuzzyMatch(block_type, [...allValidNames]);
        return {
          success: false,
          data: null,
          error: makeError('INVALID_BLOCK_NAME', `'${block_type}' is not a valid block name`, { suggestion })
        };
      }

      const item = bot.inventory.items().find(i => i.name === block_type);
      if (!item) {
        return {
          success: false,
          data: null,
          error: makeError('ITEM_NOT_IN_INVENTORY', `Bot doesn't have any ${block_type}`)
        };
      }

      setBotActing(true);
      try {
        // Navigate to within placement range
        try {
          await withTimeout(navigateToRange({ x, y, z }, 4), 15000, 'navigate_to_place');
        } catch {
          return {
            success: false,
            data: null,
            error: makeError('BLOCK_NOT_REACHABLE', `Can't navigate to within placement range of (${x}, ${y}, ${z})`)
          };
        }

        // Check if block already exists at target — overwrite if so
        const existingBlock = bot.blockAt(bot.vec3(x, y, z));
        if (existingBlock && existingBlock.name !== 'air') {
          try {
            await bot.dig(existingBlock);
            await new Promise(resolve => setTimeout(resolve, 200)); // 200ms delay per protocol spec
          } catch {
            return {
              success: false,
              data: null,
              error: makeError('PLACEMENT_FAILED', `Could not break existing block at (${x}, ${y}, ${z}) for overwrite`)
            };
          }
        }

        // Equip the block
        await bot.equip(item, 'hand');

        // Find reference block and face vector
        const targetVec = bot.vec3(x, y, z);
        const adjacentOffsets = [
          { x: 0, y: -1, z: 0 },  // below
          { x: 0, y: 1, z: 0 },   // above
          { x: 1, y: 0, z: 0 },
          { x: -1, y: 0, z: 0 },
          { x: 0, y: 0, z: 1 },
          { x: 0, y: 0, z: -1 }
        ];

        let refBlock = null;
        let faceVec = null;
        for (const offset of adjacentOffsets) {
          const adjPos = targetVec.offset(offset.x, offset.y, offset.z);
          const block = bot.blockAt(adjPos);
          if (block && block.name !== 'air') {
            refBlock = block;
            faceVec = bot.vec3(-offset.x, -offset.y, -offset.z);
            break;
          }
        }

        if (!refBlock) {
          return {
            success: false,
            data: null,
            error: makeError('PLACEMENT_FAILED', `No adjacent block to place against at (${x}, ${y}, ${z})`)
          };
        }

        await bot.placeBlock(refBlock, faceVec);
        return { success: true, data: { placed: true } };
      } catch (err) {
        return {
          success: false,
          data: null,
          error: makeError('PLACEMENT_FAILED', err.message)
        };
      } finally {
        setBotActing(false);
      }
    },

    async dig_block(args) {
      const { x, y, z } = args;
      const block = bot.blockAt(bot.vec3(x, y, z));

      if (!block) {
        return {
          success: false,
          data: null,
          error: makeError('BLOCK_NOT_FOUND', `No block data at (${x}, ${y}, ${z}) — chunk may be unloaded`)
        };
      }

      if (block.name === 'air') {
        return {
          success: false,
          data: null,
          error: makeError('NO_BLOCK_AT_POSITION', `Position (${x}, ${y}, ${z}) contains air`)
        };
      }

      setBotActing(true);
      try {
        // Navigate to within dig range
        try {
          await withTimeout(navigateToRange({ x, y, z }, 4), 15000, 'navigate_to_dig');
        } catch {
          return {
            success: false,
            data: null,
            error: makeError('BLOCK_NOT_REACHABLE', `Can't navigate to within dig range of (${x}, ${y}, ${z})`)
          };
        }

        // Equip best tool
        const bestTool = bot.pathfinder.bestHarvestTool(block);
        if (bestTool) {
          await bot.equip(bestTool, 'hand');
        }

        // Re-query block fresh to avoid stale references
        const freshBlock = bot.blockAt(bot.vec3(x, y, z));
        if (!freshBlock || freshBlock.name === 'air') {
          return {
            success: false,
            data: null,
            error: makeError('NO_BLOCK_AT_POSITION', `Block already gone at (${x}, ${y}, ${z})`)
          };
        }

        const blockType = freshBlock.name;
        await bot.dig(freshBlock);
        return { success: true, data: { broken: true, block_type: blockType } };
      } catch (err) {
        return {
          success: false,
          data: null,
          error: makeError('BLOCK_NOT_REACHABLE', err.message)
        };
      } finally {
        setBotActing(false);
      }
    },

    async dig_area(args, cmdId) {
      const { x1, y1, z1, x2, y2, z2 } = args;

      const minX = Math.min(x1, x2), maxX = Math.max(x1, x2);
      const minY = Math.min(y1, y2), maxY = Math.max(y1, y2);
      const minZ = Math.min(z1, z2), maxZ = Math.max(z1, z2);

      const totalBlocks = (maxX - minX + 1) * (maxY - minY + 1) * (maxZ - minZ + 1);
      if (totalBlocks > 1000) {
        return {
          success: false,
          data: null,
          error: makeError('REGION_TOO_LARGE', `Region contains ${totalBlocks} blocks (cap is 1000)`)
        };
      }

      setBotActing(true);
      const blockTypes = {};
      let blocksBroken = 0;
      let lastProgressTime = 0;

      try {
        // Iterate top-down so blocks don't fall into gaps
        for (let y = maxY; y >= minY; y--) {
          for (let x = minX; x <= maxX; x++) {
            for (let z = minZ; z <= maxZ; z++) {
              // Check for cancellation
              if (bot._cancelledCommand === cmdId) {
                return {
                  success: false,
                  data: { partial: { blocks_broken: blocksBroken, blocks_total: totalBlocks, block_types: blockTypes } },
                  error: makeError('CANCELLED', 'Operation cancelled by client')
                };
              }

              const block = bot.blockAt(bot.vec3(x, y, z));
              if (!block || block.name === 'air') continue;

              try {
                await navigateToRange({ x, y, z }, 4);
                const bestTool = bot.pathfinder.bestHarvestTool(block);
                if (bestTool) await bot.equip(bestTool, 'hand');

                const freshBlock = bot.blockAt(bot.vec3(x, y, z));
                if (freshBlock && freshBlock.name !== 'air') {
                  const name = freshBlock.name;
                  await bot.dig(freshBlock);
                  blocksBroken++;
                  blockTypes[name] = (blockTypes[name] || 0) + 1;

                  const now = Date.now();
                  if (now - lastProgressTime >= 1000) {
                    lastProgressTime = now;
                    sendProgress(cmdId, { blocks_broken: blocksBroken, blocks_total: totalBlocks });
                  }
                }
              } catch {
                // Skip blocks that can't be broken
              }
            }
          }
        }

        return {
          success: true,
          data: { blocks_broken: blocksBroken, block_types: blockTypes }
        };
      } finally {
        setBotActing(false);
      }
    },

    // === CRAFTING AND ITEMS ===

    async craft(args) {
      const { item_name, count = 1 } = args;
      const itemData = mcData.itemsByName[item_name];
      if (!itemData) {
        return {
          success: false,
          data: null,
          error: makeError('UNKNOWN_ITEM', `'${item_name}' is not a recognized item`)
        };
      }

      const recipes = bot.recipesFor(itemData.id);
      if (!recipes || recipes.length === 0) {
        return {
          success: false,
          data: null,
          error: makeError('RECIPE_NOT_FOUND', `No recipe found for '${item_name}'`)
        };
      }

      // Check if any recipe needs a crafting table
      const recipe = recipes[0];
      let craftingTable = null;

      if (recipe.requiresTable) {
        // Find nearby crafting table
        const tableBlock = bot.findBlock({
          matching: mcData.blocksByName['crafting_table'].id,
          maxDistance: 32
        });

        if (!tableBlock) {
          return {
            success: false,
            data: null,
            error: makeError('NO_CRAFTING_TABLE', 'Recipe requires a crafting table but none found nearby')
          };
        }

        setBotActing(true);
        try {
          await withTimeout(navigateToRange(tableBlock.position, 4), 15000, 'navigate_to_table');
        } catch {
          setBotActing(false);
          return {
            success: false,
            data: null,
            error: makeError('NO_CRAFTING_TABLE', 'Could not reach the crafting table')
          };
        }
        craftingTable = tableBlock;
      } else {
        setBotActing(true);
      }

      try {
        let crafted = 0;
        for (let i = 0; i < count; i++) {
          try {
            await bot.craft(recipe, 1, craftingTable);
            crafted++;
          } catch (err) {
            if (crafted === 0) {
              // Check what's missing
              const missing = {};
              if (recipe.ingredients) {
                for (const ingredient of recipe.ingredients) {
                  if (ingredient.id < 0) continue;
                  const ingredientItem = mcData.items[ingredient.id];
                  if (!ingredientItem) continue;
                  const have = bot.inventory.count(ingredient.id);
                  const need = ingredient.count || 1;
                  if (have < need) {
                    missing[ingredientItem.name] = need - have;
                  }
                }
              }
              return {
                success: false,
                data: null,
                error: makeError('MISSING_MATERIALS', `Not enough materials to craft '${item_name}'`, { missing })
              };
            }
            break; // Partial success
          }
        }
        return { success: true, data: { crafted } };
      } finally {
        setBotActing(false);
      }
    },

    async give(args) {
      const { item_name, count = 1 } = args;
      const item = bot.inventory.items().find(i => i.name === item_name);
      if (!item) {
        return {
          success: false,
          data: null,
          error: makeError('ITEM_NOT_IN_INVENTORY', `Bot doesn't have any ${item_name}`)
        };
      }

      // Find nearest player
      let nearestPlayer = null;
      let nearestDist = Infinity;
      for (const player of Object.values(bot.players)) {
        if (player.username === bot.username || !player.entity) continue;
        const dist = bot.entity.position.distanceTo(player.entity.position);
        if (dist < nearestDist) {
          nearestDist = dist;
          nearestPlayer = player;
        }
      }

      if (!nearestPlayer) {
        return {
          success: false,
          data: null,
          error: makeError('NO_PLAYER_NEARBY', 'No player found nearby to give items to')
        };
      }

      setBotActing(true);
      try {
        // Navigate to tossing range
        if (nearestDist > 3) {
          await withTimeout(navigateToRange(nearestPlayer.entity.position, 2), 15000, 'navigate_to_give');
        }

        const actualCount = Math.min(count, item.count);
        await bot.toss(item.type, item.metadata, actualCount);
        return { success: true, data: { given: actualCount } };
      } catch (err) {
        return {
          success: false,
          data: null,
          error: makeError('NO_PLAYER_NEARBY', err.message)
        };
      } finally {
        setBotActing(false);
      }
    },

    async equip(args) {
      const { item_name } = args;
      const item = bot.inventory.items().find(i => i.name === item_name);
      if (!item) {
        return {
          success: false,
          data: null,
          error: makeError('ITEM_NOT_IN_INVENTORY', `Bot doesn't have any ${item_name}`)
        };
      }

      try {
        await bot.equip(item, 'hand');
        // Small delay for rapid-equip bug (Mineflayer #1556)
        await new Promise(resolve => setTimeout(resolve, 100));
        return { success: true, data: { equipped: true } };
      } catch (err) {
        return {
          success: false,
          data: null,
          error: makeError('ITEM_NOT_IN_INVENTORY', err.message)
        };
      }
    },

    // === OBSERVATION ===

    async get_position() {
      return {
        success: true,
        data: roundPos(bot.entity.position)
      };
    },

    async get_player_position(args) {
      const { name } = args;
      const player = bot.players[name];
      if (!player) {
        return {
          success: false,
          data: null,
          error: makeError('PLAYER_NOT_FOUND', `Player '${name}' not found in the world`)
        };
      }
      if (!player.entity) {
        return { success: true, data: null };
      }
      return {
        success: true,
        data: roundPos(player.entity.position)
      };
    },

    async find_blocks(args) {
      const { block_type, count = 1, max_distance = 32 } = args;
      if (!isValidBlockName(block_type)) {
        const suggestion = fuzzyMatch(block_type, [...validBlockNames]);
        return {
          success: false,
          data: null,
          error: makeError('INVALID_BLOCK_NAME', `'${block_type}' is not a valid block name`, { suggestion })
        };
      }

      const blockData = mcData.blocksByName[block_type];
      const positions = bot.findBlocks({
        matching: blockData.id,
        maxDistance: Math.min(max_distance, 128),
        count
      });

      return {
        success: true,
        data: {
          positions: positions.map(p => ({ x: p.x, y: p.y, z: p.z }))
        }
      };
    },

    async find_player(args) {
      const { name } = args;
      const player = bot.players[name];
      if (!player || !player.entity) {
        return { success: true, data: null };
      }
      return {
        success: true,
        data: roundPos(player.entity.position)
      };
    },

    async get_inventory() {
      const items = bot.inventory.items().map(item => ({
        name: item.name,
        count: item.count
      }));
      return { success: true, data: { items } };
    },

    async get_block(args) {
      const { x, y, z } = args;
      const block = bot.blockAt(bot.vec3(x, y, z));
      if (!block) {
        return { success: true, data: { block_type: 'air' } };
      }
      return { success: true, data: { block_type: block.name } };
    },

    // === COMMUNICATION ===

    async say(args) {
      const { message } = args;
      bot.chat(message);
      return { success: true, data: { sent: true } };
    },

    // === COMPOUND ACTIONS ===

    async collect(args, cmdId) {
      const { block_type, count } = args;
      if (!isValidBlockName(block_type)) {
        const suggestion = fuzzyMatch(block_type, [...validBlockNames]);
        return {
          success: false,
          data: null,
          error: makeError('INVALID_BLOCK_NAME', `'${block_type}' is not a valid block name`, { suggestion })
        };
      }

      setBotActing(true);
      let collected = 0;
      let lastProgressTime = 0;

      try {
        for (let i = 0; i < count; i++) {
          if (bot._cancelledCommand === cmdId) {
            return {
              success: false,
              data: { partial: { collected, target: count } },
              error: makeError('CANCELLED', 'Operation cancelled by client')
            };
          }

          const blockData = mcData.blocksByName[block_type];
          const blockPositions = bot.findBlocks({
            matching: blockData.id,
            maxDistance: 32,
            count: 1
          });

          if (blockPositions.length === 0) {
            if (collected === 0) {
              return {
                success: false,
                data: null,
                error: makeError('NO_BLOCKS_FOUND', `No ${block_type} blocks found within search radius`)
              };
            }
            break; // Partial — ran out of blocks
          }

          const pos = blockPositions[0];
          try {
            await navigateToRange(pos, 4);
            const block = bot.blockAt(bot.vec3(pos.x, pos.y, pos.z));
            if (block && block.name !== 'air') {
              const bestTool = bot.pathfinder.bestHarvestTool(block);
              if (bestTool) await bot.equip(bestTool, 'hand');
              await bot.dig(block);
              collected++;

              const now = Date.now();
              if (now - lastProgressTime >= 1000) {
                lastProgressTime = now;
                sendProgress(cmdId, { collected_so_far: collected, target: count });
              }
            }
          } catch {
            if (collected === 0) {
              return {
                success: false,
                data: null,
                error: makeError('COLLECTION_INTERRUPTED', `Failed to collect ${block_type}`)
              };
            }
            break;
          }
        }

        return { success: true, data: { collected } };
      } finally {
        setBotActing(false);
      }
    },

    async build_line(args, cmdId) {
      const { x, y, z, direction, length, block_type } = args;

      if (!DIRECTION_VECTORS[direction]) {
        return {
          success: false,
          data: null,
          error: makeError('INVALID_DIRECTION', `'${direction}' is not a valid direction. Use: north, south, east, west, up, down`)
        };
      }

      if (!isValidBlockName(block_type) && !isValidItemName(block_type)) {
        const suggestion = fuzzyMatch(block_type, [...allValidNames]);
        return {
          success: false,
          data: null,
          error: makeError('INVALID_BLOCK_NAME', `'${block_type}' is not a valid block name`, { suggestion })
        };
      }

      const item = bot.inventory.items().find(i => i.name === block_type);
      if (!item || item.count < length) {
        return {
          success: false,
          data: null,
          error: makeError('ITEM_NOT_IN_INVENTORY', `Bot needs ${length} ${block_type} but has ${item ? item.count : 0}`)
        };
      }

      const dir = DIRECTION_VECTORS[direction];
      setBotActing(true);
      let blocksPlaced = 0;
      let lastProgressTime = 0;

      try {
        for (let i = 0; i < length; i++) {
          if (bot._cancelledCommand === cmdId) {
            return {
              success: false,
              data: { partial: { blocks_placed: blocksPlaced, blocks_total: length } },
              error: makeError('CANCELLED', 'Operation cancelled by client')
            };
          }

          const bx = x + dir.x * i;
          const by = y + dir.y * i;
          const bz = z + dir.z * i;

          const result = await actions.place_block({ x: bx, y: by, z: bz, block_type });
          if (result.success) {
            blocksPlaced++;

            const now = Date.now();
            if (now - lastProgressTime >= 1000) {
              lastProgressTime = now;
              sendProgress(cmdId, { blocks_placed: blocksPlaced, blocks_total: length });
            }
          } else if (result.error && result.error.code !== 'PLACEMENT_FAILED') {
            // Fatal error (not just a single-block failure)
            if (blocksPlaced === 0) return result;
            break;
          }
        }

        return { success: true, data: { blocks_placed: blocksPlaced } };
      } finally {
        setBotActing(false);
      }
    },

    async build_wall(args, cmdId) {
      const { x, y, z, direction, length, height, block_type } = args;

      if (!DIRECTION_VECTORS[direction]) {
        return {
          success: false,
          data: null,
          error: makeError('INVALID_DIRECTION', `'${direction}' is not a valid direction. Use: north, south, east, west, up, down`)
        };
      }

      if (!isValidBlockName(block_type) && !isValidItemName(block_type)) {
        const suggestion = fuzzyMatch(block_type, [...allValidNames]);
        return {
          success: false,
          data: null,
          error: makeError('INVALID_BLOCK_NAME', `'${block_type}' is not a valid block name`, { suggestion })
        };
      }

      const totalBlocks = length * height;
      const item = bot.inventory.items().find(i => i.name === block_type);
      if (!item || item.count < totalBlocks) {
        return {
          success: false,
          data: null,
          error: makeError('ITEM_NOT_IN_INVENTORY', `Bot needs ${totalBlocks} ${block_type} but has ${item ? item.count : 0}`)
        };
      }

      const dir = DIRECTION_VECTORS[direction];
      setBotActing(true);
      let blocksPlaced = 0;
      let lastProgressTime = 0;

      try {
        // Build row by row from bottom to top
        for (let row = 0; row < height; row++) {
          for (let col = 0; col < length; col++) {
            if (bot._cancelledCommand === cmdId) {
              return {
                success: false,
                data: { partial: { blocks_placed: blocksPlaced, blocks_total: totalBlocks } },
                error: makeError('CANCELLED', 'Operation cancelled by client')
              };
            }

            const bx = x + dir.x * col;
            const by = y + row;
            const bz = z + dir.z * col;

            // setBotActing is already true from outer scope; avoid double-set
            // Call place_block logic inline to avoid setBotActing toggling
            const result = await actions.place_block({ x: bx, y: by, z: bz, block_type });
            if (result.success) {
              blocksPlaced++;

              const now = Date.now();
              if (now - lastProgressTime >= 1000) {
                lastProgressTime = now;
                sendProgress(cmdId, {
                  blocks_placed: blocksPlaced,
                  blocks_total: totalBlocks,
                  current_row: row + 1
                });
              }
            }
          }
        }

        return { success: true, data: { blocks_placed: blocksPlaced } };
      } finally {
        setBotActing(false);
      }
    },

    // === QUERIES ===

    async get_world_state() {
      const botPos = bot.entity.position;

      // Players
      const players = [];
      for (const player of Object.values(bot.players)) {
        if (player.username === bot.username) continue;
        if (!player.entity) continue;
        players.push({
          name: player.username,
          position: roundPos(player.entity.position),
          distance: Math.round(bot.entity.position.distanceTo(player.entity.position) * 10) / 10
        });
      }

      // Nearby blocks — 16-block radius scan
      const nearbyBlocks = {};
      const radius = 16;
      for (let dx = -radius; dx <= radius; dx++) {
        for (let dy = -radius; dy <= radius; dy++) {
          for (let dz = -radius; dz <= radius; dz++) {
            const block = bot.blockAt(botPos.offset(dx, dy, dz));
            if (block && block.name !== 'air') {
              nearbyBlocks[block.name] = (nearbyBlocks[block.name] || 0) + 1;
            }
          }
        }
      }

      // Nearby entities
      const nearbyEntities = [];
      for (const entity of Object.values(bot.entities)) {
        if (entity === bot.entity) continue;
        if (entity.type !== 'mob') continue;
        const dist = entity.position.distanceTo(botPos);
        if (dist <= 16) {
          const entityName = entity.name || entity.displayName || 'unknown';
          nearbyEntities.push({
            entity_type: entityName,
            position: roundPos(entity.position),
            distance: Math.round(dist * 10) / 10,
            hostile: require('./events').HOSTILE_MOBS.has(entityName)
          });
        }
      }

      // Time
      const ticks = bot.time.timeOfDay;
      const timeLabels = ['dawn', 'noon', 'dusk', 'midnight'];
      const timeLabel = ticks < 6000 ? 'dawn' : ticks < 12000 ? 'noon' : ticks < 18000 ? 'dusk' : 'midnight';

      // Game mode
      const modes = ['survival', 'creative', 'adventure', 'spectator'];

      return {
        success: true,
        data: {
          bot: {
            position: roundPos(botPos),
            health: Math.round(bot.health),
            food: Math.round(bot.food),
            inventory: bot.inventory.items().map(i => ({ name: i.name, count: i.count }))
          },
          players,
          time: { time_of_day: timeLabel, ticks },
          game_mode: modes[bot.game.gameMode] || 'unknown',
          nearby_blocks: nearbyBlocks,
          nearby_entities: nearbyEntities
        }
      };
    },

    async validate_block_name(args) {
      const { name } = args;
      const valid = allValidNames.has(name);
      const suggestion = valid ? null : fuzzyMatch(name, [...allValidNames]);
      return {
        success: true,
        data: { valid, suggestion }
      };
    }
  };

  return actions;
}

module.exports = { createActions, TIMEOUTS, DIRECTION_VECTORS };
