# Bridge Implementation Handoff — Claude Code

## Task

Build the Mineflayer bridge: a Node.js WebSocket server that hosts a Minecraft bot and exposes the full action/event/query protocol defined in BRIDGE_PROTOCOL.md.

## Read First (in this order)

1. `CLAUDE.md` — project context and conventions
2. `BRIDGE_PROTOCOL.md` — the wire protocol spec (this is your contract, implement it exactly)
3. `DECISIONS.md` — ADR-002 (Mineflayer) and ADR-003 (agent topology) for architectural context
4. `GOLEM_SDK.md` — sections on compound commands for behavioral context on what build_line, build_wall, collect should do

## Target Files

```
bridge/
├── server.js          # Main entry: Mineflayer bot + WebSocket server
├── actions.js         # Action handlers (one function per action)
├── events.js          # Event emitters (world state → WebSocket events)
├── package.json       # Dependencies: mineflayer, mineflayer-pathfinder, mineflayer-collectblock, ws
└── test/
    └── test_bridge.js # Integration tests against a real MC 1.20.4 server
```

Split into modules if server.js exceeds ~300 lines, but keep it simple. One file is fine if it stays readable.

## Key Constraints

- **Minecraft 1.20.4 specifically.** Pin the version in mineflayer config. Do not use version auto-detection.
- **Node 18+.** Use `ws` package for WebSocket server.
- **Dependencies:** `mineflayer`, `mineflayer-pathfinder`, `mineflayer-collectblock`, `ws`, `uuid`. Nothing else unless justified.
- **Concurrency:** One command in-flight at a time. If a command arrives while another is executing, respond with error code `BUSY`.
- **Timeouts:** Implement the timeout table from BRIDGE_PROTOCOL.md §Implementation Notes. Use the pathfinder timeout wrapper pattern (race Promise against setTimeout).
- **Progress streaming:** Compound actions (collect, build_line, build_wall) must emit progress messages. Cap at 1 per second per the protocol spec.
- **Heartbeat:** Implement the 10-second ping/pong cycle from §Connection Lifecycle.
- **Error mapping:** Map Mineflayer exceptions to the 19 error codes in BRIDGE_PROTOCOL.md §Error Codes. Use the action→error mapping table.
- **Events:** Implement all 12 event types. player_moved fires on >1 block displacement with 500ms throttle. Code panel events (code_panel_edit, code_panel_run, code_panel_scroll) come FROM the Python side — don't implement emission for those, just pass through if received.
- **configure and cancel:** Implement as specified — configure sets tracked player, cancel terminates in-flight command and returns partial completion data.
- **Block overwriting:** place_block must dig existing block first, with 200ms delay per protocol spec.

## What "Done" Looks Like

- `npm start` launches the bot, connects to a local MC 1.20.4 server, and opens a WebSocket on port 3001
- A Python script can connect, send `get_position`, and get a valid response
- All 15 primitive actions work
- All 3 compound actions work with progress streaming
- configure/cancel/disconnect work
- Events stream when world changes occur
- Tests exist for at least: connection lifecycle, each primitive action, error handling for invalid args, timeout behavior, and the busy-rejection path
