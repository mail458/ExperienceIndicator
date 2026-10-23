"""Brieftexte: Löschung (Art. 17/21 DSGVO), Auskunft (Art. 15), CCPA, Erinnerung, Beschwerde."""
from datetime import timedelta

DEADLINE_DAYS = {"gdpr": 30, "ccpa": 45}  # Art. 12 Abs. 3 DSGVO: ein Monat; CCPA: 45 Tage
GRACE_DAYS = 14                            # Nachfrist nach der Erinnerung

LABELS = {
    "de": {"name": "Name", "aliases": "Weitere/frühere Namen", "address": "Anschrift",
           "prev": "Frühere Anschriften", "email": "E-Mail", "phone": "Telefon", "birthdate": "Geburtsdatum"},
    "en": {"name": "Name", "aliases": "Other/former names", "address": "Address",
           "prev": "Previous addresses", "email": "Email", "phone": "Phone", "birthdate": "Date of birth"},
}


def language(profile, broker):
    if broker.get("language") in ("de", "en"):
        return broker["language"]
    countries = set(broker.get("countries") or [])
    if countries & {"de", "at", "ch"} and profile.get("language", "de") == "de":
        return "de"
    if countries == {"all"} or not countries:
        return profile.get("language", "de")
    return "en"


def fmt_date(dt, lang):
    return dt.strftime("%d.%m.%Y") if lang == "de" else dt.strftime("%Y-%m-%d")


def identity_block(profile, broker, lang):
    """Nur die Daten, die zur Identifikation nötig sind (Datenminimierung).

    Telefon und Geburtsdatum werden nur mitgeschickt, wenn der Händler sie
    verlangt oder das Profil sie ausdrücklich freigibt (`share`).
    """
    L = LABELS[lang]
    want = set(broker.get("required", [])) | set(profile.get("share", []))
    lines = [f"{L['name']}: {profile['name']}"]
    if profile.get("aliases"):
        lines.append(f"{L['aliases']}: {', '.join(profile['aliases'])}")
    addrs = profile.get("addresses") or []
    if addrs:
        lines.append(f"{L['address']}: {addrs[0].replace(chr(10), ', ')}")
    if len(addrs) > 1:
        lines.append(f"{L['prev']}: " + "; ".join(a.replace("\n", ", ") for a in addrs[1:]))
    if profile.get("emails"):
        lines.append(f"{L['email']}: {', '.join(profile['emails'])}")
    if profile.get("phones") and want & {"phone", "phones"}:
        lines.append(f"{L['phone']}: {', '.join(profile['phones'])}")
    if profile.get("birthdate") and want & {"birthdate", "birthday"}:
        lines.append(f"{L['birthdate']}: {profile['birthdate']}")
    return "\n".join(lines)


def _behalf(profile, lang):
    rep = profile.get("on_behalf_of_by")
    if not rep:
        return ""
    if lang == "de":
        return (f"Ich, {rep}, stelle diesen Antrag im Namen und mit Vollmacht der betroffenen Person "
                f"{profile['name']}. Eine Vollmacht kann ich auf Anforderung vorlegen.\n\n")
    return (f"I, {rep}, submit this request on behalf of and authorised by the data subject "
            f"{profile['name']}. A signed authorisation is available on request.\n\n")


def _urls(urls, lang):
    if not urls:
        return ""
    head = "Dies betrifft insbesondere folgende Seiten:" if lang == "de" else \
        "This concerns in particular the following pages:"
    return head + "\n" + "\n".join(f"  - {u}" for u in urls) + "\n\n"


def _sign(profile):
    return profile.get("on_behalf_of_by") or profile["name"]


def due_date(sent_at, law):
    return sent_at + timedelta(days=DEADLINE_DAYS[law])


