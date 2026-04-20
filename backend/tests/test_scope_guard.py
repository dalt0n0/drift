"""Tests for ScopeGuard: target validation against engagement scope."""
from __future__ import annotations

import pytest

from app.models.scope import ScopeItem, ScopeType
from app.plugins.scope_guard import (
    ScopeViolationError,
    _domain_in_scope_item,
    _ip_in_scope_item,
    _target_in_scope,
    validate_targets,
)


def _make_scope_item(scope_type: str, value: str, is_excluded: bool = False) -> ScopeItem:
    """Create a mock ScopeItem without DB."""
    item = ScopeItem.__new__(ScopeItem)
    item.type = scope_type
    item.value = value
    item.is_excluded = is_excluded
    return item


class TestIPInScopeItem:
    def test_ip_matches_exact(self):
        item = _make_scope_item("ip", "93.184.216.34")
        assert _ip_in_scope_item("93.184.216.34", item) is True

    def test_ip_matches_cidr(self):
        item = _make_scope_item("cidr", "203.0.113.0/24")
        assert _ip_in_scope_item("203.0.113.50", item) is True
        assert _ip_in_scope_item("203.0.114.1", item) is False

    def test_ip_no_match(self):
        item = _make_scope_item("ip", "1.2.3.4")
        assert _ip_in_scope_item("5.6.7.8", item) is False

    def test_domain_item_no_ip_match(self):
        item = _make_scope_item("domain", "example.com")
        assert _ip_in_scope_item("1.2.3.4", item) is False


class TestDomainInScopeItem:
    def test_exact_domain_match(self):
        item = _make_scope_item("domain", "example.com")
        assert _domain_in_scope_item("example.com", item) is True

    def test_subdomain_match(self):
        item = _make_scope_item("domain", "example.com")
        assert _domain_in_scope_item("sub.example.com", item) is True

    def test_no_match(self):
        item = _make_scope_item("domain", "example.com")
        assert _domain_in_scope_item("notexample.com", item) is False

    def test_wildcard_match(self):
        item = _make_scope_item("wildcard", "*.example.com")
        assert _domain_in_scope_item("sub.example.com", item) is True
        assert _domain_in_scope_item("example.com", item) is True

    def test_wildcard_no_match(self):
        item = _make_scope_item("wildcard", "*.example.com")
        assert _domain_in_scope_item("other.com", item) is False

    def test_url_item_domain_match(self):
        item = _make_scope_item("url", "https://app.example.com/path")
        assert _domain_in_scope_item("app.example.com", item) is True
        assert _domain_in_scope_item("other.com", item) is False


class TestTargetInScope:
    def test_ip_included(self):
        included = [_make_scope_item("cidr", "203.0.113.0/24")]
        assert _target_in_scope("203.0.113.5", included, []) is True

    def test_ip_not_included(self):
        included = [_make_scope_item("cidr", "203.0.113.0/24")]
        assert _target_in_scope("198.51.100.1", included, []) is False

    def test_domain_included(self):
        included = [_make_scope_item("domain", "example.com")]
        assert _target_in_scope("example.com", included, []) is True
        assert _target_in_scope("sub.example.com", included, []) is True

    def test_domain_excluded(self):
        included = [_make_scope_item("domain", "example.com")]
        excluded = [_make_scope_item("domain", "internal.example.com", is_excluded=True)]
        assert _target_in_scope("internal.example.com", included, excluded) is False
        assert _target_in_scope("other.example.com", included, excluded) is True

    def test_ip_excluded_from_cidr(self):
        included = [_make_scope_item("cidr", "203.0.113.0/24")]
        excluded = [_make_scope_item("ip", "203.0.113.100", is_excluded=True)]
        assert _target_in_scope("203.0.113.100", included, excluded) is False
        assert _target_in_scope("203.0.113.50", included, excluded) is True


class TestValidateTargets:
    def test_valid_targets(self):
        included = [_make_scope_item("domain", "example.com")]
        valid, rejected = validate_targets(
            ["example.com", "sub.example.com"], included, []
        )
        assert len(valid) == 2
        assert len(rejected) == 0

    def test_mix_of_valid_and_invalid(self):
        included = [_make_scope_item("domain", "example.com")]
        valid, rejected = validate_targets(
            ["example.com", "other.com"], included, []
        )
        assert valid == ["example.com"]
        assert rejected == ["other.com"]

    def test_hard_blocked_target_rejected(self):
        included = [
            _make_scope_item("cidr", "0.0.0.0/0"),  # "everything"
        ]
        valid, rejected = validate_targets(
            ["127.0.0.1", "8.8.8.8"], included, []
        )
        # 127.0.0.1 is hard-blocked regardless of scope
        assert "127.0.0.1" in rejected
        assert "8.8.8.8" in valid

    def test_gov_domain_hard_blocked(self):
        included = [_make_scope_item("domain", "whitehouse.gov")]
        valid, rejected = validate_targets(
            ["whitehouse.gov"], included, []
        )
        assert len(valid) == 0
        assert "whitehouse.gov" in rejected

    def test_empty_targets(self):
        valid, rejected = validate_targets([], [], [])
        assert valid == []
        assert rejected == []
