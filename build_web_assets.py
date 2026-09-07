# -*- coding: utf-8 -*-
"""Prepare the deployable asset bundle + schedule for the posting agent.

Instagram's Graph API will only accept a **public HTTPS image URL** - it cannot
read a local file. So every image that will ever be posted has to be hosted
first. This packs them into _AGENT/assets/ at web weight and writes the
schedule the agent reads.

Per file it keeps whichever of JPEG-q90 or the original PNG is smaller: the
photo-backed covers shrink ~75-80% as JPEG, while the flat black slides are
already smaller as PNG.

Output:
    _AGENT/assets/<series>/<file>      the images to publish
    _AGENT/schedule.csv                post_id, date, time, account, images, caption
    _AGENT/manifest.json               counts and total size

Run:  python build_web_assets.py [--days N]   (default: everything)
"""
import io, os, re, csv, sys, glob, json, shutil, datetime
import platform_captions
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SMC = os.path.abspath(os.path.join(HERE, ".."))
ARCH = os.path.join(SMC, "_IG-ARCHIVE")
ASSETS = os.path.join(HERE, "assets")

DAYS = None
if "--days" in sys.argv:
    DAYS = int(sys.argv[sys.argv.index("--days") + 1])

# Reels are ~5 MB each against ~80 KB for an image, so the whole library would
# blow past the 1 GB GitHub Pages ceiling. Only the next few weeks are shipped;
# re-run this weekly and the window rolls forward.
REEL_WEEKS = 8
if "--reel-weeks" in sys.argv:
    REEL_WEEKS = int(sys.argv[sys.argv.index("--reel-weeks") + 1])
TODAY = datetime.date.today()

START = datetime.date(2026, 9, 2)      # Round 2 / 2b day 03
W1_TUE = datetime.date(2026, 9, 1)     # carousel week 1


def web_copy(src, dest_dir, stem):
    """Write the smaller of JPEG q90 / original PNG. Returns the filename."""
    os.makedirs(dest_dir, exist_ok=True)
    jpg = os.path.join(dest_dir, stem + ".jpg")
    png = os.path.join(dest_dir, stem + ".png")
    if os.path.exists(jpg):
        return os.path.basename(jpg)
    if os.path.exists(png):
        return os.path.basename(png)
    Image.open(src).convert("RGB").save(jpg, "JPEG", quality=90,
                                        optimize=True, progressive=True)
    if os.path.getsize(src) < os.path.getsize(jpg):
        os.remove(jpg)
        shutil.copy2(src, png)
        return os.path.basename(png)
    return os.path.basename(jpg)


def sections(path):
    """Parse '## Day NN' caption files into {day:int -> caption}."""
    out = {}
    if not os.path.exists(path):
        return out
    text = io.open(path, encoding="utf-8").read().replace("\r", "")
    parts = re.split(r"\n## Day (\d+)\s*[\u2014-]\s*[^\n]*\n", "\n" + text)
    for i in range(1, len(parts) - 1, 2):
        day = int(parts[i])
        body = parts[i + 1].split("\n---")[0]
        lines = body.split("\n")
        while lines and (not lines[0].strip() or
                         (lines[0].startswith("*") and lines[0].rstrip().endswith("*"))):
            lines.pop(0)
        out[day] = "\n".join(lines).strip()
    return out


rows = []
counts = {}


# Which channels each kind of post fans out to (Ramon, 2026-09-04):
#   images and carousels -> Instagram + both Facebook Pages + LinkedIn (profile
#   and company); reels -> Instagram + Facebook + YouTube Shorts. Book cards are
#   not in this schedule at all (the Claude tasks post them).
CHANNELS = {"image": "ig,fb,li", "carousel": "ig,fb,li", "reel": "ig,fb,yt"}


DISCLOSURE = u"Ramon Gutierrez PREC · eXp Realty · ramonhouses.com"


