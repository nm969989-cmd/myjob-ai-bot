"""Private career workspace and opt-in notifications. No network calls on import.

SQLite state and delivery receipts belong on a persistent volume, never in Git.
Only the continuously running bot dispatches these notifications. Existing cloud
campaigns remain independent; running another notifier with another DB duplicates receipts.
"""
import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
STATUSES = ('Saved', 'Applied', 'Interview', 'Offer', 'Rejected')
DEFAULT_DB = 'career_workspace.sqlite3'
_LOCK = threading.Lock()


def initial_state():
    return {'version': 1, 'preferences': {'skills': [], 'cities': [], 'experience': None, 'minSalary': None, 'remote': False}, 'applications': {},
            'alerts': {'enabled': False, 'followupsEnabled': False, 'time': '09:00', 'timezone': 'Asia/Kolkata', 'quietStart': '22:00', 'quietEnd': '08:00', 'minScore': 30, 'maxAgeDays': 30}}


def clean_url(value):
    try:
        parts = urlsplit(str(value or '').strip())
        if parts.scheme.lower() not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return ''
        query = sorted((k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not re.match(r'^(utm_|fbclid$|gclid$|trk$)', k, re.I))
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/') or '/', urlencode(query), ''))
    except ValueError:
        return ''


def text(value, limit=10000):
    return value.strip()[:limit] if isinstance(value, str) else ''


def terms(value):
    values = value if isinstance(value, list) else re.split('[,\n]', text(value))
    return list(dict.fromkeys(text(v, 100) for v in values if text(v, 100)))[:50]


def normalize(raw):
    job = raw if isinstance(raw, dict) else {}
    return {'id': str(job.get('id', '')), 'url': clean_url(job.get('url') or job.get('apply_url') or job.get('link') or job.get('raw_link')),
            'title': text(job.get('title') or job.get('role'), 300) or 'Untitled opportunity',
            'company': text(job.get('company'), 200) or 'Company not stated', 'city': text(job.get('city') or job.get('location'), 200),
            'description': text(job.get('description') or job.get('summary')), 'skills': terms(job.get('skills', [])),
            'salary': text(job.get('salary') or job.get('package'), 200), 'experience': text(job.get('experience'), 200),
            'verifiedAt': text(job.get('verifiedAt') or job.get('verified_at') or job.get('source_checked_at'), 100),
            'postedAt': text(job.get('postedAt') or job.get('posted_at') or job.get('date_posted'), 100),
            'deadline': text(job.get('deadline') or job.get('expires_at') or job.get('walkin_date') or job.get('event_date'), 100),
            'checkStatus': job.get('checkStatus') if job.get('checkStatus') in ('success', 'failed', 'unknown') else ('success' if job.get('verified') is True else 'failed' if job.get('verified') is False else 'unknown'),
            'closed': job.get('closed') is True or job.get('verify_reason') in ('expired', 'closed', 'http_404', 'http_410')}


def parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T.*)?', value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if len(value) == 10:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    except ValueError:
        return None


def expired(job, now):
    end = parse_date(job.get('deadline'))
    return job.get('closed') is True or (end is not None and end < now)


def validate_state(raw):
    if not isinstance(raw, dict) or raw.get('version') != 1:
        raise ValueError('Expected a version 1 workspace.')
    state = initial_state()
    p, a, apps = raw.get('preferences', {}), raw.get('alerts', {}), raw.get('applications', {})
    if not all(isinstance(v, dict) for v in (p, a, apps)) or len(apps) > 1000:
        raise ValueError('Invalid workspace or more than 1,000 applications.')
    state['preferences'].update(skills=terms(p.get('skills', [])), cities=terms(p.get('cities', [])), remote=p.get('remote') is True)
    for key, maximum in [('experience', 60), ('minSalary', 1000)]:
        value = p.get(key)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= maximum:
                raise ValueError('Invalid preference: ' + key)
        state['preferences'][key] = value
    for entry in apps.values():
        if not isinstance(entry, dict) or entry.get('status') not in STATUSES:
            raise ValueError('Invalid application status.')
        job = normalize(entry.get('job'))
        if not job['url']:
            raise ValueError('Application must have an HTTP(S) URL.')
        due = text(entry.get('followUp'), 100)
        if due and (not re.fullmatch(r'\d{4}-\d{2}-\d{2}', due) or not parse_date(due)):
            raise ValueError('Invalid follow-up date.')
        state['applications'][job['url']] = {'job': job, 'status': entry['status'], 'notes': text(entry.get('notes'), 5000), 'followUp': due, 'updatedAt': text(entry.get('updatedAt'), 100)}
    for key in ('time', 'quietStart', 'quietEnd'):
        value = a.get(key, state['alerts'][key])
        if not isinstance(value, str) or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', value):
            raise ValueError('Invalid alert time.')
        state['alerts'][key] = value
    zone = a.get('timezone', 'Asia/Kolkata')
    try:
        ZoneInfo(zone)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError('Invalid IANA timezone.') from None
    state['alerts']['timezone'] = zone
    for key, lower, upper in [('minScore', 0, 100), ('maxAgeDays', 1, 90)]:
        value = a.get(key, state['alerts'][key])
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError('Invalid alert threshold.')
        state['alerts'][key] = value
    state['alerts'].update(enabled=a.get('enabled') is True, followupsEnabled=a.get('followupsEnabled') is True)
    return state


