"""Verbindungs-Check: Ist das VPN aktiv, welche IP sieht die Welt, gibt es DNS-/IPv6-Lecks?"""
import ipaddress
import json
import platform
import re
import subprocess
from pathlib import Path

from . import net

TUNNEL_PREFIXES = ("wg", "tun", "tap", "nordlynx", "utun", "ppp", "proton", "mullvad", "ipsec", "tailscale")


def tunnels():
    names = []
    sysnet = Path("/sys/class/net")
    if sysnet.exists():
        names = [p.name for p in sysnet.iterdir()]
    elif platform.system() == "Darwin":
        try:
            names = subprocess.run(["ifconfig", "-l"], capture_output=True, text=True).stdout.split()
        except OSError:
            names = []
    return sorted(n for n in names if n.lower().startswith(TUNNEL_PREFIXES))


def resolvers():
    servers = []
    try:
        for line in Path("/etc/resolv.conf").read_text().splitlines():
            m = re.match(r"\s*nameserver\s+(\S+)", line)
            if m:
                servers.append(m.group(1))
    except OSError:
        pass
    if servers == ["127.0.0.53"]:  # systemd-resolved: echte Upstreams erfragen
        try:
            out = subprocess.run(["resolvectl", "dns"], capture_output=True, text=True, timeout=5).stdout
            servers = sorted(set(re.findall(r"(\d+\.\d+\.\d+\.\d+|[0-9a-f:]{3,})(?=\s|$)", out))) or servers
        except (OSError, subprocess.SubprocessError):
            pass
    return servers


def _json(url):
    try:
        return json.loads(net.fetch(url, timeout=8)[1])
    except Exception:
        return None


def public_ips():
    v4 = (_json("https://api.ipify.org?format=json") or {}).get("ip")
    v6 = (_json("https://api6.ipify.org?format=json") or {}).get("ip")
    info = {}
    for ip in filter(None, {v4, v6}):
        d = _json(f"https://ipinfo.io/{ip}/json") or {}
        info[ip] = {k: d.get(k) for k in ("city", "country", "org")}
    return v4, v6, info


def run(expect_vpn=False, vpn_dns=None):
    """Gibt Liste von (ampel, text) zurück: ampel ∈ ok/warn/bad/info."""
    out = []
    tun = tunnels()
    v4, v6, info = public_ips()
    if tun:
        out.append(("ok", f"Tunnel aktiv: {', '.join(tun)}"))
    else:
        out.append(("bad" if expect_vpn else "info", "Kein VPN-Tunnel aktiv"))
    for ip in filter(None, (v4, v6)):
        i = info.get(ip, {})
        out.append(("info", f"Öffentliche IP {ip} – {i.get('city') or '?'}, {i.get('country') or '?'} ({i.get('org') or '?'})"))
    if not v4 and not v6:
        out.append(("warn", "Öffentliche IP nicht ermittelbar (offline oder blockiert)"))
    if v4 and v6 and tun:
        o4, o6 = (info.get(v4) or {}).get("org"), (info.get(v6) or {}).get("org")
        if o4 and o6 and o4 != o6:
            out.append(("bad", f"Mögliches IPv6-Leck: IPv4 über {o4}, IPv6 über {o6}"))
        else:
            out.append(("ok", "IPv4 und IPv6 nehmen denselben Weg"))
    dns = resolvers()
    if dns:
        out.append(("info", f"DNS-Server: {', '.join(dns)}"))
        if tun:
            private_lan = [d for d in dns if _is_lan(d) and not (vpn_dns and d in vpn_dns)]
            if vpn_dns and all(d in vpn_dns for d in dns):
                out.append(("ok", "DNS läuft über den VPN-Server"))
            elif private_lan:
                out.append(("warn", f"Mögliches DNS-Leck: Router/Heimnetz-DNS {', '.join(private_lan)} trotz VPN"))
    return out


def _is_lan(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return ip.is_private and not ip.is_loopback
