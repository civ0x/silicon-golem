"""Integration tests — full chain: Python SDK -> WebSocket -> Mineflayer bridge -> Minecraft.

Prerequisites:
    - Minecraft Java Edition 1.20.4 server running on localhost:25565
    - bridge/ directory with node_modules installed (npm install)

Run with:
    pytest golem/test/test_integration.py -m integration

Environment variables:
    MC_HOST              - Minecraft server host (default: localhost)
    MC_PORT              - Minecraft server port (default: 25565)
    INTEGRATION_PLAYER   - Player name for player-dependent tests (default: unset, tests skipped)
"""

import json
import os
import socket
import subprocess
import time
import uuid

import pytest
import websockets.sync.client

from golem.connection import reset_connection
from golem.errors import (
    BlockError,
    CancelledError,
    GolemError,
    InventoryError,
    PathfindingError,
    PlayerError,
)
from golem.sdk import (
    Item,
    Position,
    build_line,
    build_wall,
    collect,
    connect,
    dig_block,
    disconnect,
    find_blocks,
    get_block,
    get_inventory,
    get_player_position,
    get_position,
    move_to,
    move_to_player,
    place_block,
    say,
)

pytestmark = pytest.mark.integration

# --- Configuration ---

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRIDGE_DIR = os.path.join(PROJECT_ROOT, "bridge")
BRIDGE_SCRIPT = os.path.join(BRIDGE_DIR, "server.js")
WS_PORT = 3002  # Avoid conflict with default 3001
MC_HOST = os.environ.get("MC_HOST", "localhost")
MC_PORT = os.environ.get("MC_PORT", "25565")
PLAYER_NAME = os.environ.get("INTEGRATION_PLAYER", "")


def _bridge_available() -> bool:
    return (
        os.path.isfile(BRIDGE_SCRIPT)
        and os.path.isdir(os.path.join(BRIDGE_DIR, "node_modules"))
    )


def _mc_server_reachable() -> bool:
    try:
        sock = socket.create_connection((MC_HOST, int(MC_PORT)), timeout=2)
        sock.close()
        return True
    except (socket.error, OSError):
        return False


needs_player = pytest.mark.skipif(
    not PLAYER_NAME,
    reason="No player specified (set INTEGRATION_PLAYER=<name>)",
)


# --- Helpers ---


