# -*- coding: utf-8 -*-
"""The enqueue gate. Run before EVERY push that touches queue.json:

    py tools/validate_queue.py

Born 2026-08-24 after a slate built on the 22nd was enqueued on the
24th with its dates unchanged; the idempotent publisher then fired all
five backdated posts in one morning. The publisher is correct to fire
anything past due, so the gate lives here: nothing pending may carry a
publish_at in the past, and while we are here, every entry gets the
mechanical checks a stamped slate must already have passed.

Exits 1 with named failures; prints PASS with counts otherwise.
"""
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from brands import BRANDS, brand_problems, pacific_date, cadence_problems
fails = []

# --queue <file> checks another queue against this repo's media: how the red controls prove each check fires.
QUEUE = sys.argv[sys.argv.index('--queue') + 1] if '--queue' in sys.argv else os.path.join(ROOT, 'queue.json')
try:
    q = json.load(io.open(QUEUE, encoding='utf-8-sig'))
except Exception as e:
    print('FAIL: queue.json does not parse: %s' % e)
    sys.exit(1)

now = datetime.now(timezone.utc)
pending = [e for e in q if e.get('status') == 'pending']

# A post the publisher gave up on. It kept retrying for two days and the
# content went stale, so a human has to decide: re-date it, rewrite it, or
# cancel it. Silence here would let one quietly rot in the queue.
missed = [e for e in q if e.get('status') == 'missed']

KILL = re.compile(r'\b(financing|loan|installments?|interest|rent-to-own|down payment)\b', re.I)

# The publisher does not read media off this disk. It hands Instagram a
# raw.githubusercontent URL, so a file that exists locally and was never
# committed is a 404 at publish time, and a post that dies three times.
# os.path.exists is the wrong question on its own.
try:
    TRACKED = set(subprocess.check_output(
        ['git', 'ls-files'], cwd=ROOT, text=True).replace(os.sep, '/').split('\n'))
except Exception as exc:
    TRACKED = None
    print('WARNING: could not read the git index (%s), so the committed check is skipped' % exc)

# Instagram caps a caption at 2200 characters.
CAPTION_MAX = 2200

for e in pending:
    eid = e.get('id', '<no id>')
    try:
        t = datetime.fromisoformat(e['publish_at'].replace('Z', '+00:00'))
        if t <= now:
            fails.append('%s: publish_at %s is in the past (the misfire law)' % (eid, e['publish_at']))
    except Exception:
        fails.append('%s: publish_at unparseable: %r' % (eid, e.get('publish_at')))

    media = e.get('images') or ([e['image']] if e.get('image') else []) or ([e['video']] if e.get('video') else [])
    if not media:
        fails.append('%s: no media' % eid)
    for m in media:
        if not os.path.exists(os.path.join(ROOT, m)):
            fails.append('%s: media file missing: %s' % (eid, m))
        elif TRACKED is not None and m.replace(os.sep, '/') not in TRACKED:
            fails.append('%s: media on disk but NOT COMMITTED, so it will 404 '
                         'when the publisher fetches it: %s' % (eid, m))

    cap = e.get('caption', '')
    if len(cap) > CAPTION_MAX:
        fails.append('%s: caption is %d characters, Instagram caps it at %d'
                     % (eid, len(cap), CAPTION_MAX))
    # The wrong-account gate (Brett, 2026-09-17: never, under any circumstances). The brand is read from the
    # post itself, its markers and its image, and must agree with the account it is queued for.
    account = e.get('account', 'kmd')
    for why in brand_problems(account, cap, (media or [None])[0]):
        fails.append('%s: WRONG ACCOUNT RISK, queued for %s but %s' % (eid, account, why))
    for m in media[1:]:
        for why in brand_problems(account, cap, m):
            if 'image' in why:
                fails.append('%s: WRONG ACCOUNT RISK, %s' % (eid, why))
    if account != 'kmd' and not e.get('fb_skipped'):
        fails.append('%s: a %s post must carry fb_skipped, or the publisher would try KMD facebook' % (eid, account))
    tags = re.findall(r'#\w+', cap)
    if len(tags) != 5:
        fails.append('%s: %d hashtags, law says exactly 5' % (eid, len(tags)))
    elif account == 'kmd' and tags[-1] != '#KootenayMade':
        fails.append('%s: #KootenayMade is not the last tag' % eid)
    elif account != 'kmd' and '#KootenayMade' in tags:
        fails.append('%s: #KootenayMade on a %s post' % (eid, account))
    if '—' in cap:
        fails.append('%s: em dash in caption' % eid)
    m = KILL.search(cap)
    if m:
        fails.append('%s: kill-list word "%s"' % (eid, m.group(1)))

# The cadence lock: every post that is out or on its way, per brand, per Pacific day. Published posts count
# too, so a queue cannot add a second post to a day that already had its one.
live = [e for e in q if e.get('status') in ('pending', 'published')]
for account in BRANDS:
    mine = [e for e in live if e.get('account', 'kmd') == account]
    todo = [e for e in mine if e.get('status') == 'pending']
    if not todo:
        continue
    first = min(pacific_date(e['publish_at']) for e in todo)
    days = [pacific_date(e['publish_at']) for e in mine if pacific_date(e['publish_at']) >= first]
    fails.extend(cadence_problems(account, days))

for e in missed:
    fails.append('%s: status "missed", the publisher gave up after %d attempts (%s). '
                 'Re-date it, rewrite it, or set status "cancelled".'
                 % (e.get('id'), e.get('attempts', 0), e.get('error', 'no error recorded')))

if fails:
    print('FAIL (%d):' % len(fails))
    for f in fails:
        print('  ' + f)
    sys.exit(1)

# Not a failure, a warning: the cron fires every 1.7 to 5.8 hours, so two
# slots closer than that land in the same window and the second one drifts.
times = sorted(datetime.fromisoformat(e['publish_at'].replace('Z', '+00:00'))
               for e in pending)
tight = [(a, b) for a, b in zip(times, times[1:])
         if (b - a).total_seconds() / 3600 < 4.5]
for a, b in tight:
    print('WARNING: %s and %s are %.1f h apart, inside the cron jitter window'
          % (a.strftime('%m-%d %H:%M'), b.strftime('%H:%M'),
             (b - a).total_seconds() / 3600))

per = ', '.join('%s %d' % (a, sum(1 for e in pending if e.get('account', 'kmd') == a)) for a in BRANDS)
locks = ', '.join('%s %s' % (a, b['posts_per_day'] or 'NO LOCK SET') for a, b in BRANDS.items())
print('PASS: %d entries, %d pending (%s), every post on its own brand, cadence per day: %s' % (len(q), len(pending), per, locks))
