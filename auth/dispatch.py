# -*- coding: utf-8 -*-
"""Trigger a workflow in the assets repo through the GitHub REST API, using
the git credential already on this machine (no gh CLI needed).

    python auth/dispatch.py verify-token.yml
    python auth/dispatch.py post.yml dry_run=false
    python auth/dispatch.py post.yml dry_run=false post_ids=r2-day-022
"""
import sys, json, subprocess, urllib.request, urllib.error

REPO = "ramongtzl/ramon-social-assets"


def gh_token():
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    sys.exit("no GitHub credential in the git credential store")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    wf = sys.argv[1]
    inputs = {}
    for kv in sys.argv[2:]:
        k, v = kv.split("=", 1)
        inputs[k] = v
    body = json.dumps({"ref": "main", "inputs": inputs}).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/actions/workflows/%s/dispatches" % (REPO, wf),
        data=body, method="POST",
        headers={"Authorization": "Bearer " + gh_token(), "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("dispatched %s inputs=%s (HTTP %s)" % (wf, inputs, r.status))
    except urllib.error.HTTPError as e:
        sys.exit("GitHub refused (HTTP %s): %s" % (e.code, e.read().decode("utf-8", "replace")[:400]))


if __name__ == "__main__":
    main()
