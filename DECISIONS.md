# Silicon Golem — Architectural Decisions

## ADR-001: Concept Mapping Philosophy

**Status:** Accepted
**Date:** 2026-03-05

### Context

Silicon Golem teaches Python through Minecraft gameplay. The central design question is how programming concepts relate to Minecraft mechanics: does Minecraft *illustrate* code concepts, or does the kid already *possess* the concepts through gameplay and the system provides formal notation?

### Decision

Minecraft primitives are prior knowledge, not illustration. The system identifies programming concepts the kid already uses implicitly through gameplay and provides formal syntax for those concepts. The kid is not learning new ideas — they are learning a new notation for ideas they already have.

This is a Vygotskian framing: the zone of proximal development is the gap between "I already reason about crafting recipes as input-output transforms" and "I can read `craft(material='iron_ingot', count=3)` and know what it does." The system bridges that gap.

### Concept Correspondences

| Python Concept | Minecraft Prior Knowledge | Why the Kid Already Gets It |
|---|---|---|
| Variables | Resource quantities, tool durability, hunger level | They track these mentally every session |
| Functions | Crafting recipes: typed inputs → deterministic output | Same recipe always makes the same item |
| Parameters | Recipe variations: different materials → different tool tiers | Iron pickaxe vs. diamond pickaxe, same shape |
| For-loops | Batch smelting, row planting, repetitive crafting | They already hate clicking 64 times |
| Conditionals | Material selection, survival decisions (fight/flee/shelter) | Every moment in survival is an if/else |
| Lists | Inventory slots, hotbar arrangement | They manage ordered collections constantly |
| Dictionaries | Inventory as type→count mapping, block palettes | "I have 42 cobblestone and 3 iron" is a dict |
| Dependency graphs | Tech tree: logs → planks → sticks → tools | Can't skip steps, some steps parallelize |
| Boolean logic | Redstone circuits: AND/OR/NOT gates in block form | Kids who build redstone already do digital logic |

### Implications

- The challenge engine must root challenges in the kid's existing gameplay, not in a syllabus.
- The bot should *name* what the kid already knows, not introduce foreign concepts.
- Error messages should map to Minecraft intuitions: "That's like trying to craft a pickaxe with the wrong materials" rather than "TypeError: expected int, got str."

---

## ADR-002: Dual-Track Challenge Architecture

**Status:** Accepted
**Date:** 2026-03-05

### Context

Minecraft gameplay spans two distinct modes with different concept richness profiles: creative mode (spatial, visual, fast feedback) and survival mode (resource management, state tracking, automation). The challenge engine needs to work in both.

### Decision

Two challenge tracks, selected based on observed gameplay mode:

**Building track** (creative mode or building in survival): Spatial concepts — coordinates, loops for repetition, variables for dimensions, geometry. Feedback is visual and immediate (30-second rule easily met). This is the on-ramp.

**Survival track** (crafting, smelting, gathering, combat): Computational concepts — functions as recipes, conditionals as survival decisions, loops as batch processing, data structures as inventory, dependency resolution as tech tree traversal. Feedback is functional (the bot successfully crafts/gathers/survives). Richer concept space but longer feedback loops.

The challenge engine observes what the kid is doing and selects the appropriate track. It never forces a track switch. The natural progression is: creative → building in survival → automating survival tasks. The kid's own desire to play survival drives the difficulty curve.

### The Feedback Loop Problem

Survival tasks can violate the 30-second rule. Mining, smelting, and multi-step crafting take real time. Two mitigation strategies:

1. **Narrated execution.** The bot provides real-time chat commentary while survival code runs. The kid sees progress, not a frozen screen.
2. **Abstracted results.** For long-running tasks, the bot works off-screen: "I'll go mine while you build. Be back in a bit." The kid sees the function call and the return value, not the execution. This teaches abstraction naturally — the function is a black box that produces results, like a crafting table.

Strategy selection depends on the kid's current phase. Phase 1-2 kids should see execution (narrated). Phase 3+ kids benefit from abstraction.

---

## ADR-003: Agent Topology and Model Allocation

