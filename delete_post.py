# -*- coding: utf-8 -*-
"""Delete posts that are already published (wrong image, wrong listing, ...).

Run by .github/workflows/delete-post.yml (the tokens only exist as repo secrets).
Manual only - never on a schedule.

Env:
    TARGETS   comma-separated, each prefixed with its channel, ids from post-log.csv:
                ig:<media id>   fb:<page_id>_<post_id>   li:urn:li:share:...   threads:<media id>
    DRY_RUN   "1" = list what would be deleted, delete nothing

Instagram media deletion needs a recent Graph version; if Meta refuses it the
error is printed and the post has to be deleted in the app.
"""
import os, sys, urllib.parse
import channels as ch

targets = [t.strip() for t in os.environ.get("TARGETS", "").split(",") if t.strip()]
dry = bool(os.environ.get("DRY_RUN"))
if not targets:
    sys.exit("TARGETS is required")
print("%s on %d target(s)" % ("DRY RUN" if dry else "DELETE", len(targets)))
IG_GRAPH = "https://graph.facebook.com/v23.0"


def ig_delete(media_id):
    ch._http("%s/%s?access_token=%s" % (IG_GRAPH, media_id, urllib.parse.quote(os.environ["IG_TOKEN"])),
             method="DELETE")


def fb_delete(post_id):
    page_id = post_id.split("_")[0]
    pages = ch.fb_pages(os.environ["IG_TOKEN"])
    if page_id not in pages:
        raise RuntimeError("IG_TOKEN does not manage page %s" % page_id)
    ch._http("%s/%s?access_token=%s" % (ch.GRAPH, post_id, urllib.parse.quote(pages[page_id]["token"])),
             method="DELETE")


def li_delete(urn):
    ch._http("%s/rest/posts/%s" % (ch.LI_API, urllib.parse.quote(urn, safe="")),
             headers=ch.li_headers(os.environ["LI_ACCESS_TOKEN"], json_body=False), method="DELETE", raw=True)


def threads_delete(media_id):
    ch._http("%s/%s?access_token=%s" % (ch.THREADS, media_id, urllib.parse.quote(os.environ["THREADS_TOKEN"])),
             method="DELETE")


LOG = []


def log(line):
    print(line)
    LOG.append(line)


DO = {"ig": ig_delete, "fb": fb_delete, "li": li_delete, "threads": threads_delete}
failed = 0
for t in targets:
    kind, _, ident = t.partition(":")
    if kind not in DO or not ident:
        log("   skip  %s: unknown channel prefix" % t)
        failed += 1
        continue
    if dry:
        log("   would delete %s %s" % (kind, ident))
        continue
    try:
        DO[kind](ident)
        log("   done  %s %s" % (kind, ident))
    except Exception as e:                               # noqa: BLE001
        failed += 1
        log("   FAIL  %s %s: %s" % (kind, ident, e))

import datetime
with open("delete-log.txt", "a", encoding="utf-8") as f:
    f.write("%s %s\n" % (datetime.datetime.utcnow().isoformat(), "DRY RUN" if dry else "DELETE"))
    f.writelines(l + "\n" for l in LOG)
sys.exit(1 if failed else 0)
