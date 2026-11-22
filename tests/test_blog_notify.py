import importlib.util
import sys
from pathlib import Path

_DIR = Path(__file__).parent.parent / ".github" / "scripts"
sys.path.insert(0, str(_DIR))
_spec = importlib.util.spec_from_file_location("blog_notify", _DIR / "blog_notify.py")
blog_notify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(blog_notify)

classify_changes = blog_notify.classify_changes
count_warnings = blog_notify.count_warnings
build_message = blog_notify.build_message

SITE = "https://mxgns.uk"
RUN = "https://github.com/mxgns/blog/actions/runs/1"
SHA = "3193f18" + "0" * 33


# classify_changes

def test_new_post_md():
    c = classify_changes([("A", "content/149.md"), ("A", "content/149-image-01.jpeg")])
    assert c["new_posts"] == ["149"]
    assert c["updated_posts"] == []


def test_modified_post_md_is_updated():
    assert classify_changes([("M", "content/148.md")])["updated_posts"] == ["148"]


def test_image_change_counts_as_updated_post():
    c = classify_changes([("A", "content/148-image-03.jpeg"),
                          ("D", "content/147-image-01.jpg")])
    assert c["updated_posts"] == ["147", "148"]


def test_removed_post():
    c = classify_changes([("D", "content/12.md"), ("D", "content/12-image-01.jpg")])
    assert c["removed_posts"] == ["12"]
    assert c["updated_posts"] == []


def test_slug_files_are_pages_not_posts():
    c = classify_changes([("M", "content/about.md"), ("A", "content/now.md"),
                          ("D", "content/cookies.md"),
                          ("A", "content/jnco-rhino-dark-stone-image-09.jpeg")])
    assert c["updated_pages"] == ["about", "jnco-rhino-dark-stone"]
    assert c["new_pages"] == ["now"]
    assert c["removed_pages"] == ["cookies"]
    assert c["new_posts"] == c["updated_posts"] == []


def test_new_comment_is_not_a_post_update():
    c = classify_changes([("A", "content/140-comment-02.md"),
                          ("A", "content/syntax-comment-03.md")])
    assert c["new_comments"] == ["140", "syntax"]
    assert c["updated_posts"] == c["updated_pages"] == []


def test_edited_or_removed_comment_updates_its_post():
    c = classify_changes([("M", "content/140-comment-01.md"),
                          ("D", "content/141-comment-01.md")])
    assert c["updated_posts"] == ["140", "141"]
    assert c["new_comments"] == []


def test_posts_sorted_numerically():
    c = classify_changes([("A", "content/100.md"), ("A", "content/99.md")])
    assert c["new_posts"] == ["99", "100"]


def test_site_changes_are_labelled():
    c = classify_changes([
        ("M", "templates/index.html"), ("M", "resources/style.css"),
        ("A", "resources/blog.js"), ("A", "resources/icons/x.svg"),
        ("M", "resources/robots-extra.txt"), ("M", "config.yaml"),
        ("M", "metadata.yaml"), ("M", ".github/workflows/publish.yml"),
    ])
    assert c["site"] == ["templates", "CSS", "JS", "images", "resources",
                         "config", "metadata", "workflow"]


def test_inbox_and_other_files_ignored():
    c = classify_changes([("D", "inbox/photo.jpg"), ("M", "README.md"),
                          ("A", "inbox/.gitkeep")])
    assert all(v == [] for v in c.values())


# count_warnings

def test_count_warnings_from_verbose_summary():
    log = "  148   148.md\n⚠ 2 warnings: 140.md, about.md\n\nDONE with warnings\n"
    assert count_warnings(log) == 2
    assert count_warnings("⚠ 1 warning: 140.md\n") == 1


def test_count_warnings_none():
    assert count_warnings("1 created · 0 updated · 0 deleted\nDONE.\n") == 0
    assert count_warnings("") == 0


# build_message

TITLES = {"149": "My new post", "150": "My other new post",
          "148": "Got some new JNCOs", "about": "About", "140": "Old <post> & co"}


def msg(**kw):
    args = dict(status="success", published=True, publish_outcome="success",
                save_cache="success", step_outcomes={}, sha=SHA, site_url=SITE,
                run_url=RUN, trigger="Push to main", changes=None, titles=TITLES,
                removed_titles={}, warnings=0, ingest_failed=False)
    args.update(kw)
    return build_message(**args)


def changes(**kw):
    c = {k: [] for k in ("new_posts", "updated_posts", "removed_posts", "new_pages",
                         "updated_pages", "removed_pages", "new_comments", "site")}
    c.update(kw)
    return c


