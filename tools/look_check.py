"""Stops a post look repeating on a feed.

Reads queue.json and tools/looks.json, takes one account's published and
pending posts in publish order, and fails (exit 1, naming the pair) when:
  - a pending post has no entry in looks.json;
  - the same look appears twice inside any 9 consecutive posts where at
    least one of the pair is pending;
  - the same object appears likewise (object "none" never matches);
  - two consecutive posts share a ground where at least one is pending.
Pairs where both posts are published are printed as history, never a fail.

  py tools/look_check.py --account list
  py tools/look_check.py --selftest
"""
import argparse, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW = 9


def check(posts, looks):
    """posts: list of (id, status) in publish order. looks: {id: {look, ground, object}}.
    Returns (failures, history)."""
    fails, hist = [], []
    seq = [(i, s, looks.get(i)) for i, s in posts if s in ("published", "pending")]
    for i, s, t in seq:
        if s == "pending" and t is None:
            fails.append(f"pending post has no looks.json entry: {i}")
    for a in range(len(seq)):
        for b in range(a + 1, min(a + WINDOW, len(seq))):
            ia, sa, ta = seq[a]
            ib, sb, tb = seq[b]
            if ta is None or tb is None:
                continue
            live = "pending" in (sa, sb)
            found = []
            if ta["look"] == tb["look"]:
                found.append(f'same look "{ta["look"]}"')
            if ta["object"] == tb["object"] and ta["object"] != "none":
                found.append(f'same object "{ta["object"]}"')
            if b == a + 1 and ta["ground"] == tb["ground"]:
                found.append(f'consecutive same ground "{ta["ground"]}"')
            for f in found:
                line = f"{f}: {ia} and {ib} ({b - a} apart)"
                (fails if live else hist).append(line)
    return fails, hist


def load(account):
    q = json.load(open(os.path.join(ROOT, "queue.json"), encoding="utf-8"))
    posts = sorted((p for p in q if p.get("account") == account), key=lambda p: p["publish_at"])
    looks = json.load(open(os.path.join(ROOT, "tools", "looks.json"), encoding="utf-8")).get(account, {})
    return [(p["id"], p.get("status")) for p in posts], looks


def report(fails, hist):
    for h in hist:
        print("HISTORY", h)
    for f in fails:
        print("FAIL", f)


def selftest():
    looks = {
        "a": {"look": "poster", "ground": "cream", "object": "keys"},
        "b": {"look": "board", "ground": "black", "object": "board"},
        "c": {"look": "poster", "ground": "blue", "object": "shovel"},
        "d": {"look": "wall", "ground": "blue", "object": "none"},
        "e": {"look": "tag", "ground": "green", "object": "none"},
    }
    ok = True
    # Planted: c repeats a's look two posts apart, d sits on c's ground, f has no entry.
    f, _ = check([("a", "published"), ("b", "published"), ("c", "pending"), ("d", "pending"), ("e", "pending"), ("f", "pending")], looks)
    want = ['same look "poster": a and c', 'consecutive same ground "blue": c and d', "no looks.json entry: f"]
    for w in want:
        hit = any(w in x for x in f)
        print(("CAUGHT " if hit else "MISSED ") + w)
        ok &= hit
    if any("none" in x and "object" in x for x in f):
        print('MISSED: object "none" was matched')
        ok = False
    # The same repeat with both posts published is history only.
    f2, h2 = check([("a", "published"), ("b", "published"), ("c", "published")], looks)
    print("CAUGHT published-only pair kept as history" if (not f2 and h2) else "MISSED published-only rule")
    ok &= (not f2 and bool(h2))
    # A clean sequence passes.
    f3, _ = check([("b", "published"), ("c", "pending"), ("e", "pending")], looks)
    print("CLEAN sequence passes" if not f3 else f"CLEAN sequence failed: {f3}")
    ok &= not f3
    print("SELFTEST PASS" if ok else "SELFTEST FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--account")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    if not a.account:
        ap.error("--account or --selftest")
    posts, looks = load(a.account)
    fails, hist = check(posts, looks)
    report(fails, hist)
    print(f"{a.account}: {len(posts)} posts, {len(looks)} tagged, {len(fails)} failures, {len(hist)} history pairs")
    print("LOOK CHECK PASS" if not fails else "LOOK CHECK FAIL")
    sys.exit(1 if fails else 0)
