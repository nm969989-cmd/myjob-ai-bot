"""All-category Tamil Nadu results, explicit dates and one CSV instead of flooding chat."""
import csv
import io
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from career_service import normalize, expired, parse_date, UTC


def collect(root, days=7, now=None):
    if type(days) is not int or not 1 <= days <= 90:
        raise ValueError('Choose 1–90 days.')
    now = now or datetime.now(UTC)
    aliases = json.loads((Path(root)/'tn-live-jobs/src/city-aliases.json').read_text())
    pattern = re.compile(r'\b(?:'+'|'.join(re.escape(v) for values in aliases.values() for v in values)+r')\b', re.I)
    jobs, seen, undated = [], set(), set()
    for name in ('tn-live-jobs/public/data/jobs.json','radar_results.json'):
        try:
            payload=json.loads((Path(root)/name).read_text()); rows=payload if isinstance(payload,list) else payload.get('jobs',[])
        except (OSError, ValueError):continue
        for raw in rows:
            j=normalize(raw)
            if not j['url'] or j['url'] in seen or not pattern.search(j['city']) or expired(j,now) or j['checkStatus']=='failed':continue
            posted=parse_date(j['postedAt'])
            if not posted:
                undated.add(j['url']);continue
            if posted.date()>now.date() or now-posted>timedelta(days=days):continue
            seen.add(j['url']); undated.discard(j['url'])
            j['region']='Puducherry (separate UT)' if re.search(r'\b(puducherry|pondicherry|pondi)\b',j['city'],re.I) else 'Tamil Nadu'
            jobs.append(j)
    jobs.sort(key=lambda j:j['postedAt'],reverse=True)
    return jobs, len(undated)


def csv_bytes(jobs):
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['Role','Company','Location','Region','Posted','Salary','Last checked','Check status','Job link'])
    for j in jobs:
        values=[j['title'],j['company'],j['city'],j['region'],j['postedAt'],j['salary'],j['verifiedAt'],j['checkStatus'],j['url']]
        writer.writerow(["'"+v if v.lstrip().startswith(('=','+','-','@')) else v for v in values])
    return out.getvalue().encode('utf-8-sig')


def send(sender, chat_id, root, days=7):
    jobs, unknown=collect(root,days)
    caption=f'Tamil Nadu job search: {len(jobs)} dated listings from the last {days} days. All categories in available feeds; not exhaustive. Puducherry is labeled separately. {unknown} undated listings excluded. Links may change availability.'
    document=io.BytesIO(csv_bytes(jobs));document.name='tamil-nadu-jobs.csv'
    sender.send_document(chat_id,document,caption=caption)
    return len(jobs)
