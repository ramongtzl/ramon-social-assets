# -*- coding: utf-8 -*-
"""Standing schedule rules from the 2026-09-27 growth plan (Ramon: "do D, E and F").

    D  a second reel per language each week - the spare 'b' carousel slots,
       re-rendered white (2026-09/drafts/real-estate/_build_white_b_slots.py):
       Reel EN b Monday 17:00, Reel ES b Thursday 17:00
    E  book cards off the 1 AM slot: Round 2 -> 07:00, Round 2b -> 19:00
    F  Sunday had one @ramonhouses post: a 'b' carousel every Sunday 11:00,
       EN and ES alternating week by week

    W  reel hosting window, 12 weeks (Ramon, 2026-09-28): only Reel EN / Reel ES
       rows dated within REEL_WINDOW_DAYS are in the schedule and hosted. Rows
       further out are taken out (their hosted copy deleted, but only when the
       archive original is confirmed), and each day the reels that come inside
       the window are added back from the archive - 'a' reels with the builder's
       own caption (reproduced exactly, checked on all 101 a-reels), 'b' reels
       from the white renders. prep_morning.py runs `--roll --push` at 4:30 AM.

A b row is only added when its WHITE render exists in the archive, and its media
is copied into assets/ (what GitHub Pages serves).

Two entry points, so a rebuild can never drop these rows:
    build_web_assets.py calls apply(rows, ...) just before it writes schedule.csv
    python schedule_rules.py          apply to the deployed schedule.csv in place (backup kept)
    python schedule_rules.py --dry    show what would change
    python schedule_rules.py --roll --push   daily: apply, and commit + push when something changed
"""
import os, io, re, csv, sys, glob, shutil, datetime, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_SMC = r"G:\My Drive\RAMON VAULT\20 - FILES APPS\12 - SOCIAL MEDIA CONTENT"
W1_TUE = datetime.date(2026, 9, 1)           # carousel week 1 (same as the builder)
EFFECTIVE = datetime.date(2026, 9, 28)       # rules apply from this date on; history stays as posted
BOOK_TIMES = {"Round 2": "07:00", "Round 2b": "19:00"}
B_WEEKS = range(5, 53)                        # only weeks whose white render exists get rows
REEL_WINDOW_DAYS = 84                         # 12 weeks
REEL_SERIES = ("Reel EN", "Reel ES")          # carousel reels only - Just Sold / Open House reels are left alone
ASSET_CAP_MB = 920                            # MiB (du -sm). GitHub Pages ceiling is 1 GB = ~954 MiB; keep ~35 MiB spare
TAGS = {"en": "#FraserValleyRealEstate #LangleyRealEstate #BCRealEstate #RealEstateTips #ramonhouses",
        "es": "#BienesRaicesBC #FraserValley #Langley #InmobiliariaBC #AgenteEnEspanol #ramonhouses"}
DISCLOSURE = u"Ramon Gutierrez PREC · eXp Realty · ramonhouses.com"
FIELDS = ["post_id", "post_date", "time", "account", "series", "ref", "media", "channels",
          "images", "caption", "caption_fb", "caption_li"]


def sunday_lang(week):
    return "en" if week % 2 == 1 else "es"


def _caption(folder, lang, n_slides):
    body = io.open(os.path.join(folder, "slides.txt"), encoding="utf-8").read()
    cta = (re.search(r"^CTA:\s*(.+)$", body, re.M) or [None, ""])[1].strip()
    slides = [m.group(1).strip() for m in re.finditer(r"^SLIDE \S+ \|\s*([^|]+)\|", body, re.M)]
    hook = slides[0] if slides else (re.search(r"^TITLE:\s*(.+)$", body, re.M) or [None, ""])[1]
    pts = "\n".join("%d. %s" % (i, s) for i, s in enumerate(slides[1:], 1))
    swipe = ("Swipe through all %d." % n_slides) if lang == "en" else ("Desliza para ver los %d." % n_slides)
    return "\n\n".join(x for x in [hook, pts, swipe, cta, DISCLOSURE, TAGS[lang]] if x).strip()


def _variants(caption):
    try:
        for p in (HERE, os.path.join(VAULT_SMC, "_AGENT")):     # the repo clone has no platform_captions
            if p not in sys.path:
                sys.path.append(p)
        import platform_captions
        v = platform_captions.variants(caption)
        return v.get("fb", ""), v.get("li", "")
    except Exception:                         # noqa: BLE001 - vault not reachable
        return "", ""


def _reel_source(arch, row):
    """Archive original of a Reel EN / Reel ES row, or None."""
    lang = row["series"][-2:].lower()
    root = "ramonhouses-realestate-carousels" + ("-es" if lang == "es" else "")
    src = os.path.join(arch, root, row["ref"], "%s%s-reel-music.mp4" % (row["ref"], "-es" if lang == "es" else ""))
    return src if os.path.exists(src) else None


def _posted():
    try:
        import json
        return set(json.load(open(os.path.join(HERE, "state.json"))).get("posted", {}))
    except Exception:                         # noqa: BLE001 - vault builder has no state.json
        return set()


