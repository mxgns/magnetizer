"""Tests for magnetizer/pagefind.py — run_pagefind_index()"""

import subprocess as sp
from unittest.mock import MagicMock, patch

import pytest
from magnetizer.pagefind import run_pagefind_index


class TestRunPagefindIndex:

    def test_invokes_pinned_pagefind_cli(self, tmp_path):
        with patch("magnetizer.pagefind.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            run_pagefind_index(tmp_path)
        cmd = mock_run.call_args.args[0]
        assert cmd == ["npx", "--yes", "pagefind@1.5.2", "--site", str(tmp_path)]

    def test_raises_runtime_error_on_failure(self, tmp_path):
        def side_effect(cmd, **kwargs):
            raise sp.CalledProcessError(1, cmd, stderr="pagefind: command not found")
        with patch("magnetizer.pagefind.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError):
                run_pagefind_index(tmp_path)

    def test_error_message_includes_stderr(self, tmp_path):
        def side_effect(cmd, **kwargs):
            raise sp.CalledProcessError(1, cmd, stderr="pagefind: command not found")
        with patch("magnetizer.pagefind.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError, match="command not found"):
                run_pagefind_index(tmp_path)

    def test_raises_runtime_error_when_npx_not_found(self, tmp_path):
        def side_effect(cmd, **kwargs):
            raise FileNotFoundError("[Errno 2] No such file or directory: 'npx'")
        with patch("magnetizer.pagefind.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError):
                run_pagefind_index(tmp_path)

    def test_raises_runtime_error_on_timeout(self, tmp_path):
        def side_effect(cmd, **kwargs):
            raise sp.TimeoutExpired(cmd, kwargs.get("timeout"))
        with patch("magnetizer.pagefind.subprocess.run", side_effect=side_effect):
            with pytest.raises(RuntimeError):
                run_pagefind_index(tmp_path)

    def test_does_not_raise_on_success(self, tmp_path):
        with patch("magnetizer.pagefind.subprocess.run", return_value=MagicMock(returncode=0)):
            run_pagefind_index(tmp_path)  # should not raise

    def test_specifies_timeout(self, tmp_path):
        with patch("magnetizer.pagefind.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            run_pagefind_index(tmp_path)
        assert mock_run.call_args.kwargs.get("timeout") is not None
