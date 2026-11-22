#!/usr/bin/env python3
"""Post magnetizer's CI results to Slack.

Run from the Test workflow (KIND=test) and the Trigger blog refresh workflow
(KIND=refresh). A passing Test run on main sends nothing: the refresh workflow
runs right after and announces the deploy. Stdlib only, so it runs on any
runner Python without installing anything.
"""
import json
import os
import re
import sys
import urllib.request

PRODUCTION_BRANCH = "main"
DEPLOYMENTS_URL = "https://github.com/mxgns/blog/actions/workflows/publish.yml"
# Stands in for a commit subject or PR whose GitHub lookup failed, so the
# alert still goes out (with that detail labelled) instead of being dropped.
UNAVAILABLE = object()
_UNAVAILABLE_TEXT = "unavailable (GitHub lookup failed)"


def _esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _failed_part(status, outcomes):
    if status == "cancelled":
        return "CI run was cancelled"
    if outcomes.get("lint") == "failure":
        return "Lint failed"
    if outcomes.get("tests") == "failure":
        return "Tests failed"
    return "CI setup failed"


def build_message(*, kind, status, branch, sha, subject, run_url, pr, outcomes):
    ok = status == "success"
    short = sha[:7]
    if pr is UNAVAILABLE:
        pr_line = f"PR: {_UNAVAILABLE_TEXT}"
    elif pr:
        pr_line = f"PR: <{pr['url']}|#{pr['number']}> — {_esc(pr['title'])}"
    else:
        pr_line = None
    failed = f"<{run_url}|{_failed_part(status, outcomes)}>"

    if kind == "test" and branch != PRODUCTION_BRANCH:
        lines = [
            "*🧪 MAGNETIZER · BRANCH BUILD PASSED*" if ok
            else "*🧪 MAGNETIZER · BRANCH BUILD FAILED*",
            f"✅ <{run_url}|Tests passed> · Not deployed" if ok
            else f"❌ {failed} · Not deployed",
            pr_line or "PR: none yet",
            f"Branch: `{_esc(branch)}` · `{short}`",
        ]
    else:
        if kind == "test" and ok:
            return None
        if ok:
            header = "*🧲 MAGNETIZER · PRODUCTION DEPLOYED*"
            detail = f"✅ Tests passed · <{DEPLOYMENTS_URL}|Blog rebuild triggered>"
        else:
            header = "*🧲 MAGNETIZER · PRODUCTION FAILURE*"
            if kind == "refresh":
                detail = (f"🔴 Tests passed, but the <{run_url}|blog rebuild "
                          "couldn't be triggered> · Not deployed")
            else:
                detail = f"🔴 {failed} on main · Not deployed"
        if subject is UNAVAILABLE:
            change = _UNAVAILABLE_TEXT
        else:
            change = _esc(re.sub(r"\s*\(#\d+\)$", "", subject))
        lines = [header, detail, f"Commit: `{short}`", f"Change: {change}"]
        if pr_line:
            lines.append(pr_line)

    if not ok:
        lines.insert(0, "<!here>")
    return "\n".join(lines)


def _github(path, token):
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)


def fetch_metadata(repo, sha, get):
    """Commit subject and PR for sha; each is UNAVAILABLE if its lookup fails."""
    try:
        subject = get(f"/repos/{repo}/commits/{sha}")["commit"]["message"].splitlines()[0]
    except Exception as e:
        print(f"Commit lookup failed: {e}", file=sys.stderr)
        subject = UNAVAILABLE
    try:
        pulls = get(f"/repos/{repo}/commits/{sha}/pulls")
        pr = ({"number": pulls[0]["number"], "title": pulls[0]["title"],
               "url": pulls[0]["html_url"]} if pulls else None)
    except Exception as e:
        print(f"PR lookup failed: {e}", file=sys.stderr)
        pr = UNAVAILABLE
    return subject, pr


def main():
    env = os.environ
    webhook = env.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("SLACK_WEBHOOK_URL not set; skipping.")
        return
    repo, sha, token = env["GITHUB_REPOSITORY"], env["SHA"], env["GITHUB_TOKEN"]

    subject, pr = fetch_metadata(repo, sha, lambda path: _github(path, token))

    text = build_message(
        kind=env["KIND"], status=env["STATUS"], branch=env["BRANCH"], sha=sha,
        subject=subject, run_url=env["RUN_URL"], pr=pr,
        outcomes={"lint": env.get("LINT_OUTCOME"), "tests": env.get("TESTS_OUTCOME")},
    )
    if text is None:
        print("Passing main build; the blog refresh workflow announces the deploy.")
        return
    req = urllib.request.Request(
        webhook, data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15).read()
    print(text)


if __name__ == "__main__":
    sys.exit(main())
