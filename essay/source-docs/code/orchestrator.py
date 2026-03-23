"""Silicon Golem Orchestrator — central coordinator.

Routes messages between agents, manages the challenge state machine,
assembles world context, and coordinates code execution. Does NOT
generate code, talk to the kid, or design challenges.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic

from .connection import get_connection
from .learner import LearnerModel, LearnerEvent
from .validator import validate, LEVEL_CONFIGS
from . import sdk

logger = logging.getLogger(__name__)

# ── Model IDs ────────────────────────────────────────────────────────────────

CHAT_MODEL = "claude-haiku-4-5-20251001"
CODE_MODEL = "claude-sonnet-4-6"
CHALLENGE_MODEL = "claude-opus-4-6"

# ── Timing Constants ─────────────────────────────────────────────────────────

CHALLENGE_CHECK_INTERVAL = 60  # seconds between challenge agent polls
MIN_SESSION_MINUTES_FOR_CHALLENGE = 10
LAST_MINUTES_NO_CHALLENGE = 5
MIN_MINUTES_BETWEEN_CHALLENGES = 15
MAX_CODE_RETRIES = 2
ACTIVITY_WINDOW = 30  # seconds of events for activity detection


# ── Data Types ───────────────────────────────────────────────────────────────

@dataclass
class WorldContext:
    """Assembled world state for agent consumption."""
    player_name: str
    player_position: dict[str, int]
    player_activity: str
    bot_position: dict[str, int]
    bot_inventory: list[dict[str, Any]]
    time_of_day: str
    game_mode: str
    session_duration_minutes: int
    nearby_entities: list[dict[str, Any]] = field(default_factory=list)
    nearby_blocks: dict[str, int] = field(default_factory=dict)
    recent_actions: list[str] = field(default_factory=list)

    def to_chat_dict(self) -> dict[str, Any]:
        return {
            "player_name": self.player_name,
            "player_position": self.player_position,
            "player_activity": self.player_activity,
            "bot_position": self.bot_position,
            "bot_inventory": self.bot_inventory,
            "time_of_day": self.time_of_day,
            "game_mode": self.game_mode,
            "session_duration_minutes": self.session_duration_minutes,
        }

    def to_challenge_dict(self) -> dict[str, Any]:
        return {
            "player_activity": self.player_activity,
            "player_position": self.player_position,
            "recent_actions": self.recent_actions,
            "time_of_day": self.time_of_day,
            "game_mode": self.game_mode,
            "nearby_entities": self.nearby_entities,
            "session_duration_minutes": self.session_duration_minutes,
        }

    def to_code_dict(self) -> dict[str, Any]:
        return {
            "bot_position": self.bot_position,
            "bot_inventory": self.bot_inventory,
            "nearby_blocks": self.nearby_blocks,
            "time_of_day": self.time_of_day,
            "game_mode": self.game_mode,
        }


@dataclass
class ChallengeSituation:
    """Active challenge held as a state machine."""
    challenge_id: str
    target_concept: str
    target_stage: str
    code_style: str
    beats: dict[str, dict[str, Any]]
    abort_conditions: list[str]
    current_beat: str = "ki"
    started_at: float = field(default_factory=time.monotonic)


@dataclass
class CodeResult:
    """Result of the code execution pipeline."""
    status: str  # "success", "partial", "error", "infeasible"
    code_shown: str
    blocks_placed: int = 0
    blocks_broken: int = 0
    items_crafted: int = 0
    error_details: dict[str, Any] | None = None
    execution_time_seconds: float = 0.0
    infeasible_details: dict[str, Any] | None = None


# ── Orchestrator ─────────────────────────────────────────────────────────────

class Orchestrator:
    """Central coordinator for Silicon Golem."""

    def __init__(
        self,
        player_name: str,
        bridge_host: str = "localhost",
        bridge_port: int = 3001,
        prompt_dir: str = "prompts",
        learner_state_path: str = "data/learner_state.json",
        anthropic_client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._player_name = player_name
        self._bridge_host = bridge_host
        self._bridge_port = bridge_port
        self._prompt_dir = Path(prompt_dir)

        self._learner = LearnerModel(player_name, learner_state_path)
        self._client = anthropic_client or anthropic.AsyncAnthropic()

        # Load system prompts
        self._chat_prompt = self._load_prompt("chat_agent.md")
        self._code_prompt = self._load_prompt("code_agent.md")
        self._challenge_prompt = self._load_prompt("challenge_agent.md")

        # Challenge state
        self._active_challenge: ChallengeSituation | None = None

        # Session state
        self._session_start: float | None = None
        self._challenges_this_session = 0
        self._last_challenge_time: float | None = None
        self._game_mode = "survival"
        self._disengagement_count = 0

        # Event tracking
        self._recent_events: list[dict[str, Any]] = []
        self._event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None

        # Running state
        self._running = False
        self._challenge_task: asyncio.Task[None] | None = None

    def _load_prompt(self, filename: str) -> str:
        path = self._prompt_dir / filename
        if path.exists():
            return path.read_text()
        return ""

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Connect to bridge and start the orchestrator loop."""
        self._loop = asyncio.get_running_loop()
        conn = get_connection()
        await asyncio.to_thread(conn.connect, self._bridge_host, self._bridge_port)
        conn.set_event_callback(self._on_bridge_event)
        await asyncio.to_thread(
            conn.send_command, "configure", {"track_player": self._player_name}
        )
        self._session_start = time.monotonic()
        self._running = True
        self._challenge_task = asyncio.create_task(self._challenge_loop())
        await self._event_loop()

    async def stop(self) -> None:
        """Stop the orchestrator and disconnect."""
        self._running = False
        if self._challenge_task:
            self._challenge_task.cancel()
        self._learner.save()
        conn = get_connection()
        try:
            await asyncio.to_thread(
                conn.send_command, "disconnect", {"reason": "session_end"}
            )
        except Exception:
            pass
        await asyncio.to_thread(conn.disconnect)

    def _on_bridge_event(self, msg: dict[str, Any]) -> None:
        """Callback from BridgeConnection — runs on the bridge thread."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._event_queue.put_nowait, msg)

    # ── Event Loop ───────────────────────────────────────────────────────────

    async def _event_loop(self) -> None:
        while self._running:
            try:
                msg = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            event_name = msg.get("event")
            data = msg.get("data", {})

            # Track for activity detection
            self._recent_events.append({
                "event": event_name,
                "data": data,
                "time": time.monotonic(),
            })
            cutoff = time.monotonic() - ACTIVITY_WINDOW
            self._recent_events = [e for e in self._recent_events if e["time"] > cutoff]

            if event_name == "player_chat":
                if data.get("name") == self._player_name:
                    await self.handle_player_chat(data.get("message", ""))
            elif event_name == "game_mode_changed":
                if data.get("player") == self._player_name:
                    self._game_mode = data.get("mode", "survival")
            elif event_name == "code_panel_run":
                await self._handle_code_run(data)

            if self._active_challenge:
                await self._evaluate_challenge_triggers(event_name, data)

    # ── Message Routing ──────────────────────────────────────────────────────

    async def handle_player_chat(self, message: str) -> None:
        """Main entry point — kid's chat message arrives here."""
        world_ctx = await self._assemble_world_context()
        learner_state = self._learner.get_agent_state()
        directive = self._get_active_directive()

        chat_response = await self._call_chat_agent(
            message=message,
            world_context=world_ctx,
            learner_state=learner_state,
            directive=directive,
        )

        for chat_msg in chat_response.get("chat_messages", []):
            await self._bridge_say(chat_msg)

        for event_data in chat_response.get("learner_events", []):
            self._process_learner_event(event_data, world_ctx)

        task = chat_response.get("task_description")
        if task:
            await self._handle_code_task(task, world_ctx, learner_state)

    # ── Code Execution Pipeline ──────────────────────────────────────────────

    async def _handle_code_task(
        self,
        task: dict[str, Any],
        world_ctx: WorldContext,
        learner_state: dict[str, Any],
    ) -> None:
        """Route task through code agent → validate → execute → narrate."""
        level = learner_state["current_level"]

        code_style = "compound"
        if self._active_challenge:
            code_style = self._active_challenge.code_style

        level_config = LEVEL_CONFIGS.get(level, LEVEL_CONFIGS[1])
        constraints = {
            "level": level,
            "permitted_ast_nodes": sorted(level_config["permitted_nodes"]),
            "permitted_sdk_functions": sorted(level_config["permitted_sdk_functions"]),
            "permitted_builtins": sorted(level_config["permitted_builtins"]),
            "max_lines": level_config["max_lines"],
            "max_nesting_depth": level_config["max_nesting_depth"],
        }

        code = ""
        validation_errors: list[dict[str, Any]] | None = None

        for attempt in range(MAX_CODE_RETRIES + 1):
            code_response = await self._call_code_agent(
                task=task,
                code_style=code_style,
                constraints=constraints,
                world_context=world_ctx,
                retry_errors=validation_errors,
            )

            if isinstance(code_response, dict) and code_response.get("status") == "infeasible":
                result = CodeResult(
                    status="infeasible",
                    code_shown="",
                    infeasible_details=code_response,
                )
                await self._narrate_result(result, world_ctx)
                return

            code = code_response if isinstance(code_response, str) else ""

            validation = validate(code, level)
            if validation.valid:
                validation_errors = None
                break

            validation_errors = [
                {"line": e.line, "construct": e.construct, "message": e.message}
                for e in validation.errors
            ]
            logger.info(
                "Code validation failed (attempt %d): %s", attempt + 1, validation_errors
            )

        if validation_errors:
            result = CodeResult(
                status="infeasible",
                code_shown=code,
                infeasible_details={
                    "reason": "Code could not pass validation after retries",
                    "simpler_alternative": (
                        "I got confused trying to figure that out. "
                        "Maybe try asking in a simpler way?"
                    ),
                },
            )
            await self._narrate_result(result, world_ctx)
            return

        result = await self._execute_code(code)

        if result.status in ("success", "partial"):
            self._learner.process_code_displayed(code)
            self._learner.save()

        await self._narrate_result(result, world_ctx)

        # Fire execution_complete for challenge trigger evaluation
        if self._active_challenge:
            await self._evaluate_challenge_triggers("_execution_complete", {})

    async def _execute_code(self, code: str) -> CodeResult:
        """Execute validated code in a sandboxed namespace."""
        clean_code, namespace = self._prepare_code_for_exec(code)

        start_time = time.monotonic()
        try:
            await asyncio.to_thread(exec, clean_code, namespace)
            elapsed = time.monotonic() - start_time
            return CodeResult(
                status="success",
                code_shown=code,
                execution_time_seconds=elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - start_time
            return CodeResult(
                status="error",
                code_shown=code,
                execution_time_seconds=elapsed,
                error_details={
                    "type": type(e).__name__,
                    "message": str(e),
                },
            )

    def _prepare_code_for_exec(self, code: str) -> tuple[str, dict[str, Any]]:
        """Strip golem import and build a controlled execution namespace.

        Per CLAUDE.md: use exec() with a controlled namespace containing
        only the SDK functions. The AST validator already restricts imports.
        """
        lines = code.split("\n")
        filtered = [ln for ln in lines if ln.strip() != "from golem import *"]
        clean_code = "\n".join(filtered)

        ns: dict[str, Any] = {}
        for name in sdk.__all__:
            ns[name] = getattr(sdk, name)
        ns["__builtins__"] = {
            "print": print,
            "int": int,
            "str": str,
            "len": len,
            "range": range,
            "bool": bool,
            "True": True,
            "False": False,
            "None": None,
        }
        return clean_code, ns

    async def _narrate_result(
        self, result: CodeResult, world_ctx: WorldContext
    ) -> None:
        """Call chat agent to narrate execution results."""
        learner_state = self._learner.get_agent_state()
        directive = self._get_active_directive()

        chat_response = await self._call_chat_agent(
            message=None,
            world_context=world_ctx,
            learner_state=learner_state,
            directive=directive,
            code_result=result,
        )

        for chat_msg in chat_response.get("chat_messages", []):
            await self._bridge_say(chat_msg)

        for event_data in chat_response.get("learner_events", []):
            self._process_learner_event(event_data, world_ctx)

    # ── Code Panel Events ────────────────────────────────────────────────────

    async def _handle_code_run(self, data: dict[str, Any]) -> None:
        """Kid hit re-run in the code panel."""
        source = data.get("source", "")
        if not source:
            return

        level = self._learner.get_current_level()
        validation = validate(source, level)

        if validation.valid:
            result = await self._execute_code(source)
            if result.status == "success":
                self._learner.process_code_displayed(source)
                self._learner.save()
        else:
            result = CodeResult(
                status="error",
                code_shown=source,
                error_details={
                    "type": "ValidationError",
                    "message": "; ".join(e.message for e in validation.errors),
                },
            )

        world_ctx = await self._assemble_world_context()
        await self._narrate_result(result, world_ctx)

    # ── Agent Calls ──────────────────────────────────────────────────────────

    async def _call_chat_agent(
        self,
        message: str | None,
        world_context: WorldContext,
        learner_state: dict[str, Any],
        directive: dict[str, Any] | None = None,
        code_result: CodeResult | None = None,
    ) -> dict[str, Any]:
        user_content = self._build_chat_user_message(
            message, world_context, learner_state, directive, code_result
        )

        response = await self._client.messages.create(
            model=CHAT_MODEL,
            max_tokens=1024,
            system=self._chat_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return self._parse_chat_response(response.content[0].text)

    async def _call_code_agent(
        self,
        task: dict[str, Any],
        code_style: str,
        constraints: dict[str, Any],
        world_context: WorldContext,
        retry_errors: list[dict[str, Any]] | None = None,
    ) -> str | dict[str, Any]:
        user_content = self._build_code_user_message(
            task, code_style, constraints, world_context, retry_errors
        )

        response = await self._client.messages.create(
            model=CODE_MODEL,
            max_tokens=2048,
            system=self._code_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return self._parse_code_response(response.content[0].text)

    async def _call_challenge_agent(
        self, world_context: WorldContext
    ) -> dict[str, Any] | None:
        learner_state = self._learner.get_agent_state()
        concept_readiness = self._learner.get_concept_readiness()

        user_content = self._build_challenge_user_message(
            learner_state, world_context, concept_readiness
        )

        response = await self._client.messages.create(
            model=CHALLENGE_MODEL,
            max_tokens=4096,
            system=self._challenge_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return self._parse_challenge_response(response.content[0].text)

    # ── Message Builders ─────────────────────────────────────────────────────

    def _build_chat_user_message(
        self,
        message: str | None,
        world_context: WorldContext,
        learner_state: dict[str, Any],
        directive: dict[str, Any] | None,
        code_result: CodeResult | None,
    ) -> str:
        parts: list[str] = []

        if message:
            parts.append(f"## Kid's Chat Message\n{message}")

        parts.append(
            f"## World Context\n```json\n"
            f"{json.dumps(world_context.to_chat_dict(), indent=2)}\n```"
        )
        parts.append(
            f"## Learner Model State\n```json\n"
            f"{json.dumps(learner_state, indent=2)}\n```"
        )

        if directive:
            parts.append(
                f"## Challenge Directive\n```json\n"
                f"{json.dumps(directive, indent=2)}\n```"
            )

        if code_result:
            rd: dict[str, Any] = {
                "status": code_result.status,
                "code_shown": code_result.code_shown,
                "execution_time_seconds": code_result.execution_time_seconds,
            }
            if code_result.error_details:
                rd["error_details"] = code_result.error_details
            if code_result.infeasible_details:
                rd["infeasible_details"] = code_result.infeasible_details
            parts.append(
                f"## Code Execution Results\n```json\n"
                f"{json.dumps(rd, indent=2)}\n```"
            )

        parts.append(
            "## Response Format\n"
            "Respond with a JSON object containing:\n"
            '- "chat_messages": list of strings to send as in-game chat\n'
            '- "task_description": optional object with "intent", '
            '"player_name", "player_position", "direction_hint" '
            "if the kid requested an action\n"
            '- "learner_events": optional list of objects with '
            '"event", "concept", "detail", "context"'
        )
        return "\n\n".join(parts)

    def _build_code_user_message(
        self,
        task: dict[str, Any],
        code_style: str,
        constraints: dict[str, Any],
        world_context: WorldContext,
        retry_errors: list[dict[str, Any]] | None,
    ) -> str:
        parts: list[str] = []
        task_with_style = {**task, "code_style": code_style}
        parts.append(
            f"## Task\n```json\n{json.dumps(task_with_style, indent=2)}\n```"
        )
        parts.append(
            f"## Concept Level and Constraints\n```json\n"
            f"{json.dumps(constraints, indent=2)}\n```"
        )
        parts.append(
            f"## World State\n```json\n"
            f"{json.dumps(world_context.to_code_dict(), indent=2)}\n```"
        )
        if retry_errors:
            parts.append(
                "## Previous Attempt Failed Validation\n"
                "Fix these errors:\n```json\n"
                f"{json.dumps(retry_errors, indent=2)}\n```"
            )
        return "\n\n".join(parts)

    def _build_challenge_user_message(
        self,
        learner_state: dict[str, Any],
        world_context: WorldContext,
        concept_readiness: dict[str, Any],
    ) -> str:
        parts: list[str] = []
        parts.append(
            f"## Learner Model State\n```json\n"
            f"{json.dumps(learner_state, indent=2)}\n```"
        )
        ctx = world_context.to_challenge_dict()
        ctx["challenges_this_session"] = self._challenges_this_session
        ctx["last_challenge_minutes_ago"] = (
            round((time.monotonic() - self._last_challenge_time) / 60, 1)
            if self._last_challenge_time
            else None
        )
        parts.append(
            f"## World Context\n```json\n{json.dumps(ctx, indent=2)}\n```"
        )
        parts.append(
            f"## Concept Readiness\n```json\n"
            f"{json.dumps(concept_readiness, indent=2)}\n```"
        )
        parts.append(
            "Respond with a challenge situation JSON object, "
            "or respond with just the word 'none' if no challenge "
            "is appropriate right now."
        )
        return "\n\n".join(parts)

    # ── Response Parsers ─────────────────────────────────────────────────────

    def _parse_chat_response(self, text: str) -> dict[str, Any]:
        """Parse chat agent output into structured data."""
        try:
            extracted = self._extract_json(text)
            if extracted is not None:
                return extracted
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return {"chat_messages": [text.strip()]}

    def _parse_code_response(self, text: str) -> str | dict[str, Any]:
        """Parse code agent output — Python code or infeasible JSON."""
        stripped = text.strip()

        if '"status": "infeasible"' in stripped or '"status":"infeasible"' in stripped:
            try:
                extracted = self._extract_json(stripped)
                if extracted is not None:
                    return extracted
                return json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                pass

        # Extract code from markdown fences
        if "```python" in stripped:
            code_start = stripped.index("```python") + 9
            code_end = stripped.index("```", code_start)
            return stripped[code_start:code_end].strip()
        if "```" in stripped:
            code_start = stripped.index("```") + 3
            code_end = stripped.index("```", code_start)
            return stripped[code_start:code_end].strip()

        return stripped

    def _parse_challenge_response(self, text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        if stripped.lower() in ("none", '"none"'):
            return None
        try:
            extracted = self._extract_json(stripped)
            if extracted is not None:
                return extracted
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Could not parse challenge agent response")
            return None

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Try to extract a JSON object from markdown fences."""
        for marker in ("```json", "```"):
            if marker in text:
                start = text.index(marker) + len(marker)
                try:
                    end = text.index("```", start)
                except ValueError:
                    continue
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    continue
        return None

    # ── World Context Assembly ───────────────────────────────────────────────

    async def _assemble_world_context(self) -> WorldContext:
        conn = get_connection()
        try:
            world_state = await asyncio.to_thread(
                conn.send_command, "get_world_state", {}
            )
        except Exception as e:
            logger.warning("Failed to get world state: %s", e)
            world_state = {}

        bot = world_state.get("bot", {})
        players = world_state.get("players", [])

        player_pos = {"x": 0, "y": 64, "z": 0}
        for p in players:
            if p.get("name") == self._player_name:
                player_pos = p.get("position", player_pos)
                break

        session_minutes = 0
        if self._session_start:
            session_minutes = int((time.monotonic() - self._session_start) / 60)

        return WorldContext(
            player_name=self._player_name,
            player_position=player_pos,
            player_activity=self._detect_player_activity(),
            bot_position=bot.get("position", {"x": 0, "y": 64, "z": 0}),
            bot_inventory=bot.get("inventory", []),
            time_of_day=world_state.get("time", {}).get("time_of_day", "noon"),
            game_mode=world_state.get("game_mode", self._game_mode),
            session_duration_minutes=session_minutes,
            nearby_entities=world_state.get("nearby_entities", []),
            nearby_blocks=world_state.get("nearby_blocks", {}),
            recent_actions=self._summarize_recent_actions(),
        )

    def _detect_player_activity(self) -> str:
        if not self._recent_events:
            return "idle"

        placed = sum(1 for e in self._recent_events if e["event"] == "block_placed")
        broken = sum(1 for e in self._recent_events if e["event"] == "block_broken")

        if placed >= 3 and placed > broken:
            return "building"
        if broken >= 3 and broken > placed:
            return "mining"
        if placed > 0:
            return "building"
        if broken > 0:
            return "mining"
        return "idle"

    def _summarize_recent_actions(self) -> list[str]:
        block_places: dict[str, int] = {}
        block_breaks: dict[str, int] = {}

        for e in self._recent_events:
            bt = e["data"].get("block_type", "unknown")
            if e["event"] == "block_placed":
                block_places[bt] = block_places.get(bt, 0) + 1
            elif e["event"] == "block_broken":
                block_breaks[bt] = block_breaks.get(bt, 0) + 1

        summaries: list[str] = []
        for bt, count in block_places.items():
            summaries.append(f"placed {count} {bt} blocks")
        for bt, count in block_breaks.items():
            summaries.append(f"broke {count} {bt} blocks")
        return summaries

    # ── Challenge State Machine ──────────────────────────────────────────────

    async def _challenge_loop(self) -> None:
        """Periodically check whether to generate a new challenge."""
        while self._running:
            await asyncio.sleep(CHALLENGE_CHECK_INTERVAL)
            if not self._should_generate_challenge():
                continue
            try:
                world_ctx = await self._assemble_world_context()
                challenge_data = await self._call_challenge_agent(world_ctx)
                if challenge_data:
                    self._activate_challenge(challenge_data)
            except Exception as e:
                logger.warning("Challenge agent error: %s", e)

    def _should_generate_challenge(self) -> bool:
        if self._active_challenge:
            return False
        if self._disengagement_count >= 2:
            return False
        if not self._session_start:
            return False

        session_minutes = (time.monotonic() - self._session_start) / 60

        if session_minutes < MIN_SESSION_MINUTES_FOR_CHALLENGE:
            return False

        if self._last_challenge_time:
            since = (time.monotonic() - self._last_challenge_time) / 60
            if since < MIN_MINUTES_BETWEEN_CHALLENGES:
                return False

        return True

    def _activate_challenge(self, data: dict[str, Any]) -> None:
        challenge_id = data.get("challenge_id", str(uuid.uuid4()))
        self._active_challenge = ChallengeSituation(
            challenge_id=challenge_id,
            target_concept=data.get("target_concept", ""),
            target_stage=data.get("target_stage", ""),
            code_style=data.get("setup", {}).get("code_style", "compound"),
            beats=data.get("beats", {}),
            abort_conditions=data.get("abort_conditions", []),
        )
        self._challenges_this_session += 1
        self._last_challenge_time = time.monotonic()
        logger.info("Challenge activated: %s", challenge_id)

    def _get_active_directive(self) -> dict[str, Any] | None:
        if not self._active_challenge:
            return None
        beat_data = self._active_challenge.beats.get(
            self._active_challenge.current_beat
        )
        if not beat_data:
            return None
        return {
            "challenge_id": self._active_challenge.challenge_id,
            "active_beat": self._active_challenge.current_beat,
            "bot_behavior": beat_data.get("bot_behavior", ""),
            "constraints": beat_data.get("constraints", []),
        }

    async def _evaluate_challenge_triggers(
        self, event_name: str, event_data: dict[str, Any]
    ) -> None:
        if not self._active_challenge:
            return

        if self._should_abort_challenge(event_name, event_data):
            self._retire_challenge()
            return

        beat_order = ["ki", "sho", "ten", "ketsu"]
        current = self._active_challenge.current_beat
        if current not in beat_order:
            return

        current_idx = beat_order.index(current)
        if current_idx >= len(beat_order) - 1:
            # Already at ketsu — no more beats to advance
            return

        next_beat = beat_order[current_idx + 1]
        next_data = self._active_challenge.beats.get(next_beat, {})
        trigger = next_data.get("trigger", "")

        if self._trigger_matches(trigger, event_name, event_data):
            self._active_challenge.current_beat = next_beat
            logger.info("Challenge beat advanced to: %s", next_beat)

    def _should_abort_challenge(
        self, event_name: str, event_data: dict[str, Any]
    ) -> bool:
        if event_name == "player_joined":
            return True
        if event_name == "entity_nearby" and event_data.get("hostile"):
            return True
        if event_name == "player_left" and event_data.get("name") == self._player_name:
            return True
        return False

    def _trigger_matches(
        self, trigger: str, event_name: str, event_data: dict[str, Any]
    ) -> bool:
        """Match a natural-language trigger against an event."""
        tl = trigger.lower()

        # Affirmative chat responses
        if event_name == "player_chat" and any(
            kw in tl for kw in ("accepts", "says yes", "affirmative")
        ):
            msg = event_data.get("message", "").lower()
            affirm = {"yes", "yeah", "yep", "sure", "ok", "okay", "yea", "y"}
            if any(w in msg.split() for w in affirm):
                return True

        # After execution completes
        if "execution completes" in tl or "after execution" in tl:
            return event_name == "_execution_complete"

        # Code modification / engagement
        if event_name == "code_panel_edit" and any(
            kw in tl for kw in ("modif", "engages", "edit")
        ):
            return True
        if event_name == "code_panel_scroll" and "scroll" in tl:
            return True

        # Kid asks about code
        if event_name == "player_chat" and any(
            kw in tl for kw in ("asks", "mentions", "comments", "engages")
        ):
            msg = event_data.get("message", "").lower()
            code_words = {
                "code", "line", "repeat", "same", "shorter",
                "why", "how", "what", "loop", "pattern",
            }
            if any(w in msg.split() for w in code_words):
                return True

        return False

    def _retire_challenge(self) -> None:
        if self._active_challenge:
            logger.info("Challenge retired: %s", self._active_challenge.challenge_id)
        self._active_challenge = None

    # ── Learner Model ────────────────────────────────────────────────────────

    def _process_learner_event(
        self, event_data: dict[str, Any], world_ctx: WorldContext
    ) -> None:
        event = LearnerEvent(
            event=event_data.get("event", ""),
            concept=event_data.get("concept"),
            detail=event_data.get("detail", ""),
            context=event_data.get("context", world_ctx.player_activity),
            success=event_data.get("success"),
            timestamp=datetime.now(timezone.utc),
        )

        if event.event == "disengaged":
            self._disengagement_count += 1

        change = self._learner.process_event(event)
        if change:
            logger.info(
                "Learner state change: %s %s -> %s (p_mastery: %.3f -> %.3f)",
                change.concept, change.old_stage, change.new_stage,
                change.old_p_mastery, change.new_p_mastery,
            )
        self._learner.save()

    # ── Bridge Helpers ───────────────────────────────────────────────────────

    async def _bridge_say(self, message: str) -> None:
        conn = get_connection()
        try:
            await asyncio.to_thread(conn.send_command, "say", {"message": message})
        except Exception as e:
            logger.warning("Failed to send chat: %s", e)
