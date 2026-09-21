# -*- coding: utf-8 -*-
"""Daily social posting brief (Routine 30).

Reads the live agent files in this clone - schedule.csv, post-log.csv,
state.json, health.json, recommendations.json - and writes:

    briefs/social-brief-email.html   Gmail-safe body (borders + text colour only)
    briefs/social-brief.html         full page with the signature masthead
    briefs/social-brief_YYYYMMDD_HHMM_Langley-BC.html   snapshot (never deleted)
    briefs/social-brief.txt          plain text
    briefs/subject.txt               the email subject line

and mirrors the four generic files into the vault
`20 - FILES APPS/12 - SOCIAL MEDIA CONTENT/_AGENT/briefs/`.

    python build_social_brief.py            # pulls the repo first
    python build_social_brief.py --no-pull

Nothing here invents a number: every count comes from post-log.csv and
schedule.csv. Recommendations come from recommendations.json (status open),
plus a few rule-based flags computed from the data.
"""
import csv, io, json, os, sys, subprocess, datetime, html, collections, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "briefs")
VAULT_OUT = r"G:\My Drive\RAMON VAULT\20 - FILES APPS\12 - SOCIAL MEDIA CONTENT\_AGENT\briefs"
SCHED = os.path.join(HERE, "schedule.csv")
LOG = os.path.join(HERE, "post-log.csv")
STATE = os.path.join(HERE, "state.json")
HEALTH = os.path.join(HERE, "health.json")
RECS = os.path.join(HERE, "recommendations.json")

# LinkedIn allow-list = the LI_SERIES repo variable (2026-09-18). Kept here so
# the brief shows the channels that will actually fire.
LI_SERIES = {"Blog Series EN", "Blog Series ES", "Carousel EN", "Open House", "Just Sold",
             "New Listing", "Price Reduced", "RE Single EN", "RE Single ES", "RE Quote EN", "RE Quote ES"}
# Tokens the agent cannot refresh itself. IG_TOKEN has no expiry since 2026-09-21.
TOKEN_EXPIRY = {"LinkedIn (LI_ACCESS_TOKEN)": datetime.date(2026, 11, 4),
                "Threads (THREADS_TOKEN)": datetime.date(2026, 11, 18)}
ACCOUNT = {"ramonhouses": "@ramonhouses", "growthwealth": "@ramongtzl.growthwealth"}
CHAN = {"ig": "Instagram", "fb": "Facebook", "li": "LinkedIn", "threads": "Threads", "yt": "YouTube"}
DAYS = "Mon Tue Wed Thu Fri Sat Sun".split()


def chan_label(key):
    base = key.split(":")[0]
    return CHAN.get(base, key)


def channels_for(row):
    ch = [c.strip() for c in row["channels"].split(",") if c.strip()]
    if row["series"] not in LI_SERIES and "li" in ch:
        ch.remove("li")
    order = ["ig", "fb", "li", "threads", "yt"]
    return [c for c in order if c in ch]


def first_line(text, n=80):
    t = (text or "").strip().splitlines()
    t = t[0] if t else ""
    return t if len(t) <= n else t[:n - 1] + "…"


def load():
    rows = list(csv.DictReader(io.open(SCHED, encoding="utf-8-sig")))
    log = list(csv.DictReader(io.open(LOG, encoding="utf-8")))
    state = json.load(io.open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"posted": {}}
    health = json.load(io.open(HEALTH, encoding="utf-8")) if os.path.exists(HEALTH) else {}
    recs = json.load(io.open(RECS, encoding="utf-8")) if os.path.exists(RECS) else []
    return rows, log, state, health, recs


