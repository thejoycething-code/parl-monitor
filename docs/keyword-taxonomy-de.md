# Parliamentary Monitor: German keyword taxonomy

**Version 0.4 | 22 September 2026 | Owner: Christopher | Status: AI FIRST DRAFT, NOT YET VERIFIED**

## Purpose

The German-language filter layer, for the Bundestag and the sixteen Land
parliaments. The **areas are identical to the English taxonomy** and carry the
same keys: they are CitizenGO's positions, not England's vocabulary. Only the
terms differ.

**This file is the master.** `config/taxonomy-de.yaml` is generated from it:
edit here, then run `python3 tools/generate_taxonomy.py --lang de`.

## Status: this is a first draft and must be verified

Drafted by Claude on 22 September 2026 at Christopher's instruction, to be
checked by the German team before anything is scored against it. Treat every
term as a proposal. Two kinds of error are likely and only a native political
reader will catch them: terms that are correct German but not the words the
Bundestag actually uses, and terms that name the wrong side of a debate.

Nothing has been measured against a German corpus. Every English area carries
counts from the corpus ("measured across 26,362 rows"); this file carries
none, because there is no German corpus yet. The 68 recorded votes now in
`de_divisions` are far too few to measure a term against. **Measure before
promoting anything to tier 1 on the strength of this draft.**

## Why German needs its own file rather than extra lines in the English one

Matching is substring-based, and the two languages hide inside each other's
words. `Rat` (council) sits inside "corporate"; `Tat` (act) inside "state";
`Amt` (office) inside "Parliament"; `Bund` inside "profund". A German term
added to the English yaml would fire on English text and nobody would see why.

## German-specific matching traps

These shaped every choice below and matter more here than in English.

- **Compounds are a gift.** German builds long precise nouns:
  `Schwangerschaftsabbruch`, `Selbstbestimmungsgesetz`, `Leihmutterschaft`,
  `Konversionstherapie`. They are unambiguous and belong at tier 1. Prefer the
  compound to its parts every time.
- **Short words are a trap, worse than in English.** `Ehe` (marriage) is a
  substring of `gehen`, `stehen`, `geschehen`. `Leben` (life) sits inside
  `Lebensmittel` (food) and `Lebenshaltungskosten` (cost of living). `Recht`
  sits inside `Rechtsextremismus` and `Gerechtigkeit`. None of these may ever
  be a bare term; each appears below only as part of a compound, a quoted
  phrase, or guarded.
- **ALMOST EVERY GERMAN NOUN TERM NEEDS A TRAILING `*`.** This is the single
  most important rule in this file and the draft got it wrong at first. A term
  without `*` is anchored on both sides (`src/filter.py:_compile_term` puts
  `(?![a-z0-9])` after it), so `Sterbehilfe` does **not** match
  `Sterbehilfegesetz` and `Elternrecht` does **not** match `Elternrechts`.
  German adds a genitive `-s`/`-es` and builds compounds constantly, so a bare
  noun matches only the one form nobody writes. Measured on the real corpus:
  the Bundestag's own bill was titled `Suizidhilfegesetz`, and the bare term
  matched nothing until it became `Suizidhilfe*`. 131 terms were converted to
  stems at v0.3 for this reason.
- **The `*` is safe only on a long, distinctive stem.** It removes the right
  boundary, so `Leben*` would match `Lebensmittel`. `Lebensschutz*` does not,
  because the stem itself is distinctive. That is the same reason the short
  words in the exclusions list can never be terms at all: with `*` they would
  match half the language, and without it they would match nothing.
- **Inflection changes the stem, so a plural is not a superstring.**
  `Abbruch` → `Abbrüche`: the umlaut means the singular is NOT contained in
  the plural, and no `*` helps. Where a word inflects that way the term is cut
  before the vowel (`"Schwangerschaftsabbr*"`).
- **Umlauts and ß are written properly.** Official German text uses `ä ö ü ß`,
  so the terms do. Where a source might transliterate (`ae oe ue ss`), the
  variant is added explicitly; it is not assumed.
- **Never write a German noun in ALL CAPS.** The filter treats an all-caps
  term as case-sensitive, and German capitalises every noun anyway, so an
  all-caps term would simply never match.

## Issue areas

### 1. Abortion {#1_abortion}