class Conflict(Exception):
    pass


class Store:
    def __init__(self, path=None):
        self.path = str(path or os.getenv('CAREER_DB_FILE', DEFAULT_DB))

    @contextmanager
    def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('CREATE TABLE IF NOT EXISTS workspace (id INTEGER PRIMARY KEY, revision INTEGER, data TEXT)')
            connection.execute('CREATE TABLE IF NOT EXISTS receipts (key TEXT PRIMARY KEY, sent_at TEXT)')
            connection.execute('CREATE TABLE IF NOT EXISTS observations (key TEXT PRIMARY KEY, status TEXT, checked_at TEXT)')
            connection.execute('INSERT OR IGNORE INTO workspace VALUES (1, 0, ?)', (json.dumps(initial_state()),))
            connection.commit()
            yield connection
        finally:
            connection.close()

    def read(self):
        with self.connect() as db:
            revision, raw = db.execute('SELECT revision, data FROM workspace WHERE id=1').fetchone()
            return {'revision': revision, 'state': json.loads(raw)}

    def write(self, raw, revision):
        state = validate_state(raw)
        if type(revision) is not int:
            raise ValueError('Revision is required.')
        with self.connect() as db:
            result = db.execute('UPDATE workspace SET revision=revision+1, data=? WHERE id=1 AND revision=?', (json.dumps(state), revision))
            if result.rowcount != 1:
                raise Conflict('Workspace changed in another session. Reload before saving.')
            db.commit()
            return {'revision': revision + 1, 'state': state}

    def seen(self, key):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM receipts WHERE key=?', (key,)).fetchone() is not None

    def receipt(self, keys, now):
        with self.connect() as db:
            db.executemany('INSERT OR IGNORE INTO receipts VALUES (?, ?)', [(k, now.isoformat()) for k in keys])
            db.commit()

    def observe(self, key, status, now=None):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO observations VALUES (?, ?, ?)', (key, status, (now or datetime.now(UTC)).isoformat()))
            db.commit()

    def observations(self):
        with self.connect() as db:
            return {key: {'status': status, 'checked_at': checked} for key, status, checked in db.execute('SELECT key,status,checked_at FROM observations')}


def contains(haystack, term):
    return bool(re.search(r'(^|[^a-z0-9])' + re.escape(term) + r'(?=$|[^a-z0-9])', haystack, re.I))


def match(job, preferences):
    earned, possible, reasons = 0, 0, []
    skills, cities = preferences['skills'], preferences['cities']
    if skills:
        possible += 50
        haystack = ' '.join([job['title'], job['description'], *job['skills']])
        matches = [s for s in skills if contains(haystack, s)]
        earned += 50 * len(matches) / len(skills)
        reasons.append('Skills: ' + ', '.join(matches) if matches else 'No preferred skills stated')
    if cities:
        possible += 20
        def city(value):
            return re.sub(r'th?iruv?annamalai|thiruannamalai', 'tiruvannamalai', value.lower().replace('pondicherry', 'puducherry'))
        preferred = next((c for c in cities if contains(city(job['city']), city(c))), None)
        if preferred:
            earned += 20
            reasons.append('Location: ' + preferred)
    if preferences['remote']:
        possible += 10
        if re.search(r'\bremote\b', job['city'] + ' ' + job['description'], re.I):
            earned += 10
            reasons.append('Remote work mentioned')
    if preferences['experience'] is not None:
        possible += 15
        years = re.search(r'\d+(?:\.\d+)?', job['experience'])
        if years and float(years[0]) <= preferences['experience']:
            earned += 15
            reasons.append('Minimum experience met')
    if (preferences['minSalary'] or 0) > 0:
        possible += 15
        salary = re.search(r'(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?))?\s*(?:lpa|lakhs?|lacs?)', job['salary'], re.I)
        if salary and float(salary[1]) >= preferences['minSalary']:
            earned += 15
            reasons.append('Salary minimum met')
    return (int(earned / possible * 100 + .5) if possible else None), reasons


