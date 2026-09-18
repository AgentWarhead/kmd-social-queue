# -*- coding: utf-8 -*-
"""The live gate: read back what is actually scheduled and posted, per brand, and check it.

    py tools/verify_live.py [--since 2026-09-17]

validate_queue.py checks what we intend to post. This checks what Meta actually holds, because a gate on
intent cannot see a post that went out some other way. For every brand in brands.py:

  Facebook  every scheduled post on the brand's Page carries that brand's markers and no other brand's,
            and the scheduled days hold exactly the locked number of posts per day.
  Instagram every post on the brand's feed since --since carries that brand's markers and no other
            brand's, every complete day since the brand's first post there holds exactly the locked
            number, and every queue entry marked published for this brand is on THIS feed.

Exits 1 on any problem with each one named; prints PASS with counts otherwise. Read-only.
"""
import io
import json
import os
import sys
from datetime import date, datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from brands import BRANDS, brand_problems, pacific_date, cadence_problems
import meta_local

SINCE = date.fromisoformat(sys.argv[sys.argv.index('--since') + 1]) if '--since' in sys.argv else date(2026, 9, 17)
today = pacific_date(datetime.now(timezone.utc))
fails, notes = [], []
queue = json.load(io.open(os.path.join(ROOT, 'queue.json'), encoding='utf-8'))

for account, b in BRANDS.items():
    # Facebook: what is waiting on the Page
    tok = meta_local.page_token(b['page_id'])
    sched = meta_local.get('%s/scheduled_posts' % b['page_id'], tok,
                           fields='id,message,scheduled_publish_time', limit=100).get('data', [])
    fb_days = []
    for p in sched:
        when = datetime.fromtimestamp(int(p['scheduled_publish_time']), timezone.utc)
        for why in brand_problems(account, p.get('message', '')):
            fails.append('facebook %s scheduled %s (%s): WRONG ACCOUNT RISK, %s' % (b['name'], when.isoformat(), p['id'], why))
        fb_days.append(pacific_date(when))
    fails.extend('facebook ' + c for c in cadence_problems(account, fb_days))
    notes.append('%s facebook: %d scheduled%s' % (b['name'], len(sched),
                 (', %s to %s' % (min(fb_days), max(fb_days))) if fb_days else ''))

    # Instagram: what is on the feed
    # page back until the feed is older than --since, so a busy feed never hides a post past the first page
    media, page = [], meta_local.get('%s/media' % b['ig_id'], fields='id,caption,timestamp,username', limit=50)
    while True:
        media += page.get('data', [])
        nxt = (page.get('paging') or {}).get('cursors', {}).get('after')
        if not nxt or not page.get('data') or pacific_date(page['data'][-1]['timestamp']) < SINCE:
            break
        page = meta_local.get('%s/media' % b['ig_id'], fields='id,caption,timestamp,username', limit=50, after=nxt)
    recent = [m for m in media if pacific_date(m['timestamp']) >= SINCE]
    ig_days = []
    for m in recent:
        if m.get('username') and m['username'] != b['ig_username']:
            fails.append('instagram %s: post %s reports owner @%s' % (b['name'], m['id'], m['username']))
        for why in brand_problems(account, m.get('caption', '')):
            fails.append('instagram %s post %s (%s): WRONG ACCOUNT, %s' % (b['name'], m['id'], m['timestamp'], why))
        ig_days.append(pacific_date(m['timestamp']))
    done = [d for d in ig_days if d < today]              # today may still be on its way
    fails.extend('instagram ' + c for c in cadence_problems(account, done))
    if b['posts_per_day'] and ig_days.count(today) > b['posts_per_day']:
        fails.append('instagram %s: %d posts today, locked to %d (overposting)' % (b['name'], ig_days.count(today), b['posts_per_day']))
    ids = {m['id'] for m in media}
    for e in queue:
        if e.get('status') == 'published' and e.get('account', 'kmd') == account and e.get('media_id') \
                and pacific_date(e['publish_at']) >= SINCE and e['media_id'] not in ids:
            fails.append('instagram %s: queue entry %s says published as %s, which is not on this feed' % (b['name'], e['id'], e['media_id']))
    notes.append('%s instagram: %d posts since %s' % (b['name'], len(recent), SINCE))

if fails:
    print('FAIL (%d):' % len(fails))
    for f in fails:
        print('  ' + f)
    sys.exit(1)
print('PASS: every scheduled and published post is on its own brand, and every locked cadence holds')
for n in notes:
    print('  ' + n)
