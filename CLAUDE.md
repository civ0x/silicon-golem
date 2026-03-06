# Silicon Golem — CLAUDE.md

## What This Project Is

Silicon Golem is an AI companion system for Minecraft that teaches a child Python through play. A Mineflayer bot joins the kid's Minecraft world, takes natural language commands, generates visible Python code, and executes it in-world. The child transitions from directing the bot in English to reading, modifying, and eventually writing Python — because they want to, not because they're told to.

The system is not an IDE, not a MOOC, not a tutoring chatbot. It is an apprenticeship inversion: the kid is the master, the AI is the capable-but-directed helper who happens to be better at typing.

## Read These First

Before working on any task, read the relevant design docs:

- **DECISIONS.md** — Accepted architectural decisions (ADR-001 through ADR-007). These are binding constraints. Don't contradict them without explicit discussion.
- **GOLEM_SDK.md** — The Python API surface the kid sees. Defines SDK functions, concept allowlists per level, generated code patterns, and a full challenge scenario walkthrough. This is the keystone artifact — code generation, AST validation, and challenge design all derive from it.
- **STATUS.md** — Current project state (create this when implementation begins). What's built, what's next, what's blocked.

## Architecture Overview

Four-layer runtime (see DECISIONS.md ADR-003 for agent topology):

```
Minecraft (Java Ed, 1.20.4, LAN)
    ↕ Minecraft protocol
Mineflayer (Node.js) — bot presence, world state, actions
    ↕ WebSocket (ws + websockets)
Python Orchestrator — agent routing, code execution, learner model
    ↕ Claude API
Four AI Agents — chat (Haiku), code (Sonnet), challenge (Opus), learner (rule-based)
```

The kid sees: Minecraft + a code panel (web UI) showing the bot's generated Python.

## Orchestrator Routing Responsibilities

The Python orchestrator is the central coordinator. It does not generate code, talk to the kid, or design challenges — but it owns all data flow between agents. These responsibilities are implicit in the agent prompts but documented here as the canonical reference.

### Message Routing

When a kid's chat message arrives:
1. Route to **chat agent** with world context and learner model state → chat agent produces a chat response and (optionally) a task description.
2. If task description produced, attach **code_style** from the active challenge directive (or default `"compound"`) and **concept level constraints** from the learner model. Route the enriched task to the **code agent**.
3. Route to **challenge agent** asynchronously with world context, learner model, and concept readiness. Challenge agent may produce a new challenge situation or update nothing.

### Challenge Directive Dispatch

The challenge agent produces a full challenge situation (all four kishōtenketsu beats with triggers, signals, and abort conditions). The orchestrator holds this state machine and dispatches individual beat directives to the chat agent as trigger conditions are met. The chat agent sees one beat at a time (`active_beat`, `bot_behavior`, `constraints`) — never the full arc.

Trigger evaluation is the orchestrator's job. It observes world state changes, learner model events (emitted by the chat agent), and chat messages, then matches them against the current beat's trigger condition. When a trigger fires, it sends the next beat's directive to the chat agent.

When an abort condition fires, the orchestrator retires the challenge and clears the active directive. No explicit handshake with the chat agent is needed — the absence of a directive returns the chat agent to default behavior.

### Skill Library Filtering

Before passing the skill library to the code agent, the orchestrator filters it by the kid's current concept level. Only skills whose `concepts` array is a subset of the current permitted set are included. The code agent receives a pre-filtered list and does not need to check concept levels on skills.

### World State Observation

The orchestrator assembles world context from Mineflayer bridge events (block changes, entity positions, time of day, game mode) and code panel events (code inspected, code modified, code re-run). It packages these into the JSON structures that the chat agent and challenge agent consume. The orchestrator is responsible for detecting player activity patterns ("building," "mining," "crafting") from raw block/inventory change events.

### Learner Model Updates

Learner model events emitted by the chat agent are processed by the learner model (rule-based or BKT). The orchestrator passes the updated learner state to both the chat agent and challenge agent on their next invocation. The learner model is synchronous (<100ms) and updates before the next agent call.

## Development Methodology

This project follows the Cherny fleet pattern for agent-driven development.

### Plan Before Executing