def load_jobs(root):
    jobs, seen = [], set()
    for name in ('tn-live-jobs/public/data/jobs.json', 'radar_results.json', 'radar_jobs.json'):
        try:
            payload = json.loads((Path(root) / name).read_text())
            rows = payload if isinstance(payload, list) else payload.get('jobs', [])
            for row in rows:
                job = normalize(row)
                if job['url'] and job['url'] not in seen:
                    seen.add(job['url'])
                    jobs.append(job)
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return jobs


def quiet(alerts, now):
    local = now.astimezone(ZoneInfo(alerts['timezone']))
    current = local.strftime('%H:%M')
    start, end = alerts['quietStart'], alerts['quietEnd']
    return start != end and (start <= current < end if start < end else current >= start or current < end)


def dispatch(store, jobs, sender, chat_id, now=None):
    """Mark receipts only after successful sends. Serialize across local processes."""
    import fcntl
    now = now or datetime.now(UTC)
    if not sender or not chat_id:
        return 0
    with _LOCK:
        Path(store.path).parent.mkdir(parents=True, exist_ok=True)
        with open(store.path + '.delivery.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return 0
            state = store.read()['state']
            alerts = state['alerts']
            store.observe('worker', 'running', now)
            if quiet(alerts, now):
                return 0
            local = now.astimezone(ZoneInfo(alerts['timezone']))
            owner = hashlib.sha256(str(chat_id).encode()).hexdigest()[:16]
            today = local.date().isoformat()
            count = 0
            current_time = local.strftime('%H:%M')
            digest_day = local.date()
            digest_due = current_time >= alerts['time']
            # A late-night digest blocked by overnight quiet hours belongs to
            # yesterday until today's scheduled time arrives.
            if (alerts['quietStart'] > alerts['quietEnd']
                    and alerts['time'] >= alerts['quietStart']
                    and current_time < alerts['time']):
                digest_day -= timedelta(days=1)
                digest_due = True
            if alerts['enabled'] and digest_due:
                daily = f'digest:{owner}:{digest_day.isoformat()}'
                if not store.seen(daily):
                    candidates, seen = [], set()
                    for raw in jobs:
                        job = normalize(raw)
                        if not job['url'] or job['url'] in seen:
                            continue
                        seen.add(job['url'])
                        stamp_value = job['postedAt'] if parse_date(job['postedAt']) else job['verifiedAt']
                        stamp = parse_date(stamp_value)
                        dated_today = len(stamp_value) == 10 and stamp and stamp.date() == now.date()
                        score, reasons = match(job, state['preferences'])
                        key = f'job:{owner}:' + hashlib.sha256(job['url'].encode()).hexdigest()
                        if (not expired(job, now) and job['checkStatus'] != 'failed' and stamp and (stamp <= now or dated_today) and now - stamp <= timedelta(days=alerts['maxAgeDays'])
                                and (score or 0) >= alerts['minScore'] and not store.seen(key) and job['url'] not in state['applications']):
                            candidates.append((score or 0, job, reasons, key))
                    candidates.sort(key=lambda c: -c[0])
                    # One bounded message is a single retry unit.
                    selected, lines = [], ['Your daily career matches', '']
                    for score, job, reasons, key in candidates[:8]:
                        line = f"{job['title'][:100]} — {job['company'][:70]}\n{score}% match · {', '.join(reasons)[:160]}\n{job['url']}\n"
                        if len('\n'.join(lines)) + len(line) > 3600:
                            continue
                        selected.append(key)
                        lines.append(line)
                    if selected:
                        try:
                            sender.send_message(chat_id, '\n'.join(lines), parse_mode=None, disable_web_page_preview=True)
                        except Exception:
                            store.observe('telegram', 'delivery failed; check bot credentials and chat access', now)
                            raise
                        store.receipt([daily, *selected], now)
                        store.observe('telegram', 'delivery succeeded', now)
                        count += 1
            if alerts['followupsEnabled']:
                for key, entry in state['applications'].items():
                    due = entry['followUp']
                    receipt = f'followup:{owner}:' + hashlib.sha256((key + ':' + due).encode()).hexdigest()
                    if not due or due > today or entry['status'] == 'Rejected' or store.seen(receipt):
                        continue
                    try:
                        sender.send_message(chat_id, f"Follow-up reminder ({due})\n{entry['job']['title'][:180]} — {entry['job']['company'][:100]}\nStage: {entry['status']}\n{entry['job']['url'][:1500]}", parse_mode=None, disable_web_page_preview=True)
                    except Exception:
                        store.observe('telegram', 'delivery failed; check bot credentials and chat access', now)
                        raise
                    store.receipt([receipt], now)
                    store.observe('telegram', 'delivery succeeded', now)
                    count += 1
                    if count >= 10:
                        break
            return count


def integration_health(store, root, environ=None, now=None):
    environ = dict(os.environ if environ is None else environ)
    if not environ.get('TELEGRAM_CHAT_ID'):
        try:
            if json.loads((Path(root) / 'chat_id.json').read_text()).get('chat_id'):
                environ['TELEGRAM_CHAT_ID'] = 'saved authorized chat present'
        except (OSError, ValueError, AttributeError):
            pass
    if not environ.get('TELEGRAM_TOKEN'):
        environ['TELEGRAM_TOKEN'] = environ.get('TELEGRAM_BOT_TOKEN', '')
    now = now or datetime.now(UTC)
    observations = store.observations()
    checks = []
    for name, key, names in [('Telegram', 'telegram', ['TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']), ('Gemini', 'gemini', ['GEMINI_API_KEY']), ('Groq', 'groq', ['GROQ_API_KEY']), ('Notion', 'notion', ['NOTION_API_KEY', 'NOTION_DATABASE_ID']), ('Email', 'email', ['BOT_EMAIL', 'BOT_EMAIL_PASSWORD'])]:
        observation = observations.get(key)
        if observation:
            status = 'Last observed result'
            detail = observation['status'] + ' at ' + observation['checked_at'] + '. This is not a current connectivity guarantee.'
        else:
            status = 'Configured, not checked' if all(environ.get(n) for n in names) else 'Configuration incomplete'
            detail = 'Use the existing integration controls to verify access.' if status.startswith('Configured') else 'Set ' + ', '.join(names) + ' on the server; do not enter secrets in the public site.'
        checks.append({'name': name, 'status': status, 'detail': detail})
    worker = observations.get('worker')
    recent = worker and parse_date(worker['checked_at']) and now - parse_date(worker['checked_at']) < timedelta(minutes=3)
    checks.append({'name': 'Career notification worker', 'status': 'Recently active' if recent else 'Not recently observed', 'detail': 'Last tick: ' + (worker['checked_at'] if worker else 'not recorded') + '. Keep the continuous bot running and unpaused for scheduled delivery.'})
    try:
        meta = json.loads((Path(root) / 'tn-live-jobs/data/last-run.json').read_text())
        stamp = meta.get('finished_at') or meta.get('validated_at') or meta.get('failed_at')
        when = parse_date(stamp)
        status = 'Last run failed' if meta.get('status') == 'failed' else ('Recent recorded run' if when and now - when < timedelta(hours=24) else 'Run is stale or undated')
        checks.append({'name': 'Job scraper', 'status': status, 'detail': 'Last recorded run: ' + str(stamp or 'unknown') + '. Review GitHub Actions logs if stale; use existing scrape/verify commands to refresh.'})
    except (OSError, ValueError, TypeError):
        checks.append({'name': 'Job scraper', 'status': 'No run metadata', 'detail': 'Run the existing scraper and verifier to record a feed update.'})
    return {'checks': checks}


def register_routes(app, root, store=None):
    """All routes inherit main.py's dashboard authentication and Origin guard."""
    from flask import jsonify, request, send_from_directory
    store = store or Store()

    @app.route('/api/career/state', methods=['GET', 'POST'])
    def career_state():
        if request.method == 'GET':
            return jsonify(store.read())
        if request.content_length is None or request.content_length > 2000000:
            return jsonify(error='Workspace payload must be under 2 MB.'), 413
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error='Expected JSON object.'), 400
        try:
            return jsonify(store.write(data.get('state'), data.get('revision')))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        except Conflict as error:
            return jsonify(error=str(error)), 409

    @app.route('/api/career/jobs')
    def career_jobs():
        return jsonify(jobs=load_jobs(root))

    @app.route('/api/career/health')
    def career_health():
        return jsonify(integration_health(store, root))

    @app.route('/career-assets/<path:filename>')
    def career_asset(filename):
        if filename not in {'core.js', 'workspace.js', 'workspace.css'}:
            return '', 404
        return send_from_directory(Path(root) / 'docs' / 'career', filename)
