# -*- coding: utf-8 -*-
"""Extra publishing channels for the posting agent: Facebook Pages, LinkedIn
(personal profile + company page) and YouTube (Shorts from the reels).

Instagram stays in post_agent.py. This module is imported by it and adds the
other channels so one schedule row can fan out to several targets.

Targets are configured entirely through environment variables (GitHub repo
secrets) - never hardcode an id or a token here.

    Facebook  FB_PAGE_IDS       comma-separated Page ids, e.g.
                                "61551446820788,1234567890"
                                Page access tokens are derived at run time from
                                IG_TOKEN via /me/accounts, so the Meta app needs
                                pages_manage_posts + pages_read_engagement.
    LinkedIn  LI_ACCESS_TOKEN   member token from auth/linkedin_auth.py
              LI_PERSON_URN     "urn:li:person:XXXX"  (printed by the auth script)
              LI_ORG_ID         "143590036"           (company page id)
    YouTube   YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN
                                from auth/youtube_auth.py

A target that has no configuration is skipped with a clear log line, never an
exception, so one missing secret can never stop the other channels.
"""
import os, io, json, time, urllib.request, urllib.parse, urllib.error

GRAPH = "https://graph.facebook.com/v21.0"
LI_API = "https://api.linkedin.com"
LI_VERSION = "202409"
YT_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"


# --------------------------------------------------------------- http
def _http(url, data=None, headers=None, method=None, raw=False, tries=3, timeout=120):
    """JSON in / JSON out, with retry on 5xx and rate limits.

    data: dict -> form-encoded, bytes -> sent as-is, str -> utf-8 bytes.
    raw=True returns (status, headers, body-bytes) instead of parsed JSON.
    """
    for n in range(tries):
        try:
            if isinstance(data, dict):
                body = urllib.parse.urlencode(data).encode()
            elif isinstance(data, str):
                body = data.encode("utf-8")
            else:
                body = data
            req = urllib.request.Request(url, data=body, headers=headers or {},
                                         method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                content = r.read()
                if raw:
                    return r.status, dict(r.headers), content
                return json.loads(content.decode() or "{}")
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:400]
            if e.code < 500 and e.code != 429 and "rate" not in detail.lower():
                raise RuntimeError("HTTP %s: %s" % (e.code, detail))
            if n == tries - 1:
                raise RuntimeError("HTTP %s after %d tries: %s" % (e.code, tries, detail))
        except Exception:                                # noqa: BLE001
            if n == tries - 1:
                raise
        time.sleep(5 * (n + 1))


def _fetch(url):
    """Download a hosted asset (the agent needs bytes for LinkedIn/YouTube)."""
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read(), r.headers.get("Content-Type", "application/octet-stream")


# =============================================================== FACEBOOK
_page_tokens = None


def fb_pages(user_token):
    """{page_id: {"name":..., "token":...}} for every Page the user manages."""
    global _page_tokens
    if _page_tokens is None:
        _page_tokens = {}
        url = "%s/me/accounts?fields=id,name,access_token&access_token=%s" % (
            GRAPH, urllib.parse.quote(user_token))
        while url:
            r = _http(url)
            for p in r.get("data", []):
                _page_tokens[p["id"]] = {"name": p.get("name", ""),
                                         "token": p.get("access_token", "")}
            url = r.get("paging", {}).get("next")
    return _page_tokens


def fb_targets(user_token):
    ids = [x.strip() for x in os.environ.get("FB_PAGE_IDS", "").split(",") if x.strip()]
    if not ids:
        return []
    pages = fb_pages(user_token)
    out = []
    for pid in ids:
        if pid in pages and pages[pid]["token"]:
            out.append((pid, pages[pid]))
        else:
            print("     fb: page %s not in /me/accounts - token lacks access, skipped" % pid)
    return out


