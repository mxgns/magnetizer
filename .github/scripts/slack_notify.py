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
    pr_link = [f"<{pr['url']}|View PR>"] if pr else []
    pr_line = f"PR: #{pr['number']} — {_esc(pr['title'])}" if pr else None

    if kind == "test" and branch != PRODUCTION_BRANCH:
        lines = [
            "*🧪 MAGNETIZER · BRANCH BUILD PASSED*" if ok
            else "*🧪 MAGNETIZER · BRANCH BUILD FAILED*",
            "✅ Tests passed · Not deployed" if ok
            else f"❌ {_failed_part(status, outcomes)} · Not deployed",
            pr_line or "PR: none yet",
            f"Branch: `{_esc(branch)}` · `{short}`",
            " · ".join(pr_link + [f"<{run_url}|{'View CI' if ok else 'View failed CI'}>"]),
        ]
    else:
        if kind == "test" and ok:
            return None
        if ok:
            header = "*🧲 MAGNETIZER · PRODUCTION DEPLOYED*"
            detail = "✅ Tests passed · Blog rebuild triggered"
            links = pr_link + [f"<{DEPLOYMENTS_URL}|View deployment>"]
        else:
            header = "*🧲 MAGNETIZER · PRODUCTION FAILURE*"
            if kind == "refresh":
                detail = ("🔴 Tests passed, but the blog rebuild couldn't be "
                          "triggered · Not deployed")
            else:
                detail = f"🔴 {_failed_part(status, outcomes)} on main · Not deployed"
            links = pr_link + [f"<{run_url}|View failed run>"]
        change = re.sub(r"\s*\(#\d+\)$", "", subject)
        lines = [header, detail, f"Commit: `{short}`", f"Change: {_esc(change)}"]
        if pr_line:
            lines.append(pr_line)
        lines.append(" · ".join(links))

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


def main():
    env = os.environ
    webhook = env.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("SLACK_WEBHOOK_URL not set; skipping.")
        return
    repo, sha, token = env["GITHUB_REPOSITORY"], env["SHA"], env["GITHUB_TOKEN"]

    subject = _github(f"/repos/{repo}/commits/{sha}", token)["commit"]["message"]
    subject = subject.splitlines()[0]
    pulls = _github(f"/repos/{repo}/commits/{sha}/pulls", token)
    pr = ({"number": pulls[0]["number"], "title": pulls[0]["title"],
           "url": pulls[0]["html_url"]} if pulls else None)

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
