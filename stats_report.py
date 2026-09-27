# -*- coding: utf-8 -*-
"""Turn the encrypted daily snapshot (stats/stats.enc, written by the
collect-stats Action) into the "Audience & what worked" part of the social
brief. Everything here is measured - nothing is estimated or invented.

    python stats_report.py            # print the full analysis
    python stats_report.py --setup    # one-time: create the key and save it as STATS_KEY

The key lives OUTSIDE Google Drive and outside the repo:
    %USERPROFILE%\\.ramon-social\\stats.key

Used by build_social_brief.py: section(now) -> (text_lines, html) or None.
The daily brief shows followers + the top posts of the last 14 days; on
Mondays it adds the full "what worked" breakdown (series, EN vs ES, hour,
platform, YouTube).
"""
import os, sys, io, csv, json, html, datetime, statistics, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ENC = os.path.join(HERE, "stats", "stats.enc")
KEY = os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".ramon-social", "stats.key")
NAVY, GOLD, MUTED, RED, GREEN = "#0b2545", "#c9a227", "#5b6b7c", "#b00020", "#1b7f3b"
ACCT = {"growthwealth": "@ramongtzl.growthwealth", "ramonhouses": "@ramonhouses"}
PAGE_ACCT = {"414239392030697": "ramonhouses", "543998318793132": "growthwealth"}
MIN_AGE_H = 48          # a post needs two days before its numbers are comparable


def setup():
    from cryptography.fernet import Fernet
    sys.path.insert(0, os.path.join(HERE, "auth"))
    from github_secret import set_secret
    if os.path.exists(KEY):
        sys.exit("key already exists at %s - delete it first only if you mean to re-key" % KEY)
    os.makedirs(os.path.dirname(KEY), exist_ok=True)
    k = Fernet.generate_key().decode()
    open(KEY, "w").write(k)
    set_secret("STATS_KEY", k)
    print("key written to", KEY)


def load():
    if not (os.path.exists(ENC) and os.path.exists(KEY)):
        return None
    from cryptography.fernet import Fernet
    try:
        return json.loads(Fernet(open(KEY).read().strip().encode()).decrypt(open(ENC, "rb").read()))
    except Exception:                                 # noqa: BLE001
        return None


def owner(p):
    a = p["account"]
    if a.startswith("ig:"):
        return a[3:]
    if a.startswith("fb:"):
        return PAGE_ACCT.get(a[3:], "?")
    return "ramonhouses"                              # yt / threads only carry houses posts


def eng(p):
    return (p.get("likes") or 0) + (p.get("comments") or 0) + (p.get("shares") or 0) + (p.get("saved") or 0)


def captions():
    try:
        rows = csv.DictReader(io.open(os.path.join(HERE, "schedule.csv"), encoding="utf-8-sig"))
        out = {}
        for r in rows:
            line = next((l.strip() for l in r["caption"].splitlines() if l.strip() and not l.startswith("#")), "")
            out[r["post_id"]] = line[:70]
        return out
    except OSError:
        return {}


