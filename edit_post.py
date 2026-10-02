# -*- coding: utf-8 -*-
"""Correct text in posts that are already published on Facebook or LinkedIn.

Run by .github/workflows/edit-post.yml (the tokens only exist as repo secrets).
Instagram has no caption-edit endpoint and Threads only allows a short edit
window, so those two are not handled here - fix them in the app.

Env:
    TARGETS   comma-separated: Facebook post ids (<page_id>_<post_id>) and/or
              LinkedIn share URNs (urn:li:share:...) - copy them from post-log.csv
    FIND      exact text to replace (e.g. "1,350")
    REPLACE   replacement text   (e.g. "1,662")
    DRY_RUN   "1" = show what would change, edit nothing

A target whose current text does not contain FIND is reported and skipped, so
re-running after a partial success never double-edits anything.
"""
import os, sys, json, urllib.parse
import channels as ch

targets = [t.strip() for t in os.environ.get("TARGETS", "").split(",") if t.strip()]
find, repl = os.environ.get("FIND", ""), os.environ.get("REPLACE", "")
dry = bool(os.environ.get("DRY_RUN"))
if not targets or not find:
    sys.exit("TARGETS and FIND are required")
print("%s: %r -> %r on %d target(s)" % ("DRY RUN" if dry else "EDIT", find, repl, len(targets)))


def show(text):
    for line in text.splitlines():
        if repl in line or find in line:
            print("       | " + line)


def fb_edit(post_id):
    page_id = post_id.split("_")[0]
    pages = ch.fb_pages(os.environ["IG_TOKEN"])
    if page_id not in pages:
        raise RuntimeError("IG_TOKEN does not manage page %s" % page_id)
    tok = pages[page_id]["token"]
    cur = ch._http("%s/%s?fields=message&access_token=%s"
                   % (ch.GRAPH, post_id, urllib.parse.quote(tok))).get("message", "")
    n = cur.count(find)
    if not n:
        print("   skip  fb %s: text not found (already fixed?)" % post_id)
        return
    new = cur.replace(find, repl)
    if not dry:
        r = ch._http("%s/%s" % (ch.GRAPH, post_id), {"message": new, "access_token": tok})
        if not r.get("success", True):
            raise RuntimeError("facebook refused the edit: %s" % r)
    print("   %s fb %s (%d occurrence%s)" % ("would" if dry else "done ", post_id, n, "" if n == 1 else "s"))
    show(new)


def li_posted_text(urn):
    """The app's token cannot READ posts (w_member_social only), so rebuild the
    text that was published: post-log.csv maps the URN to its post_id, and the
    agent sent caption_li, falling back to caption (channels.fan_out._cap)."""
    import csv, io
    pid = next((r["post_id"] for r in csv.DictReader(io.open("post-log.csv", encoding="utf-8-sig"))
                if r.get("media_id") == urn), None)
    if not pid:
        raise RuntimeError("urn not found in post-log.csv")
    row = next((r for r in csv.DictReader(io.open("schedule.csv", encoding="utf-8-sig"))
                if r["post_id"] == pid), None)
    if not row:
        raise RuntimeError("post_id %s not in schedule.csv" % pid)
    return ((row.get("caption_li") or "").strip() or row["caption"])


def li_edit(urn):
    tok = os.environ["LI_ACCESS_TOKEN"]
    url = "%s/rest/posts/%s" % (ch.LI_API, urllib.parse.quote(urn, safe=""))
    cur = li_posted_text(urn)
    n = cur.count(find)
    if not n:
        print("   skip  li %s: text not found (already fixed?)" % urn)
        return
    new = cur.replace(find, repl)
    if not dry:
        body = json.dumps({"patch": {"$set": {"commentary": new}}})
        for step in range(12):
            h = ch.li_headers(tok)
            h["X-RestLi-Method"] = "PARTIAL_UPDATE"
            try:
                ch._http(url, body, h, method="POST", raw=True)
                break
            except RuntimeError as e:
                if "NONEXISTENT_VERSION" not in str(e):
                    raise
                ch.LI_VERSION = ch._months_back(2 + step + 1)
    print("   %s li %s (%d occurrence%s)" % ("would" if dry else "done ", urn, n, "" if n == 1 else "s"))
    show(new)


failed = 0
for t in targets:
    try:
        (li_edit if t.startswith("urn:li:") else fb_edit)(t)
    except Exception as e:                                   # noqa: BLE001
        failed += 1
        print("   FAIL  %s: %s" % (t, e))
sys.exit(1 if failed else 0)