- **Tier 1:** "Schwangerschaftsabbr*"; "Abtreibung*"; "§ 218"; "§218"; "Paragraf 218"; "Paragraph 218"; "§ 219a"; "§219a"; Schwangerschaftskonfliktberatung*; "Schwangerschaftskonflikt*"; Fristenregelung*; Spätabtreibung*; Abtreibungspille*; Mifegyne; Mifepriston; Lebensschutz*; Lebensrechtsbewegung*; "ungeborene* Leben"; Embryonenschutzgesetz*; "Beratungsschein*"; "Marsch für das Leben"
- **Tier 2:** "reproduktive Rechte"; "reproduktive Gesundheit"; "sexuelle und reproduktive Gesundheit"; "selbstbestimmte Schwangerschaft"; Schwangerschaftskonfliktgesetz*; Pflichtberatung*; Gehsteigbelästigung*; "Bürgersteigbelästigung*"; Beratungspflicht*; "ungeboren*"; Totgeburt*; "Fehlgeburt*"; Pränataldiagnostik*; "vorgeburtlich*"
- **Notes:** `Marsch für das Leben` joined at v0.4 (22 September 2026), measured against DIP: 1 Vorgang since 2024 and the current taxonomy missed it, on the disruption of the march by counter-demonstrators. It is the German pro-life movement naming itself, the same reason `Lebensschutz` is here. `Schwangerschaftsabbruch` is the legal and parliamentary term; `Abtreibung` is the political and campaigning one, used by both sides. Both at tier 1 as stems, because both inflect. `§ 218 StGB` is the criminal-code section and is how the whole German abortion debate is named, so the bare section number is included in the spellings the Bundestag actually prints (`§ 218`, `§218`, `Paragraf 218`; the official orthography is `Paragraf`, but `Paragraph` persists in older text). `§ 219a` was the advertising ban repealed in 2022; kept because repeal-reversal and the record of the fight both use it. `Gehsteigbelästigung` is the German for pavement harassment outside clinics, the buffer-zone fight, and was made an offence in 2025 -- it sits at tier 2 because the vocabulary is contested and triage should read it. `Lebensschutz` and `Lebensrechtsbewegung` name the pro-life movement in its own words, which is precisely how a German text refers to us. NOT included: bare `Leben`, `Fristen`, `Beratung`, all of which are common administrative words; and `Embryo` alone, which belongs to area 10 and would double-tag every IVF item.

### 2. Assisted dying and end of life {#2_assisted_dying}

- **Tier 1:** Sterbehilfe*; "assistierter Suizid"; "assistierte* Selbsttötung"; Suizidassistenz*; Suizidbeihilfe*; Suizidhilfe*; "geschäftsmäßige Förderung der Selbsttötung"; "§ 217"; "§217"; Sterbebegleitung*; Tötung auf Verlangen; Euthanasie*
- **Tier 2:** Palliativmedizin*; Palliativversorgung*; Hospiz*; "Hospizarbeit*"; Patientenverfügung*; "Selbstbestimmung am Lebensende"; Suizidprävention*; "würdevolles Sterben"; Sterbewunsch*
- **Notes:** `Suizidhilfe` joined at v0.2 (22 September 2026), caught by the regression test: the 2021-2025 Bundestag voted on a bill actually titled `Suizidhilfegesetz`, and the draft carried `Suizidassistenz` and `Suizidbeihilfe` but not the plainest compound of the three. `§ 217 StGB` was the ban on organised assisted suicide struck down by the Constitutional Court in February 2020; every subsequent Bundestag bill is framed against that judgment, so the section number is tier 1. `geschäftsmäßige Förderung der Selbsttötung` is the exact statutory phrase and worth carrying verbatim. `Euthanasie` is included but is historically loaded in German -- it names the Nazi killing programme, and contemporary debate avoids it -- so expect it to fire mostly on historical and commemorative items; the German team should say whether to keep it. `Tötung auf Verlangen` (§ 216, killing on request) is the separate offence that stays in force. Palliative and hospice vocabulary is the positive flank, tier 2, as in English.

### 3. Gender medicine and children {#3_gender_medicine_children}

