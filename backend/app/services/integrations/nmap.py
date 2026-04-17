"""
Parse Nmap XML output (-oX) → list of host dicts.
"""
from lxml import etree


def parse_nmap_xml(content: bytes) -> list[dict]:
    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid Nmap XML: {e}")

    if root.tag != "nmaprun":
        raise ValueError("Not a valid Nmap XML file (expected <nmaprun> root)")

    hosts = []
    for host_el in root.findall("host"):
        # Only include hosts that are up
        status_el = host_el.find("status")
        if status_el is not None and status_el.get("state") != "up":
            continue

        # IP address
        ip = None
        hostname = None
        for addr in host_el.findall("address"):
            if addr.get("addrtype") in ("ipv4", "ipv6"):
                ip = addr.get("addr")
                break

        # Hostname
        hostnames_el = host_el.find("hostnames")
        if hostnames_el is not None:
            for hn in hostnames_el.findall("hostname"):
                if hn.get("type") in ("PTR", "user"):
                    hostname = hn.get("name")
                    break

        if not ip:
            continue

        # Open ports
        ports = []
        ports_el = host_el.find("ports")
        if ports_el is not None:
            for port_el in ports_el.findall("port"):
                state_el = port_el.find("state")
                if state_el is not None and state_el.get("state") == "open":
                    portid = port_el.get("portid")
                    if portid:
                        try:
                            ports.append(int(portid))
                        except ValueError:
                            pass

        hosts.append({
            "ip": ip,
            "hostname": hostname,
            "ports": ports,
        })

    return hosts
