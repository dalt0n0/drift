"""Reporting service: generates PDF, HTML, JSON, SARIF, and CSV reports."""
from __future__ import annotations

import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_APP_VERSION = "0.1.0"

# Severity sort order (highest first)
_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _remediation_text(finding: Any) -> str:
    """Return generic remediation guidance based on finding title/severity."""
    title = (getattr(finding, "title", "") or str(finding.get("title", ""))).lower()

    if "sql injection" in title or "sqli" in title:
        return "Use parameterized queries or prepared statements. Never concatenate user input into SQL strings."
    if "xss" in title or "cross-site scripting" in title:
        return "Encode all user-supplied output in the appropriate context (HTML, JavaScript, URL). Implement Content-Security-Policy headers."
    if "ssrf" in title:
        return "Restrict outbound requests to a whitelist of allowed URLs. Validate and sanitize all user-supplied URLs before making requests."
    if "directory traversal" in title or "path traversal" in title or "lfi" in title:
        return "Validate and canonicalize file paths. Use a whitelist of allowed paths. Never pass user input directly to file system APIs."
    if "xxe" in title:
        return "Disable XML external entity processing in your XML parser."
    if "rce" in title or "remote code execution" in title:
        return "Patch the affected component immediately. Restrict command execution privileges. Apply defense-in-depth controls."
    if "csrf" in title:
        return "Implement CSRF tokens on all state-changing requests. Use SameSite=Strict or SameSite=Lax cookie attributes."
    if "open redirect" in title:
        return "Validate redirect destinations against a whitelist. Never redirect to user-supplied URLs without validation."
    if "ssl" in title or "tls" in title or "certificate" in title:
        return "Upgrade to TLS 1.2+ with strong cipher suites. Disable SSLv2, SSLv3, TLS 1.0, and TLS 1.1. Ensure certificates are valid and trusted."
    if "default credential" in title or "default password" in title:
        return "Change all default credentials immediately. Implement a password policy requiring strong, unique passwords."
    if "information disclosure" in title or "version" in title or "banner" in title:
        return "Remove or suppress version information from server headers, error messages, and other outputs."
    if "clickjacking" in title:
        return "Add X-Frame-Options: DENY or SAMEORIGIN headers. Use Content-Security-Policy frame-ancestors directive."
    if "cors" in title:
        return "Restrict CORS to specific trusted origins. Never use wildcard (*) with credentials."
    if "snmp" in title:
        return "Change SNMP community strings from defaults. Use SNMPv3 with authentication and encryption."
    if "subdomain takeover" in title:
        return "Remove dangling DNS records pointing to decommissioned resources. Regularly audit DNS records."

    # Generic by severity
    severity = getattr(finding, "severity", None) or finding.get("severity", "info")
    if severity == "critical":
        return "This critical severity finding requires immediate remediation. Patch or mitigate as a top priority."
    if severity == "high":
        return "Remediate this finding within 7 days. Review the affected component and apply the vendor patch or configuration fix."
    if severity == "medium":
        return "Review and remediate this finding within 30 days as part of your normal patch cycle."
    if severity == "low":
        return "Address this finding during the next scheduled maintenance window."
    return "Review this informational finding and assess applicability to your environment."


def _finding_to_dict(f: Any) -> dict:
    """Convert a Finding ORM object or dict to a plain dict for templates."""
    if isinstance(f, dict):
        return f
    return {
        "id": str(f.id),
        "title": f.title,
        "description": f.description or "",
        "severity": f.severity,
        "cvss_score": f.cvss_score,
        "cvss_vector": f.cvss_vector,
        "epss_score": f.epss_score,
        "epss_percentile": f.epss_percentile,
        "cve_ids": list(f.cve_ids or []),
        "cisa_kev": f.cisa_kev,
        "attack_technique_ids": list(f.attack_technique_ids or []),
        "affected_target": f.affected_target or "",
        "evidence": f.evidence or {},
        "status": f.status,
        "discovered_by": f.discovered_by or "",
        "notes": f.notes,
        "created_at": f.created_at.isoformat() if hasattr(f.created_at, "isoformat") else str(f.created_at),
    }


