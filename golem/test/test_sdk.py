"""Tests for the Golem SDK against a mock bridge server."""

import pytest

from golem.connection import reset_connection
from golem.errors import (
    BlockError,
    CraftingError,
    GolemError,
    InventoryError,
    PathfindingError,
    PlayerError,
    from_bridge_error,
)
from golem.sdk import (
    Item,
    Position,
    __all__,
    build_line,
    build_wall,
    collect,
    connect,
    craft,
    dig_area,
    dig_block,
    disconnect,
    equip,
    find_blocks,
    find_player,
    get_block,
    get_inventory,
    get_player_position,
    get_position,
    give,
    move_to,
    move_to_player,
    place_block,
    say,
)
from golem.test.mock_bridge import MockBridge

# Use a unique port to avoid conflicts
MOCK_PORT = 3099


@pytest.fixture(scope="module")
def bridge():
    """Start a mock bridge server for the entire test module."""
    b = MockBridge(port=MOCK_PORT)
    b.start()
    yield b
    b.stop()


@pytest.fixture(autouse=True)
def sdk_connection(bridge):
    """Connect the SDK to the mock bridge before each test, disconnect after."""
    reset_connection()
    connect("localhost", MOCK_PORT)
    yield
    disconnect()
    bridge.clear_errors()
    bridge._set_default_responses()
    bridge._progress.clear()
    bridge.received_commands.clear()


# --- __all__ export list ---


class TestExportList:
    """Verify __all__ contains exactly the right names."""

    EXPECTED_EXPORTS = {
        # Types
        "Position", "Item",
        # Movement
        "move_to", "move_to_player",
        # Block interaction
        "place_block", "dig_block", "dig_area",
        # Crafting and items
        "craft", "give", "equip",
        # Observation
        "get_position", "get_player_position", "find_blocks",
        "find_player", "get_inventory", "get_block",
        # Communication
        "say",
        # Compound actions
        "collect", "build_line", "build_wall",
    }

    def test_all_contains_expected(self):
        assert set(__all__) == self.EXPECTED_EXPORTS

    def test_connect_not_exported(self):
        assert "connect" not in __all__

    def test_disconnect_not_exported(self):
        assert "disconnect" not in __all__

    def test_golem_error_not_exported(self):
        assert "GolemError" not in __all__


# --- Position and Item types ---


class TestPosition:
    def test_attributes(self):
        pos = Position(10.7, 64.2, -200.9)
        assert pos.x == 11
        assert pos.y == 64
        assert pos.z == -201

    def test_rounds_to_int(self):
        pos = Position(10.5, 64.5, -200.5)
        # Python rounds half to even
        assert isinstance(pos.x, int)
        assert isinstance(pos.y, int)
        assert isinstance(pos.z, int)

    def test_repr(self):
        pos = Position(10, 64, -200)
        assert repr(pos) == "Position(x=10, y=64, z=-200)"

    def test_equality(self):
        assert Position(10, 64, -200) == Position(10, 64, -200)
        assert Position(10, 64, -200) != Position(10, 64, -201)

    def test_int_passthrough(self):
        pos = Position(10, 64, -200)
        assert pos.x == 10
        assert pos.y == 64
        assert pos.z == -200


class TestItem:
    def test_attributes(self):
        item = Item("cobblestone", 42)
        assert item.name == "cobblestone"
        assert item.count == 42

    def test_repr(self):
        item = Item("iron_ingot", 3)
        assert repr(item) == "3x iron_ingot"

    def test_equality(self):
        assert Item("cobblestone", 42) == Item("cobblestone", 42)
        assert Item("cobblestone", 42) != Item("cobblestone", 10)


# --- Movement ---


class TestMoveTo:
    def test_success(self, bridge):
        result = move_to(10, 64, 20)
        assert result is True

    def test_sends_correct_command(self, bridge):
        move_to(10, 64, 20)
        cmd = bridge.received_commands[-1]
        assert cmd["action"] == "move_to"
        assert cmd["args"] == {"x": 10, "y": 64, "z": 20}

    def test_timeout_returns_false(self, bridge):
        bridge.set_response("move_to", {"reached": False, "final_position": {"x": 5, "y": 64, "z": 10}})
        result = move_to(10, 64, 20)
        assert result is False

    def test_pathfinder_error(self, bridge):
        bridge.set_error("move_to", "PATHFINDER_NO_PATH", "No path exists")
        with pytest.raises(PathfindingError):
            move_to(10, 64, 20)


