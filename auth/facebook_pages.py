# -*- coding: utf-8 -*-
"""List the Facebook Pages the IG_TOKEN can post to, with their ids - the
values that go into the FB_PAGE_IDS secret.

    set IG_TOKEN=<the long-lived user token>      (PowerShell: $env:IG_TOKEN="...")
    python facebook_pages.py

Both Ramon Houses Pages should appear:
    https://www.facebook.com/profile.php?id=61551446820788
    https://www.facebook.com/ramongtzl.houses/
If one is missing, the token was minted without that Page selected - re-run
the Meta login (SETUP.md step 4) and tick both Pages, then re-generate the
long-lived token. The Meta app also needs pages_manage_posts and
pages_read_engagement for the Page posts to go through.
"""
import os, sys, json, urllib.request, urllib.parse

tok = os.environ.get("IG_TOKEN", "")
if not tok:
    sys.exit("set IG_TOKEN in the environment first (never paste it into a file)")

url = ("https://graph.facebook.com/v21.0/me/accounts?fields=id,name,tasks"
       "&access_token=" + urllib.parse.quote(tok))
pages = []
while url:
    r = json.loads(urllib.request.urlopen(url, timeout=60).read())
    pages += r.get("data", [])
    url = r.get("paging", {}).get("next")

if not pages:
    sys.exit("no Pages returned - the token has no Page access")
print("Pages this token manages:\n")
for p in pages:
    can = "CREATE_CONTENT" in (p.get("tasks") or [])
    print("  %-20s %s%s" % (p["id"], p.get("name", ""),
                            "" if can else "   (no CREATE_CONTENT permission!)"))
print("\nFB_PAGE_IDS = " + ",".join(p["id"] for p in pages
                                  if "CREATE_CONTENT" in (p.get("tasks") or [])))