def results_for(day, rows, log):
    """Per scheduled post of `day`: which channels are ok / error / silent."""
    by_id = {r["post_id"]: r for r in rows if r["post_date"] == day.isoformat()}
    hits = collections.defaultdict(dict)          # pid -> chan -> (status, when, err)
    for l in log:
        pid = l.get("post_id") or l.get(list(l.keys())[1], "")
        if pid not in by_id:
            continue
        key = l.get("target") or l.get(list(l.keys())[2], "")
        st = l.get("status") or l.get(list(l.keys())[6], "")
        when = (l.get("when") or l.get(list(l.keys())[0], ""))[11:16]
        err = l.get("error") or l.get(list(l.keys())[7], "")
        prev = hits[pid].get(key)
        if st == "ok" or prev is None:            # an ok anywhere wins over an earlier error
            hits[pid][key] = (st, when, err)
    out = []
    for pid, r in sorted(by_id.items(), key=lambda kv: (kv[1]["time"], kv[0])):
        wanted = channels_for(r)
        chans = []
        for c in wanted:
            found = [(k, v) for k, v in hits[pid].items() if k.split(":")[0] == c]
            if not found:
                chans.append((c, "silent", "", ""))
            else:
                k, (st, when, err) = found[0]
                chans.append((c, st, when, err))
        out.append((r, chans))
    return out


def log_columns(log):
    """post-log.csv has a header row; map by position to be safe."""
    if not log:
        return log
    keys = list(log[0].keys())
    fixed = []
    for l in log:
        fixed.append({"when": l[keys[0]], "post_id": l[keys[1]], "target": l[keys[2]],
                      "series": l[keys[3]], "ref": l[keys[4]], "id": l[keys[5]],
                      "status": l[keys[6]], "error": l[keys[7]] if len(keys) > 7 else ""})
    return fixed


