# Stage The Kootenay List's two weeks from 2026-10-15 from the stamped slate. Posts are added as Brett
# stamps them, so POSTS lists only stamped posts. Media goes into media/kl-*, Instagram entries into
# queue.json (with --write), and the Facebook plan into list-fb-plan.json for schedule_facebook.py.
# Captions come verbatim from the slate; nothing is rewritten here. The slate carries one tag line per
# post: Instagram takes all five, Facebook takes the first (the place tag) only.
import io, json, os, re, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLATE = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\Kootenay List\social\2026-10-15-two-weeks.md"
STILLS = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\Kootenay List\social\stills\2026-10-15"
FILMS = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\Kootenay List\social\films"
POSTS = [  # (slate number, date, UTC time, id, source file, kind). Stamped by Brett 2026-10-14 (stills, the two Your Town films, then the two Drawers).
    (1, '2026-10-15', '16:00', 'kl-2026-10-15-money-farm-deadlines', os.path.join(STILLS, 'kl-2026-10-15-money-farm-deadlines.jpg'), 'image'),
    (2, '2026-10-16', '16:00', 'kl-2026-10-16-your-town-nelson', os.path.join(FILMS, '2026-10-16-your-town-nelson.mp4'), 'video'),
    (3, '2026-10-19', '16:00', 'kl-2026-10-19-drawer-creston', os.path.join(FILMS, '2026-10-19-drawer-creston.mp4'), 'video'),
    (4, '2026-10-20', '16:00', 'kl-2026-10-20-data-common-kinds', os.path.join(STILLS, 'kl-2026-10-20-data-common-kinds.jpg'), 'image'),
    (5, '2026-10-21', '16:00', 'kl-2026-10-21-claim-banjo', os.path.join(STILLS, 'kl-2026-10-21-claim-banjo.jpg'), 'image'),
    (6, '2026-10-22', '16:00', 'kl-2026-10-22-keep-sources', os.path.join(STILLS, 'kl-2026-10-22-keep-sources.jpg'), 'image'),
    (7, '2026-10-23', '16:00', 'kl-2026-10-23-your-town-castlegar', os.path.join(FILMS, '2026-10-23-your-town-castlegar.mp4'), 'video'),
    (8, '2026-10-26', '16:00', 'kl-2026-10-26-drawer-kimberley-bakeries', os.path.join(FILMS, '2026-10-26-drawer-kimberley-bakeries.mp4'), 'video'),
    (10, '2026-10-28', '16:00', 'kl-2026-10-28-open-doors', os.path.join(STILLS, 'kl-2026-10-28-open-doors.jpg'), 'image'),
]
slate = io.open(SLATE, encoding='utf-8').read()
# --from / --through YYYY-MM-DD stage only the stamped posts inside that window, so Facebook's cadence gate sees no
# empty weekday between them while later posts (the films) are still being built.
if '--through' in sys.argv:
    LAST = sys.argv[sys.argv.index('--through') + 1]
    POSTS = [p for p in POSTS if p[1] <= LAST]
if '--from' in sys.argv:
    FIRST = sys.argv[sys.argv.index('--from') + 1]
    POSTS = [p for p in POSTS if p[1] >= FIRST]


def section(n):
    for s in re.split(r'\n## ', slate):
        if s.startswith('%d. ' % n):
            m = re.search(r'\*\*Caption:\*\*\n\n(.*?)\n\n\*\*Tags:\*\* (.*?)\n', s, re.S)
            return m.group(1).strip(), m.group(2).strip()
    raise SystemExit('no section %d' % n)


entries, plan = [], []
os.makedirs(os.path.join(ROOT, 'media'), exist_ok=True)
for n, day, hm, pid, src, kind in POSTS:
    cap, tags = section(n)
    assert '\u2014' not in cap, pid
    ntags = len(re.findall(r'#\w+', tags))
    assert ntags == 5, '%s has %d tags' % (pid, ntags)
    ext = '.mp4' if kind == 'video' else '.jpg'
    rel = 'media/%s%s' % (pid, ext)
    dst = os.path.join(ROOT, rel)
    if kind == 'video':
        mb = os.path.getsize(src) / 1e6
        if mb > 19:  # reels past about 20 MB risk Instagram's processing timeout
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-c:v', 'libx264', '-crf', '22', '-preset', 'slow', '-c:a', 'copy', '-movflags', '+faststart', dst], check=True)
        else:
            shutil.copy(src, dst)
    else:
        shutil.copy(src, dst)
    igcap = cap + '\n.\n.\n' + tags
    fbcap = cap + '\n\n' + tags.split()[0]
    when = '%sT%s:00Z' % (day, hm)
    e = {'id': pid, 'account': 'list', 'publish_at': when, 'caption': igcap, 'status': 'pending',
         'fb_skipped': 'scheduled natively on The Kootenay List page'}
    e['video' if kind == 'video' else 'image'] = rel
    entries.append(e)
    plan.append({'when': when, 'file': dst, 'message': fbcap})
    print('%-40s %s %5.1f MB  ig tags %d  fb tag %s' % (pid, when, os.path.getsize(dst) / 1e6, ntags, tags.split()[0]))

json.dump(plan, io.open(os.path.join(ROOT, 'list-fb-plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if '--write' in sys.argv:
    q = json.load(io.open(os.path.join(ROOT, 'queue.json'), encoding='utf-8'))
    have = {x['id'] for x in q}
    q.extend(e for e in entries if e['id'] not in have)
    json.dump(q, io.open(os.path.join(ROOT, 'queue.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('queue.json: +%d entries' % len([e for e in entries if e['id'] not in have]))