def analyse(snap, now):
    posts = snap["posts"]
    for p in posts:
        t = datetime.datetime.fromisoformat(p["posted"])
        p["_age_h"] = (now.astimezone(t.tzinfo) - t).total_seconds() / 3600
        p["_hour"] = t.hour
        p["_owner"] = owner(p)
        p["_lang"] = "ES" if p["series"].endswith(" ES") else ("EN" if p["series"].endswith(" EN") else "")
    # one row per post_id, platforms summed
    by_post = collections.OrderedDict()
    for p in posts:
        b = by_post.setdefault(p["post_id"], {"post_id": p["post_id"], "series": p["series"], "ref": p["ref"],
                                              "owner": p["_owner"], "lang": p["_lang"], "hour": p["_hour"],
                                              "age_h": p["_age_h"], "total": 0, "ig": None, "fb": None, "yt_views": None,
                                              "permalink": None})
        b["total"] += eng(p)
        if p["account"].startswith("ig:"):
            b["ig"] = eng(p); b["permalink"] = p.get("permalink")
        elif p["account"].startswith("fb:"):
            b["fb"] = eng(p)
        elif p["account"] == "yt":
            b["yt_views"] = p.get("views")
    ripe = [b for b in by_post.values() if b["age_h"] >= MIN_AGE_H]

    def avg_by(key, items):
        g = collections.defaultdict(list)
        for b in items:
            g[key(b)].append(b["total"])
        return sorted(((k, statistics.mean(v), len(v)) for k, v in g.items() if k not in ("", None)),
                      key=lambda x: -x[1])

    out = {"posts": list(by_post.values()), "ripe": ripe}
    for o in ACCT:
        mine = [b for b in ripe if b["owner"] == o]
        out["top_" + o] = sorted(mine, key=lambda b: -b["total"])[:10]
        out["series_" + o] = avg_by(lambda b: b["series"], mine)
        out["hour_" + o] = avg_by(lambda b: b["hour"], mine)
    out["lang"] = avg_by(lambda b: b["lang"], [b for b in ripe if b["owner"] == "ramonhouses"])
    plat = collections.defaultdict(list)
    for p in posts:
        if p["_age_h"] >= MIN_AGE_H:
            plat[p["account"].split(":")[0]].append(eng(p))
    out["platform"] = sorted(((k, statistics.mean(v), len(v)) for k, v in plat.items()), key=lambda x: -x[1])
    out["yt_top"] = sorted([p for p in posts if p["account"] == "yt"], key=lambda p: -(p.get("views") or 0))[:5]
    return out


def follower_rows(snap):
    hist = snap.get("followers_history", [])
    last = hist[-1] if hist else {}

    def back(days):
        cut = (datetime.date.fromisoformat(last["date"]) - datetime.timedelta(days=days)).isoformat()
        older = [h for h in hist if h["date"] <= cut]
        return older[-1] if older else None

    d1, d7 = back(1), back(7)
    rows = []
    for k, v in snap["accounts"].items():
        name = v.get("name") or k.split(":", 1)[1]
        plat = {"ig": "Instagram", "fb": "Facebook", "yt": "YouTube"}[k.split(":")[0]]
        if k.startswith("ig:"):
            name = ACCT.get(name, name)
        f = v.get("followers")

        def delta(h):
            if not h or h.get(k) is None or f is None:
                return None
            return f - h[k]
        rows.append((plat, name, f, delta(d1), delta(d7)))
    return rows, (len(hist) - 1 if hist else 0)


def sign(n):
    return "—" if n is None else ("+%d" % n if n > 0 else str(n))


