"""Dated Tamil Nadu feed search and bounded Telegram CSV delivery; no scraping."""
import argparse
import csv
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from career_service import normalize, expired, parse_date, UTC

IST = ZoneInfo('Asia/Kolkata')
FEEDS = ('tn-live-jobs/public/data/jobs.json', 'radar_results.json')


class FeedUnavailable(ValueError):
    """No usable feed was read; distinct from a successful zero-result search."""


def _pattern(values):
    return re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(v) for v in values) + r')(?!\w)', re.I)


def search(root, days=7, city=None, now=None):
    if type(days) is not int or not 1 <= days <= 90:
        raise ValueError('Choose 1–90 days.')
    now = now or datetime.now(UTC)
    today = now.astimezone(IST).date()
    first_day = today - timedelta(days=days - 1)
    aliases = json.loads((Path(root) / 'tn-live-jobs/src/city-aliases.json').read_text())
    region_pattern = _pattern([v for values in aliases.values() for v in values])
    city_pattern = None
    if city:
        city = city.strip()
        canonical = next((name for name, values in aliases.items() if city.casefold() in [name.casefold(), *(v.casefold() for v in values)]), None)
        if not canonical:
            raise ValueError('Unknown city. Use a Tamil Nadu city or district, or Puducherry.')
        city = canonical
        city_pattern = _pattern(aliases[canonical])
    sources, candidates = [], {}
    malformed = 0
    for name in FEEDS:
        try:
            payload = json.loads((Path(root) / name).read_text(encoding='utf-8-sig'))
            rows = payload if isinstance(payload, list) else payload.get('jobs') if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError('Expected a jobs array')
        except (OSError, ValueError):
            sources.append({'name': name, 'status': 'unavailable', 'records': 0})
            continue
        sources.append({'name': name, 'status': 'loaded', 'records': len(rows)})
        for raw in rows:
            if not isinstance(raw, dict):
                malformed += 1
                continue
            j = normalize(raw)
            if not j['url']:
                malformed += 1
                continue
            j['source'] = str(raw.get('source') or name)[:200]
            # Latest recorded availability observation wins across copies of a URL.
            checked = parse_date(j['verifiedAt'])
            checked = checked if checked and checked <= now else datetime.min.replace(tzinfo=UTC)
            previous = candidates.get(j['url'])
            tie = (j['closed'] or j['checkStatus'] == 'failed', bool(parse_date(j['postedAt'])))
            rank = (checked, tie)
            if previous is None:
                candidates[j['url']] = (rank, j)
            else:
                winner_rank, winner, other = (rank, j, previous[1]) if rank > previous[0] else (previous[0], previous[1], j)
                # A newer link-check record can omit the job's descriptive fields.
                # Keep metadata without replacing its latest availability evidence.
                for key in ('title', 'company', 'city', 'description', 'skills', 'salary', 'experience', 'postedAt', 'deadline'):
                    if not winner[key] or winner[key] in ('Untitled opportunity', 'Company not stated'):
                        winner[key] = other[key]
                candidates[j['url']] = (winner_rank, winner)
    if not any(s['status'] == 'loaded' for s in sources):
        raise FeedUnavailable('Job feeds are unavailable. Refresh the scraper feeds before searching.')
    jobs, unknown, excluded = [], 0, 0
    for _, j in candidates.values():
        if not region_pattern.search(j['city']) or (city_pattern and not city_pattern.search(j['city'])):
            continue
        if expired(j, now) or j['checkStatus'] == 'failed':
            excluded += 1
            continue
        posted = parse_date(j['postedAt'])
        if posted is None:
            unknown += 1
            continue
        # Date-only source values are local calendar dates, never fabricated times.
        day_only = len(j['postedAt']) == 10
        posted_day = posted.date() if day_only else posted.astimezone(IST).date()
        if not first_day <= posted_day <= today or (not day_only and posted > now):
            continue
        j['region'] = 'Puducherry (separate UT)' if _pattern(['puducherry', 'pondicherry', 'pondi']).search(j['city']) else 'Tamil Nadu'
        jobs.append(j)
    jobs.sort(key=lambda j: (parse_date(j['postedAt']), j['title'], j['url']), reverse=True)
    return dict(jobs=jobs, undated=unknown, excluded=excluded, malformed=malformed,
                sources=sources, city=city or 'All configured locations', days=days,
                from_date=first_day.isoformat(), to_date=today.isoformat(),
                timezone='Asia/Kolkata', generated_at=now.isoformat())


def collect(root, days=7, now=None):
    result = search(root, days, now=now)
    return result['jobs'], result['undated']


def csv_bytes(jobs):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(['Role', 'Company', 'Location', 'Region', 'Posted', 'Salary', 'Last checked', 'Check status', 'Source', 'Job link'])
    for j in jobs:
        values = [j['title'], j['company'], j['city'], j['region'], j['postedAt'], j['salary'], j['verifiedAt'], j['checkStatus'], j.get('source', ''), j['url']]
        writer.writerow(["'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    return out.getvalue().encode('utf-8-sig')


def send(sender, chat_id, root, days=7, city=None):
    result = search(root, days, city)
    jobs = result['jobs']
    missing = sum(s['status'] != 'loaded' for s in result['sources'])
    caption = (f"Tamil Nadu search: {len(jobs)} listings · {result['city']}\n"
               f"{result['from_date']} to {result['to_date']} (IST calendar dates)\n"
               f"{result['undated']} undated excluded; {missing} feed(s) unavailable.\n"
               "All available categories; partial coverage. Reads saved feeds, not a new scrape. "
               "Puducherry labeled separately. Recorded checks are not current vacancy guarantees.")
    for job in jobs[:3]:
        line = f"\n\n{job['title'][:70]} — {job['company'][:50]}\n{job['url']}"
        if len(caption + line) <= 1000:
            caption += line
    document = io.BytesIO(csv_bytes(jobs))
    document.name = 'tamil-nadu-jobs.csv'
    sender.send_document(chat_id, document, caption=caption, parse_mode=None)
    return len(jobs)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export available Tamil Nadu feeds; does not scrape or send messages.')
    parser.add_argument('--days', type=int, default=7)
    parser.add_argument('--city')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = search(Path(__file__).parent, args.days, args.city)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(csv_bytes(result['jobs']))
        print(json.dumps({k: v for k, v in result.items() if k != 'jobs'} | {'count': len(result['jobs'])}))
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')