def fb_publish(page_id, page_token, kind, urls, caption):
    """Single photo, multi-photo post, or video, on one Page. Returns post id."""
    if kind == "reel":
        r = _http("%s/%s/videos" % (GRAPH, page_id),
                  {"file_url": urls[0], "description": caption,
                   "access_token": page_token})
        return r.get("id")
    if len(urls) == 1:
        r = _http("%s/%s/photos" % (GRAPH, page_id),
                  {"url": urls[0], "message": caption, "access_token": page_token})
        return r.get("post_id") or r.get("id")
    # multi-photo: upload unpublished, then one feed post that attaches them all
    media = []
    for u in urls:
        r = _http("%s/%s/photos" % (GRAPH, page_id),
                  {"url": u, "published": "false", "access_token": page_token})
        media.append(r["id"])
    form = {"message": caption, "access_token": page_token}
    for i, mid in enumerate(media):
        form["attached_media[%d]" % i] = json.dumps({"media_fbid": mid})
    r = _http("%s/%s/feed" % (GRAPH, page_id), form)
    return r.get("id")


# =============================================================== LINKEDIN
def li_headers(token, json_body=True):
    h = {"Authorization": "Bearer " + token,
         "LinkedIn-Version": LI_VERSION,
         "X-Restli-Protocol-Version": "2.0.0"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def li_targets():
    token = os.environ.get("LI_ACCESS_TOKEN", "")
    if not token:
        return []
    out = []
    person = os.environ.get("LI_PERSON_URN", "")
    org = os.environ.get("LI_ORG_ID", "")
    if person:
        out.append(("person", person))
    if org:
        out.append(("org:" + org, "urn:li:organization:" + org))
    return out


def li_upload_image(token, owner_urn, img_bytes):
    init = _http("%s/rest/images?action=initializeUpload" % LI_API,
                 json.dumps({"initializeUploadRequest": {"owner": owner_urn}}),
                 li_headers(token))
    v = init["value"]
    _http(v["uploadUrl"], img_bytes,
          {"Authorization": "Bearer " + token,
           "Content-Type": "application/octet-stream"},
          method="PUT", raw=True)
    return v["image"]


def li_publish(owner_urn, kind, urls, caption, alt=""):
    """Image or multi-image post as the person or the organisation.
    Video is skipped here: LinkedIn's video upload is a separate multi-part
    flow and the reels go to YouTube instead."""
    token = os.environ["LI_ACCESS_TOKEN"]
    if kind == "reel":
        raise RuntimeError("linkedin: video not supported by this agent, skip")
    images = []
    for u in urls[:20]:
        data, _ = _fetch(u)
        images.append(li_upload_image(token, owner_urn, data))
    if len(images) == 1:
        content = {"media": {"id": images[0], "altText": alt[:300]}}
    else:
        content = {"multiImage": {"images": [{"id": i, "altText": alt[:300]}
                                             for i in images]}}
    body = {"author": owner_urn,
            "commentary": caption,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED",
                             "targetEntities": [], "thirdPartyDistributionChannels": []},
            "content": content,
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False}
    status, hdrs, _ = _http("%s/rest/posts" % LI_API, json.dumps(body),
                            li_headers(token), raw=True)
    return hdrs.get("x-restli-id") or hdrs.get("X-RestLi-Id") or "ok"


# =============================================================== YOUTUBE
_yt_token = None


