# German taxonomy scan - 2026-09-26: what was done with it

The scan below took its vocabulary from the Bundestag's own subject
descriptors, not from ours. Every candidate it surfaced was then measured
against DIP across ALL time and its sample titles READ before anything was
decided. "Missed" in the raw list below is not a quality score: a broad
descriptor like `Krankenkasse` misses 99% of its Vorgänge because 99% of
them are not our ground.

## APPLIED at v0.5

| Term | Area | Tier | DIP Vorgänge | Missed by v0.4 |
|---|---|---|---|---|
| christliche* Minderheit* | 8 religion | 1 | 22 | 21 |
| religiöse* Minderheit* | 8 religion | 1 | 24 | 23 |
| transgeschlechtlich* | 5 sex-based rights | 1 | 17 | 14 |
| Transperson* | 5 | 1 | 6 | 5 |
| nichtbinär* | 5 | 1 | 4 | 4 |
| LSBTIQ*, LSBTTIQ* | 5 | 2 | 21 | 18 |
| sexuelle* Identität | 5 (area is a question for you) | 2 | 12 | 11 |
| Sexualerziehung* | 6 parental rights | 1 | 6 | 4 |
| Schulpflicht* | 6 | moved: guarded tier 1 -> unguarded tier 2 | 16 | 16 |
| Pränataltest* | 1 abortion | 1 | 7 | 7 |
| vertrauliche* Geburt*, anonyme* Geburt*, Babyklappe* | 1 | 2 | 5 / few / 7 | all |
| Zwangsverheiratung*, Zwangsehe* | 12 (beside Zwangsheirat) | 1 | 30 / 9 | 27 / 7 |
| Mehrehe*, Auslandsehe* | 9 (beside Kinderehe) | 1 | 3 / 4 | all |
| HateAid | 7 free speech | 1 | 11 | 9 |
| Kopftuch [guarded to school and children] | 8 | 2 | 5 | 4 |
| Kindesmissbrauch* | 12 | 2 | 47 | 44 |

## FOUND BROKEN, AND FIXED IN THE FILTER

A `*` inside a phrase was treated as a literal asterisk, so these had matched
NOTHING since the day they were written: `"ungeborene* Leben"` (area 1 tier 1),
`"assistierte* Selbsttötung"` (area 2 tier 1), `"Trans* bei Kindern"` (area 3
tier 1), and in the English file `"smartphone* in schools"`. Fixed in
`src/filter.py`; a test now fails if any term in either file can never match.

`Trans* bei Kindern`, once live, also matched `Transferleistungen bei
Kindern` (child benefit), `Transport` and `Transparenz`. It was replaced by
`Transition* bei Kindern`, `Transidentität* bei Kindern` and `Trans-Kinder*`.
**Please say whether those are the Bundestag's words.**

## FOR YOU TO DECIDE (not applied)

- **`Euthanasie*`** (area 2, tier 1): 23 Vorgänge carry it and **19 are Nazi-era
  commemoration** ("Opfer von NS-Euthanasie und Zwangssterilisation") -- 83%
  false positives on a term that drives the sweep. The file already reserved
  the keep-or-remove call to you; this is the measurement it asked for.
- **Organ donation** -- `Organspende` (74), `Widerspruchsregelung`, `Hirntod`: no
  area claims it, so the opt-out Transplantationsgesetz debate of 24
  September was invisible to the edition. A scope question, not a term.
- **Intersex** -- `Varianten der Geschlechtsentwicklung` (17), `Intersexualität`
  (9): the law on surgery on intersex children. Children and sex
  characteristics, but not the gender-dysphoria question area 3 is about.

## REJECTED, with the reason

- `Gewalt gegen Frauen` (103), `häusliche Gewalt` (98): domestic-violence
  services and EU implementation. The sharp end -- `Femizid`,
  `Gewaltschutzgesetz`, `Istanbul-Konvention` -- is already here. Rejected for
  the same reason `Frauenrechte` was at v0.4.
- `Ethikrat` (49): elections to the council and its members' allowances.
  Its substantive opinions are titled by topic and caught by topic terms.
- `reproduktive Selbstbestimmung` (12): already covered; v0.4 missed 1 of 12.
- `Konversion` on its own: see the new trap in the master file -- in German
  politics it is the civil reuse of military land.
- Descriptors that co-occurred with our seeds but name other ground
  (`Krankenkasse`, `Datenspeicherung`, `Kriegsfolgen`, `Klimaschutz`, ...).

## WHAT THIS STILL CANNOT DO

It cannot read the terms as German. It found words the Bundestag's own
indexers use; whether each is the word a German campaigner would recognise,
and which side of a debate it belongs to, is still yours to say.

---

# German taxonomy scan - 2026-09-26

*Vocabulary taken from the Bundestag's own descriptors, not from ours. Seeded from 2159 Vorgänge found by the tier-1 terms across ALL time; 401 recurring descriptors harvested; 41 already covered by the taxonomy under their own name; 108 uncovered and expanded.*

**Nothing here has been applied.** Each candidate is the Bundestag's term, the area whose seeds it recurred in, and how many of ITS Vorgänge the taxonomy misses by title. Mark each ACCEPT, REJECT or TIER2 on its DECISION line.

Migration (area 11) is listed last: it is collated and never campaigned, and its sparseness is deliberate.

---

### Kriegsfolgen
- area: Assisted dying | recurs in 3 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 100
  - 2026-09-25 Gesetz zu dem Übereinkommen vom 16. Dezember 2025 zur Einrichtung einer Internationalen Schadensersatzkommissi
  - 2026-09-08 Humanitäre Situation in Gaza - Kenntnisse und Aktivitäten der Bundesregierung
  - 2026-08-27 Wissenschaftskooperation mit der Ukraine und Unterstützung beim Wiederaufbau von Forschungsinfrastrukturen
  - 2026-08-07 Lage der christlichen Gemeinden im Libanon im Kontext von Staatskrise, bewaffneten Konflikten und demografisch
DECISION: 

### Streik
- area: Parental rights education | recurs in 3 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 100
  - 2025-10-09 Störungen im Betriebsablauf bei der Deutschen Bahn AG und deren Auswirkungen auf Sicherheit und Pünktlichkeit
  - 2024-09-12 Digitalisierung von Arbeit und Arbeitsförderung
  - 2024-04-25 Für das Recht auf politischen Streik
  - 2024-02-16 Tarifbindung in der Leiharbeit - Arbeitnehmerüberlassung
DECISION: 

### Klimaschutz
- area: Parental rights education | recurs in 3 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 100
  - 2026-09-25 Drittes Gesetz zur Änderung des Brennstoffemissionshandelsgesetzes
  - 2026-09-24 Sofortige Senkung der Energiekosten - Beendigung aller deutschen Klimaschutzmaßnahmen
  - 2026-09-24 Nationaler Aktionsplan zur Förderung von Tarifverhandlungen in Deutschland nach Artikel 4 Absatz 2 Satz 2 der 
  - 2026-09-24 Kein Klimaschutz auf Grundlage des Betriebsverfassungsgesetzes
DECISION: 

### Krankenkasse
- area: Abortion | recurs in 5 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 99
  - 2026-09-25 Gesetz für Daten und digitale Innovation im Gesundheitswesen
  - 2026-09-24 Lieferengpässe bei Arzneimitteln effektiv verringern - Abhängigkeit der Arzneimittelversorgung vom Nicht-EU-Au
  - 2026-09-04 Berichte über Millionenverluste für Krankenkassen und Kassenärztliche Vereinigungen durch risikoreiche Immobil
  - 2026-08-14 Reduktion der Zahl gesetzlicher Krankenkassen
DECISION: 

