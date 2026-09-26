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
# Norton Web Shield rewrites TLS with its own root; trust the Windows store (2026-09-04).
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
# Google hosts resolve to dead IPv6 addresses on this network - IPv4 only.
import socket as _socket
_real_getaddrinfo = _socket.getaddrinfo
def _ipv4_only_getaddrinfo(*a, **k):
    res = _real_getaddrinfo(*a, **k)
    v4 = [r for r in res if r[0] == _socket.AF_INET]
    return v4 or res
_socket.getaddrinfo = _ipv4_only_getaddrinfo

import json, urllib.parse, urllib.request, urllib.error, webbrowser, getpass, sys
from http.server import BaseHTTPRequestHandler, HTTPServer

REDIRECT = "http://localhost:8766/callback"
# upload to post; readonly so the channel check (channels.list mine=true) is allowed -
# with upload alone that check returns 403 and nothing gets saved.
SCOPE = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"

def _existing_client():
    """Reuse the Desktop OAuth client of GCP project ramon-gmail-mcp
    (~/.gmail-mcp/credentials.json). Its consent screen IS In production, so the
    refresh token never expires. The gmail-multi-mcp client is only a fallback:
    its consent screen is still in Testing and its tokens die after 7 days -
    the 2026-09-25 "Token has been expired or revoked" YouTube failure came
    from a token minted through it. Values are never printed.
    """
    import os
    home = os.environ.get("USERPROFILE", "")
    for p in (os.path.join(home, ".gmail-mcp", "credentials.json"),
              os.path.join(os.environ.get("GMAIL_MCP_HOME") or os.path.join(home, ".gmail-multi-mcp"), "client_secret.json"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "gmail-multi-mcp", "client_secret.json")):
        if os.path.exists(p):
            break
    else:
        return "", ""
    print("OAuth client: %s" % p)
    d = json.load(open(p))
    c = d.get("installed") or d.get("web") or {}
    return c.get("client_id", ""), c.get("client_secret", "")


client_id, client_secret = _existing_client()
if client_id and client_secret:
    print("Using the existing Google Cloud desktop client (see path above - it must be the In-production one).")
else:
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
webbrowser.open_new_tab(url)
print("If no Google page opened, open this link (it holds no secret):\n\n  %s\n" % url)
print("Waiting for you to approve on Google...")
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
api_disabled = False
try:
    ch = json.loads(urllib.request.urlopen(urllib.request.Request(
        "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
        headers={"Authorization": "Bearer " + tok["access_token"]})).read())
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", "replace")
    print("channel check failed (HTTP %s): %s" % (e.code, body[:600]))
    if "has not been used in project" in body or "is disabled" in body or "accessNotConfigured" in body:
        api_disabled = True          # token is fine; the API just is not switched on yet
        ch = {}
    else:
        sys.exit("cannot verify the channel - nothing saved")
names = [c["snippet"]["title"] for c in ch.get("items", [])]

# Save straight to GitHub - nothing secret is printed or pasted anywhere.
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from github_secret import set_secret
if not names and not api_disabled:
    sys.exit("no YouTube channel on that Google account - nothing saved. Re-run and pick the @Ramonhouses account.")
if api_disabled:
    print("\nYouTube Data API v3 is NOT enabled on this project - enable it at\n"
          "  https://console.cloud.google.com/apis/library/youtube.googleapis.com\n"
          "The token below is valid and is being saved so you do not have to sign in again.")
print("\nSaving to GitHub secrets:")
set_secret("YT_CLIENT_ID", client_id)
set_secret("YT_CLIENT_SECRET", client_secret)
set_secret("YT_REFRESH_TOKEN", tok["refresh_token"])
print("\nAuthorised channel(s): %s" % (", ".join(names) or "none found - wrong Google account?"))
