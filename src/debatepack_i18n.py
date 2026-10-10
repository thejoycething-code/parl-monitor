"""The words around a country debate pack, in the country's language.

src/country_debatepack.py writes the pack a campaigner reads (pack.md,
checklist.md) in the country's own language, as the German briefs are in
German (docs/debate-pack-social.md, the DE pack). Titles, names and
positions are always the source's own words, verbatim; only the frame
around them is translated here. The README stays in English (it is for
whoever runs the tool).

Written by Claude on 10 October 2026, without a native read (as X4 approved
for the term lists). The machine markers in checklist.md (`### group:`,
`### member:`, `ONSIDE:`, `NOTE:`) are never translated, so one parser reads
every language; the yes and no words each language accepts are below.

No em dashes, British spelling in the English.
"""

from __future__ import annotations

# Country -> the language its pack is written in. Belgium: Dutch, the
# language the store's headings use first (be_divisions.heading_nl).
# Switzerland: German, the language the edition shows first.
LANG = {
    "it": "it", "ch": "de", "fr": "fr", "nl": "nl", "be": "nl", "at": "de", "pl": "pl",
    "pt": "pt", "br": "pt", "hr": "hr", "sk": "sk", "hu": "hu",
    "es": "es", "ar": "es", "mx": "es", "cl": "es", "pe": "es", "ec": "es", "do": "es",
    "sv": "es", "gt": "es", "co": "es", "bo": "es", "uy": "es", "pa": "es", "hn": "es",
}

TASK_KEYS = ("task_reading", "task_agenda", "task_text", "task_members", "task_speakers",
             "task_after")

