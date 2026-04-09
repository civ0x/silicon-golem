# Silicon Golem

An AI companion for Minecraft that teaches kids Python through play.

A Mineflayer bot joins the kid's Minecraft world, takes natural language commands, generates visible Python code, and executes it in-world. The child transitions from directing the bot in English to reading, modifying, and eventually writing Python — because they want to, not because they're told to.

## How It Works

```
Kid: "build me a cobblestone wall"

  Golem generates:
    from golem import *
    pos = get_position()
    block = "cobblestone"
    build_wall(pos.x + 1, pos.y, pos.z, "east", 5, 3, block)

  Golem says: "Done! I used cobblestone — you can swap
  it to something else in my code if you want."

Kid changes "cobblestone" to "diamond_block" → hits RUN → wall changes.
```

The kid sees real Python, not a DSL. The code has obvious "knobs" — variable values the kid can change to see different results. Curiosity does the teaching.

## Architecture

```
Minecraft (Java Edition 1.20.4, LAN)
    ↕ Minecraft protocol
Mineflayer Bridge (Node.js) — bot presence, world actions
    ↕ WebSocket
Python Orchestrator — agent routing, code execution, learner model
    ↕ Claude API
AI Agents — chat (Haiku), code (Sonnet), challenge (Opus)
```

**Code Panel** — a browser-based UI that shows the bot's generated Python with syntax highlighting. The kid can read, edit, and re-run code.

## Quick Start

### Prerequisites

- **Minecraft Java Edition 1.20.4** (other versions not supported)
- **Node.js 18+**
- **Python 3.11+**
- **Anthropic API key** ([console.anthropic.com](https://console.anthropic.com))

### Setup

```bash
git clone https://github.com/civ0x/silicon-golem.git
cd silicon-golem

# Install Python dependencies
pip install anthropic websockets

# Install bridge dependencies
cd bridge && npm install && cd ..

# Add your API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

### Running

1. Open Minecraft 1.20.4, load a world, press Esc → **Open to LAN** → note the port
2. Run:

```bash
./start.sh <mc_port> <your_minecraft_username>
```

The bot joins your world, the code panel opens in your browser. Walk up to the bot and chat.

### Manual Startup

If you prefer separate terminals:

```bash
# Terminal 1: bridge
MC_PORT=<port> cd bridge && npm start

# Terminal 2: orchestrator
python -m golem --player <username> -v

# Terminal 3: code panel
open panel/index.html
```

## Design Principles

- **The kid is the boss.** The bot serves, never quizzes, never lectures.
- **Real Python, not a DSL.** `for i in range(10):` not `repeat(10)`. Transfer to real programming depends on identical syntax.
- **Minecraft concepts are prior knowledge.** The kid already understands variables (resource counts), loops (batch smelting), and conditionals (fight or flee). The system provides notation for concepts they already have.
- **No extrinsic rewards.** No points, badges, XP, or leaderboards. Minecraft play is the reward.
- **One concept at a time.** The learner model tracks mastery and gates what code constructs the bot can generate.
- **Errors are the bot's confusion.** "I got confused" not "SyntaxError on line 5."

## Project Structure

```
silicon-golem/
├── bridge/          # Mineflayer bot + WebSocket server (Node.js)
├── golem/           # Python orchestrator, SDK, validator, learner model
│   ├── sdk.py       # The Golem SDK — what the kid's code imports
│   ├── orchestrator.py  # Agent routing + code execution
│   ├── validator.py     # AST allowlist enforcement
│   ├── learner.py       # BKT learner model
│   └── skills.py        # Skill library (save/load/search)
├── panel/           # Code panel web UI (single HTML file)
├── prompts/         # AI agent system prompts
├── data/            # Block names, concept levels
├── start.sh         # One-command launcher
├── DECISIONS.md     # Architectural decisions (ADR-001 through ADR-008)
├── GOLEM_SDK.md     # SDK design + concept allowlists
└── CLAUDE.md        # Development guide
```

## The Learning Progression

The system tracks the kid through stages invisibly — no levels, no scores, no "great job":

| Stage | What the Kid Does | What They're Learning |
|---|---|---|
| **Director** | Tells the bot what to do in English | Reading code as a side effect |
| **Modifier** | Changes a value in the code and re-runs | Variables control behavior |
| **Experimenter** | Tries changes to see what happens | Cause and effect in code |
| **Debugger** | Fixes broken code | Reading error messages |
| **Author** | Writes new code from scratch | Programming |

The transition from Director to Modifier is the critical moment. The bot's "curiosity bridge" — casually mentioning changeable values — is designed to spark that transition.

## Target Audience

Designed for a 7-year-old Minecraft player. No prior coding experience assumed. The system meets the kid where they are: if they can play Minecraft and type in chat, they can use Silicon Golem.

## Running Tests

```bash
# All Python tests (~334 tests)
python -m pytest golem/test/ -v --ignore=golem/test/test_integration.py

# Bridge tests (requires running MC server)
cd bridge && npm test

# Integration tests (requires MC server + bridge)
INTEGRATION_PLAYER=<name> python -m pytest golem/test/test_integration.py -v
```

## Status

System is built and smoke-tested. All components wired and working end-to-end. Next milestone is playtesting with the target audience.

See [STATUS.md](STATUS.md) for detailed project state.

## License

This project is not yet licensed. All rights reserved.
