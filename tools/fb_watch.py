# -*- coding: utf-8 -*-
"""Facebook watch: every brand post due soon must already sit scheduled on its own Page.

    py tools/fb_watch.py [--hours 72]

Every brand but KMD posts to Facebook through tools/schedule_facebook.py, not the cron queue. Its queue
entries only say so in fb_skipped, so a week that was queued for Instagram and never scheduled on the
Page goes quiet on Facebook with nothing turning red (The Kootenay Slate, Nov 17 to 25, 2026). This reads
each Page's scheduled posts and matches them by Pacific day against the queue's feed posts due in the
window. By day, not by minute: some brands schedule Facebook at 10 am while Instagram goes earlier.
It only reads; it never posts. Exit 1 when any post is missing, so the daily run turns red and GitHub
emails the boss.
"""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from brands import BRANDS, pacific_date
import meta_local

HOURS = int(sys.argv[sys.argv.index('--hours') + 1]) if '--hours' in sys.argv else 72
QUEUE = sys.argv[sys.argv.index('--queue') + 1] if '--queue' in sys.argv else os.path.join(ROOT, 'queue.json')
SOON_MIN = 15    # Facebook will not schedule closer than 10 minutes, so nearer posts cannot be fixed anyway

now = datetime.now(timezone.utc)
start, end = now + timedelta(minutes=SOON_MIN), now + timedelta(hours=HOURS)
when = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))

due = {}
for e in json.load(io.open(QUEUE, encoding='utf-8')):
    account = e.get('account') or 'kmd'
    if account == 'kmd' or e.get('story') or e.get('status') != 'pending':
        continue
    if start <= when(e['publish_at']) <= end:
        due.setdefault(account, []).append(e)

missing = []
for account, entries in sorted(due.items()):
    brand = BRANDS[account]
    try:
        tok = meta_local.page_token(brand['page_id'])
        sched = meta_local.get('%s/scheduled_posts' % brand['page_id'], tok,
                               fields='id,scheduled_publish_time', limit=100).get('data', [])
    except (Exception, SystemExit) as err:
        missing.append('%s: could not read its Page (%s)' % (brand['name'], str(err)[:120]))
        continue
    days = [pacific_date(datetime.fromtimestamp(int(s['scheduled_publish_time']), timezone.utc)) for s in sched]
    gaps = []
    for e in sorted(entries, key=lambda e: e['publish_at']):
        day = pacific_date(e['publish_at'])
        if day in days:
            days.remove(day)
        else:
            gaps.append('%s %s' % (day, e['id']))
    if gaps:
        missing.extend('%s: not scheduled on Facebook, %s' % (brand['name'], g) for g in gaps)
    print('%s: %d of %d due in %dh scheduled on Facebook' % (brand['name'], len(entries) - len(gaps),
                                                             len(entries), HOURS))

if not due:
    print('no brand feed posts due in the next %dh' % HOURS)
if missing:
    print('MISSING (%d). Schedule them: py tools/schedule_facebook.py <plan> --account <brand> --go' % len(missing))
    for m in missing:
        print('  ' + m)
    sys.exit(1)
print('clean')