**Status:** Accepted
**Date:** 2026-03-05

### Context

The system has multiple distinct AI responsibilities with different latency, quality, and cost profiles. A single model handling everything is suboptimal — the chat personality needs speed, the code generator needs reliability, and the challenge engine needs taste.

### Decision

Four-agent runtime architecture, orchestrated by the Python bridge process:

| Agent Role | Responsibility | Model Class | Latency Requirement |
|---|---|---|---|
| Chat agent | In-game personality, conversation, narration | Fast/small (Haiku-class) | <2 seconds |
| Code agent | Python generation from intent + world state + skills | Mid-tier (Sonnet-class) | <10 seconds |
| Challenge agent | Observe patterns, generate learning situations | High-capability (Opus-class) | Async, no hard limit |
| Learner model | Update concept states from interaction events | Rule-based or lightweight ML | Synchronous, <100ms |

The orchestrator routes messages based on type: chat input → chat agent (immediate response) + code agent (if action requested) + challenge agent (background observation). The learner model updates after every interaction.

### Build-Time Agent Strategy

For building the system itself, apply the Cherny fleet pattern:

- Opus with thinking for: system prompt authorship, challenge engine design, bot personality, architectural decisions. These are the highest-leverage artifacts.
- Sonnet or Codex for: Mineflayer bridge, REST API wrapper, WebSocket plumbing, test harnesses. Mechanical layers with clear specs.
- Parallel worktrees for independent layers: skill library and code panel have zero dependencies — build simultaneously.
- Verification loops on every agent's output: code agents run tests, challenge agents evaluate against simulated learner states.

---

## ADR-004: Verification Architecture

**Status:** Accepted (with deferred items)
**Date:** 2026-03-05

### Context

A kid seeing broken code from their AI companion erodes trust immediately. The system needs verification at multiple levels, and the approach to verification differs by agent role.

### Decision

Every code generation passes through a verification gate before the kid sees the result:

1. **Sandbox execution.** Generated Python runs in a sandboxed environment against simulated world state before executing in the real Minecraft world. Type errors, syntax errors, and runtime exceptions are caught here.
2. **World state validation.** After execution, compare actual world state to expected state. If the bot was supposed to place 10 blocks and only placed 7, the discrepancy is detected.
3. **Concept-level gating.** The learner model constrains which Python constructs the code agent can use. If the kid hasn't been exposed to list comprehensions, the code agent must not generate them. The verification layer rejects code that exceeds the kid's concept ceiling.
4. **Error personality translation.** When verification catches a failure, the error is routed through the chat agent's personality layer. The kid sees "Hmm, I got confused about which block to place" rather than `IndexError: list index out of range`. Phase 2+ kids optionally see both — the friendly message and the real error, building error-reading literacy.

For the challenge agent, verification is different: generated challenge situations are evaluated against the learner model to confirm the target concept is appropriate, the challenge doesn't require concepts the kid hasn't seen, and the kishōtenketsu structure is preserved (introduction → development → twist → resolution).

### Fallback Behavior

When verification fails mid-interaction with the kid:

- The bot admits confusion honestly ("That didn't work the way I expected").
- The failing code is still shown in the code panel — visible failures are pedagogically valuable.
- The bot offers to try a different approach, not retry the same one.
- The learner model logs `error_encountered` for concept tracking.

### Implementation Status

**Implemented in v1:**
- **Concept-level gating** (item 3). AST validator (`golem/validator.py`) enforces the concept allowlist per level. Code agent receives the permitted construct set. Validator rejects code that exceeds the kid's ceiling. Orchestrator retries up to 2x with error feedback, then reports infeasible.
- **Sandbox execution** (item 1, partial). Code executes in a restricted namespace: controlled `__builtins__` (no `eval`, `exec`, `open`, `__import__`), only SDK functions injected. AST validation catches structural violations before execution. However, execution runs against the real Minecraft world, not against simulated world state first.
- **Error personality translation** (item 4). Errors route through the chat agent with the full translation table (Level 1-2: bot absorbs, Level 3: kid-friendly, Level 4: simplified traceback, Level 5+: full traceback).
- **Fallback behavior.** All four bullet points implemented. Failing code is shown in the code panel. Learner model logs `error_encountered`.