# --------------------------------------------------------------------------
def erasure(profile, broker, lang, sent_at, urls=None, round_=1):
    due = fmt_date(due_date(sent_at, "gdpr"), lang)
    ident = identity_block(profile, broker, lang)
    if lang == "de":
        again = ("Ich habe Ihnen bereits früher einen Löschantrag gestellt. Da Händler Daten erfahrungsgemäß "
                 "erneut erheben, wiederhole ich den Antrag hiermit vorsorglich.\n\n") if round_ > 1 else ""
        subject = f"Antrag auf Löschung (Art. 17 DSGVO) und Widerspruch (Art. 21 DSGVO) – {profile['name']}"
        body = f"""Sehr geehrte Damen und Herren,

{_behalf(profile, lang)}{again}hiermit widerspreche ich gemäß Art. 21 Abs. 2 und 3 DSGVO der Verarbeitung meiner personenbezogenen Daten zum Zwecke der Direktwerbung einschließlich Profiling sowie vorsorglich gemäß Art. 21 Abs. 1 DSGVO jeder Verarbeitung auf Grundlage von Art. 6 Abs. 1 lit. e oder f DSGVO. Etwaige Einwilligungen widerrufe ich gemäß Art. 7 Abs. 3 DSGVO.

Zugleich verlange ich gemäß Art. 17 Abs. 1 DSGVO die unverzügliche Löschung sämtlicher mich betreffender personenbezogener Daten.

{_urls(urls, lang)}Bitte
  1. teilen Sie die Löschung gemäß Art. 19 DSGVO allen Empfängern mit, denen Sie meine Daten offengelegt haben, und nennen Sie mir diese Empfänger;
  2. teilen Sie mir gemäß Art. 15 Abs. 1 lit. g DSGVO mit, aus welcher Quelle Sie meine Daten erhalten haben;
  3. schränken Sie die Verarbeitung gemäß Art. 18 DSGVO auf eine Werbesperrliste ein, falls Sie Daten benötigen, um mich künftig von Werbung auszunehmen;
  4. bestätigen Sie mir die Löschung – oder teilen Sie mir mit, dass Sie keine Daten über mich verarbeiten.

Zur Identifikation:
{ident}

Diese Angaben dienen ausschließlich der Identifikation und der Bearbeitung dieses Antrags. Einer anderweitigen Verwendung widerspreche ich.

Gemäß Art. 12 Abs. 3 DSGVO haben Sie meinen Antrag unverzüglich, spätestens innerhalb eines Monats zu beantworten, also bis zum {due}. Andernfalls werde ich mich an die zuständige Datenschutzaufsichtsbehörde wenden.

Mit freundlichen Grüßen
{_sign(profile)}
"""
    else:
        again = ("I have previously requested erasure. As data is frequently re-collected, I hereby repeat my "
                 "request as a precaution.\n\n") if round_ > 1 else ""
        subject = f"Erasure request (Art. 17 GDPR) and objection (Art. 21 GDPR) – {profile['name']}"
        body = f"""Dear Sir or Madam,

{_behalf(profile, lang)}{again}Pursuant to Art. 21(2) and (3) GDPR I object to the processing of my personal data for direct marketing purposes, including profiling, and, as a precaution, pursuant to Art. 21(1) GDPR to any processing based on Art. 6(1)(e) or (f) GDPR. I withdraw any consent pursuant to Art. 7(3) GDPR.

At the same time I request, pursuant to Art. 17(1) GDPR, the erasure without undue delay of all personal data concerning me.

{_urls(urls, lang)}Please
  1. communicate the erasure to every recipient to whom my data has been disclosed (Art. 19 GDPR) and tell me who they are;
  2. inform me of the source from which you obtained my data (Art. 15(1)(g) GDPR);
  3. if you need data to exclude me from future marketing, restrict processing to a suppression list only (Art. 18 GDPR);
  4. confirm the erasure – or confirm that you do not process any data about me.

For identification:
{ident}

This information is provided solely to identify me and handle this request; I object to any other use.

Under Art. 12(3) GDPR you must respond without undue delay and at the latest within one month, i.e. by {due}. Otherwise I will lodge a complaint with the competent supervisory authority.

Kind regards
{_sign(profile)}
"""
    return subject, body


