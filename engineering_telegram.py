"""Engineering-search companion. One Telegram poller only; no application submissions.
Private saved searches/profile live outside the checkout. Importing this module sends nothing.
"""
import argparse
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def node_executable():
    """Resolve the operator-installed runtime, never a chat/profile-supplied command."""
    installed = shutil.which('node')
    if installed is None:
        raise FileNotFoundError('Node runtime is required')
    executable = Path(installed).resolve(strict=True)
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise PermissionError('Node runtime must be an executable file')
    return str(executable)

# Subprocess audit: only this absolute runtime and a fixed checkout script execute.
# Profile data goes through JSON stdin, never argv or a shell. PATH and checkout
# are trusted operator configuration; production must not make them user-writable.

STATE = Path(os.environ.get('ENGINEERING_STATE_DIR', str(Path.home() / '.myjob-search'))) / 'state.json'
LOCK = threading.RLock()
DEFAULT = {'configured': False, 'branch': None, 'skills': [], 'experience_years': None,
           'travel_radius_km': 0, 'cities': ['Tiruvannamalai', 'Vellore', 'Puducherry', 'Chennai'],
           'roles': ['software engineer', 'developer', 'backend', 'full-stack', 'data engineer', 'python']}

def load_state():
    if not STATE.exists():
        return {'profile': dict(DEFAULT), 'searches': {}, 'seen': {}}
    data = json.loads(STATE.read_text(encoding='utf8'))
    if not isinstance(data, dict):
        raise TypeError('Invalid private search state; refusing to overwrite it')
    return data

def save_state(data):
    STATE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = STATE.with_suffix('.tmp')
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf8') as out:
        json.dump(data, out, ensure_ascii=False)
    os.replace(tmp, STATE)
    os.chmod(STATE, 0o600)

def run_node(flag=None, payload=None, timeout=20):
    """Fixed executable/script/options; all user data is inert JSON on stdin."""
    if flag not in (None, '--query'):
        raise ValueError('Unsupported engineering operation')
    argv = [node_executable(), str(ROOT / 'tn-live-jobs/src/engineering.js')]
    if flag is not None:
        argv.append(flag)
    return subprocess.run(argv, input=json.dumps(payload) if payload is not None else None,
                          text=True, capture_output=payload is not None, shell=False,
                          cwd=ROOT, timeout=timeout, check=True)

def query(profile):
    return json.loads(run_node('--query', {'profile': profile}).stdout)

def refresh():
    run_node(timeout=600)

def parse_profile(raw, existing):
    p = dict(existing)
    for pair in raw.split(';'):
        if not pair.strip():
            continue
        key, value = (v.strip() for v in pair.split('=', 1))
        if key == 'branch': p['branch'] = value[:80] or None
        elif key == 'skills': p['skills'] = [v.strip()[:40] for v in value.split(',') if v.strip()][:30]
        elif key == 'experience': p['experience_years'] = None if value.lower() == 'unknown' else float(value)
        elif key == 'radius': p['travel_radius_km'] = float(value)
        else: raise ValueError('Use branch, skills, experience, radius only')
    if not 0 <= p['travel_radius_km'] <= 300: raise ValueError('Radius must be 0-300 km')
    exp = p['experience_years']
    if exp is not None and not 0 <= exp <= 50: raise ValueError('Experience must be unknown or 0-50 years')
    p['configured'] = True
    return p

def search_profile(base, role, city):
    p = dict(base)
    p['roles'] = [role.strip()[:80]]
    p['cities'] = [city.strip()[:80]]
    return p

def scan_age(result):
    date = datetime.fromisoformat(result['generated_at'].replace('Z', '+00:00'))
    return (datetime.now(timezone.utc) - date).total_seconds()

def visible_jobs(result, jobs):
    # Bound every card before rendering; acknowledge only cards actually shown.
    if scan_age(result) > 48 * 3600:
        return []
    out = []
    budget = 900  # header and section labels, including an unusually long search name
    for job in jobs[:6]:
        url = str(job.get('apply_url', ''))
        if len(url) > 600:
            continue  # do not truncate a link into a broken destination
        if job.get('match', {}).get('integrity') not in ('verified', 'uncertain'):
            continue
        size = 650 + len(url)
        if budget + size > 3800:
            break
        out.append(job)
        budget += size
    return out

def digest_text(name, result, unseen):
    profile = result['preset']
    header = f"Engineering matches — {name}\nLast scan: {result['generated_at']}\n"
    if not profile.get('configured'):
        header += 'DEFAULT: software/data roles; branch, skills and experience unknown. Radius 0 km.\n'
    else:
        header += 'Saved profile; fit score is not an eligibility guarantee.\n'
    header += 'Distance is approximate city-centre distance, not travel time.\n'
    if scan_age(result) > 48 * 3600:
        return header + 'Scan older than 48h: no current verified matches claimed. Refresh required.'
    selected = visible_jobs(result, unseen)
    if not selected:
        return header + 'No new matches in the available scan (not proof of no openings).'
    sections = []
    for state in ('verified', 'uncertain'):
        group = [j for j in selected if j.get('match', {}).get('integrity') == state]
        if not group: continue
        sections.append('Evidence-verified' if state == 'verified' else 'Uncertain — check before applying')
        for j in group:
            sections.append(f"• {str(j.get('title',''))[:110]} — {str(j.get('company',''))[:60]} | {str(j.get('city','unknown'))[:60]}\n"
                            f"Source: {str(j.get('source','unknown'))[:80]} | posted: {str(j.get('posted_at') or 'unknown')[:40]}\n"
                            f"Check: {str(j.get('verify_reason','not_checked'))[:80]} | fit: {j['match']['score']}\n"
                            f"{j.get('apply_url','')}")
    return (header + '\n'.join(sections))[:3900]