def _recv_response(ws, cmd_id: str, timeout: float = 10.0) -> dict:
    """Receive messages until we get a response matching cmd_id, skipping events."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        raw = ws.recv(timeout=remaining)
        msg = json.loads(raw)
        if msg.get("type") == "response" and msg.get("id") == cmd_id:
            return msg
    raise TimeoutError(f"No response for command {cmd_id}")


def _send_cmd(ws, action: str, args: dict | None = None) -> tuple[str, dict]:
    """Send a command over raw WS and return (cmd_id, response)."""
    cmd_id = str(uuid.uuid4())
    ws.send(json.dumps({
        "type": "command",
        "id": cmd_id,
        "action": action,
        "args": args or {},
    }))
    return cmd_id, _recv_response(ws, cmd_id)


# --- Fixtures ---


@pytest.fixture(scope="module")
def bridge_process():
    """Start the Mineflayer bridge as a subprocess.

    Waits for the bot to spawn and WebSocket server to accept connections.
    """
    if not _bridge_available():
        pytest.skip("Bridge not available (bridge/server.js or node_modules missing)")
    if not _mc_server_reachable():
        pytest.skip(f"Minecraft server not reachable at {MC_HOST}:{MC_PORT}")

    env = {
        **os.environ,
        "WS_PORT": str(WS_PORT),
        "MC_HOST": MC_HOST,
        "MC_PORT": str(MC_PORT),
        "BOT_NAME": "GolemTest",
    }

    proc = subprocess.Popen(
        ["node", BRIDGE_SCRIPT],
        cwd=BRIDGE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for the WebSocket server to become ready (bot must spawn first)
    ready = False
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read() if proc.stdout else ""
            pytest.fail(f"Bridge process exited early:\n{output}")
        try:
            ws = websockets.sync.client.connect(f"ws://localhost:{WS_PORT}")
            raw = ws.recv(timeout=10)
            msg = json.loads(raw)
            if msg.get("event") == "ready":
                ready = True
                ws.close()
                break
            ws.close()
        except Exception:
            time.sleep(1)

    if not ready:
        proc.terminate()
        proc.wait(timeout=5)
        output = proc.stdout.read() if proc.stdout else ""
        pytest.fail(f"Bridge WebSocket never became ready:\n{output}")

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture()
def sdk(bridge_process):
    """Connect the SDK to the bridge, disconnect after each test."""
    reset_connection()
    connect("localhost", WS_PORT)
    yield
    disconnect()


@pytest.fixture()
def raw_ws(bridge_process):
    """Raw WebSocket connection for protocol-level tests."""
    ws = websockets.sync.client.connect(f"ws://localhost:{WS_PORT}")
    # Consume the ready event
    raw = ws.recv(timeout=5)
    msg = json.loads(raw)
    assert msg["event"] == "ready"
    yield ws
    ws.close()


# ============================================================
# 1. Connection Lifecycle
# ============================================================


class TestConnectionLifecycle:
    def test_ready_event_on_connect(self, bridge_process):
        """Bridge sends a ready event immediately on WebSocket connection."""
        ws = websockets.sync.client.connect(f"ws://localhost:{WS_PORT}")
        raw = ws.recv(timeout=5)
        msg = json.loads(raw)
        assert msg["type"] == "event"
        assert msg["event"] == "ready"
        assert msg["data"]["bot_name"] == "GolemTest"
        assert msg["data"]["mc_version"] == "1.20.4"
        ws.close()

    def test_sdk_connects_and_issues_command(self, sdk):
        """SDK connects and can issue a basic query."""
        pos = get_position()
        assert isinstance(pos, Position)

    def test_configure_player_tracking(self, raw_ws):
        """Configure command sets the tracked player."""
        cmd_id, resp = _send_cmd(raw_ws, "configure", {"track_player": "TestPlayer"})
        assert resp["success"] is True
        assert resp["data"]["configured"] is True


# ============================================================
# 2. Observation Actions
# ============================================================


class TestObservation:
    def test_get_position_valid_coords(self, sdk):
        """get_position returns coordinates within MC world bounds."""
        pos = get_position()
        assert isinstance(pos, Position)
        assert -30_000_000 <= pos.x <= 30_000_000
        assert -64 <= pos.y <= 320
        assert -30_000_000 <= pos.z <= 30_000_000

    def test_get_position_consistency(self, sdk):
        """Two rapid calls return the same position (bot is stationary)."""
        pos1 = get_position()
        pos2 = get_position()
        assert abs(pos1.x - pos2.x) <= 1
        assert abs(pos1.y - pos2.y) <= 1
        assert abs(pos1.z - pos2.z) <= 1

    def test_get_inventory_returns_item_list(self, sdk):
        """get_inventory returns a list of Item objects."""
        inv = get_inventory()
        assert isinstance(inv, list)
        for item in inv:
            assert isinstance(item, Item)
            assert isinstance(item.name, str)
            assert isinstance(item.count, int)
            assert item.count > 0

    def test_get_block_ground(self, sdk):
        """Block below the bot should be a solid block, not air."""
        pos = get_position()
        block = get_block(pos.x, pos.y - 1, pos.z)
        assert isinstance(block, str)
        assert block != "air"

    def test_get_block_high_air(self, sdk):
        """Block at build limit should be air."""
        pos = get_position()
        block = get_block(pos.x, 319, pos.z)
        assert block == "air"


# ============================================================
# 3. Movement
# ============================================================


class TestMovement:
    def test_move_to_nearby(self, sdk):
        """Bot moves a few blocks and arrives near the target."""
        pos = get_position()
        target_x = pos.x + 3
        result = move_to(target_x, pos.y, pos.z)
        assert result is True
        new_pos = get_position()
        assert abs(new_pos.x - target_x) <= 2

    def test_move_to_updates_position(self, sdk):
        """After move_to, get_position reflects the new location."""
        start = get_position()
        move_to(start.x + 5, start.y, start.z + 5)
        end = get_position()
        moved = abs(end.x - start.x) + abs(end.z - start.z)
        assert moved > 0

    @needs_player
    def test_move_to_player(self, sdk):
        """Bot navigates to the tracked player."""
        result = move_to_player(PLAYER_NAME)
        assert result is True


# ============================================================
# 4. Block Interaction
# ============================================================


class TestBlockInteraction:
    def test_dig_and_confirm(self, sdk):
        """Dig a block and verify it becomes air."""
        pos = get_position()
        # Dig two below the bot to avoid falling
        target_y = pos.y - 2
        block_before = get_block(pos.x, target_y, pos.z)
        if block_before in ("air", "bedrock"):
            pytest.skip(f"No diggable block at test position (found {block_before})")

        block_type = dig_block(pos.x, target_y, pos.z)
        assert block_type == block_before
        block_after = get_block(pos.x, target_y, pos.z)
        assert block_after == "air"

    def test_place_and_confirm(self, sdk):
        """Place a block and verify it exists at the target."""
        inv = get_inventory()
        placeable = next((i for i in inv if i.count >= 1), None)
        if not placeable:
            pytest.skip("No blocks in inventory to place")

        pos = get_position()
        tx, ty, tz = pos.x + 2, pos.y, pos.z + 2

        # Clear target if occupied
        existing = get_block(tx, ty, tz)
        if existing != "air":
            dig_block(tx, ty, tz)

        result = place_block(tx, ty, tz, placeable.name)
        assert result is True
        placed = get_block(tx, ty, tz)
        assert placed != "air"


# ============================================================
# 5. Compound Actions
# ============================================================


class TestCompoundActions:
    def test_build_line_places_correct_count(self, sdk):
        """build_line returns the number of blocks placed."""
        inv = get_inventory()
        block_item = next((i for i in inv if i.count >= 3), None)
        if not block_item:
            pytest.skip("Need 3+ of a block type in inventory")

        pos = get_position()
        count = build_line(pos.x + 3, pos.y, pos.z, "east", 3, block_item.name)
        assert count == 3

    def test_collect_gathers_blocks(self, sdk):
        """collect finds and breaks at least one block."""
        pos = get_position()
        ground = get_block(pos.x, pos.y - 1, pos.z)
        if ground in ("air", "bedrock"):
            pytest.skip("No collectible blocks at spawn")

        try:
            count = collect(ground, 1)
            assert count >= 1
        except BlockError:
            pytest.skip(f"No collectible {ground} found nearby")

    def test_build_wall_with_progress(self, sdk):
        """build_wall executes and optionally fires progress callbacks."""
        inv = get_inventory()
        block_item = next((i for i in inv if i.count >= 6), None)
        if not block_item:
            pytest.skip("Need 6+ of a block type in inventory")

        pos = get_position()
        progress_updates: list[dict] = []
        count = build_wall(
            pos.x + 5, pos.y, pos.z + 5,
            "east", 3, 2, block_item.name,
            on_progress=lambda p: progress_updates.append(p),
        )
        assert count > 0
        # Progress callbacks fire only every 1000ms, so they may not
        # appear for fast builds. Verify structure if any arrived.
        for p in progress_updates:
            assert "blocks_placed" in p
            assert "blocks_total" in p


# ============================================================
# 6. Error Paths
# ============================================================


class TestErrorPaths:
    def test_invalid_block_name_with_suggestion(self, sdk):
        """Misspelled block name raises BlockError with a suggestion."""
        with pytest.raises(BlockError) as exc_info:
            place_block(0, 64, 0, "stoone")
        assert exc_info.value.code == "INVALID_BLOCK_NAME"
        assert exc_info.value.details.get("suggestion") is not None

    def test_item_not_in_inventory(self, sdk):
        """Placing a block the bot doesn't have raises an appropriate error."""
        with pytest.raises((InventoryError, BlockError)):
            place_block(0, 64, 0, "netherite_block")

    def test_dig_air_raises_block_error(self, sdk):
        """Digging an air block raises BlockError."""
        pos = get_position()
        with pytest.raises(BlockError) as exc_info:
            dig_block(pos.x, 319, pos.z)
        assert exc_info.value.code in ("NO_BLOCK_AT_POSITION", "BLOCK_NOT_FOUND")

    def test_invalid_direction(self, sdk):
        """Invalid direction in build_line raises BlockError."""
        inv = get_inventory()
        block_item = next((i for i in inv if i.count >= 3), None)
        if not block_item:
            pytest.skip("Need blocks in inventory")

        with pytest.raises(BlockError) as exc_info:
            build_line(0, 64, 0, "northwest", 3, block_item.name)
        assert exc_info.value.code == "INVALID_DIRECTION"

    @needs_player
    def test_player_not_found(self, sdk):
        """Moving to a nonexistent player raises PlayerError."""
        with pytest.raises(PlayerError):
            move_to_player("NonexistentPlayer12345")