def with_disclosure(caption):
    """Every ramonhouses post is licensee advertising, so the brokerage line
    goes in the caption (Ramon, 2026-09-01 - no brokerage line on the cards).
    Inserted just above the hashtag line when the caption does not carry it;
    a bare 'ramonhouses.com' line is upgraded rather than duplicated."""
    if "eXp Realty" in caption:
        return caption
    lines = caption.rstrip().split("\n")
    lines = [l for l in lines if l.strip() != "ramonhouses.com"]
    # find the trailing hashtag line
    i = len(lines)
    while i > 0 and (not lines[i - 1].strip() or lines[i - 1].lstrip().startswith("#")):
        i -= 1
    head = "\n".join(lines[:i]).rstrip()
    tail = "\n".join(lines[i:]).strip()
    out = head + "\n\n" + DISCLOSURE
    return (out + "\n\n" + tail) if tail else out


def add(post_id, date, time_, account, series, ref, images, caption, media="image"):
    if account == "ramonhouses":
        caption = with_disclosure(caption)
    # Facebook and LinkedIn get their own wording, derived from the Instagram
    # caption - fewer hashtags, no emoji on LinkedIn, no "swipe" language there.
    _v = platform_captions.variants(caption)
    rows.append({"post_id": post_id, "post_date": date.isoformat(), "time": time_,
                 "account": account, "series": series, "ref": ref, "media": media,
                 "channels": CHANNELS.get(media, "ig"),
                 "images": "|".join(images), "caption": caption,
                 "caption_fb": _v["fb"], "caption_li": _v["li"]})
    counts[series] = counts.get(series, 0) + 1


# ------------------------------------------------- book cards (growthwealth)
# OFF by default since 2026-09-04. The book series is owned by the two Claude
# scheduled tasks (ig-post-round2-1am / ig-post-round2b-7pm), which drive the
# browser against @ramongtzl.growthwealth. Having the agent publish the same
# 726 rows as well was posting every book card twice - and landing the second
# copy on @ramonhouses. Pass --with-books only if those tasks are retired.
INCLUDE_BOOKS = "--with-books" in sys.argv
for series, tag, capglob, hh in () if not INCLUDE_BOOKS else (
        ("Round 2", "r2", os.path.join(SMC, "2026-09", "drafts", "daily-cards", "captions-day-*.md"), "01:00"),
        ("Round 2b", "r2b", os.path.join(SMC, "2026-09", "drafts", "round-2b", "captions-r2b-*.md"), "14:00")):
    caps = {}
    for p in sorted(glob.glob(capglob)):
        caps.update(sections(p))
    best = {}
    for f in glob.glob(os.path.join(ARCH, "ramongtzl.growthwealth", "*-%s-day-*.png" % tag)):
        m = re.search(r"-%s-day-(\d+)" % tag, os.path.basename(f))
        if m:
            d = int(m.group(1))
            if d not in best or os.path.basename(f) > os.path.basename(best[d]):
                best[d] = f
    for d in sorted(best):
        if d < 3:
            continue                                    # days 1-2 posted by hand
        date = START + datetime.timedelta(days=d - 3)
        if DAYS and (date - START).days >= DAYS:
            continue
        sub = "r2" if tag == "r2" else "r2b"
        name = web_copy(best[d], os.path.join(ASSETS, sub), "%s-day-%03d" % (sub, d))
        add("%s-day-%03d" % (sub, d), date, hh, "growthwealth", series,
            "Day %03d" % d, ["%s/%s" % (sub, name)], caps.get(d, ""))