def dispatch(bot, owner, new_only=True):
    with LOCK:
        state = load_state()
        searches = state.get('searches') or {'default': {'role': None, 'city': None}}
        sent = 0
        items = list(searches.items())
        cursor = int(state.get('cursor', 0)) % len(items)
        rotation = (items[cursor:] + items[:cursor])[:4]
        state['cursor'] = (cursor + len(rotation)) % len(items)
        save_state(state)
        for name, criteria in rotation:
            profile = state.get('profile', dict(DEFAULT))
            if criteria.get('role'): profile = search_profile(profile, criteria['role'], criteria['city'])
            result = query(profile)
            seen = set(state.setdefault('seen', {}).get(name, []))
            fresh = [j for j in result['jobs'] if f"{j['id']}:{j['match']['integrity']}" not in seen]
            if new_only and not fresh: continue
            if scan_age(result) > 48*3600 and new_only: continue
            shown = visible_jobs(result, fresh if new_only else result['jobs'])
            message = digest_text(name, result, shown)
            bot.send_message(owner, message, parse_mode=None, disable_web_page_preview=True)
            # Failed sends leave cards unseen; only rendered cards are acknowledged.
            sent += 1
            if scan_age(result) <= 48*3600:
                seen.update(f"{j['id']}:{j['match']['integrity']}" for j in shown)
                state['seen'][name] = sorted(seen)[-1000:]
                save_state(state)
        return sent

def save_search(bot, owner, state, raw):
    name, role, city_name = [v.strip() for v in raw.split('|')]
    if not name or len(name) > 40:
        raise ValueError('Name must be 1-40 characters')
    if name not in state['searches'] and len(state['searches']) >= 10:
        raise ValueError('At most 10 saved searches')
    query(search_profile(state['profile'], role, city_name))
    state['searches'][name] = {'role': role[:80], 'city': city_name[:80]}
    state['seen'].pop(name, None)
    save_state(state)
    bot.send_message(owner, f'Saved {name}: {role} | {city_name}. New-match digest after scans.', parse_mode=None)

def install_handlers(bot, owner):
    def authorised(m):
        return str(m.chat.id) == str(owner) and m.chat.type == 'private'

    @bot.message_handler(commands=['esearch', 'save_search', 'searches', 'remove_search', 'engineering_profile', 'refresh_search'])
    def handle(m):
        if not authorised(m): return
        parts = m.text.split(maxsplit=1)
        command = parts[0].split('@')[0][1:]
        raw = parts[1] if len(parts) > 1 else ''
        try:
            with LOCK:
                state = load_state()
                if command == 'engineering_profile':
                    if raw:
                        state['profile'] = parse_profile(raw, state.get('profile', dict(DEFAULT)))
                        save_state(state)
                    bot.send_message(owner, 'Private profile: ' + json.dumps(state['profile']) +
                                     '\nSet: /engineering_profile branch=...;skills=python,sql;experience=unknown;radius=0\nUnknown fields stay unknown; radius is not travel time.', parse_mode=None)
                elif command == 'save_search':
                    save_search(bot, owner, state, raw)
                elif command == 'searches':
                    bot.send_message(owner, 'Saved searches:\n' + json.dumps(state['searches'], ensure_ascii=False) +
                                     '\n/save_search name | backend | Chennai\n/esearch python | Vellore\n/remove_search name', parse_mode=None)
                elif command == 'remove_search':
                    state['searches'].pop(raw.strip(), None); state['seen'].pop(raw.strip(), None)
                    save_state(state); bot.send_message(owner, 'Saved search removed.', parse_mode=None)
                elif command == 'esearch':
                    role, city_name = [v.strip() for v in raw.split('|')]
                    result = query(search_profile(state['profile'], role, city_name))
                    bot.send_message(owner, digest_text(f'{role} | {city_name}', result, result['jobs']), parse_mode=None,
                                     disable_web_page_preview=True)
                else:
                    bot.send_message(owner, 'Refreshing bounded public sources; this does not submit applications.', parse_mode=None)
                    refresh(); dispatch(bot, owner, new_only=False)
        except Exception as exc:
            # Deliberate external-provider command boundary: SDK/source failures
            # have no closed exception taxonomy. Report failure without secrets;
            # never acknowledge unseen cards or overwrite rejected private state.
            # KeyboardInterrupt/SystemExit (BaseException) are not swallowed.
            # Never include tokens or command subprocess stdout in a chat error.
            bot.send_message(owner, f'Search could not complete ({type(exc).__name__}). Check configuration/logs; no improved coverage is claimed.', parse_mode=None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--digest-only', action='store_true')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(override=False)
    token = os.environ.get('TELEGRAM_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    owner = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not owner or owner.startswith('-'): raise SystemExit('Private owner chat and Telegram token are required')
    import telebot
    bot = telebot.TeleBot(token, parse_mode=None)
    if args.refresh: refresh()
    if args.digest_only:
        print(f'Engineering digest messages acknowledged: {dispatch(bot, owner)}')
        return
    install_handlers(bot, owner)
    def cycle():
        while True:
            try:
                with LOCK: refresh(); dispatch(bot, owner)
            except Exception as exc:
                # Deliberate worker boundary: record SDK/source failure and keep
                # the scheduler alive; no failed delivery is acknowledged.
                print(f'Engineering scan/delivery failed: {type(exc).__name__}', flush=True)
            time.sleep(max(900, int(os.environ.get('ENGINEERING_INTERVAL_SECONDS', '3600'))))
    threading.Thread(target=cycle, name='EngineeringSearch', daemon=True).start()
    # Run instead of another bot poller; do not change/delete webhooks automatically.
    bot.infinity_polling(timeout=30, long_polling_timeout=30)

if __name__ == '__main__': main()
