"""Queue the Kootenay Helpers foundation week (Brett, 2026-11-20: "go looks great please schedule").
Copies each asset into media/ under the Helpers prefix, adds pending Instagram entries to queue.json,
and writes fb-plan.json for tools/schedule_facebook.py. Never touches a published entry.
8 am Pacific is 15:00Z (BC stays on UTC-7)."""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "staging-helpers-foundation")
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

feed("kh-2026-11-22-launch-reel", "2026-11-22T15:00:00Z", cap("d1"),
     video=media(os.path.join(W, "reels", "d1.mp4"), "kh-2026-11-22-launch-reel.mp4"),
     cover=media(os.path.join(W, "reels", "d1-cover.jpg"), "kh-2026-11-22-launch-reel-cover.jpg"))
feed("kh-2026-11-23-post-a-role-reel", "2026-11-23T15:00:00Z", cap("d2"),
     video=media(os.path.join(W, "reels", "d2.mp4"), "kh-2026-11-23-post-a-role-reel.mp4"),
     cover=media(os.path.join(W, "reels", "d2-cover.jpg"), "kh-2026-11-23-post-a-role-reel-cover.jpg"))
feed("kh-2026-11-24-find-a-role", "2026-11-24T15:00:00Z", cap("d3"), images=slides("d3", 5, "2026-11-24-find-a-role"))
feed("kh-2026-11-25-where-roles-come-from", "2026-11-25T15:00:00Z", cap("d4"), images=slides("d4", 5, "2026-11-25-where-roles-come-from"))
feed("kh-2026-11-26-who-can-post", "2026-11-26T15:00:00Z", cap("d5"), images=slides("d5", 4, "2026-11-26-who-can-post"))
feed("kh-2026-11-27-what-your-group-gets", "2026-11-27T15:00:00Z", cap("d6"), images=slides("d6", 5, "2026-11-27-what-your-group-gets"))
feed("kh-2026-11-28-questions", "2026-11-28T15:00:00Z", cap("d7"), images=slides("d7", 7, "2026-11-28-questions"))

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