class TestMoveToPlayer:
    def test_success(self, bridge):
        result = move_to_player("Alex")
        assert result is True

    def test_sends_correct_args(self, bridge):
        move_to_player("Alex", distance=5)
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {"name": "Alex", "distance": 5}

    def test_default_distance(self, bridge):
        move_to_player("Alex")
        cmd = bridge.received_commands[-1]
        assert cmd["args"]["distance"] == 2

    def test_player_not_found(self, bridge):
        bridge.set_error("move_to_player", "PLAYER_NOT_FOUND", "Player not found")
        with pytest.raises(PlayerError):
            move_to_player("Nobody")


# --- Block Interaction ---


class TestPlaceBlock:
    def test_success(self, bridge):
        result = place_block(10, 64, 20, "cobblestone")
        assert result is True

    def test_sends_correct_args(self, bridge):
        place_block(10, 64, 20, "stone_bricks")
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {"x": 10, "y": 64, "z": 20, "block_type": "stone_bricks"}

    def test_invalid_block_name(self, bridge):
        bridge.set_error(
            "place_block", "INVALID_BLOCK_NAME",
            "Invalid block name", {"name": "stoone", "suggestion": "stone"},
        )
        with pytest.raises(BlockError) as exc_info:
            place_block(10, 64, 20, "stoone")
        assert "stone" in str(exc_info.value)

    def test_not_in_inventory(self, bridge):
        bridge.set_error("place_block", "ITEM_NOT_IN_INVENTORY", "Not in inventory")
        with pytest.raises(InventoryError):
            place_block(10, 64, 20, "diamond_block")


class TestDigBlock:
    def test_returns_block_type(self, bridge):
        result = dig_block(10, 64, 20)
        assert result == "cobblestone"

    def test_sends_correct_args(self, bridge):
        dig_block(5, 60, -10)
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {"x": 5, "y": 60, "z": -10}

    def test_no_block_error(self, bridge):
        bridge.set_error("dig_block", "NO_BLOCK_AT_POSITION", "Position is air")
        with pytest.raises(BlockError):
            dig_block(10, 64, 20)


class TestDigArea:
    def test_returns_count(self, bridge):
        result = dig_area(0, 60, 0, 3, 62, 3)
        assert result == 8

    def test_sends_correct_args(self, bridge):
        dig_area(0, 60, 0, 3, 62, 3)
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {"x1": 0, "y1": 60, "z1": 0, "x2": 3, "y2": 62, "z2": 3}

    def test_progress_callback(self, bridge):
        bridge.set_progress("dig_area", [
            {"blocks_broken": 3, "blocks_total": 8},
            {"blocks_broken": 6, "blocks_total": 8},
        ])
        progress_updates = []
        dig_area(0, 60, 0, 3, 62, 3, on_progress=lambda p: progress_updates.append(p))
        assert len(progress_updates) == 2
        assert progress_updates[0]["blocks_broken"] == 3

    def test_region_too_large(self, bridge):
        bridge.set_error("dig_area", "REGION_TOO_LARGE", "Too many blocks")
        with pytest.raises(BlockError):
            dig_area(0, 0, 0, 100, 100, 100)


# --- Crafting and Items ---


class TestCraft:
    def test_returns_count(self, bridge):
        result = craft("oak_planks", 4)
        assert result == 1

    def test_default_count(self, bridge):
        craft("stick")
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {"item_name": "stick", "count": 1}

    def test_missing_materials(self, bridge):
        bridge.set_error("craft", "MISSING_MATERIALS", "Not enough", {"missing": {"iron_ingot": 2}})
        with pytest.raises(CraftingError):
            craft("iron_pickaxe")


class TestGive:
    def test_returns_count(self, bridge):
        result = give("cobblestone", 10)
        assert result == 1

    def test_sends_correct_args(self, bridge):
        give("diamond", 3)
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {"item_name": "diamond", "count": 3}


class TestEquip:
    def test_success(self, bridge):
        result = equip("diamond_pickaxe")
        assert result is True

    def test_not_in_inventory(self, bridge):
        bridge.set_error("equip", "ITEM_NOT_IN_INVENTORY", "Not in inventory")
        with pytest.raises(InventoryError):
            equip("netherite_sword")


