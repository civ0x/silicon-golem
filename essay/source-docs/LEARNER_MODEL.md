# Silicon Golem — Learner Model Schema

## Purpose

The learner model tracks what the kid knows, how confidently they know it, and what they're ready to learn next. It serves three consumers with different needs:

**Code agent** needs a binary gate: can I use construct X? The orchestrator resolves this to a concept level integer and a filtered allowlist. The learner model doesn't serve the code agent directly — it feeds the orchestrator's level-gating logic.

**Challenge agent** needs concept readiness: which concepts are ripe for advancement, how confident is the estimate, and what Minecraft contexts has the kid encountered each concept in? This is the primary consumer. The challenge agent receives the full learner model state on every observation cycle.

**Chat agent** needs situational awareness: the kid's current level (for language calibration), per-concept stages (for knowing which terms to use), and contexts_seen (for transfer bridging). It receives the same state object as the challenge agent but uses a smaller slice.

---

## Concept Registry

Every trackable concept, its prerequisites, and which level gate it belongs to.

```json
{
  "concepts": {
    "variables": {
      "level_gate": 1,
      "prerequisites": [],
      "description": "Assignment, named values, the 'obvious knob' pattern"
    },
    "function_calls": {
      "level_gate": 1,
      "prerequisites": [],
      "description": "Calling SDK functions with arguments"
    },
    "attribute_access": {
      "level_gate": 1,
      "prerequisites": ["variables"],
      "description": "Dot notation: pos.x, item.name"
    },
    "arithmetic": {
      "level_gate": 1,
      "prerequisites": ["variables"],
      "description": "Add, subtract, multiply on values"
    },
    "string_concatenation": {
      "level_gate": 1,
      "prerequisites": ["variables"],
      "description": "Building strings with + and str()"
    },
    "for_loops": {
      "level_gate": 2,
      "prerequisites": ["variables"],
      "note": "variables must be at 'modified' stage, not just 'exposed'"
    },
    "conditionals": {
      "level_gate": 2,
      "prerequisites": ["variables"],
      "note": "variables must be at 'modified' stage"
    },
    "comparison_operators": {
      "level_gate": 2,
      "prerequisites": ["conditionals"],
      "description": "==, !=, <, >"
    },
    "boolean_logic": {
      "level_gate": 2,
      "prerequisites": ["conditionals"],
      "description": "and, or, not"
    },
    "function_definitions": {
      "level_gate": 3,
      "prerequisites": ["for_loops", "conditionals"],
      "note": "for_loops must be at 'modified' stage"
    },
    "return_values": {
      "level_gate": 3,
      "prerequisites": ["function_definitions"],
      "description": "return statements in kid-authored functions"
    },
    "lists": {
      "level_gate": 4,
      "prerequisites": ["for_loops"],
      "note": "for_loops must be at 'modified' stage"
    },
    "dictionaries": {
      "level_gate": 4,
      "prerequisites": ["lists"],
      "description": "Key-value mappings, inventory-as-dict pattern"
    },
    "while_loops": {
      "level_gate": 5,
      "prerequisites": ["for_loops", "conditionals"],
      "description": "Event loops, patrol routes, collect-until patterns"
    },
    "string_formatting": {
      "level_gate": 5,
      "prerequisites": ["variables", "string_concatenation"],
      "description": "F-strings"
    }
  }
}
```

### Prerequisite Semantics

A concept's prerequisites must reach a minimum stage before the concept becomes eligible for introduction. The default minimum is `modified` — the kid has not just seen the prerequisite, they've actively engaged with it. This is the Crawl-Walk-Run principle: you don't walk until you've crawled confidently.

Exception: Level 1 concepts (`variables`, `function_calls`) have no prerequisites. They're introduced through the kid's first interaction with the bot.

The concept readiness computation the orchestrator sends to the challenge agent:

```
ready_to_introduce(concept):
    return concept.stage == "none"
       AND all prerequisites at stage >= "modified"
       AND all prerequisites at p_mastery >= 0.70

ready_to_advance(concept):
    return concept.stage NOT IN ("none", "composed")
       AND concept.p_mastery < mastery_threshold(concept.stage)
```

