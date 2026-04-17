"""
Parse Nuclei JSON output → list of finding dicts.
Nuclei outputs JSONL (one JSON object per line) or a single JSON array.
"""
import json
from typing import Any


def parse_nuclei_xml(content: bytes) -> list[dict]:
    """
    Handles both Nuclei JSONL and JSON array output.
    Returns normalized finding dicts.
    """
    text = content.decode("utf-8", errors="replace").strip()
    items: list[Any] = []

    if text.startswith("["):
        # JSON array
        try:
            items = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid Nuclei JSON: {e}")
    else:
        # JSONL
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # Skip malformed lines

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        info = item.get("info", {})
        severity = _normalize_severity(info.get("severity", "info"))
        results.append({
            "title": info.get("name", "Nuclei Finding"),
            "severity": severity,
            "description": info.get("description", ""),
            "matched": item.get("matched-at", item.get("host", "")),
            "tags": info.get("tags", []) if isinstance(info.get("tags"), list) else [],
            "template_id": item.get("template-id", ""),
            "host": item.get("host", ""),
        })
    return results


def _normalize_severity(s: str) -> str:
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "info": "info",
        "informational": "info",
        "unknown": "info",
    }
    return mapping.get(s.lower(), "info")
