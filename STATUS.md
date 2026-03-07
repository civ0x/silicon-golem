# Silicon Golem — Project Status

## Current State

**Phase:** Implementation — smoke testing
**Date:** 2026-03-07

### Completed

- All design documents (CLAUDE.md, DECISIONS.md, GOLEM_SDK.md, LEARNER_MODEL.md)
- Agent prompts (chat, code, challenge) — cross-verified for interface consistency
- ADR-001 through ADR-007 accepted
- Bridge protocol specification (BRIDGE_PROTOCOL.md) — verified against all agent prompts
- AST Validator (`golem/validator.py`) — allowlist enforcement, 76 tests passing
- Orchestrator routing responsibilities documented in CLAUDE.md
- **Learner model schema** (LEARNER_MODEL.md) — concept registry, 7-stage progression, BKT parameters, stage transition rules, concept-to-AST mapping, level gate logic, `learner.py` interface spec. Cross-verified against all three agent prompts.
- **Mineflayer Bridge** (`bridge/`) — server.js (323 lines), actions.js (1057 lines), events.js (274 lines), 378 lines of integration tests. All 15 primitives + 3 compounds + 12 event types + 2 queries. All 19 error codes mapped. Protocol-compliant.
- **Python SDK** (`golem/sdk.py`, `golem/connection.py`, `golem/errors.py`) — 18 SDK functions + Position/Item types, synchronous API over async internals, error translation, progress callbacks, 72 tests passing.
- **Learner model** (`golem/learner.py`) — 290 lines. LearnerModel class with all 6 spec methods. BKT forward algorithm, 7-stage progression with skip-forward semantics, concept-to-AST mapping, 16-concept registry with prerequisite chains, JSON persistence. 83 tests passing.
- **Orchestrator** (`golem/orchestrator.py`) — 520 lines. Central coordinator: message routing (chat → code → execute → narrate), challenge state machine (kishōtenketsu beats with trigger evaluation), world context assembly, code execution pipeline with AST validation retry loop, sandboxed exec with restricted builtins, Claude API integration (Haiku/Sonnet/Opus). 62 tests passing.
- **Dev environment verified** (2026-03-07) — Python 3.13.5, Node 25.8.0, all dependencies installed (websockets, anthropic, mineflayer, ws). 308 Python tests passing, 59 skipped (integration). Bridge tests require live MC server (expected).

### In Progress

- **Smoke testing** — verifying full chain end-to-end against a live Minecraft 1.20.4 server.

### Next Up

- **Integration testing** — SDK against real bridge on a live MC 1.20.4 server. Verify the full chain: Python call → WebSocket → Mineflayer → world state change.
- **Code panel web UI** (`panel/index.html`) — independent. Plain HTML + WebSocket + syntax highlighting.
- **Skill library** (`golem/skills.py`) — save/load/search, semantic retrieval.

### Blocked

- **Bridge integration tests** — need a running Minecraft 1.20.4 server (LAN or dedicated) for the bridge to connect to. All 25 bridge tests fail with ECONNREFUSED without one.

### Cleanup

- Delete `HANDOFF.md` (consumed by validator build)
- Delete `SESSION_HANDOFF.md` (consumed by learner model session)
- Handoff prompts in `prompts/` can be deleted (both worktrees complete)
- Merge bridge-impl and sdk-impl worktree branches into main
