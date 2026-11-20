"""CLI integration tests for preview.py"""

import subprocess
import sys
import urllib.request
from pathlib import Path

from conftest import MINIMAL_MD, make_project

SCRIPT = Path(__file__).parent.parent / "preview.py"


def run_preview(args, cwd):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestHelp:

    def test_help_exits_zero(self, tmp_path):
        assert run_preview(["--help"], cwd=tmp_path).returncode == 0

    def test_help_describes_port(self, tmp_path):
        assert "--port" in run_preview(["--help"], cwd=tmp_path).stdout

    def test_help_describes_no_open(self, tmp_path):
        assert "--no-open" in run_preview(["--help"], cwd=tmp_path).stdout

    def test_help_mentions_build_flags_are_forwarded(self, tmp_path):
        assert "build.py" in run_preview(["--help"], cwd=tmp_path).stdout


class TestBuildFailure:

    def test_exits_nonzero_without_serving_when_build_fails(self, tmp_path):
        # No content/ etc. — build.py fails, so preview must not start serving
        # (which would otherwise block here until the timeout).
        result = run_preview(["--no-open", "--port", "0"], cwd=tmp_path)
        assert result.returncode != 0
        assert "Serving" not in result.stdout

    def test_unknown_build_flag_fails(self, tmp_path):
        make_project(tmp_path, posts={1: MINIMAL_MD})
        result = run_preview(["--no-open", "--port", "0", "--bogus"], cwd=tmp_path)
        assert result.returncode != 0


class TestServing:

    def _start(self, cwd, *extra):
        return subprocess.Popen(
            [sys.executable, "-u", str(SCRIPT), "--no-open", "--port", "0", *extra],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def _wait_for_url(self, proc):
        for line in proc.stdout:
            if line.startswith("Serving"):
                return line.split()[2]
        raise AssertionError("preview.py exited without serving")

    def test_builds_then_serves_the_site(self, tmp_path):
        make_project(tmp_path, posts={1: MINIMAL_MD})
        proc = self._start(tmp_path)
        try:
            url = self._wait_for_url(proc)
            assert url.startswith("http://localhost:")
            with urllib.request.urlopen(url + "1.html") as response:
                assert response.status == 200
        finally:
            proc.terminate()
            proc.wait(timeout=10)

    def test_forwards_build_flags_to_build_py(self, tmp_path):
        make_project(tmp_path, posts={1: MINIMAL_MD})
        proc = self._start(tmp_path, "--verbose")
        try:
            lines = []
            for line in proc.stdout:
                lines.append(line)
                if line.startswith("Serving"):
                    break
            assert any(line.startswith("Generating ") for line in lines)
        finally:
            proc.terminate()
            proc.wait(timeout=10)
