# -*- coding: utf-8 -*-
"""Queue a Bank of Canada rate announcement card into the posting agent.

Routine 24 renders the card the morning the Bank announces. This puts it in front
of the agent: the image goes into the hosted asset bundle, a row goes into the
schedule, and the whole thing is pushed so GitHub Pages can serve the URL that the
Instagram Graph API requires.

    python queue_boc_post.py --date 2026-10-28 \
        --card  "...\\20261028_071500-re-boc-rate-2026-10-28.png" \
        --caption "...\\boc-rate-2026-10-28-caption-en.txt" \
        --card-es "...\\20261028_071500-re-boc-rate-2026-10-28-es.png" \
        --caption-es "...\\boc-rate-2026-10-28-caption-es.txt" \
        --push

Without --push it does everything locally and stops, so a run can be inspected
before anything is public. With --push it commits and pushes, and the hourly
Action publishes at the scheduled slot.

Why the row also goes into extras.csv: build_web_assets.py REGENERATES
schedule.csv from the content plan every time it runs. A row appended only to
schedule.csv would vanish on the next rebuild. extras.csv is merged back in by
that script, so an announcement post survives.

Slotting: 08:00 Pacific for English, 09:00 for Spanish. The Bank announces at
06:45 Pacific and Routine 24 runs at 07:15, which leaves GitHub Pages time to
serve the new image before the 08:00 run. post_agent also catches up any slot
that has already come round today, so a late cron still publishes.
"""
import argparse, csv, datetime, io, os, shutil, subprocess, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets", "boc")
SCHED = os.path.join(HERE, "schedule.csv")
EXTRAS = os.path.join(HERE, "extras.csv")
COLUMNS = ["post_id", "post_date", "time", "account", "series", "ref", "media",
           "channels", "images", "caption", "caption_fb", "caption_li"]


def web_jpeg(src, dest):
    """Same treatment the bundle gives every other card: JPEG q90, RGB."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if not (320 <= w <= 1440):
        raise SystemExit("card is %dx%d; Instagram needs a width of 320 to 1440" % (w, h))
    if not (0.8 <= w / h <= 1.91):
        raise SystemExit("card aspect %.2f is outside Instagram's 4:5 to 1.91:1" % (w / h))
    im.save(dest, "JPEG", quality=90, optimize=True, progressive=True)
    return os.path.getsize(dest)


def read_caption(path):
    text = io.open(path, encoding="utf-8").read().strip()
    if not text:
        raise SystemExit("caption file is empty: %s" % path)
    if len(text) > 2200:
        raise SystemExit("caption is %d characters; Instagram's limit is 2200" % len(text))
    return text


def existing_ids():
    if not os.path.exists(SCHED):
        return set()
    return {r["post_id"] for r in csv.DictReader(io.open(SCHED, encoding="utf-8-sig"))}


def append(path, rows, header_if_new):
    new = not os.path.exists(path)
    f = io.open(path, "a", encoding="utf-8-sig" if header_if_new else "utf-8", newline="")
    w = csv.DictWriter(f, fieldnames=COLUMNS)
    if new:
        w.writeheader()
    w.writerows(rows)
    f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="announcement date, YYYY-MM-DD")
    ap.add_argument("--card", required=True, help="English card PNG")
    ap.add_argument("--caption", required=True, help="English caption, plain text file")
    ap.add_argument("--card-es", dest="card_es")
    ap.add_argument("--caption-es", dest="caption_es")
    ap.add_argument("--time", default="08:00", help="English slot, Pacific (default 08:00)")
    ap.add_argument("--time-es", dest="time_es", default="09:00")
    ap.add_argument("--push", action="store_true", help="commit and push; without it, local only")
    a = ap.parse_args()

    try:
        datetime.date.fromisoformat(a.date)
    except ValueError:
        raise SystemExit("--date must be YYYY-MM-DD")

    os.makedirs(ASSETS, exist_ok=True)
    have = existing_ids()
    rows, touched = [], []

    plan = [("en", a.card, a.caption, a.time, "Rate Note EN")]
    if a.card_es and a.caption_es:
        plan.append(("es", a.card_es, a.caption_es, a.time_es, "Rate Note ES"))
    elif a.card_es or a.caption_es:
        raise SystemExit("--card-es and --caption-es go together")

    for lang, card, cap, slot, series in plan:
        pid = "boc-%s-%s" % (lang, a.date)
        if pid in have:
            print("SKIP %s is already scheduled" % pid)
            continue
        name = "boc-%s-%s.jpg" % (lang, a.date)
        dest = os.path.join(ASSETS, name)
        size = web_jpeg(card, dest)
        touched.append(dest)
        rows.append(dict(
            post_id=pid, post_date=a.date, time=slot, account="ramonhouses",
            series=series, ref="BoC %s" % a.date, media="image", channels="ig,fb,li",
            images="boc/%s" % name, caption=read_caption(cap),
            caption_fb=read_caption(cap), caption_li=read_caption(cap)))
        print("queued %-22s %s %s  %s  (%d KB)" % (pid, a.date, slot, series, size // 1024))

    if not rows:
        print("nothing to queue")
        return 0

    append(EXTRAS, rows, header_if_new=True)
    append(SCHED, rows, header_if_new=False)
    print("wrote %d row(s) to schedule.csv and extras.csv" % len(rows))

    if not a.push:
        print("\nlocal only. Re-run with --push to publish, or revert with:\n"
              "  git -C \"%s\" checkout -- schedule.csv extras.csv && git clean -fd assets/boc" % HERE)
        return 0

    subprocess.check_call(["git", "-C", HERE, "add", "assets/boc", "schedule.csv", "extras.csv"])
    msg = "BoC rate announcement %s: queue %d post(s)" % (a.date, len(rows))
    subprocess.check_call(["git", "-C", HERE, "commit", "-m", msg])
    subprocess.check_call(["git", "-C", HERE, "push"])
    print("\npushed. The hourly Action publishes at %s Pacific." % a.time)
    return 0


if __name__ == "__main__":
    sys.exit(main())
