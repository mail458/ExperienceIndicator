"""Eigenes VPN auf WireGuard-Basis (NordLynx ist ebenfalls WireGuard).

Statt fremder Server nutzt du einen eigenen (VPS, Heimserver, Router). Das
Modul erzeugt Schlüssel und Konfigurationen für Server und Geräte:

* Vollständiger Tunnel mit Kill Switch (kein Datenverkehr am VPN vorbei)
* Split Tunneling (bestimmte Netze/Adressen am Tunnel vorbei)
* Meshnet (Geräte erreichen sich gegenseitig über den Tunnel)
* Pre-Shared Key je Gerät: zusätzliche symmetrische Schicht, die laut
  WireGuard-Whitepaper gegen künftige Quantencomputer schützt
* DNS über den Datenputz-Filter auf dem Server (Bedrohungsschutz für alle Geräte)
"""
import base64
import ipaddress
import json
import secrets
import shutil
import socket
import subprocess

from . import store as S

# --- X25519 (RFC 7748) -----------------------------------------------------
# Reine Python-Umsetzung für die einmalige, lokale Schlüsselerzeugung. Ist
# das WireGuard-Werkzeug `wg` installiert, wird stattdessen dieses genutzt.
_P = 2 ** 255 - 19
_A24 = 121665


def _x25519(k, u):
    k = bytearray(k)
    k[0] &= 248
    k[31] &= 127
    k[31] |= 64
    k = int.from_bytes(k, "little")
    u = bytearray(u)
    u[31] &= 127
    x1 = int.from_bytes(u, "little") % _P
    x2, z2, x3, z3, swap = 1, 0, x1, 1, 0
    for t in reversed(range(255)):
        kt = (k >> t) & 1
        swap ^= kt
        if swap:
            x2, x3, z2, z3 = x3, x2, z3, z2
        swap = kt
        a, b = (x2 + z2) % _P, (x2 - z2) % _P
        aa, bb = a * a % _P, b * b % _P
        e = (aa - bb) % _P
        c, d = (x3 + z3) % _P, (x3 - z3) % _P
        da, cb = d * a % _P, c * b % _P
        x3 = (da + cb) ** 2 % _P
        z3 = x1 * (da - cb) ** 2 % _P
        x2 = aa * bb % _P
        z2 = e * (aa + _A24 * e) % _P
    if swap:
        x2, z2 = x3, z3
    return (x2 * pow(z2, _P - 2, _P) % _P).to_bytes(32, "little")


def public_key(private_b64):
    if shutil.which("wg"):
        return subprocess.run(["wg", "pubkey"], input=private_b64.encode(), capture_output=True,
                              check=True).stdout.decode().strip()
    base = (9).to_bytes(32, "little")
    return base64.b64encode(_x25519(base64.b64decode(private_b64), base)).decode()


def private_key():
    if shutil.which("wg"):
        return subprocess.run(["wg", "genkey"], capture_output=True, check=True).stdout.decode().strip()
    k = bytearray(secrets.token_bytes(32))
    k[0] &= 248
    k[31] = (k[31] & 127) | 64
    return base64.b64encode(bytes(k)).decode()


def preshared_key():
    return base64.b64encode(secrets.token_bytes(32)).decode()


# --- Zustand ---------------------------------------------------------------
def folder():
    d = S.home() / "vpn"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load():
    p = folder() / "state.json"
    return json.loads(p.read_text()) if p.exists() else None


def save(state):
    p = folder() / "state.json"
    p.write_text(json.dumps(state, indent=1))
    p.chmod(0o600)


def init(endpoint, port=51820, subnet="10.66.0.0/24", subnet6="fd66:6d70::/64", dns=None, shield=True):
    net4, net6 = ipaddress.ip_network(subnet), ipaddress.ip_network(subnet6)
    priv = private_key()
    state = {
        "server": {
            "endpoint": endpoint, "port": port, "subnet": str(net4), "subnet6": str(net6),
            "address": str(net4[1]), "address6": str(net6[1]),
            "private": priv, "public": public_key(priv),
            "shield": shield,
            "dns": dns or (str(net4[1]) if shield else "9.9.9.9, 149.112.112.112"),
        },
        "peers": [],
    }
    save(state)
    return state


