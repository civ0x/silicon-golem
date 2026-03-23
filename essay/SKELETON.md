# The Notation Problem: Teaching Code Through Play

*Silicon Golem and the architecture of incidental learning*

---

## Essay Metadata

**Target publication:** thbrdy.dev/writing/silicon-golem/
**Estimated length:** 5,000–7,000 words (comparable to Circuitry of Science)
**Style:** Long-form editorial with embedded interactive diagrams. Serif prose, sans-serif structural elements. Diagrams are arguments, not illustrations.
**Audience:** Technical readers interested in learning science, AI system design, and the intersection of play and pedagogy. Not a tutorial. Not a product pitch.
**Key references:** Vygotsky (ZPD), Singley & Anderson (transfer), Deci (overjustification), Kapur (productive failure), Pólya (problem-solving heuristics), Gee (game-based learning), Boyd (OODA), Bloom (mastery learning), Toulmin (argumentation structure). Project docs: DECISIONS.md, GOLEM_SDK.md, LEARNER_MODEL.md.

---

## Epigraph (candidate)

Something from Vygotsky on the relationship between play and concept formation, or from Pólya on understanding before solving. Or: the Minecraft crafting table as metaphor — you arrange known materials in a pattern and something new emerges.

---

## 01 — The Verbosity Trap

### Argument

Open with a concrete scene: a kid in ComputerCraft, typing Lua to make a turtle dig. The turtle API is reasonable by adult standards — `turtle.dig()`, `turtle.forward()` — but the kid's experience is: I already know how to dig in Minecraft. I do it with one click. Why am I typing 47 characters to do what a mouse click does?

This is the verbosity trap. Programming education for kids falls into two failure modes:

**Failure mode 1: The toy language.** Scratch, MakeCode, and visual block editors abstract away syntax entirely. The kid learns to snap blocks together, but the production rules (Singley & Anderson) are different from any real language. Transfer to Python or JavaScript requires re-learning, not extending. The "Scratch ceiling" literature documents this: kids plateau at the block-to-text transition because the representations share concepts but not production rules.

**Failure mode 2: The verbose real language.** ComputerCraft (Lua), Minecraft Education Edition (Python via MakeCode), and similar mods throw kids into real syntax but with a punishing ratio of ceremony to intent. The kid wants to build a wall. The code requires import statements, API initialization, coordinate math, and a loop construct they haven't been taught yet. The gap between "what I want" and "what I have to type" is wide enough to kill motivation before learning begins.

The deeper problem beneath both: **these approaches treat programming as a subject to be acquired**, with Minecraft as motivational decoration. The game provides context and reward, but the concepts are assumed to be new. The kid must learn variables, functions, loops — and Minecraft makes the learning "fun."

This gets the ontology backwards.

### Diagram: The Concept Transfer Gap

**Interactive element.** Two columns: left column shows Minecraft gameplay actions (tracking resources, crafting recipes, batch smelting, survival decisions). Right column shows Python constructs (variables, functions, for-loops, conditionals). Standard pedagogy draws arrows from right to left: "we teach these concepts using Minecraft as illustration." Silicon Golem draws arrows from left to right: "the kid already has these concepts; we provide notation."

On hover/click, each correspondence pair expands to show the mapping from ADR-001's concept correspondence table. The visual makes the direction-of-transfer argument structural rather than rhetorical.

**Implementation note:** CSS grid, intersection observer for scroll-triggered reveal. No charting library. Each pair animates independently. Reduced-motion fallback: static two-column layout.

---

## 02 — Prior Knowledge, Not Illustration

### Argument

The reframe. Ground it in Vygotsky's zone of proximal development, but make it concrete: the ZPD for a Minecraft-fluent kid learning Python is not "understands nothing about computation, needs scaffolding." It's "already reasons computationally through gameplay, needs a notation that maps to existing mental models."

Walk through the concept correspondences from ADR-001 in prose, not as a table. Each one should feel like a revelation:

- **Variables.** Every survival player tracks resource counts mentally. "I have 42 cobblestone and 3 iron" is a dictionary. `iron = 3` isn't a new concept — it's a written version of something the kid already thinks.
- **Functions.** Crafting recipes: typed inputs → deterministic output. The crafting table is a function call with named parameters. `craft(material="iron_ingot", count=3)` maps directly.
- **For-loops.** Batch smelting. Row planting. Placing 64 blocks. The kid already hates clicking 64 times — the loop is the notation for the frustration they already feel.
- **Conditionals.** Every moment in survival mode. Fight, flee, or shelter. "If it's nighttime, go inside" is `if time_of_day == "night":` with syntax added to a decision the kid makes every game-night.

Then the design implication: if the kid already has the concepts, the system's job isn't teaching — it's **providing notation at the moment the kid needs it**. This means:

