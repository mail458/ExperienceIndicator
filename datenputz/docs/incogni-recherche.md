# Incogni – Recherche (Stand: 23.10.2026)

## Was ist Incogni?

Incogni ist ein kostenpflichtiger Dienst zum automatischen Entfernen persönlicher Daten, gegründet 2022 von Surfshark (gehört zur Nord-Security-Gruppe). Er schickt im Namen der Kundinnen und Kunden Lösch- und Opt-out-Anfragen an Datenhändler (Data Broker) und verfolgt sie nach.

## So funktioniert der Dienst

1. **Konto und Vollmacht:** Man gibt Name (auch mehrere bzw. frühere Nachnamen), Anschriften, E-Mail und Telefonnummer an und unterschreibt eine digitale Vollmacht. Mit ihr darf Incogni Anfragen im Namen der Person stellen.
2. **Händlerliste:** Incogni wählt die Händler aus seiner Datenbank. Die Angaben schwanken je nach Quelle, Stand 2026 sind es über 420 Händler. Unterschieden wird zwischen
   - **öffentlichen Händlern** (Personensuchseiten wie Spokeo oder Whitepages, die Profile offen anzeigen) und
   - **privaten Händlern** (Marketing- und Adresshändler, Risiko- und Finanzdaten, Recruiting), die Daten nur weiterverkaufen.
3. **Anfragen:** Jeder Händler bekommt die Anfrage über seinen eigenen Kanal (E-Mail, Webformular oder Post). Rechtsgrundlage ist je nach Wohnort die DSGVO (Art. 17 Löschung, Art. 21 Widerspruch), der britische UK GDPR, der kanadische PIPEDA oder US-Landesrecht (CCPA/CPRA).
4. **Nachfassen:** Antwortet ein Händler nicht, fragt Incogni erneut nach. Laut Tests kommen die ersten Bestätigungen nach etwa 30–45 Tagen, passend zu den gesetzlichen Fristen (DSGVO: ein Monat, CCPA: 45 Tage).
5. **Wiederkehrende Anfragen:** Händler sammeln Daten erneut ein. Incogni schickt deshalb die Anfragen spätestens alle **60 Tage (öffentliche Händler)** bzw. **90 Tage (private Händler)** erneut. Das gilt nicht, wenn die Person schon auf der Sperrliste (Suppression List) des Händlers steht. Deloitte hat diese Praxis in einem Bericht mit begrenzter Prüfsicherheit (Limited Assurance, Stichtag 18.07.2025) bestätigt.
6. **Dashboard:** Zeigt für jeden Händler den Stand (gesendet, in Bearbeitung, gelöscht), eine Einstufung, wie heikel die Daten des Händlers sind, und die Kategorie.
7. **Custom Removals** (nur im Tarif Unlimited): Man reicht Links zu beliebigen Websites mit eigenen Daten ein, und Incogni stellt dort Löschanträge. Genannt werden über 2.000 Domains.
8. **Rechtliche Durchsetzung:** Incogni hat zum Beispiel 2023 bei der niederländischen Datenschutzbehörde Beschwerde gegen GfK eingelegt, weil Löschanträge ignoriert wurden.

## Preise (Stand 2026, laut Testberichten)

| Tarif | jährlich | monatlich |
|---|---|---|
| Standard (1 Person) | ca. 7,99 $/Monat | ca. 15,98 $ |
| Unlimited (mit Custom Removals) | ca. 14,99 $/Monat | ca. 29,98 $ |
| Family (bis zu 5 Personen) | ca. 191,88 $/Jahr | – |
| Family Unlimited | ca. 275,88 $/Jahr | – |

Es gibt keine Gratisversion, aber eine 30-tägige Geld-zurück-Garantie.

## Grenzen und Kritik

- Bei häufigen Namen, Namenswechseln oder vielen früheren Adressen findet der automatische Abgleich nicht alle Einträge.
- Die Händlerliste ändert sich ständig. Manche Händler sind zeitweise nicht verfügbar, etwa während Compliance-Prüfungen.
- Google-Suchergebnisse, soziale Netzwerke und Behördenregister deckt Incogni nicht ab.
- Man gibt einem weiteren Unternehmen seine Daten und eine Vollmacht. Genau dieses Vertrauensproblem umgeht ein selbst betriebenes Werkzeug.

## Was Datenputz davon übernimmt

| Incogni | Datenputz |
|---|---|
| Datenbank mit über 420 Händlern | 458 EU-Händler (Daten von datenanfragen.de, CC0) und 21 US-Personensuchseiten |
| Anfragen in deinem Namen | Anfragen gehen direkt von deinem eigenen Postfach raus, keine Vollmacht an Dritte |
| Löschung und Widerspruch nach DSGVO/CCPA | Brief nach Art. 17 + 21 + 19 + 18 + 15 Abs. 1 lit. g, CCPA-Löschung und Opt-out, Art. 15 für Auskunfteien |
| Nachfassen | Erinnerung nach Fristablauf (30/45 Tage), danach Beschwerdeentwurf nach Art. 77 DSGVO |
| Wiederholung alle 60/90 Tage, Stopp bei Sperrliste | genauso (`RECUR_DAYS`, Status `suppressed` beendet die Wiederholung) |
| Dashboard | `report` erzeugt eine HTML-Übersicht |
| Custom Removals | `custom <URL>` |
| Familientarif | beliebig viele Profile, Pflichtfrage nach der Einwilligung |
| Antworten auswerten | `inbox` liest das Postfach per IMAP und ordnet Antworten automatisch ein |

## Quellen

- [Wikipedia: Incogni](https://en.wikipedia.org/wiki/Incogni)
- [Incogni-Blog: Deloitte Limited Assurance Report](https://blog.incogni.com/deloitte-independent-limited-assurance-report/)
- [security.org: Incogni Review and Pricing 2026](https://www.security.org/data-removal/incogni/)
- [TechRadar: Incogni review](https://www.techradar.com/reviews/incogni)
- [PCrisk: Incogni review](https://www.pcrisk.com/reviews/personal-data-removal-services/34637-incogni-review)
- [Fossbytes: Incogni Review 2026](https://fossbytes.com/incogni-review-2026/)
- [Cloudwards: Incogni Review](https://www.cloudwards.net/what-is-surfshark-incogni/)
- [PCWorld: Incogni review](https://www.pcworld.com/article/2958237/incogni-review.html)
- [Gizmodo: Incogni](https://gizmodo.com/best-data-removal-service/incogni)
- [Aura: Is Incogni worth it](https://www.aura.com/learn/is-incogni-worth-it)
- [vpnoverview: Incogni vs. GfK](https://vpnoverview.com/news/incogni-claims-gfk-group-is-ignoring-right-to-erasure-requests/)
- [Art. 17 DSGVO](https://gdpr-info.eu/art-17-gdpr/)
- [datenanfragen.de – offene Unternehmensdatenbank (CC0)](https://github.com/datenanfragen/data)
