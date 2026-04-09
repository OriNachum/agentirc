"""Tests for culture.credentials — OS credential store helpers."""

from unittest.mock import patch

from culture.credentials import _run, lookup_credential, store_credential


def test_run_missing_binary():
    """_run() returns (127, '') when the binary is not found."""
    rc, out = _run(["nonexistent-binary-xyz-12345"])
    assert rc == 127
    assert out == ""


def test_lookup_credential_missing_tool():
    """lookup_credential() returns None when the credential tool is missing."""
    with patch("culture.credentials._run", return_value=(127, "")):
        assert lookup_credential("some-peer") is None


def test_store_credential_missing_tool():
    """store_credential() returns False when the credential tool is missing."""
    with patch("culture.credentials._run", return_value=(127, "")):
        assert store_credential("some-peer", "password") is False
