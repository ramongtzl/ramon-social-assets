# -*- coding: utf-8 -*-
"""Standing schedule rules from the 2026-09-27 growth plan (Ramon: "do D, E and F").

    D  a second reel per language each week - the spare 'b' carousel slots,
       re-rendered white (2026-09/drafts/real-estate/_build_white_b_slots.py):
       Reel EN b Monday 17:00, Reel ES b Thursday 17:00
    E  book cards off the 1 AM slot: Round 2 -> 07:00, Round 2b -> 19:00
    F  Sunday had one @ramonhouses post: a 'b' carousel every Sunday 11:00,
       EN and ES alternating week by week

A row is only added when its WHITE render exists in the archive, and its media
is copied into assets/ (what GitHub Pages serves). Nothing is ever removed.

Two entry points, so a rebuild can never drop these rows:
    build_web_assets.py calls apply(rows, ...) just before it writes schedule.csv
    python schedule_rules.py          apply to the deployed schedule.csv in place (backup kept)
    python schedule_rules.py --dry    show what would change
"""
import os, io, re, csv, sys, glob, shutil, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_SMC = r"G:\My Drive\RAMON VAULT\20 - FILES APPS\12 - SOCIAL MEDIA CONTENT"
W1_TUE = datetime.date(2026, 9, 1)           # carousel week 1 (same as the builder)
EFFECTIVE = datetime.date(2026, 9, 28)       # rules apply from this date on; history stays as posted
BOOK_TIMES = {"Round 2": "07:00", "Round 2b": "19:00"}
B_WEEKS = range(5, 53)                        # only weeks whose white render exists get rows
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
        sys.path.insert(0, HERE)
        import platform_captions
        v = platform_captions.variants(caption)
        return v.get("fb", ""), v.get("li", "")
    except Exception:                         # noqa: BLE001 - the repo clone has no platform_captions
        return "", ""


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

    # ---- D + F: white 'b' slots
    if not os.path.isdir(arch):
        log("schedule_rules: archive not reachable (%s) - b-slot rows not added" % arch)
    else:
        size_mb = _assets_mb(assets)             # running total, checked before every new reel
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
                        and rdate > today and pid not in have:
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
    log("schedule_rules: %d book-card times moved, %d b-slot rows added" % (changed, added))
    return rows


def main():
    dry = "--dry" in sys.argv
    path = os.path.join(HERE, "schedule.csv")
    rows = list(csv.DictReader(io.open(path, encoding="utf-8-sig", newline="")))
    before = {r["post_id"] for r in rows}
    rows = apply(rows, assets=os.path.join(HERE, "assets") if not dry else os.path.join(HERE, "_dry_assets"))
    after = {r["post_id"] for r in rows}
    if before - after:
        sys.exit("REFUSING: %d post_ids would disappear" % len(before - after))
    for r in sorted((r for r in rows if r["post_id"] in after - before), key=lambda r: r["post_date"]):
        print("  + %s %s %-12s %s" % (r["post_date"], r["time"], r["series"], r["post_id"]))
    if dry:
        shutil.rmtree(os.path.join(HERE, "_dry_assets"), ignore_errors=True)
        return
    shutil.copy2(path, path + ".BACKUP-" + datetime.datetime.now().strftime("%Y%m%d-%H%M"))
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print("schedule.csv written (%d rows, was %d)" % (len(rows), len(before)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
