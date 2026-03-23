# Silicon Golem — Bridge Protocol Specification

## Overview

The bridge is a WebSocket connection between the Python orchestrator and the Node.js Mineflayer bot. The Python side sends commands and receives responses. The Node side pushes unsolicited events for world state changes. The protocol is JSON over WebSocket text frames.

**Transport:** WebSocket. Node side uses `ws` package, Python side uses `websockets`. Default port: `3001`.

**Connection model:** The Python orchestrator is the client. The Node bridge is the server. One connection per session. If the connection drops, the Python side reconnects with exponential backoff. The Node side maintains bot state across reconnections — the bot stays in the Minecraft world.

---

## Message Envelope

Every message is a JSON object with a `type` field that determines its structure.

### Command (Python → Node)

```json
{
  "type": "command",
  "id": "uuid-v4",
  "action": "place_block",
  "args": { "x": 10, "y": 64, "z": 20, "block_type": "cobblestone" }
}
```

- `id` — Unique identifier for request-response correlation. Python generates, Node echoes in response.
- `action` — One of the defined action names below.
- `args` — Action-specific arguments.

### Response (Node → Python)

```json
{
  "type": "response",
  "id": "uuid-v4",
  "success": true,
  "data": { "placed": true },
  "error": null
}
```

- `id` — Echoes the command's `id`.
- `success` — Boolean. `true` if the action completed, `false` on failure.
- `data` — Action-specific return value. `null` on failure.
- `error` — Error object on failure, `null` on success.

Error object structure:
```json
{
  "code": "PATHFINDER_TIMEOUT",
  "message": "Could not find path to target within 30 seconds",
  "details": { "target": { "x": 10, "y": 64, "z": 20 } }
}
```

### Event (Node → Python, unsolicited)

```json
{
  "type": "event",
  "event": "block_placed",
  "data": { "position": { "x": 10, "y": 64, "z": 20 }, "block_type": "cobblestone", "player": "Alex" }
}
```

- `event` — One of the defined event names below.
- `data` — Event-specific payload.

### Progress (Node → Python, during compound commands)

```json
{
  "type": "progress",
  "id": "uuid-v4",
  "data": { "blocks_placed": 12, "blocks_total": 25, "current_action": "place_block" }
}
```

- `id` — Echoes the compound command's `id`. Lets the Python side associate progress with the original request.
- `data` — Compound-specific progress information.

Progress messages are informational — they don't require acknowledgment. The final response message signals completion.

**Frequency cap:** Progress events are sent at most once per second, even if multiple sub-operations complete within that window. The latest state is sent, not a batch. This prevents chat spam when block placement happens faster than narration can keep up (e.g., 3 blocks/second on a fast server).

---

## Actions: Primitives

Each primitive action maps to one Mineflayer operation. The Python SDK wraps these as synchronous calls.

### Movement

#### `move_to`

Walk to coordinates using pathfinder.

```
args: { "x": int, "y": int, "z": int }
data: { "reached": bool, "final_position": { "x": int, "y": int, "z": int } }
```

Node-side behavior: Sets `GoalBlock(x, y, z)` with a 30-second timeout. Returns `reached: false` on timeout or no-path, with the bot's actual final position.

Error codes: `PATHFINDER_TIMEOUT`, `PATHFINDER_NO_PATH`.

#### `move_to_player`

Walk to a named player.

```
args: { "name": str, "distance": int (default 2) }
data: { "reached": bool, "final_position": { "x": int, "y": int, "z": int } }
```