1. Real Python, not a DSL (transfer requires identical production rules — Singley & Anderson, 1989).
2. Challenges emerge from gameplay, not from a syllabus (observe, don't impose).
3. The bot is a companion, not a tutor (the kid is the boss; see ADR-001 principle 5).
4. No extrinsic rewards — Minecraft play IS the reward (overjustification effect, Deci 1971).

### Diagram: The Notation Bridge

**Interactive element.** Animated visualization showing a single concept — say, "for-loops" — as it exists in three representations:

1. **Gameplay** (left): A kid placing blocks one by one. 25 clicks. Visual repetition.
2. **Generated code** (center): 25 `place_block()` calls. Textual repetition. The visible pattern: `pos.x + 1`, `pos.x + 2`, ... `pos.x + 25`.
3. **Loop notation** (right): `for i in range(25): place_block(pos.x + i, ...)`. The compression.

The animation shows the transition: gameplay frustration → code that mirrors the frustration → notation that resolves it. The kid doesn't learn loops in the abstract — they discover the notation for a compression they already want.

**SDK design as notation design.** Weave into this section (or subsection): the SDK's API choices are themselves notation decisions. `pos.x` reads as English ("position's x") where `pos[0]` requires index knowledge. String-based block names (`"cobblestone"`, not `BlockType.COBBLESTONE`) are "obvious knobs" — change the string, change the build. No method chaining (`move_to().place()`) because it smuggles in object semantics. No callbacks because Level 1 code is strictly sequential. Every API choice encodes a pedagogical commitment about what the kid should see, read, and eventually modify. The SDK isn't a wrapper around Mineflayer — it's a notation designed for a specific learner at a specific developmental stage.

Scroll-triggered: the three stages reveal sequentially as the reader progresses. The center panel (verbose code) should feel deliberately uncomfortable — long, repetitive, scrollable — to mirror the kid's experience of seeing 25 identical lines.

---

## 03 — Apprenticeship Inversion

### Argument

The system's core interaction model. Traditional apprenticeship: expert does, novice watches, novice gradually takes over. Silicon Golem inverts it: the kid is the master, the AI bot is the capable-but-directed apprentice. The kid says "build me a wall." The bot builds it — in visible Python. The kid gradually takes over not because they're told to, but because they see the code doing what they wanted, and they want to modify it.

This section covers:

**The companion frame.** The bot is a golem — Minecraft-native entity. Iron golems serve their creator. Silicon Golem runs on Python instead of redstone. The naming is load-bearing (ADR-006): it establishes the power dynamic, the Minecraft-native metaphor, and the computational substrate in three syllables.

**The five-phase progression.** Not taught, but observed:
1. **Director** — kid gives commands in English, bot generates code, kid watches blocks appear.
2. **Observer** — kid starts reading the code panel. "What's that `block = "cobblestone"` line?"
3. **Modifier** — kid changes a value. `"cobblestone"` → `"glass"`. Re-runs. Floor becomes transparent. This is the critical transition.
4. **Author** — kid writes new code. First a single line, then a function, then a function that calls other functions.
5. **Architect** — kid manages a skill library of their own functions. The bot is a tool, not a crutch.

The system never forces a transition. The challenge engine manufactures situations where the next phase is the path of least resistance — but if the kid stays at Director for months, that's fine. The overjustification research (Deci, 1971) is clear: extrinsic pressure on intrinsically motivated activity decreases motivation. The kid will advance because they want to, or they won't. Both are acceptable outcomes.

**Error translation as trust mechanism.** When the bot breaks, it's "I got confused," not "SyntaxError on line 5." The bot absorbs blame. This is not just UX — it's load-bearing pedagogy. If the kid thinks they caused the error, they stop experimenting. If the bot caused the error, experimentation is safe. The progressive disclosure of real error messages (Level 1: bot absorbs → Level 3: kid-friendly → Level 5: full traceback) tracks the kid's growing relationship with code-as-text.

### Diagram: The Phase Transition Map

**Interactive element.** A state diagram showing the five phases, with the trigger conditions for each transition annotated. Not a linear progression — show that kids can bounce between phases (a Level 3 Author might revert to Director for a complex task, then return to Author). The learner model's stage tracking (none → exposed → read → modified → authored → debugged → composed) overlays on each phase.

Key visual: each transition has a "manufactured situation" annotation showing how the challenge engine creates conditions for the transition without forcing it. The kishōtenketsu beat structure appears here as the mechanism.

---

## 04 — Decisions as Architecture

### Argument

This is the design-decisions section. Not a changelog — an argument about how architectural choices encode pedagogical commitments. Every ADR has a learning-science rationale, and every rationale constrains the technical implementation in non-obvious ways.

**The concept allowlist as constraint propagation.** (ADR-001 + GOLEM_SDK.md) The concept allowlist is a single JSON artifact that drives three coupled subsystems: the code agent's generation constraints, the AST validator's enforcement rules, and the few-shot examples in the code prompt. If they diverge, the code agent generates code the validator rejects, and the kid sees a broken bot. This is a constraint propagation problem: a single source of truth (the allowlist) must be maintained across three representations, and any change must cascade consistently.

The deeper point: the allowlist isn't just a technical artifact — it's the system's theory of the kid. Level 1 says "this kid can read variables and function calls." Level 2 says "this kid can handle for-loops." The levels encode a developmental model, and the AST validator enforces it with zero tolerance. Generated code that exceeds the kid's ceiling is rejected and regenerated, even if it would be "better code" by engineering standards. Pedagogical constraints override engineering elegance.

**The four-agent topology.** (ADR-003) Why four agents, not one? Because the responsibilities have incompatible optimization targets: the chat agent optimizes for speed and personality (Haiku, <2s), the code agent optimizes for correctness under constraints (Sonnet, <10s), and the challenge engine optimizes for pedagogical taste (Opus, async). A single model serving all three would be either too slow for chat, too imprecise for code, or too mechanical for challenges.

The orchestrator sits at the center — it doesn't generate code, talk to the kid, or design challenges, but it owns all data flow. This is an architectural commitment to separation of concerns where the "concerns" are cognitive, not just computational: personality is a different competency than code generation is a different competency than pedagogical design.

**The dual-track architecture.** (ADR-002) Minecraft gameplay spans two modes with different concept profiles: creative (spatial, visual, immediate feedback) and survival (resource management, state tracking, automation). The challenge engine observes which mode the kid is in and selects the appropriate track. Building track emphasizes loops-as-spatial-repetition, variables-as-dimensions. Survival track emphasizes functions-as-recipes, conditionals-as-decisions, loops-as-batch-processing. The kid's own desire to play survival drives the difficulty curve — the system never forces a track switch.

The 30-second feedback rule constrains both tracks. Building challenges satisfy it naturally (blocks appear instantly). Survival challenges — mining, smelting, multi-step crafting — can violate it, requiring two mitigations: narrated execution ("the bot provides commentary while working") at Phase 1-2, and abstracted results ("the function is a black box that produces results") at Phase 3+. This second mitigation is itself a pedagogical moment: it teaches abstraction naturally, because the kid sees the function call and the return value, not the execution. The concept of abstraction arrives as a solution to a latency problem, not as a lesson.

**Kishōtenketsu as challenge structure.** (Challenge agent prompt + GOLEM_SDK.md walkthrough) Why a four-beat narrative structure from Japanese aesthetics instead of a standard "present problem → give hint → reveal solution" tutoring pattern? Because kishōtenketsu's third beat (ten, the twist) is a recontextualization, not a hint. The twist doesn't tell the kid what to do — it reveals that what they already know is insufficient, or that what they already see has a pattern they hadn't noticed.

This connects directly to Kapur's productive failure research: the twist creates a "desirable difficulty" where the kid's current understanding suffices to see the problem but not to solve it. The gap between seeing and solving is where learning happens. The bot never fills that gap — it just makes the gap visible.

Walk through the full challenge scenario from GOLEM_SDK.md (the floor-building kishōtenketsu) as a concrete demonstration. The kid asks for a floor. The bot generates 25 `place_block` calls. The bot comments on the repetition. The kid changes `"oak_planks"` to `"birch_planks"`. The learner model updates. No lesson was taught. Learning happened because the kid wanted birch.

**Naming as design.** (ADR-006) "Silicon Golem" is load-bearing nomenclature. Golems are Minecraft-native — the kid builds them from materials, and they come alive to serve their creator. The power dynamic is correct: the kid is the builder, the golem is the capable-but-directed helper. "Silicon" signals the computational layer without breaking the Minecraft frame. `golem` as import name, "my golem" as what the kid says. Naming matters because it establishes the relationship frame the entire interaction model depends on.

**What we chose not to build.** (ADR-007) A visual block editor modeled on Minecraft's crafting table — arrange code blocks like crafting ingredients to compose programs. Parked for v1 because the chat-first interface with visible code is the core interaction to validate first. But the decision is tracked explicitly, with revisit triggers: evidence that typing speed is a barrier, evidence that the code panel is insufficient for comprehension, or successful validation of the core learning loop. Documenting parked decisions is as important as documenting active ones — it prevents re-litigation and preserves the reasoning for future sessions.

**The skill library as curriculum artifact.** (ADR-005) The skill library is inspired by Voyager (NVIDIA) — successful functions persist for reuse. But the design choice that makes it pedagogically interesting is author attribution: functions are tagged as `"bot"`, `"modified"`, or `"kid"`. A parent looking at the skill library sees their child's programming journey: early functions are bot-authored, later ones are modified, latest ones are kid-authored. The progression is visible without any dashboard, grade, or assessment. The skill library is now fully wired into the orchestrator: filtered by concept level before the code agent sees it, auto-saved after successful execution, with usage tracking and semantic retrieval via embeddings + cosine similarity. The library is the closest thing in the system to a "gradebook" — but it's a gradebook the kid curates, not one imposed on them.

### Diagram: The Constraint Propagation Chain

**Interactive element.** Show the concept allowlist (JSON) as the single source of truth, with three derivation paths:

1. Allowlist → Code agent system prompt (permitted constructs section)
2. Allowlist → AST validator configuration (enforcement rules)
3. Allowlist → Few-shot examples (code patterns at each level)

Clicking on a concept (e.g., "for_loops") highlights its presence or absence across all three derivations and shows the level gate. Changing the level slider updates all three representations simultaneously, demonstrating the coupling.

The visual argument: constraint propagation from a single source ensures the system's theory-of-the-kid is consistent across all components. Divergence between representations means the system is working against itself.

### Diagram: The Agent Topology

**Interactive element.** A message-flow diagram showing the four agents, the orchestrator, and the Mineflayer bridge. Trace a single kid message ("Build me a wall") through the full system:

1. Chat message → Orchestrator → Chat agent (Haiku) → response + task description
2. Task description + concept level + code_style → Code agent (Sonnet) → Python code
3. Python code → AST validator → (pass/fail) → Sandbox exec → Mineflayer bridge → Minecraft world
4. Asynchronously: world state + learner model → Challenge agent (Opus) → kishōtenketsu situation → stored for trigger evaluation

Each agent node shows its model class, latency requirement, and primary optimization target. The orchestrator node is visually central and larger, with all data flow passing through it.

---

## 05 — Heuristics as Scaffolding

### Argument

This section addresses the AB++ framework and Polya-like heuristics as meta-level design tools — not in the kid's experience, but in the builder's process of creating the system.

**The Orient-Execute-Reflect pattern in system design.** The AB++ framework identifies a three-layer structure across five independent methodologies (Pólya, Boyd, Crawl-Walk-Run, Bloom, Gee): orient before acting, execute in small verified loops, reflect to ratchet understanding forward. This pattern shows up in Silicon Golem at two levels:

*Level 1: The kid's learning loop.* The kishōtenketsu challenge structure maps directly: Ki/Shō is orientation (the kid encounters a situation, sees code), Ten is execution (the kid attempts a modification or encounters the twist), Ketsu is reflection (the kid sees the result, the learner model updates). The challenge engine's "observe, don't impose" principle is the Orient phase applied to pedagogy — understand what the kid is doing before manufacturing a learning situation.

*Level 2: The builder's design loop.* The project's design-first methodology (comprehensive docs before code, CLAUDE.md/DECISIONS.md/GOLEM_SDK.md as binding artifacts) is Pólya's "understand the problem" applied to system design. Each ADR is a Polya cycle: understand the constraint space → devise an approach → implement → review against the constraint space. The ADRs are the project's "looking back" artifacts — they record not just what was decided, but why alternatives were rejected.

**Where Pólya was applied well:**

- The concept allowlist design. GOLEM_SDK.md starts from the kid's prior knowledge (understand), maps to Python constructs (plan), defines the allowlist levels (execute), and cross-verifies against the AST validator and code agent prompt (review). The four-phase cycle is explicit.
- Agent prompt authorship. Each prompt was written against the full constraint set (understand), structured around specific input/output interfaces (plan), iterated through simulated scenarios (execute), and cross-verified against other agents' interfaces (review).
- The bridge protocol. BRIDGE_PROTOCOL.md was verified against all three agent prompts before implementation. The verification step (review) caught interface mismatches early.

**Where Pólya should have been applied more systematically:**

- The learner model's BKT parameters. The learn rates (P(T) per concept) are "educated guesses calibrated to Minecraft as prior knowledge." This is the Execute phase without adequate Orient — the parameters were set based on intuition rather than structured analysis of how Minecraft-as-prior-knowledge changes transfer rates. A more systematic approach would have been: (1) enumerate what "Minecraft as prior knowledge" means for each concept's learn rate, (2) find analogous BKT calibration data from game-based learning literature, (3) set initial parameters, (4) define the calibration protocol for real-kid testing.
- The challenge engine's timing rules. "Max one challenge per 15 minutes, no challenges in the first 10 or last 5 minutes" — these numbers are reasonable defaults but they were chosen by feel, not by structured analysis. The Orient phase would ask: what does the learning science say about optimal spacing? What's the kid's attention cycle length in Minecraft? What evidence would update these numbers?
- The orchestrator's activity pattern detection. The spec says the orchestrator detects "building, mining, crafting" from raw events, but the decision about what constitutes each pattern was left implicit. A Pólya cycle would have explicitly defined the pattern vocabulary, mapped it to challenge track selection, and specified the failure cases (what happens when the kid is doing something that doesn't fit any pattern?).

