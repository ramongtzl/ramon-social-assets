# -*- coding: utf-8 -*-
"""Weekly housekeeping for the posting agent, run by GitHub Actions.

Two jobs:

1. **Prune.** Delete reel files whose post date has passed. Reels are ~5 MB
   each against ~80 KB for an image, so this is what keeps the repo inside the
   1 GB GitHub Pages ceiling.

2. **Warn.** Count how many weeks of reels are still queued and fail the run
   when the window runs thin. It cannot top the window back up on its own -
   the source MP4s live on Ramon's machine, not in the repo - so a loud failure
   is the signal to run the vault-side refresh (Routine 21).

Run:  python maintain.py [--keep-days 3] [--warn-weeks 2]
"""
import io, os, csv, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.join(HERE, "schedule.csv")
ASSETS = os.path.join(HERE, "assets")
REELS = os.path.join(ASSETS, "reels")

KEEP_DAYS = 3        # grace period after a post date before its reel is dropped
WARN_WEEKS = 2       # fail the run if fewer than this many weeks of reels remain
for flag, var in (("--keep-days", "KEEP_DAYS"), ("--warn-weeks", "WARN_WEEKS")):
    if flag in sys.argv:
        globals()[var] = int(sys.argv[sys.argv.index(flag) + 1])

today = datetime.date.today()
rows = list(csv.DictReader(io.open(SCHED, encoding="utf-8-sig")))
reels = [r for r in rows if (r.get("media") or "") == "reel"]

# ---------------------------------------------------------------- prune
freed = 0
dropped = []
for r in reels:
    d = datetime.date.fromisoformat(r["post_date"])
    if d >= today - datetime.timedelta(days=KEEP_DAYS):
        continue
    p = os.path.join(ASSETS, r["images"])
    if os.path.exists(p):
        freed += os.path.getsize(p)
        os.remove(p)
        dropped.append(os.path.basename(p))

print("pruned %d reel file(s), freed %.0f MB" % (len(dropped), freed / 1048576.0))
for n in dropped:
    print("   -", n)

# ---------------------------------------------------------------- report
upcoming = [r for r in reels
            if datetime.date.fromisoformat(r["post_date"]) >= today
            and os.path.exists(os.path.join(ASSETS, r["images"]))]
if upcoming:
    last = max(datetime.date.fromisoformat(r["post_date"]) for r in upcoming)
    weeks_left = (last - today).days / 7.0
else:
    last, weeks_left = None, 0.0

total = sum(os.path.getsize(os.path.join(r, f))
            for r, _, fs in os.walk(ASSETS) for f in fs)
img_posts = [r for r in rows if (r.get("media") or "") != "reel"
             and datetime.date.fromisoformat(r["post_date"]) >= today]

print("")
print("reels queued        : %d (through %s, %.1f weeks)"
      % (len(upcoming), last or "-", weeks_left))
print("image posts queued  : %d" % len(img_posts))
print("assets on disk      : %.0f MB" % (total / 1048576.0))

io.open(os.path.join(HERE, "health.json"), "w", encoding="utf-8").write(
    json.dumps({"checked": today.isoformat(),
                "reels_queued": len(upcoming),
                "reels_through": last.isoformat() if last else None,
                "reel_weeks_left": round(weeks_left, 1),
                "image_posts_queued": len(img_posts),
                "assets_mb": round(total / 1048576.0, 1),
                "pruned_this_run": len(dropped)}, indent=2))

if weeks_left < WARN_WEEKS:
    print("")
    print("!! Only %.1f weeks of reels left. Run the vault-side refresh"
          " (Routine 21) to render more and push a new window." % weeks_left)
    sys.exit(1)
print("\nwindow healthy")