Node-side behavior: Sets `GoalFollow` with `dynamic: true` (required — static goal won't track moving player). Stops when within `distance` blocks. 30-second timeout.

Error codes: `PATHFINDER_TIMEOUT`, `PLAYER_NOT_FOUND`.

### Block Interaction

#### `place_block`

Place a block at coordinates.

```
args: { "x": int, "y": int, "z": int, "block_type": str }
data: { "placed": bool }
```

Node-side behavior: Checks inventory for `block_type`. Equips it. Navigates to within placement range (4 blocks). Computes the reference block and face vector from target coordinates (the SDK hides Mineflayer's `referenceBlock` / `faceVector` API). Places.

**Block overwriting:** If the target position already contains a block, the bridge breaks the existing block first, then places the new one. This mirrors how Minecraft players build — they don't clear first, they just place. If the existing block can't be broken (bedrock, insufficient tool), `PLACEMENT_FAILED` is returned.

Error codes: `ITEM_NOT_IN_INVENTORY`, `BLOCK_NOT_REACHABLE`, `INVALID_BLOCK_NAME`, `PLACEMENT_FAILED`.

On `INVALID_BLOCK_NAME`, include `suggestion` in error details (fuzzy match against valid MC 1.20.4 block names).

#### `dig_block`

Break a block at coordinates.

```
args: { "x": int, "y": int, "z": int }
data: { "broken": bool, "block_type": str }
```

Node-side behavior: Navigates to within dig range. Equips best available tool. Queries `bot.blockAt()` fresh (avoids stale references). Digs.

Error codes: `BLOCK_NOT_FOUND`, `BLOCK_NOT_REACHABLE`, `NO_BLOCK_AT_POSITION` (air).

#### `dig_area`

Break all blocks in a rectangular region.

```
args: { "x1": int, "y1": int, "z1": int, "x2": int, "y2": int, "z2": int }
data: { "blocks_broken": int, "block_types": { "cobblestone": 5, "dirt": 12 } }
progress: { "blocks_broken": int, "blocks_total": int }
```

Node-side behavior: Iterates through the cuboid, breaking each non-air block. Although it's a single SDK function (Tier 1), its execution is multi-step internally — the Node side handles the iteration and sends progress events. The Python side sends one command and receives progress updates until the final response.

Error codes: `REGION_TOO_LARGE` (cap at 1000 blocks to prevent accidental world destruction).

### Crafting and Items

#### `craft`

Craft an item.

```
args: { "item_name": str, "count": int (default 1) }
data: { "crafted": int }
```

Node-side behavior: Looks up recipe. If crafting table required, finds or navigates to nearest. Crafts up to `count` (may craft fewer if materials run out). Returns actual count crafted.

Error codes: `UNKNOWN_ITEM`, `MISSING_MATERIALS`, `NO_CRAFTING_TABLE`, `RECIPE_NOT_FOUND`.

On `MISSING_MATERIALS`, include `missing` in details: `{ "missing": { "iron_ingot": 2 } }`.

#### `give`

Give items to nearest player.

```
args: { "item_name": str, "count": int (default 1) }
data: { "given": int }
```

Node-side behavior: Navigates to within tossing range of nearest player. Drops items. Returns actual count given (may be less if inventory has fewer).

Error codes: `ITEM_NOT_IN_INVENTORY`, `NO_PLAYER_NEARBY`.

#### `equip`

Hold an item.

```
args: { "item_name": str }
data: { "equipped": bool }
```

Node-side behavior: Equips to hand slot. Includes a small delay to work around the rapid-equip server rejection bug (Mineflayer issue #1556).

Error codes: `ITEM_NOT_IN_INVENTORY`.

### Observation

These are read-only queries. They don't change world state.

#### `get_position`

Get the bot's current position.

```
args: { }
data: { "x": int, "y": int, "z": int }
```

Coordinates are rounded to integers.

#### `get_player_position`

Get a player's current position.

```
args: { "name": str }
data: { "x": int, "y": int, "z": int } | null
```

Returns `null` data with `success: true` if the player exists but position is unknown. Returns error if player not found at all.

Error codes: `PLAYER_NOT_FOUND`.

#### `find_blocks`

Find nearby blocks of a type.

```
args: { "block_type": str, "count": int (default 1), "max_distance": int (default 32) }
data: { "positions": [ { "x": int, "y": int, "z": int }, ... ] }
```

Node-side behavior: Uses `bot.findBlocks` with `bot.blockAt` to return proper position objects. Capped at `max_distance` to prevent performance issues (>2.5s at distance 128 with rare blocks).

Error codes: `INVALID_BLOCK_NAME`.

#### `find_player`

Find a player's position.

```
args: { "name": str }
data: { "x": int, "y": int, "z": int } | null
```

Returns `null` data with `success: true` if player not found (not an error — the SDK function returns `None`).

#### `get_inventory`

Get the bot's inventory.

```
args: { }
data: { "items": [ { "name": str, "count": int }, ... ] }
```

Filters out empty slots.

#### `get_block`

Get the block type at coordinates.

```
args: { "x": int, "y": int, "z": int }
data: { "block_type": str }
```

Returns `"air"` for empty space. Returns `"air"` with a warning for unloaded chunks (null-check on `bot.blockAt`).

### Communication

#### `say`

Send a chat message in-game.

```
args: { "message": str }
data: { "sent": bool }
```

---

## Actions: Compounds

Compound actions map to multi-step Mineflayer operations. They are atomic from the Python side — one command, one response. During execution, the Node side sends progress events so the orchestrator can drive narration.

### `collect`

Find and break blocks of a type until count reached.

```
args: { "block_type": str, "count": int }
data: { "collected": int }
progress: { "collected_so_far": int, "target": int }
```

Node-side behavior: Wraps `mineflayer-collectblock`. Pathfinds to nearest matching block, equips appropriate tool, digs, picks up, repeats. Sends progress after each block collected.

Error codes: `INVALID_BLOCK_NAME`, `NO_BLOCKS_FOUND`, `COLLECTION_INTERRUPTED`.

### `build_line`

Place blocks in a straight line.

```
args: { "x": int, "y": int, "z": int, "direction": str, "length": int, "block_type": str }
data: { "blocks_placed": int }
progress: { "blocks_placed": int, "blocks_total": int }
```

`direction` is one of: `"north"`, `"south"`, `"east"`, `"west"`, `"up"`, `"down"`.

Node-side behavior: Computes target positions from start + direction + length. For each position: navigates within placement range, computes reference block and face vector, places. Sends progress after each block.

Error codes: `ITEM_NOT_IN_INVENTORY`, `INVALID_BLOCK_NAME`, `INVALID_DIRECTION`, `PLACEMENT_FAILED`.

### `build_wall`

Place blocks in a rectangular wall.

```
args: { "x": int, "y": int, "z": int, "direction": str, "length": int, "height": int, "block_type": str }
data: { "blocks_placed": int }
progress: { "blocks_placed": int, "blocks_total": int, "current_row": int }
```

Node-side behavior: Builds row by row from bottom to top. Each row is a `build_line` operation. Sends progress after each block, with `current_row` for narration context.

Error codes: Same as `build_line`.

---

## Actions: Session Control

These actions manage the connection and bot lifecycle. They don't affect the Minecraft world.

### `configure`

Set session parameters. Must be sent once after receiving the `ready` event.

```
args: { "track_player": str }
data: { "configured": true, "tracked_player_found": bool }
```

`track_player` — The name of the kid to track. The bridge streams events for this player and uses their position for relative calculations. If the player isn't in the world yet, `tracked_player_found` is `false` and the bridge begins streaming events once they join.

### `cancel`

Cancel an in-progress command.

```
args: { }
```

Send with the same `id` as the command to cancel. The Node side attempts to stop the operation (interrupts pathfinder, stops block placement loop). The original command responds with:

```json
{
  "type": "response",
  "id": "original-command-id",
  "success": false,
  "data": { "partial": { "blocks_placed": 47, "blocks_total": 100 } },
  "error": { "code": "CANCELLED", "message": "Operation cancelled by client", "details": {} }
}
```

The `data.partial` field contains whatever was accomplished before cancellation. Its shape depends on the original action — `blocks_placed`/`blocks_total` for build commands, `collected`/`target` for collect, etc. The chat agent can use this for narration: "I got about halfway done before I had to stop."

### `disconnect`

Graceful shutdown.

```
args: { "reason": str }
data: { "disconnected": true }
```

The bridge disconnects the bot from the MC server after responding. If the WebSocket closes without a disconnect command, the bridge keeps the bot in-world for 60 seconds (in case of reconnect), then disconnects.

---

## Events: World State Stream

The Node side pushes these events as they occur. The Python orchestrator uses them for challenge trigger evaluation, world context assembly, and learner model input. Events are fire-and-forget — no acknowledgment from the Python side.

### Lightweight continuous events (always streaming)

#### `player_moved`

Sent when the tracked player moves more than 1 block from their last reported position. Not sent on every tick — debounced to avoid flooding.

```json
{ "type": "event", "event": "player_moved", "data": { "name": "Alex", "position": { "x": 100, "y": 64, "z": -200 } } }
```

#### `time_changed`

Sent when Minecraft time-of-day crosses a threshold (dawn, noon, dusk, midnight).

```json
{ "type": "event", "event": "time_changed", "data": { "time_of_day": "dusk", "ticks": 12000 } }
```

Time-of-day labels: `"dawn"` (0-6000), `"noon"` (6000-12000), `"dusk"` (12000-18000), `"midnight"` (18000-24000). Sent once at each crossing.

#### `player_chat`

Sent when any player sends a chat message. This is the primary input path — the kid's chat messages arrive here.

```json
{ "type": "event", "event": "player_chat", "data": { "name": "Alex", "message": "hey golem build me a wall" } }
```

#### `player_joined`

```json
{ "type": "event", "event": "player_joined", "data": { "name": "Steve" } }
```

#### `player_left`

```json
{ "type": "event", "event": "player_left", "data": { "name": "Steve" } }
```

### Game state events (on change)

#### `block_placed`

Sent when any player (not the bot) places a block.

```json
{ "type": "event", "event": "block_placed", "data": { "position": { "x": 10, "y": 64, "z": 20 }, "block_type": "cobblestone", "player": "Alex" } }
```

Used by the orchestrator to detect player activity patterns (building, digging) and to evaluate challenge triggers like "kid placed 12 cobblestone blocks in a line."

#### `block_broken`

Sent when any player (not the bot) breaks a block.

```json
{ "type": "event", "event": "block_broken", "data": { "position": { "x": 10, "y": 64, "z": 20 }, "block_type": "cobblestone", "player": "Alex" } }
```

#### `entity_nearby`

Sent when a mob enters within 16 blocks of the bot or tracked player. Sent once per entity (not continuously). Sent again if the entity leaves and returns.

```json
{ "type": "event", "event": "entity_nearby", "data": { "entity_type": "zombie", "position": { "x": 105, "y": 64, "z": -195 }, "distance": 12, "hostile": true } }
```

The `hostile` flag lets the orchestrator evaluate the "hostile mob approaching" abort condition without maintaining a mob classification table.

#### `entity_gone`

Sent when a previously reported nearby entity leaves the 16-block radius or is killed.

```json
{ "type": "event", "event": "entity_gone", "data": { "entity_type": "zombie" } }
```

#### `health_changed`

Sent when bot or tracked player health changes.

```json
{ "type": "event", "event": "health_changed", "data": { "entity": "bot", "health": 15, "max_health": 20 } }
```

#### `game_mode_changed`

```json
{ "type": "event", "event": "game_mode_changed", "data": { "player": "Alex", "mode": "creative" } }
```

### Code panel events (from web UI, relayed through bridge)

The code panel web UI connects to the same WebSocket server. It forwards user interaction events through the bridge to the Python orchestrator. The bridge relays them unchanged.

#### `code_panel_edit`

Kid modified code in the panel.

```json
{ "type": "event", "event": "code_panel_edit", "data": { "source": "from golem import *\n\nblock = \"glass\"\n...", "changes": [{ "line": 3, "old": "\"oak_planks\"", "new": "\"glass\"" }] } }
```

#### `code_panel_run`

Kid hit the re-run button in the panel.

```json
{ "type": "event", "event": "code_panel_run", "data": { "source": "from golem import *\n..." } }
```

#### `code_panel_scroll`

Kid scrolled through code in the panel. Debounced — sent once per scroll interaction, not per pixel.

```json
{ "type": "event", "event": "code_panel_scroll", "data": { "visible_lines": { "start": 1, "end": 20 }, "total_lines": 35 } }
```

---

## Queries: On-Demand World State

These are pull-based queries the Python orchestrator sends before agent invocations to assemble full world context. They use the command/response pattern but are read-only.

### `get_world_state`

Full snapshot for agent context assembly.

```
args: { }
data: {
  "bot": {
    "position": { "x": int, "y": int, "z": int },
    "health": int,
    "food": int,
    "inventory": [ { "name": str, "count": int }, ... ]
  },
  "players": [
    { "name": str, "position": { "x": int, "y": int, "z": int }, "distance": float }
  ],
  "time": { "time_of_day": str, "ticks": int },
  "game_mode": str,
  "nearby_blocks": { "cobblestone": 12, "dirt": 45, "grass_block": 30 },
  "nearby_entities": [
    { "entity_type": str, "position": { "x": int, "y": int, "z": int }, "distance": float, "hostile": bool }
  ]
}
```

`nearby_blocks` scans a 16-block radius and returns block type counts. This is the expensive query — avoid calling more than once per agent invocation cycle.

### `validate_block_name`

Check if a block/item name is valid for MC 1.20.4 and get fuzzy match suggestions.

```
args: { "name": str }
data: { "valid": bool, "suggestion": str | null }
```

Used by the SDK's error translation layer before surfacing "did you mean 'stone'?" messages.

---

## Error Codes Reference

| Code | Actions | Meaning |
|---|---|---|
| `PATHFINDER_TIMEOUT` | move_to, move_to_player | No path found within 30 seconds |
| `PATHFINDER_NO_PATH` | move_to | Pathfinder determined no path exists |
| `PLAYER_NOT_FOUND` | move_to_player, get_player_position | Named player not in the world |
| `ITEM_NOT_IN_INVENTORY` | place_block, give, equip | Bot doesn't have the requested item |
| `BLOCK_NOT_REACHABLE` | place_block, dig_block | Can't navigate to within interaction range |
| `BLOCK_NOT_FOUND` | dig_block | No block at the specified position |
| `NO_BLOCK_AT_POSITION` | dig_block | Position contains air |
| `INVALID_BLOCK_NAME` | place_block, find_blocks, collect, build_line, build_wall | Not a valid MC 1.20.4 block/item name |
| `INVALID_DIRECTION` | build_line, build_wall | Direction not one of north/south/east/west/up/down |
| `PLACEMENT_FAILED` | place_block, build_line, build_wall | Block placement failed (obstruction, server rejection) |
| `REGION_TOO_LARGE` | dig_area | Region exceeds 1000 block safety cap |
| `UNKNOWN_ITEM` | craft | Item name not recognized |
| `MISSING_MATERIALS` | craft | Insufficient materials (details include what's missing) |
| `NO_CRAFTING_TABLE` | craft | Recipe requires crafting table, none nearby |
| `RECIPE_NOT_FOUND` | craft | No recipe exists for this item |
| `NO_PLAYER_NEARBY` | give | No player within tossing range |
| `NO_BLOCKS_FOUND` | collect | No matching blocks within search radius |
| `COLLECTION_INTERRUPTED` | collect | Collection stopped early (pathfinder failure, obstruction) |
| `CANCELLED` | any | Operation cancelled by client via cancel command |

---

## Connection Lifecycle

### Startup Sequence

1. Node bridge starts, creates Mineflayer bot, connects to MC 1.20.4 LAN server.
2. Node bridge starts WebSocket server on port 3001.
3. Bot joins the world. Node bridge waits for `spawn` event.
4. Python orchestrator connects to WebSocket.
5. Node bridge sends a `ready` event:

```json
{ "type": "event", "event": "ready", "data": { "bot_name": "Golem", "mc_version": "1.20.4", "server": "localhost:25565" } }
```

6. Python orchestrator sends a `configure` command (see Session Control section) to set which player to track.
7. Bridge begins streaming events for the tracked player.

### Heartbeat

The bridge sends a heartbeat event every 10 seconds:

```json
{ "type": "event", "event": "heartbeat", "data": { "uptime_seconds": int, "bot_position": { "x": int, "y": int, "z": int }, "tracked_player_position": { "x": int, "y": int, "z": int } | null } }
```

If the Python side doesn't receive a heartbeat within 30 seconds, it assumes the connection is stale and reconnects.

### Shutdown

Python sends a `disconnect` command (see Session Control section) before closing. If the WebSocket closes without a disconnect command, the bridge keeps the bot in-world for 60 seconds (in case of reconnect), then disconnects.

---

## Implementation Notes

### Concurrency

The Python side sends commands and awaits responses. Only one command should be in-flight per logical operation (the SDK's synchronous API enforces this). However, events stream continuously and must be buffered by the Python side even while awaiting a command response.

The Node side handles one command at a time. If a second command arrives while the first is executing, it queues it. This prevents the bot from attempting to pathfind to two locations simultaneously.

### Timeout Handling

Every command has a default timeout on the Python side:

| Action | Timeout |
|---|---|
| move_to, move_to_player | 35 seconds (30s pathfinder + 5s overhead) |
| place_block, dig_block | 10 seconds |
| dig_area | 60 seconds |
| craft | 15 seconds |
| give, equip | 10 seconds |
| get_* (observations) | 5 seconds |
| say | 5 seconds |
| collect | 120 seconds |
| build_line | 60 seconds |
| build_wall | 120 seconds |
| get_world_state | 10 seconds |

If a timeout fires, the Python side sends a `cancel` command (see Session Control section). The original command responds with error code `CANCELLED` and includes partial completion data so the chat agent can narrate what was accomplished.

### Block Name Validation

The Node side maintains a set of valid block and item names for MC 1.20.4, loaded from `minecraft-data`. The `validate_block_name` query and `INVALID_BLOCK_NAME` error both use Levenshtein distance for fuzzy matching. The top suggestion (if distance ≤ 3) is included in the error response.
