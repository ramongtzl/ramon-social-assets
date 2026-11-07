# -*- coding: utf-8 -*-
"""Queue a local-guide post (Langley Eats / This Week) into the posting agent.

Same mechanics as queue_boc_post.py: the card goes into assets/local/, the row
goes into schedule.csv AND extras.csv (build_web_assets.py regenerates
schedule.csv and merges extras back in), then commit + push so GitHub Pages
serves the image before the slot.

    python queue_local_guide_post.py --id eats-2026-11-07-saba-pizzeria-en \
        --date 2026-11-07 --time 12:00 --series "Langley Eats EN" \
        --ref "Saba Pizzeria, Fort Langley" \
        --card  "...-ig-feed-en.jpg" --caption "...caption-en.txt" \
        --alt "Exterior of Saba Pizzeria on Mavis Avenue, Fort Langley, BC" --push

Schedule (Ramon, 2026-11-07): Langley Eats EN Thursday + Saturday 12:00, the
ES twin on another day with 2-3 posts between (never back to back);
This Week EN (events, Langley first, then nearby cities) Friday 10:00 covering
that Friday through the next Sunday, ES twin ~2 days later (Ramon, 2026-11-07). Every third-party photo carries the photographer
credit (and their verified @handle) on the card and in the caption.
"""
import argparse, csv, datetime, io, os, subprocess, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets", "local")
SCHED = os.path.join(HERE, "schedule.csv")
EXTRAS = os.path.join(HERE, "extras.csv")
COLUMNS = ["post_id", "post_date", "time", "account", "series", "ref", "media",
           "channels", "images", "caption", "caption_fb", "caption_li"]
SERIES = {"Langley Eats EN", "Langley Eats ES", "This Week EN", "This Week ES"}


def web_jpeg(src, dest):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if not (320 <= w <= 1440) or not (0.8 <= w / h <= 1.91):
        raise SystemExit("card %dx%d is outside Instagram's limits" % (w, h))
    im.save(dest, "JPEG", quality=90, optimize=True, progressive=True)
    return os.path.getsize(dest)


def read_caption(path):
    text = io.open(path, encoding="utf-8").read().strip()
    if not text or len(text) > 2200:
        raise SystemExit("caption empty or over 2200 chars: %s" % path)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--time", required=True)
    ap.add_argument("--series", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--card", required=True)
    ap.add_argument("--caption", required=True)
    ap.add_argument("--alt", default="", help="image description (kept for the alt-text step)")
    ap.add_argument("--channels", default="ig,fb,li,threads")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args()
    datetime.date.fromisoformat(a.date)
    if a.series not in SERIES:
        raise SystemExit("series must be one of %s" % sorted(SERIES))
    have = {r["post_id"] for r in csv.DictReader(io.open(SCHED, encoding="utf-8-sig"))}
    if a.id in have:
        raise SystemExit("%s is already scheduled" % a.id)
    os.makedirs(ASSETS, exist_ok=True)
    name = a.id + ".jpg"
    size = web_jpeg(a.card, os.path.join(ASSETS, name))
    cap = read_caption(a.caption)
    row = dict(post_id=a.id, post_date=a.date, time=a.time, account="ramonhouses",
               series=a.series, ref=a.ref, media="image", channels=a.channels,
               images="local/" + name, caption=cap, caption_fb=cap, caption_li=cap)
    for path in (EXTRAS, SCHED):
        with io.open(path, "a", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)
    if a.alt:
        with io.open(os.path.join(ASSETS, "alt.csv"), "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([a.id, a.alt])
    print("queued %s %s %s %s (%d KB)" % (a.id, a.date, a.time, a.series, size // 1024))
    if a.push:
        subprocess.check_call(["git", "-C", HERE, "add", "assets/local", "schedule.csv",
                               "extras.csv", "queue_local_guide_post.py"])
        subprocess.check_call(["git", "-C", HERE, "commit", "-m", "Queue local guide post: " + a.id])
        subprocess.check_call(["git", "-C", HERE, "push"])
        print("pushed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