# -------------------------------------------------- carousels (ramonhouses)
for lang, root in (("en", "ramonhouses-realestate-carousels"),
                   ("es", "ramonhouses-realestate-carousels-es")):
    base = os.path.join(ARCH, root)
    if not os.path.isdir(base):
        continue
    for slot in sorted(s for s in os.listdir(base)
                       if os.path.isdir(os.path.join(base, s)) and s.startswith("w")):
        folder = os.path.join(base, slot)
        pngs = sorted(x for x in os.listdir(folder) if x.endswith(".png"))
        if not pngs:
            continue
        wk = int(slot[1:3])
        tue = W1_TUE + datetime.timedelta(days=7 * (wk - 1))
        # 2 carousels a week (Ramon, 2026-09-04): EN Tuesday, ES Wednesday.
        # The 'b' slots stay rendered as spare inventory but are not scheduled.
        if not slot.endswith("a"):
            continue
        date, hh = tue, "11:00"
        if DAYS and (date - W1_TUE).days >= DAYS:
            continue
        # Spanish mirrors run a day later so the two languages never collide
        if lang == "es":
            date = date + datetime.timedelta(days=1)
        spec = {"TITLE": "", "SUB": "", "CTA": "", "PILLAR": ""}
        sp = os.path.join(folder, "slides.txt")
        slides = []
        if os.path.exists(sp):
            body = io.open(sp, encoding="utf-8").read()
            for k in spec:
                m = re.search(r"^%s:\s*(.+)$" % k, body, re.M)
                if m:
                    spec[k] = m.group(1).strip()
            for m in re.finditer(r"^SLIDE \S+ \|\s*([^|]+)\|", body, re.M):
                slides.append(m.group(1).strip())
        hook = slides[0] if slides else spec["TITLE"]
        pts = "\n".join("%d. %s" % (i, s) for i, s in enumerate(slides[1:], 1))
        tags = ("#FraserValleyRealEstate #LangleyRealEstate #BCRealEstate "
                "#RealEstateTips #ramonhouses" if lang == "en" else
                "#BienesRaicesBC #FraserValley #Langley #InmobiliariaBC "
                "#AgenteEnEspanol #ramonhouses")
        swipe = ("Swipe through all %d." % len(pngs) if lang == "en"
                 else "Desliza para ver los %d." % len(pngs))
        caption = "\n\n".join([hook, pts, swipe, spec["CTA"], tags]).strip()
        sub = "car-%s/%s" % (lang, slot)
        names = [web_copy(os.path.join(folder, p), os.path.join(ASSETS, sub),
                          "%02d" % (i + 1)) for i, p in enumerate(pngs)]
        add("car-%s-%s" % (lang, slot), date, hh, "ramonhouses",
            "Carousel %s" % lang.upper(), slot,
            ["%s/%s" % (sub, n) for n in names], caption, "carousel")

        # ---- reel, if one has been rendered and it falls inside the window ----
        suffix = "-es" if lang == "es" else ""
        reel = os.path.join(folder, "%s%s-reel-music.mp4" % (slot, suffix))
        if slot.endswith("a") and os.path.exists(reel):
            # EN reel Friday 11:00, ES reel Saturday 11:00 - a few days after the
            # carousel, so the same idea lands twice in two formats rather than
            # twice on one day.
            if lang != "en":
                continue            # one reel a week now, EN only (Friday)
            rdate = tue + datetime.timedelta(days=3)
            if TODAY <= rdate <= TODAY + datetime.timedelta(weeks=REEL_WEEKS):
                os.makedirs(os.path.join(ASSETS, "reels"), exist_ok=True)
                rname = "%s%s.mp4" % (slot, suffix)
                dst = os.path.join(ASSETS, "reels", rname)
                if not os.path.exists(dst):
                    shutil.copy2(reel, dst)
                add("reel-%s-%s" % (lang, slot), rdate, "11:00", "ramonhouses",
                    "Reel %s" % lang.upper(), slot, ["reels/" + rname],
                    caption, "reel")

# ------------------------------------ daily single RE cards (ramonhouses)
# Ramon, 2026-09-04: one real-estate post a day, testing. Only 30 EN + 30 ES
# singles exist, so the two languages alternate to stretch the set. Carousels
# own Tue (EN) and Wed (ES) and the reel owns Fri, so singles fill Mon, Thu,
# Sat, Sun - 4 a week, which makes the 60 cards last ~15 weeks.
RE_START = datetime.date(2026, 9, 5)
RE_WEEKDAYS = (0, 3, 5, 6)              # Mon, Thu, Sat, Sun


def re_caps_en(path):
    """'## Day NN' -> the Instagram/Facebook caption only."""
    out = {}
    if not os.path.exists(path):
        return out
    text = io.open(path, encoding="utf-8").read().replace("\r", "")
    for m in re.finditer(r"^## Day (\d+)\b.*?\n### Instagram / Facebook caption"
                         r"\n(.*?)\n### ", text, re.S | re.M):
        out[int(m.group(1))] = m.group(2).strip()
    return out