# --- Observation ---


class TestGetPosition:
    def test_returns_position(self, bridge):
        pos = get_position()
        assert isinstance(pos, Position)
        assert pos.x == 100
        assert pos.y == 64
        assert pos.z == -200

    def test_position_attributes(self, bridge):
        pos = get_position()
        # The kid writes pos.x, pos.y, pos.z
        assert hasattr(pos, "x")
        assert hasattr(pos, "y")
        assert hasattr(pos, "z")


class TestGetPlayerPosition:
    def test_returns_position(self, bridge):
        pos = get_player_position("Alex")
        assert isinstance(pos, Position)
        assert pos.x == 105

    def test_sends_name(self, bridge):
        get_player_position("Steve")
        cmd = bridge.received_commands[-1]
        assert cmd["args"]["name"] == "Steve"

    def test_player_not_found(self, bridge):
        bridge.set_error("get_player_position", "PLAYER_NOT_FOUND", "Not found")
        with pytest.raises(PlayerError):
            get_player_position("Nobody")


class TestFindBlocks:
    def test_returns_positions(self, bridge):
        positions = find_blocks("diamond_ore", 2)
        assert len(positions) == 2
        assert all(isinstance(p, Position) for p in positions)
        assert positions[0] == Position(10, 60, 20)

    def test_default_count(self, bridge):
        find_blocks("iron_ore")
        cmd = bridge.received_commands[-1]
        assert cmd["args"]["count"] == 1


class TestFindPlayer:
    def test_returns_position(self, bridge):
        pos = find_player("Alex")
        assert isinstance(pos, Position)
        assert pos.x == 105

    def test_returns_none_when_not_found(self, bridge):
        bridge.set_find_player_none()
        pos = find_player("Nobody")
        assert pos is None


class TestGetInventory:
    def test_returns_items(self, bridge):
        inv = get_inventory()
        assert len(inv) == 2
        assert all(isinstance(i, Item) for i in inv)
        assert inv[0].name == "cobblestone"
        assert inv[0].count == 42
        assert inv[1].name == "iron_ingot"
        assert inv[1].count == 3


class TestGetBlock:
    def test_returns_block_type(self, bridge):
        result = get_block(10, 64, 20)
        assert result == "cobblestone"

    def test_air(self, bridge):
        bridge.set_response("get_block", {"block_type": "air"})
        result = get_block(10, 100, 20)
        assert result == "air"


# --- Communication ---


class TestSay:
    def test_success(self, bridge):
        result = say("Hello!")
        assert result is True

    def test_sends_message(self, bridge):
        say("I'm here!")
        cmd = bridge.received_commands[-1]
        assert cmd["args"]["message"] == "I'm here!"


# --- Compound Actions ---


class TestCollect:
    def test_returns_count(self, bridge):
        result = collect("oak_log", 10)
        assert result == 10

    def test_progress_callback(self, bridge):
        bridge.set_progress("collect", [
            {"collected_so_far": 3, "target": 10},
            {"collected_so_far": 7, "target": 10},
        ])
        updates = []
        collect("oak_log", 10, on_progress=lambda p: updates.append(p))
        assert len(updates) == 2
        assert updates[1]["collected_so_far"] == 7


class TestBuildLine:
    def test_returns_count(self, bridge):
        result = build_line(10, 64, 20, "east", 5, "cobblestone")
        assert result == 5

    def test_sends_correct_args(self, bridge):
        build_line(10, 64, 20, "north", 10, "stone_bricks")
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {
            "x": 10, "y": 64, "z": 20,
            "direction": "north", "length": 10,
            "block_type": "stone_bricks",
        }

    def test_progress_callback(self, bridge):
        bridge.set_progress("build_line", [
            {"blocks_placed": 2, "blocks_total": 5},
            {"blocks_placed": 4, "blocks_total": 5},
        ])
        updates = []
        build_line(10, 64, 20, "east", 5, "cobblestone", on_progress=lambda p: updates.append(p))
        assert len(updates) == 2

    def test_invalid_direction(self, bridge):
        bridge.set_error("build_line", "INVALID_DIRECTION", "Bad direction")
        with pytest.raises(BlockError):
            build_line(10, 64, 20, "northwest", 5, "cobblestone")


