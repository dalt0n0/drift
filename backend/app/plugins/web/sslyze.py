"""sslyze: TLS/SSL configuration analyser."""
from __future__ import annotations

import json

from app.plugins.base import BasePlugin
from app.plugins.manifest import PluginManifest
from app.plugins.tool_runner import ToolResult


class SslyzePlugin(BasePlugin):
    manifest = PluginManifest(
        name="sslyze",
        version="6.0.0",
        category="web",
        is_intrusive=False,
        binary="sslyze",
        inputs=["targets"],
        outputs=["findings"],
        dependencies=[],
        rate_limit=5,
        timeout_seconds=120,
        safe_mode_allowed=True,
    )

    def build_command(self, inputs: dict) -> list[str]:
        targets = inputs.get("targets", [])
        cmd = ["sslyze", "--json_out=-"]
        cmd.extend(targets)
        return cmd

    def parse_output(self, result: ToolResult, inputs: dict) -> dict:
        findings = []
        raw = result.stdout.strip()
        if not raw:
            return {"findings": [], "total": 0}

        try:
            data = json.loads(raw)
            for server_scan in data.get("server_scan_results", []):
                server = server_scan.get("server_location", {})
                hostname = server.get("hostname", "")
                port = server.get("port", 443)
                scan_result = server_scan.get("scan_result", {})

                # Certificate info
                cert_info = scan_result.get("certificate_info", {})
                if cert_info:
                    for deployment in cert_info.get("result", {}).get("certificate_deployments", []):
                        leaf = deployment.get("received_certificate_chain", [{}])[0]
                        findings.append({
                            "type": "certificate",
                            "host": f"{hostname}:{port}",
                            "subject": leaf.get("subject", {}).get("rfc4514_string", ""),
                            "not_after": leaf.get("not_valid_after", ""),
                            "not_before": leaf.get("not_valid_before", ""),
                            "issuer": leaf.get("issuer", {}).get("rfc4514_string", ""),
                            "verified": deployment.get("verified_certificate_chain") is not None,
                        })

                # Weak protocols
                for proto in ("ssl_2_0_cipher_suites", "ssl_3_0_cipher_suites",
                              "tls_1_0_cipher_suites", "tls_1_1_cipher_suites"):
                    proto_result = scan_result.get(proto, {})
                    accepted = proto_result.get("result", {}).get("accepted_cipher_suites", [])
                    if accepted:
                        findings.append({
                            "type": "weak_protocol",
                            "host": f"{hostname}:{port}",
                            "protocol": proto.replace("_cipher_suites", "").replace("_", "."),
                            "severity": "high",
                            "ciphers_count": len(accepted),
                        })

                # Vulnerabilities (heartbleed, robot, etc.)
                for vuln in ("heartbleed", "robot", "tls_compression", "tls_fallback_scsv",
                             "openssl_ccs_injection", "session_renegotiation"):
                    vuln_result = scan_result.get(vuln, {})
                    result_data = vuln_result.get("result", {})
                    if result_data.get("is_vulnerable_to_heartbleed") or \
                       result_data.get("robot_result") not in (None, "NOT_VULNERABLE_NO_ORACLE") or \
                       result_data.get("supports_compression") or \
                       result_data.get("is_vulnerable_to_ccs_injection") or \
                       result_data.get("is_vulnerable_to_client_renegotiation_dos"):
                        findings.append({
                            "type": "vulnerability",
                            "host": f"{hostname}:{port}",
                            "name": vuln,
                            "severity": "high",
                            "detail": str(result_data),
                        })

        except (json.JSONDecodeError, AttributeError, KeyError):
            pass

        return {"findings": findings, "total": len(findings)}
