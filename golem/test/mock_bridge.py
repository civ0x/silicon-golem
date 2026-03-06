"""Mock WebSocket bridge server for testing the Golem SDK.

Accepts WebSocket connections and responds to commands with canned responses.
Can be configured to return errors or simulate progress for compound actions.
"""

import asyncio
import json
import threading
from typing import Any

import websockets
import websockets.server


class MockBridge:
    """A mock Mineflayer bridge that runs a WebSocket server for testing.

    Usage:
        bridge = MockBridge(port=3099)
        bridge.start()
        # ... run tests ...
        bridge.stop()
    """

    def __init__(self, port: int = 3099) -> None:
        self.port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: websockets.server.WebSocketServer | None = None
        self._started = threading.Event()
        self._clients: list[websockets.server.ServerConnection] = []

        # Configurable responses: action -> response data or error
        self._responses: dict[str, dict[str, Any]] = {}
        self._errors: dict[str, dict[str, Any]] = {}
        self._progress: dict[str, list[dict[str, Any]]] = {}

        # Record of received commands for assertions
        self.received_commands: list[dict[str, Any]] = []

        self._set_default_responses()

    def _set_default_responses(self) -> None:
        """Set up default successful responses for all actions."""
        self._responses = {
            "move_to": {"reached": True, "final_position": {"x": 10, "y": 64, "z": 20}},
            "move_to_player": {"reached": True, "final_position": {"x": 5, "y": 64, "z": 5}},
            "place_block": {"placed": True},
            "dig_block": {"broken": True, "block_type": "cobblestone"},
            "dig_area": {"blocks_broken": 8, "block_types": {"cobblestone": 5, "dirt": 3}},
            "craft": {"crafted": 1},
            "give": {"given": 1},
            "equip": {"equipped": True},
            "get_position": {"x": 100, "y": 64, "z": -200},
            "get_player_position": {"x": 105, "y": 64, "z": -195},
            "find_blocks": {"positions": [{"x": 10, "y": 60, "z": 20}, {"x": 12, "y": 61, "z": 22}]},
            "find_player": {"x": 105, "y": 64, "z": -195},
            "get_inventory": {"items": [{"name": "cobblestone", "count": 42}, {"name": "iron_ingot", "count": 3}]},
            "get_block": {"block_type": "cobblestone"},
            "say": {"sent": True},
            "collect": {"collected": 10},
            "build_line": {"blocks_placed": 5},
            "build_wall": {"blocks_placed": 20},
            "configure": {"configured": True, "tracked_player_found": True},
            "disconnect": {"disconnected": True},
        }

    def set_response(self, action: str, data: dict[str, Any]) -> None:
        """Configure the response for a specific action."""
        self._responses[action] = data
        self._errors.pop(action, None)

    def set_error(self, action: str, code: str, message: str, details: dict | None = None) -> None:
        """Configure an error response for a specific action."""
        self._errors[action] = {
            "code": code,
            "message": message,
            "details": details or {},
        }

    def set_progress(self, action: str, progress_messages: list[dict[str, Any]]) -> None:
        """Configure progress messages to send before the final response."""
        self._progress[action] = progress_messages

    def set_find_player_none(self) -> None:
        """Configure find_player to return null data (player not found, but success)."""
        self._responses["find_player"] = None  # type: ignore[assignment]

    def clear_errors(self) -> None:
        """Clear all configured errors."""
        self._errors.clear()

    def start(self) -> None:
        """Start the mock bridge server."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True, name="mock-bridge")
        self._thread.start()
        self._started.wait(timeout=5)

    def stop(self) -> None:
        """Stop the mock bridge server."""
        if self._loop is None:
            return
        if self._server is not None:
            self._server.close()
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        self._server = None
        self._clients.clear()
        self.received_commands.clear()

    async def send_event(self, event: str, data: dict[str, Any]) -> None:
        """Send an unsolicited event to all connected clients."""
        msg = json.dumps({"type": "event", "event": event, "data": data})
        for client in self._clients:
            try:
                await client.send(msg)
            except Exception:
                pass

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        assert self._loop is not None
        try:
            self._loop.run_until_complete(self._serve())
        except RuntimeError:
            pass  # Event loop stopped during shutdown — expected

    async def _serve(self) -> None:
        assert self._loop is not None
        self._server = await websockets.serve(
            self._handle_client,
            "localhost",
            self.port,
        )
        self._started.set()
        # Run until stopped
        try:
            await asyncio.Future()  # run forever
        except asyncio.CancelledError:
            pass

    async def _handle_client(self, ws: websockets.server.ServerConnection) -> None:
        self._clients.append(ws)
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("type") == "command":
                    self.received_commands.append(msg)
                    await self._handle_command(ws, msg)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.remove(ws)

    async def _handle_command(self, ws: websockets.server.ServerConnection, msg: dict) -> None:
        cmd_id = msg["id"]
        action = msg["action"]

        # Send progress messages first (if configured)
        if action in self._progress:
            for progress_data in self._progress[action]:
                progress_msg = {
                    "type": "progress",
                    "id": cmd_id,
                    "data": progress_data,
                }
                await ws.send(json.dumps(progress_msg))
                await asyncio.sleep(0.01)  # small delay to simulate real timing

        # Check for configured error
        if action in self._errors:
            response = {
                "type": "response",
                "id": cmd_id,
                "success": False,
                "data": None,
                "error": self._errors[action],
            }
        elif action in self._responses:
            response = {
                "type": "response",
                "id": cmd_id,
                "success": True,
                "data": self._responses[action],
                "error": None,
            }
        else:
            response = {
                "type": "response",
                "id": cmd_id,
                "success": False,
                "data": None,
                "error": {"code": "UNKNOWN_ACTION", "message": f"Unknown action: {action}", "details": {}},
            }

        await ws.send(json.dumps(response))