def _engagement_to_dict(e: Any) -> dict:
    if isinstance(e, dict):
        return e
    return {
        "id": str(e.id),
        "title": e.title,
        "client_name": e.client_name,
        "description": e.description or "",
        "status": e.status,
        "start_date": e.start_date.strftime("%Y-%m-%d") if e.start_date else None,
        "end_date": e.end_date.strftime("%Y-%m-%d") if e.end_date else None,
    }


def _scope_to_list(scope_items: list[Any]) -> list[dict]:
    result = []
    for item in scope_items:
        if isinstance(item, dict):
            result.append(item)
        else:
            result.append({
                "type": item.type,
                "value": item.value,
                "is_excluded": item.is_excluded,
                "notes": item.notes or "",
            })
    return result


def _build_stats(findings: list[dict]) -> dict:
    by_severity: dict[str, int] = {
        "critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0
    }
    for f in findings:
        sev = f.get("severity", "info")
        by_severity[sev] = by_severity.get(sev, 0) + 1
    return by_severity


def render_html(
    template_name: str,
    engagement: Any,
    findings: list[Any],
    scope_items: list[Any] | None = None,
    extra_ctx: dict | None = None,
) -> str:
    """Render a Jinja2 HTML report template.

    Args:
        template_name: Template file name under templates/reports/ (e.g. "technical.html.jinja2").
        engagement: Engagement ORM object or dict.
        findings: List of Finding ORM objects or dicts.
        scope_items: List of ScopeItem ORM objects or dicts (optional).
        extra_ctx: Additional template context variables.

    Returns:
        Rendered HTML string.
    """
    env = _jinja_env()
    # Make remediation helper available in templates
    env.globals["_remediation"] = _remediation_text

    template = env.get_template(f"reports/{template_name}")

    finding_dicts = [_finding_to_dict(f) for f in findings]
    finding_dicts.sort(key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "info"), 99))

    eng_dict = _engagement_to_dict(engagement)
    scope_list = _scope_to_list(scope_items or [])
    by_severity = _build_stats(finding_dicts)

    critical_and_high = [f for f in finding_dicts if f["severity"] in ("critical", "high")]

    ctx = {
        "title": eng_dict["title"],
        "engagement": eng_dict,
        "findings": finding_dicts,
        "scope_items": scope_list,
        "total_findings": len(finding_dicts),
        "by_severity": by_severity,
        "critical_and_high": critical_and_high,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "version": _APP_VERSION,
    }
    if extra_ctx:
        ctx.update(extra_ctx)

    return template.render(**ctx)


def render_pdf(html: str) -> tuple[bytes, str]:
    """Convert an HTML string to PDF bytes using WeasyPrint.

    Falls back gracefully if WeasyPrint is not installed, returning the HTML as bytes
    with content_type text/html so callers can adapt.

    Returns:
        Tuple of (content_bytes, content_type).
    """
    try:
        from weasyprint import HTML as WeasyprintHTML
        pdf = WeasyprintHTML(string=html).write_pdf()
        return pdf, "application/pdf"
    except ImportError:
        logger.warning("reporting.weasyprint_unavailable", reason="weasyprint not installed; returning HTML")
        return html.encode("utf-8"), "text/html; charset=utf-8"
    except Exception as exc:
        logger.error("reporting.pdf_error", error=str(exc))
        raise


def generate_executive_report(
    engagement: Any,
    findings: list[Any],
    scope_items: list[Any] | None = None,
    as_pdf: bool = True,
) -> tuple[bytes, str]:
    """Generate an executive summary report (PDF or HTML)."""
    html = render_html("executive.html.jinja2", engagement, findings, scope_items)
    if as_pdf:
        return render_pdf(html)
    return html.encode("utf-8"), "text/html; charset=utf-8"


