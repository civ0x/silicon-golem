"""Tests for the Silicon Golem orchestrator.

Mocks Claude API calls and bridge connection. Tests message routing,
challenge state machine, world context assembly, learner model integration,
code validation retry loop, level gating, and session timing.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from golem.orchestrator import (
    CHALLENGE_CHECK_INTERVAL,
    CHAT_MODEL,
    CODE_MODEL,
    CHALLENGE_MODEL,
    MAX_CODE_RETRIES,
    MIN_MINUTES_BETWEEN_CHALLENGES,
    MIN_SESSION_MINUTES_FOR_CHALLENGE,
    ChallengeSituation,
    CodeResult,
    Orchestrator,
    WorldContext,
)
from golem.learner import LearnerModel, LearnerEvent
from golem.validator import LEVEL_CONFIGS


# ── Fixtures ─────────────────────────────────────────────────────────────────


@dataclass
class MockMessage:
    """Mimics an anthropic response message."""
    text: str


@dataclass
class MockResponse:
    """Mimics anthropic.types.Message."""
    content: list[MockMessage]


def make_chat_response(
    chat_messages: list[str],
    task_description: dict | None = None,
    learner_events: list[dict] | None = None,
) -> MockResponse:
    """Build a mock chat agent response."""
    data: dict[str, Any] = {"chat_messages": chat_messages}
    if task_description:
        data["task_description"] = task_description
    if learner_events:
        data["learner_events"] = learner_events
    return MockResponse(content=[MockMessage(text=json.dumps(data))])


def make_code_response(code: str) -> MockResponse:
    """Build a mock code agent response with Python code."""
    return MockResponse(content=[MockMessage(text=f"```python\n{code}\n```")])


def make_infeasible_response() -> MockResponse:
    """Build a mock infeasible code agent response."""
    data = {
        "status": "infeasible",
        "reason": "Task requires loops",
        "simpler_alternative": "I can try something simpler.",
    }
    return MockResponse(content=[MockMessage(text=json.dumps(data))])


def make_challenge_response(challenge: dict) -> MockResponse:
    return MockResponse(content=[MockMessage(text=json.dumps(challenge))])


def make_no_challenge_response() -> MockResponse:
    return MockResponse(content=[MockMessage(text="none")])


VALID_LEVEL1_CODE = '''from golem import *

pos = get_position()
block = "cobblestone"
place_block(pos.x + 1, pos.y, pos.z, block)
'''

# Code that executes without needing a live bridge connection.
# Used in tests where we need successful execution + concept detection.
VALID_LEVEL1_CODE_PURE = '''from golem import *

block = "cobblestone"
height = 5
x = 10
y = 64
z = 20
'''

INVALID_LEVEL1_CODE = '''from golem import *

for i in range(5):
    place_block(i, 64, 0, "cobblestone")
'''

SAMPLE_WORLD_STATE = {
    "bot": {
        "position": {"x": 100, "y": 64, "z": -200},
        "health": 20,
        "food": 20,
        "inventory": [{"name": "cobblestone", "count": 64}],
    },
    "players": [
        {"name": "Alex", "position": {"x": 105, "y": 64, "z": -195}, "distance": 7.0}
    ],
    "time": {"time_of_day": "noon", "ticks": 6000},
    "game_mode": "survival",
    "nearby_blocks": {"cobblestone": 12, "dirt": 45},
    "nearby_entities": [],
}

SAMPLE_CHALLENGE = {
    "challenge_id": "test-challenge-1",
    "target_concept": "for_loops",
    "target_stage": "exposed",
    "setup": {"code_style": "explicit_repetition"},
    "beats": {
        "ki": {
            "trigger": "Bot offers help",
            "bot_behavior": "Offer to help extend the wall.",
        },
        "sho": {
            "trigger": "Kid accepts help (says yes, or affirmative)",
            "bot_behavior": "Execute the repetitive code.",
        },
        "ten": {
            "trigger": "After execution completes",
            "bot_behavior": "Comment on repetition.",
        },
        "ketsu": {
            "trigger": "Kid engages with the code or asks about the pattern",
            "bot_behavior": "Support exploration.",
        },
    },
    "abort_conditions": [
        "Kid starts different activity",
        "Hostile mob approaching",
    ],
}


@pytest.fixture
def tmp_prompts(tmp_path: Path) -> Path:
    """Create minimal prompt files."""
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "chat_agent.md").write_text("You are a test chat agent.")
    (prompt_dir / "code_agent.md").write_text("You are a test code agent.")
    (prompt_dir / "challenge_agent.md").write_text("You are a test challenge agent.")
    return prompt_dir


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    """Mock anthropic.AsyncAnthropic client."""
    client = AsyncMock()
    client.messages = AsyncMock()
    client.messages.create = AsyncMock()
    return client


@pytest.fixture
def mock_bridge_conn() -> MagicMock:
    """Mock BridgeConnection."""
    conn = MagicMock()
    conn.connect = MagicMock()
    conn.disconnect = MagicMock()
    conn.send_command = MagicMock(return_value=SAMPLE_WORLD_STATE)
    conn.set_event_callback = MagicMock()
    return conn


@pytest.fixture
def orchestrator(
    tmp_path: Path, tmp_prompts: Path, mock_anthropic_client: AsyncMock, mock_bridge_conn: MagicMock
) -> Orchestrator:
    """Create an orchestrator with mocked dependencies."""
    learner_path = str(tmp_path / "learner_state.json")
    with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
        orch = Orchestrator(
            player_name="Alex",
            prompt_dir=str(tmp_prompts),
            learner_state_path=learner_path,
            anthropic_client=mock_anthropic_client,
        )
    orch._session_start = time.monotonic()
    orch._loop = asyncio.get_event_loop()
    return orch


# ── Test: Message Routing ────────────────────────────────────────────────────


class TestMessageRouting:
    """Chat message → chat agent → code agent → execution → narration."""

    @pytest.mark.asyncio
    async def test_chat_only_no_task(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """When chat agent returns no task, only chat messages are sent."""
        mock_anthropic_client.messages.create.return_value = make_chat_response(
            chat_messages=["Hey there!"]
        )

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("hello")

        # Chat agent was called
        assert mock_anthropic_client.messages.create.call_count == 1
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == CHAT_MODEL

        # Say was called with the chat message
        say_calls = [
            c for c in mock_bridge_conn.send_command.call_args_list
            if c[0][0] == "say"
        ]
        assert len(say_calls) == 1
        assert say_calls[0][0][1]["message"] == "Hey there!"

    @pytest.mark.asyncio
    async def test_chat_with_task_triggers_code_agent(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """When chat agent returns a task, code agent is called."""
        task = {
            "intent": "build a wall",
            "player_name": "Alex",
            "player_position": {"x": 105, "y": 64, "z": -195},
        }

        # First call: chat agent returns task + chat
        # Second call: code agent returns valid code
        # Third call: chat agent narrates result
        mock_anthropic_client.messages.create.side_effect = [
            make_chat_response(
                chat_messages=["On it!"],
                task_description=task,
            ),
            make_code_response(VALID_LEVEL1_CODE),
            make_chat_response(chat_messages=["Done!"]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("build me a wall")

        # Three API calls: chat, code, narration
        assert mock_anthropic_client.messages.create.call_count == 3

        # Verify code agent was called with correct model
        code_call = mock_anthropic_client.messages.create.call_args_list[1]
        assert code_call.kwargs["model"] == CODE_MODEL

        # Verify narration was called
        narration_call = mock_anthropic_client.messages.create.call_args_list[2]
        assert narration_call.kwargs["model"] == CHAT_MODEL

    @pytest.mark.asyncio
    async def test_learner_events_processed(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Learner events from chat agent are processed through learner model."""
        mock_anthropic_client.messages.create.return_value = make_chat_response(
            chat_messages=["Nice!"],
            learner_events=[{
                "event": "code_modified",
                "concept": "variables",
                "detail": "Changed block type",
                "context": "building",
                "success": True,
            }],
        )

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("I changed the block")

        # Learner model should have been updated
        state = orchestrator._learner.get_agent_state()
        # The variable concept should have advanced from the event
        assert state["concepts"]["variables"]["stage"] != "none" or \
               state["concepts"]["variables"]["p_mastery"] > 0


