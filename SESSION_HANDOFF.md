# Silicon Golem — Session Handoff

**Date:** 2026-03-05
**Handoff from:** Cowork design session (chat agent prompt, cross-prompt verification, bridge protocol, Claude Code coordination)
**Consume after reading:** Yes — delete this file once the next session is oriented.

---

## Where We Are

All design artifacts are complete and cross-verified. Implementation has begun.

**What exists in the project folder:**

| Artifact | Status | Notes |
|---|---|---|
| CLAUDE.md | Complete | Includes orchestrator routing responsibilities section |
| DECISIONS.md | Complete | ADR-001 through ADR-007 accepted |
| GOLEM_SDK.md | Complete | SDK functions, concept allowlists, challenge walkthrough |
| BRIDGE_PROTOCOL.md | Complete | Full WebSocket protocol — verified against all agent prompts |
| prompts/chat_agent.md | Complete | Cross-verified, all consistency issues resolved |
| prompts/code_agent.md | Complete | 4 edits from cross-prompt verification |
| prompts/challenge_agent.md | Complete | Delivery model clarification added |
| golem/validator.py | Complete | AST allowlist enforcement, 76 tests passing |
| golem/test/test_validator.py | Complete | Full coverage of Levels 1-3 |
| STATUS.md | Needs update | Currently stale — update with this session's work |
| HANDOFF.md | Should delete | Consumed artifact from validator handoff |

**What's being built in Claude Code (parallel worktrees):**

- **Worktree 1: bridge/server.js** — Mineflayer bot + WebSocket server (handoff: prompts/handoff_bridge.md)
- **Worktree 2: golem/sdk.py** — Python SDK with sync API over async WebSocket (handoff: prompts/handoff_sdk.md)

These two are fully independent. They share BRIDGE_PROTOCOL.md as contract.

## The Live Question

**What's the next design artifact?** The learner model schema. This is the last piece of design work before the orchestrator can be built. It needs:

1. **BKT parameter spec** — per-concept parameters for Bayesian Knowledge Tracing (p_init, p_transit, p_slip, p_guess). Defaults plus any per-concept overrides.
2. **Stage transition heuristics** — what observable events trigger transitions between the six stages (none → exposed → read → modified → authored → debugged → composed). These need to be concrete: "If kid modifies a variable value in the code panel and re-runs, emit `concept_modified` for `variables`."
3. **Detection rules for each stage** — mapped to the 9 learner model event types defined in chat_agent.md (concept_exposed, concept_read, concept_modified, concept_authored, concept_debugged, code_inspected, variable_changed, code_rerun, asked_about_code).
4. **Mastery threshold** — when does p_mastery trigger level advancement? Current assumption: p_mastery ≥ 0.95 at `modified` stage = concept mastered.
5. **Concept dependency graph** — formal prerequisite chain. Currently implicit in GOLEM_SDK.md level definitions. Needs to be explicit JSON.
6. **contexts_seen tracking** — how context variety factors into mastery assessment (building, mining, crafting, farming, survival, combat).

## The Next Move

Design the learner model schema as a new section in GOLEM_SDK.md (or a standalone LEARNER_MODEL.md if it gets large). This feeds directly into `golem/learner.py` implementation.

**But first:** Check on the Claude Code worktrees. If they've completed, review the bridge and SDK implementations against BRIDGE_PROTOCOL.md and GOLEM_SDK.md respectively. Integration testing (SDK against real bridge) is the next implementation milestone after both are built.

## Key Constraints to Hold

1. **Companion frame is inviolable.** The bot never tutors, quizzes, or cheerleads. It's a capable-but-confused helper.
2. **One concept per challenge, zero exceptions.** Challenge engine cardinal rule.
3. **Concept allowlist is the single source of truth.** GOLEM_SDK.md defines what code can be generated. AST validator enforces it. Code agent prompt cites it.
4. **Minecraft 1.20.4 specifically.** 1.20.5 has breaking item component changes.
5. **The kid is the boss.** Every challenge has abort conditions. Disengagement ends the challenge immediately.

## Files to Read First (for next session)

1. `CLAUDE.md` — full project context (always read first)
2. `GOLEM_SDK.md` — especially the concept level definitions and the challenge walkthrough section
3. `prompts/chat_agent.md` — the 9 learner model event types that the learner model must consume
4. `DECISIONS.md` — ADR-006 (learner model) for the BKT decision
5. `STATUS.md` — current state (update it after reading)