---

## Stage Progression

Seven stages, representing qualitatively different relationships between the kid and a concept. These are not a mastery scale — they describe *what kind of interaction the kid has had*. BKT probability provides the quantitative confidence within each stage.

```
none → exposed → read → modified → authored → debugged → composed
```

| Stage | What It Means | How the Kid Got Here |
|---|---|---|
| `none` | Kid hasn't encountered this concept in code | Default state |
| `exposed` | Concept appeared in generated code the kid saw | Bot generated code containing the construct; code was visible in panel |
| `read` | Kid actively engaged with the code containing this concept | Kid scrolled to it, asked about it, or commented on it |
| `modified` | Kid changed code involving this concept and re-ran | Kid edited a variable value, loop bound, conditional expression, etc. |
| `authored` | Kid wrote code using this concept from scratch | Kid typed new code in the panel using the construct |
| `debugged` | Kid identified and fixed a bug involving this concept | Kid saw an error, located the problem in code, and corrected it |
| `composed` | Kid used this concept as scaffolding while working with another concept | Kid wrote a for-loop (composed) to support a function they were authoring |

### Stage Properties

**Stages are monotonically non-decreasing within a session.** A kid doesn't go from `modified` back to `exposed`. Across sessions, stage persists — the kid picks up where they left off.

**`composed` is a gate, not a mastery measure.** It answers the question: "Is this concept stable enough that the challenge engine can use it as assumed knowledge while teaching something else?" A concept at `composed` is load-bearing — the kid uses it without thinking about it, the way they use the crafting table without thinking about input-output transforms.

**`debugged` can occur at any stage from `read` onward.** A kid might debug a variable (change `"stoone"` to `"stone"`) before they've authored one from scratch. Debugging is an orthogonal skill, but in the stage progression it's placed after `authored` because the challenge engine targets it there — you don't design debugging challenges until the kid is authoring code. If a kid debugs earlier (spontaneously), the stage advances; the model captures the observation even if it wasn't targeted.

### Stage Transition Rules

Each transition is triggered by a specific observable event. The orchestrator evaluates these rules when it receives learner model events from the chat agent.

```json
{
  "stage_transitions": {
    "none_to_exposed": {
      "trigger": "Code containing this concept was displayed in the code panel",
      "detection": "Orchestrator compares generated code's AST against concept-to-node mapping. If the code contains nodes associated with the concept AND the code was displayed (not rejected by validator), the concept is exposed.",
      "requires_event": false,
      "note": "This is the only transition that doesn't require a chat agent event. The orchestrator detects it from code generation + display."
    },
    "exposed_to_read": {
      "trigger": "Kid actively engaged with code containing this concept",
      "chat_agent_events": ["code_inspected", "code_read", "concept_asked"],
      "detection_detail": "code_inspected: kid scrolled to the region of code containing this concept (orchestrator cross-references code_panel_scroll line range with concept location in generated code). code_read: kid asked about or commented on the code. concept_asked: kid explicitly asked what a construct is.",
      "minimum_occurrences": 1
    },
    "read_to_modified": {
      "trigger": "Kid modified code involving this concept and re-ran successfully",
      "chat_agent_events": ["code_modified"],
      "detection_detail": "Orchestrator receives code_panel_edit event, diffs the old and new code, identifies which concepts were affected by the edit. If the modified code runs successfully AND the diff touches lines containing this concept's AST nodes, transition fires.",
      "requires_successful_execution": true
    },
    "modified_to_authored": {
      "trigger": "Kid wrote new code using this concept from scratch",
      "chat_agent_events": ["code_authored"],
      "detection_detail": "Kid added new lines to the code panel (not modified existing lines) that contain this concept's AST nodes. The distinction between 'modified' and 'authored' is: modification changes an existing value within an existing structure; authoring creates new structure.",
      "minimum_occurrences": 1,
      "note": "This is the hardest transition. See challenge agent prompt for scaffolding strategies (partial completion, template filling, paired authoring)."
    },
    "authored_to_debugged": {
      "trigger": "Kid identified and fixed a bug involving this concept",
      "chat_agent_events": ["code_debugged"],
      "detection_detail": "A code_panel_run produced an error. Subsequently, the kid edited code touching this concept's nodes and re-ran successfully. The orchestrator tracks the error→edit→success sequence.",
      "requires_error_then_fix": true
    },
    "debugged_to_composed": {
      "trigger": "Kid used this concept as scaffolding while working with a different concept at 'authored' or higher stage",
      "chat_agent_events": ["concept_used"],
      "detection_detail": "In a code authoring or debugging episode targeting concept B, the kid wrote code that uses concept A without hesitation, error, or assistance. Concept A was instrumentally used, not the focus.",
      "note": "This transition is evaluated retrospectively. When the orchestrator processes an 'authored' or 'debugged' event for concept B, it checks whether concept A was present in the same code and used correctly. If so, concept A advances to 'composed'."
    }
  }
}
```