def re_caps_es(path):
    """'## Dia NN ...' -> the first fenced block under that heading."""
    out = {}
    if not os.path.exists(path):
        return out
    text = io.open(path, encoding="utf-8").read().replace("\r", "")
    for chunk in text.split("\n## ")[1:]:
        head = chunk.split("\n", 1)[0]
        m = re.search(r'(\d+)', head)
        if not m:
            continue
        parts = chunk.split("\n```")
        if len(parts) < 3:
            continue
        body = parts[1].lstrip("\n")
        out[int(m.group(1))] = body.strip()
    return out


def re_cards(folder, pat):
    best = {}
    for f in glob.glob(os.path.join(ARCH, folder, "*.png")):
        m = re.search(pat, os.path.basename(f))
        if m:
            d = int(m.group(1))
            if d not in best or os.path.basename(f) > os.path.basename(best[d]):
                best[d] = f
    return best


_encaps = {}
for _p in sorted(glob.glob(os.path.join(SMC, "2026-09", "drafts", "real-estate",
                                        "captions-re-*.md"))):
    _encaps.update(re_caps_en(_p))
_escaps = re_caps_es(os.path.join(SMC, "2026-09", "drafts", "real-estate-es",
                                  "captions-es-cards.md"))

RE_SETS = [
    ("en", re_cards("ramonhouses-realestate", r"-re-day-(\d+)"), _encaps, "re-en"),
    ("es", re_cards("ramonhouses-realestate-es", r"-re-es-day-(\d+)"), _escaps, "re-es"),
]

# Interleave the two languages: en day1, es day1, en day2, es day2, ...
_queue = []
for _i in range(1, 1 + max(len(RE_SETS[0][1]), len(RE_SETS[1][1]))):
    for _lang, _cards, _caps, _sub in RE_SETS:
        if _i in _cards:
            _queue.append((_lang, _i, _cards[_i], _caps.get(_i, ""), _sub))

_d = RE_START
for _lang, _day, _src, _cap, _sub in _queue:
    while _d.weekday() not in RE_WEEKDAYS:
        _d += datetime.timedelta(days=1)
    if DAYS and (_d - RE_START).days >= DAYS:
        break
    _name = web_copy(_src, os.path.join(ASSETS, _sub), "%s-day-%02d" % (_sub, _day))
    add("%s-day-%02d" % (_sub, _day), _d, "10:00", "ramonhouses",
        "RE Single %s" % _lang.upper(), "Day %02d" % _day,
        ["%s/%s" % (_sub, _name)], _cap)
    _d += datetime.timedelta(days=1)

rows.sort(key=lambda r: (r["post_date"], r["time"], r["series"]))

f = io.open(os.path.join(HERE, "schedule.csv"), "w", encoding="utf-8-sig", newline="")
w = csv.DictWriter(f, fieldnames=["post_id", "post_date", "time", "account",
                                  "series", "ref", "media", "channels",
                                  "images", "caption",
                                  "caption_fb", "caption_li"])
w.writeheader()
w.writerows(rows)
f.close()

total = sum(os.path.getsize(os.path.join(r, x))
            for r, _, fs in os.walk(ASSETS) for x in fs)
nfiles = sum(len(fs) for _, _, fs in os.walk(ASSETS))
manifest = {"built": datetime.datetime.now().isoformat(timespec="seconds"),
            "posts": len(rows), "by_series": counts,
            "reel_window_weeks": REEL_WEEKS,
            "asset_files": nfiles, "asset_mb": round(total / 1048576.0, 1),
            "first": rows[0]["post_date"] if rows else None,
            "last": rows[-1]["post_date"] if rows else None}
io.open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8").write(
    json.dumps(manifest, indent=2))

print(json.dumps(manifest, indent=2))
blank = [r["post_id"] for r in rows if not r["caption"].strip()]
print("posts with no caption:", len(blank), blank[:5])