def add_peer(state, name, mode="full", exclude=None, killswitch=True):
    if any(p["name"] == name for p in state["peers"]):
        raise ValueError(f"Gerät '{name}' gibt es schon")
    srv = state["server"]
    net4, net6 = ipaddress.ip_network(srv["subnet"]), ipaddress.ip_network(srv["subnet6"])
    used = {srv["address"]} | {p["address"] for p in state["peers"]}
    host = next(h for h in net4.hosts() if str(h) not in used)
    idx = int(host) - int(net4.network_address)
    priv = private_key()
    peer = {
        "name": name, "mode": mode, "exclude": exclude or [], "killswitch": killswitch and mode == "full",
        "address": str(host), "address6": str(net6[idx]),
        "private": priv, "public": public_key(priv), "psk": preshared_key(),
    }
    state["peers"].append(peer)
    save(state)
    return peer


def remove_peer(state, name):
    before = len(state["peers"])
    state["peers"] = [p for p in state["peers"] if p["name"] != name]
    save(state)
    return before != len(state["peers"])


# --- Konfigurationen -------------------------------------------------------
KILLSWITCH_UP = ("iptables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT"
                 " && ip6tables -I OUTPUT ! -o %i -m mark ! --mark $(wg show %i fwmark) -m addrtype ! --dst-type LOCAL -j REJECT")
KILLSWITCH_DOWN = KILLSWITCH_UP.replace("-I OUTPUT", "-D OUTPUT")


def _endpoint_ip(endpoint):
    try:
        return ipaddress.ip_address(endpoint)
    except ValueError:
        try:
            return ipaddress.ip_address(socket.gethostbyname(endpoint))
        except OSError:
            return None


def allowed_ips(state, peer):
    srv = state["server"]
    if peer["mode"] == "mesh":  # nur Geräte im VPN, Internet weiter direkt
        return [srv["subnet"], srv["subnet6"]]
    if peer["mode"] == "split":
        nets = {4: [ipaddress.ip_network("0.0.0.0/0")], 6: [ipaddress.ip_network("::/0")]}
        excl = [ipaddress.ip_network(e, strict=False) for e in peer["exclude"]]
        ep = _endpoint_ip(srv["endpoint"])
        if ep:  # Verbindung zum Server selbst muss am Tunnel vorbei
            excl.append(ipaddress.ip_network(ep))
        for e in excl:
            out = []
            for n in nets[e.version]:
                out.extend(n.address_exclude(e) if e.subnet_of(n) else [n] if not n.subnet_of(e) else [])
            nets[e.version] = out
        # Das VPN-Netz selbst (DNS-Filter, andere Geräte) bleibt immer im Tunnel
        nets[4].append(ipaddress.ip_network(srv["subnet"]))
        nets[6].append(ipaddress.ip_network(srv["subnet6"]))
        return [str(n) for n in ipaddress.collapse_addresses(nets[4])] + \
               [str(n) for n in ipaddress.collapse_addresses(nets[6])]
    return ["0.0.0.0/0", "::/0"]


def server_conf(state):
    srv = state["server"]
    wan = "$(ip -o -4 route show to default | awk '{print $5; exit}')"
    up = [
        "sysctl -w net.ipv4.ip_forward=1", "sysctl -w net.ipv6.conf.all.forwarding=1",
        f"iptables -t nat -A POSTROUTING -s {srv['subnet']} -o {wan} -j MASQUERADE",
        f"ip6tables -t nat -A POSTROUTING -s {srv['subnet6']} -o {wan} -j MASQUERADE",
        "iptables -A FORWARD -i %i -j ACCEPT", "iptables -A FORWARD -o %i -j ACCEPT",
        "ip6tables -A FORWARD -i %i -j ACCEPT", "ip6tables -A FORWARD -o %i -j ACCEPT",
    ]
    down = [c.replace(" -A ", " -D ") for c in up[2:]]
    lines = [
        "# Datenputz VPN – Server (wg-quick)",
        "[Interface]",
        f"Address = {srv['address']}/{ipaddress.ip_network(srv['subnet']).prefixlen}, "
        f"{srv['address6']}/{ipaddress.ip_network(srv['subnet6']).prefixlen}",
        f"ListenPort = {srv['port']}",
        f"PrivateKey = {srv['private']}",
        f"PostUp = {'; '.join(up)}",
        f"PostDown = {'; '.join(down)}",
    ]
    for p in state["peers"]:
        lines += ["", f"[Peer]", f"# {p['name']} ({p['mode']})", f"PublicKey = {p['public']}",
                  f"PresharedKey = {p['psk']}", f"AllowedIPs = {p['address']}/32, {p['address6']}/128"]
    return "\n".join(lines) + "\n"


