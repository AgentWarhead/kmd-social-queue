# Stage The Kootenay List's two weeks (2026-09-30 to 10-13) from the stamped slate: media into media/kl-*,
# Instagram entries into queue.json (with --write), and the Facebook plan into list-fb-plan.json.
# Captions come verbatim from the slate file; nothing is rewritten here.
import io, json, os, re, shutil, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLATE = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\Kootenay List\social\2026-09-30-two-weeks.md"
FILMS = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\Kootenay List\social\films"
STILLS = r"C:\Users\bfauc\Desktop\Kootenay Made Digital\remotion-lab\out\listweek"
POSTS = [  # (slate number, date, UTC time, id, source file, kind)
    (1, '2026-09-30', '17:00', 'kl-2026-09-30-money-four-offices', os.path.join(FILMS, '2026-09-30-the-money-four-offices-v4.mp4'), 'video'),
    (2, '2026-10-01', '16:00', 'kl-2026-10-01-how-i-keep-it-funding', os.path.join(STILLS, 'StillHolders.png'), 'image'),
    (3, '2026-10-02', '16:00', 'kl-2026-10-02-your-town-fernie', os.path.join(FILMS, 'YourTownFernie.mp4'), 'video'),
    (4, '2026-10-05', '16:00', 'kl-2026-10-05-drawer-crawford-bay', os.path.join(FILMS, 'DrawerCrawfordBay.mp4'), 'video'),
    (5, '2026-10-06', '16:00', 'kl-2026-10-06-data-103-ways', os.path.join(STILLS, 'StillWays.png'), 'image'),
    (6, '2026-10-07', '16:00', 'kl-2026-10-07-money-who-it-is-for', os.path.join(FILMS, 'MoneyWhoItIsFor.mp4'), 'video'),
    (7, '2026-10-08', '16:00', 'kl-2026-10-08-claim', os.path.join(STILLS, 'StillClaim.png'), 'image'),
    (8, '2026-10-09', '16:00', 'kl-2026-10-09-your-town-invermere', os.path.join(FILMS, 'YourTownInvermere.mp4'), 'video'),
    (9, '2026-10-12', '16:00', 'kl-2026-10-12-drawer-cranbrook-gear', os.path.join(FILMS, 'DrawerCranbrook.mp4'), 'video'),
    (10, '2026-10-13', '16:00', 'kl-2026-10-13-data-58-towns', os.path.join(STILLS, 'StillTowns.png'), 'image'),
]
slate = io.open(SLATE, encoding='utf-8').read()

def section(n):
    for s in re.split(r'\n## ', slate):
        if s.startswith('%d. ' % n):
            m = re.search(r'\*\*Caption:\*\*\n\n(.*?)\n\n\*\*Instagram tags:\*\* (.*?)\n\*\*Facebook tags:\*\* (.*?)\n', s, re.S)
            return m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
    raise SystemExit('no section %d' % n)

entries, plan = [], []
os.makedirs(os.path.join(ROOT, 'media'), exist_ok=True)
for n, day, hm, pid, src, kind in POSTS:
    cap, ig, fb = section(n)
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
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-q:v', '2', dst], check=True)
    igcap = cap + '\n.\n.\n' + ig
    fbcap = cap + ('' if fb.lower() == 'none' or fb.startswith('none') else '\n\n' + re.sub(r'\s*\(.*\)$', '', fb))
    when = '%sT%s:00Z' % (day, hm)
    e = {'id': pid, 'account': 'list', 'publish_at': when, 'caption': igcap, 'status': 'pending',
         'fb_skipped': 'scheduled natively on The Kootenay List page'}
    e['video' if kind == 'video' else 'image'] = rel
    entries.append(e)
    plan.append({'when': when, 'file': dst, 'message': fbcap})
    print('%-40s %s %5.1f MB  ig tags %d  fb: %s' % (pid, when, os.path.getsize(dst) / 1e6, len(re.findall(r'#\w+', igcap)), fbcap.splitlines()[-1][:40]))

json.dump(plan, io.open(os.path.join(ROOT, 'list-fb-plan.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
if '--write' in sys.argv:
    q = json.load(io.open(os.path.join(ROOT, 'queue.json'), encoding='utf-8'))
    have = {x['id'] for x in q}
    q.extend(e for e in entries if e['id'] not in have)
    json.dump(q, io.open(os.path.join(ROOT, 'queue.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('queue.json: +%d entries' % len([e for e in entries if e['id'] not in have]))
