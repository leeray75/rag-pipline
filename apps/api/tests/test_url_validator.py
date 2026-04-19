"""Tests for SSRF prevention."""

import pytest

from src.security.url_validator import SSRFError, validate_url


def test_valid_public_url():
    """Public URL passes validation."""
    url = validate_url("https://docs.python.org/3/")
    assert url == "https://docs.python.org/3/"


def test_blocks_private_ip():
    """Private IP range is blocked."""
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://192.168.1.1/secret")


def test_blocks_localhost():
    """Localhost is blocked."""
    with pytest.raises(SSRFError, match="blocked IP range"):
        validate_url("http://127.0.0.1/admin")


def test_blocks_non_http_scheme():
    """Non-HTTP schemes are blocked."""
    with pytest.raises(SSRFError, match="Unsupported scheme"):
        validate_url("ftp://example.com/file")


def test_blocks_missing_hostname():
    """Missing hostname is blocked."""
    with pytest.raises(SSRFError):
        validate_url("http:///path")
