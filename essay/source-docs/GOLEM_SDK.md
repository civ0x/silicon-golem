# Silicon Golem — Python SDK and Code Generation Surface

## Purpose

This document defines the Python API surface that the kid sees, reads, modifies, and eventually authors. It is the load-bearing artifact of the entire system: the concept allowlist, the challenge engine, the skill library schema, and the bot's code-generation prompt all derive from what's specified here.

Design constraint: every function in this SDK must satisfy three requirements simultaneously. It must be **Minecraft-native** (the name maps to an action the kid already performs in-game, per ADR-001). It must be **real Python** (the call-site is valid Python 3, enabling transfer per Singley & Anderson). And it must **hide Mineflayer's quirks** without hiding Python's constructs (thin wrapper, not a DSL, per the constraint research verdict on abstraction wrapping).

---

## Architecture: Where the SDK Sits

```
Kid's Minecraft chat
       │
       ▼
  Chat Agent (Haiku)  ──►  "Build me a cobblestone wall"
       │
       ▼
  Code Agent (Sonnet)  ──►  Generates Python using SDK functions
       │
       ▼
  AST Validator  ──►  Checks against concept allowlist for kid's level
       │
       ▼
  Code Panel (display)  ──►  Kid sees the Python
       │
       ▼
  Execution Engine  ──►  SDK functions call Mineflayer via WebSocket bridge
       │
       ▼
  Minecraft World  ──►  Blocks appear
```

The SDK is a Python module (`golem.py`) that the execution engine imports. Each function translates a clean Python call into one or more Mineflayer operations over the WebSocket bridge. The kid never sees the bridge, the JavaScript, or the async coordination. They see Python functions with Minecraft-native names.

Every generated script begins with:

```python
from golem import *
```

At Level 1-2, this line is present but not explained — it's ambient. At Level 3+, the bot can reference it when the kid starts writing their own functions: "See that line at the top? That's where all my abilities come from. Your functions don't need that — they're yours."

---

## The SDK Function Set

### Tier 1: Actions (the bot does something in the world)

These are the verbs. Each maps to a Minecraft action the kid already performs manually.

#### Movement

```python
move_to(x, y, z)
```
Walk to the specified coordinates. Wraps pathfinder with a 30-second timeout (addressing the known pathfinder hang bug). Returns `True` if reached, `False` if timed out or no path found. The bot provides chat narration while moving.

**Mineflayer underneath:** `bot.pathfinder.setGoal(GoalBlock(x, y, z))` + timeout wrapper + `goal_reached` listener.

