# The Notation Problem: Teaching Code Through Play

*Silicon Golem and the architecture of incidental learning*

---

## Essay Metadata

**Target:** thbrdy.dev/writing/silicon-golem/
**Structure:** Mirrors "Notice" — 6 sections, concrete-to-abstract, personal framing, honest about limits
**Length:** Tight — closer to Notice than the 7,000-word skeleton. ~3,500–4,500 words.
**Tone:** Measured, specific, personal. "I built this for my kid" not "we present a system." Each section opens concrete, then extracts the principle. Research woven in organically — name the researcher, explain the mechanism in one sentence, move on.
**Audience:** Technical readers interested in learning science, AI system design, play as pedagogy. Not a tutorial. Not a product pitch.

---

## 01 — The Gap

### Argument

Open with the personal hook: watching your kid play Minecraft and realizing they already think computationally — they track resource counts (variables), execute crafting recipes (functions), batch-smelt (loops), make fight/flee decisions (conditionals). The question isn't "how do I teach my kid to code" but "why doesn't anything help them write down what they already know?"

Then the landscape of what exists, structured as two failure modes:

**Failure mode 1: The toy language.** Scratch, MakeCode, visual block editors. The kid snaps blocks together, but the production rules differ from any real language. Transfer to Python requires re-learning, not extending. The "Scratch ceiling" — kids plateau at the block-to-text transition because representations share concepts but not production rules.

**Failure mode 2: The verbose real language.** ComputerCraft (Lua), Minecraft Education Edition (Python via MakeCode). Real syntax but punishing ceremony-to-intent ratio. The kid wants to build a wall; the code requires imports, API init, coordinate math, and a loop they haven't been taught. The gap between "what I want" and "what I type" kills motivation before learning begins.

**The deeper problem beneath both:** These approaches treat programming as a subject to be acquired, with Minecraft as motivational decoration. The game provides context and reward, but the concepts are assumed to be new. This gets the ontology backwards.

### Key data points to include

- Concept correspondences from ADR-001 — not as a table, but woven into the opening observation about the kid's existing computational thinking:
  - Variables ↔ resource quantities ("I have 42 cobblestone and 3 iron")
  - Functions ↔ crafting recipes (typed inputs → deterministic output)
  - For-loops ↔ batch smelting, row planting ("they already hate clicking 64 times")
  - Conditionals ↔ survival decisions (fight/flee/shelter — "every moment in survival is an if/else")
  - Lists ↔ inventory slots, hotbar arrangement
  - Dictionaries ↔ inventory as type→count mapping
  - Boolean logic ↔ redstone circuits (AND/OR/NOT gates in block form)

- The Singley & Anderson (1989) transfer principle: transfer depends on identical production rules. Scratch-to-Python transfer is weak because the production rules differ. Real Python transfers because it IS the target notation.

### Diagram suggestion

**The Concept Transfer Gap.** Two columns: left shows Minecraft gameplay actions, right shows Python constructs. Standard pedagogy draws arrows right-to-left ("we teach these concepts using Minecraft"). Silicon Golem draws arrows left-to-right ("the kid already has these concepts; we provide notation"). The directional reversal IS the argument.

### Source docs
- ADR-001 (concept correspondences, Vygotskian framing)
- GOLEM_SDK.md §Design Decisions ("No method chaining," "String-based block names," "Coordinates always explicit")

---

## 02 — The Traditions

### Argument

Ground the design in learning science — not as literature review, but as the research that shaped specific design decisions. Personal framing: these aren't citations for credibility, they're the ideas that made the system's architecture inevitable.

**Benjamin Bloom — the 2-sigma problem (1984).** One-on-one tutoring produces 2 standard deviations of improvement over classroom instruction. The question Bloom posed: can we design learning environments that approach 1:1 tutoring effectiveness at scale? Silicon Golem's answer: an AI companion that maintains a learner model, adapts code complexity to the individual kid's concept ceiling, and manufactures challenges matched to what they're ready to learn. The golem IS the 1:1 tutor — but it doesn't know it's tutoring. It thinks it's helping build a house.

**James Paul Gee — 36 learning principles from game design (2003/2007).** The principles that directly shaped Silicon Golem:

