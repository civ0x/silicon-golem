#!/bin/bash
# Silicon Golem — one-command launcher
# Usage: ./start.sh <mc_port> <player_name>
# Example: ./start.sh 59223 jumbojorge

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

if [ $# -lt 2 ]; then
  echo "Usage: ./start.sh <mc_port> <player_name>"
  echo "  mc_port     — the port from Minecraft's 'Open to LAN' message"
  echo "  player_name — your Minecraft username"
  exit 1
fi

MC_PORT="$1"
PLAYER="$2"

cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$ORCH_PID" ] && kill "$ORCH_PID" 2>/dev/null
  [ -n "$BRIDGE_PID" ] && kill "$BRIDGE_PID" 2>/dev/null
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# Start bridge
echo "Starting bridge on MC port $MC_PORT..."
cd "$DIR/bridge"
MC_PORT="$MC_PORT" node server.js &
BRIDGE_PID=$!
cd "$DIR"

# Wait for bridge to be ready
sleep 2

# Start orchestrator
echo "Starting orchestrator for player $PLAYER..."
python -m golem --player "$PLAYER" &
ORCH_PID=$!

# Open code panel
echo "Opening code panel..."
open "$DIR/panel/index.html"

echo ""
echo "Silicon Golem is running."
echo "  Bridge PID:       $BRIDGE_PID"
echo "  Orchestrator PID: $ORCH_PID"
echo "  Press Ctrl+C to stop everything."
echo ""

# Wait for either process to exit
wait
