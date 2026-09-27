# -*- coding: utf-8 -*-
"""Daily engagement snapshot for everything the agent has posted. READ-ONLY:
it never posts, edits or deletes anything.

Runs in GitHub Actions (stats.yml) because the tokens live only in the repo
secrets. The repo is public, so the result is ENCRYPTED with STATS_KEY
(Fernet) before it is committed as stats/stats.enc - only the machine holding
the same key (%USERPROFILE%\\.ramon-social\\stats.key) can read it, through
stats_report.py.

What each token can see today (no new permissions needed):
  Instagram  like_count, comments_count per post, followers_count  (instagram_basic)
  Facebook   reactions, comments, shares per post, Page fans        (pages_read_engagement)
  YouTube    views, likes, comments per Short, channel subscribers  (youtube.readonly)
  Threads    nothing yet - needs threads_manage_insights
  LinkedIn   nothing yet - needs r_member_social (restricted by LinkedIn)
Views, reach, saves and shares on Instagram need instagram_manage_insights;
when that scope appears on IG_TOKEN the IG block below picks them up on its own.
"""
import os, sys, csv, json, datetime, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from channels import _http, GRAPH, fb_pages          # noqa: E402

OUT = os.path.join(HERE, "stats", "stats.enc")
TOK = os.environ.get("IG_TOKEN", "")
q = urllib.parse.quote


def fernet():
    from cryptography.fernet import Fernet
    key = os.environ.get("STATS_KEY", "")
    if not key:
        sys.exit("STATS_KEY secret is missing - refusing to write stats unencrypted")
    return Fernet(key.encode())


def try_get(url):
    try:
        return _http(url, tries=2, timeout=60), None
    except Exception as e:                            # noqa: BLE001
        return None, str(e)[:200]


def load_previous(f):
    """Keep the follower history across runs (it lives inside the encrypted file)."""
    if not os.path.exists(OUT):
        return {}
    try:
        return json.loads(f.decrypt(open(OUT, "rb").read()))
    except Exception:                                 # noqa: BLE001
        return {}


def ig_insights_ok():
    d, _ = try_get("%s/debug_token?input_token=%s&access_token=%s" % (GRAPH, q(TOK), q(TOK)))
    return "instagram_manage_insights" in ((d or {}).get("data", {}).get("scopes") or [])