### Early Occurrence Handling

Some transitions can fire out of order. The rules:

- If a kid *authors* code for a concept that's at `exposed`, skip `read` and `modified` — advance directly to `authored`. The kid demonstrated a superset of the skipped stages.
- If a kid *debugs* code for a concept that's at `read`, advance to `debugged`. The intermediate stages were implicitly demonstrated.
- `composed` can only be reached through `debugged` or `authored`. You can't compose with a concept you've only modified — modification shows you can tweak a value, not that you can deploy the construct as structural scaffolding.

The general principle: stages can be skipped forward, never backward. If the kid demonstrates a higher-stage behavior, credit it.

---

## Bayesian Knowledge Tracing (BKT)

BKT provides a quantitative confidence estimate *within* each stage. The stage progression tells us what kind of relationship the kid has with a concept; BKT tells us how consistently they exercise it.

### The Model

Standard four-parameter BKT per concept:

| Parameter | Symbol | Description | Default |
|---|---|---|---|
| Prior knowledge | P(L₀) | Probability the kid already knows the concept before any observation | 0.0 |
| Learn rate | P(T) | Probability of transitioning from unknown to known on each opportunity | Varies by concept (see below) |
| Slip | P(S) | Probability of incorrect response despite mastery | 0.10 |
| Guess | P(G) | Probability of correct response despite non-mastery | 0.20 |

### Why These Defaults

**P(L₀) = 0.0.** We assume no prior Python knowledge. This is conservative — a kid who already knows some Python will advance through stages rapidly, and BKT's learn rate will adjust the posterior quickly. Better to underestimate and be surprised than overestimate and generate confusing code.

**P(S) = 0.10.** Kids slip — typos, misclicks, distraction. Minecraft is a rich environment with many distractions. But 10% is low enough that consistent errors are treated as genuine non-mastery rather than bad luck.

**P(G) = 0.20.** A kid can sometimes get a correct result by accident — copying the bot's pattern without understanding, or making a change that happens to work. The 20% guess rate means a single successful observation doesn't spike confidence too high. We need repeated success to confirm mastery.

**P(T) varies by concept** because some concepts click faster than others given the Minecraft-as-prior-knowledge framing:

```json
{
  "learn_rates": {
    "variables": 0.30,
    "function_calls": 0.25,
    "attribute_access": 0.25,
    "arithmetic": 0.20,
    "string_concatenation": 0.15,
    "for_loops": 0.15,
    "conditionals": 0.15,
    "comparison_operators": 0.20,
    "boolean_logic": 0.12,
    "function_definitions": 0.10,
    "return_values": 0.10,
    "lists": 0.12,
    "dictionaries": 0.10,
    "while_loops": 0.10,
    "string_formatting": 0.20
  }
}
```

Variables learn fast (0.30) because Minecraft players already track quantities. Function definitions learn slow (0.10) because "defining a reusable recipe" is a genuine abstraction leap even with the crafting metaphor.

### What Counts as an Observation

BKT needs binary observations: correct or incorrect application of a concept. The mapping from events to observations:

