# Stage one week of Global Symphony for a United World's posts from the captions Chantal approved:
# media into media/gsuw-*, Instagram entries into queue.json (with --write), and the Facebook plan into
# gsuw-fb-plan.json for tools/schedule_facebook.py. Captions come verbatim from the GSUW captions files,
# read with the same parser that builds her review PDFs; nothing is rewritten here.
#
#     py tools/stage_gsuw_week.py --week 1            check only
#     py tools/stage_gsuw_week.py --week 1 --write    copy media and append the queue entries
import io, json, os, re, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GSUW = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\KMD Clients\GSUW"
SOC = os.path.join(GSUW, "social")
YEAR = 2026
IG_TIME = "15:30"   # Instagram: the cron lands posts about 1.6 h late, so this reads as late morning Pacific
FB_TIME = "17:00"   # Facebook schedules natively on the minute: 10 am Pacific
STORY_TIME = "18:00"  # stories after the day's post; the per-brand 45 minute floor keeps them apart anyway
STORIES = os.path.join(SOC, "2026-10-Brett-only", "stories")

week = int(sys.argv[sys.argv.index("--week") + 1])
src = io.open(os.path.join(SOC, "build-review.py"), encoding="utf-8").read()
ns = {"__file__": os.path.join(SOC, "build-review.py"), "__name__": "br"}
exec(compile(src[:src.index("def assemble(")], "build-review.py", "exec"), ns)
parse, MEDIA, FULL, IMG = ns["parse"], ns["MEDIA"], ns["FULL"], ns["IMG"]
REELS = os.path.join(SOC, "2026-10-Brett-only", "reels")
MONTHS = {"Oct": 10, "Nov": 11, "Dec": 12}

entries, plan = [], []
os.makedirs(os.path.join(ROOT, "media"), exist_ok=True)
for p in parse(week):
    mon, day = p["date"].split()
    date = "%d-%02d-%02d" % (YEAR, MONTHS[mon], int(day))
    kind, name, _ = MEDIA[p["date"]]
    slug = re.sub(r"[^a-z0-9]+", "-", p["head"].split(" · ")[1].lower()).strip("-")
    pid = "gsuw-%s-%s" % (date, slug)
    if kind == "video":
        srcfile = os.path.join(REELS, FULL[name])
        rel = "media/%s.mp4" % pid
        if os.path.getsize(srcfile) / 1e6 > 19:   # past about 20 MB Instagram's processing can time out
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", srcfile, "-c:v", "libx264", "-crf", "22", "-preset", "slow",
                            "-c:a", "copy", "-movflags", "+faststart", os.path.join(ROOT, rel)], check=True)
        elif "--write" in sys.argv:
            shutil.copy(srcfile, os.path.join(ROOT, rel))
    else:
        srcfile = os.path.join(IMG, name)
        rel = "media/%s.jpg" % pid
        if "--write" in sys.argv:
            shutil.copy(srcfile, os.path.join(ROOT, rel))
    igcap = p["ig"] + "\n\n" + p["ig_tags"]
    fbcap = (p["fb"] if p["fb"] is not None else p["ig"]) + ("\n\n" + p["fb_tags"] if p["fb_tags"] else "")
    e = {"id": pid, "account": "gsuw", "publish_at": "%sT%s:00Z" % (date, IG_TIME), "caption": igcap, "status": "pending",
         "fb_skipped": "scheduled natively on the Global Symphony for a United World page"}
    e["video" if kind == "video" else "image"] = rel
    entries.append(e)
    plan.append({"when": "%sT%s:00Z" % (date, FB_TIME), "file": os.path.join(ROOT, rel) if "--write" in sys.argv else srcfile,
                 "message": fbcap})
    print("%-52s %s  ig tags %d  fb tags %d  %s" % (pid, e["publish_at"], len(re.findall(r"#\w+", igcap)),
                                                   len(re.findall(r"#\w+", fbcap)), kind))

    # The week's stories ride with the post they sit beside: "Story, Sat Oct 24 (...): ...". The story image
    # carries the invitation and gsuw.org, because the API cannot add a link sticker.
    for st in p.get("stories", []):
        sm = re.match(r"Story, \w+ (\w+) (\d+)", st)
        sdate = "%d-%02d-%02d" % (YEAR, MONTHS[sm.group(1)], int(sm.group(2)))
        img = os.path.join(STORIES, "story-%s%02d-soul-journey.jpg" % (sm.group(1).lower(), int(sm.group(2))))
        if not os.path.exists(img):
            raise SystemExit("story image missing: %s" % img)
        sid = "gsuw-%s-story-soul-journey" % sdate
        srel = "media/%s.jpg" % sid
        if "--write" in sys.argv:
            shutil.copy(img, os.path.join(ROOT, srel))
        entries.append({"id": sid, "account": "gsuw", "publish_at": "%sT%s:00Z" % (sdate, STORY_TIME), "story": srel,
                        "caption": "Instagram story, Soul Journey for Women, gsuw.org", "status": "pending",
                        "fb_skipped": "an instagram story; nothing goes to facebook"})
        print("%-52s %s  story" % (sid, entries[-1]["publish_at"]))

json.dump(plan, io.open(os.path.join(ROOT, "gsuw-fb-plan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if "--write" in sys.argv:
    q = json.load(io.open(os.path.join(ROOT, "queue.json"), encoding="utf-8"))
    have = {x["id"] for x in q}
    q.extend(e for e in entries if e["id"] not in have)
    json.dump(q, io.open(os.path.join(ROOT, "queue.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("queue.json: +%d entries" % len([e for e in entries if e["id"] not in have]))
