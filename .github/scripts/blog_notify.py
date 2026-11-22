#!/usr/bin/env python3
"""Post the Blog's Build and publish result to Slack.

Run by mxgns/blog's publish workflow from its magnetizer checkout
(.magnetizer/.github/scripts/blog_notify.py), from the blog repo root. Lists
new/updated posts and pages by diffing the blog source between the last
published commit (named in the Pages repo's "Build <sha>" commit) and HEAD,
so a page rebuilt only for its "next" link or a dynamic count isn't listed.
Stdlib only.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slack_notify import UNAVAILABLE, _esc, _github, fetch_metadata  # noqa: E402

MAGNETIZER_REPO = "mxgns/magnetizer"
MAX_LISTED = 10

_CONTENT = re.compile(r"^content/(?P<id>.+?)(?:-(?P<kind>image|comment)-\d+)?\.\w+$")
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".avif"}
_SITE_ORDER = ["templates", "CSS", "JS", "images", "resources", "config",
               "metadata", "workflow"]


def _sort_ids(ids):
    return sorted(ids, key=lambda i: (0, int(i), "") if i.isdigit() else (1, 0, i))


def _site_label(path):
    if path.startswith("templates/"):
        return "templates"
    if path.startswith("resources/"):
        ext = Path(path).suffix.lower()
        if ext == ".css":
            return "CSS"
        if ext == ".js":
            return "JS"
        return "images" if ext in _IMAGE_EXT else "resources"
    if path == "config.yaml":
        return "config"
    if path == "metadata.yaml":
        return "metadata"
    if path.startswith(".github/"):
        return "workflow"
    return None


def classify_changes(name_status):
    """[(status, path)] from `git diff --name-status --no-renames` -> change lists."""
    new, removed, touched, comments, site = set(), set(), set(), set(), set()
    for status, path in name_status:
        m = _CONTENT.match(path)
        if not m:
            label = _site_label(path)
            if label:
                site.add(label)
            continue
        page_id, kind = m.group("id"), m.group("kind")
        if kind is None and path.endswith(".md"):
            if status == "A":
                new.add(page_id)
            elif status == "D":
                removed.add(page_id)
            else:
                touched.add(page_id)
        elif kind == "comment" and status == "A":
            comments.add(page_id)
        else:  # images, and edited/removed comments
            touched.add(page_id)
    updated = touched - new - removed

    def split(ids):
        ids = _sort_ids(ids)
        return [i for i in ids if i.isdigit()], [i for i in ids if not i.isdigit()]

    new_posts, new_pages = split(new)
    updated_posts, updated_pages = split(updated)
    removed_posts, removed_pages = split(removed)
    return {
        "new_posts": new_posts, "updated_posts": updated_posts,
        "removed_posts": removed_posts, "new_pages": new_pages,
        "updated_pages": updated_pages, "removed_pages": removed_pages,
        "new_comments": _sort_ids(comments - removed),
        "site": [s for s in _SITE_ORDER if s in site],
    }


def count_warnings(build_log):
    m = re.search(r"^⚠ (\d+) warnings?:", build_log, re.MULTILINE)
    return int(m.group(1)) if m else 0


def ingested_post(ingest_log):
    m = re.search(r"^Post (\d+) created\.", ingest_log, re.MULTILINE)
    return m.group(1) if m else None


def title_from_markdown(text):
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if m:
        t = re.search(r"^title:\s*(.+?)\s*$", m.group(1), re.MULTILINE)
        if t:
            return t.group(1).strip("'\"")
    return None


def trigger_label(event, ingested, flush=False, magnetizer_sha=None, magnetizer_pr=None):
    if event == "push":
        return f"Push · inbox post {ingested} ingested" if ingested else "Push to main"
    if magnetizer_sha:
        if magnetizer_pr:
            return f"Magnetizer update <{magnetizer_pr['url']}|#{magnetizer_pr['number']}>"
        url = f"https://github.com/{MAGNETIZER_REPO}/commit/{magnetizer_sha}"
        return f"Magnetizer update <{url}|`{magnetizer_sha[:7]}`>"
    return "Manual run (full rebuild)" if flush else "Manual run"


def _list_line(singular, plural, ids, render):
    if not ids:
        return None
    label = singular if len(ids) == 1 else plural
    shown = ", ".join(render(i) for i in ids[:MAX_LISTED])
    more = f" and {len(ids) - MAX_LISTED} more" if len(ids) > MAX_LISTED else ""
    return f"{label}: {shown}{more}"


def _change_lines(changes, titles, removed_titles, site_url):
    def link(i):
        title = titles.get(i) or (f"#{i} (draft)" if i.isdigit() else i)
        return f"<{site_url}/{i}.html|{_esc(title)}>"

    def gone(i):
        return _esc(removed_titles.get(i) or (f"#{i}" if i.isdigit() else i))

    lines = [
        _list_line("New post", "New posts", changes["new_posts"], link),
        _list_line("Updated post", "Updated posts", changes["updated_posts"], link),
        _list_line("New page", "New pages", changes["new_pages"], link),
        _list_line("Updated page", "Updated pages", changes["updated_pages"], link),
        _list_line("Removed post", "Removed posts", changes["removed_posts"], gone),
        _list_line("Removed page", "Removed pages", changes["removed_pages"], gone),
        _list_line("New comment on", "New comments on", changes["new_comments"], link),
        f"Site changes: {', '.join(changes['site'])}" if changes["site"] else None,
    ]
    return [x for x in lines if x]


def build_message(*, status, published, publish_outcome, save_cache, step_outcomes,
                  sha, site_url, run_url, trigger, changes, titles, removed_titles,
                  warnings, ingest_failed):
    live = f"<{site_url}|PUBLISHED>"
    alert = False
    if published and save_cache != "success":
        alert = True
        heading = f"*🚀 BLOG · {live}, CACHE NOT SAVED*"
        detail = (f"🟠 Site published, but <{run_url}|saving the build cache failed>"
                  " · Next run does a full rebuild")
    elif status == "success":
        if published:
            heading = f"*🚀 BLOG · {live}*"
            detail = f"✅ <{run_url}|Build and publish successful>"
        elif publish_outcome == "success":
            heading = "*🚀 BLOG · NO CHANGES*"
            detail = f"✅ <{run_url}|Build successful> · Nothing new to publish"
        else:
            heading = "*🚀 BLOG · DRY RUN*"
            detail = f"✅ <{run_url}|Build successful> · Not published (dry run)"
    else:
        alert = True
        if status == "cancelled":
            what = "Run was cancelled"
        elif publish_outcome == "failure":
            what = "Publishing to the Pages repo failed"
        elif step_outcomes.get("build") == "failure":
            what = "Build failed"
        elif step_outcomes.get("commit_ingest") == "failure":
            what = "Committing the ingested inbox post failed"
        else:
            what = "CI setup failed (checkout or install)"
        heading = "*🚀 BLOG · PUBLISH FAILED*"
        detail = f"🔴 <{run_url}|{what}> · Nothing published"

    details = [detail, f"Trigger: {trigger}"]
    if changes:
        details += _change_lines(changes, titles, removed_titles, site_url)
    if warnings:
        noun = "page" if warnings == 1 else "pages"
        s = "" if warnings == 1 else "s"
        details.append(f"⚠️ <{run_url}|Build warning{s} on {warnings} {noun}>")
    if ingest_failed:
        details.append("⚠️ Inbox ingest failed · inbox/ left untouched")
    details.append(f"Commit: `{sha[:7]}`")

    lines = [heading, ""] + [f"> {x}" for x in details]
    if alert:
        lines.insert(0, "<!here>")
    return "\n".join(lines)


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def _read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def _changes_since(prev):
    """Change lists since prev (a blog commit), or (None, {}) if unknown."""
    try:
        _git("rev-parse", "--verify", "--quiet", f"{prev}^{{commit}}")
        diff = _git("diff", "--name-status", "--no-renames", prev, "HEAD")
    except (subprocess.CalledProcessError, OSError):
        return None, {}
    pairs = [tuple(line.split("\t", 1)) for line in diff.splitlines() if "\t" in line]
    changes = classify_changes(pairs)
    removed_titles = {}
    for i in changes["removed_posts"] + changes["removed_pages"]:
        try:
            removed_titles[i] = title_from_markdown(_git("show", f"{prev}:content/{i}.md"))
        except subprocess.CalledProcessError:
            pass
    return changes, removed_titles


def main():
    env = os.environ
    webhook = env.get("SLACK_WEBHOOK_URL")
    if not webhook:
        print("SLACK_WEBHOOK_URL not set; skipping.")
        return

    try:
        sha = _git("rev-parse", "HEAD").strip()
    except (subprocess.CalledProcessError, OSError):
        sha = env.get("GITHUB_SHA", "")
    prev = env.get("PREV_SHA", "")
    changes, removed_titles = _changes_since(prev) if prev else (None, {})
    try:
        titles = {k: v.get("title") for k, v in json.loads(_read(env["POSTS_JSON"])).items()}
    except (ValueError, KeyError, AttributeError):
        titles = {}

    magnetizer_sha = env.get("MAGNETIZER_SHA") or None
    magnetizer_pr = None
    if magnetizer_sha:
        token = env.get("GITHUB_TOKEN", "")
        _, pr = fetch_metadata(MAGNETIZER_REPO, magnetizer_sha,
                               lambda path: _github(path, token))
        magnetizer_pr = None if pr is UNAVAILABLE else pr

    text = build_message(
        status=env["STATUS"],
        published=env.get("PUBLISHED") == "true",
        publish_outcome=env.get("PUBLISH_OUTCOME", ""),
        save_cache=env.get("SAVE_CACHE", ""),
        step_outcomes={"build": env.get("BUILD_OUTCOME"),
                       "commit_ingest": env.get("COMMIT_INGEST_OUTCOME")},
        sha=sha, site_url=env["SITE_URL"].rstrip("/"), run_url=env["RUN_URL"],
        trigger=trigger_label(
            env.get("EVENT", ""), ingested_post(_read(env.get("INGEST_LOG", ""))),
            flush=env.get("FLUSH") == "true",
            magnetizer_sha=magnetizer_sha, magnetizer_pr=magnetizer_pr),
        changes=changes, titles=titles, removed_titles=removed_titles,
        warnings=count_warnings(_read(env.get("BUILD_LOG", ""))),
        ingest_failed=env.get("INGEST_OUTCOME") == "failure",
    )
    req = urllib.request.Request(
        webhook, data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15).read()
    print(text)


if __name__ == "__main__":
    sys.exit(main())
