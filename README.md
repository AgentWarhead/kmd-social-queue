# kmd-social-queue

The always-on Instagram publisher for Kootenay Made Digital. A GitHub
Actions cron (every 15 minutes) reads queue.json and publishes due
posts through the Instagram Graph API. Images live in images/ and are
served to the API via raw URLs. Captions here are pre-approved public
content; the access token lives ONLY in the repo's Actions secrets.

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