def access(profile, broker, lang, sent_at, urls=None, round_=1):
    due = fmt_date(due_date(sent_at, "gdpr"), lang)
    ident = identity_block(profile, broker, lang)
    if lang == "de":
        subject = f"Auskunftsersuchen nach Art. 15 DSGVO – {profile['name']}"
        body = f"""Sehr geehrte Damen und Herren,

{_behalf(profile, lang)}gemäß Art. 15 DSGVO bitte ich um Auskunft, ob Sie mich betreffende personenbezogene Daten verarbeiten. Falls ja, verlange ich
  1. eine Kopie dieser Daten (Art. 15 Abs. 3 DSGVO), einschließlich aller zu meiner Person gespeicherten oder berechneten Score- bzw. Wahrscheinlichkeitswerte;
  2. die Verarbeitungszwecke, die Kategorien der Daten und die geplante Speicherdauer;
  3. die Empfänger, denen die Daten offengelegt wurden, insbesondere in den letzten zwölf Monaten;
  4. die Herkunft der Daten (Art. 15 Abs. 1 lit. g DSGVO);
  5. aussagekräftige Informationen über die involvierte Logik einer automatisierten Entscheidungsfindung (Art. 15 Abs. 1 lit. h DSGVO).

Sollten unrichtige Daten gespeichert sein, verlange ich deren Berichtigung (Art. 16 DSGVO); unzulässig gespeicherte Daten sind zu löschen (Art. 17 DSGVO). Der Verarbeitung meiner Daten zu Werbezwecken widerspreche ich (Art. 21 Abs. 2 DSGVO).

Zur Identifikation:
{ident}

Bitte beantworten Sie meine Anfrage gemäß Art. 12 Abs. 3 DSGVO bis spätestens {due}. Die Auskunft ist nach Art. 12 Abs. 5 DSGVO unentgeltlich.

Mit freundlichen Grüßen
{_sign(profile)}
"""
    else:
        subject = f"Subject access request (Art. 15 GDPR) – {profile['name']}"
        body = f"""Dear Sir or Madam,

{_behalf(profile, lang)}pursuant to Art. 15 GDPR please confirm whether you process personal data concerning me. If so, I request
  1. a copy of the data (Art. 15(3) GDPR), including any scores or probability values stored or calculated about me;
  2. the purposes, categories of data and retention period;
  3. the recipients to whom the data was disclosed;
  4. the source of the data (Art. 15(1)(g) GDPR);
  5. meaningful information about the logic involved in any automated decision-making (Art. 15(1)(h) GDPR).

Inaccurate data must be rectified (Art. 16 GDPR) and unlawfully stored data erased (Art. 17 GDPR). I object to processing for marketing purposes (Art. 21(2) GDPR).

For identification:
{ident}

Please respond by {due} at the latest (Art. 12(3) GDPR). The information must be provided free of charge (Art. 12(5) GDPR).

Kind regards
{_sign(profile)}
"""
    return subject, body


def ccpa_delete(profile, broker, lang, sent_at, urls=None, round_=1):
    due = fmt_date(due_date(sent_at, "ccpa"), "en")
    ident = identity_block(profile, broker, "en")
    subject = f"Request to delete and to opt out of sale/sharing of personal information – {profile['name']}"
    body = f"""Dear Privacy Team,

{_behalf(profile, 'en')}under the California Consumer Privacy Act as amended by the CPRA (Cal. Civ. Code §§ 1798.105, 1798.120) and comparable state privacy laws, I request that you

  1. delete all personal information you hold about me and direct your service providers and contractors to do the same;
  2. stop selling or sharing my personal information and add me to your suppression/opt-out list;
  3. remove any public listing or profile about me from your website(s).

{_urls(urls, 'en')}For identification:
{ident}

This information may only be used to process this request. Please confirm completion within 45 days, i.e. by {due}.

Sincerely
{_sign(profile)}
"""
    return subject, body


KINDS = {"erasure": erasure, "access": access, "ccpa_delete": ccpa_delete}


def render(kind, profile, broker, sent_at, urls=None, round_=1):
    lang = "en" if kind == "ccpa_delete" else language(profile, broker)
    return KINDS[kind](profile, broker, lang, sent_at, urls=urls, round_=round_)


def reminder(profile, broker, kind, first_sent, now_):
    lang = "en" if kind == "ccpa_delete" else language(profile, broker)
    grace = fmt_date(now_ + timedelta(days=GRACE_DAYS), lang)
    first = fmt_date(first_sent, lang)
    if lang == "de":
        subject = f"Erinnerung: Mein Antrag vom {first} – Frist abgelaufen – {profile['name']}"
        body = f"""Sehr geehrte Damen und Herren,

am {first} habe ich Ihnen einen Antrag nach der DSGVO gestellt (siehe unten zitierte Nachricht). Die gesetzliche Frist von einem Monat (Art. 12 Abs. 3 DSGVO) ist verstrichen, ohne dass ich eine abschließende Antwort erhalten habe.

Ich setze Ihnen hiermit eine letzte Frist bis zum {grace}. Sollte ich bis dahin keine Antwort erhalten, werde ich Beschwerde bei der zuständigen Datenschutzaufsichtsbehörde (Art. 77 DSGVO) einlegen.

Mit freundlichen Grüßen
{_sign(profile)}
"""
    else:
        law = "45 days (CCPA)" if kind == "ccpa_delete" else "one month (Art. 12(3) GDPR)"
        subject = f"Reminder: my request of {first} – deadline passed – {profile['name']}"
        body = f"""Dear Sir or Madam,

on {first} I submitted a data protection request to you (quoted below). The statutory deadline of {law} has passed without a conclusive response.

I am giving you a final deadline of {grace}. If I do not hear from you by then, I will file a complaint with the competent authority.

Kind regards
{_sign(profile)}
"""
    return subject, body


