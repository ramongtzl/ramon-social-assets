# -*- coding: utf-8 -*-
"""Monthly reel rotation: prune what has posted, add what is coming.

The whole reel library is ~1 GB, and GitHub Pages caps a repo at 1 GB total.
So the library stays on Ramon's machine and only a slice ever ships. This is
the script that moves the slice forward.

Each run:
  1. DELETES reel files from the bundle whose post date has passed
     (plus a grace period, so a late run does not break a pending post).
  2. COPIES IN every reel needed in the next N months that is not there yet,
     pulled from the local carousel folders.
  3. Reports the size before and after, so the repo never creeps toward the
     Pages ceiling unnoticed.

Nothing is ever deleted from the local library - only from the shipped bundle.

Run:
    python sync_reels.py                 # next 1 month
    python sync_reels.py --months 2      # next 2 months
    python sync_reels.py --dry-run       # show what would change
"""
import io, os, csv, sys, glob, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SMC = os.path.dirname(HERE)
SCHED = os.path.join(HERE, "schedule.csv")
REELS_OUT = os.path.join(HERE, "assets", "reels")
LIB = [os.path.join(SMC, "_IG-ARCHIVE", "ramonhouses-realestate-carousels"),
       os.path.join(SMC, "_IG-ARCHIVE", "ramonhouses-realestate-carousels-es")]

MONTHS = 1
GRACE_DAYS = 3
DRY = "--dry-run" in sys.argv
if "--months" in sys.argv:
    MONTHS = int(sys.argv[sys.argv.index("--months") + 1])
if "--grace" in sys.argv:
    GRACE_DAYS = int(sys.argv[sys.argv.index("--grace") + 1])

today = datetime.date.today()
horizon = today + datetime.timedelta(days=int(30.44 * MONTHS))
cutoff = today - datetime.timedelta(days=GRACE_DAYS)


def mb(paths):
    return sum(os.path.getsize(p) for p in paths if os.path.exists(p)) / 1048576.0


def library_file(asset_rel):
    """assets/reels/w14b.mp4  ->  the local .mp4 that should fill it."""
    slot = os.path.splitext(os.path.basename(asset_rel))[0]      # w14b or w14b-es
    es = slot.endswith("-es")
    key = slot[:-3] if es else slot
    root = LIB[1] if es else LIB[0]
    folder = os.path.join(root, key)
    if not os.path.isdir(folder):
        return None
    # prefer the scored version, fall back to a silent one
    for pat in ("*-reel-music.mp4", "*-reel.mp4"):
        found = sorted(glob.glob(os.path.join(folder, pat)))
        if found:
            return found[0]
    return None


rows = [r for r in csv.DictReader(io.open(SCHED, encoding="utf-8-sig"))
        if (r.get("media") or "") == "reel"]
if not rows:
    print("no reel rows in schedule.csv - nothing to sync")
    sys.exit(0)

os.makedirs(REELS_OUT, exist_ok=True)
before = glob.glob(os.path.join(REELS_OUT, "*.mp4"))
print("bundle before : %d reels, %.0f MB" % (len(before), mb(before)))
print("window        : %s -> %s (%d month%s)"
      % (today, horizon, MONTHS, "" if MONTHS == 1 else "s"))

# A reel is only kept in the bundle if it sits INSIDE the window. Anything
# already posted drops off the back; anything further out than the horizon
# drops off the front and comes back on a later run. Both directions matter -
# only pruning the past leaves the whole library shipped.
wanted, expired = {}, []
for r in rows:
    d = datetime.date.fromisoformat(r["post_date"])
    rel = r["images"].split("|")[0]
    if cutoff <= d <= horizon:
        wanted[rel] = d
    else:
        expired.append(rel)

# ---------------------------------------------------------------- prune
freed, dropped = 0.0, []
for rel in expired:
    p = os.path.join(HERE, "assets", rel)
    if os.path.exists(p):
        freed += os.path.getsize(p) / 1048576.0
        dropped.append(os.path.basename(rel))
        if not DRY:
            os.remove(p)

# ------------------------------------------------------------- top up
added, missing = [], []
for rel, d in sorted(wanted.items(), key=lambda kv: kv[1]):
    p = os.path.join(HERE, "assets", rel)
    if os.path.exists(p):
        continue
    src = library_file(rel)
    if not src:
        missing.append((rel, d.isoformat()))
        continue
    if not DRY:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        shutil.copy2(src, p)
    added.append((os.path.basename(rel), d.isoformat(),
                  os.path.getsize(src) / 1048576.0))

after = glob.glob(os.path.join(REELS_OUT, "*.mp4"))
allassets = [os.path.join(r, f)
             for r, _, fs in os.walk(os.path.join(HERE, "assets")) for f in fs]

print("")
print("pruned        : %d (%.0f MB freed, outside the window)" % (len(dropped), freed))
for n in dropped[:8]:
    print("   -", n)
print("added         : %d (%.0f MB)" % (len(added), sum(a[2] for a in added)))
for n, d, s in added[:8]:
    print("   + %-16s %s  %.1f MB" % (n, d, s))
if len(added) > 8:
    print("   ... and %d more" % (len(added) - 8))
if missing:
    print("NOT IN LIBRARY: %d - render these before the date arrives" % len(missing))
    for rel, d in missing[:6]:
        print("   ! %-24s needed %s" % (rel, d))

# ------------------------------------------- keep schedule.csv honest
# A reel row whose file is not shipped would make the agent attempt a URL
# that 404s. So the schedule only ever lists reels that are actually present.
allrows = list(csv.DictReader(io.open(SCHED, encoding="utf-8-sig")))
kept, cut = [], []
for r in allrows:
    if (r.get("media") or "") != "reel":
        kept.append(r)
        continue
    rel = r["images"].split("|")[0]
    if os.path.exists(os.path.join(HERE, "assets", rel)):
        kept.append(r)
    else:
        cut.append((r["post_date"], r["post_id"]))

if not DRY and cut:
    shutil.copy2(SCHED, SCHED + ".BACKUP")
    f = io.open(SCHED, "w", encoding="utf-8-sig", newline="")
    w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
    w.writeheader()
    w.writerows(kept)
    f.close()

print("")
print("schedule      : %d rows kept, %d reel rows dropped (no file shipped)"
      % (len(kept), len(cut)))
for d, pid in cut[:5]:
    print("   -", d, pid)
if len(cut) > 5:
    print("   ... and %d more" % (len(cut) - 5))

print("")
print("bundle after  : %d reels, %.0f MB" % (len(after), mb(after)))
print("whole bundle  : %d files, %.0f MB" % (len(allassets), mb(allassets)))
head = 1024 - mb(allassets)
print("Pages headroom: %.0f MB below the 1 GB ceiling" % head)
if head < 100:
    print("!! Close to the ceiling - shorten the window (--months 1) before pushing.")
if DRY:
    print("\n(dry run - nothing was changed)")