# ============================================================
# 7. Event Streaming
# ============================================================


class TestEventStreaming:
    def test_heartbeat_received(self, raw_ws):
        """Bridge sends heartbeat events every 10 seconds."""
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            raw = raw_ws.recv(timeout=remaining)
            msg = json.loads(raw)
            if msg.get("event") == "heartbeat":
                assert "bot_position" in msg["data"]
                assert "uptime_seconds" in msg["data"]
                return
        pytest.fail("No heartbeat received within 15 seconds")

    def test_code_panel_event_relay(self, raw_ws):
        """Code panel events are broadcast through the bridge."""
        event = {
            "type": "event",
            "event": "code_panel_run",
            "data": {"code": "move_to(10, 64, 20)"},
        }
        raw_ws.send(json.dumps(event))

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = raw_ws.recv(timeout=remaining)
                msg = json.loads(raw)
                if msg.get("event") == "code_panel_run":
                    assert msg["data"]["code"] == "move_to(10, 64, 20)"
                    return
            except Exception:
                break
        # Bridge broadcasts to all ws.clients; sender should receive it back
        pytest.fail("Code panel event not relayed back")

    @needs_player
    def test_block_placed_event(self, raw_ws):
        """block_placed events fire when the tracked player places blocks.

        Requires a player in the world to manually place a block.
        This test configures tracking and waits for a block_placed event.
        """
        _send_cmd(raw_ws, "configure", {"track_player": PLAYER_NAME})

        # Wait up to 30s for the player to place a block
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                raw = raw_ws.recv(timeout=remaining)
                msg = json.loads(raw)
                if msg.get("event") == "block_placed":
                    assert "position" in msg["data"]
                    assert "block_type" in msg["data"]
                    assert msg["data"]["player"] == PLAYER_NAME
                    return
            except Exception:
                break
        pytest.skip("No block_placed event received (player may not have placed a block)")