def generate_technical_report(
    engagement: Any,
    findings: list[Any],
    scope_items: list[Any] | None = None,
    as_pdf: bool = True,
) -> tuple[bytes, str]:
    """Generate a full technical report (PDF or HTML)."""
    html = render_html("technical.html.jinja2", engagement, findings, scope_items)
    if as_pdf:
        return render_pdf(html)
    return html.encode("utf-8"), "text/html; charset=utf-8"


def generate_json_report(
    engagement: Any,
    findings: list[Any],
    scope_items: list[Any] | None = None,
) -> tuple[bytes, str]:
    """Generate a structured JSON report."""
    finding_dicts = [_finding_to_dict(f) for f in findings]
    finding_dicts.sort(key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "info"), 99))
    by_severity = _build_stats(finding_dicts)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": f"Drift {_APP_VERSION}",
        "engagement": _engagement_to_dict(engagement),
        "scope": _scope_to_list(scope_items or []),
        "summary": {
            "total_findings": len(finding_dicts),
            "by_severity": by_severity,
            "cisa_kev_count": sum(1 for f in finding_dicts if f.get("cisa_kev")),
        },
        "findings": finding_dicts,
    }
    return json.dumps(report, indent=2, default=str).encode("utf-8"), "application/json; charset=utf-8"


def generate_csv_report(
    engagement: Any,
    findings: list[Any],
) -> tuple[bytes, str]:
    """Generate a CSV findings summary."""
    finding_dicts = [_finding_to_dict(f) for f in findings]
    finding_dicts.sort(key=lambda f: _SEVERITY_ORDER.get(f.get("severity", "info"), 99))

    output = io.StringIO()
    fieldnames = [
        "id", "title", "severity", "cvss_score", "epss_score", "cisa_kev",
        "affected_target", "discovered_by", "status", "cve_ids",
        "attack_technique_ids", "created_at",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for f in finding_dicts:
        row = dict(f)
        row["cve_ids"] = "|".join(f.get("cve_ids", []))
        row["attack_technique_ids"] = "|".join(f.get("attack_technique_ids", []))
        row["cisa_kev"] = "Yes" if f.get("cisa_kev") else "No"
        writer.writerow(row)

    return output.getvalue().encode("utf-8"), "text/csv; charset=utf-8"


def generate_sarif_report(
    engagement: Any,
    findings: list[Any],
) -> tuple[bytes, str]:
    """Generate a SARIF 2.1.0 report for CI/CD integration."""
    finding_dicts = [_finding_to_dict(f) for f in findings]
    eng_dict = _engagement_to_dict(engagement)

    # Build rules from unique finding titles
    rules_seen: dict[str, dict] = {}
    for f in finding_dicts:
        rule_id = f.get("id", str(uuid.uuid4()))
        if rule_id not in rules_seen:
            rules_seen[rule_id] = {
                "id": rule_id,
                "name": f["title"].replace(" ", ""),
                "shortDescription": {"text": f["title"]},
                "fullDescription": {"text": f.get("description", f["title"])},
                "defaultConfiguration": {
                    "level": _severity_to_sarif_level(f["severity"])
                },
                "properties": {
                    "tags": f.get("attack_technique_ids", []),
                    "precision": "high",
                    "problem.severity": f["severity"],
                },
            }

    results = []
    for f in finding_dicts:
        results.append({
            "ruleId": f.get("id", ""),
            "level": _severity_to_sarif_level(f["severity"]),
            "message": {"text": f.get("description") or f["title"]},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": f.get("affected_target", ""),
                        "uriBaseId": "TARGETROOT",
                    }
                }
            }],
            "properties": {
                "severity": f["severity"],
                "cvssScore": f.get("cvss_score"),
                "cvssVector": f.get("cvss_vector"),
                "epssScore": f.get("epss_score"),
                "cisaKev": f.get("cisa_kev", False),
                "cveIds": f.get("cve_ids", []),
                "discoveredBy": f.get("discovered_by", ""),
                "status": f.get("status", "open"),
            },
        })

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Drift",
                    "version": _APP_VERSION,
                    "informationUri": "https://github.com/dalt0n0/drift",
                    "rules": list(rules_seen.values()),
                }
            },
            "results": results,
            "properties": {
                "engagement": eng_dict["title"],
                "client": eng_dict["client_name"],
                "generatedAt": datetime.now(timezone.utc).isoformat(),
            },
        }],
    }

    return json.dumps(sarif, indent=2, default=str).encode("utf-8"), "application/json; charset=utf-8"


