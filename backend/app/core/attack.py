"""MITRE ATT&CK technique tagging for findings."""
from __future__ import annotations

# Keyword -> list[technique_id] mapping (ATT&CK Enterprise)
_KEYWORD_MAP: list[tuple[str, list[str]]] = [
    # Injection / exploitation
    ("sql injection", ["T1190"]),
    ("sqli", ["T1190"]),
    ("xss", ["T1059.007"]),
    ("cross-site scripting", ["T1059.007"]),
    ("cross site scripting", ["T1059.007"]),
    ("ssrf", ["T1190"]),
    ("server-side request forgery", ["T1190"]),
    ("rce", ["T1190", "T1059"]),
    ("remote code execution", ["T1190", "T1059"]),
    ("command injection", ["T1059"]),
    ("code injection", ["T1190"]),
    ("template injection", ["T1190"]),
    ("ssti", ["T1190"]),
    ("xxe", ["T1190"]),
    ("xml external entity", ["T1190"]),
    ("deserialization", ["T1190"]),
    # File access
    ("directory traversal", ["T1083"]),
    ("path traversal", ["T1083"]),
    ("lfi", ["T1083"]),
    ("local file inclusion", ["T1083"]),
    ("rfi", ["T1190"]),
    ("remote file inclusion", ["T1190"]),
    ("file disclosure", ["T1083"]),
    ("directory listing", ["T1083"]),
    ("backup file", ["T1083"]),
    # Credentials / accounts
    ("default credentials", ["T1078.001"]),
    ("default password", ["T1078.001"]),
    ("weak credentials", ["T1078"]),
    ("brute force", ["T1110"]),
    ("credential", ["T1078"]),
    ("exposed admin", ["T1078"]),
    ("admin panel", ["T1078"]),
    # TLS / cryptography
    ("weak ssl", ["T1600"]),
    ("weak tls", ["T1600"]),
    ("ssl", ["T1600"]),
    ("heartbleed", ["T1119", "T1600"]),
    ("robot attack", ["T1600"]),
    ("rc4", ["T1600"]),
    ("certificate expired", ["T1600"]),
    ("certificate invalid", ["T1552.004"]),
    ("self-signed", ["T1552.004"]),
    # Information disclosure
    ("information disclosure", ["T1082", "T1083"]),
    ("server version", ["T1082"]),
    ("software version", ["T1082"]),
    ("banner", ["T1082"]),
    ("stack trace", ["T1082"]),
    ("error message", ["T1082"]),
    ("debug", ["T1082"]),
    # Network
    ("open port", ["T1046"]),
    ("snmp", ["T1046"]),
    ("network scan", ["T1046"]),
    # SMB / Windows
    ("smb", ["T1021.002"]),
    ("null session", ["T1021.002"]),
    ("netbios", ["T1135"]),
    ("share", ["T1135"]),
    # LDAP / Active Directory
    ("ldap", ["T1087.002", "T1018"]),
    ("active directory", ["T1087.002"]),
    ("kerberoast", ["T1558.003"]),
    ("asreproast", ["T1558.004"]),
    ("pass the hash", ["T1550.002"]),
    # Web session / browser
    ("csrf", ["T1185"]),
    ("cross-site request forgery", ["T1185"]),
    ("open redirect", ["T1566.002"]),
    ("clickjacking", ["T1185"]),
    ("cors", ["T1185"]),
    ("session fixation", ["T1185"]),
    ("cookie", ["T1539"]),
    # Subdomain / infrastructure
    ("subdomain takeover", ["T1584.001"]),
    ("dns hijacking", ["T1584.001"]),
    # Cloud
    ("s3 bucket", ["T1530"]),
    ("storage bucket", ["T1530"]),
    ("iam", ["T1078.004"]),
    ("cloud metadata", ["T1552.005"]),
    ("imds", ["T1552.005"]),
    # Generic CVE
    ("cve-", ["T1190"]),
    ("vulnerability", ["T1190"]),
    ("misconfiguration", ["T1190"]),
]


def tag_finding(title: str, description: str = "", tool: str = "") -> list[str]:
    """Return ATT&CK technique IDs relevant to a finding.

    Args:
        title: Finding title.
        description: Finding description (optional, increases recall).
        tool: Tool that discovered the finding (optional).

    Returns:
        Deduplicated list of ATT&CK Enterprise technique IDs.
    """
    haystack = f"{title} {description} {tool}".lower()
    techniques: list[str] = []

    for keyword, ids in _KEYWORD_MAP:
        if keyword in haystack:
            for tid in ids:
                if tid not in techniques:
                    techniques.append(tid)

    return techniques


def technique_url(technique_id: str) -> str:
    """Return the MITRE ATT&CK URL for a technique ID."""
    # T1190 -> https://attack.mitre.org/techniques/T1190/
    # T1059.007 -> https://attack.mitre.org/techniques/T1059/007/
    parts = technique_id.split(".")
    if len(parts) == 2:
        return f"https://attack.mitre.org/techniques/{parts[0]}/{parts[1]}/"
    return f"https://attack.mitre.org/techniques/{parts[0]}/"