# ============================================================
# 8. Cancel
# ============================================================


class TestCancel:
    def test_cancel_noop_when_idle(self, raw_ws):
        """Cancel when nothing is running returns cancelling: null."""
        cmd_id, resp = _send_cmd(raw_ws, "cancel")
        assert resp["success"] is True
        assert resp["data"]["cancelling"] is None

    def test_cancel_mid_build(self, raw_ws):
        """Start a long build_wall, cancel mid-execution, verify partial data."""
        # Check inventory for blocks
        _, inv_resp = _send_cmd(raw_ws, "get_inventory")
        if not inv_resp["success"]:
            pytest.skip("Could not query inventory")

        items = inv_resp["data"].get("items", [])
        block_item = next((i for i in items if i["count"] >= 20), None)
        if not block_item:
            pytest.skip("Need 20+ blocks in inventory for cancel test")

        # Get current position for placement
        _, pos_resp = _send_cmd(raw_ws, "get_position")
        bx = pos_resp["data"]["x"] + 10
        by = pos_resp["data"]["y"]
        bz = pos_resp["data"]["z"] + 10

        # Start a large build_wall (10 wide x 2 high = 20 blocks)
        build_id = str(uuid.uuid4())
        raw_ws.send(json.dumps({
            "type": "command",
            "id": build_id,
            "action": "build_wall",
            "args": {
                "x": bx, "y": by, "z": bz,
                "direction": "east",
                "length": 10, "height": 2,
                "block_type": block_item["name"],
            },
        }))

        # Wait briefly for the build to start placing blocks
        time.sleep(3)

        # Send cancel
        cancel_id, cancel_resp = _send_cmd(raw_ws, "cancel")
        assert cancel_resp["success"] is True
        assert cancel_resp["data"]["cancelling"] == build_id

        # Now collect the build_wall's final response
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            raw = raw_ws.recv(timeout=remaining)
            msg = json.loads(raw)
            if msg.get("type") == "response" and msg.get("id") == build_id:
                assert msg["success"] is False
                assert msg["error"]["code"] == "CANCELLED"
                # Partial data should indicate some blocks were placed
                partial = msg.get("data", {}).get("partial", {})
                assert "blocks_placed" in partial
                assert partial["blocks_placed"] > 0
                assert partial["blocks_placed"] < 20
                return

        pytest.fail("No cancellation response received for build_wall")


# ============================================================
# 9. Protocol Compliance
# ============================================================


