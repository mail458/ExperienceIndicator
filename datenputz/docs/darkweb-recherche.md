# Dark-Web-Recherche – Quellen, Methoden, Grenzen (Stand: 23.10.2026)

## Bedrohungslage in Kürze

| Art des Funds | Was passiert ist | Gefahr |
|---|---|---|
| **Datenleck (Breach)** | Ein Dienst wurde gehackt, seine Kundendaten kursieren | je nach Datenart: Phishing bis Kontoübernahme |
| **Paste** | Daten wurden öffentlich gepostet (Pastebin u. ä.), oft mit Passwörtern | hoch |
| **Combolist / Credential Stuffing** | Paare aus E-Mail und Passwort aus vielen Leaks gesammelt | hoch bei wiederverwendeten Passwörtern |
| **Infostealer / Stealer Logs** | Schadsoftware auf *deinem* Gerät hat gespeicherte Passwörter und Cookies gestohlen | **kritisch**: aktuell, oft mit Sitzungs-Cookies, die die Zwei-Faktor-Anmeldung umgehen |
| Spam-Liste | Adresse steht in Verteilerlisten, kein Einbruch | gering |

Daraus folgt: Die wichtigste Frage ist nicht nur „Ist meine Adresse in einem Leak?“, sondern auch: **Welches Passwort ist betroffen, und war ein Gerät infiziert?**

## Quellen, die Datenputz nutzt

| Quelle | Inhalt | Zugang | Was Datenputz verwendet |
|---|---|---|---|
| Have I Been Pwned | Leaks (`breachedaccount`), Pastes (`pasteaccount`), Stealer Logs (`stealerlogsbyemail`, `stealerlogsbyemaildomain`), Domain-Suche (`breacheddomain`), Tarifstatus (`subscription/status`), Leak-Verzeichnis (`breaches`, frei) | API-Schlüssel (Tarife Core/Pro/High RPM), Stealer Logs nur in höheren Tarifen | alles, mit Ratenlimit aus `Rpm` und Wartezeit nach `Retry-After` bei 429 |
| Pwned Passwords | über 1 Mrd. geleakte Passwörter | frei, k-Anonymität, `Add-Padding` | `breach password`, `breach vault`, `password --check` |
| XposedOrNot | offene Leak-Datenbank, Open Source | frei, ohne Schlüssel (2/s, 25/h, 100/Tag) | `/v1/check-email/{email}` |
| LeakCheck Public API | Leak-Quellen und Datenarten, *nie* die Daten selbst | frei, auch kommerziell | `api/public?check=` |
| Hudson Rock Cavalier | Infostealer-Infektionen (Datum, Betriebssystem, Virenschutz) | frei, inoffiziell genutzt (z. B. von theHarvester) | `osint-tools/search-by-email` |
| eigenes Postfach | Post an Dienst-Aliase von fremden Absendern | IMAP oder .eml | `alias scan` |

Handprüfungen, die sich bewusst nicht automatisieren lassen, weil das Ergebnis nur an die geprüfte Adresse geht: HPI Identity Leak Checker (rund 19 Mrd. Identitäten), Leak Checker der Uni Bonn (laut Vergleich über 55 Mrd.), Hudson Rock (Weboberfläche, auch Benutzernamen), Mozilla Monitor, Google „Ergebnisse über dich“. Google hat seinen Dark Web Report im Februar 2026 eingestellt.

## Methoden für maximale Abdeckung

1. **Alle Suchbegriffe:** aktuelle, alte und berufliche Adressen (`monitor_emails`), alle Aliase, eigene Domains.
2. **Alle Quellen:** `breach email --max`. Jede Drittquelle braucht einmalig deine Zustimmung, denn sie erfährt die geprüfte Adresse.
3. **Passwort-Audit statt Adress-Check:** `breach vault export.csv --shred` prüft *jedes* Passwort und findet mehrfach genutzte Passwörter, schwache Muster und Dienste mit Leak nach der letzten Passwortänderung.
4. **Ein Alias pro Dienst:** Leaks und Weitergaben lassen sich so einem Verursacher zuordnen. `alias request` stellt dann einen Lösch- und Auskunftsantrag, in dem nur der Alias genannt wird.
5. **Laufend statt einmalig:** täglich per Cron mit `--notify`, dazu einmal im Quartal die Handprüfungen (`breach manual`).
6. **Maßnahmen statt Listen:** Jeder Fund wird nach Datenart bewertet. `breach plan` bündelt alle Schritte, die dringendsten zuerst.