def build(now, pull=True):
    if pull:
        subprocess.run(["git", "pull", "--rebase", "-q"], cwd=HERE, capture_output=True)
    rows, log, state, health, recs = load()
    log = log_columns(log)
    today = now.date()
    yday = today - datetime.timedelta(days=1)
    tmrw = today + datetime.timedelta(days=1)

    y_res = results_for(yday, rows, log)
    t_res = results_for(today, rows, log)     # today so far (for the 01:00 / early slots)
    t_rows = sorted([r for r in rows if r["post_date"] == today.isoformat()], key=lambda r: (r["time"], r["post_id"]))
    m_rows = sorted([r for r in rows if r["post_date"] == tmrw.isoformat()], key=lambda r: (r["time"], r["post_id"]))

    def tally(res):
        ok = err = silent = 0
        for _, chans in res:
            for _, st, _, _ in chans:
                if st == "ok": ok += 1
                elif st == "silent": silent += 1
                else: err += 1
        return ok, err, silent

    y_ok, y_err, y_silent = tally(y_res)
    y_total = y_ok + y_err + y_silent

    # 7-day failure list and last successful publish
    week_ago = (now - datetime.timedelta(days=7)).isoformat()
    week_err = [l for l in log if l["when"] >= week_ago and l["status"] != "ok"]
    last_ok = max((l["when"] for l in log if l["status"] == "ok"), default="")

    # rule-based flags
    flags = []
    if y_err:
        flags.append("%d publish%s failed yesterday - details below." % (y_err, "" if y_err == 1 else "es"))
    if y_silent:
        flags.append("%d scheduled publish%s ha%s no log row at all yesterday - the hourly Action probably did not "
                     "run that hour (GitHub cron skips). Force them with auth/dispatch.py post.yml dry_run=false post_ids=…"
                     % (y_silent, "" if y_silent == 1 else "es", "s" if y_silent == 1 else "ve"))
    for name, exp in TOKEN_EXPIRY.items():
        left = (exp - today).days
        if left <= 14:
            flags.append("%s expires in %d day%s (%s) - refresh it before then or that channel stops silently."
                         % (name, left, "" if left == 1 else "s", exp.isoformat()))
    if health.get("reel_weeks_left") is not None and health["reel_weeks_left"] < 6:
        flags.append("Reel window down to %.1f weeks - run Routine 21 (agent refresh)." % health["reel_weeks_left"])
    if last_ok and last_ok[:10] < yday.isoformat():
        flags.append("No successful publish since %s." % last_ok[:16].replace("T", " "))

    open_recs = [r for r in recs if r.get("status", "open") == "open"]

    # ---------- text ----------
    T = []
    T.append("SOCIAL POSTING BRIEF - %s" % today.strftime("%A %d %b %Y"))
    T.append("")
    T.append("YESTERDAY %s: %d/%d publishes ok, %d failed, %d silent" % (yday.strftime("%a %d %b"), y_ok, y_total, y_err, y_silent))
    for r, chans in y_res:
        parts = []
        for c, st, when, err in chans:
            mark = "ok" if st == "ok" else ("SILENT" if st == "silent" else "FAIL")
            parts.append("%s %s" % (CHAN[c], mark))
        T.append("  %s %-13s %-16s %-12s %s" % (r["time"], ACCOUNT[r["account"]], r["series"], r["ref"], " · ".join(parts)))
        for c, st, when, err in chans:
            if st not in ("ok", "silent") and err:
                T.append("        %s: %s" % (CHAN[c], err[:160]))
    T.append("")
    T.append("TODAY %s - %d posts" % (today.strftime("%a %d %b"), len(t_rows)))
    t_status = {r["post_id"]: chans for r, chans in t_res}
    for r in t_rows:
        ch = channels_for(r)
        done = all(st == "ok" for _, st, _, _ in t_status.get(r["post_id"], [])) and t_status.get(r["post_id"])
        T.append("  %s %-13s %-16s %-12s %s%s" % (r["time"], ACCOUNT[r["account"]], r["series"], r["ref"],
                                                  ", ".join(CHAN[c] for c in ch), "  [posted]" if done else ""))
        T.append("        " + first_line(r.get("caption", "")))
    T.append("")
    T.append("TOMORROW %s - %d posts" % (tmrw.strftime("%a %d %b"), len(m_rows)))
    for r in m_rows:
        T.append("  %s %-13s %-16s %-12s %s" % (r["time"], ACCOUNT[r["account"]], r["series"], r["ref"],
                                                ", ".join(CHAN[c] for c in channels_for(r))))
    T.append("")
    T.append("FLAGS")
    T.extend("  - " + f for f in flags) if flags else T.append("  none - agent healthy")
    T.append("")
    T.append("OPEN RECOMMENDATIONS (%d)" % len(open_recs))
    for r in open_recs:
        T.append("  - [%s] %s" % (r.get("date", ""), r["text"]))
    T.append("")
    T.append("Last successful publish: %s · reels queued through %s (%s weeks) · 7-day failures: %d"
             % (last_ok[:16].replace("T", " ") or "none", health.get("reels_through", "?"),
                health.get("reel_weeks_left", "?"), len(week_err)))
    text = "\n".join(T)

    # ---------- email html (no background fills - Gmail strips them) ----------
    NAVY, GOLD, MUTED, RED, GREEN = "#0b2545", "#c9a227", "#5b6b7c", "#b00020", "#1b7f3b"
    e = html.escape
    H = []
    H.append('<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1c2733;max-width:760px">')
    H.append('<div style="border-bottom:3px solid %s;padding:6px 0 10px"><div style="font-size:20px;font-weight:700;color:%s">'
             'Social posting brief</div><div style="color:%s">%s · @ramonhouses + @ramongtzl.growthwealth · times Pacific</div></div>'
             % (GOLD, NAVY, MUTED, e(today.strftime("%A %d %B %Y"))))

    def section(title, sub=""):
        H.append('<div style="margin:18px 0 6px;font-size:16px;font-weight:700;color:%s;border-left:4px solid %s;padding-left:8px">%s'
                 '%s</div>' % (NAVY, GOLD, e(title), ('<span style="font-weight:400;color:%s"> %s</span>' % (MUTED, e(sub))) if sub else ""))

    def table(head, body_rows):
        H.append('<table cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px">')
        H.append("<tr>" + "".join('<th align="left" style="border-bottom:2px solid %s;color:%s">%s</th>' % (NAVY, NAVY, e(h)) for h in head) + "</tr>")
        for cells in body_rows:
            H.append("<tr>" + "".join('<td valign="top" style="border-bottom:1px solid #dfe5ec">%s</td>' % c for c in cells) + "</tr>")
        H.append("</table>")

    # yesterday
    colour = GREEN if (y_err == 0 and y_silent == 0 and y_total) else RED
    section("Yesterday - %s" % yday.strftime("%a %d %b"),
            "%d of %d publishes ok" % (y_ok, y_total))
    body = []
    for r, chans in y_res:
        cells = []
        for c, st, when, err in chans:
            if st == "ok":
                cells.append('<span style="color:%s">%s ✓</span>' % (GREEN, CHAN[c]))
            elif st == "silent":
                cells.append('<span style="color:%s">%s — no run</span>' % (MUTED, CHAN[c]))
            else:
                cells.append('<span style="color:%s;font-weight:700">%s ✗</span>' % (RED, CHAN[c]))
        errs = [err for c, st, when, err in chans if st not in ("ok", "silent") and err]
        note = ('<div style="color:%s;font-size:12px">%s</div>' % (RED, e(errs[0][:180]))) if errs else ""
        body.append([e(r["time"]), e(ACCOUNT[r["account"]]), e(r["series"]) + " · " + e(r["ref"]), " · ".join(cells) + note])
    table(["Time", "Account", "Post", "Result"], body) if body else H.append('<div style="color:%s">nothing was scheduled</div>' % MUTED)

    # today
    section("Today - %s" % today.strftime("%a %d %b"), "%d posts" % len(t_rows))
    body = []
    for r in t_rows:
        st = t_status.get(r["post_id"], [])
        done = bool(st) and all(s == "ok" for _, s, _, _ in st)
        chans = ", ".join(CHAN[c] for c in channels_for(r))
        body.append([e(r["time"]), e(ACCOUNT[r["account"]]),
                     "<b>%s</b> · %s<div style=\"color:%s;font-size:12px\">%s</div>" % (e(r["series"]), e(r["ref"]), MUTED, e(first_line(r.get("caption", "")))),
                     e(chans) + (' <span style="color:%s">✓ posted</span>' % GREEN if done else "")])
    table(["Time", "Account", "Post", "Platforms"], body)

    # tomorrow
    section("Tomorrow - %s" % tmrw.strftime("%a %d %b"), "%d posts" % len(m_rows))
    body = [[e(r["time"]), e(ACCOUNT[r["account"]]), "%s · %s" % (e(r["series"]), e(r["ref"])),
             e(", ".join(CHAN[c] for c in channels_for(r)))] for r in m_rows]
    table(["Time", "Account", "Post", "Platforms"], body)

    # flags
    section("Flags")
    if flags:
        H.append("<ul>" + "".join('<li style="color:%s">%s</li>' % (RED, e(f)) for f in flags) + "</ul>")
    else:
        H.append('<div style="color:%s">None - agent healthy. Last successful publish %s.</div>' % (GREEN, e(last_ok[:16].replace("T", " "))))

    # recommendations
    section("Exposure & growth - open recommendations", "%d" % len(open_recs))
    if open_recs:
        H.append("<ol>" + "".join('<li style="margin:4px 0"><span style="color:%s;font-size:12px">%s</span> %s</li>'
                                  % (MUTED, e(r.get("date", "")), e(r["text"])) for r in open_recs) + "</ol>")
    else:
        H.append('<div style="color:%s">Nothing open.</div>' % MUTED)

    H.append('<div style="margin-top:16px;padding-top:8px;border-top:1px solid #dfe5ec;color:%s;font-size:12px">'
             'Last successful publish %s · reels queued through %s (%s weeks) · %d failures in the last 7 days · '
             'built %s from schedule.csv / post-log.csv</div></div>'
             % (MUTED, e(last_ok[:16].replace("T", " ") or "none"), e(str(health.get("reels_through", "?"))),
                e(str(health.get("reel_weeks_left", "?"))), len(week_err), e(now.strftime("%Y-%m-%d %H:%M"))))
    email_html = "\n".join(H)

    # ---------- full page ----------
    page = PAGE_TMPL.replace("{{BODY}}", email_html).replace("{{STAMP}}", now.strftime("%Y-%m-%d %H:%M")) \
                    .replace("{{TITLE}}", "Social posting brief - %s" % today.isoformat())

    # subject
    if y_total and y_err == 0 and y_silent == 0:
        head = "all %d ok yesterday" % y_total
    elif y_total:
        head = "%d/%d ok yesterday, %d to check" % (y_ok, y_total, y_err + y_silent)
    else:
        head = "nothing scheduled yesterday"
    subject = "Social brief %s — %s · %d posts today" % (today.strftime("%a %d %b"), head, len(t_rows))

    os.makedirs(OUT, exist_ok=True)
    stamp = now.strftime("%Y%m%d_%H%M")
    files = {"social-brief-email.html": email_html, "social-brief.html": page,
             "social-brief.txt": text, "subject.txt": subject,
             "social-brief_%s_Langley-BC.html" % stamp: page}
    for name, content in files.items():
        io.open(os.path.join(OUT, name), "w", encoding="utf-8").write(content)
    try:
        os.makedirs(VAULT_OUT, exist_ok=True)
        for name, content in files.items():
            io.open(os.path.join(VAULT_OUT, name), "w", encoding="utf-8").write(content)
    except OSError as ex:
        print("vault mirror skipped: %s" % ex)
    print(subject)
    print(text)
    return subject