def yt_configured():
    return all(os.environ.get(k) for k in
               ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"))


def yt_access_token():
    global _yt_token
    if _yt_token is None:
        r = _http("https://oauth2.googleapis.com/token",
                  {"client_id": os.environ["YT_CLIENT_ID"],
                   "client_secret": os.environ["YT_CLIENT_SECRET"],
                   "refresh_token": os.environ["YT_REFRESH_TOKEN"],
                   "grant_type": "refresh_token"})
        _yt_token = r["access_token"]
    return _yt_token


def yt_publish(video_url, title, description, tags=None):
    """Resumable upload of one MP4. A 9:16 clip under 60s is treated as a
    Short by YouTube automatically. Returns the video id."""
    token = yt_access_token()
    data, _ = _fetch(video_url)
    meta = {"snippet": {"title": title[:100],
                        "description": description[:5000],
                        "tags": (tags or [])[:30],
                        "categoryId": "22"},            # People & Blogs
            "status": {"privacyStatus": "public",
                       "selfDeclaredMadeForKids": False}}
    status, hdrs, _ = _http(
        "%s?uploadType=resumable&part=snippet,status" % YT_UPLOAD,
        json.dumps(meta),
        {"Authorization": "Bearer " + token,
         "Content-Type": "application/json; charset=UTF-8",
         "X-Upload-Content-Type": "video/mp4",
         "X-Upload-Content-Length": str(len(data))},
        raw=True)
    loc = hdrs.get("Location") or hdrs.get("location")
    if not loc:
        raise RuntimeError("youtube: no resumable upload Location returned")
    r = _http(loc, data, {"Authorization": "Bearer " + token,
                          "Content-Type": "video/mp4"},
              method="PUT", timeout=600)
    return r.get("id")


def yt_title_from_caption(caption, ref=""):
    """First non-empty caption line, trimmed to YouTube's 100 chars."""
    for line in caption.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            return (line[:92] + " #Shorts") if len(line) > 92 else line + " #Shorts"
    return ("Ramon Houses %s" % ref).strip() + " #Shorts"


# =============================================================== DISPATCH
def fan_out(channels, kind, urls, caption, ref, ig_token, already, dry=False,
            captions=None):
    """Publish one schedule row to every non-Instagram channel it names.

    channels: iterable like {"fb", "li", "yt"} (ig is handled by the caller)
    already:  dict of target-key -> result for this post, so a re-run only
              retries the targets that failed
    returns:  {target_key: {"id": ..}} for the targets published this call,
              plus a list of (target_key, error) failures
    """
    done, fails = {}, []
    # Facebook and LinkedIn take their own wording where the schedule supplies
    # it; anything missing falls back to the Instagram caption.
    caps = captions or {}

    def _cap(ch):
        return (caps.get(ch) or "").strip() or caption

    def _run(key, fn):
        if key in already:
            print("     skip %s (done %s)" % (key, already[key].get("at", "")))
            return
        if dry:
            print("     DRY %s" % key)
            return
        try:
            rid = fn()
            done[key] = {"id": rid}
            print("     %s ok -> %s" % (key, rid))
        except Exception as e:                            # noqa: BLE001
            fails.append((key, str(e)[:300]))
            print("     %s FAILED: %s" % (key, str(e)[:300]))

    if "fb" in channels:
        ids = [x.strip() for x in os.environ.get("FB_PAGE_IDS", "").split(",") if x.strip()]
        if not ids:
            print("     fb: FB_PAGE_IDS not set - skipped")
        elif dry:
            for pid in ids:
                print("     DRY fb:%s" % pid)
        else:
            # resolving Page tokens is itself a network call - a bad IG_TOKEN
            # must fail this channel only, never the whole run
            try:
                pages = fb_targets(ig_token) if ig_token else []
            except Exception as e:                        # noqa: BLE001
                pages = []
                for pid in ids:
                    fails.append(("fb:" + pid, "page lookup failed: " + str(e)[:200]))
                print("     fb: page lookup FAILED: %s" % str(e)[:200])
            for pid, page in pages:
                _run("fb:" + pid,
                     lambda pid=pid, page=page: fb_publish(pid, page["token"], kind, urls, caption))

    if "li" in channels:
        targets = li_targets()
        if not targets:
            print("     li: LI_ACCESS_TOKEN / LI_PERSON_URN / LI_ORG_ID not set - skipped")
        for key, urn in targets:
            if kind == "reel":
                print("     li:%s video not supported here - skipped" % key)
                continue
            _run("li:" + key, lambda urn=urn: li_publish(urn, kind, urls, caption, alt=ref))

    if "yt" in channels:
        if not yt_configured():
            print("     yt: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN not set - skipped")
        elif kind != "reel":
            print("     yt: only video rows go to YouTube - skipped")
        else:
            tags = [t.lstrip("#") for t in caption.split() if t.startswith("#")]
            _run("yt", lambda: yt_publish(urls[0], yt_title_from_caption(caption, ref),
                                          caption, tags))
    return done, fails