def test_published_with_new_and_updated_posts():
    out = msg(changes=changes(new_posts=["149", "150"], updated_posts=["148"]))
    assert out == "\n".join([
        f"*🚀 BLOG · <{SITE}|PUBLISHED>*",
        "",
        f"> ✅ <{RUN}|Build and publish successful>",
        "> Trigger: Push to main",
        f"> New posts: <{SITE}/149.html|My new post>, <{SITE}/150.html|My other new post>",
        f"> Updated post: <{SITE}/148.html|Got some new JNCOs>",
        "> Commit: `3193f18`",
    ])


def test_pages_comments_removals_and_site_changes():
    out = msg(changes=changes(
        new_pages=["now"], updated_pages=["about"], removed_posts=["12"],
        removed_pages=["cookies"], new_comments=["140"], site=["templates", "CSS"]),
        titles=dict(TITLES, now="Now"), removed_titles={"12": "An old post"})
    lines = out.splitlines()
    assert f"> New page: <{SITE}/now.html|Now>" in lines
    assert f"> Updated page: <{SITE}/about.html|About>" in lines
    assert "> Removed post: An old post" in lines
    assert "> Removed page: cookies" in lines
    assert f"> New comment on: <{SITE}/140.html|Old &lt;post&gt; &amp; co>" in lines
    assert "> Site changes: templates, CSS" in lines


def test_draft_without_title_is_labelled():
    out = msg(changes=changes(new_posts=["151"]))
    assert f"> New post: <{SITE}/151.html|#151 (draft)>" in out.splitlines()


def test_long_lists_are_capped():
    ids = [str(i) for i in range(1, 15)]
    out = msg(changes=changes(updated_posts=ids), titles={i: f"T{i}" for i in ids})
    line = next(x for x in out.splitlines() if x.startswith("> Updated posts:"))
    assert line.count("<") == 10
    assert line.endswith(" and 4 more")


def test_no_change_lines_when_changes_unknown():
    out = msg(changes=None)
    assert "New post" not in out and "Updated" not in out


def test_build_warnings_and_ingest_failure():
    out = msg(warnings=2, ingest_failed=True)
    lines = out.splitlines()
    assert f"> ⚠️ <{RUN}|Build warnings on 2 pages>" in lines
    assert "> ⚠️ Inbox ingest failed · inbox/ left untouched" in lines
    assert f"> ⚠️ <{RUN}|Build warning on 1 page>" in msg(warnings=1).splitlines()


def test_no_changes_and_dry_run_headings():
    nothing = msg(published=False)
    assert nothing.splitlines()[0] == "*🚀 BLOG · NO CHANGES*"
    assert f"> ✅ <{RUN}|Build successful> · Nothing new to publish" in nothing
    dry = msg(published=False, publish_outcome="skipped")
    assert dry.splitlines()[0] == "*🚀 BLOG · DRY RUN*"
    assert f"> ✅ <{RUN}|Build successful> · Not published (dry run)" in dry


def test_failure_names_the_failed_step_and_keeps_change_lists():
    out = msg(status="failure", published=False, publish_outcome="skipped",
              step_outcomes={"build": "failure"},
              changes=changes(new_posts=["149"]))
    lines = out.splitlines()
    assert lines[:4] == ["<!here>", "*🚀 BLOG · PUBLISH FAILED*", "",
                         f"> 🔴 <{RUN}|Build failed> · Nothing published"]
    assert f"> New post: <{SITE}/149.html|My new post>" in lines


def test_failure_causes():
    def what(**kw):
        args = dict(status="failure", published=False, publish_outcome="skipped")
        args.update(kw)
        return msg(**args).splitlines()[3]
    assert "Publishing to the Pages repo failed" in what(
        publish_outcome="failure", step_outcomes={"build": "success"})
    assert "Committing the ingested inbox post failed" in what(
        step_outcomes={"commit_ingest": "failure"})
    assert "CI setup failed" in what()
    assert "Run was cancelled" in msg(status="cancelled", published=False,
                                      publish_outcome="skipped").splitlines()[3]


def test_published_but_cache_not_saved():
    out = msg(status="failure", save_cache="failure")
    lines = out.splitlines()
    assert lines[:4] == [
        "<!here>", f"*🚀 BLOG · <{SITE}|PUBLISHED>, CACHE NOT SAVED*", "",
        f"> 🟠 Site published, but <{RUN}|saving the build cache failed>"
        " · Next run does a full rebuild"]


def test_details_quoted_heading_not():
    out = msg(changes=changes(new_posts=["149"]), warnings=1)
    lines = out.splitlines()
    assert not lines[0].startswith(">") and lines[1] == ""
    assert all(x.startswith("> ") for x in lines[2:])


# trigger_label

