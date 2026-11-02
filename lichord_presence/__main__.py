from __future__ import annotations

import argparse
import asyncio
import logging
import threading

from .config import PresenceConfig
from .mpris import MprisPresence
from .web import run_web

def main():
    parser = argparse.ArgumentParser(description="LiChord Discord Rich Presence companion")
    parser.add_argument("--web-only", action="store_true", help="Only run the local settings page")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.web_only:
        run_web(args.host, args.port)
        return
    threading.Thread(target=run_web, args=(args.host, args.port), daemon=True).start()
    cfg = PresenceConfig.load()
    print("LiChord Presence is running. Open http://127.0.0.1:8790 to configure it.")
    try:
        asyncio.run(MprisPresence(cfg).run())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