| Event | Observation | Condition |
|---|---|---|
| `code_modified` | **Correct** | Modified code ran successfully and produced the intended change |
| `code_modified` | **Incorrect** | Modified code produced an error or unintended result |
| `code_authored` | **Correct** | Authored code ran successfully |
| `code_authored` | **Incorrect** | Authored code produced an error |
| `code_debugged` | **Correct** | Kid identified and fixed the bug successfully |
| `error_encountered` | **Incorrect** | Error occurred in code the kid wrote or modified (not bot-generated code) |
| `concept_used` | **Correct** | Kid used the concept correctly in a new context without assistance |

Events that do NOT produce BKT observations: `code_inspected`, `code_read`, `concept_asked`, `disengaged`. These are stage-relevant (they can advance from `exposed` to `read`) but they're not skill demonstrations. BKT only updates on opportunities where the kid *did something* with the concept and we can assess success or failure.

### BKT Update Rule

Standard forward algorithm. After observing response `r` (correct or incorrect) for concept `c`:

```
If r = correct:
    P(L_n) = P(L_{n-1}) * (1 - P(S)) / (P(L_{n-1}) * (1 - P(S)) + (1 - P(L_{n-1})) * P(G))

If r = incorrect:
    P(L_n) = P(L_{n-1}) * P(S) / (P(L_{n-1}) * P(S) + (1 - P(L_{n-1})) * (1 - P(G)))

Then apply learn rate:
    P(L_n) = P(L_n) + (1 - P(L_n)) * P(T)
```

The result is stored as `p_mastery` in the concept state.

### Mastery Thresholds

Different stages have different thresholds for what "confident enough" means, because the stakes change:

```json
{
  "mastery_thresholds": {
    "stage_advance_minimum": 0.70,
    "challenge_targeting": 0.50,
    "level_gate_promotion": 0.85,
    "composed_prerequisite": 0.90
  }
}
```

**stage_advance_minimum (0.70):** Before the challenge engine targets the next stage for a concept, BKT confidence at the current stage should be at least 0.70. Don't push to authoring if modification is still shaky.

**challenge_targeting (0.50):** The challenge engine can target a concept for practice (within the current stage) once p_mastery reaches 0.50. Below 0.50, the system waits for organic interactions rather than manufacturing challenges.

**level_gate_promotion (0.85):** To promote the kid from Level N to Level N+1, all concepts at Level N that have prerequisites met must reach p_mastery ≥ 0.85 at the `modified` stage. This is the code agent's gate — it determines what constructs are in the permitted set.

**composed_prerequisite (0.90):** To use a concept as a prerequisite for introducing a new concept, it must be at `modified` stage with p_mastery ≥ 0.90. Higher bar because the concept will be assumed knowledge in the new concept's challenges.

---

## Concept-to-AST-Node Mapping

The orchestrator uses this to detect which concepts appear in generated code (for `none → exposed` transitions) and which concepts were affected by code edits (for `read → modified` transitions).

```json
{
  "concept_ast_mapping": {
    "variables": ["Assign"],
    "function_calls": ["Call"],
    "attribute_access": ["Attribute"],
    "arithmetic": ["BinOp", "Add", "Sub", "Mult"],
    "string_concatenation": ["BinOp_with_str"],
    "for_loops": ["For"],
    "conditionals": ["If", "IfExp"],
    "comparison_operators": ["Compare", "Eq", "NotEq", "Lt", "Gt", "LtE", "GtE"],
    "boolean_logic": ["BoolOp", "And", "Or", "Not"],
    "function_definitions": ["FunctionDef"],
    "return_values": ["Return"],
    "lists": ["List", "Subscript"],
    "dictionaries": ["Dict"],
    "while_loops": ["While"],
    "string_formatting": ["JoinedStr", "FormattedValue"]
  }
}
```

Note: `string_concatenation` vs `arithmetic` both involve `BinOp`, but the operand types distinguish them. The orchestrator checks whether the `BinOp` operates on strings (concatenation) or numbers (arithmetic). The `BinOp_with_str` marker is a hint to the implementation, not a real AST node.

---

## Contexts

