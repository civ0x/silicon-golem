# Research Session Prompts

Three targeted research sessions for the essay "The Notation Problem: Teaching Code Through Play." Each prompt is designed to be pasted into a fresh Claude chat session and produce output that feeds directly into the essay outline.

---

## Session 1: Papert and Constructionism

```
I'm writing an essay called "The Notation Problem: Teaching Code Through Play" about Silicon Golem, an AI companion system that teaches a child Python through Minecraft gameplay. The core design insight: kids who play Minecraft already think computationally (they track resource counts, execute crafting recipes, batch-process, make conditional decisions). The system doesn't teach new concepts — it provides formal notation for concepts the kid already has, through an AI bot that joins their Minecraft world, generates visible Python code, and lets the kid gradually take over writing it.

I need a deep research pass on Seymour Papert and constructionism for this essay. Papert is the philosophical ancestor of this project and currently absent from the draft — that's a gap I need to fill.

What I need:

1. **MINDSTORMS (1980) — the specific ideas that apply.** Not a book summary. I need the particular claims Papert makes about:
   - Children as builders of their own intellectual structures (and how Logo was designed to enable this)
   - The distinction between "teaching" and creating environments where learning happens
   - His concept of "objects to think with" — how does this map to visible Python code in a Minecraft world?
   - The "Mathland" idea — an environment where math is the natural language, the way French is natural in France. Minecraft as a "Codeland" where Python is the natural language for getting things done?
   - His critique of "school math" vs. real mathematical thinking — does this parallel exist for "school coding" vs. real computational thinking?

2. **Constructionism vs. constructivism.** Papert extended Piaget. What's the specific distinction? Piaget says children construct knowledge internally. Papert adds: they construct it especially well when they're constructing something external. The Minecraft build IS the external construction. The Python code IS the artifact. How does this differ from, say, Scratch's approach (which is also constructionist)?

3. **The Logo legacy and its lessons.** Logo taught programming through a turtle that moved on screen. Silicon Golem teaches programming through a bot that moves in Minecraft. The structural parallel is obvious, but:
   - What worked about Logo that I should preserve?
   - What failed or stalled that I should learn from?
   - How does Logo's "low floor, high ceiling, wide walls" design principle apply here?
   - Did Papert address the transfer problem (Logo skills → general programming)?

4. **Quotes or passages I might use.** I need 2-3 specific Papert quotes that would work as epigraph candidates or inline citations. The essay's tone is measured and specific — I need quotes that are precise, not inspirational poster material. Particularly interested in anything Papert said about:
   - The relationship between play and formal knowledge
   - Why children should encounter powerful ideas through use, not instruction
   - The role of the computer as a medium the child programs, not a medium that programs the child

5. **Where Papert would push back on my design.** If Papert read the Silicon Golem design docs, what would concern him? The system uses AI to generate code FOR the kid initially — is that constructionist or does it undermine construction? The concept allowlist constrains what the kid sees — is that scaffolding or gatekeeping? Be honest about the tensions.

Format: Organize by the 5 points above. For each, give me the specific ideas with enough context to write about them with authority, not just cite them. I need to understand the mechanisms, not just the conclusions.
```

---

## Session 2: Bloom's 2-Sigma and Gee's Learning Principles

```
I'm writing an essay called "The Notation Problem: Teaching Code Through Play" about Silicon Golem, an AI companion system that teaches a child Python through Minecraft gameplay. The system uses an AI bot that joins the kid's Minecraft world, generates visible Python code in response to commands, and uses a learner model + challenge engine to manufacture situations where programming concepts reveal themselves through play.

I need deep research on two theorists who are critical to the design: Benjamin Bloom and James Paul Gee. Both are currently cited in my outline but without enough specificity to write with authority.

**Part 1: Bloom's 2-Sigma Problem (1984)**

The design claim: Silicon Golem approximates 1:1 tutoring through an AI companion that maintains an individual learner model, adapts code complexity to the kid's concept ceiling, and manufactures challenges matched to readiness. The golem IS the 1:1 tutor — but inverted (the kid is the master, the bot is the apprentice).

What I need:
1. What were Bloom's actual experimental conditions? What specifically produced the 2σ effect — was it the 1:1 ratio, the mastery learning, the feedback frequency, or some combination?
2. How has the 2-sigma claim held up? VanLehn (2011) and others have revisited it. What replicates and what doesn't? I need to cite this honestly.
3. What specific features of effective tutoring does the research identify? (e.g., immediate feedback, adaptive difficulty, formative assessment, sustained attention to one learner). Which of these does Silicon Golem provide, and which does it lack?
4. Bloom's mastery learning component — the idea that students must demonstrate mastery before advancing. The learner model requires p_mastery ≥ 0.85 before level promotion. Is this Bloom's threshold or a different operationalization?
5. The relationship between Bloom's mastery learning and the concept allowlist — the allowlist IS a mastery gate implemented as syntax constraints. Is this a valid application of Bloom, or am I stretching?

**Part 2: James Paul Gee — "What Video Games Have to Teach Us About Learning and Literacy" (2003/2007)**

The design claim: Minecraft already implements Gee's learning principles. Silicon Golem adds a formal notation layer that makes the implicit learning explicit without breaking the game.

What I need:
1. The specific principles from Gee's 36 that directly shape Silicon Golem's design. For each, I need: the principle name as Gee states it, a one-sentence mechanism, and how it maps to a specific design decision. The ones I think apply:
   - Regime of Competence Principle → concept ceiling / allowlist
   - Probing Principle → kishōtenketsu probe-hypothesize-reprobe cycle
   - Identity Principle → skill library author attribution (bot/modified/kid)
   - Achievement Principle → no extrinsic rewards, play IS the reward
   - Transfer Principle → varied Minecraft contexts for each concept
   - Semiotic Domains Principle → Minecraft as a semiotic domain with its own literacy
   - Any others I'm missing?

2. Gee's concept of "situated meaning" — meaning grounded in embodied experience, not abstract definition. This is exactly the design philosophy: `block = "cobblestone"` gets its meaning from the kid seeing cobblestone blocks appear, not from a definition of "variable." How does Gee articulate this?

3. Gee's distinction between "learning about" and "learning to be." The kid isn't learning about Python — they're learning to be someone who uses Python to control their Minecraft world. How does Gee frame this, and does it map to the five-phase progression (Director → Observer → Modifier → Author → Architect)?

4. Has Gee addressed Minecraft specifically in any of his work? If so, what does he say?

5. Gee's concept of "affinity spaces" vs. formal instruction. The Minecraft world with the golem is an affinity space where code is the medium of participation. Does Gee's framework support this reading?

Format: Organize as Part 1 (Bloom) and Part 2 (Gee), with numbered responses matching my questions. Include specific page numbers, paper titles, or chapter references where possible — I want to be able to trace claims back to sources.
```