- **Tier 1:** Pubertätsblocker*; "pubertätsblockierend*"; Pubertätsblockade*; "gegengeschlechtliche Hormone"; "geschlechtsangleichende Operation*"; "geschlechtsangleichende Behandlung*"; Geschlechtsdysphorie*; "Geschlechtsinkongruenz*"; Transsexuellengesetz*; "Trans* bei Kindern"; Detransition*
- **Tier 2:** "geschlechtliche Identität" [with: Kind, Kinder, Jugendliche, Minderjährige, Schule, Behandlung]; "Hormonbehandlung" [with: Kind, Kinder, Jugendliche, Minderjährige, Geschlecht]; "Trans-Jugendliche"; "geschlechtsspezifisch*" [with: Kind, Jugendliche, Behandlung, Medizin]; "Indikationsstellung*"; "S3-Leitlinie"
- **Notes:** `Pubertätsblocker` is the exact German term and unambiguous, tier 1. The German debate runs through the `S3-Leitlinie` (the medical guideline on gender incongruence in minors), which is the nearest equivalent to the Cass Review as a named object, so it is included at tier 2 -- guidelines are numbered this way across all of medicine, so it needs triage. `Transsexuellengesetz` is the old law replaced by the Selbstbestimmungsgesetz in 2024; kept because repeal debates and transitional provisions still name it. `Geschlechtsdysphorie` and `Geschlechtsinkongruenz` are the two competing clinical framings and both appear. The guarded terms exist because `geschlechtliche Identität` and `geschlechtsspezifisch` are everywhere in German equality boilerplate; without the child guard they would tag every gender-mainstreaming item.

### 4. Conversion practices {#4_conversion_practices}

- **Tier 1:** Konversionstherapie*; "Konversionsbehandlung*"; "Umpolung*"; Selbstbestimmungsstärkungsgesetz*; "Gesetz zum Schutz vor Konversionsbehandlungen"; Konversionsmaßnahme*
- **Tier 2:** "seelsorgerisch*" [with: Konversion, Verbot, Therapie, Behandlung, Identität]; Seelsorge [with: Konversion, Verbot, Therapie, Behandlung]; "geistlicher Beistand" [with: Konversion, Verbot, Therapie]; "Elterngespräch*" [with: Konversion, Verbot, Identität]; "religiöse Beratung" [with: Konversion, Verbot, Therapie]
- **Notes:** Germany banned conversion treatment for minors in 2020 (`Gesetz zum Schutz vor Konversionsbehandlungen`), earlier than the UK, so the live German question is the scope of the existing ban rather than whether to legislate. `Umpolung` is the older colloquial term and still appears in debate. The guarded pastoral vocabulary mirrors the English area-4 carve-out list and exists for the same reason: whether ordinary pastoral conversation and a parent's advice fall inside the ban is the contested ground, and `Seelsorge` unguarded would tag every church-funding item. Every guard here needs a German reader's eye: these are the terms most likely to be the wrong words.

### 5. Sex-based rights and single-sex spaces {#5_sex_based_rights}