Use plan mode (`shift+tab`) for any task touching design, architecture, or system prompts. Iterate on the plan until it's solid. Only then switch to implementation. The highest-leverage artifacts in this project are system prompts and design docs — getting those right matters more than getting code written fast.

### Parallel Worktrees for Independent Layers

The system has several layers with zero interdependencies that should be built concurrently:

- **Mineflayer bridge** (Node.js WebSocket server) — independent
- **Python SDK** (`golem.py`) — depends on bridge protocol, not bridge implementation
- **Code panel web UI** — independent (consumes WebSocket events)
- **Skill library** — independent (JSON storage + semantic search)
- **AST validator** — independent (pure Python, no external deps)
- **Learner model** — independent (event log + state machine)

Use separate worktrees. Don't serialize work that can parallelize.

### Verification on Every Output

Every code generation by agents building this project must be verified:

- **Python code**: run tests, type-check, lint. The AST validator itself needs tests against known-good and known-bad code samples.
- **System prompts**: evaluate against simulated scenarios. Does the challenge engine produce valid kishōtenketsu beats? Does the code agent respect the concept allowlist?
- **Mineflayer integration**: test against a running MC 1.20.4 server. Pathfinder timeout wrapper must be tested with unreachable goals.
- **SDK functions**: each one needs a test that exercises the full chain — Python call → WebSocket message → Mineflayer action → world state change.

If you can't verify it, flag it. Don't ship unverified code into a system a child will use.

### Compounding Knowledge

When you discover something — a Mineflayer quirk, a prompt pattern that works, an AST edge case — add it to the relevant doc:

- Mineflayer quirks → DECISIONS.md or a new `MINEFLAYER_NOTES.md`
- Prompt patterns → the relevant system prompt file
- AST edge cases → test cases in the validator test suite
- General project learnings → this file

## Technical Conventions

### Python

- Python 3.11+. Type hints on all function signatures.
- `golem.py` (the SDK) must have zero dependencies beyond the standard library + `websockets`. The kid's code imports from it; it must be clean.
- AST validator uses only `ast` module from stdlib. No third-party parsing.
- Use `asyncio` internally but expose synchronous API to generated code (see GOLEM_SDK.md execution model section).
- Tests with `pytest`. Every SDK function, every AST allowlist level, every error translation.

### Node.js

- Target Node 18+. Mineflayer + mineflayer-pathfinder + mineflayer-collectblock.
- WebSocket server via `ws` package.
- Message protocol: `{id, type, action, args}` for commands, `{id, type, success, data}` for responses, `{type, event, data}` for unsolicited events.
- Target Minecraft 1.20.4 specifically. Do not use version auto-detection — pin it.

### Code Panel (Web UI)

- Minimal. Plain HTML + WebSocket + syntax highlighting (Prism.js or similar).
- No build step for v1. Single HTML file that connects to the Python orchestrator's WebSocket.
- Panels: current code (syntax highlighted), skill library browser, execution log.
- Code must be editable at Phase 3+ (kid modifies code before re-running).

### File Organization (Target)

```
silicon-golem/
├── CLAUDE.md              # This file
├── DECISIONS.md           # Architectural decisions
├── GOLEM_SDK.md           # SDK design and concept allowlists
├── STATUS.md              # Current state (create at implementation start)
├── bridge/
│   ├── server.js          # Mineflayer bot + WebSocket server
│   ├── package.json
│   └── test/
├── golem/
│   ├── __init__.py
│   ├── sdk.py             # The Golem SDK (what the kid imports)
│   ├── orchestrator.py    # Agent routing, execution loop
│   ├── validator.py       # AST allowlist enforcement
│   ├── learner.py         # Learner model (event log + BKT)
│   ├── skills.py          # Skill library (save/load/search)
│   └── test/
├── panel/
│   └── index.html         # Code panel web UI
├── prompts/
│   ├── chat_agent.md      # Chat personality system prompt
│   ├── code_agent.md      # Code generation system prompt
│   └── challenge_agent.md # Challenge engine system prompt
└── data/
    ├── blocks.json        # Valid block/item names for MC 1.20.4
    └── concept_levels.json # Concept allowlists per level (from GOLEM_SDK.md)
```

## Concept Allowlist is the Single Source of Truth

