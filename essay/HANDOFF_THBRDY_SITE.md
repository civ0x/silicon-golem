# Handoff: Silicon Golem Essay → thbrdy.dev Composition Session

## What This Is

A handoff package for a Cowork session in the thbrdy-site folder to compose the essay "The Notation Problem: Teaching Code Through Play" and prototype its interactive diagrams. The essay is about Silicon Golem — an AI companion system that teaches a child Python through Minecraft gameplay.

## What Exists

### Essay Skeleton
`essay/SKELETON.md` — Complete eight-section skeleton with:
- Full argument structure for each section
- Diagram specifications with implementation notes (9 interactive diagrams)
- Voice/tone guidance matched to existing thbrdy.dev essays
- Composition notes and open questions

### Source Documents (in `essay/source-docs/`)
All Silicon Golem design documents have been copied to this directory for the composition session to reference:

- `DECISIONS.md` — 7 architectural decision records with full rationale. ADR-003 Accepted; ADR-004 Accepted with deferred items (world state validation, pre-execution simulation, challenge agent verification — all documented with revisit triggers)
- `GOLEM_SDK.md` — Python SDK spec, concept allowlists (Levels 1-5), generated code patterns, full challenge walkthrough scenario
- `LEARNER_MODEL.md` — Concept registry (16 concepts), 7-stage progression, BKT parameters, prerequisite chains
- `CLAUDE.md` — Architecture overview, design principles, orchestrator routing spec, non-negotiable design rules
- `BRIDGE_PROTOCOL.md` — WebSocket message protocol, 19 actions, 12 events, error codes
- `STATUS.md` — Implementation status (what's built, what's next)
- `chat_agent.md` — Bot personality prompt, error translation rules, challenge integration
- `code_agent.md` — Code generation constraints, style directives, few-shot examples by level
- `challenge_agent.md` — Kishōtenketsu structure, timing rules, concept tracks, trigger conditions

### Reference Code (in `essay/source-docs/code/`)
Key implementation files for code examples in the essay:

- `validator.py` — AST allowlist enforcement
- `learner.py` — BKT + stage tracking
- `orchestrator.py` — Central coordinator
- `sdk.py` — SDK function implementations

## The Task for the Composition Session

### Primary Deliverable
Compose the full essay as an Astro MDX page at `src/content/writing/silicon-golem.mdx` (or equivalent path per the site's content structure). The essay should follow the patterns established by:

- `/writing/trust-topologies/` — Section numbering, concrete-to-abstract structure, CSS-only diagrams
- `/writing/the-circuitry-of-science/` — Interactive annotations, popover tooltips, decomposition visualizations
- `/writing/ab-essay/` — Framework convergence argument, matrix visualizations

### Diagrams to Prototype
Nine interactive diagrams specified in the skeleton. Priority order for prototyping:

1. **The Notation Bridge** (§02) — Three-stage scroll-triggered animation. This is the visual centerpiece.
2. **Concept Transfer Gap** (§01) — Directional arrows showing prior-knowledge reframe. Sets up the whole argument.
3. **Agent Topology** (§04) — Message-flow trace. Readers need to see the system shape.
4. **Constraint Propagation Chain** (§04) — Level slider with live code updates. Most technically demanding.
5. **Execution Pipeline** (§07) — Expandable node pipeline.
6. **Concept Ceiling** (§07) — Level slider + AST tree coloring.
7. **Phase Transition Map** (§03) — State diagram with challenge annotations.
8. **Fleet Mirror** (§06) — Build-time ↔ runtime split-screen.
9. **Heuristic Stack** (§05) — 5×3 matrix.

All diagrams: CSS-only layout (no charting/animation libraries). Intersection observer for scroll-triggered reveals. `prefers-reduced-motion` fallback to static layouts. Serif for prose content, sans-serif for diagram labels and metadata.

### Style Guidelines
- **Tone:** Measured, precise, grounded in specifics. Each section opens concrete before abstracting. No product-pitch register.
- **Diagrams are arguments.** If a diagram doesn't change how the reader understands the claim, cut it.
- **Prose over lists.** Explanations in paragraphs. Use the concept correspondences from ADR-001 as a narrative walk-through, not a table.
- **Theory citations:** Name the researcher and explain the mechanism in one sentence. "Kapur's productive failure research shows that encountering a gap between what you know and what you need — before being taught the solution — produces deeper learning than direct instruction."
- **Honest about limitations.** BKT parameters are guesses. Timing rules are heuristics. No real-kid testing yet.
- **Not chronological.** Organized by argument, not by "first we did X, then Y."

### Technical Notes for thbrdy.dev
- Site is Astro-based with MDX content collection and React island components
- Design tokens in `shared/tokens.ts`
- CSS-only layout, no layout JS
- Diagrams built from HTML/CSS + intersection observer (no external libraries)
- Serif for prose (author voice), sans for structural elements
- Read the site's existing essay pages for component patterns before building new ones

## Open Questions for Thomas

These should be resolved before or during composition:

1. **Learning science depth:** How much Vygotsky/Singley & Anderson/Deci/Kapur backstory? Could be a section or a separate companion piece.
2. **Explicit comparison to alternatives?** The opening's failure-mode analysis covers Scratch/ComputerCraft/Education Edition implicitly. Worth making explicit?
3. **Personal framing?** "I built this for my kid" vs. "this is a design exploration." Trust Topologies is somewhat personal; Circuitry is detached.
4. **Implementation status in essay?** The design argument stands independently. Does mentioning what's built vs. not undercut it?
5. **Boris practices attribution?** How prominently to cite howborisusesclaudecode.com? Footnote, inline reference, or substantial discussion?
6. **Verification gaps as essay material?** ADR-004's deferred items (no world-state simulation, no challenge agent verification gate) are honest design gaps. The skeleton now has material treating these as a design tradeoff worth discussing — "strong at syntax level, absent at semantic level." How prominent should this be? It strengthens the essay's honesty but could undercut confidence in the system if overemphasized.

## Files to Read First (Ordered)

For the composition session, read in this order:

1. `essay/SKELETON.md` — The essay structure and all section arguments
2. The site's existing essays (Trust Topologies, Circuitry of Science, AB++) for style/pattern reference
3. `essay/source-docs/DECISIONS.md` — ADRs are the backbone of §04
4. `essay/source-docs/GOLEM_SDK.md` — The challenge walkthrough is the centerpiece example
5. `essay/source-docs/LEARNER_MODEL.md` — BKT and stage progression for §07
6. Site's component/layout patterns for diagram implementation
