"""Tests for reporting service: HTML rendering, JSON, CSV, SARIF."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Minimal stub engagement / finding objects
# ---------------------------------------------------------------------------

class _Eng:
    def __init__(self):
        self.id = uuid.uuid4()
        self.title = "Test Engagement"
        self.client_name = "Acme Corp"
        self.description = "Pentest of web application"
        self.status = "active"
        self.start_date = None
        self.end_date = None


class _Finding:
    def __init__(self, severity="high", title="SQL Injection", cisa_kev=False):
        self.id = uuid.uuid4()
        self.engagement_id = uuid.uuid4()
        self.run_id = None
        self.title = title
        self.description = "SQL injection in login endpoint"
        self.severity = severity
        self.cvss_score = 9.8 if severity == "critical" else 7.5
        self.cvss_vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
        self.epss_score = 0.42
        self.epss_percentile = 0.95
        self.cve_ids = ["CVE-2021-9999"]
        self.cisa_kev = cisa_kev
        self.attack_technique_ids = ["T1190"]
        self.affected_target = "https://example.com/login"
        self.evidence = {"request": "GET /login HTTP/1.1\nHost: example.com"}
        self.status = "open"
        self.discovered_by = "nuclei"
        self.deduplicated_from = []
        self.notes = None
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)


class _ScopeItem:
    def __init__(self):
        self.type = "domain"
        self.value = "example.com"
        self.is_excluded = False
        self.notes = ""


# ---------------------------------------------------------------------------
# Import reporting (pure Python; no DB needed)
# ---------------------------------------------------------------------------

from app.services.reporting import (
    _finding_to_dict,
    _engagement_to_dict,
    _build_stats,
    _remediation_text,
    generate_json_report,
    generate_csv_report,
    generate_sarif_report,
    render_html,
)


class TestFindingToDict:
    def test_orm_object_converted(self):
        f = _Finding()
        d = _finding_to_dict(f)
        assert d["title"] == "SQL Injection"
        assert d["severity"] == "high"
        assert d["cve_ids"] == ["CVE-2021-9999"]
        assert isinstance(d["attack_technique_ids"], list)

    def test_dict_passthrough(self):
        d_in = {"title": "Test", "severity": "low"}
        d_out = _finding_to_dict(d_in)
        assert d_out is d_in


class TestBuildStats:
    def test_counts_by_severity(self):
        findings = [
            {"severity": "critical"},
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "low"},
            {"severity": "info"},
        ]
        stats = _build_stats(findings)
        assert stats["critical"] == 2
        assert stats["high"] == 1
        assert stats["low"] == 1
        assert stats["info"] == 1
        assert stats["medium"] == 0


class TestRemediationText:
    def test_sql_injection(self):
        f = _Finding(title="SQL Injection")
        text = _remediation_text(f)
        assert "parameterized" in text.lower() or "prepared" in text.lower()

    def test_xss(self):
        f = _Finding(title="XSS via search")
        text = _remediation_text(f)
        assert "encod" in text.lower() or "csp" in text.lower() or "content-security" in text.lower()

    def test_csrf(self):
        f = _Finding(title="CSRF Token Missing")
        text = _remediation_text(f)
        assert "csrf" in text.lower() or "token" in text.lower() or "samesite" in text.lower()

    def test_generic_critical(self):
        f = _Finding(severity="critical", title="Unknown Critical Issue")
        text = _remediation_text(f)
        assert len(text) > 10

    def test_generic_info(self):
        f = _Finding(severity="info", title="Port Scan Result")
        text = _remediation_text(f)
        assert len(text) > 10


class TestJSONReport:
    def test_valid_json(self):
        eng = _Eng()
        findings = [_Finding(), _Finding(severity="critical", cisa_kev=True)]
        data = generate_json_report(eng, findings)
        parsed = json.loads(data)
        assert "findings" in parsed
        assert "summary" in parsed
        assert parsed["summary"]["total_findings"] == 2
        assert parsed["summary"]["cisa_kev_count"] == 1

    def test_sorted_by_severity(self):
        eng = _Eng()
        findings = [
            _Finding(severity="info", title="Info"),
            _Finding(severity="critical", title="Critical"),
            _Finding(severity="medium", title="Medium"),
        ]
        data = generate_json_report(eng, findings)
        parsed = json.loads(data)
        severities = [f["severity"] for f in parsed["findings"]]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        assert all(
            order[severities[i]] <= order[severities[i + 1]]
            for i in range(len(severities) - 1)
        )

    def test_engagement_fields_present(self):
        eng = _Eng()
        data = generate_json_report(eng, [])
        parsed = json.loads(data)
        assert parsed["engagement"]["title"] == "Test Engagement"
        assert parsed["engagement"]["client_name"] == "Acme Corp"

    def test_empty_findings(self):
        eng = _Eng()
        data = generate_json_report(eng, [])
        parsed = json.loads(data)
        assert parsed["summary"]["total_findings"] == 0


class TestCSVReport:
    def test_valid_csv(self):
        eng = _Eng()
        findings = [_Finding(), _Finding(severity="critical")]
        data = generate_csv_report(eng, findings)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        rows = list(reader)
        assert len(rows) == 2

    def test_csv_fields(self):
        eng = _Eng()
        findings = [_Finding(cisa_kev=True)]
        data = generate_csv_report(eng, findings)
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        row = next(reader)
        assert row["title"] == "SQL Injection"
        assert row["severity"] == "high"
        assert row["cisa_kev"] == "Yes"
        assert "CVE-2021-9999" in row["cve_ids"]
        assert "T1190" in row["attack_technique_ids"]

    def test_empty_findings(self):
        eng = _Eng()
        data = generate_csv_report(eng, [])
        reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
        assert list(reader) == []


class TestSARIFReport:
    def test_valid_sarif_structure(self):
        eng = _Eng()
        findings = [_Finding(), _Finding(severity="critical")]
        data = generate_sarif_report(eng, findings)
        sarif = json.loads(data)
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        run = sarif["runs"][0]
        assert run["tool"]["driver"]["name"] == "Drift"
        assert len(run["results"]) == 2

    def test_severity_to_sarif_level(self):
        from app.services.reporting import _severity_to_sarif_level
        assert _severity_to_sarif_level("critical") == "error"
        assert _severity_to_sarif_level("high") == "error"
        assert _severity_to_sarif_level("medium") == "warning"
        assert _severity_to_sarif_level("low") == "note"
        assert _severity_to_sarif_level("info") == "none"

    def test_result_properties(self):
        eng = _Eng()
        findings = [_Finding(cisa_kev=True)]
        data = generate_sarif_report(eng, findings)
        sarif = json.loads(data)
        result = sarif["runs"][0]["results"][0]
        assert result["properties"]["cisaKev"] is True
        assert "CVE-2021-9999" in result["properties"]["cveIds"]

    def test_empty_findings(self):
        eng = _Eng()
        data = generate_sarif_report(eng, [])
        sarif = json.loads(data)
        assert sarif["runs"][0]["results"] == []


class TestHTMLReport:
    def test_executive_html_renders(self):
        eng = _Eng()
        findings = [_Finding(severity="critical"), _Finding()]
        html = render_html("executive.html.jinja2", eng, findings)
        assert "<html" in html.lower()
        assert "Acme Corp" in html
        assert "Test Engagement" in html
        assert "critical" in html.lower()

    def test_technical_html_renders(self):
        eng = _Eng()
        findings = [_Finding()]
        html = render_html("technical.html.jinja2", eng, findings)
        assert "<html" in html.lower()
        assert "SQL Injection" in html
        assert "CVE-2021-9999" in html

    def test_html_contains_finding_data(self):
        eng = _Eng()
        f = _Finding(severity="critical", cisa_kev=True)
        f.title = "Unique Finding Title XYZ"
        html = render_html("technical.html.jinja2", eng, [f])
        assert "Unique Finding Title XYZ" in html

    def test_html_escapes_special_chars(self):
        eng = _Eng()
        f = _Finding()
        f.title = "XSS <script>alert('xss')</script>"
        html = render_html("technical.html.jinja2", eng, [f])
        assert "<script>alert" not in html  # should be escaped


class TestRedaction:
    def test_redact_internal_target(self):
        from app.services.reporting import _redact_internal_target
        assert "10.x.x.x" in _redact_internal_target("https://10.1.2.3/admin")
        assert "192.168.x.x" in _redact_internal_target("192.168.1.100")
        assert "172.x.x.x" in _redact_internal_target("172.16.0.1")
        # Public IPs should not be redacted
        assert "1.2.3.4" in _redact_internal_target("http://1.2.3.4/path")