## Sicherheit und Recht

- **Keine Leak-Dateien selbst beschaffen.** Wer rechtswidrig erlangte Daten verschafft, um sich zu bereichern oder jemandem zu schaden, macht sich wegen Datenhehlerei strafbar (§ 202d StGB). Die Dateien enthalten außerdem Daten Dritter und sind oft mit Schadsoftware präpariert. Datenputz fragt deshalb nur seriöse Dienste ab, die Metadaten liefern.
- **Keine Passwörter an Dritte:** Passwörter verlassen den Rechner nur als 5 Zeichen eines SHA-1-Hashes, mit Padding gegen Verkehrsanalyse. Gespeichert und ausgegeben werden nie Passwörter.
- **Geheimnisse im Schlüsselbund:** API-Schlüssel und Mailpasswörter liegen im macOS-Schlüsselbund bzw. im Secret Service (GNOME Keyring/KWallet), sonst in `config.json` mit Rechten 600. Datenbank und Konfiguration sind nur für den Eigentümer lesbar.
- **Passwort-Export:** Er enthält alles im Klartext. Mit `--shred` wird er nach der Prüfung überschrieben und gelöscht. Auf SSDs ist das nicht garantiert, daher den Export am besten in einem verschlüsselten Ordner oder auf einer RAM-Disk erzeugen.
- **Grenzen:** Kein Dienst sieht „das ganze Darknet“. Geschlossene Foren und Telegram-Kanäle werden nur teilweise erfasst. Kein Fund heißt nicht „sicher“, ein Fund heißt aber immer: handeln.

## Quellen

- [HIBP API v3](https://haveibeenpwned.com/API/v3)
- [hibp-Client (Endpunkte, Typen, Fehlercodes)](https://github.com/wKovacs64/hibp/blob/main/API.md)
- [go-hibp](https://pkg.go.dev/github.com/wneessen/go-hibp)
- [HIBP Subscription API](https://apis.io/apis/have-i-been-pwned/have-i-been-pwned-subscription-api/)
- [HIBP Breaches OpenAPI](https://raw.githubusercontent.com/api-evangelist/have-i-been-pwned/refs/heads/main/openapi/have-i-been-pwned-breaches-api-openapi.yml)
- [XposedOrNot API](https://xposedornot.com/api_doc)
- [XposedOrNot-API (Quellcode)](https://github.com/XposedOrNot/XposedOrNot-API)
- [LeakCheck Public API](https://wiki.leakcheck.io/en/api/public)
- [leakcheck-api (Quellcode)](https://github.com/leakcheck/leakcheck-api)
- [Hudson Rock Docs](https://docs.hudsonrock.com/)
- [search-leaks (Hudson-Rock-Endpunkte)](https://github.com/haltman-io/search-leaks)
- [Hudson Rock (Wikipedia)](https://en.wikipedia.org/wiki/Hudson_Rock)
- [Leak Checker Uni Bonn](https://identeco.de/en/blog/german-alternative-hibp/)
- [Verbraucherzentrale NRW](https://www.verbraucherzentrale.nrw/wissen/digitale-welt/onlinedienste/so-finden-sie-heraus-ob-ihre-logindaten-gestohlen-wurden-92617)
- [heise: Google stellt Dark Web Report ein](https://heise.de/-11116682)
- [Malwarebytes](https://www.malwarebytes.com/blog/news/2025/12/google-is-discontinuing-its-dark-web-report-why-it-matters)
