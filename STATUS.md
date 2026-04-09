# Silicon Golem — Project Status

## Current State

**Phase:** Smoke tested — first live playtest complete
**Date:** 2026-04-09

### Completed

**Design Artifacts:**
- CLAUDE.md, DECISIONS.md (ADR-001 through ADR-007), GOLEM_SDK.md, LEARNER_MODEL.md, BRIDGE_PROTOCOL.md
- Agent prompts: chat_agent.md, code_agent.md, challenge_agent.md — cross-verified for interface consistency

**Implementation — all components built and wired:**

| Component | Location | Tests |
|---|---|---|
| AST Validator | `golem/validator.py` | 76 |
| Mineflayer Bridge | `bridge/server.js`, `actions.js`, `events.js` | 378 |
| Python SDK | `golem/sdk.py`, `connection.py`, `errors.py` | 72 |
| Learner Model | `golem/learner.py` | 83 |
| Orchestrator | `golem/orchestrator.py` | 88 |
| Skill Library | `golem/skills.py` | 41 |
| Code Panel | `panel/index.html` | manual |
| Integration Tests | `golem/test/test_integration.py` | 33 (need MC server) |

**Total: ~360 automated tests passing, 0 failures.**

**Wiring complete:**
- All worktree branches merged into main
- Skill library wired into orchestrator: filter_by_level before code agent calls, auto-save after execution, usage tracking, author attribution
- Code panel events wired: code_display, code_panel_edit/run/scroll handlers, execution_start/complete, skills_list sync
- BridgeConnection.send_event() for orchestrator → panel communication

### Smoke Test Complete (2026-04-09)

First live end-to-end playtest. Found and fixed:

- **Code panel wasn't receiving code.** Orchestrator never emitted `code_display` events. Added `send_event()` to BridgeConnection, wired orchestrator to emit `code_display`, `execution_start`, `execution_complete`. Bridge event relay expanded to include these event types.
- **Code panel syntax highlighting: invisible text.** `.code-highlight` had `color: transparent`, making variable names and function calls invisible. Fixed to `#c5c8c6`.
- **Code panel line numbers horizontal.** Missing `white-space: pre` on `.line-numbers` div.
- **No orchestrator entry point.** Created `golem/__main__.py` — `python -m golem --player <name>`.
- **API key loading.** Added stdlib `.env` loader to orchestrator (no new deps).
- **Launcher script.** `start.sh` runs bridge + orchestrator + opens code panel in one command.

**Design finding:** Code panel shows code but nothing guides the kid to engage with it. Added "curiosity bridge" to chat agent prompt — bot occasionally mentions modifiable values in its code ("I used cobblestone for that — you can swap it in my code if you want"), staying in character as the golem noticing its own internals.

### Next Up

- **Kid playtest** — sit down with actual target user and observe. Does the curiosity bridge work? Does the kid notice the code? Do they try changing anything?
- **Run integration tests** against live MC server (33 tests currently skipping)
- **Investigate "something went wrong" error** seen in code panel during smoke test

### Cleanup

- Delete `HANDOFF.md`
- Delete `SESSION_HANDOFF.md`
- Delete handoff prompts in `prompts/` (consumed)