def complaint(profile, broker, kind, first_sent, reminded_at, authority, lang="de"):
    first = fmt_date(first_sent, lang)
    rem = fmt_date(reminded_at, lang) if reminded_at else "–"
    addr = (broker.get("address") or "").replace("\n", ", ")
    contact = broker.get("email") or broker.get("webform") or broker.get("web") or ""
    to = authority["name"] if authority else ("[zuständige Aufsichtsbehörde]" if lang == "de" else "[competent authority]")
    if lang == "de":
        return f"""An: {to}
{(authority or {}).get('email') or ''}

Beschwerde nach Art. 77 DSGVO

Beschwerdeführer/in: {profile['name']}, {(profile.get('addresses') or [''])[0].replace(chr(10), ', ')}, {', '.join(profile.get('emails', []))}
Verantwortlicher:   {broker['name']}, {addr} ({contact})

Sachverhalt:
Am {first} habe ich den Verantwortlichen per {'E-Mail' if broker.get('email') else 'Formular/Brief'} aufgefordert, meine personenbezogenen Daten zu {'beauskunften (Art. 15 DSGVO)' if kind == 'access' else 'löschen (Art. 17 DSGVO) und ihrer Verarbeitung zu Werbezwecken widersprochen (Art. 21 DSGVO)'}.
Am {rem} habe ich unter Setzung einer Nachfrist erinnert. Eine abschließende Antwort ist bis heute nicht erfolgt. Damit verstößt der Verantwortliche gegen Art. 12 Abs. 3 DSGVO sowie gegen {'Art. 15' if kind == 'access' else 'Art. 17 und Art. 21'} DSGVO.

Ich bitte Sie, den Sachverhalt zu prüfen und den Verantwortlichen zur Erfüllung meines Antrags anzuhalten. Kopien meiner Schreiben füge ich bei.

Mit freundlichen Grüßen
{_sign(profile)}
"""
    return f"""To: {to}
{(authority or {}).get('email') or ''}

Complaint under Art. 77 GDPR

Complainant: {profile['name']}, {(profile.get('addresses') or [''])[0].replace(chr(10), ', ')}, {', '.join(profile.get('emails', []))}
Controller:  {broker['name']}, {addr} ({contact})

On {first} I asked the controller to {'provide access to (Art. 15 GDPR)' if kind == 'access' else 'erase (Art. 17 GDPR)'} my personal data. On {rem} I sent a reminder with a final deadline. No conclusive answer has been received, in breach of Art. 12(3) GDPR.

I ask you to investigate and to order the controller to comply. Copies of my correspondence are attached.

Kind regards
{_sign(profile)}
"""


def id_rebuttal(profile, broker, lang="de"):
    """Antwort, wenn ein Händler pauschal eine Ausweiskopie verlangt (Art. 12 Abs. 6 DSGVO)."""
    if lang == "de":
        return f"""Sehr geehrte Damen und Herren,

Sie verlangen für die Bearbeitung meines Antrags eine Kopie meines Ausweises. Nach Art. 12 Abs. 6 DSGVO dürfen Sie zusätzliche Informationen zur Identität nur anfordern, wenn begründete Zweifel an meiner Identität bestehen. Solche Zweifel haben Sie nicht dargelegt.

Ich habe Ihnen bereits die Angaben übermittelt, unter denen Sie meine Daten gespeichert haben (Name, Anschrift, E-Mail-Adresse). Eine Ausweiskopie enthält dagegen zahlreiche Daten, die Sie für die Bearbeitung nicht benötigen; ihre Anforderung widerspricht dem Grundsatz der Datenminimierung (Art. 5 Abs. 1 lit. c DSGVO).

Ich bitte Sie daher, meinen Antrag ohne weitere Nachweise zu bearbeiten. Sollten Sie dennoch begründete Zweifel haben, nennen Sie mir diese bitte konkret; ich kann mich dann z. B. durch eine Antwort von der bei Ihnen hinterlegten E-Mail-Adresse ausweisen. Die gesetzliche Frist läuft weiter.

Mit freundlichen Grüßen
{profile.get('on_behalf_of_by') or profile['name']}
"""
    return f"""Dear Sir or Madam,

you have asked for a copy of my ID document. Under Art. 12(6) GDPR you may request additional information only where you have reasonable doubts concerning my identity. You have not stated any such doubts.

I have already provided the data under which you hold my records (name, address, email address). An ID copy contains a great deal of data you do not need, contrary to the principle of data minimisation (Art. 5(1)(c) GDPR).

Please process my request without further documents. If you nonetheless have reasonable doubts, please state them specifically; I can, for example, confirm my identity by replying from the email address you hold on file. The statutory deadline continues to run.

Kind regards
{profile.get('on_behalf_of_by') or profile['name']}
"""
