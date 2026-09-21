# -*- coding: utf-8 -*-
"""Show the latest workflow runs in the assets repo, and the failed step logs
of a run when asked (no gh CLI needed).

    python auth/runs.py            # last 8 runs
    python auth/runs.py <run_id>   # job steps + log tail of that run
"""
import sys, json, subprocess, urllib.request, urllib.error, re

REPO = "ramongtzl/ramon-social-assets"


def gh_token():
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    sys.exit("no GitHub credential in the git credential store")


TOK = gh_token()


def api(path, raw=False):
    req = urllib.request.Request("https://api.github.com" + path, headers={
        "Authorization": "Bearer " + TOK, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data.decode("utf-8", "replace") if raw else json.loads(data)


def main():
    if len(sys.argv) > 1:
        rid = sys.argv[1]
        jobs = api("/repos/%s/actions/runs/%s/jobs" % (REPO, rid))["jobs"]
        for j in jobs:
            print("job %s: %s / %s" % (j["name"], j["status"], j["conclusion"]))
            for s in j["steps"]:
                print("   %-9s %s" % (s["conclusion"] or s["status"], s["name"]))
            try:
                log = api("/repos/%s/actions/jobs/%s/logs" % (REPO, j["id"]), raw=True)
            except urllib.error.HTTPError as e:
                print("   (logs: HTTP %s)" % e.code)
                continue
            log = re.sub(r"EAA[A-Za-z0-9]{40,}", "<token>", log)
            lines = [l for l in log.splitlines() if "##[group]" not in l and "##[endgroup]" not in l]
            print("   --- log tail ---")
            for l in lines[-60:]:
                print("   " + l[29:] if len(l) > 29 else "   " + l)
        return
    runs = api("/repos/%s/actions/runs?per_page=8" % REPO)["workflow_runs"]
    for r in runs:
        print("%-12s %-16s %-11s %-9s %s  %s" % (r["id"], r["name"], r["status"], r["conclusion"], r["event"], r["created_at"]))


if __name__ == "__main__":
    main()
