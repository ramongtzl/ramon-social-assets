# -*- coding: utf-8 -*-
"""Save a fresh IG_TOKEN to the GitHub secrets, from the clipboard, after
checking it is long-lived and can reach both Instagram accounts and both
Facebook Pages. The token is never printed.

How to mint one (Meta app "Ramon Social Agent", 1433468848701369):
  1. https://developers.facebook.com/tools/explorer/1433468848701369/
     User token, permissions: instagram_basic, instagram_content_publish,
     pages_show_list, pages_read_engagement, pages_manage_posts,
     business_management -> Generate Access Token (tick BOTH Pages).
  2. https://developers.facebook.com/tools/debug/accesstoken/  paste it ->
     "Extend Access Token" -> copy the long-lived token (about 60 days).
  3. Copy it to the clipboard and run:  python auth/ig_token.py

2026-09-19: the token in the secrets expired at 10:00 PDT although SETUP.md
said 2026-11-06 - a short-lived token had been saved during testing. This
script refuses anything that expires in under 30 days.
"""
import os, sys, json, subprocess, urllib.request, urllib.parse, urllib.error, datetime

G = "https://graph.facebook.com/v21.0"
WANT_PAGES = {"414239392030697", "543998318793132"}      # ramonhouses, growthwealth


def clipboard():
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                              capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""


def get(url):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=60).read())
    except urllib.error.HTTPError as e:
        sys.exit("Graph refused (HTTP %s): %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


tok = os.environ.get("IG_TOKEN_NEW") or clipboard()
if not tok or len(tok) < 60 or " " in tok or not tok.startswith("EAA"):
    sys.exit("copy the long-lived user token to the clipboard first")
print("token read from the clipboard (%d characters, not shown)" % len(tok))

# expiry: debug_token needs an app token, but /me?fields=id with the same token
# plus /debug_token?input_token=X&access_token=X works for user tokens.
dbg = get(G + "/debug_token?" + urllib.parse.urlencode({"input_token": tok, "access_token": tok})).get("data", {})
exp = dbg.get("expires_at", 0)
days = (datetime.datetime.fromtimestamp(exp) - datetime.datetime.now()).days if exp else 9999
print("type %s, expires %s (%s days), scopes: %s" % (
    dbg.get("type"), datetime.date.fromtimestamp(exp) if exp else "never",
    days if exp else "n/a", ", ".join(dbg.get("scopes", []))))
if exp and days < 30:
    sys.exit("that token expires in %d days - extend it in the Access Token Debugger first" % days)

pages = {}
url = G + "/me/accounts?fields=id,name,instagram_business_account&access_token=" + urllib.parse.quote(tok)
while url:
    r = get(url)
    for p in r.get("data", []):
        pages[p["id"]] = p
    url = r.get("paging", {}).get("next")
for pid, p in pages.items():
    print("  page %s %-22s ig %s" % (pid, p.get("name", ""), (p.get("instagram_business_account") or {}).get("id", "-")))
missing = WANT_PAGES - set(pages)
if missing:
    sys.exit("token cannot see Page(s) %s - regenerate with both Pages ticked" % ", ".join(missing))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from github_secret import set_secret
print("\nSaving to GitHub secrets:")
set_secret("IG_TOKEN", tok)
print("\nDone. Expires about %s - put the refresh reminder a week before." % (
    datetime.date.fromtimestamp(exp) if exp else "never"))
