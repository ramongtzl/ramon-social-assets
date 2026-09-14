# -*- coding: utf-8 -*-
"""One-time LinkedIn authorisation. Run it on your own machine, log in in the
browser window it opens, and it prints the two values to paste into the GitHub
repo secrets LI_ACCESS_TOKEN and LI_PERSON_URN.

Before running, create the app once at https://www.linkedin.com/developers/apps
    - Associate it with the Ramon Houses company page (id 143590036)
    - Products tab: add "Share on LinkedIn" and "Sign In with LinkedIn using OpenID Connect"
      (both self-serve). For posting AS THE COMPANY PAGE also request
      "Community Management API" - that one is reviewed by LinkedIn and can
      take days; posting as your profile works without it.
    - Auth tab: add redirect URL  http://localhost:8765/callback
      and copy Client ID + Client Secret.

Then:
    python linkedin_auth.py
It asks for the client id and secret (never stored anywhere), opens the
browser, catches the redirect on localhost, exchanges the code, and prints
the token. Member tokens last 60 days - put a reminder in the calendar and
re-run this before it expires; the agent cannot refresh it on its own.
"""
import json, urllib.parse, urllib.request, urllib.error, webbrowser, getpass, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIRECT = "http://localhost:8765/callback"
# w_member_social  -> post as the member
# w_organization_social -> post as the company page (needs Community Management API)
# openid profile   -> lets us read the person URN via /v2/userinfo
# Company-page scopes are refused until LinkedIn approves the Community Management
# API for the app, and one refused scope fails the whole login. So the default
# asks only for the personal profile; re-run with --company once approved.
COMPANY = "--company" in sys.argv
SCOPES = "openid profile w_member_social" + (" w_organization_social r_organization_social" if COMPANY else "")

DEFAULT_CLIENT_ID = "86ytr1vfod54p2"   # Ramon Houses Social Agent - a client ID is not a secret


def from_clipboard():
    """Read the Windows clipboard, so a hidden paste can't go wrong."""
    import subprocess
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                             capture_output=True, text=True, timeout=15).stdout
        return out.strip()
    except Exception:
        return ""


print("Copy the LinkedIn Client Secret first (the copy icon on the app's Auth tab).")
client_id = input("LinkedIn Client ID [press Enter for %s]: " % DEFAULT_CLIENT_ID).strip() or DEFAULT_CLIENT_ID
client_secret = from_clipboard()
if not client_secret.startswith("WPL_"):
    print("The clipboard does not hold a LinkedIn secret (they start with WPL_).")
    client_secret = getpass.getpass("Paste the Client Secret instead (hidden): ").strip()
if not client_secret.startswith("WPL_"):
    sys.exit("That is not a LinkedIn client secret - copy it from the Auth tab and run again.")
print("Secret read from the clipboard (%d characters, not shown)." % len(client_secret))

url = ("https://www.linkedin.com/oauth/v2/authorization?" +
       urllib.parse.urlencode({"response_type": "code", "client_id": client_id,
                               "redirect_uri": REDIRECT, "scope": SCOPES,
                               "state": "ramonhouses"}))
code = {}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code["v"] = q.get("code", [""])[0]
        code["err"] = q.get("error_description", q.get("error", [""]))[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>LinkedIn authorised - you can close this tab.</h2>")

    def log_message(self, *a):
        pass


print("\nOpening the browser. If a scope is refused, remove it from SCOPES and re-run;")
print("w_organization_social only works once Community Management API is approved.\n")
webbrowser.open(url)
srv = HTTPServer(("localhost", 8765), H)
srv.handle_request()
if not code.get("v"):
    sys.exit("no code returned: %s" % code.get("err", "unknown"))

try:
    tok = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data=urllib.parse.urlencode({"grant_type": "authorization_code", "code": code["v"],
                                     "redirect_uri": REDIRECT, "client_id": client_id,
                                     "client_secret": client_secret}).encode())).read())
except urllib.error.HTTPError as e:
    detail = e.read().decode("utf-8", "replace")
    sys.exit("\nLinkedIn refused the login (HTTP %s): %s\n"
             "Usually the secret: copy the CURRENT one from the Auth tab and run again." % (e.code, detail[:300]))
access = tok["access_token"]
days = int(tok.get("expires_in", 0)) // 86400

me = json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://api.linkedin.com/v2/userinfo",
    headers={"Authorization": "Bearer " + access})).read())
person_urn = "urn:li:person:" + me["sub"]

# Save straight to GitHub - the token is never printed or pasted anywhere.
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from github_secret import set_secret
print("\nSaving to GitHub secrets:")
set_secret("LI_ACCESS_TOKEN", access)
set_secret("LI_PERSON_URN", person_urn)
if COMPANY:
    set_secret("LI_ORG_ID", "143590036")
else:
    print("  (LI_ORG_ID not set - company-page posting waits for LinkedIn approval; re-run with --company)")
print("\nPosting as: %s" % me.get("name", person_urn))
print("\nToken expires in ~%d days. Re-run this script before then." % days)
print("Scopes granted: %s" % tok.get("scope", "(not reported)"))
