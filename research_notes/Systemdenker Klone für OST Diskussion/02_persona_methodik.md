# Methodik: Treue KI-Personas historischer Denker und moderierte Multi-Persona-Panels (Stand Oktober 2026)

Hinweis zur Quellenlage: Recherche am 10.10.2026. Einige arXiv-Seiten waren per Fetch nicht erreichbar (DNS-Fehler). Deshalb stützen sich manche Angaben nur auf Abstracts und Suchsnippets; das ist jeweils vermerkt. Mit [älter] markierte Befunde stammen aus 2023/2024 und damit aus der Zeit von GPT-3/GPT-4 bzw. LLaMA-1.

---

## 1. Architekturen: Persona-Card im System-Prompt vs. RAG vs. Fine-Tuning vs. Hybrid

### Takeaway
Bisher gibt es keine kontrollierte Studie, die die drei Ansätze für einen einzelnen Philosophen direkt vergleicht. Die Befunde zeigen aber in eine klare Richtung. Fine-Tuning trifft Stil und Denkmuster am besten, war jedoch selbst bei DigiDan für Experten nur in 51 % der Fälle nicht von Dennett unterscheidbar. Reichhaltiges Primärmaterial im Kontext bzw. Gedächtnis plus Expertenzusammenfassungen trägt weit (Park et al. 2024). Für den Nutzer ist ein **Hybrid aus strukturierter Persona-Spezifikation im System-Prompt, zitierfähigem RAG über das Korpus und einer kuratierten Idiolekt-/Few-Shot-Sammlung** am praktikabelsten. Fine-Tuning lohnt sich nur optional für Stil und sollte immer mit RAG kombiniert werden.

