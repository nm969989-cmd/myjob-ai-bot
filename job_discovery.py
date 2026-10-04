"""Shared regional priorities, honest compact cards, and persistent walk-in reminders."""
import hashlib
import html
import json
import logging
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

IST = timezone(timedelta(hours=5, minutes=30))
PRIORITY_CITIES = {
    "Tiruvannamalai": ("tiruvannamalai", "thiruvannamalai", "thiruannamalai", "tiruvanamalai"),
    "Vellore": ("vellore",),
    "Puducherry": ("puducherry", "pondicherry", "pondi"),
    "Chennai": ("chennai", "madras"),
}
PRIORITY_LABEL = "Tiruvannamalai • Vellore • Puducherry/Pondicherry • Chennai"
_STATE_LOCK = threading.RLock()
_SEARCH_LOCK = threading.Lock()
_SEARCH_POOL = ThreadPoolExecutor(max_workers=8)
_SEARCH_TASKS = {}
STATE_FILE = os.path.join(os.path.dirname(__file__), "job_discovery_state.json")


def priority_city(location):
    text = str(location or "").lower()
    for city, aliases in PRIORITY_CITIES.items():
        if any(re.search(r"\b" + re.escape(alias) + r"\b", text) for alias in aliases):
            return city
    return ""


def city_matches(location, query):
    target = priority_city(query)
    if target:
        return priority_city(location) == target or any(
            re.search(r"\b" + re.escape(alias) + r"\b", str(location).lower())
            for alias in PRIORITY_CITIES[target]
        )
    return str(query).lower() in str(location).lower()


def canonical_link(link):
    parts = urlsplit(str(link or ""))
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "trk"}]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def rank_jobs(jobs):
    """All four preferred cities share the first tier; keep relevance within that tier."""
    return sorted(jobs, key=lambda j: (
        0 if priority_city(j.get("location") or j.get("city")) else 1,
        -float(j.get("relevance") or 0),
    ))


def automatic_search_interval_minutes(value=None):
    """Hourly by default; keep configuration within a polite 15-minute to daily range."""
    if value is None:
        value = os.getenv('AUTO_SEARCH_INTERVAL_MINUTES', '60')
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        minutes = 60
    return max(15, min(1440, minutes))


def timestamp_now():
    return datetime.now(IST).isoformat(timespec='minutes')


def source_lines(job):
    source = str(job.get("source") or job.get("source_type") or "Saved listing")
    # A feed's marketing badge is not evidence of employer verification.
    source = re.sub(r"\b(verified|official)\b", "", source, flags=re.I).strip(" •")
    link = job.get("source_url") or job.get("raw_link") or job.get("registration_link") or job.get("link") or ""
    label = html.escape(source[:100])
    if str(link).startswith(("https://", "http://")):
        label = f'<a href="{html.escape(str(link), quote=True)}">{label}</a>'
    checked = job.get("verified_at") if job.get("verification_status") == "confirmed" else None
    status = "Employer-confirmed" if checked else "Unconfirmed — check the source before travelling/applying"
    retrieved = job.get("retrieved_at") or job.get("found_at") or "Not recorded"
    text = f"🔎 <b>Source:</b> {label}\n⚠️ {status}\n🕒 <b>Retrieved:</b> {html.escape(str(retrieved))}"
    if job.get('source_checked_at'):
        text += '\n🌐 <b>Link checked:</b> ' + html.escape(str(job['source_checked_at'])) + ' (not employer confirmation)'
    if checked:
        text += f"\n✅ <b>Confirmed:</b> {html.escape(str(checked))}"
    return text


def event_start(job):
    """Only accept explicit dates; never turn 'upcoming Saturday' into a recurring event."""
    raw = job.get("event_start") or job.get("walkin_date") or job.get("event_date")
    if not raw:
        return None
    try:
        value = str(raw)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            # Date-only events need a source-supplied reporting time for reminders.
            reporting = str(job.get("reporting_time") or "")
            if not re.fullmatch(r"\d{2}:\d{2}", reporting):
                return None
            value += "T" + reporting
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.replace(tzinfo=IST) if result.tzinfo is None else result.astimezone(IST)
    except (TypeError, ValueError):
        return None