- *Regime of Competence:* good games keep players at the edge of their ability. The concept allowlist enforces this — generated code never exceeds the kid's ceiling, and challenges target the next concept they're ready for.
- *Probing Principle:* probe the world, form a hypothesis, reprobe, rethink. This is exactly the kishōtenketsu beat structure: the kid sees repetitive code (probe), wonders if there's a shorter way (hypothesis), changes a variable (reprobe), sees the result (rethink).
- *Identity Principle:* learners take on identities as producers, not consumers. The skill library with author attribution — functions tagged as "bot," "modified," or "kid" — makes the kid's identity as a code author visible and persistent.
- *Achievement Principle:* intrinsic rewards over extrinsic. No points, badges, levels, leaderboards, XP bars. Minecraft play IS the reward.

**Lev Vygotsky — Zone of Proximal Development.** The ZPD for a Minecraft-fluent kid isn't "understands nothing about computation, needs scaffolding." It's "already reasons computationally through gameplay, needs notation that maps to existing mental models." The gap between "I track resource counts mentally" and "I can read `iron = 3`" is the ZPD. The system bridges exactly that gap.

**Edward Deci — overjustification effect (1971).** Extrinsic rewards on intrinsically motivated activities decrease motivation. This is why the system has zero extrinsic rewards. The kid plays Minecraft because they want to. Adding points for "learning Python" would undermine the intrinsic motivation that makes the whole system work. Non-negotiable design constraint.