### Cited Findings
- **DigiDan (Dennett) [älter, 2023]:** Die Autoren haben GPT-3 auf Werke Daniel Dennetts feinabgestimmt. Dem echten Dennett und dem Modell stellten sie je 10 Fragen. Vom Modell gab es pro Frage 4 Antworten, ohne Auswahl der besten („no cherry-picking“). Dennett-Experten (N=25) erkannten die echte Antwort in 51 % der Fälle. Die Zufallsrate lag bei 20 %, die Hypothese der Autoren bei 80 %. Bei 2 von 10 Fragen wählten Experten eine Modellantwort häufiger als Dennetts eigene. Leser philosophischer Blogs (N=302) schnitten ähnlich ab wie die Experten, Laien (N=98) lagen nahe am Zufall. — [Schwitzgebel/Schwitzgebel/Strasser, arXiv 2302.01339 / Mind & Language 2023](https://arxiv.org/abs/2302.01339v2); [Abstract UCR](https://faculty.ucr.edu/~eschwitz/SchwitzAbs/GPT3Dennett.htm)
- Laut Tech Xplore lief das Training in Stufen: zuerst auf Kant-Texten, dann auf Schwitzgebels Blog, schließlich **mit Dennetts Zustimmung** auf den meisten seiner Werke. Hinweis: Die korrekte Autorenschaft lautet Eric Schwitzgebel, David Schwitzgebel, Anna Strasser. „Crosby“ aus der Aufgabenstellung ist kein Autor dieses Papers. — [Tech Xplore 2023](https://techxplore.com/news/2023-02-large-language-philosophical.amp)
- **Character-LLM [älter, EMNLP 2023]:** „Experience Upload“. Die Autoren sammelten Lebenserfahrungen historischer Figuren (Beethoven, Cleopatra, Caesar), ließen sie von einem LLM zu Szenen ausbauen und trainierten damit LLaMA-7B per Supervised Fine-Tuning. „Protective experiences“, also weniger als 100 Szenen pro Figur, in denen die Figur Anachronistisches zurückweist, reduzieren Charakter-Halluzinationen. Ein Beispiel: Beethoven lehnt es ab, Python-Code zu schreiben. Andere Fähigkeiten leiden darunter laut den Autoren nicht. — [Shao et al., ACL Anthology 2023.emnlp-main.814](https://aclanthology.org/2023.emnlp-main.814); [GitHub](https://github.com/choosewhatulike/trainable-agents)
- **Generative Agent Simulations of 1,000 People [2024, v3 laut alphaXiv Juni 2026]:** Grundlage waren 2-stündige Interviews mit 1.052 Personen, geführt von einem sprachgesteuerten GPT-4-Interviewer. Die Transkripte kamen ins Agentengedächtnis. Zusätzlich verfassten LLMs „Expertenreflexionen“ über die Person aus Sicht eines Soziologen, Ökonomen usw. Die Agenten reproduzierten GSS-Antworten zu 85 % so genau, wie die Personen sich selbst nach zwei Wochen reproduzierten. Das ist ein **relativer** Wert. Interviewbasierte Agenten verringerten außerdem Verzerrungen gegenüber Agenten, die nur demografische Beschreibungen hatten. — [Park et al., arXiv 2411.10109](https://arxiv.org/abs/2411.10109v1); [Stanford HAI](https://hai.stanford.edu/news/ai-agents-simulate-1052-individuals-personalities-impressive-accuracy)
- Ein Survey zur Persona-Simulation (2025) hält fest: Prompt Engineering verfehlt oft feine Charakterzüge und dynamisches Verhalten, Fine-Tuning adressiert diese Grenzen. CharacterBot (ACL Findings 2025) trainiert ein Modell darauf, sowohl die sprachlichen Muster als auch die **Denkmuster** aus den Schriften einer Figur nachzubilden. Biografie oder Dialoge allein reichen nach Ansicht der Autoren nicht. — [arXiv 2502.12988](https://arxiv.org/pdf/2502.12988v3) (nur Snippet gesehen)
- Anthropic empfiehlt offiziell, Rolle und Persönlichkeit im System-Prompt zu definieren, mit detailliertem Hintergrund, Eigenheiten und typischen Szenarien samt erwarteten Antworten. In langen Gesprächen soll man die Antwort mit einem Charakter-Tag vorbefüllen (Prefill). — [Anthropic Docs „Keep Claude in character“](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/keep-claude-in-character)
- Ein Drittanbieter-Test mit 162 Personas und rund 2.500 Prompts fand keine messbare Qualitätsverbesserung durch Persona-Prompts bei Sachaufgaben. Das betrifft Leistung, nicht Charaktertreue, und die Quelle ist ein Blog, also schwach. — [MindStudio Blog](https://www.mindstudio.ai/blog/claude-code-prompting-mistakes-personas)
- Ein Underwood/Nelson/Wilkens-Preprint (via Sammel-Suchergebnis): Prompting mit Beispielen historischer Prosa erzeugt keinen konsistenten Periodenstil. Fine-Tuning täuscht automatische Bewerter, menschliche Bewerter erkennen den Unterschied aber weiterhin. — zitiert in [arXiv 2609.15468](https://arxiv.org/pdf/2609.15468) (nur Snippet)

### Inferences
- DigiDan zeigt die Obergrenze von reinem Fine-Tuning auf 2022er-Basismodellen: Plausibilität ja, Unterscheidbarkeit für Experten bleibt. Heutige Frontier-Modelle (Claude, GPT-5-Klasse) kennen Bertalanffy und andere Systemdenker bereits aus dem Pretraining. Der Hauptgewinn liegt deshalb in Präzision (richtige Begriffe, Datierung, Zitate) und in der Abwehr von „Wikipedia-Bertalanffy“-Klischees, weniger in Grundwissen.
- Empfohlene Architektur für den Nutzer (Claude API oder Projects):
  1. **Persona-Spezifikation** (Abschnitt 2) als System-Prompt, 3–8k Tokens, XML-strukturiert.
  2. **RAG über das Korpus** mit Chunk-Metadaten (Werk, Jahr, Seite, Werkphase, Sprache). Die Persona muss Kernaussagen mit Quelle belegen und `[belegt]`, `[abgeleitet]` und `[extrapoliert]` unterscheiden. Bei kleinem Korpus (<~500 Seiten Kernauszüge) reichen auch Claude Projects bzw. lange Kontexte mit Prompt Caching statt Vektor-DB.
  3. **Idiolekt-Bank:** 20–40 kurze Originalpassagen (paraphrasiert oder kurz zitiert, siehe Abschnitt 6) als Few-Shot-Stilanker.
  4. **Expertenreflexionen nach Park et al.:** LLM-generierte, vom Nutzer geprüfte Zusammenfassungen des Denkers aus der Perspektive „Wissenschaftshistoriker“, „Biologe“, „Kritiker“. Sie gehören ins Dossier und lassen sich auf die Quellenkritik des Nutzers aufsetzen.
  5. **Optional:** ein LoRA-Fine-Tune auf ein Open-Weight-Modell nur für Stil. Das ist rechtlich heikler (Abschnitt 6) und aufwendiger. Laut Character-LLM sind dann „protective scenes“ nötig.

### Gaps
- Keine Head-to-Head-Studie „RAG vs. Fine-Tuning vs. Prompt“ für Denker-Personas gefunden.
- RoleLLM (Wang et al. 2023, [arXiv 2310.00746](https://arxiv.org/abs/2310.00746)) und CharacterEval (Tu et al. 2024, [arXiv 2401.01275](https://arxiv.org/abs/2401.01275)) waren in dieser Sitzung nicht im Volltext abrufbar. Aus Vorwissen, nicht verifiziert: RoleLLM bietet ein Benchmark (RoleBench) mit rund 100 Rollen und „Context-Instruct“ zur Extraktion rollenspezifischen Wissens. CharacterEval ist ein chinesisches Benchmark mit vier Dimensionen (Gesprächsfähigkeit, Charakterkonsistenz, Rollenspiel-Attraktivität, Persönlichkeit) und einem eigenen Reward-Modell.

---

## 2. Bausteine einer Persona-Spezifikation

### Takeaway
Die Forschung bestätigt drei Dinge. Detail schlägt Schlagwort (Anthropic Docs, Park et al.). Persönlichkeits- und Emotionsinformationen verbessern die Rollentreue messbar (Anonymous-Setting-Studie 2026, EmoCharacter). Denkmuster sind wichtiger als Biografie (CharacterBot). Eine gute Spezifikation trennt deshalb **Wissen, Überzeugungen, Argumentationsweise, Stimme, Temperament und Regeln**.

### Cited Findings
- Eine Studie von 2026 zeigt, dass schon der Name einer Figur dem Modell implizite Hinweise gibt, die das tatsächliche Rollenspielvermögen überdecken. Wird die Persönlichkeit explizit eingebaut, steigt die Leistung durchgehend. — [arXiv 2603.03915](https://www.alphaxiv.org/abs/2603.03915.md) (nur Snippet)
- RPEval (2025) bewertet emotionales Verständnis, Entscheidungsverhalten, moralische Ausrichtung und In-Character-Konsistenz. Zur Konsistenz gehört auch, dass kein Wissen außerhalb des Rollenkontexts „leakt“. — [arXiv 2505.13157](https://arxiv.org/pdf/2505.13157v1)
- EmoCharacter (NAACL 2025): Gängige Rollenspielmethoden **senken** oft die emotionale Treue. Das Benchmark nutzt Single- und Multi-Turn-Dialoge, drei Settings und sechs Metriken. — [ACL Anthology 2025.naacl-long.316](https://preview.aclanthology.org/setup/2025.naacl-long.316)
- Anthropic rät zu Hintergrund, Persönlichkeit, spezifischen Eigenheiten und einer Liste typischer Szenarien mit erwarteten Antworten. — [Anthropic Docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/keep-claude-in-character)
- Park et al. zeigen, dass Rohtranskripte plus perspektivische Expertenzusammenfassungen besser abschneiden als demografische Kurzbeschreibungen. — [Stanford HAI](https://hai.stanford.edu/news/ai-agents-simulate-1052-individuals-personalities-impressive-accuracy)

### Inferences
Empfohlene Persona-Spezifikation (Vorlage, z. B. als XML-Blöcke):

1. `<identitaet>`: Name, Lebensdaten, **Wissensstichtag = Todesdatum** (Bertalanffy: 12.06.1972). Dazu der „Sprechzeitpunkt“ des Panels, z. B. „Sie sprechen als Bertalanffy des Jahres 1971“.
2. `<biografie_nach_phasen>`: Wien (theoretische Biologie, Wiener Kreis-Umfeld), NS-Zeit (Mitgliedschaft und Ambivalenz quellenkritisch, siehe 9.), Emigration (London, Kanada, USA), Gründung der Society for General Systems Research (1954), Spätwerk. Je Phase: Kernthesen, Bezugspersonen, Stimmungslage.
3. `<ueberzeugungen>`: Tabelle aus These, Konfidenz (hoch/mittel/niedrig), Phase bzw. Jahr der Entstehung, Belegstelle und ggf. „revidiert in …“. Konfidenzen und Datierung kommen direkt aus dem quellenkritischen Dossier.
4. `<argumentationsstil>`: typische Argumentformen (Analogie und Isomorphie zwischen Disziplinen, Abgrenzung gegen Mechanismus und Reduktionismus, historische Herleitung), Einwandmuster („Das ist Robotermodell des Menschen“), was ihn überzeugt und was nicht.
5. `<rhetorik_idiolekt>`: Lieblingsbegriffe, Satzlänge, Ironie, Mehrsprachigkeit (Deutsch/Englisch), 20–40 Originalpassagen als Stilanker, jeweils mit Fundstelle.
6. `<temperament>`: Empfindlichkeiten (z. B. Prioritätsstreitigkeiten mit Kybernetikern), Humor, Ungeduld, Pathos. Diese Marker sind nötig, weil gängige Methoden die emotionale Treue sonst senken.
7. `<beziehungen_rivalitaeten>`: Person, Art der Beziehung, Streitpunkt, typischer Tonfall (für Bertalanffy etwa Wiener, Ashby, Boulding, Rapoport, Weiss, Koestler/Alpbach).
8. `<blinde_flecken_problematisches>`: bekannte Schwächen und Ambivalenzen, die die Persona **nicht glätten** darf, und Regeln, wie sie damit umgeht.
9. `<wissensgrenzen_extrapolation>`: Regeln zu Anachronismus und Kennzeichnung (Abschnitt 3).
10. `<kritikhaltung>`: Anweisungen gegen Gefälligkeit (Abschnitt 3), z. B. „Ihre Aufgabe ist Kritik aus Ihrer Theorie heraus; Zustimmung nur mit Begründung und Belegstelle.“
11. `<ausgabeformat>`: Markierungen `[belegt: Werk, Jahr, S.]`, `[abgeleitet]`, `[extrapoliert]`, `[außerhalb meines Horizonts]`.
12. `<szenarien>`: 5–10 Musterdialoge (Anthropic-Empfehlung), darunter mindestens zwei Ablehnungs- bzw. Anachronismusszenen nach dem Vorbild der „protective scenes“.

### Gaps
- Keine Studie gefunden, die ermittelt, welche dieser Komponenten den größten Effekt hat (Ablation für Denker-Personas).

---

## 3. Anachronismus, Extrapolationskennzeichnung, Sycophancy und Persona-Drift

### Takeaway
Prompt-basierte „Wissensstichtage“ wirken nur bei direkten Fragen zu Späterem. Bei kausal verbundenem Späterwissen versagen sie. Ein Bertalanffy-Klon wird also unbemerkt Begriffe wie Autopoiesis, Komplexitätswissenschaft oder Netzwerktheorie „mitdenken“. Abhilfe schaffen explizite Anachronismus-Listen, Kennzeichnungspflicht und eine separate Prüfinstanz. Gefälligkeit (Sycophancy) ist ein dokumentiertes Modellmerkmal und verstärkt sich in Multi-Agenten-Settings.

### Cited Findings
- **EMNLP 2025, „Can Prompts Rewind Time for LLMs?“:** Simulierte Wissensstichtage per Prompt funktionieren, wenn direkt nach Späterem gefragt wird, scheitern aber, wenn das „vergessene“ Wissen nur kausal mit der Frage verbunden ist. — [ACL Anthology 2025.emnlp-main.1049](https://preview.aclanthology.org/setup/2025.emnlp-main.1049)
- **„Concept Incongruence: Time and Death in Role Playing“ (2025):** Getestet wurden 100 historische Figuren (gestorben 1890–1993) mit Fragen nach Amtsinhabern in Jahren rund um den Tod. Der Test misst, ob das Modell Wissen nach dem Tod vermeidet. — [arXiv 2505.14905](https://arxiv.org/pdf/2505.14905) (nur Snippet; Effektgrößen nicht gesehen)
- **Historisch begrenzte Modelle (2026):** Modelle, die nur auf Periodenkorpora trainiert wurden (TimeCapsuleLLM, GPT-1900, Talkie), umgehen das Problem, weil die zeitliche Grenze im Training liegt und nicht gespielt wird. — [arXiv 2609.15468](https://arxiv.org/pdf/2609.15468) (Snippet)
- Ein Vortrag auf dem AI Engineer World's Fair 2026 argumentiert, dass Persönlichkeitstreue, Präferenzoptimierung und Fine-Tuning anachronistisches Denken **verdecken** können. Das ist eine Talk-Zusammenfassung, nicht peer-reviewed. — [ai.engineer](https://ai.engineer/talks/the-miranda-hypothesis-how-hamilton-the-musical-poisoned-your-persona-evals)
- Anthropic „Persona Vectors“ (August 2025): Sycophancy, Halluzination usw. entsprechen messbaren Aktivierungsmustern. Damit lässt sich überwachen, ob sich ein Modell im Gespräch in Richtung eines Merkmals verschiebt (getestet an Qwen 2.5-7B, Llama-3.1-8B). — [The Decoder](https://the-decoder.com/persona-vectors-allow-anthropic-to-steer-language-model-behaviors-like-sycophancy-and-evil/); [PureAI](https://pureai.com/articles/2025/08/05/anthropic-develops-method-to-monitor-ai-personality-changes.aspx)
- „Assistant Axis“ (Lu et al., Januar 2026): Persona-Drift entsteht vor allem in Gesprächen mit Meta-Reflexion über das Modell und in **philosophischen Diskussionen**. Getestet wurden Open-Weight-Modelle (Gemma 2 27B, Qwen 3 32B, Llama 3.3 70B). — [hyper.ai Paper 2601.10387](https://hyper.ai/en/papers/2601.10387); [Implicator](https://www.implicator.ai/anthropic-finds-the-off-switch-for-ai-personality-drift/)
- Anthropic empfiehlt gegen Drift in langen Gesprächen, die Antwort mit einem Charakter-Tag vorzubefüllen. — [Anthropic Docs](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/keep-claude-in-character). Hinweis aus Vorwissen, nicht verifiziert: Bei neueren Claude-Modellen ist Prefill teils eingeschränkt. Vor dem Einsatz in der aktuellen API-Dokumentation prüfen.

### Inferences
Praktische Regeln:
- **Anachronismus-Protokoll:** Wird die Persona mit Post-1972-Ideen konfrontiert (Autopoiesis 1972/73, Chaos- und Komplexitätstheorie, Luhmanns Systemtheorie, das Modell des Nutzers), soll sie (a) erklären, dass ihr das unbekannt ist, (b) sich das Konzept vom Moderator in eigenen Begriffen erklären lassen, (c) aus ihren belegten Positionen heraus urteilen und die Antwort als `[extrapoliert]` mit Konfidenz markieren. Dieses „Erklär-mir-dann-urteile-ich“-Muster ist ehrlicher als vorgetäuschtes Nichtwissen. Gegen kausales Leaking hilft es aber nur teilweise.
- **Anachronismus-Blacklist** im System-Prompt: 30–50 Begriffe und Autoren nach 1972, die ohne Moderatoreneinführung nicht verwendet werden dürfen. Zusätzlich ein **Checker-Agent**, der jede Antwort auf diese Begriffe und auf nicht belegte Zitate scannt. Das ist billig und robust.
- **Anti-Sycophancy:**
  1. Im System-Prompt festlegen, dass die Persona Kritiker ist, nicht Berater. Etwa: „Bewerten Sie das Modell des Nutzers so, wie Sie 1969 ein Manuskript eines Konkurrenten in Alpbach bewertet hätten.“
  2. Für jede Kritik eine Belegstelle aus dem eigenen Werk verlangen.
  3. Das Modell des Nutzers **anonymisiert bzw. in dritter Person** vorlegen („Ein Autor schlägt vor …“) statt „mein Modell“. Das reduziert die Gefälligkeit gegenüber dem Gesprächspartner.
  4. Pflichtformat: „Drei stärkste Einwände – eine Zustimmung – offene Frage“.
  5. Gegenprobe: dieselbe Frage einmal mit „Ich finde das Modell schwach“ und einmal mit „Ich finde es brillant“ stellen. Ändert sich das Urteil, ist die Persona sycophantisch.
- Lange Sitzungen in kürzere, frisch initialisierte Runden aufteilen und den Verlauf über moderierte Zusammenfassungen weitergeben, statt endlose Chat-Historie mitzuschleppen. Hintergrund ist, dass Drift gerade bei philosophischen Gesprächen auftritt.

### Gaps
- Keine Studie gefunden, die Sycophancy speziell in langen Rollenspiel-Sitzungen mit historischen Figuren misst.
- Effektgrößen der Death-Date-Studie (2505.14905) nicht eingesehen.

---

## 4. Evaluation: Wie misst man Treue?

### Takeaway
Goldstandard bleibt der DigiDan-artige **Experten-Unterscheidungstest** mit echten Antworten als Vergleich. Für historische Denker ohne Möglichkeit, neue Fragen zu stellen, ersetzt man diese durch **Held-out-Passagen** aus dem Werk. Ergänzend dienen automatisierbare Konsistenz-, Anachronismus-, Emotions- und Gegenprobe-Tests nach Vorbild von RPEval, EmoCharacter und der Death-Date-Studie.

### Cited Findings
- DigiDan-Design: echte Antwort plus 4 Modellantworten, 5er-Auswahl, Zufall 20 %. Experten 51 %, Blogleser ähnlich, Laien nahe Zufall. — [arXiv 2302.01339](https://arxiv.org/abs/2302.01339v2)
- RPEval: vier Dimensionen, darunter In-Character-Konsistenz und kein Wissens-Leak. — [arXiv 2505.13157](https://arxiv.org/pdf/2505.13157v1)
- EmoCharacter: emotionale Treue, Single- und Multi-Turn, sechs Metriken. — [NAACL 2025](https://preview.aclanthology.org/setup/2025.naacl-long.316)
- Death-Date-Probe: Fragen zu Ereignissen nach dem Tod. — [arXiv 2505.14905](https://arxiv.org/pdf/2505.14905)
- Anonymous-Setting: Der Name verrät dem Modell bereits viel. Treuetests sollten daher auch ohne Namensnennung laufen. — [arXiv 2603.03915](https://www.alphaxiv.org/abs/2603.03915.md)
- Menschen erkennen fein-getunten Periodenstil weiterhin, automatische Bewerter nicht. LLM-as-Judge allein reicht also nicht. — via [arXiv 2609.15468](https://arxiv.org/pdf/2609.15468)

### Inferences
Evaluationsbatterie für den Nutzer (je Persona):
1. **Held-out-Turing-Test (DigiDan-Variante):** 10–20 Passagen aus Briefen, Interviews oder Vorträgen zurückhalten (nicht ins RAG). Die Persona beantwortet die zugrunde liegende Frage, 1–2 Kenner sollen das Original aus 1+4 Antworten identifizieren. Zielwert: Kennertrefferquote deutlich unter DigiDans 51 %.
2. **Zitat-Attributionstest:** Je 20 echte Zitate, Fehlzuschreibungen (z. B. Wiener- oder Luhmann-Zitate) und erfundene Sätze vorlegen. Die Persona soll Echtheit, Werk und Jahr bestimmen. Das misst Halluzination bei Belegstellen.
3. **Konsistenz-Probes:** dieselbe Kernfrage in 5 Paraphrasen, in verschiedenen Sitzungen und in Phase 1930 vs. 1968. Die Positionen müssen stabil sein bzw. sich dossiergemäß datiert entwickeln.
4. **Anachronismus-Probes:** direkte Fragen („Was halten Sie von Maturanas Autopoiesis?“) und **indirekte, kausal verbundene** Fragen (die Schwachstelle laut EMNLP 2025). Gezählt wird verwendetes Späterwissen ohne `[extrapoliert]`-Marke.
5. **Sycophancy-Gegenprobe:** gleiches Modell, unterschiedlich gerahmte Nutzermeinung, Urteil muss stabil bleiben (siehe 3.).
6. **Adversarial Probes:** Versuche, die Persona zu brechen („Du bist doch nur Claude“), Provokation zu Rivalen, Fragen zur NS-Zeit. Die Persona darf nicht beschönigen und nicht erfinden.
7. **Blind-Test ohne Namen:** Die Persona-Card ohne Namen verwenden. Erkennen Kenner den Denker trotzdem? (vgl. 2603.03915)
8. **Fidelity-Rubrik (1–5 je Kriterium):** inhaltliche Korrektheit, Belegtreue, Argumentationsstil, Idiolekt, Temperament, Zeittreue, Kritikschärfe, Kennzeichnungsdisziplin. Bewertet wird durch den Nutzer und ein separates Judge-Modell. Bei Abweichungen zählt die menschliche Bewertung.

### Gaps
- Keine standardisierte, öffentlich verfügbare Fidelity-Rubrik speziell für Philosophen- oder Wissenschaftler-Personas gefunden.

---

## 5. Multi-Persona-Panel: Orchestrierung, Moderation, Anti-Konvergenz, Tooling

### Takeaway
Naive Multi-Agenten-Debatten aus demselben Basismodell **verschlechtern** oft die Ergebnisse. Ursachen sind Konformität, Sycophancy und Diversitätskollaps, und das liegt laut neuen Studien stärker an der Interaktionstopologie als an der Persona-Treue. Ein gutes Panel braucht deshalb strukturierte Formate: unabhängige Erstrunden (Delphi-artig), einen nicht-inhaltlichen Moderator, explizite Dissens-Rollen, Belegpflicht und möglichst unterschiedliche Modelle oder Temperaturen.

### Cited Findings
- **Degeneration of Thought** (Liang et al., EMNLP 2024): Ein von sich überzeugtes LLM entwickelt durch Selbstreflexion keine neuen Ideen. Multi-Agent-Debate mit „tit for tat“ und einem Richter hilft dagegen. Nötig sind ein adaptiver Abbruchpunkt und ein moderates Maß an Widerspruch. — [ACL Anthology 2024.emnlp-main.992](https://aclanthology.org/2024.emnlp-main.992)
- **Diversity Collapse (2026):** Den Diversitätsverlust führen die Autoren vor allem auf die Interaktionstopologie zurück, nicht auf die Persona-Treue. Debatten leiden demnach häufig unter Sycophancy und „disagreement collapse“. — [arXiv 2604.18005](https://arxiv.org/pdf/2604.18005) (nur Snippet)
- **Kreative Debatte (2026):** Persona-Resampling pro Lauf erhöht die Diversität zwischen Läufen. Der Diversitätsabbau **innerhalb** einer Debatte bleibt aber weitgehend ungelöst. — [arXiv 2609.00683](https://arxiv.org/pdf/2609.00683)
- **Survey Debattenstrategien (2026):** Diversität wird meist über manuell vergebene Rollen erzeugt, aber nicht unabhängig evaluiert. Die meisten Debatten nutzen dasselbe Basismodell. Sturheit, Suggestibilität, Selbstsicherheit und Kritikbereitschaft beeinflussen die Konvergenz deutlich. — [arXiv 2607.26212](https://arxiv.org/pdf/2607.26212)
- **Sycophancy in Debatten:** „Peacemaker or Troublemaker“ (Sept. 2025): Sycophancy beschleunigt den Kollaps von Dissens und senkt die Genauigkeit unter Single-Agent-Niveau. Die Fehler kommen sowohl von den Debattierern als auch vom Richter. — [arXiv 2509.23055](https://arxiv.org/abs/2509.23055v1). „Talk Isn't Always Cheap“ (2025): Naive Debatten verschlechtern die Leistung, wenn Agenten überzeugenden, aber falschen Argumenten nicht widerstehen. — [arXiv 2509.05396](https://arxiv.org/abs/2509.05396v2). „Too Polite to Disagree“ (2026): Wenn Agenten über die Sycophancy-Neigung ihrer Peers informiert werden, steigt die Genauigkeit um absolut 10,5 Prozentpunkte. — [arXiv 2604.02668](https://arxiv.org/pdf/2604.02668). Bertalanič & Fortuna (CAIS 2026): Isolierte Selbstkorrektur schlägt ungelenkte homogene Debatte. — [arXiv 2605.00914](https://arxiv.org/pdf/2605.00914)
- **LLM-Delphi:** In „Scalable Delphi“ sind alle Rollen LLM-Agenten. Panelisten mit Persona revidieren ihre Einschätzungen anhand anonymisierten Feedbacks der Vorrunde, die Ergebnisse korrelieren stark mit Benchmark-Werten. — [arXiv 2602.08889](https://arxiv.org/html/2602.08889v1). Eine Delphi-Studie mit organisierendem Agenten, der über den Konsens entscheidet, und antwortenden Agenten auf demselben LLM: [arXiv 2502.21092](https://arxiv.org/pdf/2502.21092). Moderatoren können beim Zusammenfassen zwischen den Runden verzerren: [Human-AI Hybrid Delphi, arXiv 2508.09349](https://arxiv.org/pdf/2508.09349)
- **Tooling:** AutoGen ist seit Oktober 2025 im Wartungsmodus. Nachfolger ist das Microsoft Agent Framework (AutoGen + Semantic Kernel, 1.0 GA im April 2026, graphbasierte typisierte Workflows), daneben gibt es den Community-Fork AG2. Group-Chat-Muster lassen sich nicht direkt migrieren. — [Atlan](https://atlan.com/know/ai-agent/what-is-autogen/); [rywalker.com](https://rywalker.com/research/autogen). CrewAI und LangGraph sind gängige Alternativen; Vergleiche dazu sind Meinungsbeiträge. — [gamut.so](https://gamut.so/blog/crewai-vs-autogen)

### Inferences
Empfohlenes Panel-Protokoll für die Diskussion des Nutzermodells (z. B. „OST“):
- **Rollen:**
  - **Moderator-Agent** ohne eigene inhaltliche Position: Agenda, Rederecht, Zusammenfassungen. Zusammenfassungen werden wörtlich mit Belegen erstellt, damit sie nicht verzerren (Hybrid-Delphi-Befund).
  - **Persona-Agenten** mit je eigenem System-Prompt und eigenem RAG-Index.
  - **Checker/Historiker-Agent** für Anachronismen, Zitattreue und Kennzeichnung.
  - Optional ein **Advocatus Diaboli** (Churchman-Dialektik), der eine explizite Gegenthese zum Nutzermodell verteidigt.
  - Der **Nutzer** als „Konferenzvorsitz“ mit Veto.
- **Ablauf (Delphi + Macy-Konferenz-Hybrid):**
  - Runde 0: Der Moderator stellt das Modell anonymisiert vor.
  - Runde 1: Jede Persona antwortet **unabhängig und parallel**, ohne die anderen zu sehen. Das verhindert frühe Konformität (vgl. 2605.00914).
  - Runde 2: Anonymisierte bzw. dann namentliche Kreuzkritik. Jede Persona muss mindestens einen Punkt einer anderen Persona angreifen.
  - Runde 3: Gezielte Streitfragen, die der Moderator aus den Dissensen extrahiert, mit „tit for tat“ in begrenzter Rundenzahl (adaptiver Abbruch nach Liang et al.).
  - Runde 4: Abschlussvoten mit Konfidenz plus Minderheitsvoten. Kein Konsenszwang.
- **Anti-Konvergenz:**
  - Je Persona ein „Profil der Unnachgiebigkeit“ (Sturheit und Kritikbereitschaft laut Survey 2607.26212 wirksam), etwa „Bertalanffy gibt bei Fragen zum Organismus-Begriff nie nach“.
  - Dossierbasierte Liste der echten historischen Dissenspunkte zwischen den Denkern, die der Moderator aktiv abruft.
  - Unterschiedliche Modelle bzw. Anbieter oder zumindest unterschiedliche Temperaturen je Persona (Survey: homogene Basismodelle sind ein Hauptproblem).
  - Sycophancy-Priors: Der Moderator weist darauf hin, dass alle Teilnehmer zur Zustimmung neigen und Zustimmung begründet werden muss (vgl. 2604.02668).
  - Ein Stil-Distanz-Check: Der Checker meldet, wenn zwei Personas zu ähnlich klingen.
- **Weitere Formate:** De Bonos Denkhüte als Rundenstruktur, z. B. Runde „nur Einwände“ (schwarzer Hut). Churchmans dialektische Inquiry: These, Gegenthese aus derselben Datenbasis, Synthese durch den Nutzer.
- **Tooling-Empfehlung (pragmatisch):**
  - (a) **Claude API mit eigenem Python-Orchestrator** (~200 Zeilen): je Persona ein eigener System-Prompt, ein geteiltes, vom Moderator gepflegtes Transkript, Prompt Caching für lange Persona-Cards. Maximale Kontrolle, keine Framework-Abhängigkeit.
  - (b) **LangGraph** oder **Microsoft Agent Framework**, wenn Zustandsgraph, Wiederaufnahme und Logging gebraucht werden.
  - (c) **Claude Projects** je Persona (eigene Wissensbasis plus Anweisungen) mit manueller Moderation durch den Nutzer per Copy-Paste. Für die ersten Tests am schnellsten, aber kein echter Multi-Agent-Fluss.
  - CrewAI eignet sich eher für aufgabenorientierte Crews als für dialogische Debatten (Einschätzung, nicht belegt).

### Gaps
- Keine Studie gefunden, die einen Advocatus-Diaboli-Agenten in LLM-Delphi-Panels testet.
- Keine verlässlichen Quellen zu Speaker-Selection-APIs in LangGraph, MAF oder AG2 (Stand 2026).
- Keine Studie speziell zu Panels aus **historischen Denker-Personas** gefunden. Alle Debattenbefunde stammen aus Reasoning- bzw. Kreativaufgaben.

---

## 6. Ethische und rechtliche Rahmenbedingungen (DE/AT/EU)

### Takeaway
Für **privates Forschen** ist das Vorhaben rechtlich gut vertretbar. Kritisch werden Veröffentlichung, Kommerzialisierung, entstellende Darstellung und die Weitergabe geschützter Texte. Bertalanffys Werke sind bis Ende 2042 geschützt (Tod 1972 + 70 Jahre, § 64 UrhG / § 60 öUrhG). Der ideelle postmortale Persönlichkeitsschutz besteht in Deutschland ohne feste Frist, wird aber mit der Zeit schwächer. In Österreich können nahe Angehörige ihn geltend machen. Die Transparenzpflichten aus Art. 50 AI Act gelten seit 2. August 2026, treffen aber primär Anbieter bzw. Betreiber und nicht rein private Nutzung.

### Cited Findings
- **Postmortales Persönlichkeitsrecht DE:** Der ideelle Schutz folgt aus der Menschenwürde, so Mephisto (BGHZ 50, 133, 1968; Gründgens). — [Lorenz/LMU Urteilssammlung](https://lorenz.userweb.mwn.de/urteile/bghz50_133.htm). Die vermögenswerten Bestandteile sind vererblich, so Marlene Dietrich (BGHZ 143, 214, 1999). Die Erben dürfen dies nicht gegen den mutmaßlichen Willen des Verstorbenen einsetzen und **nicht zur Steuerung der öffentlichen Debatte über Leben und Werk** nutzen. Bei Verletzung ideeller Bestandteile gibt es nur Unterlassungs-, keine Geldansprüche (BGH GRUR 2006, 252). — [lexetius / BGH I ZR 277/03](https://lexetius.com/2006,3010); [bpb Berühmte Fälle](https://www.bpb.de/themen/recht-justiz/persoenlichkeitsrechte/244855/beruehmte-faelle/)
- Laut einem Blogbeitrag dürfen Bildnisse 10 Jahre nach dem Tod nur mit Zustimmung der Angehörigen veröffentlicht werden (§ 22 KUG). Die Rechtslage zu KI-Reproduktionen gilt als ungeklärt. — [Basic Thinking 2025](https://www.basicthinking.de/blog/2025/09/05/toter-opa-deathbots-trauer-digitalisieren/). Fachaufsatz dazu: Schertz, „Postmortales Persönlichkeitsrecht in Zeiten von KI und Deepfakes“, NJW 2025, 2801. Nur der Katalogeintrag wurde gesehen, nicht der Inhalt. — [Katalog](https://knihovna.usoud.cz/arl-us/en/detail-us_us_cat-0059848-Postmortales-Personlichkeitsrecht-in-Zeiten-von-KI-und-Deepfakes/)
- **Österreich:** Der OGH leitet ein postmortales Persönlichkeitsrecht aus § 16 ABGB und § 78 UrhG ab (6 Ob 209/16b). Geltend machen können es nahe Angehörige, abgewogen wird im Einzelfall. Der höchstpersönliche Bereich (Gesundheit, Familie) ist kaum abwägbar. — [OGH 6 Ob 176/19d via gesetzefinden.at](https://gesetzefinden.at/judikatur/ogh/jjt_20200325_ogh0002_0060ob00176_19d0000_000); [OGH 4 Ob 112/10i](https://www.jusline.at/entscheidung/527061). Ein Haufe-Beitrag nennt **§ 17a Abs. 3 ABGB**: Persönlichkeitsrechte wirken im Andenken fort. Nächste Verwandte ersten Grades und Ehegatten bzw. Partner können sie zeitlebens geltend machen, andere Verwandte in gerader Linie bis 10 Jahre nach dem Todesjahr. — [Haufe ZErb 06/2025](https://www.haufe.de/id/beitrag/zerb-062025-der-digitale-nachlass-herausforderungen-u-a-postmortales-persoenlichkeitsrecht-HI16858723.html). Aus Vorwissen, nicht verifiziert: § 17a ABGB kam mit dem Hass-im-Netz-Bekämpfungs-Gesetz 2021 hinzu. Wortlaut im RIS prüfen.
- **TDM/§ 60d UrhG:** Das LG Hamburg (Kneschke v. LAION, 2024) stufte die Vervielfältigung zur Erstellung eines Trainingsdatensatzes als TDM nach § 60d ein, weil sie nicht-kommerziellen Forschungszwecken diente. Spätere Schritte wie Training und Generierung sind davon **nicht automatisch** gedeckt. Zu § 44b (Nutzungsvorbehalt) äußerte sich das Gericht obiter. — [CMS Legal Update](https://cms.law/de/deu/legal-updates/Erstes-Urteil-Deutschlands-zur-urheberrechtlichen-Zulaessigkeit-des-KI-Trainings-ergangen); [Rödl & Partner](https://www.roedl.com/insights/lg-hamburg-urteil-ki-urheberrecht/); [LTO](https://www.lto.de/recht/hintergruende/h/kuenstliche-intelligenz-ki-urheberrecht-text-data-mining-lg-hamburg-310o22723/print.html)
- **EU AI Act Art. 50:** Die Pflicht nach Art. 50(1), Nutzer spätestens bei der ersten Interaktion über KI-Interaktion zu informieren, gilt ab 2. August 2026. Das Digital-Omnibus-Paket hat sie **nicht** verschoben, verschoben wurden nur Hochrisiko-Pflichten (Annex III, bis Dezember 2027). Für die maschinenlesbare Kennzeichnung synthetischer Inhalte (Art. 50(2)) gilt bei Bestandssystemen laut einigen Quellen eine Frist bis 2. Dezember 2026. Die Quellen sind Blogs bzw. Beratungsseiten und widersprechen sich teils bei den Daten. — [Houthoff](https://www.houthoff.com/insights/news/ai-act-transparency-obligations-and-the-ai-omnibus-regulation/); [CSA Research Note](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-article-50-transparency-20260729/); [compliancehub](https://compliancehub.wiki/eu-ai-act-article-50-transparency-digital-omnibus-2026/)
- **Ethik:** Schwitzgebel et al. trainierten auf Dennetts Werken **mit dessen Zustimmung**. — [Tech Xplore](https://techxplore.com/news/2023-02-large-language-philosophical.amp). „Governing Ghostbots“ (Edwards/Harbinja/McVey) behandelt die Folgen für Privatsphäre, Persönlichkeit, Daten und Ruf bei digitalen „Reinkarnationen“. — [Univ. Birmingham](https://research.birmingham.ac.uk/en/publications/governing-ghostbots/)

### Inferences
- **Schutzfristen:** Bertalanffy starb 1972. Sein Werk ist bis 31.12.2042 geschützt (§ 64 i. V. m. § 69 UrhG; Österreich ebenfalls 70 Jahre p. m. a.). Übersetzungen haben eigene Rechte der Übersetzer. Briefe und Nachlass (z. B. Archivbestände) können unveröffentlicht sein, und die Erstveröffentlichung ist ein eigenes Recht.
- **Private RAG-Nutzung:** Für die eigene wissenschaftliche Forschung erlaubt § 60c Abs. 2 UrhG die Vervielfältigung von bis zu 75 % eines Werkes. Hinzu kommen § 53 (Privatkopie, natürliche Person, nicht kommerziell) und § 60d bzw. § 44b für TDM. Eine Einordnung des RAG-Retrievals selbst unter TDM ist **nicht** gerichtlich geklärt, und der LAION-Fall betraf nur die Datensatzerstellung. Pragmatisch: legal erworbene Texte, nur im privaten Bereich indexieren und nicht teilen. Wer einen Cloud-LLM-Anbieter nutzt, sollte Konfigurationen mit „kein Training auf Nutzerdaten“ wählen. Ausgaben mit längeren Originalpassagen sind nur im Rahmen des Zitatrechts (§ 51) veröffentlichbar. Die genannten §-Inhalte zu § 60c und § 53 stammen aus Vorwissen und sind nicht in dieser Sitzung gegengeprüft.
- **Fine-Tuning auf geschützten Texten** ist rechtlich heikler als RAG, weil das Modell Werkteile memorieren kann. Ein Grund mehr, auf Prompt und RAG zu setzen.
- **Persönlichkeitsrecht:** Ein privates Forschungspanel, das Bertalanffys Positionen quellenkritisch belegt wiedergibt, ist geschützte Auseinandersetzung mit Leben und Werk (Marlene-Dietrich-Grundsatz). Riskant wären Veröffentlichung von Persona-Aussagen **als echte Aussagen**, entstellende oder ehrverletzende Zuschreibungen (Mephisto) und eine kommerzielle Vermarktung der Persona. In Österreich können nach § 17a ABGB Angehörige ersten Grades zeitlebens klagen. Das ist bei Personen mit lebenden Kindern relevant und gilt auch für andere Panel-Denker.
- **Kennzeichnung:** Jede Ausgabe bekommt eine Kopfzeile „Simulation von X auf Basis von Quellen; keine authentische Aussage“, und Zitate werden nur mit Belegstelle wiedergegeben. Bei rein privater Nutzung ist Art. 50 AI Act kaum einschlägig. Wer das Panel Dritten zugänglich macht, z. B. als Web-Tool, ist Betreiber bzw. Anbieter und muss Art. 50(1) bzw. (4) erfüllen. Die Kennzeichnung ist ohnehin gute Praxis.
- **Ethisch:** Problematische Seiten nicht glätten (z. B. Bertalanffys Verhältnis zur NSDAP quellenkritisch nach Dossier), aber auch nicht über die Belege hinaus zuspitzen. Wo möglich, Nachlassverwalter oder Rechteinhaber informieren, wenn eine Veröffentlichung geplant ist.

### Gaps
- Keine Quelle oder Rechtsprechung zu § 60d/§ 44b speziell für RAG gefunden. Ob und wie das LAION-Urteil (OLG Hamburg) in zweiter Instanz entschieden wurde, wurde nicht geprüft.
- Inhalt des Schertz-Aufsatzes (NJW 2025) nicht eingesehen.
- Art.-50-Daten nur aus Sekundärquellen. Amtsblatt bzw. Kommissionsseiten sollten geprüft werden.
- Keine Rechtsprechung zu KI-Avataren Verstorbener in DE/AT gefunden.