---

## Session 3: Block-to-Text Transition and the Scratch Ceiling

```
I'm writing an essay called "The Notation Problem: Teaching Code Through Play" about Silicon Golem, an AI companion system that teaches a child Python through Minecraft gameplay. The essay's opening argument hinges on a claim about existing approaches to teaching kids to code: visual block languages (Scratch, MakeCode) create a transfer problem when kids move to text-based languages, and text-first approaches in game contexts (ComputerCraft, Minecraft Education Edition) have too much ceremony relative to intent.

I need this claim to be evidence-based, not assertion. Research the block-to-text transition literature.

**Part 1: The "Scratch Ceiling" — What's the Evidence?**

1. What does the research actually say about the transition from block-based to text-based programming? Who has studied this, what were the findings, and how strong is the evidence?
2. Is "Scratch ceiling" an established term in the literature, or is it informal? If informal, what's the proper framing?
3. Singley & Anderson (1989) — "Transfer of Cognitive Skill." The specific claim I'm making: transfer depends on identical production rules between training and target. Scratch-to-Python transfer is weak because the production rules (drag-and-snap vs. type syntax) differ even when the concepts (loops, variables, conditionals) are shared. Is this a fair reading of Singley & Anderson, or am I oversimplifying?
4. What research exists on hybrid approaches — showing blocks AND text simultaneously? Alrubaye et al. (2019) is cited in my outline as showing >30% improvement with hybrid viewing. Verify this: what was the actual study, what was measured, and is 30% the right number?
5. Resnick's own framing of Scratch — what does the Scratch team say Scratch is designed to do? I want to critique fairly. If Scratch isn't designed for Python transfer, I shouldn't fault it for not achieving it. What IS Scratch's stated pedagogical goal?

**Part 2: Situated Learning and Apprenticeship**

6. Lave & Wenger (1991) — "Situated Learning: Legitimate Peripheral Participation." Silicon Golem inverts the apprenticeship model: instead of the novice watching the expert, the kid (master) directs the bot (apprentice), and the bot's visible code is the artifact of peripheral participation — except the kid is at the center and the bot is peripheral. Does Lave & Wenger's framework support this inversion, or does it break?
7. The concept of "legitimate peripheral participation" — the newcomer participates in real practice at the edges before moving to fuller participation. In Silicon Golem: the kid starts by directing (commanding in English), then observing code, then modifying, then authoring. Is this a form of legitimate peripheral participation where "the practice" is programming and the kid moves from edge to center?

**Part 3: Error Framing and Mindset**

8. Dweck's growth mindset research — the Silicon Golem bot absorbs all errors at early levels ("I got confused" not "SyntaxError on line 5"). The design rationale: if the kid believes they caused the error, they stop experimenting; if the bot caused it, experimentation is safe. Is there research that directly supports this error-attribution design? Beyond Dweck, anything on how error framing affects willingness to experiment in programming contexts specifically?
9. Kapur's productive failure — I already have this cited (Cohen's d = 0.36, 12K+ participants). But: what are the boundary conditions? When does productive failure NOT work? Kirschner, Sweller & Clark (2006) argue that minimal guidance fails for novices. The kishōtenketsu structure is designed to thread this needle — the twist recontextualizes what was shown, it doesn't introduce new information. Does Kapur address this boundary?

**Part 4: What I Might Be Missing**

10. Are there other researchers or frameworks I should know about for an essay on teaching programming through play? Specifically interested in anyone who has studied:
    - Programming education in game contexts (not gamified education — actual game contexts)
    - The role of AI companions or agents in learning
    - Intrinsic motivation and programming education for children ages 9-12

Format: Number your responses to match my questions. For each, give me: the finding, the strength of evidence, the specific citation (authors, year, title), and a one-sentence formulation I could use in the essay. Flag anything where I'm making a stronger claim than the evidence supports.
```
