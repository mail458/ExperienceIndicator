# Datenputz

Ein selbst betriebener Privatsphäre-Werkzeugkasten, der die Kernfunktionen von zwei kommerziellen Diensten nachbaut:

- **[Incogni](docs/incogni-recherche.md):** Lösch- und Widerspruchsanträge an Datenhändler senden, Fristen überwachen, erinnern, Beschwerden an die Datenschutzaufsicht entwerfen und die Anträge regelmäßig wiederholen.
- **[NordVPN](docs/nordvpn-recherche.md):** Dark-Web-Monitor, DNS-Bedrohungsschutz gegen Werbung, Tracker, Malware und Phishing, Link-, Betrugs- und Dateiprüfung, Verbindungs-Check und ein eigenes WireGuard-VPN mit Kill Switch, Split Tunneling und Meshnet.

Alles läuft lokal, über dein eigenes Postfach und deinen eigenen Server. Es geht keine Vollmacht an einen Dritten, und es gibt kein Abo. Nur die Python-Standardbibliothek (ab 3.9), keine Abhängigkeiten.

### Datenentfernung (wie Incogni)

- **479 Händler:** 458 EU-Adress- und Werbehändler, Auskunfteien und Inkassounternehmen aus der offenen Datenbank von [datenanfragen.de](https://github.com/datenanfragen/data) (CC0), dazu 21 US-Personensuchseiten
- **Rechtssichere Briefe** auf Deutsch und Englisch: Art. 17, 21, 19, 18 und 15 Abs. 1 lit. g DSGVO, für Auskunfteien Art. 15, für die USA CCPA/CPRA
- **Datenminimierung:** Telefon und Geburtsdatum werden nur mitgeschickt, wenn ein Händler sie verlangt
- **Fristen:** Erinnerung nach 30 (DSGVO) bzw. 45 Tagen (CCPA), nach weiteren 14 Tagen ein Beschwerdeentwurf nach Art. 77 DSGVO
- **Wiederholung** alle 60 Tage (Personensuchseiten) bzw. 90 Tage (übrige Händler); sie endet, sobald ein Händler eine dauerhafte Sperre bestätigt
- **Postfach-Auswertung** per IMAP: erkennt „gelöscht“, „keine Daten“, „Ausweis nötig“, „Sperrliste“ und Unzustellbares
- **Custom Removals** für beliebige Websites, **mehrere Profile** (Familie), **HTML-Dashboard**

### Sicherheit (wie NordVPN)

| Befehl | entspricht bei NordVPN | Was passiert |
|---|---|---|
| `breach email [--notify]` | Dark Web Monitor | prüft die E-Mail-Adressen aller Profile bei Have I Been Pwned und meldet nur neue Leaks (API-Schlüssel nötig) |
| `breach password` | NordPass-Leckprüfung | k-Anonymität: Nur 5 Zeichen des SHA-1-Hashes verlassen den Rechner |
| `shield update` / `shield serve` | Threat Protection | DNS-Filter mit rund 1 Mio. gesperrten Domains, Upstream verschlüsselt per DNS-over-HTTPS |
| `shield export --format …` | – | Sperrliste für hosts, Pi-hole/AdGuard, dnsmasq, Unbound |
| `clean-url` | URL cleaning | Tracking-Parameter (utm_*, fbclid, gclid …) entfernen |
| `link <URL>` | Link Checker | Sperrlisten plus Merkmale wie Marken-Nachahmung, Punycode, IP-Adressen, Kurzlinks |
| `scam [Text]` | Scam Checker | typische Maschen (Kontosperrung, Paketgebühr, „Hallo Mama“, TAN-Abfrage …) und alle enthaltenen Links |
| `file <Datei>` | File Checker | getarnte Programme erkennen, SHA-256, optional Abgleich mit MalwareBazaar |
| `vpn …` | NordLynx, Kill Switch, Split Tunneling, Meshnet | eigener WireGuard-Server mit Pre-Shared Key je Gerät (Post-Quanten-Schicht) und DNS-Filter für alle Geräte |
| `check [--expect-vpn]` | – | VPN aktiv? Öffentliche IP und Standort, IPv6- und DNS-Lecks |
| `password` | NordPass-Generator | starke Zufallspasswörter, optional mit Leckprüfung |

## Schnellstart

```bash
cd datenputz
python3 -m datenputz init            # Profil anlegen (Name, frühere Namen, Adressen, E-Mail)
python3 -m datenputz plan            # Anfragen an alle passenden Händler vorbereiten
python3 -m datenputz run             # VORSCHAU: Entwürfe unter ~/.datenputz/preview ansehen
python3 -m datenputz smtp            # Versand einrichten (Gmail/Outlook: App-Passwort)
python3 -m datenputz run --send      # echt versenden (Tageslimit, Pause zwischen den Mails)
python3 -m datenputz forms           # Webformulare/Briefe, die du selbst abschickst
python3 -m datenputz inbox --apply   # Antworten aus dem Postfach übernehmen
python3 -m datenputz report          # Dashboard: ~/.datenputz/report.html
```

Wer kein SMTP nutzen will, nimmt `run --outbox`. Dann landen die Mails als `.eml`-Dateien in `~/.datenputz/outbox` und lassen sich im Mailprogramm öffnen und abschicken.

### Täglich automatisch

```cron
# m h dom mon dow
17 8 * * *  cd /pfad/zu/datenputz && DATENPUTZ_SMTP_PASSWORD=… python3 -m datenputz inbox --apply && python3 -m datenputz run --send --yes && python3 -m datenputz report
43 7 * * *  cd /pfad/zu/datenputz && DATENPUTZ_SMTP_PASSWORD=… python3 -m datenputz breach email --notify
11 4 * * 1  cd /pfad/zu/datenputz && python3 -m datenputz shield update
```

`run` ist idempotent: Bei jedem Aufruf erledigt es genau das, was gerade fällig ist (neue Anfragen innerhalb des Tageslimits, Erinnerungen, Beschwerdeentwürfe, neue Runden).

## Befehle

| Befehl | Zweck |
|---|---|
| `init [--key k] [--from-json f] [--on-behalf-by "Dein Name"]` | Profil anlegen, auch für Familienmitglieder (nur mit Einwilligung) |
| `profiles` | Profile auflisten |
| `brokers [--country de] [--category ads] [--search x] [--public] [--count]` | Händlerverzeichnis durchsuchen |
| `authorities [--country de]` | Aufsichtsbehörden auflisten; Slug im Profil als `"authority"` eintragen |
| `plan [--profile k] [--category …] [--only id,id] [--public]` | Anfragen planen |
| `run [--send \| --outbox] [--yes]` | fällige Schritte ausführen, ohne Option nur als Vorschau |
| `status [--all] [--filter gesperrt]` | Fortschritt anzeigen |
| `show <ID>` | Details und Verlauf einer Anfrage |
| `mark <status> <ID…> [--note]` | Status setzen: `gesendet`, `gelöscht`, `keine-daten`, `gesperrt`, `abgelehnt`, `aktion`, `unzustellbar` |
| `custom <URL…> [--email privacy@…] [--name …]` | eigene Löschanfrage für eine beliebige Website |
| `inbox [--days 60] [--apply] [--eml-dir ordner]` | Antworten auswerten |
| `report [-o datei.html]` | Dashboard erzeugen |

## Sicherheitsfunktionen im Detail

### Dark-Web-Monitor

```bash
python3 -m datenputz breach email --key <HIBP-SCHLÜSSEL> --save-key   # einmalig; Schlüssel: haveibeenpwned.com/API/Key
python3 -m datenputz breach email --notify                            # täglich per Cron, neue Funde per Mail
python3 -m datenputz breach password                                  # Passwort prüfen, kostenlos
```

### Bedrohungsschutz (DNS-Filter)

```bash
python3 -m datenputz shield update                     # Listen laden (ca. 1 Mio. Domains); --only bedrohungen für reinen Malware-/Phishing-Schutz
python3 -m datenputz shield test doubleclick.net       # prüfen, ob eine Domain gesperrt ist
python3 -m datenputz shield serve                      # Filter auf 127.0.0.1:5353
sudo python3 -m datenputz shield serve --port 53       # als System-DNS (dann DNS auf 127.0.0.1 stellen)
python3 -m datenputz shield allow meine-bank.de        # Fehlalarm freigeben
python3 -m datenputz shield export --format domains -o liste.txt   # für Pi-hole/AdGuard Home
```

Quellen: [HaGeZi Multi PRO](https://github.com/hagezi/dns-blocklists) (Werbung/Tracker), HaGeZi Threat Intelligence Feeds (Malware/Phishing/Betrug) und [Phishing.Database](https://github.com/mitchellkrogza/Phishing.Database). Sie werden beim `update` geladen, nicht mitgeliefert. Upstream ist standardmäßig Quad9 per DoH (`--upstream udp:9.9.9.9` für klassisches DNS).

### Eigenes VPN

```bash
python3 -m datenputz vpn init --endpoint 203.0.113.10          # öffentliche IP oder Hostname deines Servers
python3 -m datenputz vpn add laptop                            # voller Tunnel + Kill Switch
python3 -m datenputz vpn add handy --split 192.168.0.0/16      # Heimnetz am Tunnel vorbei
python3 -m datenputz vpn add nas --mesh                        # nur Geräte untereinander (Meshnet)
python3 -m datenputz vpn export                                # ~/.datenputz/vpn/export/
python3 -m datenputz vpn show handy | qrencode -t ansiutf8     # QR-Code für die WireGuard-App
```

Den Export-Ordner auf den Server kopieren und dort `install-server.sh` als root ausführen. Für den DNS-Filter auf dem Server zusätzlich Datenputz nach `/opt/datenputz` kopieren; das Skript richtet dann den Dienst `datenputz-dns` ein. Danach `check --expect-vpn` auf dem Gerät ausführen.

Schlüssel: Ist `wg` installiert, wird es genutzt, sonst eine geprüfte Python-Umsetzung von X25519 (RFC 7748). Jedes Gerät bekommt zusätzlich einen Pre-Shared Key, eine symmetrische Schicht, die laut WireGuard-Whitepaper gegen künftige Quantencomputer schützt.

## Ablauf einer Anfrage

```
geplant ──run──► versendet ──30/45 Tage──► erinnert ──14 Tage──► Beschwerde (Entwurf)
   │                │
   │ Webformular/   ├─► gelöscht / keine Daten ──60/90 Tage──► neue Runde
   │ Brief          ├─► gesperrt (Sperrliste) → keine Wiederholung
   ▼                └─► abgelehnt / unzustellbar
Aktion nötig ──mark gesendet──► versendet
```

Auskunfteien (z. B. SCHUFA, CRIF, infoscore) und Inkassounternehmen bekommen standardmäßig eine Auskunft nach Art. 15 statt einer Löschung. Bei ihnen scheitert die Löschung meist am berechtigten Interesse; die Auskunft zeigt dagegen, welche Daten und Scores gespeichert sind, und lässt sich mit einer Berichtigung kombinieren.

## Dateien

Alles liegt in `~/.datenputz` (oder in `$DATENPUTZ_HOME` bzw. `--home`), mit den Rechten 700/600:

- `datenputz.db`: Profile, Anfragen, Verlauf (SQLite)
- `sent/`: Kopie jeder versendeten Mail als Nachweis
- `forms/`, `letters/`: fertige Texte zum Einfügen ins Formular bzw. zum Ausdrucken
- `complaints/`: Beschwerdeentwürfe an die Aufsichtsbehörde (werden nie automatisch verschickt)
- `custom_brokers.json`: eigene Händler
- `shield/`: Sperrlisten, eigene Erlauben-/Sperrlisten, Statistik
- `vpn/`: Schlüssel und Konfigurationen (`state.json` mit Rechten 600 – enthält private Schlüssel!)

## Händlerdaten aktualisieren

```bash
git clone --depth 1 https://github.com/datenanfragen/data.git /tmp/dadata
python3 scripts/build_brokers.py /tmp/dadata
```

Die US-Personensuchseiten in `datenputz/data/people_search.json` sind von Hand gepflegt. Ihre Opt-out-URLs bitte vor dem Absenden prüfen, die Seiten ändern sie oft.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Wichtige Hinweise

- **Nur für dich selbst oder mit Einwilligung.** Anfragen für andere Personen (Familie) brauchen deren Einverständnis, bei Kindern die Sorgeberechtigung.
- **Mailanbieter-Limits:** Standardmäßig gehen höchstens 40 Mails pro Tag raus, mit 20 Sekunden Pause dazwischen. So sperrt der Anbieter dein Konto nicht, und rund 400 Händler sind in etwa zehn Tagen abgearbeitet.
- Die Briefe sind sorgfältig formuliert, ersetzen aber keine Rechtsberatung. Beschwerdeentwürfe bitte vor dem Absenden prüfen.
- **VPN-Grenzen:** Datenputz ersetzt kein Servernetz in vielen Ländern. Double VPN, Onion over VPN und verschleierte Server gibt es nicht. Deine Anonymität hängt vom Anbieter deines Servers ab.
- **Link-, Betrugs- und Dateiprüfung** arbeiten mit Sperrlisten und Merkmalen. Sie sind eine Warnhilfe, kein Virenscanner.
- Händlerdaten: © datenanfragen.de e. V. und Mitwirkende, [CC0 1.0](https://github.com/datenanfragen/data/blob/master/LICENSE).