def client_conf(state, peer):
    srv = state["server"]
    lines = [
        f"# Datenputz VPN – Gerät „{peer['name']}“ ({peer['mode']})",
        "[Interface]",
        f"PrivateKey = {peer['private']}",
        f"Address = {peer['address']}/32, {peer['address6']}/128",
    ]
    if peer["mode"] != "mesh":
        lines.append(f"DNS = {srv['dns']}")
    if peer.get("killswitch"):
        lines += ["# Kill Switch (Linux/wg-quick): blockiert jeden Verkehr außerhalb des Tunnels.",
                  "# Windows/macOS/Android/iOS: im WireGuard-Client „Untunneled Traffic blockieren“ bzw.",
                  "# „Immer aktives VPN“ einschalten.",
                  f"PostUp = {KILLSWITCH_UP}", f"PreDown = {KILLSWITCH_DOWN}"]
    host = srv["endpoint"]
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    lines += ["", "[Peer]", f"PublicKey = {srv['public']}", f"PresharedKey = {peer['psk']}",
              f"Endpoint = {host}:{srv['port']}", f"AllowedIPs = {', '.join(allowed_ips(state, peer))}",
              "PersistentKeepalive = 25"]
    return "\n".join(lines) + "\n"


INSTALL = """#!/bin/sh
# Datenputz VPN – Server einrichten (Debian/Ubuntu, als root ausführen)
set -e
apt-get update
apt-get install -y wireguard iptables python3
install -m 600 wg0.conf /etc/wireguard/wg0.conf
systemctl enable --now wg-quick@wg0
{shield}
echo "Fertig. UDP-Port {port} in der Firewall des Anbieters freigeben."
"""

SHIELD_UNIT = """[Unit]
Description=Datenputz DNS-Filter für VPN-Geräte
After=wg-quick@wg0.service network-online.target
Requires=wg-quick@wg0.service

[Service]
Environment=DATENPUTZ_HOME=/var/lib/datenputz
WorkingDirectory=/opt/datenputz
ExecStartPre=/usr/bin/python3 -m datenputz shield update
ExecStart=/usr/bin/python3 -m datenputz shield serve --listen {addr} --port 53
Restart=on-failure
DynamicUser=yes
StateDirectory=datenputz
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
"""


def export(state, out=None):
    out = out or folder() / "export"
    out.mkdir(parents=True, exist_ok=True)
    files = []

    def write(name, text, mode=0o600):
        p = out / name
        p.write_text(text, encoding="utf-8")
        p.chmod(mode)
        files.append(p)

    write("wg0.conf", server_conf(state))
    srv = state["server"]
    shield_cmd = ""
    if srv.get("shield"):
        write("datenputz-dns.service", SHIELD_UNIT.format(addr=srv["address"]), 0o644)
        shield_cmd = ("# DNS-Filter: Datenputz nach /opt/datenputz kopieren, dann:\n"
                      "install -m 644 datenputz-dns.service /etc/systemd/system/\n"
                      "systemctl daemon-reload && systemctl enable --now datenputz-dns")
    write("install-server.sh", INSTALL.format(shield=shield_cmd, port=srv["port"]), 0o700)
    for p in state["peers"]:
        write(f"{p['name']}.conf", client_conf(state, p))
    return files
