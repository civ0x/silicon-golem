# SDK Implementation Handoff — Claude Code

## Task

Build `golem/sdk.py` — the Python SDK that the kid's generated code imports via `from golem import *`. It exposes synchronous functions that internally send WebSocket commands to the Mineflayer bridge and return results.

## Read First (in this order)

1. `CLAUDE.md` — project context and conventions
2. `GOLEM_SDK.md` — the SDK design spec. This is your primary contract. Every function signature, return type, and behavior is defined here.
3. `BRIDGE_PROTOCOL.md` — the wire protocol. SDK functions map to bridge actions. The mapping is 1:1 for primitives.
4. `DECISIONS.md` — ADR-005 (execution model: synchronous API over async internals)

## Target Files

```
golem/
├── sdk.py             # The SDK — what `from golem import *` exposes
├── connection.py      # WebSocket connection management (internal, not exported)
├── errors.py          # Error types and translation (internal, not exported)
└── test/
    ├── test_sdk.py        # Unit tests against a mock bridge
    └── mock_bridge.py     # Mock WebSocket server for testing
```

## Key Constraints

- **Zero dependencies beyond stdlib + websockets.** The kid's code imports from this. It must be clean. Only `websockets` as the external dep.
- **Synchronous API.** Every SDK function is synchronous from the caller's perspective. Use `asyncio.run()` or an event loop thread internally. The kid writes `pos = get_position()`, not `pos = await get_position()`. See GOLEM_SDK.md §Execution Model and ADR-005.
- **Type hints on all function signatures.** Follow the exact signatures in GOLEM_SDK.md.
- **Position namedtuple.** `get_position()` and `get_player_position()` return a Position namedtuple with `.x`, `.y`, `.z` — the kid writes `pos.x`, not `pos["x"]`.
- **Error translation.** Bridge error codes → Python exceptions. But keep it simple: a `GolemError` base class with a human-readable message. The chat agent translates for the kid; the SDK just needs clean exception types.
- **`__all__` export list.** Only SDK functions are exported via `from golem import *`. Connection internals stay private.
- **Command ID generation.** SDK generates UUID for each command, correlates responses by ID.
- **Connection lifecycle.** `connect(host, port)` and `disconnect()` functions. The orchestrator calls these, not the kid's code. They should NOT be in `__all__`.
- **Progress callbacks.** For compound actions (collect, build_line, build_wall), accept an optional `on_progress` callback. Default to None (ignore progress). The orchestrator uses this to feed narration to the chat agent.

## Test Strategy

Build a mock bridge server (`mock_bridge.py`) that:
- Accepts WebSocket connections on a test port
- Responds to commands with canned responses
- Simulates progress messages for compound actions
- Can be configured to return errors for testing error paths

Test every SDK function against the mock. Test error translation. Test the synchronous wrapper (ensure it doesn't deadlock). Test `__all__` contains exactly the right set of names.

## What "Done" Looks Like

- `from golem import *` works and exports exactly the functions listed in GOLEM_SDK.md
- Each function sends the correct bridge command and returns the correct Python type
- Compound functions stream progress to an optional callback
- Errors from the bridge become clean Python exceptions
- All tests pass against the mock bridge
- The kid can write `pos = get_position()` and get a Position back with `.x`, `.y`, `.z`
