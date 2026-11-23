"""Queue the Kootenay Helpers second week (Brett, 2026-11-22: "stamped week 2").
Copies each asset into media/ under the Helpers prefix, adds pending Instagram entries to queue.json,
and writes fb-plan.json for tools/schedule_facebook.py. Never touches a published entry.
8 am Pacific is 15:00Z (BC stays on UTC-7)."""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "staging-helpers-week2")
FB = "scheduled natively on the Kootenay Helpers page"
caps = open(os.path.join(W, "captions.md"), encoding="utf-8").read()

def cap(key):
    m = re.search(r"^## " + re.escape(key) + r" [^\n]*\n\n(.*?)(?=\n## |\Z)", caps, re.S | re.M)
    if not m:
        sys.exit("no caption for " + key)
    return m.group(1).strip()

def media(src, name):
    if not os.path.exists(src):
        sys.exit("missing " + src)
    shutil.copyfile(src, os.path.join(ROOT, "media", name))
    return "media/" + name

entries, fb = [], []
def feed(eid, when, caption, **m):
    entries.append({"id": eid, "account": "helpers", "publish_at": when, **m, "caption": caption,
                    "status": "pending", "fb_skipped": FB})
    first = m.get("video") or m.get("image") or m["images"][0]
    plan = {"when": when, "file": first, "message": caption}
    if m.get("images"):
        plan["files"] = m["images"]
    fb.append(plan)

def slides(day, n, slug):
    return [media(os.path.join(W, "out", day, f"{day}-{i:02d}.jpg"), f"kh-{slug}-{i:02d}.jpg") for i in range(1, n + 1)]

feed("kh-2026-11-29-why-i-built-it", "2026-11-29T15:00:00Z", cap("w1"), images=slides("w1", 5, "2026-11-29-why-i-built-it"))
feed("kh-2026-11-30-after-you-post", "2026-11-30T15:00:00Z", cap("w2"), images=slides("w2", 6, "2026-11-30-after-you-post"))
feed("kh-2026-12-01-quilt-reel", "2026-12-01T15:00:00Z", cap("w3"),
     video=media(os.path.join(W, "reels", "w3.mp4"), "kh-2026-12-01-quilt-reel.mp4"),
     cover=media(os.path.join(W, "reels", "w3-cover.jpg"), "kh-2026-12-01-quilt-reel-cover.jpg"))
feed("kh-2026-12-02-be-the-somebody", "2026-12-02T15:00:00Z", cap("w4"), image=media(os.path.join(W, "out", "w4", "w4-01.jpg"), "kh-2026-12-02-be-the-somebody.jpg"))
feed("kh-2026-12-03-know-a-group", "2026-12-03T15:00:00Z", cap("w5"), images=slides("w5", 3, "2026-12-03-know-a-group"))
feed("kh-2026-12-04-tomorrow", "2026-12-04T15:00:00Z", cap("w6"), image=media(os.path.join(W, "out", "w6", "w6-01.jpg"), "kh-2026-12-04-tomorrow.jpg"))
FILM = os.path.join(ROOT, "staging-helpers-intro", "film")
feed("kh-2026-12-05-volunteer-day-film", "2026-12-05T15:00:00Z", cap("w7"),
     video=media(os.path.join(FILM, "intro-9x16.mp4"), "kh-2026-12-05-volunteer-day-film.mp4"),
     cover=media(os.path.join(FILM, "poster-9x16.jpg"), "kh-2026-12-05-volunteer-day-film-cover.jpg"))

qp = os.path.join(ROOT, "queue.json")
q = json.load(open(qp, encoding="utf-8"))
have = {e["id"] for e in q}
dupe = [e["id"] for e in entries if e["id"] in have]
if dupe:
    sys.exit("already queued: " + ", ".join(dupe))
q.extend(entries)
json.dump(q, open(qp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(qp, "a", encoding="utf-8").write("\n")
json.dump(fb, open(os.path.join(W, "fb-plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("queued", len(entries))
for e in entries:
    print(e["publish_at"], e["id"], len(e["caption"].split()), "words")