Minecraft gameplay contexts. The learner model tracks which contexts each concept has appeared in. The challenge agent uses this to vary practice contexts for transfer.

```json
{
  "contexts": {
    "building": "Placing blocks, constructing structures, spatial layout",
    "mining": "Breaking blocks, digging tunnels, collecting resources",
    "crafting": "Using crafting recipes, managing materials",
    "farming": "Planting, harvesting, animal husbandry",
    "survival": "Day/night management, shelter, food, health",
    "combat": "Dealing with hostile mobs, weapons, armor",
    "exploration": "Moving through the world, finding biomes, mapping",
    "redstone": "Circuits, mechanisms, automation (advanced)"
  }
}
```

The orchestrator determines the current context from world state events (block placement → building, block breaking in underground → mining, crafting table interaction → crafting, etc.). Context detection is heuristic and doesn't need to be precise — it's used for challenge variety, not for gating.

Transfer research (Barnett & Ceci, 2002) suggests a concept should appear in 3-5 different contexts before the model treats it as transferable. The challenge agent already knows this (it's in the challenge prompt's `varied_practice_note`). The learner model's job is to track `contexts_seen` so the challenge agent can select underrepresented contexts.

---

## Level Gate Logic

The code agent's construct ceiling is determined by the kid's current level. Level promotion is the orchestrator's decision, based on learner model state.

```
current_level(learner_state):
    For each level L from highest to 1:
        required_concepts = all concepts where level_gate <= L-1
        If every required_concept has:
            stage >= "modified"
            AND p_mastery >= level_gate_promotion (0.85)
        Then return L
    Return 1
```

In practice, this means:

- **Level 1 → 2:** `variables` must be at `modified` with p_mastery ≥ 0.85.
- **Level 2 → 3:** All Level 1 concepts plus `for_loops` and `conditionals` must be at `modified` with p_mastery ≥ 0.85.
- **Level 3 → 4:** All Level 1-2 concepts plus `function_definitions` must be at `modified` with p_mastery ≥ 0.85.

Level promotion is conservative. The kid should be comfortable with the current level's concepts before seeing new ones. The 0.85 threshold means roughly 5-6 consecutive successful interactions with each concept.

Level demotion does not occur. If a kid struggles after promotion, the challenge engine targets the weak concept for reinforcement within the current level rather than reducing the construct ceiling.

---

## Per-Concept State Object

The full state for each concept, as stored by the learner model and passed to agents:

```json
{
  "variables": {
    "stage": "modified",
    "p_mastery": 0.82,
    "contexts_seen": ["building", "crafting"],
    "total_observations": 7,
    "correct_observations": 6,
    "last_observation_timestamp": "2026-03-05T14:32:00Z",
    "stage_history": [
      {"stage": "exposed", "timestamp": "2026-03-05T14:05:00Z"},
      {"stage": "read", "timestamp": "2026-03-05T14:12:00Z"},
      {"stage": "modified", "timestamp": "2026-03-05T14:28:00Z"}
    ]
  }
}
```

**Agents receive a trimmed view.** The challenge agent and chat agent see `stage`, `p_mastery`, and `contexts_seen`. The `total_observations`, `correct_observations`, `last_observation_timestamp`, and `stage_history` are internal to the learner model — used for persistence, debugging, and the BKT computation. Don't bloat the agent context windows with operational metadata.

---

## The Disengagement Signal

`disengaged` is not a concept event — it's a session-level signal. When the chat agent emits `disengaged`, the learner model records it in a separate channel:

```json
{
  "session_signals": {
    "disengagement_events": [
      {
        "timestamp": "2026-03-05T14:35:00Z",
        "detail": "Kid said 'this is boring' after third wall-building task",
        "active_challenge_id": "uuid-or-null",
        "current_activity": "building"
      }
    ]
  }
}
```

The challenge engine reads this to adjust pacing, not concept targeting. Two or more disengagement events in a session should suppress new challenges for the remainder of the session. The challenge agent's existing timing rules (max 1 per 15 minutes, no challenges in first 10 or last 5 minutes) provide the primary throttle; disengagement signals add a dynamic override.