### Medizinische Forschung
- area: Abortion | recurs in 5 seed Vorgänge (62% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 99
  - 2026-09-21 Stand der Migräne-Forschung in Deutschland
  - 2026-09-11 Datenlage zur nekrotisierenden Fasziitis vor und nach der Covid-19-Pandemie
  - 2026-08-28 Projektstart der Förderrichtlinien zur Frauengesundheit und Zeitplan für den Mittelabruf
  - 2026-08-21 Möglichkeiten der Sekundärnutzung nicht transplantierter postmortaler Gewebespenden für Forschungszwecke
DECISION: 

### Militärstandort
- area: Conversion practices | recurs in 5 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 99
  - 2026-09-25 Bundeswehr-Infrastrukturbeschleunigungsgesetz
  - 2026-08-21 Kinderbetreuung als Faktor zur Personalbindung und Einsatzbereitschaft der Bundeswehr
  - 2026-07-16 Die Brigade "Litauen" der Bundeswehr und das ehemalige Partisanenlager im Wald von Rüdninkai (Nachfrage zur An
  - 2026-07-03 Standortentscheidung hinsichtlich einer Bundeswehr-Stationierung in Bamberg
DECISION: 

### Umweltbewegung
- area: Parental rights education | recurs in 5 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 99
  - 2026-07-03 Strafverfahren im Zusammenhang mit der Letzten Generation und den Bauernprotesten zwischen Dezember 2023 und M
  - 2026-07-03 Ermittlungsverfahren gegen Mitglieder der Letzten Generation wegen Bildung krimineller Vereinigungen
  - 2025-08-08 Aufklärungsbemühungen der Bundesregierung bei Extremismushinweisen
  - 2025-06-06 Lage von indigenen Gemeinschaften und Umweltaktivisten in Lateinamerika
DECISION: 

### EU-Erweiterung
- area: Freedom of religion | recurs in 3 seed Vorgänge (60% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 99
  - 2026-09-24 Keine EU-Mitgliedschaft und keine militärischen Beistandsgarantien für die Ukraine
  - 2026-08-21 Zusätzliche deutsche Beitragszahlungen im Falle eines EU-Beitritts des Westbalkan
  - 2026-08-10 Erweiterung der Europäischen Union um die Ukraine vor dem Hintergrund einer assoziierten Mitgliedschaft
  - 2026-07-17 Property-Law-Reform als EU-Beitrittskriterium für Albanien vor dem Hintergrund von Bauten im Vjosa-Delta
DECISION: 

### Verordnung der EU
- area: Free speech online safety | recurs in 19 seed Vorgänge (63% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 98
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates über einen Rahmen für Maßnahmen zur St
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates über das Verfahren zur Genehmigung von
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates zur Änderung der Verordnung (EU) 2021/
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates zur Änderung der Verordnung (EU) 2018/
DECISION: 

### Rüstungskonversion
- area: Conversion practices | recurs in 3 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 98
  - 2026-08-14 Aussetzung der Umwandlung von ehemaligen Militärliegenschaften in Thüringen
  - 2026-07-01 Aussetzung der Umwandlung von ehemaligen Militärliegenschaften in Rheinland-Pfalz
  - 2026-06-15 Nutzung von Liegenschaften und Verkehrswegen durch die Bundeswehr in Hamburg
  - 2026-06-02 Moratorium für die Konversion von Bundeswehrliegenschaften: Aktueller Stand
DECISION: 

### ITK-Branche
- area: Free speech online safety | recurs in 23 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 97
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates über einen Rahmen für Maßnahmen zur St
  - 2026-09-21 Souveränität kritischer IT-Sicherheitsinfrastruktur - Übernahmepläne PSI durch Warburg-Pincus
  - 2026-09-21 Ausbau strategischer Halbleitertechnologien durch chinesische Unternehmen in Dresden
  - 2026-09-15 Zum KI-gestützten Assistenzsystem zur Unterstützung und Beschleunigung von Planungs- und Genehmigungsverfahren
DECISION: 

### Gleichbehandlungsgrundsatz
- area: Marriage family | recurs in 15 seed Vorgänge (83% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 97
  - 2026-09-23 ... Gesetz zur Änderung des Grundgesetzes (Artikel 3 Absatz 3 Satz 1)
  - 2026-08-17 Diskriminierungstatbestände im Zusammenhang mit nichtbinären Geschlechtsidentitäten im Rahmen des Allgemeinen 
  - 2026-08-14 Mehrbelastung von Ehepaaren gegenüber unverheirateten Paaren durch die Neuregelung der Familienversicherung
  - 2026-07-17 Auftragsvolumen für Zeitarbeitspersonal in Truppenküchen der Bundeswehr in den Jahren 2022 bis 2025
DECISION: 

### Telekommunikation
- area: Free speech online safety | recurs in 15 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 97
  - 2026-07-31 Abstimmungsverhalten der Bundesregierung über die Verlängerung der befristeten Ausnahme von der ePrivacy-Richt
  - 2026-03-06 Ausländische Direktinvestitionen in Deutschland in den Jahren 2019 und 2025
  - 2026-02-02 Zu den Aufsichts- und Kontrollmandaten der Bundesnetzagentur im Bereich der Digitalpolitik
  - 2026-01-30 Tätigkeitsbericht der Bundesnetzagentur - Telekommunikation 2024/2025 mit 14.Sektorgutachten der Monopolkommis
DECISION: 

### Arbeitsbedingungen
- area: Prostitution | recurs in 8 seed Vorgänge (89% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 97
  - 2026-09-25 Entschließung des Bundesrates für faire Arbeitsbedingungen in der Plattformarbeit
  - 2026-09-24 Situation der Seeleute im Persischen Golf und im Roten Meer
  - 2026-09-08 Position der Bundesregierung zu Auswirkungen des Freihandelsabkommens zwischen der EU und Indien
  - 2026-08-18 Mitteilung über eine angenommene Urkunde eines Übereinkommens der Internationalen Arbeitsorganisation
DECISION: 

### Technikfolgenabschätzung
- area: Surrogacy embryology | recurs in 5 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 97
  - 2026-06-24 Bericht des Ausschusses für Forschung, Technologie, Raumfahrt und Technikfolgenabschätzung (18. Ausschuss) gem
  - 2026-06-10 Bericht des Ausschusses für Forschung, Technologie, Raumfahrt und Technikfolgenabschätzung (18. Ausschuss) gem
  - 2026-05-06 Bericht des Ausschusses für Forschung, Technologie, Raumfahrt und Technikfolgenabschätzung (18. Ausschuss) gem
  - 2026-05-06 Bericht des Ausschusses für Forschung, Technologie, Raumfahrt und Technikfolgenabschätzung (18. Ausschuss) gem
DECISION: 

### Betäubungsmittel
- area: Assisted dying | recurs in 5 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 97
  - 2026-09-23 Gesetz zur strafrechtlichen Bekämpfung der Verabreichung sogenannter K.O.-Tropfen zur Begehung von Raub- und S
  - 2026-09-23 ... Gesetz zur Änderung des Strafgesetzbuches - Stärkung des strafrechtlichen Schutzes vor sogenannten K.-o.-T
  - 2026-06-09 K.O.-Tropfen (Spiking) - Dunkelfeld sexualisierter Gewalt und Handlungsbedarf bei Prävention, Beweissicherung 
  - 2026-06-02 Chemische Unterwerfung als spezifische Form sexualisierter Gewalt
DECISION: 

### Datenschutz
- area: Free speech online safety | recurs in 29 seed Vorgänge (76% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates zur Änderung der Verordnung (EU) 2018/
  - 2026-09-25 Gesetz zur Reform des Nachrichtendienstrechts
  - 2026-09-25 Gesetz zu der Mehrseitigen Vereinbarung vom 15. Januar 2025 zwischen den zuständigen Behörden über den Austaus
  - 2026-09-25 Entschließung des Bundesrates: Einführung einer gesetzlichen Regelung zum "Recht auf Vergessenwerden" für ehem
DECISION: 

### Wiedergutmachung nationalsozialistischen Unrechts
- area: Assisted dying | recurs in 10 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-09-01 Einhaltung des gesetzlichen Stiftungszwecks und Mittelverwendung der Stiftung Erinnerung, Verantwortung und Zu
  - 2026-07-10 Entschädigungszahlungen an polnische NS-Opfer
  - 2026-06-24 Schätzungen zu Kosten möglicher Reparationszahlungen an NS-Opfer in Polen
  - 2026-06-08 Einhaltung des gesetzlichen Stiftungszwecks und Mittelverwendung der Stiftung Erinnerung, Verantwortung und Zu
DECISION: 

### Arzneimittel
- area: Gender medicine children | recurs in 10 seed Vorgänge (83% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-09-24 Lieferengpässe bei Arzneimitteln effektiv verringern - Abhängigkeit der Arzneimittelversorgung vom Nicht-EU-Au
  - 2026-09-23 Entscheidungsgrundlagen und Auswirkungen der Neuregelung des § 31 Abs. 6 SGB V zum Vorrang cannabishaltiger Fe
  - 2026-08-21 Zulassungsverfahren für den Wirkstoff Daraxonrasib
  - 2026-08-14 Bestandsschutz und Erstattungsfähigkeit von Cannabisblüten nach dem GKV-Beitragssatzstabilisierungsgesetz
DECISION: 

### Gedenkstätte
- area: Assisted dying | recurs in 6 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-08-18 Deutsche Erinnerungskultur neu ausrichten - Gedenkstättenkonzeption des Bundes durch eine Bundeskonzeption nat
  - 2026-08-07 Stopp der geplanten Gedenkstätte für die Opfer der Colonia Dignidad durch die neue chilenische Regierung
  - 2026-07-31 Erhalt des Bunkers der Neuen Reichskanzlei als Erinnerungsort an den Nationalsozialismus
  - 2026-07-17 Höhe der Miete für den "Tränenpalast" in Berlin
DECISION: 

### Internationale Beziehungen
- area: Freedom of religion | recurs in 6 seed Vorgänge (60% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-09-16 Islamische Republik Iran - diplomatische Bemühungen
  - 2026-09-16 Deutsch-afghanische Beziehungen seit Machtübernahme der Taliban
  - 2026-09-11 Reise von Bundesaußenminister Dr. Wadephul nach Mauretanien und die deutsch-mauretanischen Beziehungen
  - 2026-09-11 Illegalen Entsorgung und Deponierung von aus Deutschland exportierten Alttextilien
DECISION: 

### Gesundheitskosten
- area: Gender medicine children | recurs in 4 seed Vorgänge (57% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-09-11 Behandlungskosten im Krankenhausbereich für Verletzungen durch scharfe oder spitze Gegenstände
  - 2026-08-21 Ernährungsarmut und Kantinenwesen
  - 2026-08-18 Entschließung des Bundesrates "Pflegebudget sachgerecht nutzen, Anreize zum Qualifikationsmissbrauch vermeiden
  - 2026-08-14 Reduktion der Zahl gesetzlicher Krankenkassen
DECISION: 

### Kinderbetreuung
- area: Marriage family | recurs in 22 seed Vorgänge (92% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 95
  - 2026-09-04 Gesetz zur Verbesserung der Startchancen von Kindern und zur Qualitätsentwicklung in der Kindertagesbetreuung 
  - 2026-08-21 Kinderbetreuung als Faktor zur Personalbindung und Einsatzbereitschaft der Bundeswehr
  - 2026-08-07 Mindereinnahmen für die Bundesländer durch den Rückgang der Umsatzsteueranteile im Rahmen des Gesetzes zur Ver
  - 2026-08-06 Folgen für Kinder und Familien durch Änderungen in Leistungsgesetzen - Datengrundlagen und Kostenkalkulationen
DECISION: 

### Gesundheitserziehung
- area: Gender medicine children | recurs in 3 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 95
  - 2026-09-24 Viertes Gesetz zur Änderung des Transplantationsgesetzes - Einführung einer Widerspruchsregelung
  - 2026-09-24 Freiwilligkeit der Organspende sichern - Aufklärungs- und Registrierungspotenziale heben
  - 2026-09-24 ... Gesetz zur Änderung des Transplantationsgesetzes und Einführung der Widerspruchslösung
  - 2026-09-11 Datenlage zur nekrotisierenden Fasziitis vor und nach der Covid-19-Pandemie
DECISION: 

### Datenspeicherung
- area: Free speech online safety | recurs in 72 seed Vorgänge (95% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 94
  - 2026-09-24 Stärkung der nationalen Souveränität und der operativen Fähigkeiten des Bundesnachrichtendienstes
  - 2026-09-15 Zum KI-gestützten Assistenzsystem zur Unterstützung und Beschleunigung von Planungs- und Genehmigungsverfahren
  - 2026-09-07 Erhebung und Verarbeitung personenbezogener Daten im Geschäftsbereich des Bundesministeriums der Verteidigung 
  - 2026-09-02 Gesetz zur Änderung des Wärmeplanungsgesetzes
DECISION: 

### Einkommensteuer
- area: Marriage family | recurs in 19 seed Vorgänge (95% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 94
  - 2026-09-25 Jahressteuergesetz 2026
  - 2026-09-24 Kryptowerte streng regulieren und gerecht besteuern
  - 2026-09-23 Gesetz zur Einführung des Tarifs auf Rädern zur automatischen Anpassung des Steuerrechts an die kalte Progress
  - 2026-09-23 Aufteilung des Entlastungsvolumens der Einkommensteuerreform auf den Ausgleich der kalten Progression und weit
DECISION: 

### Datenaustausch
- area: Free speech online safety | recurs in 16 seed Vorgänge (70% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 94
  - 2026-09-25 Zweites Gesetz zur Änderung des Straßenverkehrsunfallstatistikgesetzes
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates zur Änderung der Verordnung (EU) 2018/
  - 2026-09-25 Gesetz zur Stärkung des Innovations- und Wirtschaftsstandorts Deutschland durch Erprobungsfreiräume
  - 2026-09-25 Gesetz zur Stärkung der genossenschaftlichen Rechtsform
DECISION: 

### Kriminalitätsbekämpfung
- area: Prostitution | recurs in 11 seed Vorgänge (50% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 94
  - 2026-09-25 Gesetz für mehr Gerechtigkeit durch die Stärkung der Zollverwaltung und die Bekämpfung der Finanzkriminalität
  - 2026-09-25 Entschließung des Bundesrates zur Bekämpfung der Kriminalität junger Menschen in Deutschland
  - 2026-09-23 Gesetz zur strafrechtlichen Bekämpfung der Verabreichung sogenannter K.O.-Tropfen zur Begehung von Raub- und S
  - 2026-09-23 Gesetz zur Umsetzung der Richtlinie (EU) 2024/1260 über die Abschöpfung und Einziehung von Vermögenswerten
DECISION: 

### Vergangenheitsbewältigung
- area: Assisted dying | recurs in 4 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 94
  - 2026-09-23 85 Jahre Massaker von Babyn Jar - Deutschlands historische Verantwortung für die Ukraine
  - 2026-09-16 Zur Position der Bundesregierung zur Kritik am Bauhaus und zu den Folgen der architektonischen Moderne
  - 2026-09-10 Jahresbericht 2026 Der lange Schatten der SED-Diktatur. Die Bewältigung der Folgen des staatlichen Unrechts in
  - 2026-09-10 Beschluss der Deutsch-Französischen Parlamentarischen Versammlung vom 22. Juni 2026 zu zwangsrekrutierten Sold
DECISION: 

### Arzt
- area: Assisted dying | recurs in 4 seed Vorgänge (80% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 94
  - 2026-09-25 Gesetz zur Modernisierung des Befristungsrechts im Wissenschaftsbereich
  - 2026-09-04 Bearbeitung von Visumanträgen an der Botschaft in Teheran
  - 2026-08-07 Fortschritte hinsichtlich der geplanten Reform der Approbationsordnung für Ärzte seit März 2026
  - 2026-07-10 Gesetz zur Beschleunigung der Anerkennungsverfahren ausländischer Berufsqualifikationen in Heilberufen
DECISION: 

### Ermittlungsverfahren
- area: Free speech online safety | recurs in 15 seed Vorgänge (58% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 93
  - 2026-09-25 Gesetz für mehr Gerechtigkeit durch die Stärkung der Zollverwaltung und die Bekämpfung der Finanzkriminalität
  - 2026-09-11 Erkenntnisgrundlage für die Zuschreibung des Anschlagsversuchs am Flughafen Leipzig/Halle an Russland
  - 2026-09-11 Erkenntnisgrundlage für die Zuschreibung des Anschlagsversuchs am Flughafen Leipzig/Halle an Russland
  - 2026-09-04 Vorlage der zugesagten Behördenchronologie zum Anschlag auf den Berliner CSD
DECISION: 

### Religiöse Minderheit
- area: Freedom of religion | recurs in 10 seed Vorgänge (91% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 93
  - 2026-09-22 Lage der christlichen Minderheit im Jemen im Kontext des langjährigen Bürgerkriegs und der dschihadistischen B
  - 2026-09-01 Lage der christlichen Minderheit in Somalia und die anhaltende Existenzbedrohung durch dschihadistischen Terro
  - 2026-08-25 Lage der christlichen Minderheit im Iran - Systematische Unterdrückung, staatliche Repressionsmaßnahmen und di
  - 2026-08-17 Lage der christlichen Minderheit in Israel und den Palästinensischen Gebieten im Kontext zunehmender Übergriff
DECISION: 

### Organisierte Kriminalität
- area: Prostitution | recurs in 13 seed Vorgänge (81% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 92
  - 2026-09-24 Wirksamkeit von Finanzermittlungen und Vermögensabschöpfung bei Organisierter Kriminalität
  - 2026-09-23 Wirksamkeit der strafrechtlichen Vermögensabschöpfung
  - 2026-09-23 Gesetz zur Umsetzung der Richtlinie (EU) 2024/1260 über die Abschöpfung und Einziehung von Vermögenswerten
  - 2026-09-23 Erkenntnisse zum Kriminalitätsphänomen „Crime as a Service“
DECISION: 

### Schüler
- area: Parental rights education | recurs in 8 seed Vorgänge (80% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 92
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
  - 2026-06-24 Öffentliche Auftritte der Bundeswehr im dritten Quartal 2026
  - 2026-06-23 Mit dem Neun-Euro-Ticket private Haushalte entlasten
  - 2026-05-05 Ferien-, Kennenlern-, IT- und Abenteuercamps für Schülerinnen und Schüler sowie Jugendliche bei der Bundeswehr
DECISION: 

### Nationalsozialistisches Unrecht
- area: Assisted dying | recurs in 7 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 92
  - 2026-09-23 85 Jahre Massaker von Babyn Jar - Deutschlands historische Verantwortung für die Ukraine
  - 2026-09-16 Zur Position der Bundesregierung zur Kritik am Bauhaus und zu den Folgen der architektonischen Moderne
  - 2026-09-10 Beschluss der Deutsch-Französischen Parlamentarischen Versammlung vom 22. Juni 2026 zu zwangsrekrutierten Sold
  - 2026-07-31 Erhalt des Bunkers der Neuen Reichskanzlei als Erinnerungsort an den Nationalsozialismus
DECISION: 

### Personenbezogene Daten
- area: Free speech online safety | recurs in 24 seed Vorgänge (62% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2026-09-25 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates zur Änderung der Verordnung (EU) 2018/
  - 2026-09-25 Gesetz über eine Beauftragte oder einen Beauftragten der Bundesregierung für die Anliegen von Betroffenen von 
  - 2026-09-25 Gesetz zur Stärkung der Reserve (Reservestärkungsgesetz - ResStG)
  - 2026-09-25 Gesetz zur Reform des Nachrichtendienstrechts
DECISION: 

### Therapie
- area: Conversion practices | recurs in 14 seed Vorgänge (93% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2026-09-23 Entscheidungsgrundlagen und Auswirkungen der Neuregelung des § 31 Abs. 6 SGB V zum Vorrang cannabishaltiger Fe
  - 2026-07-10 Medizinische Behandlung mit Bakteriophagen ergänzend oder alternativ zu Antibiotika sowie Bakteriophagen in we
  - 2026-04-22 Transparenz bei der Vergabe von Kindertherapieplätzen
  - 2026-04-22 Huaier-Granulat (Trametes robiniophila, "Huaier") zwischen Krebsbegleittherapie in China und Nahrungsergänzung
DECISION: 

### Verbrechensopfer
- area: Prostitution | recurs in 6 seed Vorgänge (60% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
  - 2026-09-07 Angriffe auf Politiker, Parteibüros und Wahlplakate im ersten Halbjahr 2026
  - 2026-08-28 Ausschluss männlicher Opfer häuslicher Gewalt vom Rechtsanspruch auf Schutz und Beratung
  - 2026-07-17 Anzahl von Gewaltopfern unter Kindern und Jugendlichen zwischen den Jahren 2002 und 2025
DECISION: 

### Krankenversicherung der Landwirte
- area: Abortion | recurs in 3 seed Vorgänge (75% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2025-01-30 Stabilität und Nachhaltigkeit der Finanzierung der Sozialversicherung
  - 2023-12-15 Gesetz zur Anpassung des Zwölften und des Vierzehnten Buches Sozialgesetzbuch und weiterer Gesetze
  - 2023-10-27 Versicherungspflicht in der Sozialversicherung für Landwirtschaft, Forsten und Gartenbau für im Nebenerwerb tä
  - 2023-02-06 Gesetz zur Stärkung der Chancen für Qualifizierung und für mehr Schutz in der Arbeitslosenversicherung (Qualif
DECISION: 

### Kinderpornografie
- area: Prostitution | recurs in 14 seed Vorgänge (70% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 90
  - 2026-09-08 Effiziente Strafverfolgung im digitalen Raum - Technische Methoden und digitale Analyseverfahren des BKA gegen
  - 2026-06-19 Position der Bundesregierung zu Client Side Scanning und der Interimsverordnung bei den CSAM-Trilogverhandlung
  - 2026-02-23 Fragen zum systematischen Suchen und Löschen von bereits bekannten Darstellungen sexualisierter Gewalt gegen K
  - 2026-01-28 Verstöße der Plattform X gegen europäisches Recht im Zusammenhang mit dem KI-Chatbot Grok
DECISION: 

### Zwangsarbeit
- area: Prostitution | recurs in 9 seed Vorgänge (90% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 90
  - 2026-09-08 Position der Bundesregierung zu Auswirkungen des Freihandelsabkommens zwischen der EU und Indien
  - 2026-09-01 Lage der christlichen Minderheit in Somalia und die anhaltende Existenzbedrohung durch dschihadistischen Terro
  - 2026-08-28 Risiko von Zwangsarbeit durch hohe Gebühren bei der Vermittlung bzw. Beschäftigung aus Drittstaaten
  - 2026-08-13 Lage der christlichen Minderheit im Sudan im Kontext des Bürgerkriegs seit April 2023
DECISION: 

### Familie
- area: Marriage family | recurs in 35 seed Vorgänge (67% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 89
  - 2026-09-24 Viertes Gesetz zur Änderung des Transplantationsgesetzes - Einführung einer Widerspruchsregelung
  - 2026-09-09 Keine Einschnitte beim Wohngeld - Entlastung für Familien und Rentnerinnen und Rentner sichern
  - 2026-09-04 Kennzahlen zur Wirkungsmessung des KfW-Programms "Jung kauft Alt"
  - 2026-08-28 Beitragszahlungen zur gesetzlichen Rentenversicherung für pflegende Angehörige in den Jahren 2023 bis 2025
DECISION: 

### Behindertes Kind
- area: Abortion | recurs in 3 seed Vorgänge (60% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 89
  - 2026-06-26 Anzahl von kaum bzw. nicht beschulten Kindern und Jugendlichen mit Behinderungen seit 2022
  - 2026-06-22 Barrierefreie und inklusive Gesundheitsversorgung insbesondere für Frauen und Mädchen mit Behinderungen stärke
  - 2026-05-15 Geplante Ausnahmeregelungen bei der Einschränkung der beitragsfreien Mitversicherung in der Krankenversicherun
  - 2026-05-08 Schlussfolgerungen aus Pool-Modellen für die Schulbegleitung ohne Einzelfallprüfung
DECISION: 

### Sexueller Missbrauch
- area: Prostitution | recurs in 30 seed Vorgänge (79% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 88
  - 2026-07-22 Gesetz zur Stärkung des strafrechtlichen Kinderschutzes und zur Verschärfung der Sanktionen bei schweren sexue
  - 2026-07-10 Fallzahlen zu Ermittlungsverfahren bei sexueller Gewalt und Ausbeutung Minderjähriger
  - 2026-07-06 Bilanz des ersten Jahres der Tätigkeit des Unabhängigen Beauftragten für Fragen des sexuellen Kindesmissbrauch
  - 2026-07-03 Fälle von Vergewaltigung und sexuellem Missbrauch mit syrischen Tatverdächtigen in den Jahren 2013 bis 2026
DECISION: 

### Telekommunikationsüberwachung
- area: Free speech online safety | recurs in 22 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 88
  - 2026-09-11 Vorschlag für eine Richtlinie des Europäischen Parlaments und des Rates über die Europäische Ermittlungsanordn
  - 2026-09-10 Gesetz zur Änderung des Strafrechts - Umsetzung der Richtlinie (EU) 2024/1203 über den strafrechtlichen Schutz
  - 2026-08-12 ... Gesetz zur Änderung des Waffengesetzes - Ausgestaltung des unerlaubten Umgangs mit halbautomatischen Kurzw
  - 2026-07-24 Haltung der Bundesregierung zu EU-Regelungen über die Durchleuchtung verschlüsselter Kommunikation
DECISION: 

### LSBTTIQ
- area: Parental rights education | recurs in 14 seed Vorgänge (50% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 88
  - 2026-09-24 Versorgung von transgeschlechtlichen und nichtbinären Menschen sicherstellen
  - 2026-09-23 ... Gesetz zur Änderung des Grundgesetzes (Artikel 3 Absatz 3 Satz 1)
  - 2026-09-15 Queere Dating- und Cruising-Kultur in Gefahr
  - 2026-09-09 Strategie des Auswärtigen Amts zur humanitären Hilfe
DECISION: 

### Strafverfolgung
- area: Free speech online safety | recurs in 22 seed Vorgänge (50% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 86
  - 2026-09-25 Entschließung des Bundesrates zum für das Jahr 2026 vorgesehenen Bericht der Europäischen Kommission über die 
  - 2026-09-25 Entschließung des Bundesrates "Flächendeckender Ausbau multiprofessioneller Kinderschutzstrukturen"
  - 2026-09-21 US-amerikanische aufsichtsrechtliche Maßnahmen gegen die Deutsche Bank im Zusammenhang mit Jeffrey Epstein
  - 2026-09-14 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates über die Agentur der Europäischen Unio
DECISION: 

### Kinderschutz
- area: Prostitution | recurs in 16 seed Vorgänge (50% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 86
  - 2026-09-25 Entschließung des Bundesrates "Flächendeckender Ausbau multiprofessioneller Kinderschutzstrukturen"
  - 2026-09-10 Beschluss der Deutsch-Französischen Parlamentarischen Versammlung vom 22. Juni 2026 zum Schutz von Minderjähri
  - 2026-07-31 Priorisierung der Empfehlungen zum Kinder- und Jugendschutz in der digitalen Welt
  - 2026-07-22 Gesetz zur Stärkung des strafrechtlichen Kinderschutzes und zur Verschärfung der Sanktionen bei schweren sexue
DECISION: 

### Religiöse Verfolgung
- area: Freedom of religion | recurs in 25 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 85
  - 2026-09-22 Lage der christlichen Minderheit im Jemen im Kontext des langjährigen Bürgerkriegs und der dschihadistischen B
  - 2026-09-01 Lage der christlichen Minderheit in Somalia und die anhaltende Existenzbedrohung durch dschihadistischen Terro
  - 2026-08-25 Lage der christlichen Minderheit im Iran - Systematische Unterdrückung, staatliche Repressionsmaßnahmen und di
  - 2026-08-17 Lage der christlichen Minderheit in Israel und den Palästinensischen Gebieten im Kontext zunehmender Übergriff
DECISION: 

### Christentum
- area: Freedom of religion | recurs in 23 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 85
  - 2026-09-22 Lage der christlichen Minderheit im Jemen im Kontext des langjährigen Bürgerkriegs und der dschihadistischen B
  - 2026-09-01 Lage der christlichen Minderheit in Somalia und die anhaltende Existenzbedrohung durch dschihadistischen Terro
  - 2026-08-25 Lage der christlichen Minderheit im Iran - Systematische Unterdrückung, staatliche Repressionsmaßnahmen und di
  - 2026-08-17 Lage der christlichen Minderheit in Israel und den Palästinensischen Gebieten im Kontext zunehmender Übergriff
DECISION: 

### Online-Dienst
- area: Free speech online safety | recurs in 69 seed Vorgänge (97% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 84
  - 2026-09-25 Jahressteuergesetz 2026
  - 2026-09-25 Entschließung des Bundesrates für faire Arbeitsbedingungen in der Plattformarbeit
  - 2026-09-24 Gesetz zu der Mehrseitigen Vereinbarung vom 22. Juni 2021 zwischen den zuständigen Behörden über den automatis
  - 2026-09-02 Gesetz zur Förderung europäischer audiovisueller Werke durch eine Investitionsverpflichtung für Mediendienstea
DECISION: 

### Opferschutz
- area: Prostitution | recurs in 26 seed Vorgänge (90% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 84
  - 2026-09-23 Gesetz zur strafrechtlichen Bekämpfung der Verabreichung sogenannter K.O.-Tropfen zur Begehung von Raub- und S
  - 2026-08-14 Ausbau des Opferschutzes in Strafverfahren
  - 2026-08-04 Antimuslimische Vorfälle im ersten Halbjahr 2026
  - 2026-07-22 Gesetz zur Stärkung des strafrechtlichen Kinderschutzes und zur Verschärfung der Sanktionen bei schweren sexue
DECISION: 

### Schwangerschaft
- area: Abortion | recurs in 15 seed Vorgänge (71% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 84
  - 2026-09-24 Drittes Gesetz zur Änderung des Seelotsgesetzes
  - 2026-09-15 Die vertrauliche Geburt und Formen anonymer Kindesabgabe
  - 2026-07-08 Illegale Medikamentenversuche an Schwangeren, Minderjährigen und politischen Gefangenen in der DDR (Nachfragen
  - 2026-07-08 Auswirkungen der Einstufung von Trifluoressigsäure als fruchtbarkeitsschädigend
DECISION: 

### Kirche
- area: Freedom of religion | recurs in 5 seed Vorgänge (62% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 84
  - 2026-08-14 Umgang mit durch den Kosovo-Krieg beschädigten christlichen Stätten und Friedhöfen
  - 2026-07-16 Haushaltsmittel des Bundes für Kirchen, kirchliche Träger und kirchennahe Einrichtungen in den Haushaltsjahren
  - 2026-06-25 Staatliche Förderung kirchlicher Entwicklungsorganisationen
  - 2026-04-30 Sexueller Missbrauch von Kindern und Jugendlichen als Arbeits- oder Schulunfall - Verletzung der Meldepflicht 
DECISION: 

### Soziale Medien
- area: Free speech online safety | recurs in 73 seed Vorgänge (92% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 83
  - 2026-09-24 Öffentlichkeitsarbeit der Bundesregierung
  - 2026-09-14 Aufwendungen der Bundesregierung für Broschüren (Print- und Onlinepublikationen), Veranstaltungen sowie Podcas
  - 2026-09-10 Beschluss der Deutsch-Französischen Parlamentarischen Versammlung vom 22. Juni 2026 zum Schutz von Minderjähri
  - 2026-08-31 Social-Media-Kommunikation des Bundesministers des Auswärtigen
DECISION: 

### Rahmenbeschluss der EU
- area: Prostitution | recurs in 12 seed Vorgänge (100% of its appearances) | its own Vorgänge: 89, of which the taxonomy MISSES 83
  - 2026-09-25 Verordnung zur Umsetzung der Richtlinie (EU) 2024/1785 und zur Umsetzung des Durchführungsbeschlusses (EU) 202
  - 2026-08-12 Gesetz zur Neuregelung des Rechts der internationalen Rechtshilfe in Strafsachen
  - 2025-09-01 Anerkennung und Vollstreckung ausländischer Geldsanktionen
  - 2024-11-07 Initiativen der Bundesregierung zur Vollendung des Europäischen Bildungsraums bis 2025
DECISION: 

### Chirurgischer Eingriff
- area: Gender medicine children | recurs in 11 seed Vorgänge (65% of its appearances) | its own Vorgänge: 97, of which the taxonomy MISSES 83
  - 2026-09-21 Umsetzung des Patient Blood Managements, Förderung der Direktrückgewinnung und Aufbereitung des eigenen Bluts 
  - 2026-07-17 Familiengerichtsverfahren im Kontext des Gesetzes zum Schutz von Kindern mit Variationen der Geschlechtsentwic
  - 2026-07-10 Gesetz zur Stabilisierung der Beitragssätze in der gesetzlichen Krankenversicherung (GKV-Beitragssatzstabilisi
  - 2026-04-24 Genitaloperationen an Kindern bis neun Jahren
DECISION: 

### Internet
- area: Free speech online safety | recurs in 46 seed Vorgänge (78% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 82
  - 2026-09-08 Effiziente Strafverfolgung im digitalen Raum - Technische Methoden und digitale Analyseverfahren des BKA gegen
  - 2026-09-04 Position der Bundesregierung zu EU-Verhandlungen über Privacy Signals und einer Einflussnahme von Google
  - 2026-08-21 Termine von Bundesminister Karsten Wildberger mit Zivilgesellschaft und mit der Ionos SE
  - 2026-07-22 Gesetz zur Stärkung digitaler Ermittlungsbefugnisse zur Abwehr von Gefahren des internationalen Terrorismus
DECISION: 

### Digitale Medien
- area: Free speech online safety | recurs in 19 seed Vorgänge (86% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 82
  - 2026-09-25 Entschließung des Bundesrates "Verleitung Minderjähriger zur Selbstschädigung mittels digitaler Medien strafre
  - 2026-09-14 Aufwendungen der Bundesregierung für Broschüren (Print- und Onlinepublikationen), Veranstaltungen sowie Podcas
  - 2026-08-31 Schutz der Medienfreiheit im Europäischen Demokratieschild
  - 2026-08-03 Das Portal "Apollo News" im Visier des Bundesamtes für Verfassungsschutz und des Bundeskriminalamtes
DECISION: 

### Existenzminimum
- area: Marriage family | recurs in 17 seed Vorgänge (63% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 82
  - 2026-05-26 Gesunde Ernährung und andere Fragen zur Neuberechnung der Regelsätze in der Grundsicherung
  - 2026-05-21 Bis zur Abschaffung des Rundfunkbeitrags die Bürger bei Zahlung dieser Zwangsabgabe steuerlich entlasten
  - 2026-05-15 Veröffentlichung der Sonderauswertung zum Regelbedarfsermittlungsgesetz
  - 2026-05-15 Rentenbezogene Daten zu Aussiedlern bzw. Spätaussiedlern
DECISION: 

### Islam
- area: Freedom of religion | recurs in 9 seed Vorgänge (75% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 80
  - 2026-09-17 Umsetzung der Empfehlungen des Bundesrechnungshofes in Bezug auf die Förderung von Islamic Relief Deutschland 
  - 2026-09-01 Lage der christlichen Minderheit in Somalia und die anhaltende Existenzbedrohung durch dschihadistischen Terro
  - 2026-08-25 Lage der christlichen Minderheit im Iran - Systematische Unterdrückung, staatliche Repressionsmaßnahmen und di
  - 2026-08-24 Entscheidungsprozesse im Auswärtigen Amt bei der Förderung von Islamic Relief Deutschland e.V. (Nachfrage zur 
DECISION: 

### Häusliche Gewalt
- area: Sex based rights | recurs in 41 seed Vorgänge (91% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 78
  - 2026-09-14 Prävention und Sensibilisierung zu Gewalt gegen Frauen
  - 2026-09-04 Evaluation der elektronischen Aufenthaltsüberwachung
  - 2026-08-28 Ausschluss männlicher Opfer häuslicher Gewalt vom Rechtsanspruch auf Schutz und Beratung
  - 2026-08-07 Schutzplätze für männliche Gewaltopfer
DECISION: 

### Gewaltschutz
- area: Sex based rights | recurs in 26 seed Vorgänge (76% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 74
  - 2026-09-14 Prävention und Sensibilisierung zu Gewalt gegen Frauen
  - 2026-08-18 Mitteilung über eine angenommene Urkunde eines Übereinkommens der Internationalen Arbeitsorganisation
  - 2026-07-21 Beitrag der Bundesregierung zur Minderung der humanitären Krise und zur Unterstützung von UNMISS im Südsudan
  - 2026-07-17 Ausbau des Hilfesystems nach dem Gewalthilfegesetz trotz kommunalen Rückzugs aus der Gewaltschutzfinanzierung
DECISION: 

### Eltern
- area: Marriage family | recurs in 19 seed Vorgänge (58% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 73
  - 2026-07-09 Ablehnung jeglicher Impfpflichten - Aufhebung des Masernschutzgesetzes
  - 2026-06-12 Kriterien für eine Härtefallprüfung bei Totalsanktionen gegen Familien im Bürgergeldbezug
  - 2026-06-12 Beteiligung von Kindern an elterlichen Pflegekosten
  - 2026-05-22 Erster Fortschrittsbericht zur Umsetzung des Nationalen Aktionsplans "Neue Chancen für Kinder in Deutschland"
DECISION: 

### Intersexualität
- area: Sex based rights | recurs in 23 seed Vorgänge (68% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 72
  - 2026-07-17 Familiengerichtsverfahren im Kontext des Gesetzes zum Schutz von Kindern mit Variationen der Geschlechtsentwic
  - 2026-07-10 Stand des Berichts zur Evaluation des Gesetzes zum Schutz von Kindern mit Varianten der Geschlechtsentwicklung
  - 2026-06-05 Evaluierung des Gesetzes zum Schutz von Kindern mit Varianten der Geschlechtsentwicklung
  - 2026-04-24 Genitaloperationen an Kindern bis neun Jahren
DECISION: 

### Familienleistung
- area: Marriage family | recurs in 21 seed Vorgänge (88% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 72
  - 2026-09-24 Verteilungswirkungen des Familienleistungsausgleichs
  - 2026-07-31 Anwendung des Artikels 68 Absatz 2 Satz 3 der Verordnung (EG) Nummer 883/2004
  - 2026-06-11 Zukunftsinvestitionen statt Kürzungen - Familien stärken und Kinder fördern
  - 2026-03-19 Steuer- und sozialrechtliche Ausgestaltung kindbezogener Leistungen
DECISION: 

### Katholische Kirche
- area: Abortion | recurs in 5 seed Vorgänge (56% of its appearances) | its own Vorgänge: 85, of which the taxonomy MISSES 69
  - 2026-06-25 Staatliche Förderung kirchlicher Entwicklungsorganisationen
  - 2025-11-28 Unterstützung des Kolpingwerks Deutschland
  - 2025-11-24 Mögliche gemeinsame diplomatische Abstimmungen und Initiativen der Bundesrepublik Deutschland und des Heiligen
  - 2024-11-01 Öffentlichkeit der Fachtagung zur Aufarbeitung von sexuellem Missbrauch in der katholischen Kirche am 7. und 8
DECISION: 

### Suizid
- area: Assisted dying | recurs in 12 seed Vorgänge (80% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 65
  - 2026-09-25 Entschließung des Bundesrates "Verleitung Minderjähriger zur Selbstschädigung mittels digitaler Medien strafre
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
  - 2026-07-29 Burn-out, psychische Belastungen und Suizidgefährdung in der deutschen Landwirtschaft
  - 2026-06-19 Ankündigungen und Umsetzung - Bilanz der gesundheitspolitischen Vorhaben der Bundesministerin für Gesundheit n
DECISION: 

### Ethikkommission
- area: Surrogacy embryology | recurs in 4 seed Vorgänge (100% of its appearances) | its own Vorgänge: 68, of which the taxonomy MISSES 61
  - 2026-01-26 Medizinforschungsgesetz
  - 2025-12-12 Aufwandsentschädigungen für die Mitglieder des Deutschen Ethikrats in den Jahren 2023, 2024 und 2025
  - 2024-11-29 Fortschritte in der Energiewende hinsichtlich der Integration von Verbrauchern als Produzenten und einer Öffen
  - 2024-07-04 Entschließungsantrag zum Medizinforschungsgesetz
DECISION: 

### Namensrecht
- area: Sex based rights | recurs in 15 seed Vorgänge (75% of its appearances) | its own Vorgänge: 81, of which the taxonomy MISSES 58
  - 2026-07-08 Transparenz und Zugriffsberechtigungen beim Konto des Bundeskanzlers Friedrich Merz auf der Plattform X
  - 2025-10-10 Vorlage eines Regierungsentwurfs zur Reform des öffentlichen Namensrechts
  - 2025-06-27 Häufigste Vornamen von Bürgergeldbeziehern
  - 2024-08-09 Tatverdächtige von Gewalttaten und Straftaten gegen die sexuelle Selbstbestimmung am Hauptbahnhof Rostock und 
DECISION: 

### Geschlecht
- area: Sex based rights | recurs in 76 seed Vorgänge (83% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 57
  - 2026-09-24 Versorgung von transgeschlechtlichen und nichtbinären Menschen sicherstellen
  - 2026-09-14 Struktur, Kosten und gesellschaftspolitische Ausrichtung der Hochschule der Bundesagentur für Arbeit
  - 2026-08-17 Diskriminierungstatbestände im Zusammenhang mit nichtbinären Geschlechtsidentitäten im Rahmen des Allgemeinen 
  - 2026-08-07 Geschlechtsspezifische Einschränkungen für Verwendungen in bestimmten Bereichen der Bundeswehr
DECISION: 

### Embryo
- area: Abortion | recurs in 4 seed Vorgänge (57% of its appearances) | its own Vorgänge: 78, of which the taxonomy MISSES 57
  - 2024-06-14 Vorschlag für eine Verordnung des Europäischen Parlaments und des Rates über Qualitäts- und Sicherheitsstandar
  - 2024-04-09 Verfahrensstand des vom Bundesminister für Gesundheit angekündigten Rechtsgutachtens zum Thema Duogynon
  - 2023-11-15 Studie zu den Ursachen und dem Verlauf des Duogynon-Skandals
  - 2020-12-04 Untersuchungsvorhaben zur Rolle deutscher Behörden hinsichtlich der Registrierung und Pharmakovigilanz von Duo
DECISION: 

### Kinder- und Jugendarmut
- area: Marriage family | recurs in 15 seed Vorgänge (100% of its appearances) | its own Vorgänge: 72, of which the taxonomy MISSES 54
  - 2026-09-25 Mitteilung der Kommission an das Europäische Parlament, den Rat, den Europäischen Wirtschafts- und Sozialaussc
  - 2026-09-10 Das Solidarprinzip stärken
  - 2026-07-15 Maßnahmen der Bundesregierung zur Umsetzung der EU-Anti-Armutsstrategie
  - 2026-06-11 Zukunftsinvestitionen statt Kürzungen - Familien stärken und Kinder fördern
DECISION: 

### Sexualerziehung
- area: Abortion | recurs in 5 seed Vorgänge (56% of its appearances) | its own Vorgänge: 67, of which the taxonomy MISSES 54
  - 2026-06-02 Projekt des Bundesministeriums für wirtschaftliche Zusammenarbeit und Entwicklung "Theater als Methode zur Bew
  - 2026-04-23 Vorfälle bei einem von der Amadeu Antonio Stiftung geförderten Schulprojekt
  - 2026-02-04 Bundesförderung sexualpädagogischer Maßnahmen - Inhalte, Standards und der Umgang mit körperbezogenen Konzepte
  - 2025-12-17 Altersgrenze für die Vermittlung von Inhalten zu Sexualität und geschlechtlicher Identität in Kindertageseinri
DECISION: 

### Evangelische Kirche
- area: Freedom of religion | recurs in 3 seed Vorgänge (75% of its appearances) | its own Vorgänge: 54, of which the taxonomy MISSES 49
  - 2026-06-25 Staatliche Förderung kirchlicher Entwicklungsorganisationen
  - 2025-01-24 Mitwirkung des Bundeskanzleramts an der Vorbereitung eines Termins von Wolfgang Schmidt in Hamburg
  - 2024-01-17 Haltung der Bundesregierung zur Verschenkung des Danziger Paramentenschatzes an die Danziger Marienkirche in P
  - 2023-12-22 Einbindung der Staatsanwaltschaften bei der Aufarbeitung von Missbrauch in der Evangelischen Kirche
DECISION: 

### Schwangerschaftsberatung
- area: Abortion | recurs in 35 seed Vorgänge (92% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 48
  - 2026-06-11 Humanitäre Hilfe stärken, Völkerrecht verteidigen, international Verantwortung übernehmen
  - 2026-05-20 Kassenzulassung des nicht-invasiven Pränataltests - Monitoring der Konsequenzen und Einrichtung eines Gremiums
  - 2026-02-27 Reproduktive Gerechtigkeit verwirklichen - Selbstbestimmung gewährleisten
  - 2025-12-03 Versorgungslage ungewollt Schwangerer
DECISION: 

### Ehe
- area: Marriage family | recurs in 30 seed Vorgänge (86% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 45
  - 2026-07-03 Wissenschaftliche Erkenntnisse zu Erbkrankheiten bei Verwandtenehen
  - 2026-06-19 Erkenntnisse zu erhöhten gesundheitlichen Risiken für Kinder aus Verwandtenehen bzw. Zwangsehen
  - 2026-05-06 Grunderwerbsteuer und steuerliche Ungleichbehandlung ehelicher und nichtehelicher Lebensgemeinschaften
  - 2026-02-20 Härtefallbedingte Abweichungen von der Dreijahresfrist für die eheliche Lebensgemeinschaft seit 2015
DECISION: 

### Splittingverfahren
- area: Marriage family | recurs in 54 seed Vorgänge (100% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 43
  - 2026-06-10 Vereinbarkeit statt Verfügbarkeit - Für eine moderne Arbeitszeitpolitik
  - 2026-04-10 Gesamtbelastung von Privathaushalten durch mögliche Reformen
  - 2025-09-26 Entschließung des Bundesrates zur Beibehaltung der Wahlmöglichkeit von Lohnsteuerklasse 3 und 5 für Ehegatten
  - 2024-12-20 Gesetz zur Fortentwicklung des Steuerrechts und zur Anpassung des Einkommensteuertarifs (Steuerfortentwicklung
DECISION: 

### Transsexualität
- area: Sex based rights | recurs in 54 seed Vorgänge (57% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 42
  - 2026-09-07 Staatliche Mitfinanzierung der HateAid gGmbH und anderer Nichtregierungsorganisationen sowie deren Einbindung 
  - 2026-05-20 Relevanz von Studienergebnissen aus Großbritannien zur Täterschaft von Transpersonen bei Tötungsdelikten für D
  - 2026-05-15 Übertragbarkeit von britischen Studienergebnissen zu Tötungsdelikten durch Transgender-Personen auf Deutschlan
  - 2026-03-20 Gesundheitsversorgung für trans-, inter- und nichtbinäre Menschen bei geschlechtsaffirmativen Maßnahmen
DECISION: 

### Personenstand
- area: Sex based rights | recurs in 61 seed Vorgänge (80% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 41
  - 2026-07-27 Kolonialrechtliche Diskriminierung, Staatsangehörigkeitsfragen und behördliches Handeln am Beispiel der Famili
  - 2026-02-27 Jahresbericht 2024
  - 2025-10-17 Entschließung des Bundesrates für ein Gesetz zur Anerkennung der Geschlechtsidentität und zum Schutz der Selbs
  - 2025-06-19 Negative Auswirkungen der Transgenderpolitik auf Fairness in sportlichen Wettbewerben
DECISION: 

### Schulpflicht
- area: Parental rights education | recurs in 13 seed Vorgänge (100% of its appearances) | its own Vorgänge: 44, of which the taxonomy MISSES 41
  - 2026-07-10 Entschließung des Bundesrates: Schulpflicht als Garant für Chancengerechtigkeit und gesellschaftlichen Zusamme
  - 2026-06-10 Position der Bundesregierung zur Zeitgemäßheit der Schulpflicht
  - 2026-02-20 Befreiungen vom Präsenzunterricht infolge eines ärztlichen Attests im Jahr 2024
  - 2025-01-06 Situation pflegender Kinder und Jugendlicher
DECISION: 

### Familienbesteuerung
- area: Marriage family | recurs in 17 seed Vorgänge (100% of its appearances) | its own Vorgänge: 60, of which the taxonomy MISSES 40
  - 2025-09-26 Entschließung des Bundesrates zur Beibehaltung der Wahlmöglichkeit von Lohnsteuerklasse 3 und 5 für Ehegatten
  - 2024-12-20 Gesetz zur Fortentwicklung des Steuerrechts und zur Anpassung des Einkommensteuertarifs (Steuerfortentwicklung
  - 2024-03-15 Mehreinnahmen bei einer Abschaffung der Steuerklassen III und V
  - 2024-03-07 Auswirkungen des Splittingeffekts bei Ehen mit und ohne Kinder
DECISION: 

### Selbstbestimmungsrecht
- area: Sex based rights | recurs in 58 seed Vorgänge (78% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 32
  - 2026-08-17 Diskriminierungstatbestände im Zusammenhang mit nichtbinären Geschlechtsidentitäten im Rahmen des Allgemeinen 
  - 2026-07-10 Stand des Berichts zur Evaluation des Gesetzes zum Schutz von Kindern mit Varianten der Geschlechtsentwicklung
  - 2026-07-09 Zwangsbehandlungen reduzieren statt ausweiten - Rechte von Patientinnen und Patienten stärken
  - 2026-06-05 Evaluierung des Gesetzes zum Schutz von Kindern mit Varianten der Geschlechtsentwicklung
DECISION: 

### Zwangssterilisation
- area: Assisted dying | recurs in 13 seed Vorgänge (100% of its appearances) | its own Vorgänge: 39, of which the taxonomy MISSES 25
  - 2023-12-12 Umsetzung der Koalitionsversprechen im Bereich Kultur und Medien
  - 2023-01-26 Bilanz der Beauftragten der Bundesregierung für Kultur und Medien
  - 2022-07-22 Kenntnisse über eine Beteiligung der "China Family Planning Association" an Zwangsabtreibungen und -sterilisat
  - 2021-03-26 Gesetz zur Reform des Vormundschafts- und Betreuungsrechts
DECISION: 

### Standesamt
- area: Sex based rights | recurs in 11 seed Vorgänge (85% of its appearances) | its own Vorgänge: 39, of which the taxonomy MISSES 22
  - 2024-06-14 Gesetz zum Schutz Minderjähriger bei Auslandsehen
  - 2023-08-31 Rassismuserfahrungen von Familien in Jugend-, Standesämtern und Familiengerichten
  - 2022-10-07 Drittes Gesetz zur Änderung personenstandsrechtlicher Vorschriften
  - 2020-04-24 Gesetzesvorhaben in Ungarn zur künftigen Eintragung des Geschlechts beim Standesamt
DECISION: 

### Religionsausübung
- area: Freedom of religion | recurs in 4 seed Vorgänge (100% of its appearances) | its own Vorgänge: 26, of which the taxonomy MISSES 22
  - 2026-04-24 Unterstützung von Lehrkräften bei religiös motivierten Konflikten in der Schule
  - 2026-04-22 Erhebung der Anzahl unter 14-jähriger Schülerinnen mit Kopftuch an öffentlichen Schulen in Deutschland
  - 2026-04-02 Maßnahmen gegen eine islamische Einflussnahme auf deutsche Schulen
  - 2025-07-31 Berichte über Mobbing an Schulen durch religiös motivierte Bekleidungsvorschriften und insbesondere gegen Schü
DECISION: 

### Eherecht
- area: Marriage family | recurs in 17 seed Vorgänge (89% of its appearances) | its own Vorgänge: 41, of which the taxonomy MISSES 17
  - 2026-07-03 Wissenschaftliche Erkenntnisse zu Erbkrankheiten bei Verwandtenehen
  - 2025-10-17 Gesetz zur Bekämpfung der Mehrehe
  - 2024-06-14 Gesetz zum Schutz Minderjähriger bei Auslandsehen
  - 2020-12-22 Rechtliche Situation gleichgeschlechtlicher Ehepaare in Deutschland, der Europäischen Union und weltweit
DECISION: 

### Fortpflanzung
- area: Surrogacy embryology | recurs in 5 seed Vorgänge (100% of its appearances) | its own Vorgänge: 14, of which the taxonomy MISSES 8
  - 2025-10-17 Rechtswidrigkeit der Entfernung von Fortpflanzungsorganen bei Minderjährigen
  - 2022-09-23 Zeitplan für die Umsetzung des Vorhabens "Reproduktive Selbstbestimmung"
  - 2022-07-08 Wissenschaftliche Fundierung des Ausschlusses einer negativen Wirkung von mRNA-Impfstoffen auf die Fruchtbarke
  - 2020-07-31 Möglicher Zusammenhang von Unfruchtbarkeit und Entwicklungsstörungen bei Männern mit der Belastung durch hormo
DECISION: 

### Hormontherapie
- area: Gender medicine children | recurs in 6 seed Vorgänge (60% of its appearances) | its own Vorgänge: 17, of which the taxonomy MISSES 7
  - 2026-04-24 Versorgungsengpässe bei injizierbarem Östrogen für Hormonersatztherapien
  - 2026-04-02 Verfügbarkeit von injizierbarem Östrogen für Hormonersatztherapien
  - 2025-04-17 Anleitung zur medizinisch nicht überwachten Hormonbehandlung als geschlechtsangleichende Maßnahme im Jugendmag
  - 2024-04-09 Verfahrensstand des vom Bundesminister für Gesundheit angekündigten Rechtsgutachtens zum Thema Duogynon
DECISION: 

### Standesbeamter
- area: Sex based rights | recurs in 15 seed Vorgänge (100% of its appearances) | its own Vorgänge: 17, of which the taxonomy MISSES 3
  - 2025-10-17 Gesetz zur Bekämpfung der Mehrehe
  - 2024-03-07 Befugnisse von Standesbeamten bei Änderungen der Geschlechtseinträge von Kindern
  - 2007-07-06 Neunzehnte allgemeine Verwaltungsvorschrift zur Änderung der Dienstanweisung für die Standesbeamten und ihre A
DECISION: 

### Grenzkontrolle
- area: Migration | recurs in 57 seed Vorgänge (95% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 96
  - 2026-09-21 Umsetzung von Screening- und Grenzverfahren
  - 2026-09-21 Binnengrenzkontrollen an den Grenzübergängen Stadtbrücke Frankfurt (Oder), Autobahn A12 und Schienenstrecke
  - 2026-09-11 Zahl unerlaubter Einreisen und Zurückweisungen im Rahmen von Binnengrenzkontrollen seit Beginn 2026
  - 2026-09-11 Gerichtliche Entscheidungen zur Rechtmäßigkeit von Binnengrenzkontrollen
DECISION: 

### Einreisegenehmigung
- area: Migration | recurs in 35 seed Vorgänge (90% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2026-09-16 Deutsch-afghanische Beziehungen seit Machtübernahme der Taliban
  - 2026-09-11 Rechtliche Bewertung der Zurückweisungspraxis der Bundespolizei an den Binnengrenzen
  - 2026-09-08 Humanitäre Situation in Gaza - Kenntnisse und Aktivitäten der Bundesregierung
  - 2026-08-28 Prüfung von Social-Media-Konten bei Einreisen und Visa-Anträgen aus Drittstaaten
DECISION: 

### Drittstaat
- area: Migration | recurs in 28 seed Vorgänge (93% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2026-09-24 Völkerrecht konsequent umsetzen - Keine wirtschaftliche und wissenschaftliche Unterstützung der völkerrechtswi
  - 2026-09-24 Gesetz zu der Mehrseitigen Vereinbarung vom 22. Juni 2021 zwischen den zuständigen Behörden über den automatis
  - 2026-09-11 Verbringung von Schlachttieren aus Deutschland in Drittstaaten
  - 2026-09-07 Staatliche Förderung von Rüstungsexporten
DECISION: 

### Zuständigkeit
- area: Migration | recurs in 22 seed Vorgänge (69% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 91
  - 2026-09-10 Strukturelle Defizite des Bundesministeriums für Digitales und Staatsmodernisierung
  - 2026-09-07 Umsetzung des Wehrdienst-Modernisierungsgesetzes im zweiten Quartal 2026
  - 2026-08-26 ... Gesetz zur Änderung des Bundesdatenschutzgesetzes (BDSG)
  - 2026-08-21 Sicherstellung ausreichender regionaler stationärer Pflegekapazitäten
DECISION: 

### Diplomatische Vertretung
- area: Migration | recurs in 25 seed Vorgänge (76% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 90
  - 2026-09-16 Deutsch-afghanische Beziehungen seit Machtübernahme der Taliban
  - 2026-09-11 Weiterentwicklung der Übungen zur Evakuierung von Auslandsvertretungen
  - 2026-09-11 Maßnahmen im Fall des in der Türkei inhaftierten deutschen Staatsbürgers Ferdi Soylu
  - 2026-09-11 Konsularische Betreuung der Aktivistin und Journalistin Eva Marie Michelmann während ihrer Haft in Syrien
DECISION: 

### Sozialleistung
- area: Migration | recurs in 57 seed Vorgänge (69% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 89
  - 2026-09-24 Sozialleistungsmissbrauch stoppen - Lücken im Aktionsplan der Bundesregierung schließen
  - 2026-09-18 Kosten, Empfänger und Kontrolle der deutschen Ukraine-Hilfe im In- und Ausland
  - 2026-08-28 Konsequenzen aus dem EuGH-Urteil vom 4. Juni 2026 zu Sozialleistungen in Dublin-Fällen
  - 2026-08-28 Aberkennung von Sozialleistungen für ausreisepflichtige Personen in den Jahren 2025 und 2026
DECISION: 

### Straftäter
- area: Migration | recurs in 21 seed Vorgänge (75% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 86
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
  - 2026-09-11 Zahl der mit Haftbefehl gesuchten Personen und Grundsicherungsbezug
  - 2026-09-04 Stand der Prüfung möglicher Deutschland-Bezüge in den sogenannten Epstein-Files
  - 2026-09-01 Eineinhalb Jahre nach Ende des Bürgerkrieges - Sachstand zur Rückkehr nach Syrien, zum Widerruf von Schutztite
DECISION: 

### Visum
- area: Migration | recurs in 72 seed Vorgänge (91% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 84
  - 2026-09-16 Deutsch-afghanische Beziehungen seit Machtübernahme der Taliban
  - 2026-09-11 Verzögerungen bei der Visumvergabe für iranische Studierende
  - 2026-09-11 Ausgestellte Chancenkarten und Beschäftigungsquote der Inhaber
  - 2026-09-04 Zahl der an qualifizierte Drittstaatsangehörige im ersten Halbjahr 2026 ausgegebenen Chancenkarten und erfolgr
DECISION: 

### Rückführung ausreisepflichtiger Personen
- area: Migration | recurs in 128 seed Vorgänge (98% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 83
  - 2026-09-24 Fünfter Bericht der Bundesregierung zu der Überprüfung der Voraussetzungen zur Einstufung der in Anlage II zum
  - 2026-09-24 Einwanderungspolitik als Ursache der Krise im deutschen Bildungssystem benennen und konsequent angehen
  - 2026-09-24 Datengrundlage und Erfolgskontrolle bei Vollzug aufenthaltsbeendender Maßnahmen (Nachfrage zur Antwort der Bun
  - 2026-09-22 Lage der christlichen Minderheit im Jemen im Kontext des langjährigen Bürgerkriegs und der dschihadistischen B
DECISION: 

### Asylrecht
- area: Migration | recurs in 46 seed Vorgänge (85% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 81
  - 2026-09-24 Fünfter Bericht der Bundesregierung zu der Überprüfung der Voraussetzungen zur Einstufung der in Anlage II zum
  - 2026-07-03 Zusammenhang zwischen der Anwendung des Rechts auf Asyl bzw. des Freizügigkeitsgesetzes und der Anzahl an Asyl
  - 2026-06-26 Widerrufsverfahren gegenüber syrischen Schutzberechtigten im Zeitraum vom 1. Juni 2025 bis zum 31. Mai 2026
  - 2026-06-11 Klimapolitik an den Belastungsgrenzen unseres Planeten ausrichten
DECISION: 

### Ausländer
- area: Migration | recurs in 26 seed Vorgänge (58% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 81
  - 2026-09-24 Sozialleistungsmissbrauch stoppen - Lücken im Aktionsplan der Bundesregierung schließen
  - 2026-09-23 Erkenntnisse zum Kriminalitätsphänomen „Crime as a Service“
  - 2026-09-14 Rentenzahlungen und Altersarmut im Jahr 2025
  - 2026-08-28 Bearbeitung von Anträgen auf Zeugnisbewertung durch die Zentralstelle für ausländisches Bildungswesen in den l
DECISION: 

### Migrant
- area: Migration | recurs in 17 seed Vorgänge (68% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 80
  - 2026-09-23 Tatverdächtige mit Zuwandererstatus in der Polizeilichen Kriminalstatistik nach Deliktbereichen zwischen 2015 
  - 2026-09-23 Studienabschlussquote von Personen aus Hauptasylherkunftsländern an deutschen Hochschulen seit 2015
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
  - 2026-08-18 Mitteilung über eine angenommene Urkunde eines Übereinkommens der Internationalen Arbeitsorganisation
DECISION: 

### Illegale Einwanderung
- area: Migration | recurs in 49 seed Vorgänge (92% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 79
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
  - 2026-09-11 Zahl unerlaubter Einreisen und Zurückweisungen im Rahmen von Binnengrenzkontrollen seit Beginn 2026
  - 2026-09-11 Drei Monate nach Einführung des Gemeinsamen Europäischen Asylsystems - Auswirkungen und Stand der Umsetzung
  - 2026-09-08 Ergänzende Informationen zur Asylstatistik für das erste Halbjahr 2026
DECISION: 

### Flüchtling
- area: Migration | recurs in 188 seed Vorgänge (89% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 76
  - 2026-09-22 Lage der christlichen Minderheit im Jemen im Kontext des langjährigen Bürgerkriegs und der dschihadistischen B
  - 2026-09-11 Drei Monate nach Einführung des Gemeinsamen Europäischen Asylsystems - Auswirkungen und Stand der Umsetzung
  - 2026-09-10 Deutsch-ukrainische strategische Partnerschaft und Folgen der Regierungskonsultationen vom 14. April 2026
  - 2026-09-08 Ergänzende Informationen zur Asylstatistik für das erste Halbjahr 2026
DECISION: 

### Asylbewerber
- area: Migration | recurs in 265 seed Vorgänge (93% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 72
  - 2026-09-24 Fünfter Bericht der Bundesregierung zu der Überprüfung der Voraussetzungen zur Einstufung der in Anlage II zum
  - 2026-09-22 Lage der christlichen Minderheit im Jemen im Kontext des langjährigen Bürgerkriegs und der dschihadistischen B
  - 2026-09-21 Umsetzung von Screening- und Grenzverfahren
  - 2026-09-14 Folgen der Zuwanderung seit 2015 - Kriminalitätsentwicklung, öffentliche Sicherheit, Justiz, Sozialkosten und 
DECISION: 

### Flüchtlingspolitik
- area: Migration | recurs in 81 seed Vorgänge (96% of its appearances) | its own Vorgänge: 100, of which the taxonomy MISSES 70
  - 2026-09-11 Gründe für den Rückgang der Asylerstanträge im ersten Halbjahr 2026
  - 2026-09-11 Drei Monate nach Einführung des Gemeinsamen Europäischen Asylsystems - Auswirkungen und Stand der Umsetzung
  - 2026-09-09 Verhandlungen über Abschiebezentren in Drittstaaten
  - 2026-09-04 Verknüpfung deutscher GEAS-Solidaritätsbeiträge mit der EURODAC-Registrierungspflicht anderer Mitgliedstaaten
DECISION: 

### Sozialhilferecht
- area: Migration | recurs in 25 seed Vorgänge (100% of its appearances) | its own Vorgänge: 96, of which the taxonomy MISSES 66
  - 2026-09-25 Haushaltsbegleitgesetz 2027
  - 2026-08-28 Ausgestaltung der Höhe von Regelsätzen im Rahmen der Regelbedarfsermittlung
  - 2026-06-25 Einwanderung in das Sozialsystem und Sozialleistungsmissbrauch stoppen
  - 2026-05-29 Integration des Kinderzuschlags in den Regelsatz des geplanten Regelbedarfsermittlungsgesetzes
DECISION: 

### Sicherer Herkunftsstaat
- area: Migration | recurs in 53 seed Vorgänge (98% of its appearances) | its own Vorgänge: 76, of which the taxonomy MISSES 42
  - 2026-09-24 Fünfter Bericht der Bundesregierung zu der Überprüfung der Voraussetzungen zur Einstufung der in Anlage II zum
  - 2026-05-29 Ausstehender Bericht zur Überprüfung der Einstufung sicherer Herkunftsstaaten
  - 2026-04-13 Kooperationen der Bundesregierung mit Drittstaaten im Zusammenhang mit der möglichen Einrichtung von "Return H
  - 2026-04-10 Umgang mit LGBTIQ+-Personen im Senegal und in Ghana im Kontext sicherer Herkunftsstaaten
DECISION: 

---

## Already covered (the taxonomy matches the descriptor's own name)

- Aufenthaltsrecht -> Migration via Aufenthaltsrecht*
- Familiennachzug -> Migration via Familiennachzug*
- Asylverfahren -> Migration via Asylverfahren*
- Elterngeld -> Marriage family via Elterngeld*
- Abschiebung -> Migration via Abschiebung*
- Schwangerschaftsabbruch -> Abortion via Schwangerschaftsabbr*
- Menschenhandel -> Prostitution via Menschenhandel*
- Meinungsfreiheit -> Free speech online safety via Meinungsfreiheit*
- Kindergrundsicherung -> Marriage family via Kindergrundsicherung*
- Religionsfreiheit -> Freedom of religion via Religionsfreiheit*
- Eheschließung -> Marriage family via Eheschließung*
- Familienpolitik -> Marriage family via Familienpolitik*
- Prostitution -> Prostitution via Prostitution*
- Präimplantationsdiagnostik -> Surrogacy embryology via Präimplantationsdiagnostik*
- Familienförderung -> Marriage family via Familienförderung*
- Sterbehilfe -> Assisted dying via Sterbehilfe*
- Hasskriminalität -> Free speech online safety via Hasskriminalität*
- Kinderehe -> Marriage family via Kinderehe*
- Eingetragene Lebenspartnerschaft -> Marriage family via Lebenspartnerschaft*
- Reproduktionsmedizin -> Surrogacy embryology via Reproduktionsmedizin*
- Kindergeld -> Marriage family via Kindergeld*
- Alleinerziehender -> Marriage family via Alleinerziehende*
- NS-Euthanasieprogramm -> Assisted dying via Euthanasie*
- Kirchenasyl -> Freedom of religion via Kirchenasyl*
- Elternzeit -> Marriage family via Elternzeit*
- Volksverhetzung -> Free speech online safety via Volksverhetzung*
- Zwangsheirat -> Prostitution via Zwangsheirat*
- Leihmutter -> Surrogacy embryology via Leihmutter*
- Vereinbarkeit von Familie und Beruf -> Marriage family via Vereinbarkeit von Familie und Beruf
- Desinformation -> Free speech online safety via Desinformation*
- Migration -> Migration via Migration*
- Abschiebungshaft -> Migration via Abschiebung*
- Künstliche Befruchtung -> Surrogacy embryology via künstliche Befruchtung
- Embryonenschutz -> Surrogacy embryology via Embryonenschutz*
- Sterbebegleitung -> Assisted dying via Sterbebegleitung*
- Jugendmedienschutz -> Free speech online safety via Jugendmedienschutz*
- Religionsgemeinschaft -> Freedom of religion via Religionsgemeinschaft*
- Einbürgerung -> Migration via Einbürgerung*
- Zuhälterei -> Prostitution via Zuhälterei*
- Abtreibungspille -> Abortion via Abtreibung*, Abtreibungspille*
- Religionsunterricht -> Freedom of religion via Religionsunterricht*
