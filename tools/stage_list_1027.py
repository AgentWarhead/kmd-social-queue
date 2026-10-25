# Stage The Kootenay List's two weeks from 2026-10-27 (Tue Oct 27 to Mon Nov 9), stamped by Brett 2026-10-24.
# Same machinery as stage_list_1015.py: media into media/kl-*, Instagram entries into queue.json (with
# --write), the Facebook plan into list-fb-plan.json for schedule_facebook.py. Captions verbatim from the
# slate. Post 2 (open doors) was stamped in the 2026-10-15 slate and takes its caption from there. Reels
# carry their designed cover (Instagram only). 9:00 am Pacific throughout: 16:00 UTC until clocks fall
# back on Nov 1, 17:00 UTC after.
import io, json, os, re, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIST = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\Kootenay List\social"
SLATE = os.path.join(LIST, '2026-10-27-two-weeks.md')
OLD = os.path.join(LIST, '2026-10-15-two-weeks.md')
STILLS = os.path.join(LIST, 'stills', '2026-10-27')
FILMS = os.path.join(LIST, 'films')
POSTS = [  # (slate, section number, date, UTC time, id, source file, kind, cover)
    (SLATE, 1, '2026-10-27', '16:00', 'kl-2026-10-27-data-new-this-month', os.path.join(STILLS, 'kl-2026-10-27-data-new-this-month.jpg'), 'image', None),
    (OLD, 10, '2026-10-28', '16:00', 'kl-2026-10-28-open-doors', os.path.join(LIST, 'stills', '2026-10-15', 'kl-2026-10-28-open-doors.jpg'), 'image', None),
    (SLATE, 3, '2026-10-29', '16:00', 'kl-2026-10-29-drawer-trail-tires', os.path.join(STILLS, 'kl-2026-10-29-drawer-trail-tires.jpg'), 'image', None),
    (SLATE, 4, '2026-10-30', '16:00', 'kl-2026-10-30-drawer-sparwood-butchers', os.path.join(FILMS, '2026-10-30-drawer-sparwood-butchers.mp4'), 'video', os.path.join(FILMS, '2026-10-30-drawer-sparwood-butchers-cover.jpg')),
    (SLATE, 5, '2026-11-02', '17:00', 'kl-2026-11-02-data-busiest-small-towns', os.path.join(STILLS, 'kl-2026-11-02-data-busiest-small-towns.jpg'), 'image', None),
    (SLATE, 6, '2026-11-03', '17:00', 'kl-2026-11-03-drawer-grand-forks-heating', os.path.join(STILLS, 'kl-2026-11-03-drawer-grand-forks-heating.jpg'), 'image', None),
    (SLATE, 7, '2026-11-04', '17:00', 'kl-2026-11-04-drawer-kaslo-cafes', os.path.join(FILMS, '2026-11-04-drawer-kaslo-cafes.mp4'), 'video', os.path.join(FILMS, '2026-11-04-drawer-kaslo-cafes-cover.jpg')),
    (SLATE, 8, '2026-11-05', '17:00', 'kl-2026-11-05-data-gift-shops', os.path.join(STILLS, 'kl-2026-11-05-data-gift-shops.jpg'), 'image', None),
    (SLATE, 9, '2026-11-06', '17:00', 'kl-2026-11-06-drawer-rossland-ski', os.path.join(STILLS, 'kl-2026-11-06-drawer-rossland-ski.jpg'), 'image', None),
    (SLATE, 10, '2026-11-09', '17:00', 'kl-2026-11-09-drawer-towing', os.path.join(STILLS, 'kl-2026-11-09-drawer-towing.jpg'), 'image', None),
]
TEXT = {p: io.open(p, encoding='utf-8').read() for p in (SLATE, OLD)}
# --from / --through YYYY-MM-DD stage only the posts inside that window.
if '--through' in sys.argv:
    LAST = sys.argv[sys.argv.index('--through') + 1]
    POSTS = [p for p in POSTS if p[2] <= LAST]
if '--from' in sys.argv:
    FIRST = sys.argv[sys.argv.index('--from') + 1]
    POSTS = [p for p in POSTS if p[2] >= FIRST]


def section(path, n):
    for s in re.split(r'\n## ', TEXT[path]):
        if s.startswith('%d. ' % n):
            m = re.search(r'\*\*Caption:\*\*\n\n(.*?)\n\n\*\*Tags:\*\* (.*?)\n', s, re.S)
            return m.group(1).strip(), m.group(2).strip()
    raise SystemExit('no section %d in %s' % (n, path))


entries, plan = [], []
os.makedirs(os.path.join(ROOT, 'media'), exist_ok=True)
for path, n, day, hm, pid, src, kind, cover in POSTS:
    cap, tags = section(path, n)
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
    if cover:
        crel = 'media/%s-cover.jpg' % pid
        shutil.copy(cover, os.path.join(ROOT, crel))
        e['cover'] = crel
    entries.append(e)
    plan.append({'when': when, 'file': dst, 'message': fbcap})
    print('%-42s %s %5.1f MB  ig tags %d  fb tag %s%s' % (pid, when, os.path.getsize(dst) / 1e6, ntags, tags.split()[0], '  +cover' if cover else ''))

json.dump(plan, io.open(os.path.join(ROOT, 'list-fb-plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if '--write' in sys.argv:
    q = json.load(io.open(os.path.join(ROOT, 'queue.json'), encoding='utf-8'))
    have = {x['id'] for x in q}
    q.extend(e for e in entries if e['id'] not in have)
    json.dump(q, io.open(os.path.join(ROOT, 'queue.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('queue.json: +%d entries' % len([e for e in entries if e['id'] not in have]))