class TestProtocolCompliance:
    def test_response_id_matches_command_id(self, raw_ws):
        """Response ID exactly matches the command ID sent."""
        cmd_id, resp = _send_cmd(raw_ws, "get_position")
        assert resp["id"] == cmd_id

    def test_response_has_required_fields(self, raw_ws):
        """Successful response has type, id, success, data."""
        cmd_id, resp = _send_cmd(raw_ws, "get_position")
        assert resp["type"] == "response"
        assert resp["id"] == cmd_id
        assert resp["success"] is True
        assert "data" in resp
        assert isinstance(resp["data"], dict)

    def test_error_response_structure(self, raw_ws):
        """Error response includes error.code, error.message, error.details."""
        cmd_id, resp = _send_cmd(raw_ws, "totally_fake_action")
        assert resp["success"] is False
        err = resp["error"]
        assert "code" in err
        assert "message" in err
        assert "details" in err
        assert err["code"] == "UNKNOWN_ACTION"

    def test_busy_rejection(self, raw_ws):
        """Second command while first is executing gets BUSY rejection."""
        # Start a slow move_to (unreachable coordinates)
        cmd1_id = str(uuid.uuid4())
        raw_ws.send(json.dumps({
            "type": "command",
            "id": cmd1_id,
            "action": "move_to",
            "args": {"x": 99999, "y": 64, "z": 99999},
        }))

        # Brief pause to let the bridge start processing
        time.sleep(0.3)

        # Send a second command — should be rejected as BUSY
        cmd2_id, resp2 = _send_cmd(raw_ws, "get_position")
        assert resp2["success"] is False
        assert resp2["error"]["code"] == "BUSY"
        assert resp2["error"]["details"]["busy_with"] == cmd1_id

        # Clean up: cancel the first command
        _send_cmd(raw_ws, "cancel")

        # Drain the move_to response
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            try:
                raw = raw_ws.recv(timeout=2)
                msg = json.loads(raw)
                if msg.get("type") == "response" and msg.get("id") == cmd1_id:
                    break
            except Exception:
                break

    def test_progress_references_correct_id(self, raw_ws):
        """Progress messages carry the same ID as the originating command."""
        # Check inventory for enough blocks
        _, inv_resp = _send_cmd(raw_ws, "get_inventory")
        items = inv_resp["data"].get("items", [])
        block_item = next((i for i in items if i["count"] >= 10), None)
        if not block_item:
            pytest.skip("Need 10+ blocks in inventory for progress test")

        _, pos_resp = _send_cmd(raw_ws, "get_position")
        bx = pos_resp["data"]["x"] + 15
        by = pos_resp["data"]["y"]
        bz = pos_resp["data"]["z"] + 15

        # Start build_wall (5x2 = 10 blocks)
        build_id = str(uuid.uuid4())
        raw_ws.send(json.dumps({
            "type": "command",
            "id": build_id,
            "action": "build_wall",
            "args": {
                "x": bx, "y": by, "z": bz,
                "direction": "east", "length": 5, "height": 2,
                "block_type": block_item["name"],
            },
        }))

        # Collect all messages until the final response
        progress_ids: list[str] = []
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                raw = raw_ws.recv(timeout=5)
                msg = json.loads(raw)
                if msg.get("type") == "progress":
                    progress_ids.append(msg["id"])
                elif msg.get("type") == "response" and msg.get("id") == build_id:
                    break
            except Exception:
                break

        # Every progress message should reference the build command
        for pid in progress_ids:
            assert pid == build_id

    def test_invalid_json_returns_error(self, raw_ws):
        """Malformed JSON gets an error response."""
        raw_ws.send("this is not json{{{")

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            raw = raw_ws.recv(timeout=remaining)
            msg = json.loads(raw)
            if msg.get("type") == "response":
                assert msg["success"] is False
                assert msg["error"]["code"] == "INVALID_MESSAGE"
                return
        pytest.fail("No error response for invalid JSON")

    def test_multiple_commands_sequential(self, raw_ws):
        """Multiple commands sent sequentially each get correct responses."""
        ids_and_actions = []
        for action in ("get_position", "get_inventory", "get_block"):
            args = {"x": 0, "y": 64, "z": 0} if action == "get_block" else {}
            cmd_id, resp = _send_cmd(raw_ws, action, args)
            ids_and_actions.append((cmd_id, action, resp))

        for cmd_id, action, resp in ids_and_actions:
            assert resp["id"] == cmd_id
            assert resp["success"] is True