def _assets_mb(assets):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(assets) for f in fs) / 1048576.0


def _copy(src, dst):
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def _slide_copy(src, dest_dir, stem):
    """Same output as the builder's web_copy: smaller of JPEG q90 / PNG."""
    os.makedirs(dest_dir, exist_ok=True)
    for ext in (".jpg", ".png"):
        if os.path.exists(os.path.join(dest_dir, stem + ext)):
            return stem + ext
    from PIL import Image
    jpg = os.path.join(dest_dir, stem + ".jpg")
    Image.open(src).convert("RGB").save(jpg, "JPEG", quality=90, optimize=True, progressive=True)
    if os.path.getsize(src) < os.path.getsize(jpg):
        os.remove(jpg)
        shutil.copy2(src, os.path.join(dest_dir, stem + ".png"))
        return stem + ".png"
    return stem + ".jpg"


def apply(rows, arch=None, assets=None, today=None, log=print):
    arch = arch or os.path.join(VAULT_SMC, "_IG-ARCHIVE")
    assets = assets or os.path.join(HERE, "assets")
    today = today or datetime.date.today()
    have = {r["post_id"] for r in rows}
    changed = added = 0

    # ---- E: book card times
    for r in rows:
        if r.get("series") in BOOK_TIMES and r["post_date"] >= EFFECTIVE.isoformat() \
                and r["time"] != BOOK_TIMES[r["series"]]:
            r["time"] = BOOK_TIMES[r["series"]]
            changed += 1

    horizon = today + datetime.timedelta(days=REEL_WINDOW_DAYS)
    trimmed = rolled = 0
    if not os.path.isdir(arch):
        log("schedule_rules: archive not reachable (%s) - window, a-reel and b-slot rules skipped" % arch)
    else:
        # ---- W1: take out reels beyond the window (never one already posted, never one we cannot re-make)
        posted = _posted()
        keep = []
        for r in rows:
            if r.get("series") in REEL_SERIES and r["post_date"] > horizon.isoformat() \
                    and r["post_id"] not in posted and _reel_source(arch, r):
                f = os.path.join(assets, r["images"])
                if os.path.exists(f):
                    os.remove(f)
                have.discard(r["post_id"])
                trimmed += 1
                continue
            keep.append(r)
        rows[:] = keep

        # ---- W2: 'a' reels that are now inside the window
        size_mb = _assets_mb(assets)             # running total, checked before every new reel
        for lang, root, suffix, offset in (("en", "ramonhouses-realestate-carousels", "", 3),
                                           ("es", "ramonhouses-realestate-carousels-es", "-es", 4)):
            for folder in sorted(glob.glob(os.path.join(arch, root, "w??a"))):
                slot = os.path.basename(folder)
                rdate = W1_TUE + datetime.timedelta(days=7 * (int(slot[1:3]) - 1) + offset)
                pid = "reel-%s-%s" % (lang, slot)
                src = os.path.join(folder, "%s%s-reel-music.mp4" % (slot, suffix))
                if pid in have or not (today <= rdate <= horizon) or not os.path.exists(src):
                    continue
                dst = os.path.join(assets, "reels", "%s%s.mp4" % (slot, suffix))
                if not os.path.exists(dst):
                    mb = os.path.getsize(src) / 1048576.0
                    if size_mb + mb > ASSET_CAP_MB:
                        log("schedule_rules: would pass %d MB - %s not added" % (ASSET_CAP_MB, pid))
                        continue
                    size_mb += mb
                    _copy(src, dst)
                pngs = [x for x in os.listdir(folder) if x.endswith(".png")]
                cap = _caption(folder, lang, len(pngs))
                fb, li = _variants(cap)
                rows.append({"post_id": pid, "post_date": rdate.isoformat(), "time": "11:00",
                             "account": "ramonhouses", "series": "Reel %s" % lang.upper(), "ref": slot,
                             "media": "reel", "channels": "ig,fb,yt,threads",
                             "images": "reels/%s%s.mp4" % (slot, suffix),
                             "caption": cap, "caption_fb": fb, "caption_li": li})
                have.add(pid); rolled += 1

        # ---- D + F: white 'b' slots
        for week in B_WEEKS:
            slot = "w%02db" % week
            tue = W1_TUE + datetime.timedelta(days=7 * (week - 1))
            for lang, root, suffix in (("en", "ramonhouses-realestate-carousels", ""),
                                       ("es", "ramonhouses-realestate-carousels-es", "-es")):
                folder = os.path.join(arch, root, slot)
                pngs = sorted(glob.glob(os.path.join(folder, "*-white-%s-slide-*.png" % slot)))
                n_slides = len(pngs) or 8

                # F: Sunday carousel
                sun = tue + datetime.timedelta(days=5)
                pid = "car-%s-%s" % (lang, slot)
                if lang == sunday_lang(week) and pngs and sun > today and pid not in have:
                    sub = "car-%s/%s" % (lang, slot)
                    names = [_slide_copy(p, os.path.join(assets, sub), "%02d" % (i + 1)) for i, p in enumerate(pngs)]
                    cap = _caption(folder, lang, len(pngs))
                    fb, li = _variants(cap)
                    rows.append({"post_id": pid, "post_date": sun.isoformat(), "time": "11:00",
                                 "account": "ramonhouses", "series": "Carousel %s" % lang.upper(), "ref": slot,
                                 "media": "carousel", "channels": "ig,fb,li,threads",
                                 "images": "|".join("%s/%s" % (sub, n) for n in names),
                                 "caption": cap, "caption_fb": fb, "caption_li": li})
                    have.add(pid); added += 1

                # D: second weekly reel
                reel = os.path.join(folder, "%s%s-reel-music.mp4" % (slot, suffix))
                rdate = tue + datetime.timedelta(days=6 if lang == "en" else 9)   # Mon / Thu after the Sunday
                pid = "reel-%s-%s" % (lang, slot)
                if os.path.exists(os.path.join(folder, ".white-reel")) and os.path.exists(reel) \
                        and today < rdate <= horizon and pid not in have:
                    rname = "%s%s.mp4" % (slot, suffix)
                    dst = os.path.join(assets, "reels", rname)
                    if not os.path.exists(dst):
                        mb = os.path.getsize(reel) / 1048576.0
                        if size_mb + mb > ASSET_CAP_MB:
                            log("schedule_rules: would pass %d MB - %s not added" % (ASSET_CAP_MB, pid))
                            continue
                        size_mb += mb
                    _copy(reel, dst)
                    cap = _caption(folder, lang, n_slides)
                    fb, li = _variants(cap)
                    rows.append({"post_id": pid, "post_date": rdate.isoformat(), "time": "17:00",
                                 "account": "ramonhouses", "series": "Reel %s" % lang.upper(), "ref": slot,
                                 "media": "reel", "channels": "ig,fb,yt,threads",
                                 "images": "reels/" + rname,
                                 "caption": cap, "caption_fb": fb, "caption_li": li})
                    have.add(pid); added += 1

    rows.sort(key=lambda r: (r["post_date"], r["time"], r["series"]))
    log("schedule_rules: %d book-card times moved, %d reels past the %d-day window taken out, "
        "%d a-reels rolled in, %d b-slot rows added" % (changed, trimmed, REEL_WINDOW_DAYS, rolled, added))
    return rows


