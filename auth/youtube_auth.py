# -*- coding: utf-8 -*-
"""One-time YouTube authorisation for @Ramonhouses. Prints the refresh token
to paste into the GitHub secrets YT_CLIENT_ID / YT_CLIENT_SECRET /
YT_REFRESH_TOKEN. Same pattern as the gmail-multi setup.

Before running, in Google Cloud Console (https://console.cloud.google.com):
    1. Pick or create a project, enable "YouTube Data API v3".
    2. OAuth consent screen: External. **Set publishing status to
       "In production"** - in "Testing" the refresh token dies after 7 days and
       posting silently stops. Add the youtube.upload scope.
    3. Credentials -> Create OAuth client ID -> Desktop app. Copy id + secret.

Then:
    python youtube_auth.py
Log in as the Google account that owns the @Ramonhouses channel.

Known limit: until Google verifies the app (a review you can request from the
consent screen), videos uploaded through the API are locked to PRIVATE by
YouTube. Everything else works; they just need to be flipped to public in
YouTube Studio, or the app verified once. Quota: 10,000 units/day, an upload
costs 1,600 - six uploads a day at most, which is far more than the schedule.
"""
import json, urllib.parse, urllib.request, webbrowser, getpass, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIRECT = "http://localhost:8766/callback"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"

client_id = input("YouTube OAuth Client ID: ").strip()
client_secret = getpass.getpass("Client Secret (hidden): ").strip()
if not client_id or not client_secret:
    sys.exit("both values are required")

url = ("https://accounts.google.com/o/oauth2/v2/auth?" +
       urllib.parse.urlencode({"response_type": "code", "client_id": client_id,
                               "redirect_uri": REDIRECT, "scope": SCOPE,
                               "access_type": "offline", "prompt": "consent"}))
code = {}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code["v"] = q.get("code", [""])[0]
        code["err"] = q.get("error", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>YouTube authorised - you can close this tab.</h2>")

    def log_message(self, *a):
        pass


print("\nOpening the browser - sign in as the owner of @Ramonhouses.\n")
webbrowser.open(url)
srv = HTTPServer(("localhost", 8766), H)
srv.handle_request()
if not code.get("v"):
    sys.exit("no code returned: %s" % code.get("err", "unknown"))

tok = json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://oauth2.googleapis.com/token",
    data=urllib.parse.urlencode({"grant_type": "authorization_code", "code": code["v"],
                                 "redirect_uri": REDIRECT, "client_id": client_id,
                                 "client_secret": client_secret}).encode())).read())
if "refresh_token" not in tok:
    sys.exit("no refresh_token returned - revoke the app at myaccount.google.com/permissions and re-run")

# sanity check: which channel did we get?
ch = json.loads(urllib.request.urlopen(urllib.request.Request(
    "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
    headers={"Authorization": "Bearer " + tok["access_token"]})).read())
names = [c["snippet"]["title"] for c in ch.get("items", [])]

print("\n=== paste these into GitHub -> Settings -> Secrets -> Actions ===")
print("YT_CLIENT_ID     = %s" % client_id)
print("YT_CLIENT_SECRET = (the secret you entered)")
print("YT_REFRESH_TOKEN = %s" % tok["refresh_token"])
print("\nAuthorised channel(s): %s" % (", ".join(names) or "none found - wrong Google account?"))
