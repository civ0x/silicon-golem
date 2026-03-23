# Silicon Golem — Project Status

## Current State

**Phase:** System complete — ready for smoke test
**Date:** 2026-03-05

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

### Next Up

- **End-to-end smoke test** — start MC 1.20.4 server + bridge + orchestrator + code panel, connect a Minecraft client, verify the full loop: chat → code generation → execution → world change → code panel display → kid edits → re-run
- **Run integration tests** against live MC server (33 tests currently skipping)
- **Anthropic API key** — orchestrator needs ANTHROPIC_API_KEY env var for chat/code/challenge agent calls

### Cleanup

- Delete `HANDOFF.md`
- Delete `SESSION_HANDOFF.md`
- Delete handoff prompts in `prompts/` (consumed)
