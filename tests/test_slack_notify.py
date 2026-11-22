import importlib.util
from pathlib import Path

_PATH = Path(__file__).parent.parent / ".github" / "scripts" / "slack_notify.py"
_spec = importlib.util.spec_from_file_location("slack_notify", _PATH)
slack_notify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slack_notify)
build_message = slack_notify.build_message

RUN = "https://github.com/mxgns/magnetizer/actions/runs/1"
DEPLOYS = "https://github.com/mxgns/blog/actions/workflows/publish.yml"
PR = {"number": 117, "title": "Hide generated headings on untitled posts",
      "url": "https://github.com/mxgns/magnetizer/pull/117"}
SHA = "d44f3d7aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OK = {"lint": "success", "tests": "success"}


def msg(**kw):
    args = dict(kind="test", status="success", branch="main", sha=SHA,
                subject="Hide generated headings on untitled posts (#117)",
                run_url=RUN, pr=PR, outcomes=OK)
    args.update(kw)
    return build_message(**args)


# Production (main)

def test_main_test_success_sends_nothing_because_refresh_announces_deploy():
    assert msg() is None


def test_production_deployed():
    assert msg(kind="refresh") == "\n".join([
        "*🧲 MAGNETIZER · PRODUCTION DEPLOYED*",
        "",
        f"✅ Tests passed · <{DEPLOYS}|Blog rebuild triggered>",
        "Commit: `d44f3d7`",
        "Change: Hide generated headings on untitled posts",
        f"PR: <{PR['url']}|#117> — Hide generated headings on untitled posts",
    ])


def test_production_test_failure():
    out = msg(status="failure", outcomes={"lint": "success", "tests": "failure"})
    assert out == "\n".join([
        "<!here>",
        "*🧲 MAGNETIZER · PRODUCTION FAILURE*",
        "",
        f"🔴 <{RUN}|Tests failed> on main · Not deployed",
        "Commit: `d44f3d7`",
        "Change: Hide generated headings on untitled posts",
        f"PR: <{PR['url']}|#117> — Hide generated headings on untitled posts",
    ])


def test_production_lint_failure_names_lint():
    out = msg(status="failure", outcomes={"lint": "failure", "tests": "skipped"})
    assert f"🔴 <{RUN}|Lint failed> on main · Not deployed" in out


def test_production_setup_failure_names_setup():
    out = msg(status="failure", outcomes={"lint": "skipped", "tests": "skipped"})
    assert f"🔴 <{RUN}|CI setup failed> on main · Not deployed" in out


def test_cancelled_run_says_cancelled():
    out = msg(status="cancelled", outcomes={"lint": "success", "tests": "cancelled"})
    assert f"🔴 <{RUN}|CI run was cancelled> on main · Not deployed" in out


def test_refresh_trigger_failure():
    out = msg(kind="refresh", status="failure")
    assert out.splitlines()[:4] == [
        "<!here>",
        "*🧲 MAGNETIZER · PRODUCTION FAILURE*",
        "",
        f"🔴 Tests passed, but the <{RUN}|blog rebuild couldn't be triggered>"
        " · Not deployed",
    ]
    assert "View" not in out


def test_production_without_pr_omits_pr_line_and_link():
    out = msg(kind="refresh", pr=None, subject="Direct commit")
    assert "PR:" not in out
    assert "Change: Direct commit" in out
    assert out.endswith("Change: Direct commit")


# Branch builds

def test_branch_build_passed():
    pr = {"number": 118, "title": "Add related posts",
          "url": "https://github.com/mxgns/magnetizer/pull/118"}
    out = msg(branch="related-posts", sha="ee3ee29" + "0" * 33, pr=pr)
    assert out == "\n".join([
        "*🧪 MAGNETIZER · BRANCH BUILD PASSED*",
        "",
        f"✅ <{RUN}|Tests passed> · Not deployed",
        f"PR: <{pr['url']}|#118> — Add related posts",
        "Branch: `related-posts` · `ee3ee29`",
    ])


def test_branch_build_failed():
    out = msg(branch="related-posts", status="failure",
              outcomes={"lint": "success", "tests": "failure"})
    assert out.splitlines()[:4] == [
        "<!here>",
        "*🧪 MAGNETIZER · BRANCH BUILD FAILED*",
        "",
        f"❌ <{RUN}|Tests failed> · Not deployed",
    ]
    assert "View" not in out


def test_branch_without_pr_says_so():
    out = msg(branch="wip", pr=None)
    assert "PR: none yet" in out
    assert out.endswith("Branch: `wip` · `d44f3d7`")


def test_slack_control_characters_are_escaped():
    pr = dict(PR, title="Use <b> & <i>")
    out = msg(kind="refresh", pr=pr, subject="a < b & c")
    assert f"PR: <{PR['url']}|#117> — Use &lt;b&gt; &amp; &lt;i&gt;" in out
    assert "Change: a &lt; b &amp; c" in out


# GitHub metadata lookups

UNAVAILABLE = slack_notify.UNAVAILABLE


def test_unavailable_metadata_is_labelled_not_dropped():
    out = msg(kind="refresh", status="failure", subject=UNAVAILABLE, pr=UNAVAILABLE)
    assert "Change: unavailable (GitHub lookup failed)" in out
    assert "PR: unavailable (GitHub lookup failed)" in out
    assert "Commit: `d44f3d7`" in out
    assert "View" not in out


def test_unavailable_pr_on_branch_is_not_reported_as_none_yet():
    out = msg(branch="wip", pr=UNAVAILABLE)
    assert "PR: unavailable (GitHub lookup failed)" in out
    assert "none yet" not in out
    assert out.endswith("Branch: `wip` · `d44f3d7`")


def _getter(responses):
    def get(path):
        result = responses[path]
        if isinstance(result, Exception):
            raise result
        return result
    return get


def test_fetch_metadata_success():
    get = _getter({
        "/repos/r/commits/s": {"commit": {"message": "Subject line\n\nBody"}},
        "/repos/r/commits/s/pulls": [{"number": 1, "title": "T", "html_url": "U"}],
    })
    assert slack_notify.fetch_metadata("r", "s", get) == (
        "Subject line", {"number": 1, "title": "T", "url": "U"})


def test_fetch_metadata_no_pr():
    get = _getter({
        "/repos/r/commits/s": {"commit": {"message": "Subject"}},
        "/repos/r/commits/s/pulls": [],
    })
    assert slack_notify.fetch_metadata("r", "s", get) == ("Subject", None)


def test_fetch_metadata_failures_are_independent():
    get = _getter({
        "/repos/r/commits/s": OSError("503"),
        "/repos/r/commits/s/pulls": [{"number": 1, "title": "T", "html_url": "U"}],
    })
    assert slack_notify.fetch_metadata("r", "s", get) == (
        UNAVAILABLE, {"number": 1, "title": "T", "url": "U"})
    get = _getter({
        "/repos/r/commits/s": {"commit": {"message": "Subject"}},
        "/repos/r/commits/s/pulls": OSError("503"),
    })
    assert slack_notify.fetch_metadata("r", "s", get) == ("Subject", UNAVAILABLE)


def test_heading_is_followed_by_an_empty_row():
    for out in [msg(kind="refresh"), msg(status="failure"), msg(branch="wip")]:
        lines = out.splitlines()
        heading = 1 if lines[0] == "<!here>" else 0
        assert lines[heading].startswith("*")
        assert lines[heading + 1] == ""
        assert lines[heading + 2] != ""
