# -*- coding: utf-8 -*-
"""Social watch: every brand has posts coming, and every brand's Facebook is scheduled.

    py tools/social_watch.py [--days 5] [--hours 72] [--queue queue.json]

Two checks, read only, one daily run. Exit 1 on any problem, so the run turns red and GitHub emails the boss.

  Runway    for every brand, each of the next --days Pacific days holds the brand's locked number of feed
            posts in the queue (stories do not count). An empty day means nothing goes to Instagram OR
            Facebook that day, so it is caught days ahead, while there is still time to stage a week.
  Facebook  every brand but KMD posts to Facebook through tools/schedule_facebook.py, not the cron, and
            its queue entries only say so in fb_skipped. Each brand feed post due in the next --hours must
            already sit scheduled on its Page that Pacific day (The Kootenay Slate went quiet on Facebook
            from Nov 17 to 25, 2026, this way). By day, not by minute: some brands schedule Facebook at
            10 am while Instagram goes earlier.

Instagram publishing itself is not checked here: publish.mjs turns its own run red when any post is 20
minutes past its slot. Nothing here posts.
"""
import io
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from brands import BRANDS, pacific_date, posts_allowed
import meta_local


def arg(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


DAYS = int(arg('--days', 5))
HOURS = int(arg('--hours', 72))
QUEUE = arg('--queue', os.path.join(ROOT, 'queue.json'))
SOON_MIN = 15    # Facebook will not schedule closer than 10 minutes, so nearer posts cannot be fixed anyway
LIVE = ('pending', 'published')

now = datetime.now(timezone.utc)
today = pacific_date(now)
when = lambda s: datetime.fromisoformat(s.replace('Z', '+00:00'))
queue = json.load(io.open(QUEUE, encoding='utf-8'))
feed = [e for e in queue if not e.get('story') and e.get('status') in LIVE]
account_of = lambda e: e.get('account') or 'kmd'
problems = []

# Runway: tomorrow through DAYS days out. Today is the publisher's own late alarm.
print('Runway, the next %d days' % DAYS)
for account, brand in BRANDS.items():
    if brand.get('since') and brand['since'] > (today + timedelta(days=DAYS)).isoformat():
        continue
    count = {}
    for e in feed:
        if account_of(e) == account:
            d = pacific_date(e['publish_at'])
            count[d] = count.get(d, 0) + 1
    short = []
    for i in range(1, DAYS + 1):
        d = today + timedelta(days=i)
        want = posts_allowed(account, d)
        if want and count.get(d, 0) < want:
            short.append('%s %s (%d of %d)' % (d.strftime('%a'), d.isoformat(), count.get(d, 0), want))
    last = max((d for d in count if d >= today), default=None)
    print('  %s: %s, queued through %s' % (brand['name'], 'short ' + ', '.join(short) if short else 'full',
                                          last.isoformat() if last else 'nothing'))
    problems.extend('%s: nothing queued for %s' % (brand['name'], s) for s in short)

# Facebook: brand feed posts due in the window must be scheduled on their own Page.
print('Facebook, posts due in the next %dh' % HOURS)
start, end = now + timedelta(minutes=SOON_MIN), now + timedelta(hours=HOURS)
due = {}
for e in feed:
    if account_of(e) != 'kmd' and e['status'] == 'pending' and start <= when(e['publish_at']) <= end:
        due.setdefault(account_of(e), []).append(e)
for account, entries in sorted(due.items()):
    brand = BRANDS[account]
    try:
        tok = meta_local.page_token(brand['page_id'])
        sched = meta_local.get('%s/scheduled_posts' % brand['page_id'], tok,
                               fields='id,scheduled_publish_time', limit=100).get('data', [])
    except (Exception, SystemExit) as err:
        problems.append('%s: could not read its Page (%s)' % (brand['name'], str(err)[:120]))
        continue
    days = [pacific_date(datetime.fromtimestamp(int(s['scheduled_publish_time']), timezone.utc)) for s in sched]
    gaps = []
    for e in sorted(entries, key=lambda e: e['publish_at']):
        day = pacific_date(e['publish_at'])
        if day in days:
            days.remove(day)
        else:
            gaps.append('%s %s' % (day, e['id']))
    print('  %s: %d of %d scheduled' % (brand['name'], len(entries) - len(gaps), len(entries)))
    problems.extend('%s: not scheduled on Facebook, %s' % (brand['name'], g) for g in gaps)
if not due:
    print('  no brand feed posts due')

if problems:
    print('PROBLEMS (%d). Stage the week, or schedule its Facebook: '
          'py tools/schedule_facebook.py <plan> --account <brand> --go' % len(problems))
    for p in problems:
        print('  ' + p)
    sys.exit(1)
print('clean')
