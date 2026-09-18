# -*- coding: utf-8 -*-
"""Which brand a post belongs to, and how many posts a day each brand is locked to.

Born 2026-09-17 when Lapphund Designs joined this queue. One token now reaches two brands, so the
only things standing between a post and the wrong feed are these definitions and the gates that read
them (validate_queue.py before every push, verify_live.py after scheduling, and the same markers
mirrored in publish.mjs at posting time). Brett's law: a post on the wrong account is never acceptable,
and each brand posts exactly its locked number per day, with no extra posts and no missed days.

A brand's post must carry at least one of its own markers and none of any other brand's. There is no
override flag on purpose: a cross-brand mention is a change to this file, made on purpose.
"""
from datetime import datetime, timedelta, timezone

BRANDS = {
    'kmd': {
        'name': 'Kootenay Made Digital',
        'ig_id': '17841446312533398', 'ig_username': 'kootenaymadedigital',
        'page_id': '1001276889744302',
        'markers': ['#kootenaymade', 'kootenaymade.ca'],
        'image_prefix': None,                 # anything except another brand's prefix
        'posts_per_day': 2,                   # Brett, 2026-09-17: two a day
    },
    'lapphund': {
        'name': 'Lapphund Designs',
        'ig_id': '17841459350887730', 'ig_username': 'lapphunddesigns',
        'page_id': '109874835456732',
        'markers': ['lapphunddesigns.com', '#lapphunddesigns'],
        'image_prefix': 'images/ld-',
        'posts_per_day': 2,                   # Brett, 2026-09-17: two a day, one lifestyle post and one Halloween product
    },
}


def brand_problems(account, text, image=None):
    """Every reason this post cannot belong to `account`. Empty means it can."""
    if account not in BRANDS:
        return ['unknown account "%s"' % account]
    low = (text or '').lower()
    out = []
    mine = BRANDS[account]
    if not any(m in low for m in mine['markers']):
        out.append('carries none of the %s markers (%s)' % (mine['name'], ', '.join(mine['markers'])))
    for other, b in BRANDS.items():
        if other == account:
            continue
        hit = [m for m in b['markers'] if m in low]
        if hit:
            out.append('carries %s markers: %s' % (b['name'], ', '.join(hit)))
        if image and b['image_prefix'] and image.replace('\\', '/').startswith(b['image_prefix']):
            out.append('uses a %s image: %s' % (b['name'], image))
    if image and mine['image_prefix'] and not image.replace('\\', '/').startswith(mine['image_prefix']):
        out.append('image is not a %s image (%s...): %s' % (mine['name'], mine['image_prefix'], image))
    return out


def _nth_sunday(year, month, n):
    d = datetime(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def pacific_date(when):
    """The calendar day in Pacific time. The day is what the cadence lock counts, and a UTC date would
    move a late evening post onto tomorrow. This PC has no tz database, so the DST rule is written out:
    daylight time from 2 am on the second Sunday of March to 2 am on the first Sunday of November."""
    if isinstance(when, str):
        when = datetime.fromisoformat(when.replace('Z', '+00:00'))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    u = when.astimezone(timezone.utc).replace(tzinfo=None)
    start = _nth_sunday(u.year, 3, 2) + timedelta(hours=10)     # 2 am PST is 10:00 UTC
    end = _nth_sunday(u.year, 11, 1) + timedelta(hours=9)       # 2 am PDT is 09:00 UTC
    offset = -7 if start <= u < end else -8
    return (u + timedelta(hours=offset)).date()


def cadence_problems(account, dates):
    """dates: the Pacific day of every post that is out or on its way for this brand. Across the span from
    the first to the last day, each day must hold exactly the locked number."""
    lock = BRANDS[account]['posts_per_day']
    if lock is None or not dates:
        return []
    count = {}
    for d in dates:
        count[d] = count.get(d, 0) + 1
    out = []
    day, last = min(count), max(count)
    while day <= last:
        n = count.get(day, 0)
        if n != lock:
            out.append('%s on %s: %d post%s, locked to %d a day (%s)' % (
                BRANDS[account]['name'], day.isoformat(), n, '' if n == 1 else 's', lock,
                'missed day' if n < lock else 'overposting'))
        day += timedelta(days=1)
    return out