**Manu Kapur — productive failure.** Encountering a gap between what you know and what you need — before being taught the solution — produces deeper learning than direct instruction (Cohen's d = 0.36 across 12,000+ participants). The kishōtenketsu structure operationalizes this: the twist (ten) reveals a limitation the kid can see but not yet solve. The bot never fills the gap. It makes the gap visible.

### Key design decisions that derive from the research

- No educational jargon ever — the bot is a companion, not a tutor (Gee's identity principle + Deci's overjustification)
- Error translation through bot personality: "I got confused" not "SyntaxError on line 5" (preserves the companion frame, keeps experimentation safe)
- One concept per challenge, zero exceptions (cognitive load theory — overload kills intrinsic motivation)
- Challenges emerge from gameplay, never imposed (Gee's regime of competence + Deci's autonomy)
- The kid is always the boss — the bot defers, serves, occasionally reveals its limits (Bloom's 1:1 dynamic, inverted)

### Source docs
- ADR-001 (Vygotskian framing, concept correspondences)
- ADR-002 (dual-track, 30-second feedback rule)
- Challenge agent prompt (kishōtenketsu structure, productive failure, Kapur citation, Bjork's desirable difficulties, Chi & Wylie ICAP framework)
- CLAUDE.md §Key Design Principles (the 7 non-negotiable rules)

---

## 03 — The Interaction

### Argument

The core UX moment. Not abstract — walk through the complete kishōtenketsu scenario from GOLEM_SDK.md. This is the equivalent of Notice's "Frame Snap" section: the single interaction that demonstrates the entire design philosophy in action.

**Setup:** A kid (10 years old) has been playing with the golem for 20 minutes. They've given "come here" and "dig this" commands. The learner model shows: `variables=exposed` (seen in code, never modified), `function_calls=exposed`. Now they're building a house and need a floor.

**Ki (Introduction):** Kid says "Hey golem, can you help me fill in this floor? It's 5 by 5, use oak planks." Natural request. No pedagogical setup the kid can detect.

**Shō (Development):** The code agent generates 25 `place_block` calls — explicit repetition, NOT the `build_wall` compound function. The challenge engine instructed `code_style: "explicit_repetition"` because the learner model says variables are exposed but not yet modified. The code panel shows:

```python
from golem import *

pos = get_player_position("Alex")
block = "oak_planks"

# Row 1
place_block(pos.x, pos.y - 1, pos.z, block)
place_block(pos.x + 1, pos.y - 1, pos.z, block)
place_block(pos.x + 2, pos.y - 1, pos.z, block)
# ... 22 more lines
```

The floor appears. 25 nearly identical lines with visible `+ 0`, `+ 1`, `+ 2` pattern.

**Ten (Twist):** Bot says in chat: "Done! That was a LOT of typing though — basically the same line 25 times. I wonder if there's a shorter way..." Tone: genuinely puzzled, not hinting. Then the bot moves on. Does NOT push further.

**Ketsu (Resolution):** The kid wants birch instead of oak. They look at the code. They see `block = "oak_planks"` at the top. They change it to `"birch_planks"`. Hit re-run. The floor rebuilds in birch.

Bot: "Oh nice, you changed the block type! That one variable controls all 25 blocks — that's the power of a variable."

Learner model updates: `variables: exposed → modified`.

**What didn't happen:** The bot didn't say "let's learn about variables." Didn't quiz. Didn't refuse to build the floor until the kid wrote code. It built the floor, mentioned the repetition, and waited. The learning happened because the kid wanted birch, saw the lever, and pulled it.

### Key details to include

- The challenge engine's actual output (JSON structure showing target_concept, code_style, beats, success_signals, abort_conditions)
- The bot personality in action: "Oh that's way better than what I had" not "Great job!"
- The code panel as the critical artifact: syntax-highlighted, "knob" lines (variable assignments) get subtle highlight, editable textarea
- The five-phase progression observed through this lens:
  1. **Director** — kid gives commands, sees generated code
  2. **Observer** — kid starts reading the code panel
  3. **Modifier** — kid changes a value (THIS is the moment in the scenario)
  4. **Author** — kid writes new code
  5. **Architect** — kid manages a skill library of their own functions
- The system never forces a transition. If the kid stays at Director for months, that's fine. (Deci: extrinsic pressure decreases motivation.)

### What the challenge engine actually computed

The challenge agent observed: kid is placing floor blocks manually (repetitive spatial task). Checked learner model: variables exposed but not modified. Generated challenge situation targeting `variables` → `modified` stage, with `code_style: "explicit_repetition"`. The bot_nudge: "Comment on repetition after execution. Do NOT suggest the kid modify the variable — wait for them to discover it."

### Diagram suggestion

**The Notation Bridge.** Three-panel animation showing a single concept (for-loops) in three representations:
1. Gameplay: kid placing blocks one by one (25 clicks, visual repetition)
2. Generated code: 25 `place_block()` calls (textual repetition, visible `+1, +2, +3` pattern)
3. Loop notation: `for i in range(25): place_block(pos.x + i, ...)` (the compression)

The center panel (verbose code) should feel deliberately long — mirror the kid's experience of seeing 25 identical lines.

### Source docs
- GOLEM_SDK.md §Concrete Challenge Scenario (the complete walkthrough)
- GOLEM_SDK.md §Generated Code Patterns (Pattern 2: Variables as Knobs)
- Challenge agent prompt (kishōtenketsu structure, beat definitions, success/failure/abort signals)
- Chat agent prompt §Who You Are (personality traits, what the bot is NOT)

---

## 04 — The Build

### Argument

How the system was built — methodology, not just output. This mirrors Notice's "Build" section (24 hours, Claude Agent SDK, design-docs-first). Personal framing: this is what agent-driven development looks like when you take design documents seriously.

**Timeline:** The entire system was built on 2026-03-05 — a single day from first commit (design docs + AST validator) to final wiring commit (skill library and code panel events into orchestrator). 18 commits, 6 components, ~360 tests.

**Design-docs-first.** The highest-leverage artifacts were written before any code:
- CLAUDE.md — architecture overview, 7 non-negotiable design principles
- DECISIONS.md — 7 ADRs with full rationale (not just decisions, but rejected alternatives and revisit triggers)
- GOLEM_SDK.md — the keystone artifact. SDK function set, concept allowlists per level, generated code patterns, full challenge scenario walkthrough. Everything derives from this document.
- LEARNER_MODEL.md — concept registry (16 concepts), 7-stage progression, BKT parameters, prerequisite chains
- BRIDGE_PROTOCOL.md — WebSocket message protocol (19 actions, 12 events, error codes)
- Three agent prompts (chat personality, code generation constraints, challenge engine structure)

The prompts and design docs were cross-verified against each other's interfaces before implementation began. The payoff: when implementation started, the specs were stable enough that code could be generated against them as contracts.

**Parallel worktrees for independent layers.** The system has 6 components with minimal interdependencies:

| Component | Language | Tests | Lines |
|---|---|---|---|
| Mineflayer Bridge | Node.js | 378 | ~1,650 (server + actions + events) |
| Python SDK | Python | 72 | ~300 (sdk + connection + errors) |
| AST Validator | Python | 76 | ~250 |
| Learner Model | Python | 83 | ~290 |
| Orchestrator | Python | 88 | ~520 |
| Skill Library | Python | 41 | ~200 |
| Code Panel | HTML/JS | manual | ~400 |

Each built in an isolated git worktree with its own Claude session, working against shared spec docs. Integration as the final step. The bridge (Node.js), SDK (Python), and validator (pure Python, no deps) have zero runtime coupling — they could be built simultaneously.

**The recursive insight.** The runtime system uses four specialized AI agents orchestrated by a central coordinator. The system itself was built using a multi-agent pattern with the same separation-of-concerns philosophy:

| Build-time | Runtime |
|---|---|
| Opus for design docs, prompts, ADRs | Challenge agent (Opus) for pedagogical design |
| Sonnet for bridge, SDK, validator, tests | Code agent (Sonnet) for code generation |
| Parallel worktrees | Async agent invocations |
| Design docs as interface contracts | Concept allowlist as single source of truth |
| Test suites as verification gates | AST validator as verification gate |

This isn't a cute parallel — it reflects a general principle. When you understand why specialized agents with a shared contract produce better outcomes than a monolithic agent, you apply the same principle to the build process. The architecture of the tool shapes the architecture of the artifact.

**Verification as build methodology.** Every component has a test suite that runs as part of the implementation process. Total: ~360 automated tests, 0 failures. The tests were written alongside (sometimes before) the implementation — they're the verification loop that allows the code agent to self-correct.

### Key data points

- 18 commits on 2026-03-05
- 6 components built in parallel worktrees
- ~360 automated tests, 0 failures
- 33 integration tests (require live MC server — the one verification gap)
- GOLEM_SDK.md is ~650 lines — the most complex single artifact
- Three agent prompts: chat (~180 lines), code (~150 lines), challenge (~180 lines) — all cross-verified before implementation
- Commit sequence: design docs → AST validator → bridge → SDK → learner model → orchestrator → integration tests → skill library → code panel → wiring

### Diagram suggestion

**The Fleet Mirror.** Split-screen: left shows build-time fleet (model tiers, parallel worktrees, design docs as contracts), right shows runtime fleet (4 agents, orchestrator, allowlist, AST validator). Connecting lines between corresponding elements.

### Source docs
- Git log (commit sequence and dates)
- CLAUDE.md §Development Methodology
- ADR-003 §Build-Time Agent Strategy
- STATUS.md (component inventory with test counts)

---

## 05 — The Machine

### Argument

Technical architecture — enough for the reader to understand the system's shape, not a full spec walkthrough. Focus on the engineering decisions that derive from pedagogical constraints.

**The four-agent topology.** Four agents with incompatible optimization targets:

| Agent | Model | Latency | Optimizes for |
|---|---|---|---|
| Chat | Haiku | <2s | Speed, personality, companion frame |
| Code | Sonnet | <10s | Correctness under constraints |
| Challenge | Opus | Async | Pedagogical taste, timing |
| Learner | Rule-based | <100ms | Consistency, prerequisite enforcement |

A single model serving all three AI roles would be too slow for chat, too imprecise for code, or too mechanical for challenges.

**The orchestrator as pedagogical router.** The orchestrator doesn't generate code, talk to the kid, or design challenges — but it owns all data flow. Its routing decisions ARE pedagogical decisions:
- When the challenge engine sets `code_style: "explicit_repetition"`, the orchestrator passes this to the code agent, which generates 25 lines instead of using `build_wall`
- It pre-filters the skill library by concept level before the code agent sees it
- It dispatches individual kishōtenketsu beats as trigger conditions fire — the chat agent sees one beat at a time, never the full arc. The bot doesn't know it's teaching, because it literally doesn't have the information.

**The concept allowlist as single source of truth.** One JSON artifact (defined in GOLEM_SDK.md) drives three coupled subsystems:
1. Code agent prompt → what constructs to use
2. AST validator → what constructs to accept
3. Few-shot examples → what code patterns to follow

If they diverge, the code agent generates code the validator rejects and the kid sees a broken bot. The allowlist isn't a config file — it's the system's theory of the kid.

**AST validation as developmental enforcement.** Python's `ast` module parses generated code; the validator walks the tree checking every node against the allowlist. Level 1 code cannot contain `ast.For` nodes. If the code agent generates a loop (because loops are "better code"), the validator rejects it, and the orchestrator retries with constraint feedback up to 2x, then reports infeasible. Engineering elegance must yield to pedagogical appropriateness.

The validator also catches the code agent's common failure modes: method chaining (`bot.move().place()`), implicit returns in expressions (`if get_position().y > 64:`), callbacks. Forbidden not because they're bad Python but because each smuggles in a concept the kid isn't ready for.

**The learner model: BKT + stage tracking.** Two complementary representations:
- Stages (qualitative): none → exposed → read → modified → authored → debugged → composed. Tracks the *kind* of engagement.
- BKT (quantitative): P(mastery) between 0 and 1. Tracks confidence within a stage.
- Level promotion requires p_mastery ≥ 0.85 on prerequisites.
- Context tracking: each concept tracks which Minecraft contexts (building, mining, crafting, farming) it appeared in. Requires 3–5 contexts before treating as transferable (Barnett & Ceci, 2002: varied contexts produce better generalization).
- BKT learn rates calibrated to Minecraft-as-prior-knowledge: variables learn fast (P(T)=0.30 — kids already track quantities), function definitions learn slowly (P(T)=0.10 — abstraction is a genuine cognitive leap even with crafting-recipe intuitions).

**The bridge: hiding JavaScript from Python.** The kid writes `move_to(10, 64, 20)` and the bot walks there. Underneath: Python SDK → async WebSocket → Node.js pathfinder → movement events → completion signal → WebSocket response → Python continuation. The kid sees sequential code that does sequential things. The async machinery is invisible because it's not pedagogically relevant.

**Progressive error disclosure.** Error handling evolves with the kid:
- Level 1-2: Bot absorbs errors. "I couldn't reach that block — something's in the way."
- Level 3: Kid-friendly translation. "I got confused because `hight` isn't a word I know — did you mean `height`?"
- Level 4: Simplified traceback with bot commentary.
- Level 5+: Full Python traceback visible.

The progression tracks the kid's growing relationship with code-as-text. At Level 1, a traceback would be hostile noise. At Level 5, it's useful diagnostic information.

### Key data points

- 18 SDK functions + Position/Item types
- 15 primitive actions + 3 compound actions + 2 queries in bridge
- 19 error codes with fuzzy block-name matching (Levenshtein distance)
- 16 concepts in registry with prerequisite chains
- 7 stages of concept engagement
- Sandbox execution: restricted `__builtins__` (no `eval`, `exec`, `open`, `__import__`), only SDK functions injected
- Pathfinder 30-second timeout wrapper (addressing known Mineflayer hang bug)

### Diagram suggestion

**The Execution Pipeline.** Trace a single kid message ("Build me a wall") through the full system, step by step. Each node expandable to show data payloads. Annotate latency at each hop. Total wall-clock: ~12-15 seconds from message to blocks appearing.

### Source docs
- ADR-003 (agent topology, model allocation)
- ADR-004 (verification architecture, deferred items)
- GOLEM_SDK.md §Level 1 Concept Allowlist
- GOLEM_SDK.md §SDK Implementation Notes
- LEARNER_MODEL.md §Concept Registry, §BKT Parameters
- BRIDGE_PROTOCOL.md (message protocol)
- Code agent prompt (constraints, code_style directives)

---

## 06 — Honest Limits

### Argument

What's untested, what's uncertain, what would validate. Mirror Notice's closing: "this hypothesis remains untested" — but with specific proxies for what success and failure would look like.

**No kid has used this yet.** The design argument stands on learning science. The implementation passes 360 tests. But the system hasn't been tested with its intended user. The floor-building kishōtenketsu scenario is a design artifact, not an observation. The question isn't whether the system works mechanically — it's whether a real kid, in a real Minecraft session, actually pulls the lever.

**BKT parameters are guesses.** The learn rates (P(T) per concept) are "educated guesses calibrated to Minecraft as prior knowledge." Variables at P(T)=0.30, function definitions at P(T)=0.10 — plausible, but not calibrated against real interaction data. The Orient phase (Pólya) was abbreviated here: parameters were set by intuition, not by structured analysis of how Minecraft-as-prior-knowledge changes transfer rates. Real-kid data would be the first thing to calibrate.

**Timing rules are heuristics.** "Max one challenge per 15 minutes, no challenges in first 10 minutes or last 5 minutes." Reasonable defaults, but chosen by feel. What's the kid's actual attention cycle length in Minecraft? What does the spacing literature say for this context? These numbers need empirical tuning.

**Verification is strong at syntax, absent at semantics.** The AST validator catches structural violations. The sandbox catches runtime exceptions. But:
- No pre-execution simulation: if the code agent generates `place_block` calls with off-by-one coordinates, the blocks appear in the wrong place. The protocol succeeds but the visual result is wrong.
- No post-execution state validation: the system doesn't compare expected vs. actual block positions.
- No programmatic challenge verification: the challenge agent's system prompt constrains concept targeting, but there's no enforcement gate checking `get_concept_readiness()` before dispatch. A misbehaving challenge agent could target a concept the kid isn't ready for.

These are documented as deferred items in ADR-004 with specific revisit triggers — not forgotten, but consciously deferred because the implementation cost was high relative to the v1 validation goal.

**What would validate the design:**

Behavioral proxies (not test scores, not surveys):
- **The Modifier transition happens.** A kid changes a variable value in the code panel without being told to. This is the critical design bet — that visible code with "obvious knobs" creates the Modifier instinct.
- **Challenge frequency stabilizes.** The system creates fewer challenges over time (the kid is advancing on their own) rather than more (the system is doing the work). If challenge frequency increases, the scaffolding is creating dependency, not competence.
- **Skill library authorship shifts.** Early functions tagged "bot," later ones "modified," latest ones "kid." If this progression doesn't appear, the Author transition isn't happening.
- **The kid explains code to the bot.** The apprenticeship inversion: the bot asks "how'd you know to change that?" and the kid explains. If this happens, the companion frame is working and the kid has adopted the identity of someone-who-understands-code.
- **Session length stays constant or increases.** If Minecraft sessions get shorter after the golem joins, the system is interfering with play. If they stay the same or get longer, the golem is adding to the experience.
- **The kid asks the golem to do things that require new constructs.** "Can you do this for every block?" (needs loops). "Only if it's nighttime" (needs conditionals). The kid discovers they need the notation before they're taught it.

**What would invalidate the design:**

- The kid never looks at the code panel. The entire system assumes the kid sees the code. If they treat the golem as a voice assistant and ignore the code, the learning pathway doesn't activate.
- The kid feels quizzed or taught. If the challenge engine's manufactured situations feel like lessons, the companion frame is broken and Deci's overjustification kicks in.
- Error translation feels condescending. If "I got confused" reads as baby talk to the kid rather than as the golem's honest limitation, the personality doesn't work for this age range.

### Source docs
- ADR-004 §Implementation Status, §Deferred to v2, §Revisit Triggers
- LEARNER_MODEL.md §BKT Parameters (the "educated guesses" framing)
- Challenge agent prompt §Timing and Pacing
- GOLEM_SDK.md §Error Handling Strategy

---

## Structural Notes for Composition

### Mapping to Notice's pattern

| Notice | Silicon Golem | Structural role |
|---|---|---|
| 01 — The Gap | 01 — The Gap | Problem identification: what exists fails, and the ontology is backwards |
| 02 — The Traditions | 02 — The Traditions | Research grounding: Bloom, Gee, Vygotsky, Deci, Kapur — not as lit review but as the ideas that made the architecture inevitable |
| 03 — The Build | 04 — The Build | Methodology: design-docs-first, parallel worktrees, single-day implementation, recursive insight |
| 04 — The Interaction | 03 — The Interaction | Core UX moment: the kishōtenketsu floor scenario. This is the Frame Snap equivalent — show don't tell. |
| 05 — The Architecture | 05 — The Machine | Technical implementation: enough to understand the shape, focused on where pedagogy constrains engineering |
| 06 — Honest Limits | 06 — Honest Limits | Epistemic humility: what's untested, what would validate, what would invalidate |

**Note on ordering:** I moved The Interaction before The Build (swapped from Notice's order) because the floor scenario is the reader's on-ramp to caring about the system. Once they've seen what the interaction looks like, the build methodology has stakes. Consider whether Notice's order (Build before Interaction) works better — it depends on whether the reader needs to understand HOW before WHAT, or WHAT before HOW. The kid-changes-a-variable moment is visceral enough that I'd lead with it.

### Voice calibration

From the Notice analysis:
- Sentences balance specificity with accessibility
- Design decisions receive philosophical grounding, not just feature justification
- Research integration feels organic, not appended
- Subheadings function as thesis statements
- Diagrams are arguments, not illustrations

### What to avoid

- Product pitch register
- "We built a thing and it's great"
- Excessive technical detail (link to docs for completeness)
- Chronological structure ("and then we did X")
- Educational jargon — ironic to use it in an essay about a system that bans it

### Diagrams as arguments

Three diagrams recommended (Notice had ~4). Each must change how the reader understands a claim:

1. **The Concept Transfer Gap** (§01) — Direction-of-arrows reversal. Standard pedagogy: teach concepts using Minecraft. Silicon Golem: the kid has the concepts, provide notation. The visual makes the ontological reframe structural.

2. **The Notation Bridge** (§03) — Three-panel: gameplay repetition → code repetition → loop compression. The center panel should feel long and uncomfortable — that's the kid's experience of seeing 25 identical lines.

3. **The Execution Pipeline** (§05) — Single message traced through the full system. Shows the architecture's shape without requiring the reader to parse a spec doc.

Optional fourth: **The Fleet Mirror** (§04) — Build-time/runtime parallel. Only if it doesn't feel like showing off.

### Research citations — quick reference

| Researcher | Concept | One-sentence mechanism | Where it shapes the design |
|---|---|---|---|
| Bloom (1984) | 2-sigma problem | 1:1 tutoring produces 2σ improvement; can we approach this at scale? | The golem IS the 1:1 tutor — maintains learner model, adapts to individual |
| Gee (2003) | 36 learning principles | Good games keep players at competence edge, use probing cycles, build producer identity | Concept ceiling, kishōtenketsu beats, skill library authorship |
| Vygotsky | Zone of Proximal Development | The gap between "can do alone" and "can do with help" — learning happens in this zone | The ZPD here is notation, not concepts. The kid already has the concepts. |
| Singley & Anderson (1989) | Transfer of cognitive skill | Transfer depends on identical production rules between training and target | Real Python, not a DSL. Scratch blocks don't transfer because production rules differ. |
| Deci (1971) | Overjustification effect | Extrinsic rewards on intrinsically motivated activities decrease motivation | Zero extrinsic rewards. No points, badges, XP. Minecraft play IS the reward. |
| Kapur | Productive failure | Encountering a gap before being taught produces deeper learning (d=0.36, 12K+ participants) | Kishōtenketsu twist: reveals limitation without filling it. Bot never solves the gap. |
| Barnett & Ceci (2002) | Transfer and context | Varied practice contexts produce better generalization than blocked single-context | Context tracking: concept needs 3-5 Minecraft contexts before considered transferable |
| Chi & Wylie (2014) | ICAP framework | Interactive > Constructive > Active > Passive for learning gains | Modifier→Author is largest gain AND most likely failure point. Disproportionate design attention. |
| Bjork | Desirable difficulties | Varied practice with oscillating difficulty beats steady escalation | Challenge difficulty: easy→medium→hard→easy pattern, not monotonic increase |

### Source document inventory for composition session

**Must reference:**
- DECISIONS.md — ADR-001 (concept mapping), ADR-003 (agent topology), ADR-004 (verification + deferred items), ADR-006 (naming)
- GOLEM_SDK.md — Challenge walkthrough scenario, Level 1 allowlist, code patterns, SDK design decisions
- LEARNER_MODEL.md — Concept registry, BKT parameters, stage progression
- Chat agent prompt — Bot personality, what the bot is NOT, error translation
- Challenge agent prompt — Kishōtenketsu structure, timing rules, productive failure, one-concept rule

**For code examples:**
- `golem/validator.py` — AST allowlist enforcement
- `golem/learner.py` — BKT + stage tracking
- `golem/orchestrator.py` — Central coordinator, routing logic
- `golem/sdk.py` — SDK function implementations

**For build timeline:**
- Git log: 18 commits on 2026-03-05, from design docs to wiring
