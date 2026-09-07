# -*- coding: utf-8 -*-
"""Instagram posting agent - two accounts, one schedule.

Runs hourly. Reads schedule.csv, works out what is due in the current Pacific
hour, publishes it through the Instagram Graph API, records the result in
state.json.

    @ramongtzl.growthwealth   Round 2   01:00   single image
                              Round 2b  14:00   single image
    @ramonhouses              carousel  Tue 11:00 / Sun 12:00   8 slides
                              reel      Fri 11:00 EN / Sat 11:00 ES   MP4

Why hourly rather than a cron per slot: GitHub Actions cron is UTC, and Pacific
shifts an hour twice a year. Running hourly and deciding in local time means the
schedule never drifts at a DST boundary.

Environment (GitHub repo secrets):
    IG_TOKEN            long-lived user access token
    IG_USER_GROWTH      Instagram Business account id for @ramongtzl.growthwealth
    IG_USER_HOUSES      Instagram Business account id for @ramonhouses
    ASSET_BASE_URL      public https base the images are served from
    DRY_RUN             "1" to log what would post without calling the API

Extra channels (all optional - see channels.py and SETUP.md):
    FB_PAGE_IDS                          Facebook Pages (comma-separated ids)
    LI_ACCESS_TOKEN / LI_PERSON_URN / LI_ORG_ID    LinkedIn profile + company
    YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN   YouTube Shorts

Each schedule row carries a `channels` column ("ig,fb,li"). Every target is
tracked separately in state.json, so a failed LinkedIn post is retried next
hour without re-posting the Instagram copy.

Never commit a token. Never hardcode one here.
"""
import os, io, csv, json, sys, time, urllib.request, urllib.parse, urllib.error
import datetime
import channels as extra

def _pacific():
    """America/Vancouver, however this machine can give it to us.

    zoneinfo needs the IANA database, which Linux has natively but Windows
    does not unless the `tzdata` package is installed (see requirements.txt).
    Falling back to system local time is correct on Ramon's machine, which is
    already on Pacific, and the CI runner always has tzdata.
    """
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("America/Vancouver")
    except Exception:                                   # noqa: BLE001
        print("NOTE: no IANA tz database - using system local time")
        return None

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.join(HERE, "schedule.csv")
STATE = os.path.join(HERE, "state.json")
LOG = os.path.join(HERE, "post-log.csv")

GRAPH = "https://graph.facebook.com/v21.0"
TZ = _pacific()

TOKEN = os.environ.get("IG_TOKEN", "")
USERS = {
    "growthwealth": os.environ.get("IG_USER_GROWTH", ""),
    "ramonhouses": os.environ.get("IG_USER_HOUSES", ""),
}
BASE = os.environ.get("ASSET_BASE_URL", "").rstrip("/")

# The schedule stores image paths relative to the assets/ directory
# ("re-es/re-es-day-01.jpg"), but Pages serves the whole repo, so the public
# URL needs the assets/ segment in it. If the secret points at the repo root
# the images 404, GitHub answers with an HTML error page, and Graph reports
# the useless "Only photo or video can be accepted as media type" - which is
# how this was found on 2026-09-06. Appending it here means the secret works
# whether or not it already carries the segment.
if BASE and os.path.isdir(os.path.join(HERE, "assets"))         and not BASE.endswith("/assets"):
    BASE += "/assets"
DRY = os.environ.get("DRY_RUN", "") == "1"


# --------------------------------------------------------------- http
def _call(url, data=None, tries=3):
    for n in range(tries):
        try:
            body = urllib.parse.urlencode(data).encode() if data else None
            req = urllib.request.Request(url, data=body)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode()[:400]
            # 4xx other than rate limiting will not fix themselves
            if e.code < 500 and "rate" not in detail.lower():
                raise RuntimeError("HTTP %s: %s" % (e.code, detail))
            if n == tries - 1:
                raise RuntimeError("HTTP %s after %d tries: %s" % (e.code, tries, detail))
        except Exception as e:                          # noqa: BLE001
            if n == tries - 1:
                raise
        time.sleep(5 * (n + 1))


