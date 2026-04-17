"""
Parse Burp Suite XML export → list of finding dicts.
Burp XML: <issues><issue><name>, <severity>, <confidence>, <detail>, <background>, etc.
"""
from lxml import etree


def parse_burp_xml(content: bytes) -> list[dict]:
    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML: {e}")

    # Burp XML root tag is <issues> with <issue> children
    if root.tag == "issues":
        issue_elements = root.findall("issue")
    elif root.tag == "issue":
        issue_elements = [root]
    else:
        issue_elements = root.findall(".//issue")

    results = []
    for issue in issue_elements:
        def txt(tag: str) -> str:
            el = issue.find(tag)
            return (el.text or "").strip() if el is not None else ""

        severity = _normalize_severity(txt("severity"))
        results.append({
            "title": txt("name") or "Burp Finding",
            "severity": severity,
            "detail": txt("issueDetail") or txt("detail"),
            "background": txt("issueBackground") or txt("background"),
            "remediation_background": txt("remediationBackground"),
            "remediation_detail": txt("remediationDetail"),
            "confidence": txt("confidence"),
            "host": txt("host"),
            "path": txt("path"),
            "request": txt("request"),
            "response": txt("response"),
        })
    return results


def _normalize_severity(s: str) -> str:
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "information": "info",
        "informational": "info",
        "info": "info",
    }
    return mapping.get(s.lower(), "info")
