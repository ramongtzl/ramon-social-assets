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
import json, urllib.parse, urllib.request, webbrowser, getpass, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIRECT = "http://localhost:8765/callback"
# w_member_social  -> post as the member
# w_organization_social -> post as the company page (needs Community Management API)
# openid profile   -> lets us read the person URN via /v2/userinfo
SCOPES = "openid profile w_member_social w_organization_social r_organization_social"

client_id = input("LinkedIn Client ID: ").strip()
client_secret = getpass.getpass("LinkedIn Client Secret (hidden): ").strip()
if not client_id or not client_secret:
    sys.exit("both values are required")

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

tok = json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://www.linkedin.com/oauth/v2/accessToken",
    data=urllib.parse.urlencode({"grant_type": "authorization_code", "code": code["v"],
                                 "redirect_uri": REDIRECT, "client_id": client_id,
                                 "client_secret": client_secret}).encode())).read())
access = tok["access_token"]
days = int(tok.get("expires_in", 0)) // 86400

me = json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://api.linkedin.com/v2/userinfo",
    headers={"Authorization": "Bearer " + access})).read())
person_urn = "urn:li:person:" + me["sub"]

print("\n=== paste these into GitHub -> Settings -> Secrets -> Actions ===")
print("LI_ACCESS_TOKEN = %s" % access)
print("LI_PERSON_URN   = %s" % person_urn)
print("LI_ORG_ID       = 143590036")
print("\nToken expires in ~%d days. Re-run this script before then." % days)
print("Scopes granted: %s" % tok.get("scope", "(not reported)"))
