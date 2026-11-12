# -*- coding: utf-8 -*-
"""Hourly laptop trigger for post-to-social (Ramon OK 2026-11-11).

Task Scheduler "\\Social Post Dispatch Hourly" runs this at :02 every hour.
It dispatches post.yml with no post_ids, so the agent posts only what is due
and state.json stops repeats. GitHub's own hourly cron stays on as a backup.

Every step is logged to auth/dispatch-hourly.log (no secrets) with timeouts,
so a hung run shows where it stopped.
"""
import datetime, json, os, subprocess, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "dispatch-hourly.log")
REPO = "ramongtzl/ramon-social-assets"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s  %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))


def token():
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, timeout=90,
                         env=dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never"),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise RuntimeError("no GitHub credential returned")


def main():
    log("start")
    try:
        t = token()
        log("credential ok")
        body = json.dumps({"ref": "main", "inputs": {"dry_run": "false"}}).encode()
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/actions/workflows/post.yml/dispatches" % REPO,
            data=body, method="POST",
            headers={"Authorization": "Bearer " + t, "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            log("dispatched post.yml (HTTP %s)" % r.status)
    except urllib.error.HTTPError as e:
        log("GitHub refused HTTP %s" % e.code)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        log("FAILED %s: %s" % (type(e).__name__, str(e)[:200]))
        sys.exit(1)


if __name__ == "__main__":
    main()