PAGE_TMPL = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{{TITLE}}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{margin:0;background:#f4f6f9;font-family:Segoe UI,Arial,sans-serif;color:#1c2733}
.brandbar{background:#0b2545;color:#fff;text-align:center;padding:16px 12px}
.brandbar .name-line{font-size:18px}.brandbar .name-line strong{color:#fff}
.brandbar .mba{background:#c9a227;color:#0b2545;font-weight:700;font-size:11px;padding:1px 6px;border-radius:4px;margin-left:4px}
.brandbar .name-line span:last-child{color:#a9b7c6}
.brandbar .tagline{color:#c9a227;text-transform:uppercase;letter-spacing:.14em;font-weight:700;font-size:12px;margin-top:4px}
.brandbar .links{margin-top:10px;display:flex;justify-content:center;flex-wrap:wrap;gap:8px}
.brandbar .links a{display:inline-flex;align-items:center;gap:6px;color:#e6ecf2;text-decoration:none;border:1px solid #33507a;background:#132f5a;border-radius:999px;padding:5px 12px;font-size:12px}
.brandbar .links svg{width:14px;height:14px}
.infobar{background:#fff;border-bottom:1px solid #dfe5ec;padding:8px 16px;font-size:12px;color:#5b6b7c;display:flex;gap:18px;flex-wrap:wrap}
.wrap{max-width:820px;margin:18px auto;background:#fff;border:1px solid #dfe5ec;border-radius:10px;padding:18px 22px}
</style></head><body>
<div class="brandbar">
  <div class="name-line"><strong>Ramon Gutierrez</strong><span class="mba">MBA</span> <span>&middot; Growth &amp; Wealth</span></div>
  <div class="tagline">Investor &middot; Mentor &middot; Advisor</div>
  <div class="links">
    <a href="https://www.linkedin.com/in/ramongtzl/" target="_blank" rel="noopener">LinkedIn</a>
    <a href="https://www.instagram.com/ramonhouses/" target="_blank" rel="noopener">Houses</a>
    <a href="https://www.facebook.com/ramongtzl.houses" target="_blank" rel="noopener">Facebook</a>
    <a href="https://www.instagram.com/ramongtzl.growthwealth/" target="_blank" rel="noopener">Growth</a>
    <a href="https://ramonhouses.com/masterminds" target="_blank" rel="noopener">Explore My Resources</a>
    <a href="https://growth-and-wealth-superstars.ca/" target="_blank" rel="noopener">Superstars Multiplier</a>
  </div>
</div>
<div class="infobar"><span>Last updated: {{STAMP}}</span><span>File: 20 - FILES APPS\\12 - SOCIAL MEDIA CONTENT\\_AGENT\\briefs\\social-brief.html</span><span id="views"></span></div>
<div class="wrap">{{BODY}}</div>
<script>try{var k='views:social-brief',n=(+localStorage.getItem(k)||0)+1;localStorage.setItem(k,n);document.getElementById('views').textContent='Views on this device: '+n}catch(e){}</script>
</body></html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pull", action="store_true")
    ap.add_argument("--date", help="build as if today were YYYY-MM-DD")
    a = ap.parse_args()
    now = datetime.datetime.now()
    if a.date:
        now = datetime.datetime.combine(datetime.date.fromisoformat(a.date), now.time())
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    build(now, pull=not a.no_pull)