def event_label(job):
    start = event_start(job)
    if start:
        return start.strftime("%a, %d %b %Y • %I:%M %p IST")
    raw = job.get("walkin_date") or job.get("event_date")
    try:
        if raw and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(raw)):
            return datetime.fromisoformat(str(raw)).strftime("%a, %d %b %Y") + " • reporting time unconfirmed"
    except ValueError:
        pass
    return "Date unconfirmed — verify with the employer"


def compact_walkin(job):
    def esc(key, fallback="Not stated"):
        return html.escape(str(job.get(key) or fallback))
    priority = "⭐ Priority city\n" if priority_city(job.get("city")) else ""
    return (
        f"🏢 <b>{esc('company')}</b>\n💼 {esc('role')}\n{priority}"
        f"📍 {esc('city')}\n💰 <b>Reported salary:</b> {esc('package')}\n"
        f"📅 {html.escape(event_label(job))}\n"
        f"🎓 {esc('batches')} • {esc('experience')}\n"
        f"{source_lines(job)}"
    )


def _load_state(path):
    if not os.path.exists(path):
        return {"cards": {}, "reminders": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _save_state(state, path):
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def store_card(job, path=None):
    path = path or STATE_FILE
    ident = str(job.get("id") or canonical_link(job.get("link")) or job.get("company"))
    key = hashlib.sha256(ident.encode()).hexdigest()[:16]
    with _STATE_LOCK:
        state = _load_state(path)
        state.setdefault("cards", {})[key] = dict(job)
        _save_state(state, path)
    return key


def get_card(key, path=None):
    with _STATE_LOCK:
        return _load_state(path or STATE_FILE).get("cards", {}).get(key)


def walkin_keyboard(job):
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    key = store_card(job)
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("📄 Full details", callback_data=f"jobcard:details:{key}"),
               InlineKeyboardButton("🔔 Remind me", callback_data=f"jobcard:remind:{key}"))
    if event_start(job):
        markup.row(InlineKeyboardButton('📅 Add to calendar', callback_data=f'jobcard:calendar:{key}'))
    for field, label in (("registration_link", "🔗 Employer page"), ("google_maps", "🗺️ Maps")):
        url = str(job.get(field) or "")
        if url.startswith(("https://", "http://")):
            markup.row(InlineKeyboardButton(label, url=url))
    return markup


def schedule_reminder(chat_id, job, now=None, path=None):
    path = path or STATE_FILE
    now = now or datetime.now(IST)
    start = event_start(job)
    if not start:
        return "⚠️ No exact date and reporting time in the source. Reminder not set; please confirm with the employer."
    if start <= now:
        return "⚠️ This event has already started or expired. Reminder not set."
    due = max(now, start - timedelta(hours=24))
    key = store_card(job, path=path)
    with _STATE_LOCK:
        state = _load_state(path)
        existing = state.get('reminders', {}).get(f'{chat_id}:{key}')
        if existing and existing.get('event_start') == start.isoformat():
            return '🔔 You already have a reminder for this event (or it was delivered). Use /reminders to manage it.'
        state.setdefault("reminders", {})[f"{chat_id}:{key}"] = {
            "chat_id": chat_id, "card_key": key, "due": due.isoformat(),
            "event_start": start.isoformat(), "sent": False,
        }
        _save_state(state, path)
    return "🔔 Reminder set for " + due.strftime("%d %b %Y, %I:%M %p IST") + ". Use /reminders to view or cancel."


def list_reminders(chat_id, path=None):
    with _STATE_LOCK:
        state = _load_state(path or STATE_FILE)
        return [(r, state.get("cards", {}).get(r["card_key"], {})) for r in state.get("reminders", {}).values()
                if str(r["chat_id"]) == str(chat_id) and not r.get("sent")]


def cancel_reminders(chat_id, path=None):
    path = path or STATE_FILE
    with _STATE_LOCK:
        state = _load_state(path)
        state["reminders"] = {k: r for k, r in state.get("reminders", {}).items() if str(r["chat_id"]) != str(chat_id)}
        _save_state(state, path)


def dispatch_due_reminders(bot, now=None, path=None):
    path = path or STATE_FILE
    now = now or datetime.now(IST)
    with _STATE_LOCK:
        state = _load_state(path)
        changed = False
        for reminder in state.get("reminders", {}).values():
            if reminder.get("sent") or datetime.fromisoformat(reminder["due"]) > now:
                continue
            if datetime.fromisoformat(reminder["event_start"]) <= now:
                reminder["sent"] = True
                changed = True
                continue
            job = state.get("cards", {}).get(reminder["card_key"], {})
            try:
                bot.send_message(reminder["chat_id"], "🔔 <b>Walk-in reminder</b>\n\n" + compact_walkin(job), parse_mode="HTML", disable_web_page_preview=True)
                reminder["sent"] = True
                changed = True
            except Exception:
                logging.exception("Walk-in reminder delivery failed; will retry")
        if changed:
            _save_state(state, path)