**The meta-lesson: heuristics as habits, not checklists.** The AB++ framework works best when Orient-Execute-Reflect is a habit rather than a procedure. In Silicon Golem's development, the places where it was applied naturally (allowlist design, prompt authorship) produced the strongest artifacts. The places where it was skipped (BKT calibration, timing parameters) are exactly the places where the design has the most uncertainty. The correlation isn't coincidental — the heuristic works by forcing you to surface what you don't know before you commit to a decision.

### Diagram: The Heuristic Stack

**Interactive element.** Show the five AB++ methodologies (Pólya, Boyd, Crawl-Walk-Run, Bloom, Gee) as horizontal layers, with the Orient-Execute-Reflect pattern as vertical columns cutting across all five. Map specific Silicon Golem design decisions to cells in this matrix:

- Pólya/Orient: GOLEM_SDK.md's concept mapping analysis
- Boyd/Orient: Challenge engine's "observe, don't impose" principle
- Bloom/Execute: Learner model's mastery gates (p_mastery ≥ 0.85 for level promotion)
- Gee/Execute: Kishōtenketsu's "probe-hypothesize-reprobe" mapping
- Crawl-Walk-Run/Reflect: The five-phase progression (Director → Architect) as verified mastery levels

Hovering on each cell shows the specific artifact or decision it maps to. Gaps in the matrix (cells where the heuristic wasn't applied) are highlighted in a different color — these are the places identified above where more systematic application would have strengthened the design.

---

## 06 — Building With Agents

### Argument

This section makes the recursive structure explicit: the runtime system uses four specialized AI agents orchestrated by a central coordinator, and the system itself was built using a multi-agent fleet pattern with the same separation-of-concerns philosophy. The build methodology draws heavily on the Cherny fleet pattern and Boris Cherny's Claude Code best practices — and the parallels between build-time and runtime architecture are not coincidental. They reflect the same design insight: different cognitive tasks have incompatible optimization targets, and routing them to appropriately-specialized agents produces better outcomes than running everything through a single generalist.

**The build-time fleet pattern.** (ADR-003, Build-Time Agent Strategy.) The system was constructed using model-appropriate task allocation:

- **Opus with extended thinking** for the highest-leverage artifacts: system prompts, challenge engine design, bot personality, architectural decisions. These are the artifacts where taste, subtlety, and constraint-awareness matter most. The three agent prompts (chat, code, challenge) were authored at this tier and cross-verified against each other's interfaces.
- **Sonnet/Codex** for mechanical implementation layers with clear specs: the Mineflayer bridge, WebSocket plumbing, AST validator, test harnesses. These tasks have well-defined inputs and outputs — the spec documents function as unambiguous contracts.
- **Parallel worktrees** for independent layers. The bridge (Node.js), SDK (Python), validator, learner model, and orchestrator have minimal interdependencies. Each was built in an isolated git worktree, with its own Claude session, working against the shared spec docs. This enabled genuine concurrency — five components advancing simultaneously without merge conflicts or context contamination.

**Why parallel worktrees matter.** The standard Claude Code workflow serializes tasks: implement component A, test it, then implement component B. For a system with five independent layers, this means each layer waits for the others. The worktree approach (from Boris's practices) eliminates this bottleneck: each component gets its own branch, its own working directory, and its own Claude session. The shared design documents (DECISIONS.md, GOLEM_SDK.md, BRIDGE_PROTOCOL.md) function as interface contracts — each worktree reads the same specs and implements against them, guaranteeing compatibility without requiring runtime coordination.

The result: the bridge, SDK, validator, learner model, and orchestrator were all built in a single development session window, with integration verification as the final step. This is the software equivalent of the concurrent engineering pattern from manufacturing — design for interfaces, build in parallel, integrate late.

**CLAUDE.md as compounding knowledge.** Following Boris's practice of treating CLAUDE.md as a living document, the project's CLAUDE.md grew throughout development. Every Mineflayer quirk, every prompt pattern that worked, every AST edge case was captured in the relevant doc as it was discovered. This creates a compounding knowledge effect: each subsequent Claude session starts with a richer context, makes fewer mistakes, and produces output that's more consistent with earlier decisions.

The key insight: CLAUDE.md isn't documentation for humans — it's a persistent system prompt that accumulates project intelligence across sessions. It's the mechanism by which design decisions survive context window boundaries. When a fresh session reads CLAUDE.md + DECISIONS.md + GOLEM_SDK.md, it inherits not just the current state but the reasoning behind it.

**Plan mode as design-first methodology.** The project's design-first approach (comprehensive docs before code) maps directly to Boris's emphasis on plan mode: iterate on the plan until it's solid, then execute. Every major component started with a design document or ADR before any code was written. The GOLEM_SDK.md document — the most complex artifact in the project — went through multiple revision cycles before the first line of Python was written. The payoff: when implementation began, the specs were stable enough that the code agent could work from them as contracts, producing implementations that passed verification on the first or second iteration.

**Verification as build-time feedback loop.** Boris's principle — "give Claude a way to verify its work" — shaped the development methodology. Every component has a test suite that runs as part of the implementation process:

- AST validator: 76 tests against known-good and known-bad code samples
- SDK: 72 tests covering all 18 functions
- Learner model: 83 tests covering BKT algorithm, stage transitions, prerequisite chains
- Orchestrator: 88 tests covering routing, challenge state machine, execution pipeline
- Skill library: 41 tests covering save/load, semantic search, concept filtering, author attribution
- Integration tests: 33 (require live MC 1.20.4 server — the one verification gap)

Total: ~360 automated tests, 0 failures. The tests were written alongside (and sometimes before) the implementation — they're the verification loop that allows the code agent to self-correct. Without them, generated code would require manual review for every change. With them, the agent can iterate autonomously until the tests pass.

**The recursive insight.** The runtime's four-agent topology mirrors the build-time fleet. Both separate responsibilities by optimization target: fast personality vs. precise code generation vs. high-taste pedagogical design at runtime; high-leverage design vs. mechanical implementation vs. parallel independent work at build time. Both use a central coordinator (runtime orchestrator / project design docs) to maintain consistency. Both verify outputs before integration.

This isn't just a cute parallel — it reflects a general principle about agent-based system design. When you understand why a multi-agent runtime with specialized roles produces better outcomes than a monolithic agent, you apply the same principle to the build process. The architecture of the tool shapes the architecture of the artifact.

### Diagram: The Fleet Mirror

**Interactive element.** A split-screen visualization. Left side: the build-time fleet (three model tiers, parallel worktrees, design docs as contracts, verification loops). Right side: the runtime fleet (four agents, orchestrator routing, concept allowlist as contract, AST validation as verification). Draw structural parallels with connecting lines between corresponding elements:

- Opus (build) ↔ Challenge agent/Opus (runtime): both handle the highest-leverage, taste-dependent tasks
- Sonnet (build) ↔ Code agent/Sonnet (runtime): both handle precise, spec-driven generation
- Parallel worktrees (build) ↔ Async agent invocations (runtime): both enable concurrent independent work
- CLAUDE.md + design docs (build) ↔ Concept allowlist + learner model (runtime): both are single-source-of-truth contracts
- Test suites (build) ↔ AST validator (runtime): both are verification gates before integration

The visual makes the recursive structure legible. Hover on any element to highlight its counterpart.

---

## 07 — The Machine Underneath

> *Note: previously §06. Renumbered after inserting "Building With Agents."*

### Argument

Technical implementation section. Not a complete architecture doc — the reader can follow references to the project docs for that. Instead, focus on the interesting engineering decisions that derive from pedagogical constraints.

**The bridge: hiding JavaScript from Python.** The Mineflayer bot runs in Node.js. The kid's code runs in Python. The WebSocket bridge between them handles protocol translation, but the interesting design choice is what it hides: the entire concept of asynchronous operations. The kid writes `move_to(10, 64, 20)` and the bot walks there. Under the hood: Python SDK function → async WebSocket call → Node.js pathfinder goal → movement events → completion signal → WebSocket response → Python continuation. The kid sees sequential code that does sequential things. The async machinery is invisible because it's not pedagogically relevant — and making it visible would violate the concept ceiling.

**AST validation as pedagogical enforcement.** The validator uses Python's `ast` module to parse generated code and walk the tree, checking every node against the allowlist for the kid's current level. This is more than type-checking — it's enforcing a developmental model. A Level 1 kid's code cannot contain `ast.For` nodes, period. If the code agent generates a loop (because loops are "better code"), the validator rejects it, and the orchestrator re-invokes the code agent with explicit constraint feedback up to twice, then reports the task as infeasible. The engineering instinct to write clean code must be overridden by the pedagogical requirement to write appropriate code.

The validator also catches the code agent's common failure modes: method chaining (`bot.move().place()`), implicit returns used in expressions (`if get_position().y > 64:`), and callback patterns. These are forbidden not because they're bad Python but because each one smuggles in a concept (objects, expression composition, higher-order functions) that the kid isn't ready for.

**What verification doesn't cover yet.** (ADR-004, deferred items.) The system validates code structure (AST allowlist) and catches runtime exceptions (restricted sandbox), but it doesn't predict outcomes. There's no dry-run against simulated world state before executing in the real Minecraft world, and no post-execution comparison of expected vs. actual block positions. If the code agent generates `place_block` calls with an off-by-one error in coordinates, the blocks appear in the wrong place — the protocol succeeds but the visual result is wrong. The kid sees a crooked wall and the system doesn't know anything went wrong.

Similarly, the challenge agent isn't programmatically verified against the learner model before its challenges are dispatched. The agent's system prompt constrains it to only target concepts in the `ready_to_introduce` or `ready_to_advance` sets, but there's no enforcement gate. A misbehaving challenge agent could target a concept whose prerequisites aren't met — which would violate the "one concept per challenge" principle and the concept ceiling.

These gaps are worth discussing in the essay because they illustrate a real design tradeoff: the verification architecture you can build with a finite context budget vs. the verification architecture you'd want. Pre-execution simulation requires a world-state model that predicts SDK call outcomes — nontrivial inference. Challenge verification requires a programmatic gate that checks `get_concept_readiness()` before activating — small enough to be the first deferred item implemented. The essay should be honest that the v1 verification story is "strong at the syntax level, absent at the semantic level," and that this is a known gap with defined revisit triggers.

**The learner model: BKT meets stage tracking.** Two complementary representations of what the kid knows. Stages (qualitative: none → exposed → read → modified → authored → debugged → composed) track the kid's relationship with a concept. BKT (quantitative: P(mastery) between 0 and 1) tracks confidence within a stage. A kid can be at the "modified" stage for variables with p_mastery of 0.6 — meaning they've changed a variable successfully a few times, but the model isn't yet confident this is stable mastery.

The quantitative layer matters for gating decisions. Level promotion requires p_mastery ≥ 0.85 on prerequisite concepts. Stage advancement requires ≥ 0.70. The BKT learn rates are calibrated to Minecraft-as-prior-knowledge: variables learn fast (P(T)=0.30) because kids already track quantities mentally; function definitions learn slowly (P(T)=0.10) because genuine abstraction is a cognitive leap even with crafting-recipe intuitions. These numbers are educated guesses awaiting calibration on real kids — and the essay should say so explicitly (see §05's point about where Pólya should have been applied more systematically).

Context tracking adds a transfer dimension: each concept tracks which Minecraft contexts it appeared in (building, mining, crafting, farming, etc.). A concept that's been encountered in only one context isn't yet transferable — the learner model requires 3-5 contexts before treating it as stable. This is grounded in transfer research: skills that are practiced in varied contexts generalize better than those drilled in a single context.

The stage progression is interesting because it's not strictly linear. A kid who debugs a variable error (stage: debugged) demonstrates deeper understanding than a kid who has only modified values (stage: modified), even though both have "used" variables. The stage tracks the *kind* of engagement, not just the *frequency*. And the "composed" stage — using a concept as scaffolding while working on something else — is the real signal of mastery. When the kid writes `for i in range(height):` while thinking about the tower shape, not the loop syntax, `for_loops` has become load-bearing knowledge.

**The orchestrator: routing as pedagogy.** The central coordinator makes routing decisions that are pedagogically meaningful. When the challenge engine sets `code_style: "explicit_repetition"`, the orchestrator passes this to the code agent, which generates 25 `place_block` calls instead of using `build_wall`. The routing decision IS the pedagogical decision — the orchestrator is choosing what the kid will see, and that choice is grounded in the learner model's assessment of what the kid is ready for.

**Progressive error disclosure.** Error handling evolves with the kid. Level 1-2: the bot absorbs errors entirely ("I couldn't reach that block"). Level 3: kid-friendly translation ("I got confused because `hight` isn't a word I know — did you mean `height`?"). Level 4: simplified traceback with bot commentary. Level 5+: full Python traceback, visible. The progression tracks the kid's growing relationship with code-as-text. At Level 1, the traceback would be hostile noise. At Level 5, it's useful diagnostic information. The system doesn't decide when to show errors — the learner model does, based on demonstrated engagement with code.

**Orchestrator routing logic.** The orchestrator's routing decisions are pedagogically meaningful in specific ways worth detailing: (1) It evaluates whether a chat message requires code generation or just a response — not every kid message triggers the code agent. (2) When a challenge is active, it dispatches individual kishōtenketsu beats as trigger conditions are met from world state events, learner model events, and chat messages — the chat agent sees one beat at a time, never the full arc. (3) It pre-filters the skill library by concept level before the code agent sees it, so the code agent can't accidentally use functions above the kid's ceiling. (4) It detects activity patterns (building, mining, crafting) from raw Mineflayer events, which determines challenge track selection.

The challenge state machine is particularly interesting: the challenge agent produces a full four-beat kishōtenketsu situation once, then the orchestrator holds it and dispatches individual beats as trigger conditions are met from world state events. The chat agent never sees the full arc — only the current beat directive. This separation means the bot's personality is never contaminated by pedagogical meta-awareness: the bot doesn't know it's teaching, because it literally doesn't have the information.

### Diagram: The Execution Pipeline

**Interactive element.** Trace a single kid command through the full system, step by step. A horizontal pipeline with expandable nodes:

1. Kid types: "Build me a cobblestone wall, 5 blocks long"
2. → Mineflayer bridge captures chat event → WebSocket → Orchestrator
3. → Orchestrator routes to Chat agent with world context + learner model state
4. → Chat agent returns: response ("On it!") + task_description ("Build 5-block cobblestone wall east of player") + learner_events ([])
5. → Orchestrator attaches: code_style ("explicit_repetition" — from active challenge) + concept_level (1) + filtered skill library
6. → Code agent returns: Python code (25 place_block calls with `block = "cobblestone"` variable)
7. → AST validator checks: all nodes in Level 1 allowlist? ✓. Max nesting depth ≤ 1? ✓. Max lines ≤ 40? ✓ (30 lines).
8. → Sandbox exec: restricted namespace (only SDK functions + permitted builtins). Code runs.
9. → SDK functions → WebSocket commands → Mineflayer actions → blocks appear in Minecraft
10. → Orchestrator emits learner events: `code_generated(concepts=[variables, function_calls, arithmetic])`
11. → Learner model updates: variables remains `exposed`, function_calls remains `exposed`
12. → Challenge agent (async): observes building activity, learner model state → evaluates whether to generate new challenge situation

Each node is expandable. Clicking shows the actual data payload (JSON) at that stage. The latency for each hop is annotated. Total wall-clock time from kid's message to blocks appearing: ~12-15 seconds.

### Diagram: The Concept Ceiling

**Interactive element.** A slider at the top sets the concept level (1-5). Below, two panels:

Left panel: a code snippet that changes as the level changes. Level 1 shows 25 `place_block` calls. Level 2 shows the for-loop version. Level 3 shows a function definition. Level 4 shows list comprehension. Level 5 shows event-driven while-loop.

Right panel: the AST tree of the code, with each node colored green (permitted at this level) or red (forbidden). As the slider moves, nodes transition between green and red, showing how the allowlist expands.

The visual argument: the concept ceiling is not a simplification — it's a developmental model encoded as syntax constraints. Each level doesn't just add constructs; it expands the space of expressible programs in ways that align with the kid's growing capacity.

---

## 08 — What Generalizes

### Argument

The closing section. Pull back from Silicon Golem specifics to identify patterns that apply beyond this project.

**Prior knowledge is the most underused resource in pedagogy.** Most teaching systems start from "the learner knows nothing about this domain." But expertise in adjacent domains creates conceptual footholds that dramatically reduce the learning curve — if the system is designed to find and leverage them. The Minecraft-to-Python mapping isn't unique; similar mappings exist wherever a rich interactive domain meets a formal notation system. Music production → signal processing. Cooking → chemistry. Game modding → software engineering. The design pattern is: identify the prior knowledge, map it to formal concepts, provide notation at the moment of need.

**Constraint propagation from a single source of truth.** The concept allowlist pattern — one artifact driving multiple subsystems — is applicable wherever a system needs to maintain consistency across representations. The key insight: the allowlist isn't a configuration file; it's the system's theory of the learner, and all components must agree on that theory. When you find yourself maintaining parallel constraints that could diverge, you have an allowlist problem.

**Manufactured situations, not lessons.** The kishōtenketsu challenge structure encodes a general principle: the best learning happens when the learner encounters a gap between what they know and what they want to do, in a context where they care about the outcome. The teacher's job is to manufacture situations where that gap appears naturally — not to explain the gap, not to fill it, just to make it visible. This is Kapur's productive failure applied as system design rather than classroom pedagogy.

**The Orient-Execute-Reflect heuristic applied to design.** The places where Silicon Golem's design is strongest (allowlist, prompts, bridge protocol) are the places where the Pólya cycle was applied most carefully: understand the constraint space, devise an approach, implement, verify against constraints. The places where the design has the most uncertainty (BKT parameters, timing rules, pattern detection) are where the cycle was abbreviated. The meta-lesson: the heuristic doesn't guarantee good design, but skipping it reliably produces designs with hidden uncertainty. AB++ is right that this pattern is convergent across domains — and the convergence is itself evidence that it captures something real about how understanding compounds.

**Agent architecture is fractal.** The most effective pattern for building AI systems with AI tools turns out to be the same pattern the systems themselves use: specialize agents by optimization target, coordinate through shared contracts (design docs at build-time, allowlists at runtime), verify at integration boundaries. Boris Cherny's Claude Code practices — parallel worktrees, model-appropriate task allocation, CLAUDE.md as compounding knowledge, verification loops — aren't just productivity tricks. They're the build-time expression of the same separation-of-concerns principle that makes the runtime's four-agent topology work. When you find the same architecture appearing at both levels, it's evidence that the pattern captures something real about how complex cognitive work decomposes.

**Closing image.** Return to the opening scene: a kid and a Minecraft world. But now the kid has a golem. The golem builds what the kid asks for, in visible Python. The kid reads the code not because they were told to, but because they want to know how to make the wall taller. The notation finds its host because the concept was already there, waiting for a name.

---

## Diagram Inventory (for handoff to thbrdy-site session)

| # | Name | Type | Section | Complexity |
|---|------|------|---------|------------|
| 1 | Concept Transfer Gap | Two-column with directional arrows | 01 | Medium — CSS grid + hover interactions |
| 2 | The Notation Bridge | Three-stage animation (gameplay → verbose code → loop) | 02 | High — scroll-triggered reveal, scrollable center panel |
| 3 | Phase Transition Map | State diagram with annotations | 03 | Medium — SVG or CSS, hover to show challenge mechanisms |
| 4 | Constraint Propagation Chain | Source-of-truth → three derivation paths | 04 | High — interactive level slider, live code updates |
| 5 | Agent Topology | Message-flow diagram with trace animation | 04 | Medium — CSS grid, click to trace message path |
| 6 | Heuristic Stack | 5×3 matrix with hover annotations | 05 | Medium — CSS grid, gap highlighting |
| 7 | Fleet Mirror | Split-screen build-time ↔ runtime parallel | 06 | Medium — CSS grid, hover to highlight counterparts |
| 8 | Execution Pipeline | Horizontal pipeline with expandable nodes | 07 | High — click-to-expand, JSON payload display |
| 9 | Concept Ceiling | Slider + dual-panel (code + AST tree) | 07 | High — level slider, AST visualization, node coloring |

---

## Source Documents for Composition

The thbrdy-site cowork session will need these artifacts from the silicon-golem project:

### Must Copy
- `DECISIONS.md` — All 7 ADRs with full rationale
- `GOLEM_SDK.md` — SDK spec, concept allowlists, challenge walkthrough, code patterns
- `LEARNER_MODEL.md` — Concept registry, stage progression, BKT parameters
- `CLAUDE.md` — Architecture overview, design principles, orchestrator routing
- `prompts/chat_agent.md` — Bot personality, error translation, challenge integration
- `prompts/code_agent.md` — Code style rules, constraint handling, few-shot examples
- `prompts/challenge_agent.md` — Kishōtenketsu structure, timing rules, concept tracks
- `STATUS.md` — Implementation state for accuracy
- `BRIDGE_PROTOCOL.md` — Message protocol, error codes, event types

### For Reference (code examples in essay)
- `golem/validator.py` — AST validation implementation
- `golem/learner.py` — BKT + stage tracking implementation
- `golem/orchestrator.py` — Central coordinator implementation
- `golem/sdk.py` — SDK function implementations

---

## Structural Notes for the Composition Session

### Voice and Tone
Match Trust Topologies and Circuitry of Science: measured, precise, grounded in specifics. Each section opens with a concrete situation before extracting the principle. Avoid pedagogical jargon except when naming specific theories (Vygotsky, Singley & Anderson, etc.) — and when using theory names, explain the mechanism in one sentence, not just the citation.

### Diagrams as Arguments
Every diagram must advance the argument, not merely illustrate it. The Notation Bridge (§02) makes the directional-transfer claim structural. The Constraint Propagation Chain (§04) makes the coupling argument visible. The Concept Ceiling (§06) makes the developmental-model-as-code argument interactive. If a diagram doesn't change how the reader understands the claim, cut it.

### Things to Avoid
- Product pitch register. This is an essay about learning, design, and architecture — not a launch announcement.
- "We built a thing and it's great." The essay should be honest about the design's uncertainties: BKT parameters are guesses, timing rules are heuristics, the system hasn't been tested with real kids yet.
- Excessive technical detail. The reader should understand the architecture without needing to read the full spec docs. Use the pipeline diagram and code examples to convey mechanism; link to docs for completeness.
- The "and then we did X" chronological structure. The essay is organized by argument, not by timeline.

### ADR Status Note
ADR-003 (Agent Topology) is now Accepted — matches implementation exactly. ADR-004 (Verification Architecture) is Accepted with deferred items. The honest accounting: concept-level gating, sandbox execution (partial — restricted namespace but no dry-run against simulated world state), error personality translation, and all fallback behaviors are implemented. Three items are deferred to v2: pre-execution simulation (requires building a world-state simulator), post-execution world state validation (requires inferring expected outcomes from code), and challenge agent verification (no programmatic gate checking concept readiness before dispatch). The challenge verification gap is the most concerning — it's a guardrail against the challenge agent targeting concepts the kid isn't ready for. The essay should treat ADR-004's partial status as honest design — not everything ships in v1, and documenting what you chose to defer (and why) is as important as documenting what you built.

### Open Questions for Thomas During Composition
1. How much of the learning science research backstory belongs in the essay vs. in a separate companion piece? The Vygotsky/Singley & Anderson/Deci/Kapur foundations are substantial — they could be a section or an entire essay.
2. Should the essay address the "why not just use Scratch/ComputerCraft/Education Edition?" question explicitly, or is the opening section's failure-mode analysis sufficient?
3. How personal should the framing be? "I built this for my kid" vs. "this is a design exploration." The Trust Topologies essay is somewhat personal (building Notice), Circuitry of Science is more detached.
4. Should the implementation status (what's built, what's not) be in the essay, or does that undercut the argument? The design stands independent of whether the implementation is complete.
