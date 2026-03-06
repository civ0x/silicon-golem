# Handoff: Begin Implementation — AST Validator

## Where We Are

The design layer is complete. The project folder contains:

- **CLAUDE.md** — Project overview, architecture, orchestrator routing responsibilities, development methodology, technical conventions, file organization target.
- **DECISIONS.md** — Seven accepted ADRs (concept mapping philosophy, dual-track challenges, agent topology, verification architecture, skill library, project name, visual block editor parked).
- **GOLEM_SDK.md** — The Python API surface, concept allowlists (Level 1 fully specified, Levels 2-3 previewed), generated code patterns, full challenge scenario walkthrough, SDK implementation notes.
- **prompts/chat_agent.md** — Bot personality, conversation rules, error translation, challenge integration, learner event emission.
- **prompts/code_agent.md** — Code generation constraints, style rules, construct constraints by level, few-shot examples, infeasible task handling.
- **prompts/challenge_agent.md** — Challenge engine rules, kishōtenketsu beat structure, concept progression, timing/pacing, delivery model.

All three agent prompts have been cross-verified for interface consistency. The orchestrator routing responsibilities are documented in CLAUDE.md.

No STATUS.md exists yet — create it when implementation begins.

## The Next Move: AST Validator

Build `golem/validator.py` — the AST allowlist enforcement module. This is pure Python (only `ast` stdlib module), zero external dependencies, and fully specified by the concept allowlist in GOLEM_SDK.md.

### What It Does

Takes a Python source string and a concept level configuration. Parses it into an AST. Walks every node and rejects anything not in the permitted set for that level. Returns either success or a structured error describing what construct was used and why it's not allowed.

### Key Constraints

1. **Allowlist, not blocklist.** Anything not explicitly permitted is rejected. This is safer — new Python syntax additions are blocked by default.
2. **The Level 1 allowlist in GOLEM_SDK.md is the canonical spec.** The JSON under "Level 1 Concept Allowlist" defines every permitted AST node, SDK function, builtin, and constraint.
3. **ImportFrom is restricted.** The only permitted import is `from golem import *`. Any other import is rejected.
4. **SDK function calls are validated.** Only functions in `permitted_sdk_functions` may be called. Calls to anything else (except `permitted_builtins`) are rejected.
5. **Max constraints:** `max_lines`, `max_nesting_depth`, `max_variables`, `max_repeated_similar_lines` (heuristic).
6. **Error messages are structured** — they'll be consumed by the error translation layer in the chat agent. Include the line number, the offending construct, and a plain description.

### Test Strategy

Every SDK function, every AST allowlist level, every error case. Specifically:

- All Level 1 code patterns from GOLEM_SDK.md should pass validation at Level 1.
- All Level 2 code patterns should fail at Level 1 and pass at Level 2.
- All Level 3 code patterns should fail at Level 2 and pass at Level 3.
- Import validation: `from golem import *` passes, `import os` fails, `from os import path` fails.
- Function call validation: `place_block(...)` passes, `open(...)` fails, `exec(...)` fails.
- Nesting depth: code within limits passes, code exceeding `max_nesting_depth` fails.
- Line count: code within `max_lines` passes, code exceeding it fails.
- Variable count: code within `max_variables` passes, code exceeding it fails.
- Edge cases: empty script, script with only comments, script with only the import line.

### Files to Read First

1. `CLAUDE.md` — project conventions, file organization target
2. `GOLEM_SDK.md` — Level 1 Concept Allowlist section (the JSON spec), code patterns section (test cases)
3. `DECISIONS.md` — ADR-004 (verification architecture)

### Target File Organization

```
golem/
├── __init__.py
├── validator.py       # The AST validator
└── test/
    ├── __init__.py
    └── test_validator.py
```

### After the Validator

The next parallel tracks are:

- **Bridge protocol spec + Mineflayer bridge** (`bridge/server.js`) — defines the WebSocket message vocabulary, implements the Node.js bot. Depends on Minecraft 1.20.4, Mineflayer, mineflayer-pathfinder, mineflayer-collectblock.
- **SDK module** (`golem/sdk.py`) — the Python SDK the kid's code imports. Depends on the bridge protocol (wire format), not the bridge implementation. Can build against a mock bridge.

These two share the protocol contract but are otherwise independent.
