"""Tests for scope validator — all hard-block ranges."""
from __future__ import annotations

import os
from unittest import mock

import pytest

from app.models.scope import ScopeValidationError, ScopeValidator


class TestBlockedCIDRs:
    """Test that all blocked CIDR ranges are rejected."""

    @pytest.mark.parametrize(
        "value",
        [
            "10.0.0.1",
            "10.255.255.255",
            "10.0.0.0/8",
            "10.1.2.0/24",
            "172.16.0.1",
            "172.31.255.255",
            "172.16.0.0/12",
            "192.168.0.1",
            "192.168.1.0/24",
            "192.168.0.0/16",
            "127.0.0.1",
            "127.0.0.0/8",
            "169.254.0.1",
            "169.254.0.0/16",
            "169.254.169.254",
            "169.254.169.254/32",
            "100.64.0.1",
            "100.64.0.0/10",
            "100.127.255.255",
        ],
    )
    def test_ipv4_blocked_ranges(self, value):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("ip", value)

    @pytest.mark.parametrize(
        "value",
        [
            "::1",
            "::1/128",
            "fe80::1",
            "fe80::/10",
            "fd00:ec2::254",
            "fd00:ec2::254/128",
        ],
    )
    def test_ipv6_blocked_ranges(self, value):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("ip", value)

    @pytest.mark.parametrize(
        "value",
        [
            "8.8.8.8",
            "1.1.1.1",
            "203.0.113.1",
            "198.51.100.0/24",
            "93.184.216.34",
        ],
    )
    def test_public_ips_allowed(self, value):
        # Should not raise
        ScopeValidator.validate("ip", value)

    def test_cidr_type_also_validates(self):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("cidr", "10.0.0.0/8")

        # Public CIDR should pass
        ScopeValidator.validate("cidr", "203.0.113.0/24")


class TestBlockedTLDs:
    """Test that .gov and .mil TLDs are blocked."""

    @pytest.mark.parametrize(
        "value",
        [
            "whitehouse.gov",
            "defense.mil",
            "test.sub.whitehouse.gov",
            "army.mil",
            "irs.gov",
        ],
    )
    def test_blocked_tlds(self, value):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("domain", value)

    @pytest.mark.parametrize(
        "value",
        [
            "example.com",
            "test.org",
            "company.io",
            "mil.example.com",  # .mil as subdomain is fine
            "gov.example.com",  # .gov as subdomain is fine
        ],
    )
    def test_allowed_tlds(self, value):
        ScopeValidator.validate("domain", value)


class TestBlockedDomains:
    """Test that cloud metadata domains are blocked."""

    @pytest.mark.parametrize(
        "value",
        [
            "metadata.google.internal",
            "metadata.azure.com",
            "sub.metadata.google.internal",
            "sub.metadata.azure.com",
        ],
    )
    def test_blocked_metadata_domains(self, value):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("domain", value)


class TestURLValidation:
    """Test URL scope type validation."""

    def test_url_with_blocked_domain(self):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("url", "https://whitehouse.gov/admin")

    def test_url_with_blocked_ip(self):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("url", "http://169.254.169.254/latest/meta-data/")

    def test_url_with_allowed_domain(self):
        ScopeValidator.validate("url", "https://example.com/path")

    def test_url_with_allowed_ip(self):
        ScopeValidator.validate("url", "http://93.184.216.34/test")

    def test_invalid_url_format(self):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("url", "not-a-url")


class TestWildcardValidation:
    """Test wildcard scope type validation."""

    def test_wildcard_blocked_tld(self):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("wildcard", "*.whitehouse.gov")

    def test_wildcard_allowed(self):
        ScopeValidator.validate("wildcard", "*.example.com")

    def test_wildcard_blocked_domain(self):
        with pytest.raises(ScopeValidationError):
            ScopeValidator.validate("wildcard", "*.metadata.google.internal")


class TestRFC1918Override:
    """Test ALLOW_RFC1918 env flag behavior."""

    def test_rfc1918_blocked_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ScopeValidationError):
                ScopeValidator.validate("ip", "192.168.1.1")

    def test_rfc1918_allowed_with_flag(self):
        with mock.patch.dict(os.environ, {"ALLOW_RFC1918": "true"}):
            # Should NOT raise for RFC 1918
            ScopeValidator.validate("ip", "192.168.1.1")
            ScopeValidator.validate("ip", "10.0.0.1")
            ScopeValidator.validate("cidr", "172.16.0.0/12")

    def test_non_rfc1918_still_blocked_with_flag(self):
        """Even with ALLOW_RFC1918, loopback/link-local/metadata stay blocked."""
        with mock.patch.dict(os.environ, {"ALLOW_RFC1918": "true"}):
            with pytest.raises(ScopeValidationError):
                ScopeValidator.validate("ip", "127.0.0.1")
            with pytest.raises(ScopeValidationError):
                ScopeValidator.validate("ip", "169.254.169.254")
            with pytest.raises(ScopeValidationError):
                ScopeValidator.validate("ip", "100.64.0.1")


class TestBatchValidation:
    """Test batch validation returns all errors."""

    def test_batch_mixed(self):
        items = [
            {"type": "ip", "value": "8.8.8.8"},
            {"type": "ip", "value": "10.0.0.1"},
            {"type": "domain", "value": "whitehouse.gov"},
            {"type": "domain", "value": "example.com"},
        ]
        errors = ScopeValidator.validate_batch(items)
        assert len(errors) == 2
        blocked_values = {e["value"] for e in errors}
        assert "10.0.0.1" in blocked_values
        assert "whitehouse.gov" in blocked_values

    def test_batch_all_valid(self):
        items = [
            {"type": "ip", "value": "8.8.8.8"},
            {"type": "domain", "value": "example.com"},
        ]
        errors = ScopeValidator.validate_batch(items)
        assert len(errors) == 0

    def test_batch_all_invalid(self):
        items = [
            {"type": "ip", "value": "127.0.0.1"},
            {"type": "domain", "value": "test.mil"},
        ]
        errors = ScopeValidator.validate_batch(items)
        assert len(errors) == 2


class TestUnknownScopeType:
    def test_unknown_type_raises(self):
        with pytest.raises(ScopeValidationError, match="Unknown scope type"):
            ScopeValidator.validate("foobar", "value")
