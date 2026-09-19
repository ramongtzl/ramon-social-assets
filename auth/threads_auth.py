# -*- coding: utf-8 -*-
"""Threads credentials for the posting agent -> GitHub secrets, without the
token ever being printed, pasted into a file or left on disk.

Threads is its own API (graph.threads.net) with its own user id and token.
IG_TOKEN and the Instagram account id do NOT work there - that was the
2026-09-18 "Unsupported post request ... 17841405720640790" error.

Set-up, once, on the Meta app "Ramon Social Agent" (app 1433468848701369):
    Use cases -> Access the Threads API   (Threads app id 1095800076313361)
      Permissions: threads_basic + threads_content_publish  "Ready for testing"
      Settings: the three callback URLs = the threads-callback.html page in
                this repo, served by GitHub Pages
    App roles -> Roles -> Add People -> Threads Tester -> ramonhouses
    threads.com/settings/website_permissions -> Invites -> Accept (as @ramonhouses)
    Done 2026-09-19.

Getting a token - two ways, both land here:

  A) Dashboard (no OAuth dance, the way used 2026-09-19):
     Use case Settings -> User Token Generator -> ramonhouses -> Generate token
     -> Copy. Then:
         python auth/threads_auth.py
     It reads the token from the clipboard, asks Threads who it belongs to,
     and writes THREADS_TOKEN + THREADS_USER_ID to the GitHub repo secrets.

  B) OAuth (if the generator ever goes away). Open, logged in as @ramonhouses:
         https://threads.net/oauth/authorize?client_id=1095800076313361
           &redirect_uri=https://ramongtzl.github.io/ramon-social-assets/threads-callback.html
           &scope=threads_basic,threads_content_publish&response_type=code
     Threads redirects to the callback page with ?code=... in the URL. Copy the
     Threads app SECRET (Settings -> Show) to the clipboard, then:
         python auth/threads_auth.py --code <the code>
     Exchanges it for a short-lived token, then a long-lived one, then saves.

Tokens last ~60 days (same as IG_TOKEN). Re-run before they expire - the
agent cannot refresh a token it only holds as a write-only secret.
"""
import os, sys, json, subprocess, urllib.request, urllib.parse, urllib.error

THREADS_APP_ID = "1095800076313361"          # public id, not a secret
REDIRECT = "https://ramongtzl.github.io/ramon-social-assets/threads-callback.html"
API = "https://graph.threads.net"


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
        sys.exit("Threads refused (HTTP %s): %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


def post(url, data):
    try:
        return json.loads(urllib.request.urlopen(
            urllib.request.Request(url, data=urllib.parse.urlencode(data).encode()), timeout=60).read())
    except urllib.error.HTTPError as e:
        sys.exit("Threads refused (HTTP %s): %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))


if "--code" in sys.argv:
    code = sys.argv[sys.argv.index("--code") + 1].split("#")[0]
    secret = os.environ.get("THREADS_APP_SECRET") or clipboard()
    if not secret or len(secret) < 20 or " " in secret:
        sys.exit("copy the Threads app secret to the clipboard first (Settings -> Show -> copy)")
    short = post(API + "/oauth/access_token",
                 {"client_id": THREADS_APP_ID, "client_secret": secret,
                  "grant_type": "authorization_code", "redirect_uri": REDIRECT, "code": code})
    longl = get(API + "/access_token?" + urllib.parse.urlencode(
        {"grant_type": "th_exchange_token", "client_secret": secret,
         "access_token": short["access_token"]}))
    token = longl["access_token"]
    print("long-lived token obtained, expires in ~%d days" % (int(longl.get("expires_in", 0)) // 86400))
else:
    token = os.environ.get("THREADS_TOKEN") or clipboard()
    if not token or len(token) < 40 or " " in token:
        sys.exit("copy the token from the User Token Generator to the clipboard first")
    print("token read from the clipboard (%d characters, not shown)" % len(token))

me = get(API + "/v1.0/me?fields=id,username&access_token=" + urllib.parse.quote(token))
if not me.get("id"):
    sys.exit("token does not resolve to a Threads user: %s" % json.dumps(me)[:200])
print("Threads user: @%s  id %s" % (me.get("username"), me["id"]))
if me.get("username") != "ramonhouses":
    sys.exit("that is not @ramonhouses - generate the token for the right account")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from github_secret import set_secret
print("\nSaving to GitHub secrets:")
set_secret("THREADS_USER_ID", me["id"])
set_secret("THREADS_TOKEN", token)
print("\nDone. Run the post-to-social workflow with dry run OFF and post_ids set to a\n"
      "row whose channels include 'threads' to make the first real post.")
