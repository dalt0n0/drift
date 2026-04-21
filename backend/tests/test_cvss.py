"""Tests for CVSS 3.1 calculator."""
from __future__ import annotations

import pytest

from app.core.cvss import CVSSParseError, calculate, severity_from_score


class TestCVSSCalculate:
    def test_critical_network_vector(self):
        # Log4Shell-style: AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H = 10.0
        result = calculate("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H")
        assert result["score"] == 10.0
        assert result["severity"] == "critical"

    def test_high_score(self):
        # AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H = 9.8
        result = calculate("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
        assert result["score"] == 9.8
        assert result["severity"] == "critical"

    def test_medium_score(self):
        # AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N
        result = calculate("AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:L/A:N")
        assert 4.0 <= result["score"] < 7.0
        assert result["severity"] == "medium"

    def test_low_score(self):
        # AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N
        result = calculate("AV:L/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N")
        assert 0 < result["score"] < 4.0
        assert result["severity"] == "low"

    def test_none_score_all_none(self):
        # AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N = 0.0
        result = calculate("AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N")
        assert result["score"] == 0.0
        assert result["severity"] == "none"

    def test_prefix_with_and_without(self):
        v = "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
        r1 = calculate(v)
        r2 = calculate(f"CVSS:3.1/{v}")
        assert r1["score"] == r2["score"]

    def test_result_contains_expected_keys(self):
        result = calculate("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
        for key in ("score", "severity", "vector", "iss", "impact", "exploitability"):
            assert key in result

    def test_vector_normalized_in_result(self):
        result = calculate("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
        assert result["vector"].startswith("CVSS:3.1/")

    def test_scope_changed_pr_weights(self):
        # S:C means PR:L = 0.50 not 0.62
        r_unchanged = calculate("AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H")
        r_changed = calculate("AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H")
        # Scope Changed with PR:L should give different exploitability
        assert r_changed["exploitability"] != r_unchanged["exploitability"]

    def test_invalid_metric_value(self):
        with pytest.raises(CVSSParseError):
            calculate("AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")

    def test_missing_metric(self):
        with pytest.raises(CVSSParseError):
            calculate("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H")

    def test_malformed_vector(self):
        with pytest.raises((CVSSParseError, ValueError)):
            calculate("not-a-vector")

    def test_physical_access_vector(self):
        result = calculate("AV:P/AC:H/PR:H/UI:R/S:U/C:L/I:N/A:N")
        assert result["score"] >= 0

    def test_roundup_precision(self):
        # Score should be rounded to 1 decimal
        result = calculate("AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:H")
        score_str = str(result["score"])
        # At most 1 decimal place
        if "." in score_str:
            assert len(score_str.split(".")[1]) <= 1

    def test_cve_2021_44228_log4shell(self):
        # Log4Shell CVSS vector
        result = calculate("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H")
        assert result["score"] == 10.0
        assert result["severity"] == "critical"

    def test_cve_2014_0160_heartbleed(self):
        # Heartbleed: AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N = 7.5
        result = calculate("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N")
        assert result["score"] == 7.5
        assert result["severity"] == "high"


class TestSeverityFromScore:
    def test_critical(self):
        assert severity_from_score(9.0) == "critical"
        assert severity_from_score(10.0) == "critical"

    def test_high(self):
        assert severity_from_score(7.0) == "high"
        assert severity_from_score(8.9) == "high"

    def test_medium(self):
        assert severity_from_score(4.0) == "medium"
        assert severity_from_score(6.9) == "medium"

    def test_low(self):
        assert severity_from_score(0.1) == "low"
        assert severity_from_score(3.9) == "low"

    def test_none_zero(self):
        assert severity_from_score(0.0) == "none"

    def test_none_null(self):
        assert severity_from_score(None) == "info"
