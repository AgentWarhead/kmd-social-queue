"""Queue the Slate's stamped week three (Brett, 2026-11-26: "Stamp the week").

    py staging-slate-week3/enqueue.py --sweep     the dupe sweep only, with its red control
    py staging-slate-week3/enqueue.py --media     copy the media into media/ (commit and push it first)
    py staging-slate-week3/enqueue.py --queue     add the entries to queue.json
"""
import hashlib, io, json, os, re, shutil, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, "staging-slate-week3"); OUT = os.path.join(W, "out")
FB = "scheduled natively on The Kootenay Slate page"; FB_STORY = "an instagram story; nothing goes to facebook"
caps = io.open(os.path.join(W, "captions.md"), encoding="utf-8").read()


def cap(head):
    m = re.search(r"## " + re.escape(head) + r"[^\n]*\n\n(.*?)(?=\n\nAlt text|\n## |\Z)", caps, re.S)
    if not m: sys.exit("no caption for " + head)
    return m.group(1).strip()


flip_cap = io.open(os.path.join(W, "reel-flip", "caption.txt"), encoding="utf-8").read().strip()
COPY = []   # (source, media name)


def media(src, name):
    COPY.append((src, name)); return "media/" + name


E = []
def feed(eid, when, caption, **m): E.append({"id": eid, "account": "slate", "publish_at": when, **m, "caption": caption, "status": "pending", "fb_skipped": FB})
def story(eid, when, src, label): E.append({"id": eid, "account": "slate", "publish_at": when, "story": media(src, eid + ".jpg"), "caption": label, "status": "pending", "fb_skipped": FB_STORY})


feed("ks-2026-12-03-cranbrook-tonight", "2026-12-03T17:00:00Z", cap("Thu Dec 3"),
     image=media(os.path.join(OUT, "thu-1.jpg"), "ks-2026-12-03-cranbrook-tonight.jpg"))
feed("ks-2026-12-04-flip-reel", "2026-12-04T17:00:00Z", flip_cap,
     video=media(os.path.join(W, "reel-flip", "reel.mp4"), "ks-2026-12-04-flip-reel.mp4"),
     cover=media(os.path.join(W, "reel-flip", "reel-cover.jpg"), "ks-2026-12-04-flip-reel-cover.jpg"))
story("ks-2026-12-05-rock-creek-market-story", "2026-12-05T15:00:00Z", os.path.join(OUT, "story-sat-1.jpg"), "42nd Annual Rock Creek Christmas Market, today #kootenayslate")
story("ks-2026-12-05-kaslo-light-up-story", "2026-12-05T19:30:00Z", os.path.join(OUT, "story-sat-2.jpg"), "Kaslo Light Up! Christmas Parade and Tree Lighting, tonight #kootenayslate")
story("ks-2026-12-06-contra-dance-story", "2026-12-06T15:00:00Z", os.path.join(OUT, "story-sun.jpg"), "Kootenay Community Contra Barn Dance, tonight in Nelson #kootenayslate")
feed("ks-2026-12-07-eight-papers", "2026-12-07T17:00:00Z", cap("Mon Dec 7"),
     images=[media(os.path.join(OUT, f"mon-{i}.jpg"), f"ks-2026-12-07-eight-papers-{i:02d}.jpg") for i in range(1, 9)])
feed("ks-2026-12-08-your-poster", "2026-12-08T17:00:00Z", cap("Tue Dec 8"),
     image=media(os.path.join(OUT, "tue-1.jpg"), "ks-2026-12-08-your-poster.jpg"))
feed("ks-2026-12-09-christmas-posters", "2026-12-09T17:00:00Z", cap("Wed Dec 9"),
     image=media(os.path.join(OUT, "wed-1.jpg"), "ks-2026-12-09-christmas-posters.jpg"))

qp = os.path.join(ROOT, "queue.json"); q = json.load(io.open(qp, encoding="utf-8"))
toks = lambda s: set(re.findall(r"[a-z0-9']+", s.lower()))
sim = lambda a, b: len(toks(a) & toks(b)) / max(1, min(len(toks(a)), len(toks(b))))
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()

if "--sweep" in sys.argv:
    old = [e for e in q if e.get("account") == "slate" and e["publish_at"] >= "2026-11-05" and not e.get("story")]
    fails = []
    # red control: a caption against itself must trip the similarity line
    if sim(E[0]["caption"], E[0]["caption"]) < 0.5: sys.exit("the sweep cannot fail: its red control passed")
    for e in E:
        if e.get("story"): continue
        for o in old + [x for x in E if x is not e and not x.get("story")]:
            s = sim(e["caption"], o["caption"])
            if s > 0.5: fails.append("%s vs %s: captions %.0f%% alike" % (e["id"], o["id"], s * 100))
            if e["caption"].split("\n")[0].strip() == o["caption"].split("\n")[0].strip(): fails.append("%s reuses the hook line of %s" % (e["id"], o["id"]))
    have = {}
    for name in os.listdir(os.path.join(ROOT, "media")):
        if name.startswith("ks-2026-1"): have[sha(os.path.join(ROOT, "media", name))] = name
    seen = {}
    for src, name in COPY:
        h = sha(src)
        if h in have and have[h] != name: fails.append("%s is byte-identical to media/%s" % (name, have[h]))
        if h in seen: fails.append("%s is byte-identical to %s" % (name, seen[h]))
        seen[h] = name
    worst = max((sim(e["caption"], o["caption"]), e["id"], o["id"]) for e in E if not e.get("story") for o in old)
    print("closest pair: %.0f%% alike, %s vs %s" % (worst[0] * 100, worst[1], worst[2]))
    if fails:
        print("DUPES (%d):" % len(fails)); [print("  " + f) for f in fails]; sys.exit(1)
    print("sweep clean: %d new feed posts against %d Slate posts since Nov 5, %d media files" % (sum(1 for e in E if not e.get("story")), len(old), len(COPY)))
    sys.exit(0)

if "--media" in sys.argv:
    for src, name in COPY: shutil.copyfile(src, os.path.join(ROOT, "media", name))
    print("copied %d files into media/" % len(COPY)); sys.exit(0)

if "--queue" in sys.argv:
    have = {e["id"] for e in q}; dupe = [e["id"] for e in E if e["id"] in have]
    if dupe: sys.exit("already queued: " + ", ".join(dupe))
    q.extend(E)
    f = io.open(qp, "w", encoding="utf-8", newline="\n"); json.dump(q, f, ensure_ascii=False, indent=2); f.write("\n"); f.close()
    for e in E: print(e["publish_at"], e["id"], len(e["caption"].split()), "words")
    sys.exit(0)
print(__doc__)
