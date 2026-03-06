"""Error types for the Golem SDK.

Translates bridge error codes into Python exceptions with human-readable messages.
Internal module — not exported via `from golem import *`.
"""


class GolemError(Exception):
    """Base exception for all Golem SDK errors."""

    def __init__(self, message: str, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class PathfindingError(GolemError):
    """Bot couldn't reach the target location."""
    pass


class InventoryError(GolemError):
    """Item not available in inventory."""
    pass


class BlockError(GolemError):
    """Block interaction failed (placement, digging, invalid name)."""
    pass


class CraftingError(GolemError):
    """Crafting operation failed."""
    pass


class PlayerError(GolemError):
    """Player not found or not nearby."""
    pass


class ConnectionError(GolemError):
    """WebSocket connection issue."""
    pass


class TimeoutError(GolemError):
    """Command timed out waiting for bridge response."""
    pass


class CancelledError(GolemError):
    """Operation was cancelled."""
    pass


# Bridge error code -> (exception class, human-readable message template)
_ERROR_MAP: dict[str, tuple[type[GolemError], str]] = {
    "PATHFINDER_TIMEOUT": (PathfindingError, "I couldn't find a way there in time"),
    "PATHFINDER_NO_PATH": (PathfindingError, "I can't find a path to get there"),
    "PLAYER_NOT_FOUND": (PlayerError, "I can't find a player named '{name}'"),
    "ITEM_NOT_IN_INVENTORY": (InventoryError, "I don't have any {item}"),
    "BLOCK_NOT_REACHABLE": (BlockError, "I can't reach that block"),
    "BLOCK_NOT_FOUND": (BlockError, "There's no block there"),
    "NO_BLOCK_AT_POSITION": (BlockError, "That spot is empty (just air)"),
    "INVALID_BLOCK_NAME": (BlockError, "I don't know what '{name}' is"),
    "INVALID_DIRECTION": (BlockError, "I don't understand that direction"),
    "PLACEMENT_FAILED": (BlockError, "I couldn't place the block there"),
    "REGION_TOO_LARGE": (BlockError, "That area is too big for me to dig all at once"),
    "UNKNOWN_ITEM": (CraftingError, "I don't know what '{item}' is"),
    "MISSING_MATERIALS": (CraftingError, "I don't have enough materials to craft that"),
    "NO_CRAFTING_TABLE": (CraftingError, "I need a crafting table nearby to make that"),
    "RECIPE_NOT_FOUND": (CraftingError, "I don't know how to craft that"),
    "NO_PLAYER_NEARBY": (PlayerError, "There's no player close enough"),
    "NO_BLOCKS_FOUND": (BlockError, "I couldn't find any of those blocks nearby"),
    "COLLECTION_INTERRUPTED": (BlockError, "I had to stop collecting early"),
    "CANCELLED": (CancelledError, "I stopped what I was doing"),
}


def from_bridge_error(error: dict) -> GolemError:
    """Convert a bridge error response into the appropriate GolemError subclass.

    Args:
        error: The error object from a bridge response, containing
               'code', 'message', and optionally 'details'.

    Returns:
        A GolemError subclass instance with a human-readable message.
    """
    code = error.get("code", "UNKNOWN")
    details = error.get("details", {})

    if code in _ERROR_MAP:
        exc_class, template = _ERROR_MAP[code]
        # Build format kwargs from details plus the error code
        fmt = {**details, "name": details.get("name", "???"), "item": details.get("item", "that")}
        try:
            message = template.format(**fmt)
        except KeyError:
            message = template
        # Append suggestion if present
        suggestion = details.get("suggestion")
        if suggestion:
            message += f" — did you mean '{suggestion}'?"
    else:
        exc_class = GolemError
        message = error.get("message", f"Something went wrong (error: {code})")

    return exc_class(message, code=code, details=details)