**Deferred to v2:**
- **Pre-execution simulation** (remainder of item 1). Running code against simulated world state before the real world requires building a world-state simulator that predicts the outcome of SDK calls. The implementation cost is high and the failure mode (simulation diverges from real Mineflayer behavior) introduces its own class of bugs. For v1, the AST validator + restricted namespace + error personality translation provide sufficient safety. The kid sees errors as the bot's confusion, which is pedagogically aligned.
- **World state validation** (item 2). Post-execution comparison of expected vs actual state requires the orchestrator to infer intended outcomes from generated code — mapping `place_block(x, y, z, "cobblestone")` calls to expected block positions and then querying the bridge to verify. This is valuable but non-trivial. The current system detects errors through execution exceptions and bridge error codes, which catches most failures. The gap is silent failures (block placed at wrong coordinates, off-by-one errors) which succeed at the protocol level but produce the wrong visual result.
- **Challenge agent verification** (challenge paragraph). Generated challenges are not validated against the learner model before dispatch. The challenge agent's system prompt constrains it to only target concepts in the `ready_to_introduce` or `ready_to_advance` sets, but there's no programmatic enforcement. A misbehaving challenge agent could target a concept whose prerequisites aren't met.

### Revisit Triggers for Deferred Items

- **Pre-execution simulation:** If playtesting reveals that runtime errors are frequent enough to break the companion frame (kid loses trust in the bot), add a dry-run step. The bridge's `get_world_state` query could support a lightweight feasibility check (e.g., "does the bot have enough cobblestone for 25 place_block calls?") without full simulation.
- **World state validation:** If playtesting reveals silent failures (wrong coordinates, missing blocks) that confuse the kid, add post-execution state comparison. Start with block-count validation (expected N placements, verify N new blocks) before attempting coordinate-level comparison.
- **Challenge agent verification:** If the challenge agent produces challenges targeting concepts the kid hasn't reached, add a programmatic gate in the orchestrator that checks `get_concept_readiness()` before activating a challenge situation. This is a small addition — likely the first deferred item to implement.

---

## ADR-005: Skill Library as Growing Codebase

**Status:** Accepted
**Date:** 2026-03-05

### Context

The Voyager pattern (NVIDIA) demonstrated that LLM agents improve dramatically when they can retrieve and reuse previously successful functions. For Silicon Golem, the skill library serves double duty: it makes the agent more capable AND it gives the kid a tangible artifact of ownership — "my functions."

### Decision

Every function that successfully executes gets offered for saving to the kid's skill library. Storage format:

```json
{
  "name": "build_wall",
  "source": "def build_wall(length, height, block_type='cobblestone'):\n    ...",
  "description": "Builds a straight wall of specified dimensions",
  "concepts": ["for-loop", "parameters", "variables"],
  "author": "kid" | "bot" | "modified",
  "created": "2026-03-05T14:30:00Z",
  "times_used": 3
}
```

Key design choices:

- **Author attribution matters.** Functions the kid wrote or modified are tagged differently from bot-generated ones. The skill library browser shows this. It feeds the ownership narrative.
- **Retrieval is semantic.** When the kid says "build me a wall" the system embeds the request and finds relevant skills by cosine similarity on descriptions.
- **The library is the curriculum artifact.** A parent looking at the skill library sees their kid's programming journey: early functions are bot-authored, later ones are modified, latest ones are kid-authored. The progression is visible.
- **Curation is itself a learning opportunity.** Phase 4+ kids can rename, refactor, and delete functions. Managing the library teaches software engineering instincts (naming, organization, deprecation) through a collection they care about.

---

## ADR-006: Project Name — Silicon Golem

**Status:** Accepted
**Date:** 2026-03-05

### Context

The project needed a name that communicates the core relationship dynamic, resonates with the target user (a Minecraft-fluent kid), and works as a technical identifier.

### Decision

**Silicon Golem.** The reasoning:

- **Minecraft-native.** Golems are entities the player builds from materials — iron blocks and a pumpkin become an iron golem. The kid already understands the concept: you construct something from parts and it comes alive to serve you. Silicon Golem is the same idea, but the material is code instead of iron.
- **Correct power dynamic.** Golems serve their creator. The kid is the builder; the golem is the capable but directed helper. This matches the "kid as boss, bot as apprentice" design principle.
- **Silicon signals the computational layer.** It distinguishes this from the in-game entity while making the metaphor explicit: this golem is made of silicon (computation) rather than iron (blocks).
- **Works technically.** `silicon-golem` as repo name, `golem` as CLI command, "my golem" as what the kid says.

---

## ADR-007: Visual Block Editor — Not Building (v1)

**Status:** Parked
**Date:** 2026-03-05

### Context

A visual block programming interface modeled on Minecraft's crafting table — where code blocks are arranged like crafting ingredients to compose programs — would provide an alternative entry point for kids who can't type fluently. The crafting-grid metaphor maps construct composition to a familiar game mechanic: arrange known primitives in a pattern → produce a new capability, exactly like crafting recipes.

### Decision

Not building for v1. The chat-first interface with visible code is the core interaction to validate. The crafting-grid editor is a substantial front-end project (likely Blockly-based) that would delay the core learning loop validation.

### Revisit Triggers

- Evidence that typing speed is a significant barrier for the target age group (9-12)
- Evidence that the code panel's text display is insufficient for code comprehension at Level 1-2
- Successful validation of the core learning loop (kids do transition from Director → Modifier)

### Prior Art to Study If Revisiting

- Minecraft Education Edition's Code Builder (MakeCode/Blockly → JavaScript → Python)
- The "Scratch ceiling" literature on block-to-text transitions
- Alrubaye et al. (2019): hybrid viewing (blocks + text side by side) improved transfer by >30%

---

## ADR-008: Curiosity Bridge — Bot-Initiated Code Nudges

**Status:** Accepted
**Date:** 2026-04-09

### Context

First live smoke test revealed that showing code in a side panel is necessary but not sufficient. The code panel displays generated Python, but nothing bridges the gap between "code exists on screen" and "kid engages with code." The kid has to independently notice the code, understand it's editable, and spot something worth changing. That's too many unguided steps.

### Decision

The chat agent occasionally mentions a specific modifiable value from the generated code after successful execution. The mention is framed as the golem noticing something about its own internals — consistent with the personality (curious about its own code, doesn't fully understand it).

**Frequency:** Roughly 1 in 3 successful commands. More often when the kid hasn't touched the code yet. Backs off after the kid's first modification (the bridge has served its purpose). Never during active challenge directives.

**Tone examples:**
- "I used cobblestone for that. I think you can swap it to something else in my code if you want."
- "That wall's 5 blocks tall — I bet that number's in my code somewhere."
- "I put 'oak_planks' in there. Wonder what happens if you change it to something else."

**Constraints:**
- Never names code constructs ("variable", "parameter", "line 3")
- Never frames it as a task ("try changing...", "see if you can...")
- Never uses "code panel" — says "my code" or "that code thing"
- The nudge is an invitation, not an assignment

### Rationale

The GOLEM_SDK.md design assumes the kid transitions naturally from Director (gives commands) to Modifier (changes values in code). But the first smoke test showed the transition requires a catalyst — the kid needs a reason to look at the code and a hint that it's touchable. The bot mentioning a specific value ("I used cobblestone") makes the value salient and the phrase "you can swap it" establishes editability.

This is distinct from the challenge engine's role. Challenges manufacture situations where specific concepts become useful. The curiosity bridge is simpler — it just makes the code panel feel relevant before the challenge engine ever activates. It's the difference between "here's a puzzle to solve" (challenge) and "hey, that thing over there is interesting" (curiosity bridge).

### Revisit Triggers

- If playtesting shows the nudges feel repetitive or teacher-like, reduce frequency or revise tone
- If kids engage with code without nudges, the bridge may be unnecessary — remove to reduce chat noise
- If kids never engage despite nudges, the problem may be deeper (code panel placement, code readability, developmental readiness) and the bridge alone won't fix it