class TestBuildWall:
    def test_returns_count(self, bridge):
        result = build_wall(10, 64, 20, "east", 5, 4, "cobblestone")
        assert result == 20

    def test_sends_correct_args(self, bridge):
        build_wall(0, 64, 0, "south", 8, 3, "stone_bricks")
        cmd = bridge.received_commands[-1]
        assert cmd["args"] == {
            "x": 0, "y": 64, "z": 0,
            "direction": "south", "length": 8, "height": 3,
            "block_type": "stone_bricks",
        }


# --- Error Translation ---


class TestErrorTranslation:
    def test_pathfinder_timeout(self):
        err = from_bridge_error({"code": "PATHFINDER_TIMEOUT", "message": "timeout", "details": {}})
        assert isinstance(err, PathfindingError)
        assert err.code == "PATHFINDER_TIMEOUT"

    def test_invalid_block_with_suggestion(self):
        err = from_bridge_error({
            "code": "INVALID_BLOCK_NAME",
            "message": "bad name",
            "details": {"name": "stoone", "suggestion": "stone"},
        })
        assert isinstance(err, BlockError)
        assert "stoone" in str(err)
        assert "stone" in str(err)

    def test_missing_materials_with_details(self):
        err = from_bridge_error({
            "code": "MISSING_MATERIALS",
            "message": "not enough",
            "details": {"missing": {"iron_ingot": 2}},
        })
        assert isinstance(err, CraftingError)
        assert err.details["missing"]["iron_ingot"] == 2

    def test_unknown_error_code(self):
        err = from_bridge_error({
            "code": "SOMETHING_NEW",
            "message": "unexpected error",
            "details": {},
        })
        assert isinstance(err, GolemError)
        assert "unexpected error" in str(err)

    def test_cancelled(self):
        err = from_bridge_error({"code": "CANCELLED", "message": "cancelled", "details": {}})
        from golem.errors import CancelledError
        assert isinstance(err, CancelledError)


# --- Connection Lifecycle ---


class TestConnectionLifecycle:
    def test_command_sends_uuid(self, bridge):
        get_position()
        cmd = bridge.received_commands[-1]
        # id should be a UUID string
        assert len(cmd["id"]) == 36  # UUID format: 8-4-4-4-12
        assert cmd["id"].count("-") == 4

    def test_command_type_field(self, bridge):
        get_position()
        cmd = bridge.received_commands[-1]
        assert cmd["type"] == "command"


# --- Integration: Kid-style code patterns ---


class TestKidCodePatterns:
    """Test the patterns from GOLEM_SDK.md that a kid would actually write."""

    def test_pattern1_simple_action(self, bridge):
        """Kid says: 'Come here'"""
        player_pos = get_player_position("Alex")
        move_to(player_pos.x, player_pos.y, player_pos.z)
        say("I'm here! What do you need?")
        # Verify the move used the position values
        move_cmd = bridge.received_commands[-2]
        assert move_cmd["args"]["x"] == 105

    def test_pattern2_variables_as_knobs(self, bridge):
        """Kid says: 'Build me a cobblestone wall, 5 blocks long'"""
        pos = get_position()
        block = "cobblestone"
        place_block(pos.x + 1, pos.y, pos.z, block)
        place_block(pos.x + 2, pos.y, pos.z, block)
        # Verify coordinates are offset correctly
        cmds = [c for c in bridge.received_commands if c["action"] == "place_block"]
        assert cmds[-2]["args"]["x"] == 101
        assert cmds[-1]["args"]["x"] == 102
        assert cmds[-1]["args"]["block_type"] == "cobblestone"

    def test_pattern3_observation(self, bridge):
        """Kid says: 'What blocks are near me?'"""
        pos = get_position()
        ground = get_block(pos.x, pos.y - 1, pos.z)
        assert isinstance(ground, str)
        say("You're standing on " + ground)

    def test_position_arithmetic(self, bridge):
        """The kid uses pos.x + 1 style arithmetic."""
        pos = get_position()
        new_x = pos.x + 5
        new_y = pos.y - 1
        new_z = pos.z * 1  # silly but valid
        assert new_x == 105
        assert new_y == 63
        assert new_z == -200

    def test_inventory_iteration(self, bridge):
        """At Level 2+, the kid iterates inventory."""
        inv = get_inventory()
        names = [item.name for item in inv]
        assert "cobblestone" in names
        assert "iron_ingot" in names