The JSON allowlist defined in GOLEM_SDK.md drives both the code agent's system prompt and the AST validator. When you update what constructs are available at a level, update the JSON, then regenerate:

1. The code agent's system prompt section listing permitted constructs
2. The AST validator's configuration
3. The few-shot examples in the code agent prompt

These three must always be in sync. If they diverge, the code agent generates code the validator rejects, and the kid sees a broken bot.

## Key Design Principles (Non-Negotiable)

These are grounded in research (see the learning science research doc in project knowledge) and ADR-001:

1. **Minecraft primitives are prior knowledge, not illustration.** The kid already has the concepts through gameplay. We provide notation.
2. **Real Python, not a DSL.** Transfer depends on identical production rules (Singley & Anderson). The kid writes `for i in range(10):`, not `repeat(10)`.
3. **One concept per challenge, zero exceptions.** Cognitive overload kills intrinsic motivation.
4. **Observe, don't impose.** Challenges emerge from what the kid is already doing. Never say "time for a lesson."
5. **The kid is the boss.** The bot serves, defers, and occasionally reveals its limits. Never quizzes, never uses educational jargon, never refuses to do something to force coding.
6. **Code designed to be modified.** Generated code has obvious variable names, clear parameters, and "obvious knobs to turn" — `block = "cobblestone"`, `height = 5`. The Modifier transition (kid changes a value) is the most critical learning moment.
7. **Errors are the bot's confusion, not the kid's failure.** Error translation through the bot personality: "I got confused" not "SyntaxError on line 5."

## What NOT to Do

- **Don't add extrinsic rewards.** No points, badges, levels, leaderboards, XP bars. The overjustification effect (Deci, 1971) means extrinsic rewards on intrinsically motivating activities *decrease* motivation. Minecraft play IS the reward.
- **Don't generate code above the kid's concept ceiling.** If the learner model says Level 1, the code agent must not use for-loops, even if it would be "better code." The constraint system exists for pedagogical reasons, not stylistic ones.
- **Don't break the companion frame.** The bot is a Minecraft companion, not a tutor. It never says "great job!" — it says "oh THAT's how you do it, I'm saving that." It never says "let's learn about loops" — it says "there's probably a shorter way to write this but I'm not sure how."
- **Don't use Minecraft versions other than 1.20.4** without updating the entire dependency chain (minecraft-data → node-minecraft-protocol → mineflayer). The 1.20.5 item component breaking change is catastrophic.
- **Don't use `eval()` for generated code execution.** Use `exec()` with a controlled namespace containing only the SDK functions. Sandboxing matters — a child will be running this code.

## Session Management and Handoff Protocol

### Context Budget Awareness

This project involves large design documents. Before starting substantive work, assess whether the remaining context is sufficient for the task. If you're past ~60% of context capacity, prioritize completing the current artifact and preparing a handoff rather than starting new work.

Signs you should prepare a handoff rather than continuing:

- You're losing track of design decisions made earlier in the conversation
- You need to re-read files you already read to recall their contents
- The task ahead requires reading multiple large docs plus producing substantial output
- Your responses are getting less precise or missing constraints from the design docs

### Handoff Format

When the session is running long, proactively initiate a handoff. Don't wait to be asked. Frame it as a natural pause:

"We've covered [what was accomplished]. The next move is [specific next task]. Here's a handoff prompt for a fresh session:"

Then produce a handoff prompt in a fenced block that includes:

1. **Where we are:** One paragraph summarizing what exists in the project folder and what was just completed.
2. **The live question:** The specific design or implementation question that was being worked when the session paused.
3. **The next move:** The concrete next step — not a vague direction, but a specific artifact to produce or decision to make.
4. **Key constraints to re-load:** The 3-5 most important design constraints from the docs that the next session must hold in mind (don't dump everything — just the ones that constrain the next task).
5. **Files to read first:** Ordered list of which project files to read and in what order.

### Between Sessions

Durable project state lives in versioned documents in the project folder, not in chat history. Every session should leave the project folder in a state where a fresh session can pick up from the docs alone. If a design decision was made in conversation but not yet written into DECISIONS.md, GOLEM_SDK.md, or CLAUDE.md, write it before ending the session.
