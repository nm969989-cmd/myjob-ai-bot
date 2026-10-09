"""Opt-in bounded Lever applications with durable attempts and Telegram receipts.

Unknown outcomes are never retried automatically: a timeout can follow a real submit.
No network calls occur on import; the continuous worker is the only dispatcher.
"""
import json
import re
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from career_service import Store, UTC, normalize, expired, contains, parse_date


def defaults():
    return dict(enabled=False, employers=[], roles=[], cities=[], minSalaryLpa=0,
                dailyLimit=3, timezone='Asia/Kolkata', profileConfirmed=False)


def validate(raw):
    if not isinstance(raw, dict):
        raise ValueError('Expected automation settings object.')
    p = defaults()
    p.update({k: raw[k] for k in p if k in raw})
    if type(p['enabled']) is not bool or type(p['profileConfirmed']) is not bool:
        raise ValueError('Enabled and profileConfirmed must be true or false.')
    for key in ('roles', 'cities'):
        if not isinstance(p[key], list) or len(p[key]) > 30 or any(not isinstance(x, str) or not x.strip() or len(x) > 150 for x in p[key]):
            raise ValueError('Provide a list of nonempty ' + key)
        p[key] = list(dict.fromkeys(x.strip() for x in p[key]))
    if not isinstance(p['employers'], list) or len(p['employers']) > 30:
        raise ValueError('Provide up to 30 employers.')
    for employer in p['employers']:
        if (not isinstance(employer, dict) or set(employer) != {'company', 'leverSlug'}
                or not isinstance(employer['company'], str) or not employer['company'].strip()
                or len(employer['company']) > 150 or not isinstance(employer['leverSlug'], str)
                or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', employer['leverSlug'])):
            raise ValueError('Each employer needs company and its exact Lever leverSlug.')
    if type(p['dailyLimit']) is not int or not 1 <= p['dailyLimit'] <= 50:
        raise ValueError('Daily limit must be 1–50 attempts.')
    if type(p['minSalaryLpa']) not in (int, float) or not 0 <= p['minSalaryLpa'] <= 1000:
        raise ValueError('Minimum salary must be 0–1000 LPA.')
    try:
        ZoneInfo(p['timezone'])
    except (ValueError, TypeError, KeyError):
        raise ValueError('Use a valid IANA timezone.') from None
    if p['enabled'] and (not all(p[k] for k in ('employers', 'roles', 'cities')) or not p['profileConfirmed']):
        raise ValueError('Set employers, roles, cities and confirm your real profile before enabling.')
    return p


def tables(db):
    db.execute('CREATE TABLE IF NOT EXISTS auto_policy (id INTEGER PRIMARY KEY, revision INTEGER, data TEXT)')
    db.execute('INSERT OR IGNORE INTO auto_policy VALUES (1,0,?)', (json.dumps(defaults()),))
    db.execute('CREATE TABLE IF NOT EXISTS auto_attempts (url TEXT PRIMARY KEY, day TEXT, status TEXT, job TEXT, detail TEXT, notified INTEGER DEFAULT 0)')
    db.commit()


def policy(store):
    with store.connect() as db:
        tables(db)
        revision, raw = db.execute('SELECT revision,data FROM auto_policy WHERE id=1').fetchone()
        attempts = [dict(url=u, status=s, detail=d, notified=bool(n)) for u,s,d,n in db.execute('SELECT url,status,detail,notified FROM auto_attempts ORDER BY rowid DESC LIMIT 10')]
        return dict(revision=revision, settings=json.loads(raw), attempts=attempts)


def save_policy(store, raw, revision):
    p = validate(raw)
    if type(revision) is not int:
        raise ValueError('Revision required.')
    with store.connect() as db:
        tables(db)
        if db.execute('UPDATE auto_policy SET revision=revision+1,data=? WHERE id=1 AND revision=?', (json.dumps(p), revision)).rowcount != 1:
            from career_service import Conflict
            raise Conflict('Settings changed in another session. Reload before saving.')
        db.commit()
    return dict(revision=revision + 1, settings=p)


def lever_url(value):
    u = urlsplit(value)
    if u.scheme != 'https' or u.netloc not in ('jobs.lever.co', 'jobs.eu.lever.co') or u.query or u.fragment:
        return None
    m = re.fullmatch(r'/([a-zA-Z0-9_-]+)/([a-fA-F0-9-]{36})(?:/apply)?/?', u.path)
    return (u.netloc, m[1], f'https://{u.netloc}/{m[1]}/{m[2]}') if m else None


def eligible(raw, p, now):
    j = normalize(raw)
    target = lever_url(j['url'])
    if not target or expired(j, now) or j['checkStatus'] == 'failed':
        return False
    if not any(e['company'].strip().casefold() == j['company'].casefold() and e['leverSlug'] == target[1] for e in p['employers']):
        return False
    if not any(contains(j['title'], role) for role in p['roles']):
        return False
    if j['city'].casefold() not in [city.casefold() for city in p['cities']]:
        return False
    stamp = parse_date(j['postedAt']) or parse_date(j['verifiedAt'])
    if not stamp or (now - stamp).days > 30 or (stamp > now and stamp.date() != now.date()):
        return False
    salary = re.search(r'(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*(?:LPA|lakhs?|lacs?)\b', j['salary'], re.I)
    return p['minSalaryLpa'] == 0 or bool(salary and float(salary[1]) >= p['minSalaryLpa'])


def credentials(root):
    # Read real files directly; main.load_profile has demo fallback values.
    profile = json.loads((Path(root) / 'profile.json').read_text())
    if not isinstance(profile, dict) or not all(isinstance(profile.get(k), str) and profile[k].strip() for k in ('full_name', 'email', 'phone')):
        raise ValueError('Real profile.json needs full_name, email and phone.')
    if profile['email'].lower().endswith(('@example.com', '@example.org', '@example.net')):
        raise ValueError('Replace the example email with your real email.')
    resume = Path(os.getenv('AUTO_APPLY_RESUME', str(Path(root) / 'resume.pdf')))
    if not resume.is_file() or not 0 < resume.stat().st_size <= 10 * 1024 * 1024:
        raise ValueError('Provide a resume PDF under 10 MB.')
    if not resume.read_bytes().startswith(b'%PDF-'):
        raise ValueError('Resume must be a PDF.')
    return profile, resume


def notify(store, sender, chat_id):
    with store.connect() as db:
        tables(db)
        rows = db.execute("SELECT url,status,job,detail FROM auto_attempts WHERE notified=0 AND status!='reserved' LIMIT 20").fetchall()
    for url, status, raw, detail in rows:
        j = json.loads(raw)
        heading = '✅ Application submitted' if status == 'submitted' else '⚠️ Application needs manual review'
        message = f"{heading}\n{j['title'][:200]} — {j['company'][:150]}\n{detail}\nJob link: {url}"
        sender.send_message(chat_id, message, parse_mode=None, disable_web_page_preview=True)
        with store.connect() as db:
            db.execute('UPDATE auto_attempts SET notified=1 WHERE url=?', (url,)); db.commit()


def tick(store, jobs, root, sender, chat_id, adapter, now=None):
    import fcntl
    now = now or datetime.now(UTC)
    if not sender or not chat_id:
        return
    Path(store.path).parent.mkdir(parents=True, exist_ok=True)
    with open(store.path + '.auto.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        # A reserved record from an interrupted previous process may have submitted.
        with store.connect() as db:
            tables(db)
            db.execute("UPDATE auto_attempts SET status='unknown',detail='Previous attempt was interrupted; check employer confirmation before retrying.' WHERE status='reserved'")
            db.commit()
        notify(store, sender, chat_id)
        snapshot = policy(store); p = snapshot['settings']
        if not p['enabled']:
            return
        profile, resume = credentials(root)
        legacy_path = Path(root) / 'applied_jobs.json'
        legacy = json.loads(legacy_path.read_text()) if legacy_path.exists() else []
        if not isinstance(legacy, list) or any(not isinstance(url, str) for url in legacy):
            raise ValueError('Existing applied-job history must be a URL list.')
        legacy = {(lever_url(url) or ('', '', url))[2] for url in legacy}
        day = now.astimezone(ZoneInfo(p['timezone'])).date().isoformat()
        for raw in jobs:
            if not eligible(raw, p, now):
                continue
            j = normalize(raw); j['url'] = lever_url(j['url'])[2]
            if j['url'] in legacy:
                continue
            with store.connect() as db:
                tables(db); db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT revision FROM auto_policy WHERE id=1').fetchone()[0]
                tracked = json.loads(db.execute('SELECT data FROM workspace WHERE id=1').fetchone()[0])['applications']
                if current != snapshot['revision']:
                    return
                if db.execute('SELECT count(*) FROM auto_attempts WHERE day=?', (day,)).fetchone()[0] >= p['dailyLimit']:
                    break
                if any((lever_url(url) or ('', '', url))[2] == j['url'] for url in tracked):
                    continue
                if db.execute('SELECT 1 FROM auto_attempts WHERE url=?', (j['url'],)).fetchone():
                    continue
                db.execute("INSERT INTO auto_attempts VALUES (?,?,'reserved',?,'',0)", (j['url'], day, json.dumps(j))); db.commit()
            try:
                result = adapter(j, p, profile, resume)
                status = 'submitted' if result is True else 'manual'
                detail = 'Employer confirmation page detected.' if result is True else 'Submission was not confirmed. Check the job link; no automatic retry.'
            except Exception:
                status, detail = 'unknown', 'Attempt interrupted. Check the employer for confirmation; no automatic retry.'
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('UPDATE auto_attempts SET status=?,detail=? WHERE url=?', (status, detail, j['url']))
                if status == 'submitted':
                    state = json.loads(db.execute('SELECT data FROM workspace WHERE id=1').fetchone()[0])
                    entry = state['applications'].setdefault(j['url'], dict(job=j, notes='', followUp=''))
                    entry.update(status='Applied', updatedAt=now.isoformat())
                    db.execute('UPDATE workspace SET revision=revision+1,data=? WHERE id=1', (json.dumps(state),))
                db.commit()
            notify(store, sender, chat_id)
            # One application per minute; daily cap includes all outcomes.
            break