# ── Test: Code Validation Retry Loop ─────────────────────────────────────────


class TestCodeValidation:
    """Code validation → retry → valid / infeasible."""

    @pytest.mark.asyncio
    async def test_valid_code_executes(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Valid code passes validation and is executed."""
        task = {"intent": "test", "player_name": "Alex"}

        mock_anthropic_client.messages.create.side_effect = [
            make_chat_response(chat_messages=["On it!"], task_description=task),
            make_code_response(VALID_LEVEL1_CODE),
            make_chat_response(chat_messages=["Done!"]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("do something")

        # Code was executed (say calls from narration)
        assert mock_anthropic_client.messages.create.call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_code_retries(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Invalid code triggers retry with validation errors."""
        task = {"intent": "test", "player_name": "Alex"}

        mock_anthropic_client.messages.create.side_effect = [
            # 1. Chat agent returns task
            make_chat_response(chat_messages=["On it!"], task_description=task),
            # 2. First code attempt: invalid (uses for-loop at level 1)
            make_code_response(INVALID_LEVEL1_CODE),
            # 3. Second code attempt: valid
            make_code_response(VALID_LEVEL1_CODE),
            # 4. Narration
            make_chat_response(chat_messages=["Done!"]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("build something")

        # 4 API calls: chat + invalid code + retry code + narration
        assert mock_anthropic_client.messages.create.call_count == 4

        # The retry call should include validation errors
        retry_call = mock_anthropic_client.messages.create.call_args_list[2]
        user_msg = retry_call.kwargs["messages"][0]["content"]
        assert "Previous Attempt Failed Validation" in user_msg

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """When all retries produce invalid code, report infeasible."""
        task = {"intent": "test", "player_name": "Alex"}

        responses = [
            make_chat_response(chat_messages=["On it!"], task_description=task),
        ]
        # All code attempts invalid
        for _ in range(MAX_CODE_RETRIES + 1):
            responses.append(make_code_response(INVALID_LEVEL1_CODE))
        # Narration for infeasible
        responses.append(make_chat_response(chat_messages=["I can't figure that out."]))

        mock_anthropic_client.messages.create.side_effect = responses

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("sort my inventory")

        # Narration call should include infeasible details
        narration_call = mock_anthropic_client.messages.create.call_args_list[-1]
        user_msg = narration_call.kwargs["messages"][0]["content"]
        assert "infeasible" in user_msg.lower() or "Code Execution Results" in user_msg

    @pytest.mark.asyncio
    async def test_infeasible_from_code_agent(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Code agent returning infeasible is handled without retries."""
        task = {"intent": "sort inventory", "player_name": "Alex"}

        mock_anthropic_client.messages.create.side_effect = [
            make_chat_response(chat_messages=["Let me try..."], task_description=task),
            make_infeasible_response(),
            make_chat_response(chat_messages=["I can't do that yet."]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("sort my stuff")

        # Only 3 calls: chat + infeasible code + narration (no retries)
        assert mock_anthropic_client.messages.create.call_count == 3


# ── Test: Level Gating ───────────────────────────────────────────────────────


class TestLevelGating:
    """Concept constraints are attached correctly to code agent calls."""

    @pytest.mark.asyncio
    async def test_level1_constraints(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Level 1 constraints are sent to code agent."""
        task = {"intent": "build wall", "player_name": "Alex"}
        mock_anthropic_client.messages.create.side_effect = [
            make_chat_response(chat_messages=["On it!"], task_description=task),
            make_code_response(VALID_LEVEL1_CODE),
            make_chat_response(chat_messages=["Done!"]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("build a wall")

        # Check code agent call has level 1 constraints
        code_call = mock_anthropic_client.messages.create.call_args_list[1]
        user_msg = code_call.kwargs["messages"][0]["content"]
        assert '"level": 1' in user_msg
        assert "max_nesting_depth" in user_msg

    @pytest.mark.asyncio
    async def test_code_style_from_challenge(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Active challenge's code_style is passed to code agent."""
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        task = {"intent": "help with wall", "player_name": "Alex"}
        mock_anthropic_client.messages.create.side_effect = [
            make_chat_response(chat_messages=["Sure!"], task_description=task),
            make_code_response(VALID_LEVEL1_CODE),
            make_chat_response(chat_messages=["Done!"]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("help me build")

        code_call = mock_anthropic_client.messages.create.call_args_list[1]
        user_msg = code_call.kwargs["messages"][0]["content"]
        assert "explicit_repetition" in user_msg


# ── Test: Challenge State Machine ────────────────────────────────────────────


class TestChallengeStateMachine:
    """Beat progression, trigger evaluation, abort conditions."""

    def test_activate_challenge(self, orchestrator: Orchestrator) -> None:
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        assert orchestrator._active_challenge is not None
        assert orchestrator._active_challenge.challenge_id == "test-challenge-1"
        assert orchestrator._active_challenge.current_beat == "ki"
        assert orchestrator._active_challenge.code_style == "explicit_repetition"
        assert orchestrator._challenges_this_session == 1

    @pytest.mark.asyncio
    async def test_beat_progression_on_affirmative(
        self, orchestrator: Orchestrator
    ) -> None:
        """Trigger 'says yes' advances from ki to sho."""
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        await orchestrator._evaluate_challenge_triggers(
            "player_chat", {"name": "Alex", "message": "yes sure"}
        )
        assert orchestrator._active_challenge is not None
        assert orchestrator._active_challenge.current_beat == "sho"

    @pytest.mark.asyncio
    async def test_beat_progression_on_execution_complete(
        self, orchestrator: Orchestrator
    ) -> None:
        """Trigger 'after execution completes' advances from sho to ten."""
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)
        orchestrator._active_challenge.current_beat = "sho"  # type: ignore

        await orchestrator._evaluate_challenge_triggers("_execution_complete", {})
        assert orchestrator._active_challenge is not None
        assert orchestrator._active_challenge.current_beat == "ten"

    @pytest.mark.asyncio
    async def test_beat_progression_on_code_engagement(
        self, orchestrator: Orchestrator
    ) -> None:
        """Trigger 'kid engages with code' advances from ten to ketsu."""
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)
        orchestrator._active_challenge.current_beat = "ten"  # type: ignore

        await orchestrator._evaluate_challenge_triggers(
            "player_chat", {"name": "Alex", "message": "why does the code repeat?"}
        )
        assert orchestrator._active_challenge is not None
        assert orchestrator._active_challenge.current_beat == "ketsu"

    @pytest.mark.asyncio
    async def test_abort_on_hostile_mob(self, orchestrator: Orchestrator) -> None:
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)
        assert orchestrator._active_challenge is not None

        await orchestrator._evaluate_challenge_triggers(
            "entity_nearby", {"entity_type": "zombie", "hostile": True}
        )
        assert orchestrator._active_challenge is None

    @pytest.mark.asyncio
    async def test_abort_on_player_joined(self, orchestrator: Orchestrator) -> None:
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        await orchestrator._evaluate_challenge_triggers(
            "player_joined", {"name": "Steve"}
        )
        assert orchestrator._active_challenge is None

    @pytest.mark.asyncio
    async def test_abort_on_player_left(self, orchestrator: Orchestrator) -> None:
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        await orchestrator._evaluate_challenge_triggers(
            "player_left", {"name": "Alex"}
        )
        assert orchestrator._active_challenge is None

    @pytest.mark.asyncio
    async def test_no_advance_on_wrong_trigger(
        self, orchestrator: Orchestrator
    ) -> None:
        """Non-matching event doesn't advance the beat."""
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        await orchestrator._evaluate_challenge_triggers(
            "block_placed", {"block_type": "cobblestone"}
        )
        assert orchestrator._active_challenge is not None
        assert orchestrator._active_challenge.current_beat == "ki"

    def test_get_active_directive(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._get_active_directive() is None

        orchestrator._activate_challenge(SAMPLE_CHALLENGE)
        directive = orchestrator._get_active_directive()

        assert directive is not None
        assert directive["active_beat"] == "ki"
        assert directive["challenge_id"] == "test-challenge-1"

    def test_retire_challenge(self, orchestrator: Orchestrator) -> None:
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)
        assert orchestrator._active_challenge is not None

        orchestrator._retire_challenge()
        assert orchestrator._active_challenge is None


# ── Test: World Context Assembly ─────────────────────────────────────────────


class TestWorldContext:
    """World context from bridge events."""

    @pytest.mark.asyncio
    async def test_assemble_from_bridge(
        self, orchestrator: Orchestrator, mock_bridge_conn: MagicMock
    ) -> None:
        mock_bridge_conn.send_command.return_value = SAMPLE_WORLD_STATE

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            ctx = await orchestrator._assemble_world_context()

        assert ctx.player_name == "Alex"
        assert ctx.player_position == {"x": 105, "y": 64, "z": -195}
        assert ctx.bot_position == {"x": 100, "y": 64, "z": -200}
        assert ctx.time_of_day == "noon"
        assert ctx.game_mode == "survival"

    @pytest.mark.asyncio
    async def test_assemble_handles_bridge_error(
        self, orchestrator: Orchestrator, mock_bridge_conn: MagicMock
    ) -> None:
        """Gracefully handles bridge communication failure."""
        mock_bridge_conn.send_command.side_effect = Exception("connection lost")

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            ctx = await orchestrator._assemble_world_context()

        # Should return defaults, not raise
        assert ctx.player_name == "Alex"
        assert ctx.time_of_day == "noon"

    def test_detect_building_activity(self, orchestrator: Orchestrator) -> None:
        now = time.monotonic()
        orchestrator._recent_events = [
            {"event": "block_placed", "data": {"block_type": "cobblestone"}, "time": now},
            {"event": "block_placed", "data": {"block_type": "cobblestone"}, "time": now},
            {"event": "block_placed", "data": {"block_type": "cobblestone"}, "time": now},
        ]
        assert orchestrator._detect_player_activity() == "building"

    def test_detect_mining_activity(self, orchestrator: Orchestrator) -> None:
        now = time.monotonic()
        orchestrator._recent_events = [
            {"event": "block_broken", "data": {"block_type": "stone"}, "time": now},
            {"event": "block_broken", "data": {"block_type": "stone"}, "time": now},
            {"event": "block_broken", "data": {"block_type": "stone"}, "time": now},
        ]
        assert orchestrator._detect_player_activity() == "mining"

    def test_detect_idle(self, orchestrator: Orchestrator) -> None:
        orchestrator._recent_events = []
        assert orchestrator._detect_player_activity() == "idle"

    def test_summarize_recent_actions(self, orchestrator: Orchestrator) -> None:
        now = time.monotonic()
        orchestrator._recent_events = [
            {"event": "block_placed", "data": {"block_type": "cobblestone"}, "time": now},
            {"event": "block_placed", "data": {"block_type": "cobblestone"}, "time": now},
            {"event": "block_broken", "data": {"block_type": "dirt"}, "time": now},
        ]
        summaries = orchestrator._summarize_recent_actions()
        assert "placed 2 cobblestone blocks" in summaries
        assert "broke 1 dirt blocks" in summaries

    def test_world_context_to_chat_dict(self) -> None:
        ctx = WorldContext(
            player_name="Alex",
            player_position={"x": 1, "y": 2, "z": 3},
            player_activity="building",
            bot_position={"x": 4, "y": 5, "z": 6},
            bot_inventory=[],
            time_of_day="noon",
            game_mode="survival",
            session_duration_minutes=15,
        )
        d = ctx.to_chat_dict()
        assert d["player_name"] == "Alex"
        assert d["player_activity"] == "building"
        assert "nearby_entities" not in d

    def test_world_context_to_code_dict(self) -> None:
        ctx = WorldContext(
            player_name="Alex",
            player_position={"x": 1, "y": 2, "z": 3},
            player_activity="building",
            bot_position={"x": 4, "y": 5, "z": 6},
            bot_inventory=[{"name": "stone", "count": 10}],
            time_of_day="dusk",
            game_mode="creative",
            session_duration_minutes=15,
        )
        d = ctx.to_code_dict()
        assert d["bot_position"] == {"x": 4, "y": 5, "z": 6}
        assert d["game_mode"] == "creative"
        assert "player_name" not in d


# ── Test: Learner Model Integration ──────────────────────────────────────────


class TestLearnerIntegration:
    """Events flow through, state updates propagate to next agent call."""

    def test_process_learner_event_updates_model(
        self, orchestrator: Orchestrator
    ) -> None:
        ctx = WorldContext(
            player_name="Alex",
            player_position={"x": 0, "y": 0, "z": 0},
            player_activity="building",
            bot_position={"x": 0, "y": 0, "z": 0},
            bot_inventory=[],
            time_of_day="noon",
            game_mode="survival",
            session_duration_minutes=10,
        )
        event_data = {
            "event": "code_modified",
            "concept": "variables",
            "detail": "Changed block type",
            "context": "building",
            "success": True,
        }
        orchestrator._process_learner_event(event_data, ctx)

        state = orchestrator._learner.get_agent_state()
        var_state = state["concepts"]["variables"]
        assert var_state["p_mastery"] > 0
        assert "building" in var_state["contexts_seen"]

    def test_disengagement_increments_counter(
        self, orchestrator: Orchestrator
    ) -> None:
        ctx = WorldContext(
            player_name="Alex",
            player_position={"x": 0, "y": 0, "z": 0},
            player_activity="idle",
            bot_position={"x": 0, "y": 0, "z": 0},
            bot_inventory=[],
            time_of_day="noon",
            game_mode="survival",
            session_duration_minutes=10,
        )
        event_data = {
            "event": "disengaged",
            "concept": None,
            "detail": "Kid said this is boring",
            "context": "building",
        }
        orchestrator._process_learner_event(event_data, ctx)
        assert orchestrator._disengagement_count == 1

        orchestrator._process_learner_event(event_data, ctx)
        assert orchestrator._disengagement_count == 2

    @pytest.mark.asyncio
    async def test_learner_state_in_chat_agent_call(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Learner state is included in chat agent's user message."""
        mock_anthropic_client.messages.create.return_value = make_chat_response(
            chat_messages=["Hi!"]
        )

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("hello")

        call_kwargs = mock_anthropic_client.messages.create.call_args
        user_msg = call_kwargs.kwargs["messages"][0]["content"]
        assert "Learner Model State" in user_msg
        assert "current_level" in user_msg

    @pytest.mark.asyncio
    async def test_code_displayed_updates_learner(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """process_code_displayed is called after successful execution."""
        task = {"intent": "test", "player_name": "Alex"}
        # Use VALID_LEVEL1_CODE_PURE which has only assignments (no SDK calls)
        # so execution succeeds without a live bridge.
        mock_anthropic_client.messages.create.side_effect = [
            make_chat_response(chat_messages=["On it!"], task_description=task),
            make_code_response(VALID_LEVEL1_CODE_PURE),
            make_chat_response(chat_messages=["Done!"]),
        ]

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("do something")

        # Concepts in the pure-assignment code should now be exposed
        state = orchestrator._learner.get_agent_state()
        # VALID_LEVEL1_CODE_PURE has Assign → variables
        assert state["concepts"]["variables"]["stage"] == "exposed"


# ── Test: Session Timing ─────────────────────────────────────────────────────


class TestSessionTiming:
    """Challenge suppression based on session timing."""

    def test_no_challenge_before_10_minutes(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator._session_start = time.monotonic()  # just started
        assert orchestrator._should_generate_challenge() is False

    def test_challenge_allowed_after_10_minutes(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator._session_start = time.monotonic() - (11 * 60)  # 11 min ago
        assert orchestrator._should_generate_challenge() is True

    def test_no_challenge_while_active(self, orchestrator: Orchestrator) -> None:
        orchestrator._session_start = time.monotonic() - (15 * 60)
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)
        assert orchestrator._should_generate_challenge() is False

    def test_min_15_minutes_between_challenges(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator._session_start = time.monotonic() - (30 * 60)
        orchestrator._last_challenge_time = time.monotonic() - (10 * 60)  # 10 min ago
        assert orchestrator._should_generate_challenge() is False

        orchestrator._last_challenge_time = time.monotonic() - (16 * 60)  # 16 min ago
        assert orchestrator._should_generate_challenge() is True

    def test_no_challenge_after_2_disengagements(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator._session_start = time.monotonic() - (20 * 60)
        orchestrator._disengagement_count = 2
        assert orchestrator._should_generate_challenge() is False

    def test_no_challenge_without_session_start(
        self, orchestrator: Orchestrator
    ) -> None:
        orchestrator._session_start = None
        assert orchestrator._should_generate_challenge() is False


# ── Test: Response Parsers ───────────────────────────────────────────────────


class TestResponseParsers:
    """Parse various agent response formats."""

    def test_parse_chat_json(self, orchestrator: Orchestrator) -> None:
        text = json.dumps({"chat_messages": ["Hello!"], "task_description": None})
        result = orchestrator._parse_chat_response(text)
        assert result["chat_messages"] == ["Hello!"]

    def test_parse_chat_json_in_markdown(self, orchestrator: Orchestrator) -> None:
        text = '```json\n{"chat_messages": ["Hi!"]}\n```'
        result = orchestrator._parse_chat_response(text)
        assert result["chat_messages"] == ["Hi!"]

    def test_parse_chat_plain_text(self, orchestrator: Orchestrator) -> None:
        text = "I'm just a golem doing golem things."
        result = orchestrator._parse_chat_response(text)
        assert result["chat_messages"] == [text]

    def test_parse_code_python_block(self, orchestrator: Orchestrator) -> None:
        text = '```python\nfrom golem import *\npos = get_position()\n```'
        result = orchestrator._parse_code_response(text)
        assert isinstance(result, str)
        assert "from golem import *" in result

    def test_parse_code_plain(self, orchestrator: Orchestrator) -> None:
        text = 'from golem import *\npos = get_position()'
        result = orchestrator._parse_code_response(text)
        assert isinstance(result, str)
        assert "from golem import *" in result

    def test_parse_code_infeasible(self, orchestrator: Orchestrator) -> None:
        data = {"status": "infeasible", "reason": "needs loops"}
        text = json.dumps(data)
        result = orchestrator._parse_code_response(text)
        assert isinstance(result, dict)
        assert result["status"] == "infeasible"

    def test_parse_challenge_none(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._parse_challenge_response("none") is None
        assert orchestrator._parse_challenge_response("None") is None

    def test_parse_challenge_json(self, orchestrator: Orchestrator) -> None:
        text = json.dumps(SAMPLE_CHALLENGE)
        result = orchestrator._parse_challenge_response(text)
        assert result is not None
        assert result["challenge_id"] == "test-challenge-1"

    def test_parse_challenge_invalid(self, orchestrator: Orchestrator) -> None:
        result = orchestrator._parse_challenge_response("not json at all {{{")
        assert result is None


# ── Test: Code Execution ─────────────────────────────────────────────────────


class TestCodeExecution:
    """Sandboxed code execution."""

    def test_prepare_strips_import(self, orchestrator: Orchestrator) -> None:
        code = "from golem import *\n\nblock = 'stone'\n"
        clean, ns = orchestrator._prepare_code_for_exec(code)
        assert "from golem import *" not in clean
        assert "block = 'stone'" in clean

    def test_prepare_provides_sdk_functions(self, orchestrator: Orchestrator) -> None:
        _, ns = orchestrator._prepare_code_for_exec("")
        # SDK functions should be in namespace
        assert "place_block" in ns
        assert "get_position" in ns
        assert "move_to" in ns

    def test_prepare_restricts_builtins(self, orchestrator: Orchestrator) -> None:
        _, ns = orchestrator._prepare_code_for_exec("")
        builtins = ns["__builtins__"]
        assert "print" in builtins
        assert "int" in builtins
        # Dangerous builtins should NOT be present
        assert "eval" not in builtins
        assert "exec" not in builtins
        assert "open" not in builtins
        assert "__import__" not in builtins

    @pytest.mark.asyncio
    async def test_execute_success(
        self, orchestrator: Orchestrator, mock_bridge_conn: MagicMock
    ) -> None:
        """Simple code executes successfully."""
        code = "x = 1 + 2\n"
        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            result = await orchestrator._execute_code(code)
        assert result.status == "success"
        assert result.execution_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_execute_error(self, orchestrator: Orchestrator) -> None:
        """Code that raises an exception returns error status."""
        code = "x = 1 / 0\n"
        result = await orchestrator._execute_code(code)
        assert result.status == "error"
        assert result.error_details is not None
        assert result.error_details["type"] == "ZeroDivisionError"


# ── Test: Trigger Matching ───────────────────────────────────────────────────


class TestTriggerMatching:
    """Challenge trigger condition matching."""

    def test_affirmative_trigger(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._trigger_matches(
            "Kid accepts help (says yes, or affirmative)",
            "player_chat",
            {"message": "yes please"},
        )

    def test_affirmative_no_match(self, orchestrator: Orchestrator) -> None:
        assert not orchestrator._trigger_matches(
            "Kid accepts help (says yes, or affirmative)",
            "player_chat",
            {"message": "no thanks"},
        )

    def test_execution_complete_trigger(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._trigger_matches(
            "After execution completes",
            "_execution_complete",
            {},
        )

    def test_code_edit_trigger(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._trigger_matches(
            "Kid modifies the code",
            "code_panel_edit",
            {"source": "..."},
        )

    def test_code_question_trigger(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._trigger_matches(
            "Kid asks about the pattern",
            "player_chat",
            {"message": "why does the code repeat so much?"},
        )

    def test_scroll_trigger(self, orchestrator: Orchestrator) -> None:
        assert orchestrator._trigger_matches(
            "Kid scrolls through the code",
            "code_panel_scroll",
            {"visible_lines": {"start": 1, "end": 20}},
        )

    def test_no_match_on_unrelated(self, orchestrator: Orchestrator) -> None:
        assert not orchestrator._trigger_matches(
            "Kid accepts help",
            "block_placed",
            {"block_type": "stone"},
        )


# ── Test: Challenge Agent Integration ────────────────────────────────────────


class TestChallengeAgent:
    """Challenge agent call and activation."""

    @pytest.mark.asyncio
    async def test_call_challenge_agent(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        mock_anthropic_client.messages.create.return_value = make_challenge_response(
            SAMPLE_CHALLENGE
        )

        ctx = WorldContext(
            player_name="Alex",
            player_position={"x": 0, "y": 0, "z": 0},
            player_activity="building",
            bot_position={"x": 0, "y": 0, "z": 0},
            bot_inventory=[],
            time_of_day="noon",
            game_mode="survival",
            session_duration_minutes=15,
        )

        result = await orchestrator._call_challenge_agent(ctx)
        assert result is not None
        assert result["target_concept"] == "for_loops"

        # Verify correct model was used
        call_kwargs = mock_anthropic_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == CHALLENGE_MODEL

    @pytest.mark.asyncio
    async def test_call_challenge_agent_none(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        mock_anthropic_client.messages.create.return_value = make_no_challenge_response()

        ctx = WorldContext(
            player_name="Alex",
            player_position={"x": 0, "y": 0, "z": 0},
            player_activity="idle",
            bot_position={"x": 0, "y": 0, "z": 0},
            bot_inventory=[],
            time_of_day="noon",
            game_mode="survival",
            session_duration_minutes=5,
        )

        result = await orchestrator._call_challenge_agent(ctx)
        assert result is None


# ── Test: Directive Passing ──────────────────────────────────────────────────


class TestDirectivePassing:
    """Challenge directives are passed to chat agent."""

    @pytest.mark.asyncio
    async def test_directive_in_chat_call(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Active directive is included in chat agent's context."""
        orchestrator._activate_challenge(SAMPLE_CHALLENGE)

        mock_anthropic_client.messages.create.return_value = make_chat_response(
            chat_messages=["I can help with that!"]
        )

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("help me build a wall")

        call_kwargs = mock_anthropic_client.messages.create.call_args
        user_msg = call_kwargs.kwargs["messages"][0]["content"]
        assert "Challenge Directive" in user_msg
        assert "active_beat" in user_msg

    @pytest.mark.asyncio
    async def test_no_directive_without_challenge(
        self, orchestrator: Orchestrator, mock_anthropic_client: AsyncMock,
        mock_bridge_conn: MagicMock,
    ) -> None:
        """Without an active challenge, no directive is included."""
        mock_anthropic_client.messages.create.return_value = make_chat_response(
            chat_messages=["Sure!"]
        )

        with patch("golem.orchestrator.get_connection", return_value=mock_bridge_conn):
            await orchestrator.handle_player_chat("hello")

        call_kwargs = mock_anthropic_client.messages.create.call_args
        user_msg = call_kwargs.kwargs["messages"][0]["content"]
        assert "Challenge Directive" not in user_msg