def _wait_ready(container_id, timeout=180):
    """A container must report FINISHED before it can be published."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = _call("%s/%s?fields=status_code&access_token=%s"
                  % (GRAPH, container_id, urllib.parse.quote(TOKEN)))
        st = r.get("status_code")
        if st == "FINISHED":
            return True
        if st == "ERROR":
            raise RuntimeError("container %s reported ERROR" % container_id)
        time.sleep(5)
    raise RuntimeError("container %s not ready within %ds" % (container_id, timeout))


# --------------------------------------------------------------- publish
def publish_single(user_id, image_url, caption):
    c = _call("%s/%s/media" % (GRAPH, user_id),
              {"image_url": image_url, "caption": caption, "access_token": TOKEN})
    _wait_ready(c["id"])
    r = _call("%s/%s/media_publish" % (GRAPH, user_id),
              {"creation_id": c["id"], "access_token": TOKEN})
    return r.get("id")


def publish_carousel(user_id, image_urls, caption):
    if not 2 <= len(image_urls) <= 10:
        raise RuntimeError("carousel needs 2-10 images, got %d" % len(image_urls))
    children = []
    for u in image_urls:
        c = _call("%s/%s/media" % (GRAPH, user_id),
                  {"image_url": u, "is_carousel_item": "true", "access_token": TOKEN})
        children.append(c["id"])
    for cid in children:
        _wait_ready(cid)
    parent = _call("%s/%s/media" % (GRAPH, user_id),
                   {"media_type": "CAROUSEL",
                    "children": ",".join(children),
                    "caption": caption, "access_token": TOKEN})
    _wait_ready(parent["id"])
    r = _call("%s/%s/media_publish" % (GRAPH, user_id),
              {"creation_id": parent["id"], "access_token": TOKEN})
    return r.get("id")


def publish_reel(user_id, video_url, caption):
    """Reels use the same permission as images, but the container takes far
    longer to become FINISHED because Meta has to transcode the file."""
    c = _call("%s/%s/media" % (GRAPH, user_id),
              {"media_type": "REELS", "video_url": video_url,
               "caption": caption, "share_to_feed": "true",
               "access_token": TOKEN})
    _wait_ready(c["id"], timeout=600)
    r = _call("%s/%s/media_publish" % (GRAPH, user_id),
              {"creation_id": c["id"], "access_token": TOKEN})
    return r.get("id")


# --------------------------------------------------------------- state
def load_state():
    if os.path.exists(STATE):
        return json.loads(io.open(STATE, encoding="utf-8").read())
    return {"posted": {}}


def save_state(s):
    io.open(STATE, "w", encoding="utf-8").write(json.dumps(s, indent=2))


def log_row(row):
    new = not os.path.exists(LOG)
    f = io.open(LOG, "a", encoding="utf-8", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["run_at_pacific", "post_id", "account", "series",
                    "ref", "media_id", "status", "detail"])
    w.writerow(row)
    f.close()


# --------------------------------------------------------------- main
def due_rows(now):
    """Rows scheduled for today whose hour matches, and not already posted.

    POST_IDS overrides the date and hour test with an explicit comma-separated
    list of post_ids. It exists so a real publish can be exercised on demand
    instead of waiting for a slot - the rest of the path is untouched, so what
    it proves is the path that actually runs. State dedupe still applies, so a
    row forced early does not post again at its scheduled hour.
    """
    forced = [x.strip() for x in os.environ.get("POST_IDS", "").split(",")
              if x.strip()]
    if forced:
        by_id = {r["post_id"]: r for r in
                 csv.DictReader(io.open(SCHED, encoding="utf-8-sig"))}
        missing = [f for f in forced if f not in by_id]
        if missing:
            print("UNKNOWN post_id: %s" % ", ".join(missing))
        return [by_id[f] for f in forced if f in by_id]

    today = now.date().isoformat()
    hour = now.hour
    out = []
    for r in csv.DictReader(io.open(SCHED, encoding="utf-8-sig")):
        if r["post_date"] != today:
            continue
        try:
            if int(r["time"].split(":")[0]) != hour:
                continue
        except ValueError:
            continue
        out.append(r)
    return out


def main():
    now = datetime.datetime.now(TZ) if TZ else datetime.datetime.now()
    print("run at %s (Pacific)" % now.strftime("%Y-%m-%d %H:%M %Z"))

    missing = [k for k, v in
               [("IG_TOKEN", TOKEN), ("ASSET_BASE_URL", BASE)] if not v]
    if missing and not DRY:
        print("MISSING CONFIG: %s - nothing posted" % ", ".join(missing))
        return 1

    rows = due_rows(now)
    if not rows:
        print("nothing due this hour")
        return 0

    state = load_state()
    posted = state.setdefault("posted", {})
    fails = 0

    for r in rows:
        pid = r["post_id"]
        acct = r["account"]
        uid = USERS.get(acct, "")
        imgs = [BASE + "/" + p.strip() for p in r["images"].split("|") if p.strip()]
        caption = r["caption"]
        kind = (r.get("media") or "").strip().lower() or (
            "carousel" if len(imgs) > 1 else "image")
        chans = set(c.strip().lower() for c in
                    (r.get("channels") or "ig").split(",") if c.strip())

        # state per target. Older entries were {"at","media_id"} = IG only.
        entry = posted.setdefault(pid, {})
        targets = entry.setdefault("targets", {})
        if entry.get("media_id") and "ig:" + acct not in targets:
            targets["ig:" + acct] = {"id": entry["media_id"], "at": entry.get("at", "")}

        wanted = []
        if "ig" in chans:
            wanted.append("ig:" + acct)
        if all(k in targets for k in wanted) and not ({"fb", "li", "yt"} & chans):
            print("  skip %s (already posted %s)" % (pid, entry.get("at", "")))
            continue

        print("  %s -> %s (%s, %s, %d file%s, channels %s)"
              % (pid, acct, r["series"], kind, len(imgs),
                 "" if len(imgs) == 1 else "s", ",".join(sorted(chans))))
        if DRY:
            print("     DRY RUN, first url: %s" % (imgs[0] if imgs else "(none)"))
            print("     caption: %s..." % caption[:70].replace("\n", " "))

        # ---- Instagram ----
        ig_key = "ig:" + acct
        if "ig" in chans and ig_key not in targets:
            if not uid and not DRY:
                print("     FAIL: no IG user id configured for %s" % acct)
                log_row([now.isoformat(), pid, acct, r["series"], r["ref"], "",
                         "no-account-id", ""])
                fails += 1
            elif not DRY:
                try:
                    if kind == "reel":
                        mid = publish_reel(uid, imgs[0], caption)
                    elif kind == "carousel" or len(imgs) > 1:
                        mid = publish_carousel(uid, imgs, caption)
                    else:
                        mid = publish_single(uid, imgs[0], caption)
                    targets[ig_key] = {"id": mid, "at": now.isoformat()}
                    entry["at"] = now.isoformat()
                    entry["media_id"] = mid
                    log_row([now.isoformat(), pid, ig_key, r["series"], r["ref"], mid, "ok", ""])
                    print("     ig ok -> %s" % mid)
                except Exception as e:                  # noqa: BLE001
                    fails += 1
                    log_row([now.isoformat(), pid, ig_key, r["series"], r["ref"], "",
                             "error", str(e)[:300]])
                    print("     ig FAILED: %s" % str(e)[:300])
        elif "ig" in chans:
            print("     skip %s (done %s)" % (ig_key, targets[ig_key].get("at", "")))

        # ---- Facebook / LinkedIn / YouTube ----
        done, errs = extra.fan_out(chans - {"ig"}, kind, imgs, caption, r["ref"],
                                   TOKEN, targets, dry=DRY,
                                   captions={"fb": r.get("caption_fb", ""),
                                             "li": r.get("caption_li", "")})
        for key, res in done.items():
            res["at"] = now.isoformat()
            targets[key] = res
            log_row([now.isoformat(), pid, key, r["series"], r["ref"], res.get("id", ""), "ok", ""])
        for key, err in errs:
            fails += 1
            log_row([now.isoformat(), pid, key, r["series"], r["ref"], "", "error", err])
        if not entry.get("at") and targets:
            entry["at"] = now.isoformat()
        if not targets:
            posted.pop(pid, None)

    if not DRY:
        save_state(state)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

