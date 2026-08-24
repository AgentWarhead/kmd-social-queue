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
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []

try:
    q = json.load(io.open(os.path.join(ROOT, 'queue.json'), encoding='utf-8-sig'))
except Exception as e:
    print('FAIL: queue.json does not parse: %s' % e)
    sys.exit(1)

now = datetime.now(timezone.utc)
pending = [e for e in q if e.get('status') == 'pending']

KILL = re.compile(r'\b(financing|loan|installments?|interest|rent-to-own|down payment)\b', re.I)

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

    cap = e.get('caption', '')
    tags = re.findall(r'#\w+', cap)
    if len(tags) != 5:
        fails.append('%s: %d hashtags, law says exactly 5' % (eid, len(tags)))
    elif tags[-1] != '#KootenayMade':
        fails.append('%s: #KootenayMade is not the last tag' % eid)
    if '—' in cap:
        fails.append('%s: em dash in caption' % eid)
    m = KILL.search(cap)
    if m:
        fails.append('%s: kill-list word "%s"' % (eid, m.group(1)))

if fails:
    print('FAIL (%d):' % len(fails))
    for f in fails:
        print('  ' + f)
    sys.exit(1)

print('PASS: %d entries, %d pending, all future-dated with media present and captions lawful' % (len(q), len(pending)))
