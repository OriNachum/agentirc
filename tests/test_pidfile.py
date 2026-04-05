"""Tests for culture.pidfile — PID file management and process validation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from culture.pidfile import (
    is_culture_process,
    is_process_alive,
    read_pid,
    remove_pid,
    write_pid,
)


@pytest.fixture()
def pid_dir(tmp_path):
    """Use a temporary directory for PID files."""
    with patch("culture.pidfile.PID_DIR", str(tmp_path)):
        yield tmp_path


class TestWriteReadRemove:
    def test_write_and_read(self, pid_dir):
        write_pid("agent-bot", 12345)
        assert read_pid("agent-bot") == 12345

    def test_read_missing(self, pid_dir):
        assert read_pid("nonexistent") is None

    def test_remove(self, pid_dir):
        write_pid("agent-bot", 12345)
        remove_pid("agent-bot")
        assert read_pid("agent-bot") is None

    def test_remove_missing_is_noop(self, pid_dir):
        remove_pid("nonexistent")  # should not raise


class TestIsProcessAlive:
    def test_current_process_alive(self):
        assert is_process_alive(os.getpid()) is True

    def test_nonexistent_pid(self):
        # Use a very high PID unlikely to exist.
        assert is_process_alive(4_000_000) is False


class TestIsCultureProcess:
    @pytest.mark.skipif(
        not Path("/proc/self/cmdline").exists(),
        reason="/proc not available",
    )
    def test_current_process_is_python(self):
        # We're running under pytest — cmdline won't contain "culture"
        # as an exact argv token, so this should return False.
        result = is_culture_process(os.getpid())
        assert isinstance(result, bool)

    def test_cmdline_with_culture_token(self):
        """Exact argv token 'culture' is recognized (e.g. -m culture)."""
        raw = b"/usr/bin/python3\x00-m\x00culture\x00start\x00"
        with (
            patch("culture.pidfile.Path") as mock_path,
            patch("culture.pidfile.os.path.isdir", return_value=True),
        ):
            mock_path.return_value.read_bytes.return_value = raw
            assert is_culture_process(999) is True

    def test_cmdline_with_culture_basename(self):
        """argv[0] with basename 'culture' is recognized."""
        raw = b"/home/user/.local/bin/culture\x00server\x00start\x00"
        with (
            patch("culture.pidfile.Path") as mock_path,
            patch("culture.pidfile.os.path.isdir", return_value=True),
        ):
            mock_path.return_value.read_bytes.return_value = raw
            assert is_culture_process(999) is True

    def test_cmdline_without_culture(self):
        """Process with unrelated cmdline is rejected."""
        raw = b"/sbin/init\x00--system\x00"
        with (
            patch("culture.pidfile.Path") as mock_path,
            patch("culture.pidfile.os.path.isdir", return_value=True),
        ):
            mock_path.return_value.read_bytes.return_value = raw
            assert is_culture_process(999) is False

    def test_cmdline_substring_not_matched(self):
        """Substring 'culture' inside another token is NOT matched."""
        raw = b"/usr/bin/agriculture-daemon\x00--flag\x00"
        with (
            patch("culture.pidfile.Path") as mock_path,
            patch("culture.pidfile.os.path.isdir", return_value=True),
        ):
            mock_path.return_value.read_bytes.return_value = raw
            assert is_culture_process(999) is False

    def test_no_proc_returns_true(self):
        """When /proc doesn't exist (macOS/Windows), assume valid."""
        with patch("culture.pidfile.os.path.isdir", return_value=False):
            assert is_culture_process(999) is True

    def test_oserror_on_linux_returns_false(self):
        """On Linux, read failures fail closed (return False)."""
        with (
            patch("culture.pidfile.Path") as mock_path,
            patch("culture.pidfile.os.path.isdir", return_value=True),
        ):
            mock_path.return_value.read_bytes.side_effect = OSError("denied")
            assert is_culture_process(999) is False

    @pytest.mark.skipif(
        not Path("/proc/self/cmdline").exists(),
        reason="/proc not available",
    )
    def test_nonexistent_pid_fails_closed(self):
        """/proc exists but PID doesn't — should return False."""
        assert is_culture_process(4_000_000) is False
