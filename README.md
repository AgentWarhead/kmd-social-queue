# kmd-social-queue

The always-on publisher for Kootenay Made Digital's Instagram account
and Facebook Page. A GitHub Actions cron (every 15 minutes) reads
queue.json and publishes due posts through the Graph API (Facebook
since 2026-09-09). The Action commits queue.json after every run:
always pull before editing it. Cadence: one KMD post a day (Brett,
2026-10-07); the lock lives in tools/brands.py. Images live in images/ and are
served to the API via raw URLs. Captions here are pre-approved public
content; the access token lives ONLY in the repo's Actions secrets.

Every other brand's Facebook is scheduled natively on its own Page with
tools/schedule_facebook.py, in the same session its week is queued. The
cron never posts it. A second Action, Facebook watch (daily, 6 am
Pacific), runs tools/fb_watch.py: every brand feed post due in the next
72 hours must already be scheduled on its Page, matched by Pacific day.
Red means one is missing (The Kootenay Slate went quiet on Facebook from
Nov 17 to 25, 2026, this way).

Queue entry shape:

    {
      "id": "day25-example",
      "publish_at": "2026-07-26T16:30:00Z",
      "image": "images/day25-example.png",
      "caption": "Caption text with hashtags.",
      "status": "pending"
    }

Carousels use "images": ["images/a.png", "images/b.png"] instead of
"image". Times are UTC. Managed by the KMD studio pipeline; posts are
stamped by Brett before they ever enter this queue.

Reels use "video": "images/day30-example.mp4" instead of "image"
(full-bleed 9:16 MP4; the publisher posts it as an Instagram Reel
shared to feed).
