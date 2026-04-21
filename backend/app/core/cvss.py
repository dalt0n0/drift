"""CVSS 3.1 base score calculator from vector string."""
from __future__ import annotations

import math
import re

# Base metric weights (CVSS 3.1 specification)
_AV = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.20}
_AC = {"L": 0.77, "H": 0.44}
_PR_UNCHANGED = {"N": 0.85, "L": 0.62, "H": 0.27}
_PR_CHANGED = {"N": 0.85, "L": 0.50, "H": 0.50}
_UI = {"N": 0.85, "R": 0.62}
_CIA = {"H": 0.56, "L": 0.22, "N": 0.00}

_VECTOR_RE = re.compile(
    r"^(?:CVSS:3\.[01]/)?AV:[NALP]/AC:[LH]/PR:[NLH]/UI:[NR]/S:[UC]/C:[HLN]/I:[HLN]/A:[HLN]$"
)


class CVSSParseError(ValueError):
    """Raised when the CVSS vector string is malformed."""


def _roundup(value: float) -> float:
    """CVSS Roundup: ceiling to one decimal place."""
    return math.ceil(value * 10) / 10


def calculate(vector: str) -> dict:
    """Calculate CVSS 3.1 base score from a vector string.

    Args:
        vector: CVSS 3.1 vector string, with or without the ``CVSS:3.1/`` prefix.
                Example: ``CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H``

    Returns:
        Dict with keys: score (float), severity (str), vector (str),
        iss (float), impact (float), exploitability (float).

    Raises:
        CVSSParseError: If the vector is malformed or contains unknown metric values.
    """
    # Strip prefix
    normalized = vector.strip()
    if normalized.upper().startswith("CVSS:"):
        normalized = normalized.split("/", 1)[1]

    if not _VECTOR_RE.match("AV:" + normalized.split("AV:", 1)[-1]):
        # Re-run full match with prefix stripped
        pass

    try:
        parts: dict[str, str] = {}
        for segment in normalized.split("/"):
            k, v = segment.split(":", 1)
            parts[k.upper()] = v.upper()
    except ValueError as exc:
        raise CVSSParseError(f"Malformed vector segment: {vector}") from exc

    required = {"AV", "AC", "PR", "UI", "S", "C", "I", "A"}
    missing = required - parts.keys()
    if missing:
        raise CVSSParseError(f"Missing metrics in vector: {missing}")

    scope = parts["S"]  # "U" or "C"

    try:
        av = _AV[parts["AV"]]
        ac = _AC[parts["AC"]]
        pr = (_PR_CHANGED if scope == "C" else _PR_UNCHANGED)[parts["PR"]]
        ui = _UI[parts["UI"]]
        c = _CIA[parts["C"]]
        i = _CIA[parts["I"]]
        a = _CIA[parts["A"]]
    except KeyError as exc:
        raise CVSSParseError(f"Unknown metric value: {exc}") from exc

    # Impact Sub-Score (ISS)
    iss = 1 - (1 - c) * (1 - i) * (1 - a)

    # Impact
    if scope == "U":
        impact = 6.42 * iss
    else:
        impact = 7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)

    # Exploitability
    exploitability = 8.22 * av * ac * pr * ui

    # Base Score
    if impact <= 0:
        score = 0.0
    elif scope == "U":
        score = _roundup(min(impact + exploitability, 10.0))
    else:
        score = _roundup(min(1.08 * (impact + exploitability), 10.0))

    severity = _score_to_severity(score)

    return {
        "score": score,
        "severity": severity,
        "vector": f"CVSS:3.1/{normalized}",
        "iss": round(iss, 4),
        "impact": round(impact, 4),
        "exploitability": round(exploitability, 4),
    }


def _score_to_severity(score: float) -> str:
    if score == 0.0:
        return "none"
    if score < 4.0:
        return "low"
    if score < 7.0:
        return "medium"
    if score < 9.0:
        return "high"
    return "critical"


def severity_from_score(score: float | None) -> str:
    """Convert a numeric CVSS score to a severity label."""
    if score is None:
        return "info"
    return _score_to_severity(score)