def calendar_event(job, now=None):
    start = event_start(job)
    if not start:
        raise ValueError('An exact date and reporting time are required')
    now = now or datetime.now(IST)
    def escape(value):
        return str(value or '').replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')
    uid = hashlib.sha256((str(job.get('id') or job.get('company')) + start.isoformat()).encode()).hexdigest()
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Myjob//Walk-in reminders//EN',
             'BEGIN:VEVENT', f'UID:{uid}@myjob',
             'DTSTAMP:' + now.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
             'DTSTART:' + start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'),
             'SUMMARY:' + escape(f"{job.get('company', 'Company')} walk-in: {job.get('role', '')}"),
             'LOCATION:' + escape(job.get('venue_address') or job.get('city')),
             'DESCRIPTION:' + escape('Confirm availability with the employer before travelling. Source: ' + str(job.get('registration_link') or job.get('source_url') or 'Not provided')),
             'END:VEVENT', 'END:VCALENDAR']
    # RFC 5545 lines are folded at 75 octets, not 75 Unicode characters.
    folded = []
    for line in lines:
        part = ''
        for char in line:
            if len((part + char).encode('utf-8')) > 75:
                folded.append(part)
                part = ' '
            part += char
        folded.append(part)
    return ('\r\n'.join(folded) + '\r\n').encode('utf-8')


def send_walkin_cards(bot, chat_id, drives, navigation=None):
    for job in rank_jobs(drives):
        start = event_start(job)
        if start and start <= datetime.now(IST):
            continue
        bot.send_message(chat_id, compact_walkin(job), parse_mode="HTML", reply_markup=walkin_keyboard(job), disable_web_page_preview=True)
        time.sleep(0.5)
    if navigation:
        add_priority_buttons(navigation, prefix='walkins')
        bot.send_message(chat_id, "📍 Priority: " + PRIORITY_LABEL + "\nChoose a location or refresh below.", reply_markup=navigation)


def add_priority_buttons(markup, prefix='search'):
    from telebot.types import InlineKeyboardButton
    cities = list(PRIORITY_CITIES)
    for index in range(0, len(cities), 2):
        markup.row(*[InlineKeyboardButton(f'📍 {city}', callback_data=f'{prefix}:{city.lower()}') for city in cities[index:index + 2]])
    return markup


def fetch_priority_search(query, fetchers, limit=8, timeout=25):
    """Search each preferred city even when cached listings already fill the result limit."""
    requested = priority_city(query)
    locations = [requested] if requested else list(PRIORITY_CITIES)
    role = str(query)
    for aliases in PRIORITY_CITIES.values():
        for alias in aliases:
            role = re.sub(r"\b" + re.escape(alias) + r"\b", "", role, flags=re.I)
    role = role.strip() or "fresher"
    futures = []
    with _SEARCH_LOCK:
        for key, (started, task) in list(_SEARCH_TASKS.items()):
            if task.done() and time.monotonic() - started >= 900:
                del _SEARCH_TASKS[key]
        for city in locations:
            for fetch in fetchers:
                key = (fetch, role.lower(), city, limit)
                entry = _SEARCH_TASKS.get(key)
                if entry is None:
                    entry = (time.monotonic(), _SEARCH_POOL.submit(fetch, query=role, location=f'{city}, India', limit=limit))
                    _SEARCH_TASKS[key] = entry
                futures.append(entry[1])
    # Reuse in-flight work and a fixed worker pool so timeouts cannot spawn unbounded threads.
    done, _ = wait(futures, timeout=timeout)
    jobs = []
    seen = set()
    for future in done:
        try:
            for result in future.result():
                job = dict(result)
                link = canonical_link(job.get('link'))
                if not link or link in seen:
                    continue
                if requested and not city_matches(job.get('location', ''), requested):
                    continue
                seen.add(link)
                jobs.append(job)
        except Exception:
            logging.exception('Priority-city search source failed')
    return rank_jobs(jobs)
