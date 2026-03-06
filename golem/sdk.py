"""Silicon Golem SDK — the Python API surface the kid sees.

Usage in generated code:
    from golem import *

Every function is synchronous from the caller's perspective.
Internally, commands are sent over WebSocket to the Mineflayer bridge.
"""

from typing import Callable

from .connection import get_connection
from .errors import GolemError  # noqa: F401 — re-exported for orchestrator use


class Position:
    """A position in the Minecraft world."""

    def __init__(self, x: float | int, y: float | int, z: float | int):
        self.x = round(x)
        self.y = round(y)
        self.z = round(z)

    def __repr__(self) -> str:
        return f"Position(x={self.x}, y={self.y}, z={self.z})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return NotImplemented
        return self.x == other.x and self.y == other.y and self.z == other.z


class Item:
    """An item in the bot's inventory."""

    def __init__(self, name: str, count: int):
        self.name = name
        self.count = count

    def __repr__(self) -> str:
        return f"{self.count}x {self.name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Item):
            return NotImplemented
        return self.name == other.name and self.count == other.count


# --- SDK Functions (exported via __all__) ---


def move_to(x: int, y: int, z: int) -> bool:
    """Walk to the specified coordinates.

    Returns True if reached, False if timed out or no path found.
    """
    conn = get_connection()
    data = conn.send_command("move_to", {"x": x, "y": y, "z": z})
    return bool(data.get("reached", False))


def move_to_player(name: str, distance: int = 2) -> bool:
    """Walk to the named player.

    Returns True if reached, False if timed out.
    """
    conn = get_connection()
    data = conn.send_command("move_to_player", {"name": name, "distance": distance})
    return bool(data.get("reached", False))


def place_block(x: int, y: int, z: int, block_type: str) -> bool:
    """Place a block at the given coordinates.

    Returns True if placed successfully.
    """
    conn = get_connection()
    data = conn.send_command(
        "place_block", {"x": x, "y": y, "z": z, "block_type": block_type}
    )
    return bool(data.get("placed", False))


def dig_block(x: int, y: int, z: int) -> str:
    """Break the block at the given coordinates.

    Returns the block type that was broken.
    """
    conn = get_connection()
    data = conn.send_command("dig_block", {"x": x, "y": y, "z": z})
    return str(data.get("block_type", "unknown"))


def dig_area(
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    on_progress: Callable[[dict], None] | None = None,
) -> int:
    """Break all blocks in a rectangular region.

    Returns the number of blocks broken.
    """
    conn = get_connection()
    data = conn.send_command(
        "dig_area",
        {"x1": x1, "y1": y1, "z1": z1, "x2": x2, "y2": y2, "z2": z2},
        on_progress=on_progress,
    )
    return int(data.get("blocks_broken", 0))


def craft(item_name: str, count: int = 1) -> int:
    """Craft the specified item.

    Returns the number of items successfully crafted.
    """
    conn = get_connection()
    data = conn.send_command("craft", {"item_name": item_name, "count": count})
    return int(data.get("crafted", 0))


def give(item_name: str, count: int = 1) -> int:
    """Give items to the nearest player.

    Returns the number of items given.
    """
    conn = get_connection()
    data = conn.send_command("give", {"item_name": item_name, "count": count})
    return int(data.get("given", 0))


def equip(item_name: str) -> bool:
    """Hold the specified item.

    Returns True if equipped successfully.
    """
    conn = get_connection()
    data = conn.send_command("equip", {"item_name": item_name})
    return bool(data.get("equipped", False))


def get_position() -> Position:
    """Get the bot's current position.

    Returns a Position with .x, .y, .z attributes.
    """
    conn = get_connection()
    data = conn.send_command("get_position", {})
    return Position(data.get("x", 0), data.get("y", 0), data.get("z", 0))


def get_player_position(name: str) -> Position:
    """Get a player's current position.

    Returns a Position with .x, .y, .z attributes.
    """
    conn = get_connection()
    data = conn.send_command("get_player_position", {"name": name})
    return Position(data.get("x", 0), data.get("y", 0), data.get("z", 0))