def main():
    f = fernet()
    prev = load_previous(f)
    now = datetime.datetime.now(datetime.timezone.utc)
    log = list(csv.DictReader(open(os.path.join(HERE, "post-log.csv"), encoding="utf-8-sig")))
    ok = [r for r in log if r["status"] == "ok" and r["media_id"]]
    posts, errors, accounts = [], {}, {}

    def err(ch, msg):
        errors.setdefault(ch, []).append(msg)

    # ---------------------------------------------------------- Instagram
    insights = ig_insights_ok()
    for label, key in (("growthwealth", "IG_USER_GROWTH"), ("ramonhouses", "IG_USER_HOUSES")):
        d, e = try_get("%s/%s?fields=username,followers_count,media_count&access_token=%s"
                       % (GRAPH, os.environ.get(key, ""), q(TOK)))
        if d:
            accounts["ig:" + label] = {"followers": d.get("followers_count"),
                                       "posts": d.get("media_count")}
        else:
            err("ig", "%s account: %s" % (label, e))

    # ---------------------------------------------------------- Facebook
    pages = {}
    try:
        pages = fb_pages(TOK)
    except Exception as e:                            # noqa: BLE001
        err("fb", "page tokens: %s" % str(e)[:200])
    for pid, p in pages.items():
        d, e = try_get("%s/%s?fields=name,followers_count,fan_count&access_token=%s"
                       % (GRAPH, pid, q(p["token"])))
        if d:
            accounts["fb:" + pid] = {"name": d.get("name"),
                                     "followers": d.get("followers_count") or d.get("fan_count")}

    # ---------------------------------------------------------- YouTube
    yt_tok = None
    if all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        try:
            yt_tok = _http("https://oauth2.googleapis.com/token",
                           {"client_id": os.environ["YT_CLIENT_ID"],
                            "client_secret": os.environ["YT_CLIENT_SECRET"],
                            "refresh_token": os.environ["YT_REFRESH_TOKEN"],
                            "grant_type": "refresh_token"})["access_token"]
            d = _http("https://www.googleapis.com/youtube/v3/channels?part=statistics,snippet&mine=true",
                      headers={"Authorization": "Bearer " + yt_tok})
            for c in d.get("items", []):
                s = c.get("statistics", {})
                accounts["yt:" + c["snippet"]["title"]] = {
                    "followers": int(s.get("subscriberCount", 0)),
                    "views": int(s.get("viewCount", 0)), "posts": int(s.get("videoCount", 0))}
        except Exception as e:                        # noqa: BLE001
            err("yt", "token/channel: %s" % str(e)[:200]); yt_tok = None

    yt_ids = [r["media_id"] for r in ok if r["account"] == "yt"]
    yt_stats = {}
    for i in range(0, len(yt_ids), 50) if yt_tok else []:
        d, e = try_get_auth("https://www.googleapis.com/youtube/v3/videos?part=statistics&id="
                            + ",".join(yt_ids[i:i + 50]), yt_tok)
        if d:
            for v in d.get("items", []):
                s = v.get("statistics", {})
                yt_stats[v["id"]] = {"views": int(s.get("viewCount", 0)),
                                     "likes": int(s.get("likeCount", 0)),
                                     "comments": int(s.get("commentCount", 0))}
        else:
            err("yt", e)

    # ---------------------------------------------------------- per post
    for r in ok:
        acct, mid = r["account"], r["media_id"]
        rec = {"post_id": r["post_id"], "account": acct, "series": r["series"],
               "ref": r["ref"], "posted": r["run_at_pacific"], "media_id": mid}
        if acct.startswith("ig:"):
            fields = "like_count,comments_count,media_type,permalink"
            d, e = try_get("%s/%s?fields=%s&access_token=%s" % (GRAPH, mid, fields, q(TOK)))
            if not d:
                err("ig", "%s: %s" % (r["post_id"], e)); continue
            rec.update(likes=d.get("like_count", 0), comments=d.get("comments_count", 0),
                       media_type=d.get("media_type"), permalink=d.get("permalink"))
            if insights:
                metric = "views,reach,saved,shares,total_interactions"
                i, e = try_get("%s/%s/insights?metric=%s&access_token=%s" % (GRAPH, mid, metric, q(TOK)))
                for m in (i or {}).get("data", []):
                    rec[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value"))
        elif acct.startswith("fb:"):
            page = pages.get(acct.split(":", 1)[1])
            if not page:
                continue
            fields = "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0),shares"
            d, e = try_get("%s/%s?fields=%s&access_token=%s" % (GRAPH, mid, fields, q(page["token"])))
            if not d:   # reels are logged with the video id, which has no shares field
                d, e = try_get("%s/%s?fields=likes.summary(total_count).limit(0),comments.summary(total_count).limit(0)&access_token=%s"
                               % (GRAPH, mid, q(page["token"])))
            if not d:
                err("fb", "%s: %s" % (r["post_id"], e)); continue
            rec.update(likes=(d.get("reactions") or d.get("likes") or {}).get("summary", {}).get("total_count", 0),
                       comments=(d.get("comments") or {}).get("summary", {}).get("total_count", 0),
                       shares=(d.get("shares") or {}).get("count", 0))
        elif acct == "yt":
            if mid not in yt_stats:
                continue
            rec.update(yt_stats[mid])
        else:
            continue                                  # threads / linkedin: no read scope yet
        posts.append(rec)

    today = now.date().isoformat()                    # one entry per day; a re-run replaces it
    hist = [h for h in prev.get("followers_history", []) if h.get("date") != today]
    hist = (hist + [{"date": today, **{k: v.get("followers") for k, v in accounts.items()}}])[-400:]

    snap = {"collected_utc": now.isoformat(timespec="seconds"), "ig_insights": insights,
            "accounts": accounts, "posts": posts, "errors": {k: v[:10] for k, v in errors.items()},
            "error_counts": {k: len(v) for k, v in errors.items()}, "followers_history": hist}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "wb").write(f.encrypt(json.dumps(snap).encode()))
    # counts only - no numbers per post in the public Actions log
    print("posts measured: %d | accounts: %d | errors: %s | ig insights: %s"
          % (len(posts), len(accounts), snap["error_counts"] or "none", insights))


def try_get_auth(url, token):
    try:
        return _http(url, headers={"Authorization": "Bearer " + token}, tries=2, timeout=60), None
    except Exception as e:                            # noqa: BLE001
        return None, str(e)[:200]


if __name__ == "__main__":
    main()