Disengagement does NOT penalize concept mastery. A bored kid isn't a confused kid. BKT is unaffected.

---

## Persistence

The learner model persists to disk as JSON after every state change. The file lives at `data/learner_state.json`. The schema:

```json
{
  "version": 1,
  "player_name": "Alex",
  "created": "2026-03-05T13:00:00Z",
  "last_updated": "2026-03-05T14:35:00Z",
  "current_level": 1,
  "concepts": {
    "variables": { "...per-concept state object..." },
    "function_calls": { "..." }
  },
  "session_signals": {
    "disengagement_events": []
  },
  "session_history": {
    "total_sessions": 3,
    "total_play_minutes": 87,
    "concepts_introduced_per_session": [2, 1, 0]
  }
}
```

Session history is minimal — just enough for the challenge engine to gauge pacing across sessions. The detailed interaction log is not persisted (it would grow without bound and the BKT posterior captures the relevant information).

---

## Implementation: learner.py Interface

The orchestrator calls the learner model synchronously. Target latency: <100ms per update (see ADR-003).

```python
class LearnerModel:
    """Tracks kid's concept mastery. Synchronous, <100ms per operation."""

    def __init__(self, player_name: str, state_path: str = "data/learner_state.json"):
        """Load or create learner state for the given player."""

    def process_event(self, event: LearnerEvent) -> StateChange | None:
        """
        Process a learner model event from the chat agent.
        Returns a StateChange if any concept's stage or p_mastery changed meaningfully,
        None if the event didn't affect state.

        The orchestrator uses the return value to decide whether to re-invoke
        the challenge agent (stage change) or just update the next agent call's
        context (p_mastery change).
        """

    def process_code_displayed(self, code: str) -> list[str]:
        """
        Called by orchestrator after code is shown in the panel.
        Parses the code's AST, identifies concepts present, advances any
        'none' concepts to 'exposed'. Returns list of newly exposed concepts.
        """

    def get_agent_state(self) -> dict:
        """
        Returns the trimmed state for agent context injection.
        Includes: current_level, and per-concept: stage, p_mastery, contexts_seen.
        """

    def get_concept_readiness(self) -> dict:
        """
        Returns readiness assessment for the challenge agent.
        Includes: ready_to_introduce, ready_to_advance, prerequisites_not_met,
        with reasons.
        """

    def get_current_level(self) -> int:
        """Returns the kid's current concept level (1-5+)."""

    def save(self) -> None:
        """Persist state to disk."""
```

### Event Types

```python
@dataclass
class LearnerEvent:
    event: str          # One of the 9 event types from chat agent
    concept: str | None # Which concept was involved (None for disengaged)
    detail: str         # Human-readable description
    context: str        # Current Minecraft context
    success: bool | None # For BKT: True=correct, False=incorrect, None=not applicable
    timestamp: datetime
```

The `success` field is set by the orchestrator, not the chat agent. The chat agent emits the event with qualitative detail; the orchestrator determines success/failure from execution results and code diffs, then passes the enriched event to the learner model.

---

## Open Questions for Implementation

**BKT parameter tuning.** The learn rates and slip/guess parameters are educated guesses from the cognitive science literature and Minecraft-as-prior-knowledge reasoning. They should be treated as initial values. Once the system is running with real kids, the parameters should be calibrated against observed learning trajectories. The `total_observations` and `correct_observations` fields enable offline recalibration.

**`string_concatenation` vs `arithmetic` disambiguation.** Both map to `BinOp`. The implementation needs to inspect operand types to distinguish them. This requires running type inference on the generated code's AST, which adds complexity to `process_code_displayed`. For v1, a heuristic approach (if either operand is a string literal or `str()` call, it's concatenation) is probably sufficient.

**Cross-session decay.** Should p_mastery decay between sessions? Spacing effect research (Cepeda et al., 2006) suggests that longer gaps between practice lead to more forgetting but also more durable re-learning. For v1, no decay — the model assumes the kid picks up where they left off. If playtesting reveals that kids forget constructs between sessions, add a decay factor keyed to days-since-last-observation.
