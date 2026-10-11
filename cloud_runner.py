#!/usr/bin/env python3
"""One bounded job-bot cycle for the GitHub Actions cloud workflow.

``python cloud_runner.py`` runs a single pass and exits with:

* ``0`` - completed with no recorded stage or delivery errors.
* ``1`` - a caught stage or delivery error was recorded.
* ``2`` - Telegram delivery is not configured (nothing is searched or sent).

Individual channels that are unavailable, and budget skips, are recorded as
nonfatal notes: an empty but otherwise successful cycle is *not* an error.

The four preferred cities are searched and their regional digest is delivered
*before* the longer Telegram channel scans, so the most relevant regional job
cards go out first even if a later stage is slow or fails.
"""
from __future__ import annotations

import csv
import os
import sys
import time
from datetime import datetime

# Imported here (not lazily) so it is a real module attribute that callers and
# tests can substitute with ``monkeypatch.setattr(cloud_runner, "run_radar", ...)``.
from job_radar import run_radar

# --- module state (tests patch these directly) ----------------------------
START_TIME = time.time()
step_errors: list[str] = []
stage_notes: list[str] = []
stage_times: dict[str, float] = {}

# Used when neither TARGET_CHANNEL(S) nor the bot config lists any channel.
DEFAULT_CHANNELS = ["jobopenings_india", "JobSkull"]
APPLIED_LOG_FILE = "applied_jobs_log.csv"
FOLLOWUP_AFTER_DAYS = 3


def _load_bot():
    token = str(
        os.getenv("TELEGRAM_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    ).strip().strip('"').strip("'")
    if token.lower().startswith("bot"):
        token = token[3:]
    chat = str(os.getenv("TELEGRAM_CHAT_ID", "")).strip().strip('"').strip("'")
    if not token:
        return None, chat
    import telebot  # lazy import: no hard dependency when delivery is unconfigured

    return telebot.TeleBot(token), chat


bot, chat_id = _load_bot()


def _target_channels(configured):
    """Resolve the channel list: explicit env wins, then bot config, then default."""
    raw = os.getenv("TARGET_CHANNEL", "") or os.getenv("TARGET_CHANNELS", "")
    if raw:
        parsed = [c.strip().lstrip("@") for c in raw.split(",") if c.strip()]
        if parsed:
            return parsed
    return list(configured or []) or list(DEFAULT_CHANNELS)


def _parse_date(value):
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _pending_followups(log_path: str = APPLIED_LOG_FILE, now=None):
    """Applications old enough to chase that were never marked "Followed Up"."""
    if not os.path.exists(log_path):
        return []
    now = now or datetime.now()
    try:
        with open(log_path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return []

    latest: dict[str, dict] = {}
    for row in rows:
        url = (row.get("URL") or row.get("url") or "").strip()
        if url:
            latest[url] = row  # last row for a URL is its latest state

    pending = []
    for url, row in latest.items():
        notes = (row.get("Notes") or row.get("notes") or "").lower()
        status = (row.get("Status") or row.get("status") or "").lower()
        if "followed up" in notes or "followed up" in status:
            continue
        applied = _parse_date(row.get("Date") or row.get("date"))
        if applied is None or (now - applied).days < FOLLOWUP_AFTER_DAYS:
            continue
        title = (row.get("Job Title") or row.get("Title") or "your application").strip()
        pending.append({"url": url, "title": title})
    return pending


def _status_summary(elapsed: float, scanned: int, applied_count: int) -> str:
    lines = [
        "🤖 Cloud job cycle finished",
        f"⏱ {elapsed:.0f}s • channels scanned: {scanned} • tracked applications: {applied_count}",
    ]
    if step_errors:
        lines.append("⚠️ " + "; ".join(step_errors))
    elif stage_notes:
        lines.append("ℹ️ " + "; ".join(stage_notes))
    else:
        lines.append("✅ No stage errors.")
    return "\n".join(lines)


def run_cloud() -> int:
    """Run one cycle. Returns the process exit code (see module docstring)."""
    if not bot or not chat_id:
        print("[Cloud] Missing Telegram delivery configuration; exiting 2.")
        return 2

    # Resolved at call time so tests / callers can substitute the modules.
    from job_radar import dispatch_tamil_nadu_alerts
    from bot_optimizer import dispatch_walkin_alerts
    from main import TARGET_CHANNELS, scrape_single_channel, load_applied_jobs

    # 1) Priority regional digest (Tiruvannamalai, Vellore, Puducherry, Chennai)
    #    BEFORE the longer channel scans.
    _started = time.time()
    try:
        dispatch_tamil_nadu_alerts(
            bot=bot, chat_id=chat_id, limit=6, force_refresh=True, only_unseen=True
        )
    except Exception as error:  # noqa: BLE001 - stage failures must not abort the cycle
        step_errors.append(f"Regional stage failed: {error}")
    stage_times["regional"] = round(time.time() - _started, 3)

    # 2) Verified walk-in drives (the helper enforces the once-per-day guard).
    _started = time.time()
    try:
        dispatch_walkin_alerts(bot=bot, chat_id=chat_id, once_per_day=True, limit=6)
    except Exception as error:  # noqa: BLE001
        step_errors.append(f"Walk-in stage failed: {error}")
    stage_times["walkins"] = round(time.time() - _started, 3)

    # 3) Full multi-platform radar refresh.
    _started = time.time()
    try:
        run_radar()
    except Exception as error:  # noqa: BLE001
        step_errors.append(f"Radar stage failed: {error}")
    stage_times["radar"] = round(time.time() - _started, 3)

    # 4) Longer Telegram channel scans. A single unavailable channel is a
    #    nonfatal note, never a cycle failure.
    applied_jobs = load_applied_jobs()
    channels = _target_channels(TARGET_CHANNELS)
    scanned = 0
    for channel in channels:
        _started = time.time()
        try:
            new_jobs_found, _attempts = scrape_single_channel(
                channel, applied_jobs, chat_id, max_jobs=2
            )
            scanned += 1
            if new_jobs_found:
                applied_jobs = load_applied_jobs()
        except Exception as error:  # noqa: BLE001 - one bad channel must not stop the rest
            stage_notes.append(f"{channel} unavailable: {error}")
        finally:
            stage_times[f"channel:{channel}"] = round(time.time() - _started, 3)

    # 5) Follow-up reminders, skipping applications already marked "Followed Up".
    for item in _pending_followups():
        try:
            bot.send_message(
                chat_id,
                f"🔔 Follow up on {item['title']}\n{item['url']}",
                disable_web_page_preview=True,
            )
        except Exception as error:  # noqa: BLE001
            step_errors.append(f"Follow-up delivery failed: {error}")

    # 6) Final status summary (delivered whenever configuration is present).
    try:
        bot.send_message(
            chat_id,
            _status_summary(time.time() - START_TIME, scanned, len(applied_jobs)),
            disable_web_page_preview=True,
        )
    except Exception as error:  # noqa: BLE001
        step_errors.append(f"Status delivery failed: {error}")

    return 1 if step_errors else 0


if __name__ == "__main__":
    sys.exit(run_cloud())