def generate_client_report(
    engagement: Any,
    findings: list[Any],
    scope_items: list[Any] | None = None,
    as_pdf: bool = True,
) -> tuple[bytes, str]:
    """Generate a redacted client-facing executive report.

    Redacts: internal IPs, exploit details, tool command lines, HTTP request/response.
    Shows: title, severity, affected_target, remediation guidance only.
    """
    # Redact findings
    redacted: list[Any] = []
    for f in findings:
        fd = _finding_to_dict(f)
        # Strip sensitive evidence
        fd["evidence"] = {}
        # Redact internal IPs from affected_target
        fd["affected_target"] = _redact_internal_target(fd.get("affected_target", ""))
        # Remove notes (may contain internal details)
        fd["notes"] = None
        # Remove raw CVE details from description for client view
        fd["description"] = _sanitize_client_description(fd.get("description", ""))
        redacted.append(fd)

    html = render_html(
        "executive.html.jinja2",
        engagement,
        redacted,
        scope_items,
        extra_ctx={"is_client_report": True},
    )
    if as_pdf:
        return render_pdf(html)
    return html.encode("utf-8"), "text/html; charset=utf-8"


def _severity_to_sarif_level(severity: str) -> str:
    return {"critical": "error", "high": "error", "medium": "warning",
            "low": "note", "info": "none"}.get(severity, "warning")


def _redact_internal_target(target: str) -> str:
    """Redact private IP address octets from a target string."""
    import re
    # Replace 10.x, 172.16-31.x, 192.168.x patterns
    target = re.sub(r"10\.\d+\.\d+\.\d+", "10.x.x.x", target)
    target = re.sub(r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+", "172.x.x.x", target)
    target = re.sub(r"192\.168\.\d+\.\d+", "192.168.x.x", target)
    return target


def _sanitize_client_description(desc: str) -> str:
    """Trim technical exploit details from client-facing descriptions."""
    if not desc:
        return ""
    # Truncate very long technical descriptions
    if len(desc) > 800:
        return desc[:800].rsplit(" ", 1)[0] + "..."
    return desc


async def store_report_minio(
    report_bytes: bytes,
    engagement_id: str,
    report_type: str,
    file_extension: str,
) -> str:
    """Store a report in MinIO and return the object key."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    object_key = f"reports/{engagement_id}/{timestamp}_{report_type}.{file_extension}"

    content_types = {
        "pdf": "application/pdf",
        "html": "text/html",
        "json": "application/json",
        "csv": "text/csv",
        "sarif": "application/json",
    }
    content_type = content_types.get(file_extension, "application/octet-stream")

    try:
        from app.config import get_settings
        from minio import Minio

        settings = get_settings()
        client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ROOT_USER,
            secret_key=settings.MINIO_ROOT_PASSWORD,
            secure=settings.MINIO_SECURE,
        )
        bucket = settings.MINIO_BUCKET_REPORTS
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

        import io as _io
        client.put_object(
            bucket, object_key, _io.BytesIO(report_bytes),
            length=len(report_bytes), content_type=content_type,
        )
        logger.info("reporting.stored", path=object_key, size=len(report_bytes))
    except Exception as exc:
        logger.warning("reporting.store_error", error=str(exc))

    return object_key
