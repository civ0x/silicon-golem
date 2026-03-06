"""WebSocket connection management for the Golem SDK.

Internal module — not exported via `from golem import *`.
Handles connecting to the Mineflayer bridge, sending commands,
correlating responses by ID, and routing progress/event messages.
"""

import asyncio
import json
import threading
import uuid
from typing import Any, Callable

import websockets
import websockets.client

from .errors import GolemError, TimeoutError, from_bridge_error


# Default timeouts per action (seconds), from BRIDGE_PROTOCOL.md
_ACTION_TIMEOUTS: dict[str, float] = {
    "move_to": 35,
    "move_to_player": 35,
    "place_block": 10,
    "dig_block": 10,
    "dig_area": 60,
    "craft": 15,
    "give": 10,
    "equip": 10,
    "get_position": 5,
    "get_player_position": 5,
    "find_blocks": 5,
    "find_player": 5,
    "get_inventory": 5,
    "get_block": 5,
    "say": 5,
    "collect": 120,
    "build_line": 60,
    "build_wall": 120,
    "get_world_state": 10,
    "validate_block_name": 5,
    "configure": 5,
    "cancel": 5,
    "disconnect": 5,
}

DEFAULT_TIMEOUT = 30.0


class BridgeConnection:
    """Manages a WebSocket connection to the Mineflayer bridge.

    Runs an asyncio event loop on a background thread. SDK functions
    call `send_command` which is synchronous from the caller's perspective
    but internally dispatches to the async loop.
    """

    def __init__(self) -> None:
        self._ws: websockets.client.ClientConnection | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._connected = threading.Event()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._progress_callbacks: dict[str, Callable[[dict], None]] = {}
        self._event_callback: Callable[[dict], None] | None = None
        self._closing = False

    def connect(self, host: str = "localhost", port: int = 3001) -> None:
        """Connect to the bridge WebSocket server.

        Starts a background thread running the asyncio event loop.
        Blocks until the connection is established.
        """
        if self._loop is not None:
            raise GolemError("Already connected", code="ALREADY_CONNECTED")

        self._closing = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            args=(host, port),
            daemon=True,
            name="golem-bridge",
        )
        self._thread.start()

        if not self._connected.wait(timeout=10):
            self._shutdown()
            raise GolemError(
                f"Could not connect to bridge at ws://{host}:{port}",
                code="CONNECTION_FAILED",
            )

    def disconnect(self) -> None:
        """Disconnect from the bridge."""
        if self._loop is None:
            return
        self._shutdown()

    def send_command(
        self,
        action: str,
        args: dict[str, Any] | None = None,
        on_progress: Callable[[dict], None] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Send a command to the bridge and wait for the response.

        Args:
            action: The bridge action name (e.g., 'place_block').
            args: Action-specific arguments.
            on_progress: Optional callback for progress updates (compound actions).
            timeout: Override the default timeout for this action.

        Returns:
            The response data dict on success.

        Raises:
            GolemError: On bridge errors, timeouts, or connection issues.
        """
        if self._loop is None or self._ws is None:
            raise GolemError("Not connected to bridge", code="NOT_CONNECTED")

        cmd_id = str(uuid.uuid4())
        if timeout is None:
            timeout = _ACTION_TIMEOUTS.get(action, DEFAULT_TIMEOUT)

        future = asyncio.run_coroutine_threadsafe(
            self._send_and_wait(cmd_id, action, args or {}, on_progress, timeout),
            self._loop,
        )

        try:
            return future.result(timeout=timeout + 5)  # extra margin for the outer wait
        except TimeoutError:
            raise
        except GolemError:
            raise
        except Exception as e:
            raise GolemError(f"Command failed: {e}", code="COMMAND_FAILED")

    def set_event_callback(self, callback: Callable[[dict], None] | None) -> None:
        """Set a callback for unsolicited events (player_chat, block_placed, etc.)."""
        self._event_callback = callback

    # --- internal async machinery ---

    def _run_loop(self, host: str, port: int) -> None:
        """Entry point for the background thread."""
        asyncio.set_event_loop(self._loop)
        assert self._loop is not None
        self._loop.run_until_complete(self._connect_and_listen(host, port))

    async def _connect_and_listen(self, host: str, port: int) -> None:
        """Connect to the bridge and listen for messages."""
        assert self._loop is not None
        uri = f"ws://{host}:{port}"
        try:
            async with websockets.connect(uri) as ws:
                self._ws = ws
                self._connected.set()
                await self._listen(ws)
        except Exception:
            self._connected.set()  # unblock connect() even on failure

    async def _listen(self, ws: websockets.client.ClientConnection) -> None:
        """Read messages from the WebSocket and dispatch them."""
        try:
            async for raw in ws:
                if self._closing:
                    break
                msg = json.loads(raw)
                msg_type = msg.get("type")

                if msg_type == "response":
                    self._handle_response(msg)
                elif msg_type == "progress":
                    self._handle_progress(msg)
                elif msg_type == "event":
                    self._handle_event(msg)
        except websockets.exceptions.ConnectionClosed:
            if not self._closing:
                self._fail_pending("Connection to bridge lost")

    def _handle_response(self, msg: dict) -> None:
        """Dispatch a response to the waiting future."""
        cmd_id = msg.get("id")
        if cmd_id and cmd_id in self._pending:
            future = self._pending.pop(cmd_id)
            self._progress_callbacks.pop(cmd_id, None)
            if not future.done():
                future.set_result(msg)

    def _handle_progress(self, msg: dict) -> None:
        """Dispatch a progress update to the registered callback."""
        cmd_id = msg.get("id")
        if cmd_id and cmd_id in self._progress_callbacks:
            cb = self._progress_callbacks[cmd_id]
            if cb is not None:
                try:
                    cb(msg.get("data", {}))
                except Exception:
                    pass  # progress callback errors are non-fatal

    def _handle_event(self, msg: dict) -> None:
        """Dispatch an unsolicited event."""
        if self._event_callback is not None:
            try:
                self._event_callback(msg)
            except Exception:
                pass  # event callback errors are non-fatal

    async def _send_and_wait(
        self,
        cmd_id: str,
        action: str,
        args: dict,
        on_progress: Callable[[dict], None] | None,
        timeout: float,
    ) -> dict[str, Any]:
        """Send a command and wait for its response."""
        if self._ws is None:
            raise GolemError("Not connected to bridge", code="NOT_CONNECTED")

        command = {
            "type": "command",
            "id": cmd_id,
            "action": action,
            "args": args,
        }

        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = future
        if on_progress is not None:
            self._progress_callbacks[cmd_id] = on_progress

        await self._ws.send(json.dumps(command))

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(cmd_id, None)
            self._progress_callbacks.pop(cmd_id, None)
            # Send cancel command (best-effort, don't wait)
            cancel = {"type": "command", "id": cmd_id, "action": "cancel", "args": {}}
            try:
                await self._ws.send(json.dumps(cancel))
            except Exception:
                pass
            raise TimeoutError(
                f"The '{action}' command took too long",
                code="TIMEOUT",
                details={"action": action, "timeout": timeout},
            )

        if not response.get("success", False):
            error = response.get("error", {})
            raise from_bridge_error(error)

        return response.get("data", {})

    def _fail_pending(self, reason: str) -> None:
        """Fail all pending futures (e.g., on connection loss)."""
        for cmd_id, future in list(self._pending.items()):
            if not future.done():
                future.set_result({
                    "success": False,
                    "error": {"code": "CONNECTION_LOST", "message": reason, "details": {}},
                })
        self._pending.clear()
        self._progress_callbacks.clear()

    def _shutdown(self) -> None:
        """Stop the event loop and clean up."""
        self._closing = True
        if self._loop is not None and self._ws is not None:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._ws = None
        self._loop = None
        self._thread = None
        self._connected.clear()
        self._pending.clear()
        self._progress_callbacks.clear()


# Module-level singleton
_connection = BridgeConnection()


def get_connection() -> BridgeConnection:
    """Get the module-level bridge connection singleton."""
    return _connection


def reset_connection() -> None:
    """Replace the singleton with a fresh instance. Used for testing."""
    global _connection
    _connection.disconnect()
    _connection = BridgeConnection()