- **Tier 1:** Selbstbestimmungsgesetz*; "Geschlechtseintrag*"; "Personenstandsgesetz*"; "Personenstandsänderung*"; "drittes Geschlecht"; Frauenschutzraum*; "Schutzräume für Frauen"; "biologisches Geschlecht"; "Istanbul-Konvention"; Istanbulkonvention*; Femizid*; Gewaltschutzgesetz*
- **Tier 2:** "geschlechtergerecht*"; Gendern; "geschlechtergerechte Sprache"; Frauenquote*; "Frauenhaus" [with: Geschlecht, Selbstbestimmung, Schutz, trans]; Umkleide [with: Geschlecht, Schule, Schwimmbad, trans]; Frauensport*; "Gleichstellungsgesetz*"; "geschlechtsspezifische Gewalt"; Gleichstellungsbeauftragte*
- **Notes:** `Femizid` (8 Vorgänge, all missed) and `Gewaltschutzgesetz` (9, all missed) joined at v0.4, measured against DIP. `Frauenrechte` was probed and REJECTED: 8 hits, but the evidence was foreign-aid projects in southern Africa, not the sex-based-rights fight. `Quotenregelung` was rejected the same way -- its hits were defence-spending quotas. The `Selbstbestimmungsgesetz` (Self-Determination Act, in force November 2024) is the German self-ID law and the single most important term in this file. `Geschlechtseintrag` and `Personenstandsänderung` are how a change of registered sex is named administratively. The Istanbul Convention appears in both German spellings. `Gendern` (the verb for using gender-inclusive language) names a live and specifically German culture-war fight that has no English equivalent term; at tier 2 because it is also just a linguistic topic. `Frauenhaus` (women's refuge) is guarded: unguarded it tags every refuge-funding item, which is not our ground unless the admission question is at stake.

### 6. Parental rights and education {#6_parental_rights_education}

- **Tier 1:** Elternrecht*; "elterliches Erziehungsrecht"; "Erziehungsrecht der Eltern"; Sexualkundeunterricht*; Sexualpädagogik*; "sexuelle Bildung"; Aufklärungsunterricht*; Schulpflicht [with: Eltern, Befreiung, Weltanschauung, Religion, häuslich]; Hausunterricht*; "häuslicher Unterricht"; Bildungsplan [with: Sexual, Vielfalt, Gender, Elternrecht]; "Queer-Beauftragte*"; Regenbogenportal*; "Aktionsplan Queer"
- **Tier 2:** "Vielfalt" [with: Schule, Unterricht, Lehrplan, sexuell, Bildungsplan]; "sexuelle Vielfalt"; Elternbeirat*; Erziehungsauftrag*; "Mediennutzung" [with: Kinder, Jugendliche, Schule, Verbot]; "soziale Medien" [with: Jugendliche, Kinder, Minderjährige, "unter 16", "unter 18", Schule, Smartphone]; Smartphoneverbot*; Handyverbot [with: Schule, Unterricht]; Jugendmedienschutz*; Schulverweigerung*
- **Notes:** The federal queer-policy apparatus joined at v0.4, measured against DIP and all missed by the taxonomy: `Queer-Beauftragte` (2), `Regenbogenportal` (1, on the closure of the portal itself) and `Aktionsplan Queer` (4). This is the machinery our German audience argues with, and none of it was catchable. `Elternrecht` is constitutional in Germany -- Article 6 of the Basic Law -- which makes it a stronger and more frequently used term than its English counterpart, so it is tier 1 unguarded. `Schulpflicht` (compulsory schooling) is guarded because it is also routine truancy administration; Germany effectively prohibits home education, so `Hausunterricht` items are about the prohibition itself. `Bildungsplan` is guarded after the Baden-Württemberg curriculum fight, which is the German precedent for the sexual-diversity-in-curriculum dispute. The guarded `soziale Medien` line mirrors English v1.8 exactly, including the under-16 guards, and for the same measured reason: unguarded it is press-office traffic. `Handyverbot` and `Smartphoneverbot` name the school phone-ban debate now live in several Länder.

### 7. Free speech, privacy and civil liberties {#7_free_speech_online_safety}

- **Tier 1:** Meinungsfreiheit*; "Netzwerkdurchsetzungsgesetz*"; NetzDG; Digitale-Dienste-Gesetz; "Chatkontrolle*"; Vorratsdatenspeicherung*; "Uploadfilter*"; Bestandsdatenauskunft*; "Zensur" [with: Meinung, Internet, Plattform, Rede, Netz]; Volksverhetzung*; "§ 188"; "§188"; "Paragraf 188"; Politikerbeleidigung*; "Digital Services Act"; "Trusted Flagger"; Staatstrojaner*
- **Tier 2:** Hassrede*; "Hasskriminalität*"; Desinformation*; Faktenchecker*; "Melde- und Abhilfeverfahren"; Plattformregulierung*; "digitale Gewalt"; Medienstaatsvertrag*; Bundespolizeigesetz [with: Überwachung, Daten]; Gesichtserkennung*; Meldestelle [with: Inhalte, strafbar, Internet, Online, Plattform]
- **Notes:** THE BIGGEST v0.4 GAIN, all measured against DIP and all previously missed. `§ 188 StGB` is the politician-insult provision and the whole German free-speech flashpoint: 6 Vorgänge, every one on point (its reform, its extension to journalists, its abolition), and the Bundestag prints it both with and without the space, as it does § 218. `Politikerbeleidigung` (3, every one ours) names the offence in the words the abolition bills use. `Digital Services Act` (19, 17 missed) is used in German text under its ENGLISH name, which `Digitale-Dienste-Gesetz` never matches -- the same lesson the English taxonomy learned when "freedom of speech" matched nothing because only "free speech" was a term. `Trusted Flagger` (3) and `Staatstrojaner` (2) are the DSA flagging fight and state surveillance software. `Meldestelle` is GUARDED: 18 hits, mostly the Zentrale Meldestelle für strafbare Inhalte im Internet, which is ours, but the externe Meldestelle des Bundes is whistleblower plumbing, which is not. `NetzDG` is the German platform-takedown law that became the template other countries copied, and it is written exactly that way, so both the abbreviation and the full `Netzwerkdurchsetzungsgesetz` are tier 1. NetzDG is all-caps and therefore case-sensitive under the filter convention, which is correct here because that is how it is always printed. `Chatkontrolle` is the German name for the EU CSA-regulation client-side-scanning fight, which the EU monitor tracks as the ePrivacy derogation -- the same fight in two vocabularies. `Volksverhetzung` (incitement) is tier 1 because prosecutions under it are the German free-speech flashpoint, though the German team should confirm we want every such case. `Zensur` is guarded: alone it catches historical and foreign-affairs usage.

### 8. Freedom of religion or belief {#8_freedom_of_religion}

- **Tier 1:** Religionsfreiheit*; "Glaubensfreiheit*"; Christenverfolgung*; "Verfolgung von Christen"; Kirchenasyl*; Religionsunterricht*; "Kopftuchverbot*"; Kruzifix*; Gotteslästerung*; "§ 166"; Blasphemieparagraf*; Körperschaftsstatus*
- **Tier 2:** Kirchensteuer*; Staatsleistungen*; "kirchliches Arbeitsrecht"; Gottesdienst [with: Verbot, Beschränkung, Freiheit, Recht]; Beschneidung*; Schächten; "religiöse Symbole"; Islamismus*; "Islamistisch*"; Religionsgemeinschaft*; Antisemitismus*; Islamfeindlichkeit*
- **Notes:** `Antisemitismus` (41 Vorgänge) and `Islamfeindlichkeit` (8) joined at TIER 2 at v0.4. Both are religious hatred and so belong to freedom of religion or belief, but 41 items is the volume at which a term stops being a filter, and the German national antisemitism strategy is mostly administration. Triage should score 2+ only where religious practice or belief is what is at stake. `§ 166 StGB` is the blasphemy provision, and its repeal is periodically proposed, so both the section number and `Blasphemieparagraf` are carried. `Staatsleistungen` are the historic state payments to the churches whose replacement is a standing constitutional question and a live Bundestag bill. `Körperschaftsstatus` is the public-corporation status that defines a religious community's legal standing in Germany, with no English equivalent. `Kirchenasyl` (church sanctuary for migrants) sits here rather than in area 11 because the contested question is the church's freedom to offer it. `Beschneidung` (circumcision) and `Schächten` (religious slaughter) are the two recurring religious-practice fights and are tier 2 because both also appear as pure animal-welfare or medical items.

### 9. Marriage and family {#9_marriage_family}

- **Tier 1:** "Ehe für alle"; Eheschließung*; Ehegattensplitting*; "Verantwortungsgemeinschaft*"; Familienförderung*; Elterngeld*; Kindergrundsicherung*; "Familienbild*"; Familienpolitik*; Kinderehe*
- **Tier 2:** Kindergeld*; Elternzeit*; "Vereinbarkeit von Familie und Beruf"; Alleinerziehende*; Adoptionsrecht*; "gleichgeschlechtliche Paare"; Lebenspartnerschaft*; Unterhaltsrecht*; "Kinderrechte ins Grundgesetz"; Familienstartzeit*; Sorgerecht*
- **Notes:** `Kinderehe` joined at tier 1 at v0.4 (7 Vorgänge, all missed); forced marriage of minors is our ground and had no term at all. `Familienstartzeit` (3, the new paid partner leave) and `Sorgerecht` (1) at tier 2. **`Ehe` never appears bare**, and this is the sharpest example of the German trap: `Ehe` is a substring of `gehen`, `stehen` and `geschehen`, so a bare term would match a large share of all German political text. Every marriage term here is therefore a compound or a quoted phrase. `Verantwortungsgemeinschaft` is the coalition's proposed non-marital partnership status and a live legislative object. `Ehegattensplitting` is the joint-taxation rule whose abolition is repeatedly proposed and which CitizenGO's German audience reads as a family-policy question. `Kinderrechte ins Grundgesetz` (children's rights into the Basic Law) is the recurring constitutional proposal that the parental-rights side opposes; it sits at tier 2 here and cross-tags naturally with area 6.

### 10. Surrogacy and embryology {#10_surrogacy_embryology}

- **Tier 1:** Leihmutterschaft*; "Leihmutter*"; Eizellspende*; Embryonenspende*; Präimplantationsdiagnostik*; PID; "Embryonenschutz*"; Klonen*; "Keimbahneingriff*"; Samenspende*; "Abstammungsrecht*"; Fortpflanzungsmedizin*
- **Tier 2:** Kinderwunschbehandlung*; "künstliche Befruchtung"; Reproduktionsmedizin*; "Social Freezing"; Fortpflanzungsmedizingesetz*; Stammzellforschung*; "genetische Selektion"
- **Notes:** Bare `Fortpflanzungsmedizin` joined at v0.4: the taxonomy carried only `Fortpflanzungsmedizingesetz`, and the Kommission report on reproductive medicine -- the vehicle through which liberalisation is being argued -- names the field, not the Act. Germany's `Embryonenschutzgesetz` of 1990 is among the most restrictive in Europe and bans both surrogacy and egg donation, so the live German question is liberalisation -- the opposite direction from the UK. That makes this area unusually important for Germany and unusually easy to filter, because the statutory terms are precise. `PID` is an abbreviation and all-caps, therefore case-sensitive, which is right: lower-case `pid` would match inside other words. `Abstammungsrecht` (parentage law) is the reform vehicle through which surrogacy recognition is being argued.

### 11. Migration {#11_migration}

- **Tier 1:** Familiennachzug*; "subsidiär Schutzberechtigte"; Asylbewerberleistungsgesetz*; "sichere Herkunftsstaaten"; Abschiebung*; "Gemeinsames Europäisches Asylsystem"; Zurückweisung [with: Grenze, Asyl, Migration]; Aufenthaltsrecht*
- **Tier 2:** "Migration*"; Asylverfahren*; Einbürgerung*; Bleiberecht*; Duldung [with: Aufenthalt, Asyl, Abschiebung]; Integrationskurs*; "irreguläre Migration"; Seenotrettung*; Dublin-Verfahren
- **Notes:** Area 11 is collated and never campaigned, and is hidden on every surface, so these terms exist to file items correctly rather than to raise them. They are drafted more briefly than the rest for that reason. `Duldung` and `Zurückweisung` are guarded because both are ordinary administrative and legal words outside migration.

### 12. Prostitution, trafficking and sexual exploitation {#12_prostitution}

- **Tier 1:** Prostitutionsschutzgesetz*; "Prostituiertenschutzgesetz*"; Sexkaufverbot*; "Nordisches Modell"; Menschenhandel*; Zwangsprostitution*; "sexuelle Ausbeutung"; Freierbestrafung*; Zuhälterei*; Zwangsheirat*
- **Tier 2:** Prostitution*; Sexarbeit*; "Sexarbeiterin*"; Bordell*; "Missbrauchsdarstellung*"; "sexualisierte Gewalt"; Loverboy*; "Anwerbung" [with: Prostitution, Menschenhandel, Ausbeutung]
- **Notes:** `Zwangsheirat` joined at v0.4 to sit beside `Zwangsprostitution`, which was here from the start while forced marriage was not. Germany legalised prostitution in 2002 and is the largest market in Europe, so this area carries more German parliamentary traffic than its English counterpart. `Sexkaufverbot` and `Nordisches Modell` name the abolitionist position CitizenGO supports; `Sexarbeit` names the opposing frame, and both must be caught. `Missbrauchsdarstellung` replaced `Kinderpornografie` in German legal usage and is the current statutory word. `Loverboy` is the German term for the grooming-into-prostitution method and is used in parliamentary questions.

## Global exclusions

- **Terms:** Ehe; Leben; Recht; Kind; Familie; Geschlecht; Beratung; Schutz; Bildung; Vielfalt; Gewalt; Zensur; Migration; Prostitution
- **Notes:** These are the bare words that must never be promoted to a term on their own, recorded here so the reason survives. Each is either a substring of unrelated common words (`Ehe` in `gehen`, `Recht` in `Gerechtigkeit`, `Leben` in `Lebensmittel`) or so frequent in German political text that it would tag everything (`Schutz`, `Bildung`, `Familie`). Where the concept is genuinely needed it appears above as a compound, a quoted phrase, or guarded. `Migration` and `Prostitution` appear as tier-2 terms in their own areas deliberately and are listed here only as a reminder that they are broad; the exclusions list is advisory prose, not a filter input.