TEXT = {
    "en": {
        "other_votes": "{n} more vote(s) on this bill (amendments, articles, procedure) are not shown; their keys are in pack.json.",
        "title": "Debate pack",
        "sample": "SAMPLE: built from a scoping store with test confirmations. Never send.",
        "built": "Built on {today} from the store; nothing was fetched.",
        "debate_date": "Debate date",
        "section_item": "The item",
        "kind": "Kind",
        "watched": "On CitizenGO's watchlist",
        "areas": "Our ground",
        "bill": "Bill or dossier",
        "link": "Link",
        "section_agenda": "On the agenda",
        "agenda_none": "No agenda point found for this item between {a} and {b}.",
        "agenda_uncollected": ("The agenda for this country is not collected yet, so the slot is "
                               "not known: check the chamber's own programme."),
        "section_bill_votes": "Recorded votes on this bill",
        "bill_votes_none": "No recorded vote on this bill in the store yet.",
        "abstain": "Abstain",
        "by_group": "By group",
        "section_topic": "Past votes on this topic",
        "topic_none": "No earlier recorded vote on this topic in the store.",
        "section_place": "5CA placement",
        "place_awaiting": ("Awaiting sign-off: nobody is placed. CitizenGO's reading of these "
                           "votes has not been confirmed by a named person yet, so this pack "
                           "shows what each member did and makes no claim about whose side "
                           "they are on."),
        "place_note": ("Placements come only from readings a named person has confirmed in "
                       "config/{cc}_stance.yaml ({n} confirmed on this topic)."),
        "awaiting_cell": "awaiting sign-off",
        "not_placed": "not placed",
        "section_speakers": "Likely speakers",
        "speakers_none": ("The source publishes no speakers' list before the debate. When it "
                          "does, rebuild the pack with --speakers \"Name; Name\"; until then the "
                          "members to watch below are the ones to read first."),
        "speakers_given": "Named for this debate",
        "not_in_roster": "not found in the member list",
        "authors": "Authors of the bill",
        "section_watch": "Members to watch",
        "watch_intro": "Members who broke with their group's majority on this bill or topic.",
        "watch_none": "Nobody broke with their group on these votes.",
        "broke": "{pos} while most of {party} voted {major}",
        "section_members": "Members",
        "members_intro": ("Every member with a recorded position on this bill or topic. "
                          "Positions are the record's own words."),
        "col_member": "Member", "col_group": "Group", "col_bill": "On this bill",
        "col_topic": "On this topic", "col_5ca": "5CA", "col_profile": "Profile",
        "no_record": "no record",
        "derived_note": "Positions marked * are DERIVED from the group's vote (X5), not the member's own record.",
        "profile": "profile",
        "no_member_votes": ("This country's source publishes no member-level votes, so the pack "
                            "holds the item and the agenda only."),
        "section_sources": "Sources",
        "check_title": "Campaigner checklist",
        "check_before": "Before the debate",
        "task_reading": "Confirm CitizenGO's reading of the votes in config/{cc}_stance.yaml (a named person signs).",
        "task_agenda": "Check the slot on the chamber's own agenda: dates move.",
        "task_text": "Read the text that is actually being debated, not only its title.",
        "task_members": "Agree which members to contact, from the groups and members below.",
        "task_speakers": "When the speakers' list is published, rebuild the pack with --speakers.",
        "task_after": "After the debate: record the vote and its reading so the 5CA updates.",
        "check_intro": ("One line per group and per member to watch. Write yes or no after "
                        "ONSIDE:. Nothing is treated as onside until you have. Blank is not "
                        "agreement."),
        "check_markers": "Do not edit the ### lines.",
        "check_groups": "Groups",
        "check_members": "Members",
        "record": "record",
        "chamber": "Chamber",
        "summary": "{n} position(s) on this topic",
        "and_more": "and {n} more",
        "yes": ("yes", "y"), "no": ("no", "n"),
        "areas_labels": {
            1: "abortion", 2: "assisted dying", 3: "gender medicine and children",
            4: "conversion practices", 5: "sex-based rights", 6: "parental rights and education",
            7: "free speech and civil liberties", 8: "religious freedom", 9: "marriage and family",
            10: "surrogacy and embryology", 11: "migration", 12: "prostitution and trafficking",
            13: "organ donation", 14: "gambling and betting", 15: "drug decriminalisation"},
    },
    "es": {
        "other_votes": "Otras {n} votaciones sobre este proyecto (enmiendas, artículos, trámite) no se muestran; sus claves están en pack.json.",
        "title": "Dosier del debate",
        "sample": "MUESTRA: hecho con un almacén de prueba y confirmaciones de prueba. No enviar.",
        "built": "Preparado el {today} a partir del almacén; no se ha descargado nada.",
        "debate_date": "Fecha del debate",
        "section_item": "El asunto",
        "kind": "Tipo",
        "watched": "En la lista de seguimiento de CitizenGO",
        "areas": "Nuestro terreno",
        "bill": "Proyecto o expediente",
        "link": "Enlace",
        "section_agenda": "En el orden del día",
        "agenda_none": "No hay ningún punto del orden del día sobre este asunto entre el {a} y el {b}.",
        "agenda_uncollected": ("El orden del día de este país aún no se recoge, así que no se "
                               "conoce el turno: consulte la programación de la propia cámara."),
        "section_bill_votes": "Votaciones registradas sobre este proyecto",
        "bill_votes_none": "Aún no hay ninguna votación registrada sobre este proyecto.",
        "abstain": "Abstención",
        "by_group": "Por grupo",
        "section_topic": "Votaciones anteriores sobre este tema",
        "topic_none": "No hay votaciones anteriores registradas sobre este tema.",
        "section_place": "Clasificación 5CA",
        "place_awaiting": ("Pendiente de firma: no se clasifica a nadie. La lectura de CitizenGO "
                           "sobre estas votaciones aún no la ha confirmado una persona con "
                           "nombre, así que este dosier muestra lo que hizo cada miembro y no "
                           "dice de qué lado está nadie."),
        "place_note": ("Las clasificaciones salen solo de lecturas confirmadas por una persona "
                       "con nombre en config/{cc}_stance.yaml ({n} confirmadas sobre este tema)."),
        "awaiting_cell": "pendiente de firma",
        "not_placed": "sin clasificar",
        "section_speakers": "Probables oradores",
        "speakers_none": ("La fuente no publica la lista de oradores antes del debate. Cuando "
                          "lo haga, rehaga el dosier con --speakers \"Nombre; Nombre\"; hasta "
                          "entonces, lea primero a los miembros a seguir de abajo."),
        "speakers_given": "Nombrados para este debate",
        "not_in_roster": "no aparece en la lista de miembros",
        "authors": "Autores del proyecto",
        "section_watch": "Miembros a seguir",
        "watch_intro": "Miembros que se apartaron de la mayoría de su grupo en este proyecto o tema.",
        "watch_none": "Nadie se apartó de su grupo en estas votaciones.",
        "broke": "{pos} cuando la mayoría de {party} votó {major}",
        "section_members": "Miembros",
        "members_intro": ("Todos los miembros con una posición registrada sobre este proyecto o "
                          "tema. Las posiciones son las palabras del propio registro."),
        "col_member": "Miembro", "col_group": "Grupo", "col_bill": "En este proyecto",
        "col_topic": "En este tema", "col_5ca": "5CA", "col_profile": "Perfil",
        "no_record": "sin registro",
        "derived_note": "Las posiciones con * se DERIVAN del voto del grupo (X5), no son el registro propio del miembro.",
        "profile": "perfil",
        "no_member_votes": ("La fuente de este país no publica votos individuales, así que el "
                            "dosier recoge solo el asunto y el orden del día."),
        "section_sources": "Fuentes",
        "check_title": "Lista de control para la campaña",
        "check_before": "Antes del debate",
        "task_reading": "Confirmar la lectura de CitizenGO de las votaciones en config/{cc}_stance.yaml (firma una persona con nombre).",
        "task_agenda": "Comprobar el turno en el orden del día de la propia cámara: las fechas cambian.",
        "task_text": "Leer el texto que de verdad se debate, no solo su título.",
        "task_members": "Acordar a qué miembros contactar, a partir de los grupos y miembros de abajo.",
        "task_speakers": "Cuando se publique la lista de oradores, rehacer el dosier con --speakers.",
        "task_after": "Después del debate: registrar la votación y su lectura para que se actualice el 5CA.",
        "check_intro": ("Una línea por grupo y por miembro a seguir. Escriba yes o no (sí o no) "
                        "tras ONSIDE:. Nada cuenta como de nuestro lado hasta entonces. En "
                        "blanco no es acuerdo."),
        "check_markers": "No edite las líneas ###.",
        "check_groups": "Grupos",
        "check_members": "Miembros",
        "record": "registro",
        "chamber": "Cámara",
        "summary": "{n} posición(es) sobre este tema",
        "and_more": "y {n} más",
        "yes": ("sí", "si", "s"), "no": ("no",),
        "areas_labels": {
            1: "aborto", 2: "eutanasia y suicidio asistido", 3: "medicina de género y menores",
            4: "terapias de conversión", 5: "derechos basados en el sexo",
            6: "derechos de los padres y educación", 7: "libertad de expresión y libertades civiles",
            8: "libertad religiosa", 9: "matrimonio y familia", 10: "gestación subrogada y embriones",
            11: "migración", 12: "prostitución y trata", 13: "donación de órganos",
            14: "juego y apuestas", 15: "despenalización de drogas"},
    },
    "it": {
        "other_votes": "Altre {n} votazioni su questo atto (emendamenti, articoli, procedura) non sono mostrate; le chiavi sono in pack.json.",
        "title": "Dossier per il dibattito",
        "sample": "CAMPIONE: costruito da un archivio di prova con conferme di prova. Non inviare.",
        "built": "Preparato il {today} dall'archivio; nulla è stato scaricato.",
        "debate_date": "Data del dibattito",
        "section_item": "L'atto",
        "kind": "Tipo",
        "watched": "Nella lista di monitoraggio di CitizenGO",
        "areas": "Il nostro ambito",
        "bill": "Disegno di legge o fascicolo",
        "link": "Collegamento",
        "section_agenda": "All'ordine del giorno",
        "agenda_none": "Nessun punto all'ordine del giorno su questo atto tra il {a} e il {b}.",
        "agenda_uncollected": ("Il calendario di questo paese non è ancora raccolto, quindi la "
                               "seduta non è nota: verificare il calendario della camera."),
        "section_bill_votes": "Votazioni registrate su questo atto",
        "bill_votes_none": "Ancora nessuna votazione registrata su questo atto.",
        "abstain": "Astenuto",
        "by_group": "Per gruppo",
        "section_topic": "Votazioni precedenti su questo tema",
        "topic_none": "Nessuna votazione precedente registrata su questo tema.",
        "section_place": "Collocazione 5CA",
        "place_awaiting": ("In attesa di firma: nessuno è collocato. La lettura di CitizenGO su "
                           "queste votazioni non è ancora stata confermata da una persona "
                           "indicata per nome, quindi il dossier mostra cosa ha fatto ciascun "
                           "membro e non dice da che parte sta nessuno."),
        "place_note": ("Le collocazioni derivano solo da letture confermate da una persona "
                       "indicata per nome in config/{cc}_stance.yaml ({n} confermate su questo tema)."),
        "awaiting_cell": "in attesa di firma",
        "not_placed": "non collocato",
        "section_speakers": "Probabili oratori",
        "speakers_none": ("La fonte non pubblica l'elenco degli oratori prima del dibattito. "
                          "Quando lo fa, rigenerare il dossier con --speakers \"Nome; Nome\"; "
                          "fino ad allora leggere prima i membri da seguire qui sotto."),
        "speakers_given": "Indicati per questo dibattito",
        "not_in_roster": "non trovato nell'elenco dei membri",
        "authors": "Firmatari dell'atto",
        "section_watch": "Membri da seguire",
        "watch_intro": "Membri che si sono discostati dalla maggioranza del proprio gruppo su questo atto o tema.",
        "watch_none": "Nessuno si è discostato dal proprio gruppo in queste votazioni.",
        "broke": "{pos} mentre la maggioranza di {party} ha votato {major}",
        "section_members": "Membri",
        "members_intro": ("Tutti i membri con una posizione registrata su questo atto o tema. "
                          "Le posizioni sono le parole del resoconto."),
        "col_member": "Membro", "col_group": "Gruppo", "col_bill": "Su questo atto",
        "col_topic": "Su questo tema", "col_5ca": "5CA", "col_profile": "Profilo",
        "no_record": "nessun dato",
        "derived_note": "Le posizioni con * sono DERIVATE dal voto del gruppo (X5), non dal voto del membro.",
        "profile": "profilo",
        "no_member_votes": ("La fonte di questo paese non pubblica i voti dei singoli membri, "
                            "quindi il dossier contiene solo l'atto e il calendario."),
        "section_sources": "Fonti",
        "check_title": "Lista di controllo per la campagna",
        "check_before": "Prima del dibattito",
        "task_reading": "Confermare la lettura di CitizenGO delle votazioni in config/{cc}_stance.yaml (firma una persona indicata per nome).",
        "task_agenda": "Verificare la seduta sul calendario della camera: le date cambiano.",
        "task_text": "Leggere il testo effettivamente in discussione, non solo il titolo.",
        "task_members": "Concordare quali membri contattare, dai gruppi e membri qui sotto.",
        "task_speakers": "Quando è pubblicato l'elenco degli oratori, rigenerare il dossier con --speakers.",
        "task_after": "Dopo il dibattito: registrare la votazione e la sua lettura perché il 5CA si aggiorni.",
        "check_intro": ("Una riga per gruppo e per membro da seguire. Scrivere yes o no (sì o "
                        "no) dopo ONSIDE:. Nulla conta come dalla nostra parte finché non lo "
                        "avete fatto. Vuoto non è un sì."),
        "check_markers": "Non modificare le righe ###.",
        "check_groups": "Gruppi",
        "check_members": "Membri",
        "record": "voti",
        "chamber": "Camera",
        "summary": "{n} posizione/i su questo tema",
        "and_more": "e altri {n}",
        "yes": ("sì", "si", "s"), "no": ("no",),
        "areas_labels": {
            1: "aborto", 2: "fine vita e suicidio assistito", 3: "medicina di genere e minori",
            4: "terapie di conversione", 5: "diritti basati sul sesso",
            6: "diritti dei genitori e istruzione", 7: "libertà di espressione e libertà civili",
            8: "libertà religiosa", 9: "matrimonio e famiglia", 10: "maternità surrogata ed embrioni",
            11: "migrazione", 12: "prostituzione e tratta", 13: "donazione di organi",
            14: "gioco d'azzardo e scommesse", 15: "depenalizzazione delle droghe"},
    },
    "fr": {
        "other_votes": "{n} autres scrutins sur ce texte (amendements, articles, procédure) ne sont pas affichés ; leurs clés sont dans pack.json.",
        "title": "Dossier de débat",
        "sample": "ÉCHANTILLON : construit à partir d'une base d'essai et de confirmations d'essai. Ne pas envoyer.",
        "built": "Préparé le {today} à partir de la base ; rien n'a été téléchargé.",
        "debate_date": "Date du débat",
        "section_item": "Le texte",
        "kind": "Type",
        "watched": "Sur la liste de suivi de CitizenGO",
        "areas": "Notre terrain",
        "bill": "Projet ou dossier",
        "link": "Lien",
        "section_agenda": "À l'ordre du jour",
        "agenda_none": "Aucun point de l'ordre du jour sur ce texte entre le {a} et le {b}.",
        "agenda_uncollected": ("L'ordre du jour de ce pays n'est pas encore collecté, la séance "
                               "n'est donc pas connue : vérifier l'agenda de l'assemblée."),
        "section_bill_votes": "Scrutins enregistrés sur ce texte",
        "bill_votes_none": "Aucun scrutin enregistré sur ce texte pour l'instant.",
        "abstain": "Abstention",
        "by_group": "Par groupe",
        "section_topic": "Scrutins antérieurs sur ce sujet",
        "topic_none": "Aucun scrutin antérieur enregistré sur ce sujet.",
        "section_place": "Classement 5CA",
        "place_awaiting": ("En attente de validation : personne n'est classé. La lecture de "
                           "CitizenGO sur ces scrutins n'a pas encore été confirmée par une "
                           "personne nommée ; ce dossier montre ce que chacun a voté et ne dit "
                           "pas de quel côté il se trouve."),
        "place_note": ("Les classements viennent uniquement de lectures confirmées par une "
                       "personne nommée dans config/{cc}_stance.yaml ({n} confirmées sur ce sujet)."),
        "awaiting_cell": "en attente de validation",
        "not_placed": "non classé",
        "section_speakers": "Orateurs probables",
        "speakers_none": ("La source ne publie pas la liste des orateurs avant le débat. "
                          "Quand elle le fait, reconstruire le dossier avec --speakers \"Nom; "
                          "Nom\" ; d'ici là, lire d'abord les membres à suivre ci-dessous."),
        "speakers_given": "Inscrits pour ce débat",
        "not_in_roster": "introuvable dans la liste des membres",
        "authors": "Auteurs du texte",
        "section_watch": "Membres à suivre",
        "watch_intro": "Membres qui se sont écartés de la majorité de leur groupe sur ce texte ou ce sujet.",
        "watch_none": "Personne ne s'est écarté de son groupe lors de ces scrutins.",
        "broke": "{pos} alors que la majorité de {party} a voté {major}",
        "section_members": "Membres",
        "members_intro": ("Tous les membres ayant une position enregistrée sur ce texte ou ce "
                          "sujet. Les positions sont les mots du compte rendu."),
        "col_member": "Membre", "col_group": "Groupe", "col_bill": "Sur ce texte",
        "col_topic": "Sur ce sujet", "col_5ca": "5CA", "col_profile": "Profil",
        "no_record": "aucun vote",
        "derived_note": "Les positions marquées * sont DÉDUITES du vote du groupe (X5), pas du vote du membre.",
        "profile": "profil",
        "no_member_votes": ("La source de ce pays ne publie pas de votes individuels ; le "
                            "dossier contient seulement le texte et l'ordre du jour."),
        "section_sources": "Sources",
        "check_title": "Liste de contrôle pour la campagne",
        "check_before": "Avant le débat",
        "task_reading": "Confirmer la lecture de CitizenGO des scrutins dans config/{cc}_stance.yaml (une personne nommée signe).",
        "task_agenda": "Vérifier la séance sur l'ordre du jour de l'assemblée : les dates bougent.",
        "task_text": "Lire le texte réellement débattu, pas seulement son titre.",
        "task_members": "Convenir des membres à contacter, à partir des groupes et membres ci-dessous.",
        "task_speakers": "Quand la liste des orateurs est publiée, reconstruire le dossier avec --speakers.",
        "task_after": "Après le débat : enregistrer le scrutin et sa lecture pour mettre à jour le 5CA.",
        "check_intro": ("Une ligne par groupe et par membre à suivre. Écrire yes ou no (oui ou "
                        "non) après ONSIDE:. Rien ne compte comme de notre côté avant cela. "
                        "Vide ne vaut pas accord."),
        "check_markers": "Ne pas modifier les lignes ###.",
        "check_groups": "Groupes",
        "check_members": "Membres",
        "record": "votes",
        "chamber": "Assemblée",
        "summary": "{n} position(s) sur ce sujet",
        "and_more": "et {n} autres",
        "yes": ("oui", "o"), "no": ("non",),
        "areas_labels": {
            1: "avortement", 2: "aide à mourir", 3: "médecine du genre et mineurs",
            4: "thérapies de conversion", 5: "droits fondés sur le sexe",
            6: "droits des parents et éducation", 7: "liberté d'expression et libertés publiques",
            8: "liberté religieuse", 9: "mariage et famille", 10: "GPA et embryons",
            11: "migration", 12: "prostitution et traite", 13: "don d'organes",
            14: "jeux d'argent", 15: "dépénalisation des drogues"},
    },
    "de": {
        "other_votes": "Weitere {n} Abstimmungen zu dieser Vorlage (Änderungsanträge, Artikel, Verfahren) sind nicht aufgeführt; ihre Schlüssel stehen in pack.json.",
        "title": "Debattenmappe",
        "sample": "MUSTER: aus einem Testbestand mit Testbestätigungen erstellt. Nicht versenden.",
        "built": "Erstellt am {today} aus dem Datenbestand; nichts wurde abgerufen.",
        "debate_date": "Datum der Debatte",
        "section_item": "Der Gegenstand",
        "kind": "Art",
        "watched": "Auf der Beobachtungsliste von CitizenGO",
        "areas": "Unser Themenfeld",
        "bill": "Vorlage oder Geschäft",
        "link": "Link",
        "section_agenda": "Auf der Tagesordnung",
        "agenda_none": "Kein Tagesordnungspunkt zu diesem Gegenstand zwischen {a} und {b}.",
        "agenda_uncollected": ("Die Tagesordnung dieses Landes wird noch nicht erfasst, der "
                               "Termin ist also nicht bekannt: bitte das Programm des Parlaments prüfen."),
        "section_bill_votes": "Namentliche Abstimmungen zu dieser Vorlage",
        "bill_votes_none": "Noch keine erfasste Abstimmung zu dieser Vorlage.",
        "abstain": "Enthaltung",
        "by_group": "Nach Fraktion",
        "section_topic": "Frühere Abstimmungen zu diesem Thema",
        "topic_none": "Keine frühere erfasste Abstimmung zu diesem Thema.",
        "section_place": "5CA-Einordnung",
        "place_awaiting": ("Freigabe ausstehend: niemand wird eingeordnet. Die Lesart von "
                           "CitizenGO zu diesen Abstimmungen ist noch nicht von einer namentlich "
                           "genannten Person bestätigt; die Mappe zeigt daher, wie jedes Mitglied "
                           "abgestimmt hat, und sagt nicht, auf welcher Seite jemand steht."),
        "place_note": ("Einordnungen stammen nur aus Lesarten, die eine namentlich genannte "
                       "Person in config/{cc}_stance.yaml bestätigt hat ({n} bestätigt zu diesem Thema)."),
        "awaiting_cell": "Freigabe ausstehend",
        "not_placed": "nicht eingeordnet",
        "section_speakers": "Voraussichtliche Rednerinnen und Redner",
        "speakers_none": ("Die Quelle veröffentlicht vor der Debatte keine Rednerliste. Sobald "
                          "sie es tut, die Mappe mit --speakers \"Name; Name\" neu erstellen; bis "
                          "dahin zuerst die unten genannten Mitglieder lesen."),
        "speakers_given": "Für diese Debatte genannt",
        "not_in_roster": "nicht in der Mitgliederliste gefunden",
        "authors": "Urheber der Vorlage",
        "section_watch": "Mitglieder im Blick",
        "watch_intro": "Mitglieder, die bei dieser Vorlage oder diesem Thema von der Mehrheit ihrer Fraktion abgewichen sind.",
        "watch_none": "Bei diesen Abstimmungen ist niemand von seiner Fraktion abgewichen.",
        "broke": "{pos}, während die Mehrheit von {party} {major} stimmte",
        "section_members": "Mitglieder",
        "members_intro": ("Alle Mitglieder mit einer erfassten Stimme zu dieser Vorlage oder "
                          "diesem Thema. Die Stimmen stehen im Wortlaut des Protokolls."),
        "col_member": "Mitglied", "col_group": "Fraktion", "col_bill": "Zu dieser Vorlage",
        "col_topic": "Zu diesem Thema", "col_5ca": "5CA", "col_profile": "Profil",
        "no_record": "keine Stimme",
        "derived_note": "Mit * markierte Stimmen sind aus dem Fraktionsvotum ABGELEITET (X5), nicht die eigene Stimme des Mitglieds.",
        "profile": "Profil",
        "no_member_votes": ("Die Quelle dieses Landes veröffentlicht keine Einzelstimmen; die "
                            "Mappe enthält nur den Gegenstand und die Tagesordnung."),
        "section_sources": "Quellen",
        "check_title": "Checkliste für die Kampagne",
        "check_before": "Vor der Debatte",
        "task_reading": "Die Lesart von CitizenGO zu den Abstimmungen in config/{cc}_stance.yaml bestätigen (eine namentlich genannte Person zeichnet).",
        "task_agenda": "Den Termin auf der Tagesordnung des Parlaments prüfen: Termine verschieben sich.",
        "task_text": "Den tatsächlich beratenen Text lesen, nicht nur den Titel.",
        "task_members": "Vereinbaren, welche Mitglieder angesprochen werden, anhand der Fraktionen und Mitglieder unten.",
        "task_speakers": "Sobald die Rednerliste vorliegt, die Mappe mit --speakers neu erstellen.",
        "task_after": "Nach der Debatte: die Abstimmung und ihre Lesart erfassen, damit die 5CA aktualisiert wird.",
        "check_intro": ("Eine Zeile pro Fraktion und pro Mitglied im Blick. Nach ONSIDE: yes "
                        "oder no (ja oder nein) eintragen. Nichts gilt als auf unserer Seite, "
                        "bevor das geschehen ist. Leer ist keine Zustimmung."),
        "check_markers": "Die ###-Zeilen nicht ändern.",
        "check_groups": "Fraktionen",
        "check_members": "Mitglieder",
        "record": "Stimmen",
        "chamber": "Kammer",
        "summary": "{n} Stimme(n) zu diesem Thema",
        "and_more": "und {n} weitere",
        "yes": ("ja", "j"), "no": ("nein",),
        "areas_labels": {
            1: "Abtreibung", 2: "Sterbehilfe", 3: "Geschlechtsmedizin und Kinder",
            4: "Konversionsbehandlungen", 5: "geschlechtsbezogene Rechte",
            6: "Elternrechte und Bildung", 7: "Meinungsfreiheit und Bürgerrechte",
            8: "Religionsfreiheit", 9: "Ehe und Familie", 10: "Leihmutterschaft und Embryonen",
            11: "Migration", 12: "Prostitution und Menschenhandel", 13: "Organspende",
            14: "Glücksspiel und Wetten", 15: "Entkriminalisierung von Drogen"},
    },
    "nl": {
        "other_votes": "Nog {n} stemmingen over dit voorstel (amendementen, artikelen, procedure) staan hier niet; hun sleutels staan in pack.json.",
        "title": "Debatdossier",
        "sample": "PROEF: gemaakt uit een testbestand met testbevestigingen. Niet versturen.",
        "built": "Opgesteld op {today} uit het bestand; er is niets opgehaald.",
        "debate_date": "Datum van het debat",
        "section_item": "Het onderwerp",
        "kind": "Soort",
        "watched": "Op de volglijst van CitizenGO",
        "areas": "Ons terrein",
        "bill": "Wetsvoorstel of dossier",
        "link": "Link",
        "section_agenda": "Op de agenda",
        "agenda_none": "Geen agendapunt over dit onderwerp tussen {a} en {b}.",
        "agenda_uncollected": ("De agenda van dit land wordt nog niet verzameld, dus het moment "
                               "is niet bekend: controleer de agenda van de Kamer zelf."),
        "section_bill_votes": "Geregistreerde stemmingen over dit voorstel",
        "bill_votes_none": "Nog geen geregistreerde stemming over dit voorstel.",
        "abstain": "Onthouding",
        "by_group": "Per fractie",
        "section_topic": "Eerdere stemmingen over dit thema",
        "topic_none": "Geen eerdere geregistreerde stemming over dit thema.",
        "section_place": "5CA-indeling",
        "place_awaiting": ("Wacht op goedkeuring: niemand is ingedeeld. De lezing van CitizenGO "
                           "van deze stemmingen is nog niet bevestigd door een persoon met naam; "
                           "dit dossier laat zien wat ieder lid deed en zegt niet aan welke kant "
                           "iemand staat."),
        "place_note": ("Indelingen komen alleen uit lezingen die een persoon met naam heeft "
                       "bevestigd in config/{cc}_stance.yaml ({n} bevestigd over dit thema)."),
        "awaiting_cell": "wacht op goedkeuring",
        "not_placed": "niet ingedeeld",
        "section_speakers": "Waarschijnlijke sprekers",
        "speakers_none": ("De bron publiceert geen sprekerslijst vóór het debat. Zodra dat "
                          "gebeurt, maak het dossier opnieuw met --speakers \"Naam; Naam\"; lees "
                          "tot dan eerst de leden om te volgen hieronder."),
        "speakers_given": "Genoemd voor dit debat",
        "not_in_roster": "niet gevonden in de ledenlijst",
        "authors": "Indieners van het voorstel",
        "section_watch": "Leden om te volgen",
        "watch_intro": "Leden die bij dit voorstel of thema afweken van de meerderheid van hun fractie.",
        "watch_none": "Niemand week bij deze stemmingen af van de fractie.",
        "broke": "{pos} terwijl de meerderheid van {party} {major} stemde",
        "section_members": "Leden",
        "members_intro": ("Alle leden met een geregistreerde stem over dit voorstel of thema. "
                          "De stemmen staan zoals in het verslag."),
        "col_member": "Lid", "col_group": "Fractie", "col_bill": "Over dit voorstel",
        "col_topic": "Over dit thema", "col_5ca": "5CA", "col_profile": "Profiel",
        "no_record": "geen stem",
        "derived_note": "Stemmen met * zijn AFGELEID van de stem van de fractie (X5), niet de eigen stem van het lid.",
        "profile": "profiel",
        "no_member_votes": ("De bron van dit land publiceert geen stemmen per lid; het dossier "
                            "bevat alleen het onderwerp en de agenda."),
        "section_sources": "Bronnen",
        "check_title": "Checklist voor de campagne",
        "check_before": "Vóór het debat",
        "task_reading": "De lezing van CitizenGO van de stemmingen bevestigen in config/{cc}_stance.yaml (een persoon met naam tekent).",
        "task_agenda": "Het moment controleren op de agenda van de Kamer: data schuiven.",
        "task_text": "De tekst lezen die echt besproken wordt, niet alleen de titel.",
        "task_members": "Afspreken welke leden we benaderen, op basis van de fracties en leden hieronder.",
        "task_speakers": "Zodra de sprekerslijst er is, het dossier opnieuw maken met --speakers.",
        "task_after": "Na het debat: de stemming en haar lezing vastleggen zodat de 5CA bijgewerkt wordt.",
        "check_intro": ("Eén regel per fractie en per lid om te volgen. Schrijf yes of no (ja of "
                        "nee) na ONSIDE:. Niets geldt als aan onze kant voordat u dat gedaan "
                        "hebt. Leeg is geen instemming."),
        "check_markers": "Wijzig de ###-regels niet.",
        "check_groups": "Fracties",
        "check_members": "Leden",
        "record": "stemmen",
        "chamber": "Kamer",
        "summary": "{n} stem(men) over dit thema",
        "and_more": "en {n} meer",
        "yes": ("ja", "j"), "no": ("nee",),
        "areas_labels": {
            1: "abortus", 2: "euthanasie en hulp bij zelfdoding", 3: "gendergeneeskunde en kinderen",
            4: "conversiehandelingen", 5: "op geslacht gebaseerde rechten",
            6: "ouderrechten en onderwijs", 7: "vrijheid van meningsuiting en burgerrechten",
            8: "godsdienstvrijheid", 9: "huwelijk en gezin", 10: "draagmoederschap en embryo's",
            11: "migratie", 12: "prostitutie en mensenhandel", 13: "orgaandonatie",
            14: "kansspelen", 15: "decriminalisering van drugs"},
    },
    "pl": {
        "other_votes": "Kolejne głosowania nad tym projektem ({n}: poprawki, artykuły, sprawy proceduralne) nie są pokazane; ich klucze są w pack.json.",
        "title": "Pakiet na debatę",
        "sample": "PRÓBKA: przygotowana z bazy testowej z testowymi zatwierdzeniami. Nie wysyłać.",
        "built": "Przygotowano {today} z bazy danych; niczego nie pobierano.",
        "debate_date": "Data debaty",
        "section_item": "Sprawa",
        "kind": "Rodzaj",
        "watched": "Na liście obserwowanych CitizenGO",
        "areas": "Nasz obszar",
        "bill": "Projekt lub druk",
        "link": "Link",
        "section_agenda": "W porządku obrad",
        "agenda_none": "Brak punktu porządku obrad w tej sprawie między {a} a {b}.",
        "agenda_uncollected": ("Porządek obrad tego kraju nie jest jeszcze zbierany, więc termin "
                               "nie jest znany: sprawdź harmonogram izby."),
        "section_bill_votes": "Zarejestrowane głosowania nad tym projektem",
        "bill_votes_none": "Brak jeszcze zarejestrowanego głosowania nad tym projektem.",
        "abstain": "Wstrzymał się",
        "by_group": "Według klubów",
        "section_topic": "Wcześniejsze głosowania w tej sprawie",
        "topic_none": "Brak wcześniejszych zarejestrowanych głosowań w tej sprawie.",
        "section_place": "Klasyfikacja 5CA",
        "place_awaiting": ("Czeka na zatwierdzenie: nikt nie jest sklasyfikowany. Odczytanie "
                           "tych głosowań przez CitizenGO nie zostało jeszcze potwierdzone przez "
                           "wskazaną z nazwiska osobę, więc pakiet pokazuje, jak kto głosował, i "
                           "nie mówi, kto jest po czyjej stronie."),
        "place_note": ("Klasyfikacje pochodzą wyłącznie z odczytań potwierdzonych przez wskazaną "
                       "z nazwiska osobę w config/{cc}_stance.yaml ({n} potwierdzonych w tej sprawie)."),
        "awaiting_cell": "czeka na zatwierdzenie",
        "not_placed": "niesklasyfikowany",
        "section_speakers": "Prawdopodobni mówcy",
        "speakers_none": ("Źródło nie publikuje listy mówców przed debatą. Gdy to zrobi, "
                          "przygotuj pakiet ponownie z --speakers \"Imię Nazwisko; Imię "
                          "Nazwisko\"; do tego czasu najpierw przeczytaj posłów do obserwacji poniżej."),
        "speakers_given": "Zgłoszeni do tej debaty",
        "not_in_roster": "nie znaleziono na liście posłów",
        "authors": "Wnioskodawcy projektu",
        "section_watch": "Posłowie do obserwacji",
        "watch_intro": "Posłowie, którzy w tym projekcie lub tej sprawie głosowali inaczej niż większość ich klubu.",
        "watch_none": "W tych głosowaniach nikt nie odszedł od swojego klubu.",
        "broke": "{pos}, gdy większość {party} głosowała {major}",
        "section_members": "Posłowie",
        "members_intro": ("Wszyscy posłowie z zarejestrowanym stanowiskiem w tym projekcie lub "
                          "tej sprawie. Stanowiska w brzmieniu rejestru."),
        "col_member": "Poseł", "col_group": "Klub", "col_bill": "W tym projekcie",
        "col_topic": "W tej sprawie", "col_5ca": "5CA", "col_profile": "Profil",
        "no_record": "brak głosu",
        "derived_note": "Stanowiska oznaczone * są WYPROWADZONE z głosu klubu (X5), a nie z głosu posła.",
        "profile": "profil",
        "no_member_votes": ("Źródło tego kraju nie publikuje głosów poszczególnych członków; "
                            "pakiet zawiera tylko sprawę i porządek obrad."),
        "section_sources": "Źródła",
        "check_title": "Lista kontrolna kampanii",
        "check_before": "Przed debatą",
        "task_reading": "Potwierdzić odczytanie głosowań przez CitizenGO w config/{cc}_stance.yaml (podpisuje wskazana z nazwiska osoba).",
        "task_agenda": "Sprawdzić termin w porządku obrad izby: daty się zmieniają.",
        "task_text": "Przeczytać tekst faktycznie rozpatrywany, nie tylko tytuł.",
        "task_members": "Uzgodnić, z którymi posłami się kontaktujemy, na podstawie klubów i posłów poniżej.",
        "task_speakers": "Gdy lista mówców zostanie opublikowana, przygotować pakiet ponownie z --speakers.",
        "task_after": "Po debacie: zapisać głosowanie i jego odczytanie, aby zaktualizować 5CA.",
        "check_intro": ("Jedna linia na klub i na posła do obserwacji. Wpisz yes lub no (tak lub "
                        "nie) po ONSIDE:. Nic nie liczy się jako po naszej stronie, dopóki tego "
                        "nie zrobisz. Puste pole to nie zgoda."),
        "check_markers": "Nie zmieniaj linii ###.",
        "check_groups": "Kluby",
        "check_members": "Posłowie",
        "record": "głosy",
        "chamber": "Izba",
        "summary": "{n} stanowisk(o) w tej sprawie",
        "and_more": "i {n} więcej",
        "yes": ("tak", "t"), "no": ("nie",),
        "areas_labels": {
            1: "aborcja", 2: "eutanazja i wspomagane samobójstwo", 3: "medycyna płci i dzieci",
            4: "terapie konwersyjne", 5: "prawa oparte na płci biologicznej",
            6: "prawa rodziców i edukacja", 7: "wolność słowa i swobody obywatelskie",
            8: "wolność religijna", 9: "małżeństwo i rodzina", 10: "surogacja i embriony",
            11: "migracja", 12: "prostytucja i handel ludźmi", 13: "dawstwo narządów",
            14: "hazard i zakłady", 15: "dekryminalizacja narkotyków"},
    },
    "pt": {
        "other_votes": "Outras {n} votações sobre esta matéria (propostas de alteração, artigos, procedimento) não são mostradas; as chaves estão em pack.json.",
        "title": "Dossiê do debate",
        "sample": "AMOSTRA: feita a partir de uma base de teste com confirmações de teste. Não enviar.",
        "built": "Preparado em {today} a partir da base; nada foi descarregado.",
        "debate_date": "Data do debate",
        "section_item": "A matéria",
        "kind": "Tipo",
        "watched": "Na lista de acompanhamento da CitizenGO",
        "areas": "O nosso terreno",
        "bill": "Projeto ou iniciativa",
        "link": "Ligação",
        "section_agenda": "Na ordem do dia",
        "agenda_none": "Nenhum ponto da ordem do dia sobre esta matéria entre {a} e {b}.",
        "agenda_uncollected": ("A ordem do dia deste país ainda não é recolhida, por isso a "
                               "sessão não é conhecida: consultar a agenda da própria câmara."),
        "section_bill_votes": "Votações registadas sobre esta matéria",
        "bill_votes_none": "Ainda não há votação registada sobre esta matéria.",
        "abstain": "Abstenção",
        "by_group": "Por grupo",
        "section_topic": "Votações anteriores sobre este tema",
        "topic_none": "Nenhuma votação anterior registada sobre este tema.",
        "section_place": "Classificação 5CA",
        "place_awaiting": ("A aguardar validação: ninguém é classificado. A leitura da CitizenGO "
                           "sobre estas votações ainda não foi confirmada por uma pessoa "
                           "identificada, por isso este dossiê mostra o que cada membro fez e "
                           "não diz de que lado alguém está."),
        "place_note": ("As classificações vêm apenas de leituras confirmadas por uma pessoa "
                       "identificada em config/{cc}_stance.yaml ({n} confirmadas sobre este tema)."),
        "awaiting_cell": "a aguardar validação",
        "not_placed": "não classificado",
        "section_speakers": "Prováveis oradores",
        "speakers_none": ("A fonte não publica a lista de oradores antes do debate. Quando o "
                          "fizer, refazer o dossiê com --speakers \"Nome; Nome\"; até lá, ler "
                          "primeiro os membros a acompanhar abaixo."),
        "speakers_given": "Indicados para este debate",
        "not_in_roster": "não encontrado na lista de membros",
        "authors": "Autores da iniciativa",
        "section_watch": "Membros a acompanhar",
        "watch_intro": "Membros que se afastaram da maioria do seu grupo nesta matéria ou tema.",
        "watch_none": "Ninguém se afastou do seu grupo nestas votações.",
        "broke": "{pos} quando a maioria de {party} votou {major}",
        "section_members": "Membros",
        "members_intro": ("Todos os membros com uma posição registada sobre esta matéria ou "
                          "tema. As posições são as palavras do próprio registo."),
        "col_member": "Membro", "col_group": "Grupo", "col_bill": "Nesta matéria",
        "col_topic": "Neste tema", "col_5ca": "5CA", "col_profile": "Perfil",
        "no_record": "sem registo",
        "derived_note": "As posições com * são DERIVADAS do voto do grupo (X5), não do voto do próprio membro.",
        "profile": "perfil",
        "no_member_votes": ("A fonte deste país não publica votos individuais; o dossiê contém "
                            "apenas a matéria e a ordem do dia."),
        "section_sources": "Fontes",
        "check_title": "Lista de verificação da campanha",
        "check_before": "Antes do debate",
        "task_reading": "Confirmar a leitura da CitizenGO das votações em config/{cc}_stance.yaml (assina uma pessoa identificada).",
        "task_agenda": "Verificar a sessão na ordem do dia da câmara: as datas mudam.",
        "task_text": "Ler o texto que é de facto debatido, não só o título.",
        "task_members": "Combinar que membros contactar, a partir dos grupos e membros abaixo.",
        "task_speakers": "Quando a lista de oradores for publicada, refazer o dossiê com --speakers.",
        "task_after": "Depois do debate: registar a votação e a sua leitura para atualizar o 5CA.",
        "check_intro": ("Uma linha por grupo e por membro a acompanhar. Escrever yes ou no (sim "
                        "ou não) depois de ONSIDE:. Nada conta como do nosso lado antes disso. "
                        "Em branco não é concordância."),
        "check_markers": "Não editar as linhas ###.",
        "check_groups": "Grupos",
        "check_members": "Membros",
        "record": "votos",
        "chamber": "Câmara",
        "summary": "{n} posição(ões) sobre este tema",
        "and_more": "e mais {n}",
        "yes": ("sim", "s"), "no": ("não", "nao"),
        "areas_labels": {
            1: "aborto", 2: "eutanásia e suicídio assistido", 3: "medicina de género e menores",
            4: "terapias de conversão", 5: "direitos baseados no sexo",
            6: "direitos dos pais e educação", 7: "liberdade de expressão e liberdades cívicas",
            8: "liberdade religiosa", 9: "casamento e família", 10: "barriga de aluguer e embriões",
            11: "migração", 12: "prostituição e tráfico", 13: "doação de órgãos",
            14: "jogo e apostas", 15: "descriminalização das drogas"},
    },
    "hr": {
        "other_votes": "Još {n} glasovanja o ovom prijedlogu (amandmani, članci, postupak) nije prikazano; njihovi ključevi su u pack.json.",
        "title": "Paket za raspravu",
        "sample": "UZORAK: izrađen iz probne baze s probnim potvrdama. Ne slati.",
        "built": "Pripremljeno {today} iz baze; ništa nije preuzeto.",
        "debate_date": "Datum rasprave",
        "section_item": "Točka",
        "kind": "Vrsta",
        "watched": "Na popisu praćenja CitizenGO-a",
        "areas": "Naše područje",
        "bill": "Prijedlog zakona ili predmet",
        "link": "Poveznica",
        "section_agenda": "Na dnevnom redu",
        "agenda_none": "Nema točke dnevnog reda o ovome između {a} i {b}.",
        "agenda_uncollected": ("Dnevni red ove zemlje još se ne prikuplja pa termin nije poznat: "
                               "provjerite raspored samog sabora."),
        "section_bill_votes": "Zabilježena glasovanja o ovom prijedlogu",
        "bill_votes_none": "Još nema zabilježenog glasovanja o ovom prijedlogu.",
        "abstain": "Suzdržan",
        "by_group": "Po klubovima",
        "section_topic": "Ranija glasovanja o ovoj temi",
        "topic_none": "Nema ranijih zabilježenih glasovanja o ovoj temi.",
        "section_place": "Razvrstavanje 5CA",
        "place_awaiting": ("Čeka potvrdu: nitko nije razvrstan. Tumačenje ovih glasovanja od "
                           "strane CitizenGO-a još nije potvrdila imenovana osoba, pa paket "
                           "prikazuje kako je tko glasovao i ne tvrdi tko je na čijoj strani."),
        "place_note": ("Razvrstavanja dolaze samo iz tumačenja koja je imenovana osoba potvrdila "
                       "u config/{cc}_stance.yaml ({n} potvrđeno o ovoj temi)."),
        "awaiting_cell": "čeka potvrdu",
        "not_placed": "nije razvrstan",
        "section_speakers": "Vjerojatni govornici",
        "speakers_none": ("Izvor ne objavljuje popis govornika prije rasprave. Kad ga objavi, "
                          "ponovno izradite paket s --speakers \"Ime; Ime\"; do tada najprije "
                          "pročitajte zastupnike za praćenje u nastavku."),
        "speakers_given": "Navedeni za ovu raspravu",
        "not_in_roster": "nije pronađen na popisu zastupnika",
        "authors": "Predlagatelji",
        "section_watch": "Zastupnici za praćenje",
        "watch_intro": "Zastupnici koji su o ovom prijedlogu ili temi glasovali drukčije od većine svog kluba.",
        "watch_none": "U ovim glasovanjima nitko nije odstupio od svog kluba.",
        "broke": "{pos}, dok je većina {party} glasovala {major}",
        "section_members": "Zastupnici",
        "members_intro": ("Svi zastupnici sa zabilježenim glasom o ovom prijedlogu ili temi. "
                          "Glasovi su doslovno iz zapisa."),
        "col_member": "Zastupnik", "col_group": "Klub", "col_bill": "O ovom prijedlogu",
        "col_topic": "O ovoj temi", "col_5ca": "5CA", "col_profile": "Profil",
        "no_record": "nema glasa",
        "derived_note": "Glasovi označeni * IZVEDENI su iz glasa kluba (X5), a ne vlastiti glas zastupnika.",
        "profile": "profil",
        "no_member_votes": ("Izvor ove zemlje ne objavljuje pojedinačne glasove; paket sadrži "
                            "samo točku i dnevni red."),
        "section_sources": "Izvori",
        "check_title": "Kontrolni popis za kampanju",
        "check_before": "Prije rasprave",
        "task_reading": "Potvrditi tumačenje glasovanja od strane CitizenGO-a u config/{cc}_stance.yaml (potpisuje imenovana osoba).",
        "task_agenda": "Provjeriti termin na dnevnom redu sabora: datumi se mijenjaju.",
        "task_text": "Pročitati tekst o kojem se doista raspravlja, ne samo naslov.",
        "task_members": "Dogovoriti kojim se zastupnicima obraćamo, prema klubovima i zastupnicima u nastavku.",
        "task_speakers": "Kad se objavi popis govornika, ponovno izraditi paket s --speakers.",
        "task_after": "Nakon rasprave: zabilježiti glasovanje i njegovo tumačenje kako bi se 5CA ažurirao.",
        "check_intro": ("Jedan redak po klubu i po zastupniku za praćenje. Upišite yes ili no "
                        "(da ili ne) nakon ONSIDE:. Ništa se ne smatra našom stranom dok to ne "
                        "učinite. Prazno nije slaganje."),
        "check_markers": "Ne mijenjajte retke ###.",
        "check_groups": "Klubovi",
        "check_members": "Zastupnici",
        "record": "glasovi",
        "chamber": "Dom",
        "summary": "{n} glas(ova) o ovoj temi",
        "and_more": "i još {n}",
        "yes": ("da", "d"), "no": ("ne",),
        "areas_labels": {
            1: "pobačaj", 2: "eutanazija i potpomognuto samoubojstvo", 3: "rodna medicina i djeca",
            4: "konverzijske terapije", 5: "prava utemeljena na spolu",
            6: "roditeljska prava i obrazovanje", 7: "sloboda govora i građanske slobode",
            8: "vjerska sloboda", 9: "brak i obitelj", 10: "surogatstvo i embriji",
            11: "migracije", 12: "prostitucija i trgovanje ljudima", 13: "darivanje organa",
            14: "igre na sreću i klađenje", 15: "dekriminalizacija droga"},
    },
    "sk": {
        "other_votes": "Ďalšie hlasovania o tomto návrhu ({n}: pozmeňujúce návrhy, články, procedúra) nie sú zobrazené; ich kľúče sú v pack.json.",
        "title": "Podklady k rozprave",
        "sample": "VZORKA: pripravené zo skúšobnej databázy so skúšobnými potvrdeniami. Neposielať.",
        "built": "Pripravené {today} z databázy; nič sa nesťahovalo.",
        "debate_date": "Dátum rozpravy",
        "section_item": "Bod",
        "kind": "Druh",
        "watched": "Na zozname sledovaných CitizenGO",
        "areas": "Naša oblasť",
        "bill": "Návrh zákona alebo tlač",
        "link": "Odkaz",
        "section_agenda": "V programe schôdze",
        "agenda_none": "Žiadny bod programu k tejto veci medzi {a} a {b}.",
        "agenda_uncollected": ("Program tejto krajiny sa zatiaľ nezbiera, termín preto nie je "
                               "známy: overte harmonogram samotnej rady."),
        "section_bill_votes": "Zaznamenané hlasovania o tomto návrhu",
        "bill_votes_none": "O tomto návrhu zatiaľ nie je zaznamenané žiadne hlasovanie.",
        "abstain": "Zdržal sa",
        "by_group": "Podľa klubov",
        "section_topic": "Predchádzajúce hlasovania k tejto téme",
        "topic_none": "K tejto téme nie je zaznamenané žiadne predchádzajúce hlasovanie.",
        "section_place": "Zaradenie 5CA",
        "place_awaiting": ("Čaká na schválenie: nikto nie je zaradený. Výklad týchto hlasovaní "
                           "zo strany CitizenGO ešte nepotvrdila menovaná osoba, preto podklady "
                           "ukazujú, ako kto hlasoval, a netvrdia, kto stojí na ktorej strane."),
        "place_note": ("Zaradenia pochádzajú len z výkladov, ktoré potvrdila menovaná osoba v "
                       "config/{cc}_stance.yaml ({n} potvrdených k tejto téme)."),
        "awaiting_cell": "čaká na schválenie",
        "not_placed": "nezaradený",
        "section_speakers": "Pravdepodobní rečníci",
        "speakers_none": ("Zdroj nezverejňuje zoznam rečníkov pred rozpravou. Keď ho zverejní, "
                          "pripravte podklady znova s --speakers \"Meno; Meno\"; dovtedy si "
                          "najprv prečítajte poslancov na sledovanie nižšie."),
        "speakers_given": "Prihlásení do tejto rozpravy",
        "not_in_roster": "nenájdený v zozname poslancov",
        "authors": "Navrhovatelia",
        "section_watch": "Poslanci na sledovanie",
        "watch_intro": "Poslanci, ktorí pri tomto návrhu alebo téme hlasovali inak ako väčšina ich klubu.",
        "watch_none": "Pri týchto hlasovaniach sa nikto neodchýlil od svojho klubu.",
        "broke": "{pos}, kým väčšina {party} hlasovala {major}",
        "section_members": "Poslanci",
        "members_intro": ("Všetci poslanci so zaznamenaným hlasom o tomto návrhu alebo téme. "
                          "Hlasy sú v znení záznamu."),
        "col_member": "Poslanec", "col_group": "Klub", "col_bill": "K tomuto návrhu",
        "col_topic": "K tejto téme", "col_5ca": "5CA", "col_profile": "Profil",
        "no_record": "bez hlasu",
        "derived_note": "Hlasy označené * sú ODVODENÉ z hlasu klubu (X5), nie vlastný hlas poslanca.",
        "profile": "profil",
        "no_member_votes": ("Zdroj tejto krajiny nezverejňuje hlasy jednotlivcov; podklady "
                            "obsahujú len bod a program."),
        "section_sources": "Zdroje",
        "check_title": "Kontrolný zoznam kampane",
        "check_before": "Pred rozpravou",
        "task_reading": "Potvrdiť výklad hlasovaní zo strany CitizenGO v config/{cc}_stance.yaml (podpisuje menovaná osoba).",
        "task_agenda": "Overiť termín v programe schôdze: dátumy sa posúvajú.",
        "task_text": "Prečítať text, o ktorom sa naozaj rokuje, nielen názov.",
        "task_members": "Dohodnúť, ktorých poslancov oslovíme, podľa klubov a poslancov nižšie.",
        "task_speakers": "Keď sa zverejní zoznam rečníkov, pripraviť podklady znova s --speakers.",
        "task_after": "Po rozprave: zaznamenať hlasovanie a jeho výklad, aby sa 5CA aktualizovalo.",
        "check_intro": ("Jeden riadok na klub a na poslanca na sledovanie. Za ONSIDE: napíšte "
                        "yes alebo no (áno alebo nie). Nič sa nepovažuje za našu stranu, kým "
                        "to neurobíte. Prázdne nie je súhlas."),
        "check_markers": "Neupravujte riadky ###.",
        "check_groups": "Kluby",
        "check_members": "Poslanci",
        "record": "hlasy",
        "chamber": "Snemovňa",
        "summary": "{n} hlas(ov) k tejto téme",
        "and_more": "a ďalších {n}",
        "yes": ("áno", "ano", "a"), "no": ("nie",),
        "areas_labels": {
            1: "potraty", 2: "eutanázia a asistovaná samovražda", 3: "rodová medicína a deti",
            4: "konverzné terapie", 5: "práva založené na pohlaví",
            6: "práva rodičov a vzdelávanie", 7: "sloboda prejavu a občianske slobody",
            8: "náboženská sloboda", 9: "manželstvo a rodina", 10: "náhradné materstvo a embryá",
            11: "migrácia", 12: "prostitúcia a obchodovanie s ľuďmi", 13: "darcovstvo orgánov",
            14: "hazard a stávkovanie", 15: "dekriminalizácia drog"},
    },
    "hu": {
        "other_votes": "További {n} szavazás erről az irományról (módosító javaslatok, cikkek, eljárás) nem szerepel itt; kulcsaik a pack.json fájlban vannak.",
        "title": "Vitacsomag",
        "sample": "MINTA: próba-adatbázisból, próba-jóváhagyásokkal készült. Nem küldhető ki.",
        "built": "Készült: {today}, az adatbázisból; semmi nem lett letöltve.",
        "debate_date": "A vita dátuma",
        "section_item": "A napirendi tétel",
        "kind": "Fajta",
        "watched": "A CitizenGO figyelőlistáján",
        "areas": "A mi területünk",
        "bill": "Törvényjavaslat vagy iromány",
        "link": "Hivatkozás",
        "section_agenda": "A napirenden",
        "agenda_none": "Nincs napirendi pont erről {a} és {b} között.",
        "agenda_uncollected": ("Ennek az országnak a napirendjét még nem gyűjtjük, így az "
                               "időpont nem ismert: nézze meg az Országgyűlés saját programját."),
        "section_bill_votes": "Rögzített szavazások erről az irományról",
        "bill_votes_none": "Erről az irományról még nincs rögzített szavazás.",
        "abstain": "Tartózkodott",
        "by_group": "Frakciónként",
        "section_topic": "Korábbi szavazások ebben a témában",
        "topic_none": "Ebben a témában nincs korábbi rögzített szavazás.",
        "section_place": "5CA-besorolás",
        "place_awaiting": ("Jóváhagyásra vár: senki sincs besorolva. A CitizenGO olvasatát "
                           "ezekről a szavazásokról még nem erősítette meg megnevezett személy, "
                           "ezért a csomag azt mutatja, ki hogyan szavazott, és nem állítja, ki "
                           "melyik oldalon áll."),
        "place_note": ("Besorolás csak olyan olvasatból készül, amelyet megnevezett személy "
                       "megerősített a config/{cc}_stance.yaml fájlban ({n} megerősítve ebben a témában)."),
        "awaiting_cell": "jóváhagyásra vár",
        "not_placed": "nincs besorolva",
        "section_speakers": "Várható felszólalók",
        "speakers_none": ("A forrás a vita előtt nem tesz közzé felszólalói listát. Ha közzéteszi, "
                          "készítse el újra a csomagot a --speakers \"Név; Név\" kapcsolóval; "
                          "addig először az alábbi figyelendő képviselőket olvassa el."),
        "speakers_given": "Erre a vitára megnevezve",
        "not_in_roster": "nem szerepel a képviselők listáján",
        "authors": "Az iromány benyújtói",
        "section_watch": "Figyelendő képviselők",
        "watch_intro": "Képviselők, akik ebben az irományban vagy témában eltértek frakciójuk többségétől.",
        "watch_none": "Ezekben a szavazásokban senki sem tért el a frakciójától.",
        "broke": "{pos}, miközben a(z) {party} többsége {major} szavazott",
        "section_members": "Képviselők",
        "members_intro": ("Minden képviselő, akinek van rögzített szavazata erről az irományról "
                          "vagy témáról. A szavazat a jegyzőkönyv szövege szerint."),
        "col_member": "Képviselő", "col_group": "Frakció", "col_bill": "Erről az irományról",
        "col_topic": "Ebben a témában", "col_5ca": "5CA", "col_profile": "Profil",
        "no_record": "nincs szavazat",
        "derived_note": "A *-gal jelölt szavazatok a frakció szavazatából SZÁRMAZTATOTTAK (X5), nem a képviselő saját szavazatai.",
        "profile": "profil",
        "no_member_votes": ("Ennek az országnak a forrása nem tesz közzé egyéni szavazatokat; a "
                            "csomag csak a tételt és a napirendet tartalmazza."),
        "section_sources": "Források",
        "check_title": "Kampány-ellenőrzőlista",
        "check_before": "A vita előtt",
        "task_reading": "A CitizenGO olvasatának megerősítése a config/{cc}_stance.yaml fájlban (megnevezett személy írja alá).",
        "task_agenda": "Az időpont ellenőrzése az Országgyűlés napirendjén: a dátumok változnak.",
        "task_text": "A ténylegesen tárgyalt szöveg elolvasása, nem csak a címé.",
        "task_members": "Megállapodás arról, mely képviselőket keressük meg, az alábbi frakciók és képviselők alapján.",
        "task_speakers": "Ha megjelenik a felszólalói lista, a csomag újbóli elkészítése a --speakers kapcsolóval.",
        "task_after": "A vita után: a szavazás és olvasata rögzítése, hogy az 5CA frissüljön.",
        "check_intro": ("Egy sor frakciónként és figyelendő képviselőnként. Az ONSIDE: után írja "
                        "be: yes vagy no (igen vagy nem). Addig semmi sem számít a mi "
                        "oldalunknak. Az üres nem egyetértés."),
        "check_markers": "A ### sorokat ne módosítsa.",
        "check_groups": "Frakciók",
        "check_members": "Képviselők",
        "record": "szavazatok",
        "chamber": "Ház",
        "summary": "{n} szavazat ebben a témában",
        "and_more": "és még {n}",
        "yes": ("igen", "i"), "no": ("nem",),
        "areas_labels": {
            1: "abortusz", 2: "eutanázia és asszisztált öngyilkosság", 3: "gendergyógyászat és gyermekek",
            4: "konverziós terápiák", 5: "nemen alapuló jogok",
            6: "szülői jogok és oktatás", 7: "szólásszabadság és polgári szabadságjogok",
            8: "vallásszabadság", 9: "házasság és család", 10: "béranyaság és embriók",
            11: "migráció", 12: "prostitúció és emberkereskedelem", 13: "szervadományozás",
            14: "szerencsejáték és fogadás", 15: "a kábítószerek dekriminalizálása"},
    },
}


def lang_of(cc):
    return LANG.get(cc, "en")


def text(lang, key, **kw):
    """One phrase in a language, English when the language lacks it."""
    table = TEXT.get(lang) or TEXT["en"]
    raw = table.get(key, TEXT["en"].get(key, key))
    return raw.format(**kw) if kw and isinstance(raw, str) else raw


def area_label(lang, area):
    labels = text(lang, "areas_labels")
    return labels.get(int(area), "area {0}".format(area)) if isinstance(labels, dict) else str(area)


def answer_words():
    """({yes words}, {no words}) over every language, folded to lower case."""
    yes, no = set(), set()
    for table in TEXT.values():
        yes.update(w.lower() for w in table.get("yes", ()) if len(w) > 1 or w == "y")
        no.update(w.lower() for w in table.get("no", ()) if len(w) > 1 or w == "n")
    return yes, no
