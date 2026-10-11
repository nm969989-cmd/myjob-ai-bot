#!/usr/bin/env python3
"""Opt-in engineering-search launcher.

Reuses the single Telegram bot, the existing command handlers, the application
worker and the Flask dashboard from ``main.py``, then adds:

* the private engineering commands (``/esearch``, ``/save_search``, ...), and
* one bounded background scan thread that refreshes and dispatches digests.

It deliberately does **not** create a second Telegram poller: the existing
``main.thread_supervisor`` still owns the one polling loop. Run this *instead of*
``python main.py``; never run both at the same time (they would share one bot
token and conflict). Nothing is submitted and no message is sent on import.
"""
from __future__ import annotations

import os
import threading
import time

from dotenv import load_dotenv

load_dotenv(override=False)

import engineering_telegram as engineering  # noqa: E402
import main  # noqa: E402  - existing bot, handlers, Flask app and workers


def _owner_chat_id() -> str:
    owner = str(os.environ.get("TELEGRAM_CHAT_ID", "")).strip()
    # A negative id is a group/channel; engineering mode is owner-only and private.
    if not owner or owner.startswith("-"):
        raise SystemExit("A positive private TELEGRAM_CHAT_ID is required for engineering mode")
    return owner


def _engineering_cycle(owner: str) -> None:
    interval = max(900, int(os.environ.get("ENGINEERING_INTERVAL_SECONDS", "3600")))
    while True:
        try:
            with engineering.LOCK:
                engineering.refresh()
                engineering.dispatch(main.bot, owner)
        except Exception as exc:  # noqa: BLE001 - keep the scheduler alive
            # Report the failure type only; never tokens or command stdout.
            print(f"Engineering scan/delivery failed: {type(exc).__name__}", flush=True)
        time.sleep(interval)


def run_engineering_app() -> None:
    if main.bot is None:
        raise SystemExit("TELEGRAM_TOKEN is required to run engineering mode")
    owner = _owner_chat_id()

    # Same bot object, extra private commands - no second poller.
    engineering.install_handlers(main.bot, owner)
    threading.Thread(
        target=_engineering_cycle, args=(owner,), name="EngineeringSearch", daemon=True
    ).start()

    # Reuse the existing supervisor so exactly one Telegram poller runs.
    threading.Thread(
        target=main.thread_supervisor, name="Supervisor", daemon=True
    ).start()

    main.app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))


if __name__ == "__main__":
    run_engineering_app()