def test_trigger_labels():
    t = blog_notify.trigger_label
    assert t("push", ingested=None) == "Push to main"
    assert t("push", ingested="149") == "Push · inbox post 149 ingested"
    assert t("workflow_dispatch", ingested=None) == "Manual run"
    assert t("workflow_dispatch", ingested=None, flush=True) == "Manual run (full rebuild)"
    pr = {"number": 119, "title": "T", "url": "https://github.com/mxgns/magnetizer/pull/119"}
    assert t("workflow_dispatch", ingested=None, magnetizer_sha="ca09750abc",
             magnetizer_pr=pr) == f"Magnetizer update <{pr['url']}|#119>"
    assert t("workflow_dispatch", ingested=None, magnetizer_sha="ca09750abc",
             magnetizer_pr=None) == (
        "Magnetizer update <https://github.com/mxgns/magnetizer/commit/ca09750abc|`ca09750`>")


def test_ingested_post_id_from_log():
    assert blog_notify.ingested_post("Post 149 created.\n") == "149"
    assert blog_notify.ingested_post("Nothing to ingest.\n") is None


def test_title_from_markdown():
    md = "---\ndate: 2026-01-01\ntitle: An old post\n---\n\nBody\n"
    assert blog_notify.title_from_markdown(md) == "An old post"
    assert blog_notify.title_from_markdown("---\ndate: 2026\n---\nx") is None


# Warning details (posted as a thread reply)

BUILD_LOG = """Building...
  148   148.md   [1 img]   ⚠ Broken internal link: 'jnco-1169.md'
  index.html   ⚠ Broken internal link: 'jnco-1169.md'
  inventory.html   ⚠ Broken internal link: 'jnco-1169.md', Other thing
1 created · 1 updated · 0 deleted
⚠ 3 warnings: 148.md, index.html, inventory.html

DONE with warnings
"""


def test_warning_lines_from_build_log():
    assert blog_notify.warning_lines(BUILD_LOG) == [
        "148   148.md   [1 img]   ⚠ Broken internal link: 'jnco-1169.md'",
        "index.html   ⚠ Broken internal link: 'jnco-1169.md'",
        "inventory.html   ⚠ Broken internal link: 'jnco-1169.md', Other thing",
    ]
    assert blog_notify.warning_lines("DONE.\n") == []


def test_warnings_reply():
    lines = blog_notify.warning_lines(BUILD_LOG)
    assert blog_notify.warnings_reply(lines) == "\n".join([
        ":warning: *Build warnings on 3 pages*",
        "```",
        *lines,
        "```",
    ])
    assert blog_notify.warnings_reply(lines[:1]).startswith(
        ":warning: *Build warning on 1 page*\n```\n")


def test_warnings_reply_caps_long_lists():
    lines = [f"{i}.html   ⚠ x" for i in range(60)]
    out = blog_notify.warnings_reply(lines).splitlines()
    assert out[0] == ":warning: *Build warnings on 60 pages*"
    assert out[-2] == "… and 10 more"
    assert len(out) == 1 + 1 + 50 + 1 + 1


def test_warnings_reply_none():
    assert blog_notify.warnings_reply([]) is None


def test_backticks_in_warnings_cannot_end_the_code_block():
    out = blog_notify.warnings_reply(["a.html   ⚠ Bad ```code```"])
    assert out.count("```") == 2


# Posting: bot token (threaded) vs webhook

class FakeSlack:
    def __init__(self):
        self.calls = []

    def api(self, method, payload, token):
        self.calls.append(("api", method, payload, token))
        return {"ok": True, "ts": "111.222"}

    def webhook(self, url, payload):
        self.calls.append(("webhook", url, payload))


def test_bot_token_posts_message_then_threaded_warnings():
    fake = FakeSlack()
    blog_notify.deliver("MAIN", "WARN", bot_token="xoxb", channel="C1",
                        webhook=None, api=fake.api, post_webhook=fake.webhook)
    assert fake.calls == [
        ("api", "chat.postMessage", {"channel": "C1", "text": "MAIN",
                                     "unfurl_links": False}, "xoxb"),
        ("api", "chat.postMessage", {"channel": "C1", "text": "WARN",
                                     "thread_ts": "111.222"}, "xoxb"),
    ]


def test_bot_token_without_warnings_posts_once():
    fake = FakeSlack()
    blog_notify.deliver("MAIN", None, bot_token="xoxb", channel="C1",
                        webhook=None, api=fake.api, post_webhook=fake.webhook)
    assert len(fake.calls) == 1


def test_webhook_fallback_posts_main_message_only():
    fake = FakeSlack()
    blog_notify.deliver("MAIN", "WARN", bot_token=None, channel=None,
                        webhook="https://hook", api=fake.api, post_webhook=fake.webhook)
    assert fake.calls == [("webhook", "https://hook", {"text": "MAIN"})]


def test_bot_token_preferred_over_webhook():
    fake = FakeSlack()
    blog_notify.deliver("MAIN", None, bot_token="xoxb", channel="C1",
                        webhook="https://hook", api=fake.api, post_webhook=fake.webhook)
    assert [c[0] for c in fake.calls] == ["api"]