def main():
    dry = "--dry" in sys.argv
    path = os.path.join(HERE, "schedule.csv")
    rows = list(csv.DictReader(io.open(path, encoding="utf-8-sig", newline="")))
    push = "--push" in sys.argv
    if push:
        subprocess.run(["git", "pull", "--rebase", "-q"], cwd=HERE, check=True)
        rows = list(csv.DictReader(io.open(path, encoding="utf-8-sig", newline="")))
    by_id = {r["post_id"]: r for r in rows}
    before = set(by_id)
    if dry:                                   # never touch the hosted files on a dry run
        tmp = os.path.join(HERE, "_dry_assets")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(os.path.join(HERE, "assets", "reels"), os.path.join(tmp, "reels"))
    rows = apply(rows, assets=os.path.join(HERE, "assets") if not dry else os.path.join(HERE, "_dry_assets"))
    after = {r["post_id"] for r in rows}
    horizon = (datetime.date.today() + datetime.timedelta(days=REEL_WINDOW_DAYS)).isoformat()
    lost = [p for p in before - after
            if not (by_id[p]["series"] in REEL_SERIES and by_id[p]["post_date"] > horizon)]
    if lost:
        sys.exit("REFUSING: %d post_ids would disappear that are not beyond-window reels: %s" % (len(lost), lost[:5]))
    if before - after:
        print("  - %d reels beyond %s taken out (re-added from the archive as they enter the window)"
              % (len(before - after), horizon))
    for r in sorted((r for r in rows if r["post_id"] in after - before), key=lambda r: r["post_date"]):
        print("  + %s %s %-12s %s" % (r["post_date"], r["time"], r["series"], r["post_id"]))
    if dry:
        shutil.rmtree(os.path.join(HERE, "_dry_assets"), ignore_errors=True)
        return
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    text = buf.getvalue()
    if text == io.open(path, encoding="utf-8-sig", newline="").read():
        print("schedule.csv unchanged")           # the daily roll is usually a no-op - no backup, no commit
        return
    shutil.copy2(path, path + ".BACKUP-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    io.open(path, "w", encoding="utf-8-sig", newline="").write(text)
    print("schedule.csv written (%d rows, was %d)" % (len(rows), len(before)))
    if push:
        subprocess.run(["git", "add", "-A", "schedule.csv", "assets/reels", "assets/car-en", "assets/car-es"], cwd=HERE, check=True)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=HERE).returncode == 0:
            print("nothing changed - no commit")
            return
        subprocess.run(["git", "commit", "-q", "-m", "reel window roll %s (schedule_rules --roll)" % datetime.date.today()],
                       cwd=HERE, check=True)
        subprocess.run(["git", "pull", "--rebase", "-q"], cwd=HERE, check=True)
        subprocess.run(["git", "push", "-q"], cwd=HERE, check=True)
        print("pushed")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
