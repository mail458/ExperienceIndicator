# Datenputz

Ein selbst betriebener Nachbau des Prinzips von [Incogni](docs/incogni-recherche.md): Datenputz schickt Lösch- und Widerspruchsanträge an Datenhändler, überwacht die gesetzlichen Fristen, erinnert, entwirft Beschwerden an die Datenschutzaufsicht und wiederholt die Anträge regelmäßig. Alles läuft lokal und über dein eigenes Postfach, es geht keine Vollmacht an einen Dritten.

- **479 Händler:** 458 EU-Adress- und Werbehändler, Auskunfteien und Inkassounternehmen aus der offenen Datenbank von [datenanfragen.de](https://github.com/datenanfragen/data) (CC0), dazu 21 US-Personensuchseiten
- **Rechtssichere Briefe** auf Deutsch und Englisch: Art. 17, 21, 19, 18 und 15 Abs. 1 lit. g DSGVO, für Auskunfteien Art. 15, für die USA CCPA/CPRA
- **Datenminimierung:** Telefon und Geburtsdatum werden nur mitgeschickt, wenn ein Händler sie verlangt
- **Fristen:** Erinnerung nach 30 (DSGVO) bzw. 45 Tagen (CCPA), nach weiteren 14 Tagen ein Beschwerdeentwurf nach Art. 77 DSGVO
- **Wiederholung** alle 60 Tage (Personensuchseiten) bzw. 90 Tage (übrige Händler); sie endet, sobald ein Händler eine dauerhafte Sperre bestätigt
- **Postfach-Auswertung** per IMAP: erkennt „gelöscht“, „keine Daten“, „Ausweis nötig“, „Sperrliste“ und Unzustellbares
- **Custom Removals** für beliebige Websites, **mehrere Profile** (Familie), **HTML-Dashboard**
- Nur die Python-Standardbibliothek (ab 3.9), keine Abhängigkeiten

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
- Händlerdaten: © datenanfragen.de e. V. und Mitwirkende, [CC0 1.0](https://github.com/datenanfragen/data/blob/master/LICENSE).