def find_blocks(block_type: str, count: int = 1) -> list[Position]:
    """Find nearby blocks of the specified type.

    Returns a list of Position objects.
    """
    conn = get_connection()
    data = conn.send_command(
        "find_blocks", {"block_type": block_type, "count": count}
    )
    positions = data.get("positions", [])
    return [Position(p["x"], p["y"], p["z"]) for p in positions]


def find_player(name: str) -> Position | None:
    """Find a player's position.

    Returns a Position, or None if the player is not found.
    """
    conn = get_connection()
    data = conn.send_command("find_player", {"name": name})
    if data is None:
        return None
    return Position(data.get("x", 0), data.get("y", 0), data.get("z", 0))


def get_inventory() -> list[Item]:
    """Get the bot's inventory.

    Returns a list of Item objects with .name and .count attributes.
    """
    conn = get_connection()
    data = conn.send_command("get_inventory", {})
    items = data.get("items", [])
    return [Item(i["name"], i["count"]) for i in items]


def get_block(x: int, y: int, z: int) -> str:
    """Get the block type at the given coordinates.

    Returns the block type string, or "air" for empty space.
    """
    conn = get_connection()
    data = conn.send_command("get_block", {"x": x, "y": y, "z": z})
    return str(data.get("block_type", "air"))


def say(message: str) -> bool:
    """Send a chat message in-game.

    Returns True if sent successfully.
    """
    conn = get_connection()
    data = conn.send_command("say", {"message": message})
    return bool(data.get("sent", False))


# --- Compound Actions ---


def collect(
    block_type: str,
    count: int,
    on_progress: Callable[[dict], None] | None = None,
) -> int:
    """Find and break blocks of the specified type until count is reached.

    Returns the number actually collected.
    """
    conn = get_connection()
    data = conn.send_command(
        "collect",
        {"block_type": block_type, "count": count},
        on_progress=on_progress,
    )
    return int(data.get("collected", 0))


def build_line(
    x: int, y: int, z: int,
    direction: str,
    length: int,
    block_type: str,
    on_progress: Callable[[dict], None] | None = None,
) -> int:
    """Place blocks in a straight line.

    direction: one of "north", "south", "east", "west", "up", "down".
    Returns the number of blocks placed.
    """
    conn = get_connection()
    data = conn.send_command(
        "build_line",
        {
            "x": x, "y": y, "z": z,
            "direction": direction,
            "length": length,
            "block_type": block_type,
        },
        on_progress=on_progress,
    )
    return int(data.get("blocks_placed", 0))


def build_wall(
    x: int, y: int, z: int,
    direction: str,
    length: int,
    height: int,
    block_type: str,
    on_progress: Callable[[dict], None] | None = None,
) -> int:
    """Place blocks in a rectangular wall.

    direction: one of "north", "south", "east", "west".
    Returns the number of blocks placed.
    """
    conn = get_connection()
    data = conn.send_command(
        "build_wall",
        {
            "x": x, "y": y, "z": z,
            "direction": direction,
            "length": length,
            "height": height,
            "block_type": block_type,
        },
        on_progress=on_progress,
    )
    return int(data.get("blocks_placed", 0))


# --- Connection lifecycle (NOT exported — orchestrator only) ---


def connect(host: str = "localhost", port: int = 3001) -> None:
    """Connect to the Mineflayer bridge. Called by the orchestrator, not the kid."""
    get_connection().connect(host, port)


def disconnect() -> None:
    """Disconnect from the Mineflayer bridge. Called by the orchestrator, not the kid."""
    get_connection().disconnect()


# --- Export list ---
# Only SDK functions and types the kid's code uses.
# connect/disconnect are NOT exported — orchestrator calls them directly.

__all__ = [
    # Types
    "Position",
    "Item",
    # Movement
    "move_to",
    "move_to_player",
    # Block interaction
    "place_block",
    "dig_block",
    "dig_area",
    # Crafting and items
    "craft",
    "give",
    "equip",
    # Observation
    "get_position",
    "get_player_position",
    "find_blocks",
    "find_player",
    "get_inventory",
    "get_block",
    # Communication
    "say",
    # Compound actions
    "collect",
    "build_line",
    "build_wall",
]
