"""Entry point: python -m golem --player <MinecraftUsername>"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Silicon Golem orchestrator")
    parser.add_argument("--player", required=True, help="Minecraft player name to track")
    parser.add_argument("--bridge-host", default="localhost")
    parser.add_argument("--bridge-port", type=int, default=3001)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )

    project_root = Path(__file__).resolve().parent.parent
    orch = Orchestrator(
        player_name=args.player,
        bridge_host=args.bridge_host,
        bridge_port=args.bridge_port,
        prompt_dir=str(project_root / "prompts"),
        learner_state_path=str(project_root / "data" / "learner_state.json"),
    )

    async def run() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))

        async def shutdown() -> None:
            logging.getLogger(__name__).info("Shutting down...")
            await orch.stop()

        await orch.start()

    asyncio.run(run())


if __name__ == "__main__":
    main()
