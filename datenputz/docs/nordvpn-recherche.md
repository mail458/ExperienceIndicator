# NordVPN – Recherche (Stand: 23.10.2026)

## Überblick

NordVPN ist ein kommerzieller VPN-Dienst der Nord Security (Litauen/Panama). Zur selben Gruppe gehören Surfshark und damit auch Incogni. Inzwischen ist NordVPN mehr als ein VPN, nämlich ein Sicherheitspaket mit mehreren Tarifstufen.

## Funktionen

| Bereich | Funktion | Kurzbeschreibung |
|---|---|---|
| VPN | **NordLynx** | eigenes Protokoll auf Basis von WireGuard (daneben OpenVPN, NordWhisper) |
| | **Post-Quanten-Verschlüsselung** | hybrides ML-KEM (NIST-Standard) in NordLynx; seit 2024 unter Linux, seit 2025 auf allen Plattformen, muss von Hand eingeschaltet werden |
| | **Kill Switch** | trennt den Internetzugang, sobald das VPN abbricht |
| | **Split Tunneling** | ausgewählte Apps/Adressen am VPN vorbei |
| | **Meshnet** | verschlüsselte Direktverbindungen zwischen eigenen Geräten (laut Drittquellen bis zu 60 Geräte) |
| | Double VPN, Onion over VPN, Obfuscated Server, Dedicated IP | Spezialserver im Netz des Anbieters |
| | AES-256, geprüfte No-Logs-Politik | laut Anbieter unabhängig auditiert |
| Bedrohungsschutz | **Threat Protection Pro** | blockiert Phishing- und Malware-Domains, Werbung und Tracker, prüft Downloads auf Malware, warnt vor Betrug, entfernt Tracking-Parameter aus URLs („URL cleaning“); ab Tarif Plus, voller Umfang nur unter Windows und macOS |
| | Threat Protection Lite | DNS-basierte Variante, die nur bei aktivem VPN wirkt |
| | **Link Checker, File Checker, Scam Checker** | kostenlose Online-Werkzeuge; der Scam Checker prüft Texte, E-Mails und Nachrichten mit bis zu fünf Adressen, Links oder Telefonnummern |
| | Call Protection | warnt vor Betrugsanrufen (Android; zuerst USA, dann Europa) |
| Identität | **Dark Web Monitor** | überwacht Hacker-Marktplätze auf Zugangsdaten zur eigenen E-Mail-Adresse und schlägt bei Funden Alarm; ab Tarif Plus |
| | Identitätsschutz, Cyber-Versicherung, Kreditüberwachung | nur in den Top-Tarifen, überwiegend für die USA |
| Paket | NordPass, NordLocker, Incogni | Passwortmanager (ab Plus), 1 TB verschlüsselter Cloudspeicher, Datenentfernung (in den Top-Tarifen) |

## Tarife (Stand 2026, Angaben schwanken je nach Quelle)

Basic, dann Plus (mit Threat Protection Pro, NordPass und Dark Web Monitor), dann Complete/Ultimate (mit 1 TB Cloudspeicher), dann Prime/Ultra (mit Identitätsschutz und Incogni). Im 2-Jahres-Abo kostet Basic etwa 3 $ im Monat, die Top-Stufe etwa 6,30–6,70 $. Die Verlängerung ist deutlich teurer.

## Was Datenputz davon nachbaut

| NordVPN | Datenputz | Umsetzung |
|---|---|---|
| NordLynx (WireGuard) | `vpn` | eigener WireGuard-Server (VPS, Heimserver): Schlüssel, Server- und Gerätekonfigurationen, Installationsskript |
| Post-Quanten-Verschlüsselung | `vpn` | Pre-Shared Key je Gerät: eine symmetrische Zusatzschicht, die laut WireGuard-Whitepaper gegen künftige Quantenangriffe schützt (ein anderer Ansatz als ML-KEM) |
| Kill Switch | `vpn add <gerät>` | Firewallregeln aus der wg-quick-Dokumentation (Linux), Hinweis für die WireGuard-Apps |
| Split Tunneling | `vpn add <gerät> --split 192.168.0.0/16` | nach Netzen/Adressen; berechnete AllowedIPs |
| Meshnet | `vpn add <gerät> --mesh` | Geräte erreichen sich gegenseitig über den eigenen Server |
| Threat Protection | `shield` | DNS-Filter mit rund 1 Mio. Domains (HaGeZi Multi PRO + Threat Intelligence Feeds + Phishing.Database), Upstream verschlüsselt per DNS-over-HTTPS (Quad9), eigene Erlauben-/Sperrlisten, Export für Pi-hole/AdGuard/hosts |
| Threat Protection für alle Geräte | `vpn` + `shield` | Der Filter läuft auf dem VPN-Server als DNS für alle VPN-Geräte |
| URL cleaning | `clean-url`, `link` | entfernt utm_*, fbclid, gclid und rund 40 weitere Tracking-Parameter |
| Link Checker | `link` | Sperrlisten plus Merkmale: Marken-Nachahmungen (paypa1, amazon-sicherheit, dhl-zustellung), Punycode, IP-Adressen, riskante Endungen, Kurzlinks, „@“-Tricks |
| Scam Checker | `scam` | Muster typischer Maschen (Kontosperrung, Paketgebühr, „Hallo Mama“, Gutscheinkarten, TAN-Abfrage, Fernwartung) plus Prüfung aller enthaltenen Links |
| File Checker | `file` | Tarnung erkennen (doppelte Endung, Programm mit Dokument-Endung, Schreibrichtungs-Trick), SHA-256, optional Abgleich mit MalwareBazaar |
| Dark Web Monitor | `breach email` | Have-I-Been-Pwned-API, meldet nur neue Funde, optional per Mail; für den täglichen Lauf per Cron |
| Passwort-Leckprüfung (NordPass) | `breach password`, `password --check` | k-Anonymität: Nur 5 Hash-Zeichen verlassen den Rechner |
| Passwortgenerator (NordPass) | `password` | kryptografisch sicher (`secrets`) |
| VPN-/Leck-Test | `check` | Tunnel aktiv? Öffentliche IP und Standort, IPv6-Leck, DNS-Leck |
| Incogni (in den Top-Tarifen) | Hauptfunktion von Datenputz | siehe [incogni-recherche.md](incogni-recherche.md) |