def section(now, full=None):
    """(text_lines, html) for the brief, or None when there is no snapshot yet."""
    snap = load()
    if not snap:
        return None
    full = now.weekday() == 0 if full is None else full
    a = analyse(snap, now)
    cap = captions()
    e = html.escape
    fol, days = follower_rows(snap)
    T, H = [], []

    def h_table(head, rows):
        H.append('<table cellpadding="5" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;margin:4px 0 10px">')
        H.append("<tr>" + "".join('<th align="left" style="border-bottom:2px solid %s;color:%s">%s</th>' % (NAVY, NAVY, e(h)) for h in head) + "</tr>")
        for cells in rows:
            H.append("<tr>" + "".join('<td valign="top" style="border-bottom:1px solid #dfe5ec">%s</td>' % c for c in cells) + "</tr>")
        H.append("</table>")

    def sub(t):
        H.append('<div style="font-weight:700;color:%s;margin-top:10px">%s</div>' % (NAVY, e(t)))
        T.append(""); T.append("  " + t.upper())

    # followers
    sub("Followers")
    h_table(["Platform", "Account", "Followers", "1 day", "7 days"],
            [[e(p), e(n), "%s" % ("?" if f is None else "{:,}".format(f)), sign(d1), sign(d7)] for p, n, f, d1, d7 in fol])
    for p, n, f, d1, d7 in fol:
        T.append("    %-9s %-26s %6s  1d %4s  7d %4s" % (p, n, f, sign(d1), sign(d7)))
    if days < 7:
        H.append('<div style="color:%s;font-size:12px">History started %d day%s ago - the 7-day change fills in after a week.</div>'
                 % (MUTED, days, "" if days == 1 else "s"))

    # top posts
    recent = sorted([b for b in a["ripe"] if b["age_h"] <= 14 * 24], key=lambda b: -b["total"])
    n_top = 10 if full else 5
    for o, label in ACCT.items():
        rows = [b for b in recent if b["owner"] == o][:n_top]
        if not rows:
            continue
        sub("Top %d posts, last 14 days - %s" % (len(rows), label))
        h_table(["#", "Post", "Likes+comments", "IG", "FB", "YT views"],
                [[str(i + 1),
                  ('<a href="%s" style="color:%s">%s · %s</a>' % (e(b["permalink"]), NAVY, e(b["series"]), e(b["ref"]))
                   if b["permalink"] else "%s · %s" % (e(b["series"]), e(b["ref"])))
                  + '<div style="color:%s;font-size:12px">%s</div>' % (MUTED, e(cap.get(b["post_id"], ""))),
                  "<b>%d</b>" % b["total"], sign_blank(b["ig"]), sign_blank(b["fb"]), sign_blank(b["yt_views"])]
                 for i, b in enumerate(rows)])
        for i, b in enumerate(rows):
            T.append("    %2d. %-4d %-16s %-10s %s" % (i + 1, b["total"], b["series"], b["ref"], cap.get(b["post_id"], "")[:50]))

    if full:
        for o, label in ACCT.items():
            s = a["series_" + o]
            if s:
                sub("Average likes+comments per post by series - %s" % label)
                h_table(["Series", "Avg", "Posts"], [[e(k), "%.1f" % m, str(n)] for k, m, n in s])
                T.extend("    %-18s %5.1f  (%d posts)" % (k, m, n) for k, m, n in s)
        if a["lang"]:
            sub("English vs Spanish - @ramonhouses")
            h_table(["Language", "Avg", "Posts"], [[k, "%.1f" % m, str(n)] for k, m, n in a["lang"]])
            T.extend("    %-3s %5.1f  (%d posts)" % x for x in a["lang"])
        for o, label in ACCT.items():
            hrs = a["hour_" + o]
            if len(hrs) > 1:
                sub("By hour actually posted (Pacific) - %s" % label)
                h_table(["Hour", "Avg", "Posts"], [["%02d:00" % k, "%.1f" % m, str(n)] for k, m, n in hrs])
                T.extend("    %02d:00 %5.1f  (%d posts)" % x for x in hrs)
        if a["platform"]:
            sub("Average likes+comments per publish, by platform")
            names = {"ig": "Instagram", "fb": "Facebook", "yt": "YouTube"}
            h_table(["Platform", "Avg", "Publishes"], [[names.get(k, k), "%.1f" % m, str(n)] for k, m, n in a["platform"]])
            T.extend("    %-9s %5.1f  (%d)" % (names.get(k, k), m, n) for k, m, n in a["platform"])
        if a["yt_top"]:
            sub("YouTube Shorts by views")
            h_table(["Short", "Views", "Likes"], [["%s · %s" % (e(p["series"]), e(p["ref"])), str(p.get("views", 0)),
                                                   str(p.get("likes", 0))] for p in a["yt_top"]])
            T.extend("    %-24s %6d views" % (p["series"] + " " + p["ref"], p.get("views", 0)) for p in a["yt_top"])

    notes = ["Posts under 48 h old are left out of the rankings.",
             "Instagram views, reach and saves need the instagram_manage_insights permission"
             + (" - it is ON." if snap.get("ig_insights") else " - not granted yet, so IG counts are likes + comments only."),
             "Threads and LinkedIn are not measured (their tokens have no read-stats permission)."]
    if snap.get("error_counts"):
        notes.append("Some reads failed: %s." % ", ".join("%s %d" % kv for kv in snap["error_counts"].items()))
    H.append('<div style="color:%s;font-size:12px">%s Snapshot %s UTC.</div>'
             % (MUTED, e(" ".join(notes)), e(snap["collected_utc"][:16].replace("T", " "))))
    T.append("    " + " ".join(notes))
    return T, "\n".join(H)


def sign_blank(n):
    return "" if n is None else "{:,}".format(n)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--setup" in sys.argv:
        setup()
    else:
        r = section(datetime.datetime.now().astimezone(), full=True)
        print("\n".join(r[0]) if r else "no snapshot yet (or no key) - run the collect-stats Action first")