```python
move_to_player(name)
```
Walk to the named player. Wraps `GoalFollow` with `dynamic=True` (required or goal won't track). Takes an optional `distance` parameter (default 2 blocks).

**Why two functions instead of one:** `move_to(x, y, z)` maps to "go to coordinates" — a concept Minecraft players use (F3 screen). `move_to_player("Steve")` maps to "follow me" — the most common first command. Collapsing them into one function with overloaded signatures introduces type-checking concepts the kid doesn't need yet.

#### Block Interaction

```python
place_block(x, y, z, block_type)
```
Place a block of the specified type at the given coordinates. The SDK handles: finding the block in inventory (or reporting what's missing), equipping it, navigating to within placement range, computing the correct reference block and face vector (Mineflayer's most confusing API), and placing.

**What it hides:** The `referenceBlock` / `faceVector` semantics. Mineflayer's `placeBlock` requires you to specify an existing block to place *against* and a direction vector pointing *away from* that block. This is incomprehensible to a child (and to most adults). The SDK computes this from the target coordinates.

**What it doesn't hide:** The coordinates are explicit. The block_type is a string the kid can read and change. If inventory is insufficient, the error comes through as a chat message: "I don't have any cobblestone — I need some to build with."

```python
dig_block(x, y, z)
```
Break the block at the given coordinates. Equips the best available tool automatically. Returns the block type that was broken.

**Mineflayer underneath:** Navigate to within range → `bot.dig(bot.blockAt(Vec3(x,y,z)))`. Re-queries `blockAt` fresh to avoid stale references.

```python
dig_area(x1, y1, z1, x2, y2, z2)
```
Break all blocks in the rectangular region defined by two corners. This is a **convenience wrapper** — at Level 1, it lets the bot respond to "dig a hole" without generating a triple-nested loop the kid can't read. At Level 2+, the challenge engine can offer the single-call version *or* generate the explicit loop version depending on the pedagogical goal.

#### Crafting and Items

```python
craft(item_name, count=1)
```
Craft the specified item. The SDK handles: checking recipes, finding or navigating to a crafting table if needed, and executing the craft. Returns the number of items successfully crafted.

**Why not `craft(recipe)`:** Minecraft players say "craft a pickaxe," not "execute recipe #47." The item name is the natural parameter. The SDK resolves the recipe internally.

```python
give(item_name, count=1)
```
Give items to the nearest player (almost always the kid). Navigates to within tossing range and drops the items.

```python
equip(item_name)
```
Hold the specified item. Handles the "rapid equip" bug (server rejected transaction, issue #1556) with a small delay.

#### Observation

```python
get_position()
```
Returns the bot's current position as a `Position` object with `.x`, `.y`, `.z` attributes (integers, rounded from float). This is a synchronous read — no awaiting needed.

**Return type design:** A named object rather than a tuple, because `pos.x` reads as English ("position's x") while `pos[0]` requires index knowledge. The kid sees:

```python
pos = get_position()
place_block(pos.x + 1, pos.y, pos.z, "cobblestone")
```

Not:

```python
x, y, z = get_position()  # tuple unpacking — Level 3+ concept
```

```python
get_player_position(name)
```
Returns the named player's position. Same `Position` return type. This is how the bot knows where the kid is.

```python
find_blocks(block_type, count=1)
```
Find nearby blocks of the specified type. Returns a list of `Position` objects. Wraps `bot.findBlocks` with `bot.blockAt` to return proper position objects, not raw Vec3 (a common Mineflayer code-gen mistake per the architecture research).

**Performance note:** Capped at `maxDistance=32` by default. The Mineflayer research documented 2.5+ second latency at maxDistance=128 with rare blocks. The SDK uses a safe default and the code agent can override when appropriate.

```python
find_player(name)
```
Returns the named player's `Position`, or `None` if not found. Simpler than `get_player_position` for the case where the player might not be nearby.

```python
get_inventory()
```
Returns a list of `Item` objects, each with `.name` and `.count` attributes. Filters out empty slots.

**Return type design:** `Item` objects rather than a dictionary, for the same readability reason as `Position`. `item.name` reads as English. At Level 4 when dictionaries are introduced, the bot can show how inventory maps to `{"cobblestone": 42, "iron_ingot": 3}`.

```python
get_block(x, y, z)
```
Returns the block type (string) at the given coordinates, or `"air"` for empty space. Wraps `bot.blockAt()` with null-check for unloaded chunks.

#### Communication

```python
say(message)
```
Send a chat message in-game. This is the bot talking. At Level 1 it's used for status reporting; at Level 5 (string formatting), the kid discovers they can make the bot say computed messages.

---

### Tier 2: Compound Actions (available at all levels, but pedagogically relevant at different stages)

These exist because some common Minecraft operations can't be expressed within Level 1 constructs but kids ask for them immediately. They're "black boxes with good names" — the kid reads `collect("oak_log", 10)` and knows what it does from gameplay experience, even though the implementation involves pathfinding, tool selection, digging, and pickup.

```python
collect(block_type, count)
```
Find and break blocks of the specified type until `count` is reached or none are nearby. Returns the number actually collected. Wraps `mineflayer-collectblock`.

```python
build_line(x, y, z, direction, length, block_type)
```
Place blocks in a straight line. `direction` is one of `"north"`, `"south"`, `"east"`, `"west"`, `"up"`, `"down"`. This is the **key Level 1 → Level 2 bridge function**: at Level 1, the bot uses it as a convenience. When the challenge engine introduces loops, it generates the equivalent explicit code, and the kid can see that `build_line` was just a for-loop all along.

```python
build_wall(x, y, z, direction, length, height, block_type)
```
Place blocks in a rectangular wall. Like `build_line` but adds the height dimension. Same bridge function role — at Level 2, the bot shows the double-loop implementation.

---

### Design Decisions in the API

**No method chaining.** Every function is a standalone call. `move_to(x, y, z)` then `place_block(...)` on the next line, not `bot.move_to(...).place(...)`. Method chaining requires understanding objects and return-value semantics.

**No callbacks or event handlers.** Level 1 code is strictly sequential. Events (mob approaches, day/night change) are handled by the execution engine and surfaced as chat messages, not as code the kid sees. Event handling enters at Level 5+ via while-loops.

**String-based block and item names.** `"cobblestone"`, not `BlockType.COBBLESTONE` or `blocks["cobblestone"]`. Strings are the first data type kids encounter, they match how Minecraft players talk about items, and they're the "obvious knob" — change `"cobblestone"` to `"stone_bricks"` and the build changes. The SDK validates names internally and surfaces Minecraft-friendly errors: "I don't know what 'stoone' is — did you mean 'stone'?"

**Coordinates are always explicit.** No implicit "place block in front of bot" magic. Coordinates are the kid's first exposure to variables-as-meaningful-values (ADR-001: "they track these mentally every session"). The code should show where things go, because spatial reasoning is the Minecraft player's strongest existing skill.

**Return values are simple at Level 1.** Functions return `True`/`False`, counts (int), or single objects (`Position`, `Item`). No lists until Level 4. The compound actions (`collect`, `build_line`) return counts. The observation functions return objects with readable attributes. The code agent generates code that uses return values only via assignment: `pos = get_position()`, not `if get_position().y > 64:` (that requires attribute access inside a conditional — two concepts at once).

---

## Level 1 Concept Allowlist

This JSON artifact drives both the code agent's system prompt and the AST validator. It defines everything the code agent is permitted to generate, and everything the AST validator will accept.

```json
{
  "level": 1,
  "name": "Director",
  "description": "Kid gives commands, sees generated code. Variables and function calls only.",

  "permitted_ast_nodes": {
    "statements": [
      "Assign",
      "Expr",
      "Module"
    ],
    "expressions": [
      "Call",
      "Name",
      "Constant",
      "Attribute",
      "BinOp",
      "UnaryOp"
    ],
    "operators": [
      "Add",
      "Sub",
      "Mult"
    ],
    "other": [
      "arguments",
      "arg",
      "keyword",
      "ImportFrom",
      "alias"
    ]
  },

  "permitted_sdk_functions": [
    "move_to",
    "move_to_player",
    "place_block",
    "dig_block",
    "dig_area",
    "craft",
    "give",
    "equip",
    "get_position",
    "get_player_position",
    "find_blocks",
    "find_player",
    "get_inventory",
    "get_block",
    "say",
    "collect",
    "build_line",
    "build_wall"
  ],

  "permitted_builtins": [
    "print",
    "int",
    "str",
    "len"
  ],

  "forbidden_patterns": {
    "note": "These are the constructs NOT available at Level 1. The AST allowlist approach catches them by default — anything not in permitted_ast_nodes is rejected.",
    "explicitly_forbidden": [
      "For / While (loops)",
      "If / IfExp (conditionals)",
      "FunctionDef (function definitions)",
      "ListComp / DictComp / SetComp / GeneratorExp (comprehensions)",
      "Lambda",
      "ClassDef",
      "Try / ExceptHandler",
      "With",
      "Import (bare — only ImportFrom for golem)",
      "Global / Nonlocal",
      "Assert / Raise / Delete",
      "AsyncFor / AsyncWith / Await"
    ]
  },

  "max_nesting_depth": 1,
  "max_lines": 40,
  "max_variables": 10,
  "note_on_max_lines": "Level 1 deliberately uses repetition to set up loop introduction at Level 2. 40 lines accommodates a 5x5 grid (25 place_block calls) plus setup variables, import, and comments. The max_repeated_similar_lines heuristic below catches truly excessive repetition.",

  "code_quality_heuristics": {
    "max_repeated_similar_lines": 8,
    "note": "At Level 1, repetition is expected and pedagogically useful (it's the setup for introducing loops at Level 2). But more than ~8 near-identical lines suggests the task itself is too complex for this level."
  }
}
```

### Why These Specific Nodes

**`Assign`** — Variables. The kid's first Python concept. `height = 5`, `block = "cobblestone"`, `pos = get_position()`.

**`Expr`** — Bare function calls on their own line. `place_block(x, y, z, "stone")` as a statement.

**`Call`** — Function calls. Every SDK function. Also `print()` for debugging.

**`Name`** — Variable references. `height`, `block`, `pos`.

**`Constant`** — Literals. Numbers (`5`, `64`), strings (`"cobblestone"`), booleans (`True`).

**`Attribute`** — Dot access on objects. `pos.x`, `pos.y`, `item.name`. This is the one "advanced" node at Level 1, justified because `pos.x` reads as natural English and the Position/Item objects are fundamental to every interaction.

**`BinOp` with `Add`/`Sub`/`Mult`** — Arithmetic. `pos.x + 1`, `height * 2`. Minecraft players already do this math mentally ("I need 3 more blocks"). Restricting to add/sub/mult prevents division (float results are confusing) and modulo/power (unnecessary at this stage).

**`ImportFrom`** — Only for `from golem import *`. The AST validator specifically checks that the only ImportFrom is from the `golem` module.

---

## Generated Code Patterns at Level 1

### Pattern 1: Simple Action

Kid says: "Come here"

```python
from golem import *

player_pos = get_player_position("Alex")
move_to(player_pos.x, player_pos.y, player_pos.z)
say("I'm here! What do you need?")
```

**Pedagogical notes:** Three lines, three actions. The variable `player_pos` is meaningful — it's where the player is. The `.x`, `.y`, `.z` pattern is visible but not explained.

### Pattern 2: Variables as Knobs

Kid says: "Build me a cobblestone wall, 5 blocks long"

```python
from golem import *

pos = get_position()
block = "cobblestone"
length = 5

place_block(pos.x + 1, pos.y, pos.z, block)
place_block(pos.x + 2, pos.y, pos.z, block)
place_block(pos.x + 3, pos.y, pos.z, block)
place_block(pos.x + 4, pos.y, pos.z, block)
place_block(pos.x + 5, pos.y, pos.z, block)
```

**Pedagogical notes:** The `block` variable appears five times — changing it once changes them all. This is the Modifier on-ramp. The `length` variable is declared but not yet used programmatically (it's used by the human who wrote 5 lines). The repetition is visible and deliberate: the kid sees five nearly identical lines and the `+ 1`, `+ 2` pattern. This is kishōtenketsu setup — the twist comes when the challenge engine introduces loops.

**The code agent could also generate:**

```python
from golem import *

pos = get_position()
build_wall(pos.x + 1, pos.y, pos.z, "east", 5, 1, "cobblestone")
```

The choice between explicit repetition and the compound function depends on the pedagogical context. If the challenge engine wants to set up a loop introduction, it instructs the code agent to use explicit placement. If the kid just wants a wall built quickly, it uses `build_wall`. The challenge agent controls this via a flag in its output to the code agent: `"code_style": "explicit_repetition"` vs `"code_style": "compound"`.

### Pattern 3: Observation and Action

Kid says: "What blocks are near me?"

```python
from golem import *

pos = get_position()
ground = get_block(pos.x, pos.y - 1, pos.z)
front = get_block(pos.x + 1, pos.y, pos.z)
above = get_block(pos.x, pos.y + 2, pos.z)

say("You're standing on " + ground)
say("In front of you: " + front)
say("Above you: " + above)
```

**Pedagogical notes:** Variables have descriptive names (`ground`, `front`, `above`) that map to spatial concepts the kid already understands. String concatenation with `+` is the simplest string operation and reads naturally.

### Pattern 4: Multi-Step Task

Kid says: "Get me 10 oak logs and then build a small floor"

```python
from golem import *

# Step 1: Collect the logs
collected = collect("oak_log", 10)
say("Got " + str(collected) + " oak logs!")

# Step 2: Build a 3x3 oak plank floor
craft("oak_planks", 10)
pos = get_player_position("Alex")

x = pos.x + 1
y = pos.y - 1
z = pos.z + 1

place_block(x, y, z, "oak_planks")
place_block(x + 1, y, z, "oak_planks")
place_block(x + 2, y, z, "oak_planks")
place_block(x, y, z + 1, "oak_planks")
place_block(x + 1, y, z + 1, "oak_planks")
place_block(x + 2, y, z + 1, "oak_planks")
place_block(x, y, z + 2, "oak_planks")
place_block(x + 1, y, z + 2, "oak_planks")
place_block(x + 2, y, z + 2, "oak_planks")
```

**Pedagogical notes:** Comments act as section headers — the code reads as a plan. The `collect` → `craft` → `place` sequence mirrors the kid's own gameplay loop. The 3x3 grid of place calls shows a 2D pattern that foreshadows nested loops (Level 3). The `x + 1`, `z + 1` variations make the coordinate system tangible.

---

## Concrete Challenge Scenario: Full Chain Walkthrough

### Context

The kid (Alex, age 10) has been playing with the golem for about 20 minutes. They've given several "come here" and "dig this" commands. The learner model shows: `variables=exposed` (they've seen variables in generated code but never modified one), `function_calls=exposed`. The kid is now building a house manually and has finished the walls. They're starting on a floor.

### The Kishōtenketsu Beats

**Ki (Introduction):** The kid is placing floor blocks one by one. It's tedious. They say in chat:

> "Hey golem, can you help me fill in this floor? It's 5 by 5, use oak planks"

**Shō (Development):** The code agent generates:

```python
from golem import *

pos = get_player_position("Alex")
block = "oak_planks"

# Floor starting corner (offset from player)
x = pos.x - 2
y = pos.y - 1
z = pos.z - 2

# Row 1
place_block(x, y, z, block)
place_block(x + 1, y, z, block)
place_block(x + 2, y, z, block)
place_block(x + 3, y, z, block)
place_block(x + 4, y, z, block)

# Row 2
place_block(x, y, z + 1, block)
place_block(x + 1, y, z + 1, block)
place_block(x + 2, y, z + 1, block)
place_block(x + 3, y, z + 1, block)
place_block(x + 4, y, z + 1, block)

# Row 3
place_block(x, y, z + 2, block)
place_block(x + 1, y, z + 2, block)
place_block(x + 2, y, z + 2, block)
place_block(x + 3, y, z + 2, block)
place_block(x + 4, y, z + 2, block)

# Row 4
place_block(x, y, z + 3, block)
place_block(x + 1, y, z + 3, block)
place_block(x + 2, y, z + 3, block)
place_block(x + 3, y, z + 3, block)
place_block(x + 4, y, z + 3, block)

# Row 5
place_block(x, y, z + 4, block)
place_block(x + 1, y, z + 4, block)
place_block(x + 2, y, z + 4, block)
place_block(x + 3, y, z + 4, block)
place_block(x + 4, y, z + 4, block)
```

The code executes. Oak planks fill in the floor. The code panel shows 25 nearly identical lines with a visible pattern: `+ 0`, `+ 1`, `+ 2`, `+ 3`, `+ 4` repeating in both directions.

The bot says in chat: "Done! That was a LOT of typing though — basically the same line 25 times. I wonder if there's a shorter way..."

The kid sees the floor appear. The build works. The bot doesn't push further.

**Ten (Twist):** The kid decides they want the floor to be birch planks instead of oak. They look at the code. They see `block = "oak_planks"` at the top. The Modifier instinct activates: "What if I change that?"

The kid changes `"oak_planks"` to `"birch_planks"` in the code panel and hits re-run. The floor rebuilds in birch.

The bot notices the modification. Chat: "Oh nice, you changed the block type! That one variable controls all 25 blocks — that's the power of a variable."

The learner model updates: `variables: exposed → modified`.

**Ketsu (Resolution):** The kid now understands that the variable at the top is a lever that controls the whole build. They experiment: change `"birch_planks"` to `"glass"`. Transparent floor. Change the `x` and `z` values. Floor moves. Each change is a 2-second experiment with immediate spatial feedback.

The bot doesn't quiz. It occasionally narrates: "Glass floor — now you can see the cave underneath!"

### What the Challenge Engine Actually Did

The challenge agent observed: kid is placing floor blocks manually (repetitive spatial task). It checked the learner model: variables are exposed but not yet modified. It generated the challenge situation:

```json
{
  "target_concept": "variables",
  "target_stage": "modified",
  "code_style": "explicit_repetition",
  "setup": "Generate floor code with a clearly named variable at the top (block = 'oak_planks'). Use explicit place_block calls (not build_wall compound) so the variable appears many times.",
  "bot_nudge": "Comment on the repetition after execution. Do NOT suggest the kid modify the variable — wait for them to discover it. If they don't engage within this session, that's fine.",
  "success_signal": "Kid modifies the block variable in the code panel",
  "fallback": "If kid asks 'can you make it birch instead', the bot should say 'sure — or you could change that one word at the top of the code, the one that says oak_planks' with a light tone"
}
```

### What Didn't Happen

The bot didn't say "Let's learn about variables." It didn't quiz. It didn't refuse to build the floor until the kid wrote code. It built the floor, mentioned the repetition casually, and waited. The learning happened because the kid wanted birch, saw the lever, and pulled it.

---

## Level 2 Preview: What Changes

Level 2 adds `For` loops and `Range` to the concept allowlist. The AST validator now accepts `ast.For` nodes. The code agent can generate:

```python
from golem import *

pos = get_position()
block = "cobblestone"
length = 10

for i in range(length):
    place_block(pos.x + i, pos.y, pos.z, block)
```

The compound functions (`build_line`, `build_wall`) are still available but the code agent now has the option to generate the loop version when the challenge engine says `"code_style": "explicit_loop"`. The challenge engine uses this when the kid has mastered variables and the next concept target is loops.

The critical pedagogical moment: the kid who changed `block = "oak_planks"` to `"birch_planks"` at Level 1 now sees `length = 10` and knows what to do with it. The variable-modification skill transfers to the loop parameter. They change `10` to `20` and the wall doubles. Then they start wondering what `for i in range(length)` means — because they want to understand the mechanism, not because they were assigned to learn it.

Level 2 also adds:
- `If` / `Else` (conditionals)
- `Compare` operators (`==`, `!=`, `<`, `>`)
- `BoolOp` (`and`, `or`)

These unlock survival-track challenges: "Check if it's nighttime and build a shelter."

---

## Level 3 Preview: Functions as Recipes

Level 3 adds `FunctionDef` and `Return` to the allowlist. The kid can now save their own recipes:

```python
from golem import *

def build_tower(x, y, z, height, block):
    for i in range(height):
        place_block(x, y + i, z, block)

# Build three towers
build_tower(10, 64, 20, 8, "cobblestone")
build_tower(15, 64, 20, 12, "stone_bricks")
build_tower(20, 64, 20, 6, "oak_planks")
```

This is the "recipe" concept from ADR-001: same function, different materials, different results — exactly like crafting. The kid's function enters the skill library with `"author": "kid"`.

---

## SDK Implementation Notes

### Position and Item Types

```python
class Position:
    def __init__(self, x, y, z):
        self.x = round(x)
        self.y = round(y)
        self.z = round(z)

    def __repr__(self):
        return f"Position(x={self.x}, y={self.y}, z={self.z})"

class Item:
    def __init__(self, name, count):
        self.name = name
        self.count = count

    def __repr__(self):
        return f"{self.count}x {self.name}"
```

These are deliberately simple. No inheritance, no dunder methods beyond `__repr__`. The kid will eventually read these class definitions (Level 6+), and they should be immediately comprehensible when that happens.

### Error Handling Strategy

The SDK catches all exceptions internally and translates them to chat messages via the bot personality. The kid never sees a traceback at Level 1-2. At Level 3+, the system uses the progressive disclosure strategy from the learning science research:

1. **Level 1-2:** Bot absorbs errors, reports in chat. "I couldn't reach that block — something's in the way."
2. **Level 3:** Bot explains errors in kid-friendly language. "I got confused because `hight` isn't a word I know — did you mean `height`?"
3. **Level 4:** Bot shows simplified traceback. "Line 5 had a problem: `NameError: name 'hight' is not defined` — that means I don't have a variable called 'hight'."
4. **Level 5+:** Full Python traceback visible with bot commentary.

### Block Name Validation

The SDK maintains a set of valid Minecraft block/item names for the target version (1.20.4). When the kid writes `"stoone"`, the SDK uses fuzzy matching (Levenshtein distance) to suggest the closest valid name. This surfaces as a chat message, not a Python exception.

### Execution Model

Generated code runs top-to-bottom, synchronously from the kid's perspective. The SDK functions are `async` under the hood (because Mineflayer operations are async), but the execution engine wraps them in a synchronous runner. The kid writes:

```python
move_to(10, 64, 20)
place_block(10, 65, 20, "torch")
```

And the bot moves, then places. No `await`, no callbacks, no promises.

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