### Bewusst nicht nachgebaut

- **Servernetz in vielen Ländern, Double VPN, Onion, Obfuscation, Dedicated IP:** Dafür braucht man eine Serverinfrastruktur. Datenputz nutzt stattdessen *deinen* Server. Wer mehrere Standorte will, richtet mehrere Server ein (`--home` je Server).
- **Echtzeit-Virenscan, Browser-Integration, Call Protection:** Das erfordert systemnahe Komponenten oder Apps auf dem Gerät und ist für ein Python-Werkzeug nicht sinnvoll.
- **Verschlüsselter Cloudspeicher (NordLocker):** Die Python-Standardbibliothek hat keine AES-Verschlüsselung. Dafür gibt es bessere fertige Werkzeuge (z. B. Cryptomator).

## Quellen

- [TechRadar: 6 tips and tricks to get the most out of NordVPN](https://www.techradar.com/vpn/vpn-services/6-tips-and-tricks-to-get-the-most-out-of-nordvpn)
- [TechRadar: NordVPN review](https://www.techradar.com/au/news/techradar-aussie-deals-get-30-off-our-favourite-vpn-for-netflix)
- [TechRadar: Post-quantum encryption is not the end](https://www.techradar.com/vpn/vpn-privacy-security/post-quantum-encryption-is-not-the-end-nordvpn-aims-for-world-first-security-milestones-in-2026)
- [TechRadar: How NordVPN changed in 2025](https://www.techradar.com/vpn/vpn-services/beyond-vpn-protection-how-nordvpn-changed-in-2025-and-whats-in-store-for-2026)
- [TechRadar: Threat Protection Pro is now even better](https://www.techradar.com/pro/nordvpn-threat-protection-pro-is-now-even-better-at-keeping-you-safe)
- [TechRadar: NordVPN's free scam checker](https://techradar.com/vpn/vpn-services/nordvpns-new-tool-helps-you-spot-online-scams-and-its-free-for-everyone)
- [Tom's Guide: NordVPN price and plans 2026](https://www.tomsguide.com/computing/vpns/nordvpn-price-plans)
- [Tom's Guide: post-quantum encryption](https://www.tomsguide.com/computing/vpns/nordvpn-introduces-post-quantum-encryption-for-future-proofed-privacy)
- [Tom's Guide: NordVPN scam checker](https://www.tomsguide.com/computing/vpns/nordvpn-launches-a-new-scam-checker-to-help-you-spot-phishing-and-fraud-and-its-completely-free-to-use)
- [NordVPN: Threat Protection Pro – scam and fraud alerts](https://nordvpn.com/features/threat-protection/scam-and-fraud-alert/)
- [NordVPN: Threat Protection review page](https://nordvpn.com/review/threat-protection)
- [NordVPN Blog: Post-quantum cryptography](https://nordvpn.com/blog/post-quantum-cryptography/)
- [NordVPN (DE)](https://nordvpn.com/de/nordvpn-site/)
- [GameStar: NordVPN-Funktionen](https://www.gamestar.de/artikel/sicheres-schnelles-internet-nordvpn-black-friday-angebot,3423182.html)
- [grey.co: NordVPN subscription pricing 2026](https://grey.co/blog/nordvpn-subscription-pricing)
- [security.org: NordVPN pricing](https://www.security.org/vpn/nordvpn)
- [FileHorse: NordVPN (Meshnet)](https://www.filehorse.com/download-nordvpn/)
- [WireGuard-Whitepaper (Pre-Shared Key, Post-Quanten-Resistenz)](https://www.wireguard.com/papers/wireguard.pdf)
- [Have I Been Pwned API v3](https://haveibeenpwned.com/API/v3)
- [HaGeZi DNS-Blocklists](https://github.com/hagezi/dns-blocklists)
