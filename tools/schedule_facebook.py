# -*- coding: utf-8 -*-
"""Schedule a brand's Facebook posts natively on its own Page.

    py tools/schedule_facebook.py <plan.json> --account lapphund [--go]

plan.json is a list of {"when": ISO UTC time, "file": local image path, "message": text}. Facebook
schedules natively through the API, so these never touch the cron queue.

Without --go it only checks. With --go it checks, schedules, then reads the Page back. It refuses to
schedule anything unless every post passes the brand gate for --account and the plan, together with what
is already scheduled on that Page, holds exactly the brand's locked number of posts per day. The Page is
taken from brands.py by account, never from the plan, so a plan cannot name the wrong Page.
"""
import io
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from brands import BRANDS, brand_problems, pacific_date, cadence_problems
import meta_local

plan_path = sys.argv[1]
account = sys.argv[sys.argv.index('--account') + 1]
GO = '--go' in sys.argv
if account not in BRANDS:
    raise SystemExit('unknown account %s' % account)
brand = BRANDS[account]
plan = json.load(io.open(plan_path, encoding='utf-8'))
tok = meta_local.page_token(brand['page_id'])
existing = meta_local.get('%s/scheduled_posts' % brand['page_id'], tok,
                          fields='id,message,scheduled_publish_time', limit=100).get('data', [])

fails = []
now = datetime.now(timezone.utc)
for i, p in enumerate(plan):
    when = datetime.fromisoformat(p['when'].replace('Z', '+00:00'))
    mins = (when - now).total_seconds() / 60
    if not 10 < mins < 30 * 24 * 60:
        fails.append('post %d at %s: Facebook schedules 10 minutes to 30 days ahead' % (i + 1, p['when']))
    if not os.path.exists(p['file']):
        fails.append('post %d: image missing %s' % (i + 1, p['file']))
    for why in brand_problems(account, p['message']):
        fails.append('post %d: WRONG ACCOUNT RISK for %s, %s' % (i + 1, brand['name'], why))
days = [pacific_date(p['when']) for p in plan] + \
       [pacific_date(datetime.fromtimestamp(int(e['scheduled_publish_time']), timezone.utc)) for e in existing]
fails.extend(cadence_problems(account, days))
if fails:
    print('REFUSED (%d):' % len(fails))
    for f in fails:
        print('  ' + f)
    sys.exit(1)
print('checks pass: %d posts for %s, %d already scheduled there' % (len(plan), brand['name'], len(existing)))
if not GO:
    print('dry run; add --go to schedule')
    sys.exit(0)

for i, p in enumerate(plan):
    when = int(datetime.fromisoformat(p['when'].replace('Z', '+00:00')).timestamp())
    data = open(p['file'], 'rb').read()
    # an unpublished photo, then one scheduled feed post that attaches it. Meta's docs say temporary=true for
    # this; with only the Content task on a Page it is refused as "no permission to create an unpublished
    # post" (2026-09-17, Lapphund Designs), while the same upload without it succeeds and schedules fine.
    ph = meta_local.post_file('%s/photos' % brand['page_id'], tok, 'source', os.path.basename(p['file']), data,
                              published='false')
    r = meta_local.post('%s/feed' % brand['page_id'], tok, message=p['message'], published='false',
                        scheduled_publish_time=str(when),
                        **{'attached_media[0]': json.dumps({'media_fbid': ph['id']})})
    print('scheduled %d/%d  %s  %s' % (i + 1, len(plan), pacific_date(p['when']), r['id']))

after = meta_local.get('%s/scheduled_posts' % brand['page_id'], tok,
                       fields='id,message,scheduled_publish_time', limit=100).get('data', [])
print('read back: %d scheduled on %s' % (len(after), brand['name']))
