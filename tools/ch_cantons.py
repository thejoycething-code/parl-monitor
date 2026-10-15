#!/usr/bin/env python3
"""Switzerland's cantonal parliaments (CH7, 13 October 2026): business items
and, where published, recorded votes of the cantons with a usable source,
into ch_canton_acts and ch_canton_divisions (src/ch_store.py).

    python3 tools/ch_cantons.py                      # every canton below
    python3 tools/ch_cantons.py --canton zh be       # some of them
    python3 tools/ch_cantons.py --reclassify         # offline, after a taxonomy change
    python3 tools/ch_cantons.py --dry-run            # one read per canton, store nothing

Scoped, live-probed, in docs/switzerland-cantons-scope.md. Five of the 26
cantonal parliaments are read; the rest are listed there with the reason
(robots.txt refuses the open-data API, no list without a search form, a
single-page app with an undocumented backend, small cantons not probed yet).

  zh  Kantonsrat Zuerich. The Parliament's open data service (CMI CDWS,
      parlzhcdws.cmicloud.ch, the backend of kantonsrat.zh.ch; its
      robots.txt answers 404, so no rules): the Geschaeft index, queried in
      its own CQL. Each run reads the businesses begun in the last
      ZH_NEW_DAYS days and every business whose index sequence (SEQ) moved
      past the highest one stored, 25 a page, capped.
  be  Grosser Rat Bern. The Parliament's daily OGD export
      (ogd.parl.apps.be.ch, listed on opendata.swiss; no robots.txt): every
      business in German and French with its submission date, last
      treatment and decision, and the Tagblatt's votes with their tallies.
      Rows of the current legislature (BE_SINCE) are kept.
  ge  Grand Conseil de Geneve. The Grand Conseil's own search
      (/grandconseil/searchm/), asked for each of GE_TERMS within the last
      year, two pages each: the objects (PL, M, R, P, IN, RD, ...) with the
      month of their latest document and the decision with its date. A
      keyword search: an object no term finds is not read.
  vd  Grand Conseil vaudois. The lists of objects awaiting treatment, one
      page per department plus the Grand Conseil's own: motions,
      postulates, initiatives, Council of State reports and bills, with
      the committee and the latest step (report received, committee
      sitting).
  ti  Gran Consiglio ticinese. The order of the day of the next (or last)
      sitting: each point with its acts (motions, initiatives, messages
      and reports). The search of messages and acts is disallowed by
      robots.txt and is not read.

ALTERNATIVE ROUTES (13 October 2026, branch access-routes; Chris: "Email all
and explore external ways too"). The open-data portals of Basel-Stadt,
Basel-Landschaft, St. Gallen and Thurgau (robots.txt: Disallow /api/) and
www.ag.ch/grossrat were unread; Basel-Stadt, Thurgau and (since the same
day) Basel-Landschaft are now read there under written permissions (below),
with these routes as their fallback. Each canton is read from another
official host of its own whose robots.txt allows it (asked every run):

  bs  Grosser Rat Basel-Stadt. Since 13 October 2026 (branch bs-gribs)
      first from the Grand Council's own raw data exports on
      grosserrat.bs.ch/component/gribs (offered by its Parlamentsdienst,
      Peter Frankenbach; robots.txt allows /component/): the whole
      Geschaefte table (ges, JSON, the CSV if the JSON fails), its documents
      (dok) and steps (vor, dated by siz), diffed against the store. Since
      15 October 2026 also zuw (committee assignments: the committee a
      business sits with, named by the gre export, and each completed
      assignment as a step) and adr (members: the first author's party and
      each voter's party; only number, name and party are read). Frankenbach
      allowed a daily download (data refreshed about 03:00); we read weekly. Votes,
      and the business if an export fails, from data.bs.ch (see WRITTEN
      PERMISSIONS below); the last fallback is the Grand Council's
      pages on grosserrat.bs.ch (its robots.txt
      disallows only /api/ and system folders): the new parliamentary
      motions page (the business numbers and titles lodged for the next
      sitting) and the weekly Grossratsversand page (every report, Ratschlag
      and written answer since February, dated).
  bl  Landrat Basel-Landschaft. Since 13 October 2026 from data.bl.ch (see
      WRITTEN PERMISSIONS below); the fallback is baselland.talus.ch, the
      Landrat's business system "Politik Baselland": the newest documents
      list, about six weeks of motions, postulates, interpellations,
      Vorlagen, committee reports and answers, each with its business
      number and date.
  sg  Kantonsrat St. Gallen (via www.ratsinfo.sg.ch, the Kantonsrat's
      Ratsinformationssystem; its robots.txt sets no rules): the JSON the
      RIS page itself loads, /api/businesses (ordered by last change) with
      its business types and process states, and /api/votings: every
      recorded vote with its tally (read for the votes on business on our
      ground).
  tg  Grosser Rat Thurgau. Since 13 October 2026 from data.tg.ch (see
      WRITTEN PERMISSIONS below); the fallback is grgeko.tg.ch, the Grosser
      Rat's electronic business database (robots.txt allows everything): the
      list of pending business (Pendente Geschäfte), with each item's
      registration date.
  ag  Aargau (via gesetzessammlungen.ag.ch, the canton's official law
      collection; robots.txt disallows only its search paths): the
      Aargauische Gesetzessammlung's chronological index of published acts
      (laws, decrees, ordinances), as the collection's app loads it. Adopted
      acts only: the Grosser Rat's business is on the disallowed /grossrat.

opendata.swiss was checked: its dataset pages for these parliaments only
link back to the cantons' /api/ exports (no file is hosted on
opendata.swiss), and ckan.opendata.swiss disallows /api/ itself. The
official gazettes (Kantonsblatt Basel-Stadt, amtsblattportal.ch, the
St. Gallen and Thurgau Amtsblatt) all disallow every path to every agent.

WRITTEN PERMISSIONS (13 October 2026; src/robots_guard.PERMISSIONS,
docs/robots-runtime.md "Written permissions"). Basel-Stadt's Statistisches
Amt, Thurgau's Amt fuer Daten und Statistik and Basel-Landschaft's
Statistisches Amt (Johannes Hool) wrote that our targeted use of their
Opendatasoft APIs is welcome, though robots.txt there disallows /api/. Only
the parliament datasets below are read; JSON exports filtered
server-side to the window, votes in date batches (Basel-Stadt: "if the API
is slow, download in batches"), 3 s between requests, once a week:

  bs  data.bs.ch (CC BY 4.0: the data source must be linked): 100311
      Geschaefte begun or ended in the last BS_API_DAYS days, or touched in
      them by a document (100313) or a Grosser Rat step (100314, its
      'vermerk' as the status); 100186 every vote since the newest stored,
      with its published counts and each member's vote (J/N/E/A/P).
  tg  data.tg.ch (CC0): sk-stat-140 business received or closed in the last
      TG_API_DAYS days and everything pending, its state, where it is
      pending, its newest dated step and its flags as printed; sk-stat-141
      the signatories; sk-stat-136 each member's vote (or the option they
      chose in a vote between motions), counts tallied from them (the
      dataset prints none).
  bl  data.bl.ch (the Landeskanzlei's datasets; opendata.swiss terms_by:
      free use, the source must be cited): 13090 business begun or ended in
      the last BL_API_DAYS days and everything in progress, its state,
      Landrat standing and committee; 13130 the newest document of the
      window as its latest step; 13140 the authors (and the count of
      co-signatories) of motions and questions not yet stored with them;
      13080 each member's vote since the newest stored (the first read
      from the 2023-2027 legislature, BL_VOTE_SINCE), counts tallied from
      them (the dataset prints none); a vote's act through its
      geschaeft_id. Items link the Landrat's page on baselland.talus.ch.

Every act and vote read there carries `source_url`, its dataset link, shown
on the item in the edition. Members' votes go to ch_canton_votes. If an API
fails, the canton is read from the pages above and one gap says so.

CLASSIFICATION as the federal collector does it (tools/ch_rollcalls.py):
German text with config/taxonomy-atch.yaml for `ch`, French with
config/taxonomy-fr.yaml for `ch`, Italian (Ticino) with
config/taxonomy-it.yaml for `ch`; Bern's two titles are both matched and
unioned. Plus config/watchlist-ch.yaml's `cantons` section BY KEY.
Nothing is hand-classified, and titles are matched, never full texts.

STATUS AND DATES. Zuerich, Bern and Ticino date their steps, so status_date
is the source's. Geneva dates a decision; a report with no decision, and
every step in Vaud, prints no date: a run that sees a stored row's status
change stamps the day it saw it (status_seen = 1), and the first sighting
is never a change. Geneva, Vaud and Ticino print no submission date: a
row first seen after a canton's first read is new on the day we saw it;
rows of the first read are a baseline (baseline = 1) and are never shown
as new.

Exit 0, or 3 when it stored what it could and recorded gaps (the gaps table
and [gap] lines): jobs/ch-weekly.sh treats its failure as a [gap] line and
never as the run's.

ROBOTS.TXT AT RUN TIME: every request goes through
src/robots_guard.GuardedClient (no exemptions but the written permissions), which reads each host's
robots.txt once per run before the first request. A disallowed URL, or a
host whose robots.txt cannot be read, is a [gap] line and a gaps row,
never fetched and never fatal. That is why the open-data portal of
St. Gallen (an Opendatasoft portal whose robots.txt disallows /api/ to
every agent but Googlebot) and Aargau's www.ag.ch/grossrat are never
asked; those cantons are read through the routes under ALTERNATIVE ROUTES
above. data.bs.ch, data.tg.ch and data.bl.ch are asked only under their
written permissions (the listed datasets skip the robots.txt read;
anything else on those hosts is still refused).
"""

from __future__ import annotations

import argparse
import csv
import datetime
import html
import io
import json
import os
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src import ch_store, db, drain, filter as filt  # noqa: E402
from src.http import FetchError, HttpClient  # noqa: E402
from src.robots_guard import GuardedClient, RobotsRefused  # noqa: E402

FEED = "ch-cantons"
TAXONOMY_DE = os.path.join(ROOT, "config", "taxonomy-atch.yaml")
TAXONOMY_FR = os.path.join(ROOT, "config", "taxonomy-fr.yaml")
TAXONOMY_IT = os.path.join(ROOT, "config", "taxonomy-it.yaml")
TAXONOMY_COUNTRY = "ch"
BUDGET_S = 420

CANTONS = {
    "zh": "Kantonsrat Zürich",
    "be": "Grosser Rat Bern",
    "ge": "Grand Conseil de Genève",
    "vd": "Grand Conseil vaudois",
    "ti": "Gran Consiglio ticinese",
    "sg": "Kantonsrat St. Gallen",
    "bl": "Landrat Basel-Landschaft",
    "bs": "Grosser Rat Basel-Stadt",
    "tg": "Grosser Rat Thurgau",
    "ag": "Kanton Aargau (Gesetzessammlung)",
}
# Geneva last: its search is the slow one (see GE_TERMS), so a short budget
# costs Geneva, not the others.
ORDER = ("zh", "be", "sg", "bl", "bs", "tg", "ag", "vd", "ti", "ge")
LANGUAGE = {"zh": "de", "be": "de", "ge": "fr", "vd": "fr", "ti": "it", "sg": "de", "bl": "de",
            "bs": "de", "tg": "de", "ag": "de"}
# Cantons with no submission date in the source (see STATUS AND DATES).
UNDATED = ("ge", "vd", "ti", "bs")

# --- Zuerich -------------------------------------------------------------------
ZH_API = "https://parlzhcdws.cmicloud.ch/parlzh5/cdws/Index/GESCHAEFT/searchdetails"
# The Geschaeft records' XML namespace (an identifier, in Clark notation).
ZH_G = "{http://www.cmiag.ch/cdws/Geschaeft}"
ZH_NS = {"g": ZH_G.strip("{}")}
ZH_PAGE = 25
ZH_MAX_PAGES = 12
ZH_NEW_DAYS = 45
ZH_URL = "https://www.kantonsrat.zh.ch/geschaefte/geschaeft/?id={0}"
ZH_QUESTIONS = ("Anfrage", "Interpellation", "Dringliche Anfrage")

# --- Bern ----------------------------------------------------------------------
BE_GESCHAEFT = "https://ogd.parl.apps.be.ch/data/geschaeft.json"
BE_VOTES = "https://ogd.parl.apps.be.ch/data/abstimmung_tagblatt.json"
BE_SINCE = "2022-06-01"     # the legislature began on 1 June 2022
BE_URL = ("https://www.gr.be.ch/de/start/geschaefte/geschaeftssuche/"
          "geschaeftsdetail.html?guid={0}")
# Appointments, pardons and deadline extensions are never on our ground.
BE_SKIP = ("Ernennung / Wahl", "Begnadigung / Straferlass", "Fristverlängerung Vollzug",
           "Konzession")
BE_QUESTIONS = ("Interpellation", "Anfrage")

# --- Geneva --------------------------------------------------------------------
GE_SEARCH = "https://ge.ch/grandconseil/searchm/search/index"
GE_DETAIL = "https://ge.ch/grandconseil/searchm/search/index?q={0}&m=0"
# One search per term, the last year, the first page (the newest objects).
# French words of our areas (taxonomy-fr decides what is on our ground;
# these only choose what to read). MEASURED 13 October 2026: the search
# answers a narrow term in under a second and a broad one ("genre",
# "famille") in 12 to 13 seconds, so the list is short and the broadest
# words are left out.
GE_TERMS = ("avortement", "interruption de grossesse", "suicide assisté",
            "assistance au suicide", "fin de vie", "soins palliatifs", "genre",
            "transgenre", "conversion", "éducation sexuelle", "santé sexuelle",
            "laïcité", "voile", "prostitution", "gestation pour autrui",
            "procréation", "liberté d'expression")
GE_PAGES = 1
GE_MONTHS = {"janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
             "juil": 7, "août": 8, "aout": 8, "sept": 9, "oct": 10, "nov": 11,
             "déc": 12, "dec": 12}
GE_QUESTIONS = ("Q", "QUE", "IUE")

# --- Vaud ----------------------------------------------------------------------
VD_BASE = "https://www.vd.ch/gc/liste-des-objets-en-attente-de-traitement-par-le-grand-conseil/"
VD_PAGES = ("departement-des-institutions-et-du-territoire-et-du-sport",
            "departement-de-lenseignement-et-de-la-formation",
            "departement-de-la-jeunesse-de-lenvironnement-et-de-la-securite",
            "departement-de-la-sante-et-de-laction-sociale",
            "departement-de-leconomie-de-linnovation-de-lemploi-et-du-patrimoine",
            "departement-de-la-culture-des-infrastructures-et-des-ressources-humaines",
            "departement-des-finances-et-de-lagriculture",
            "grand-conseil")
VD_KINDS = {"MOT": "Motion", "POS": "Postulat", "INI": "Initiative", "RAP": "Rapport",
            "EMPL": "Exposé des motifs et projet de loi", "EMPD": "Exposé des motifs et projet de décret",
            "PET": "Pétition", "INT": "Interpellation", "SIMP": "Simple question",
            "QUE": "Question", "DEC": "Projet de décret", "LOI": "Projet de loi"}

# --- Ticino --------------------------------------------------------------------
TI_ODG = "https://www4.ti.ch/poteri/gc/attivita/ordine-del-giorno/"
TI_ACT = ("https://www4.ti.ch/index.php?id=83064&r=1&user_gcparlamento_pi8[attid]={0}"
          "&user_gcparlamento_pi8[tatid]={1}")
TI_MONTHS = {"gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
             "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11,
             "dicembre": 12}

# --- St. Gallen (via www.ratsinfo.sg.ch) ------------------------------------------
SG_API = "https://www.ratsinfo.sg.ch/api/"
SG_COMMITTEE = 468           # the Kantonsrat (the RIS's default committee)
SG_PAGE = 100
SG_MAX_PAGES = 6
SG_DAYS = 60                 # business changed in the last SG_DAYS days
SG_VOTE_DAYS = 120
SG_VOTE_PAGES = 4
SG_VOTE_DETAILS = 15         # tallies read per run, for votes on business on our ground
SG_URL = "https://www.ratsinfo.sg.ch/businesses/{0}"
SG_VOTE_URL = "https://www.ratsinfo.sg.ch/votings/{0}"
SG_QUESTIONS = ("Einfache Anfrage", "Interpellation")

# --- Basel-Landschaft (via baselland.talus.ch, the fallback since 13 October 2026) --
BL_NEW = "https://baselland.talus.ch/de/politik/cdws/neuste-geschaefte.php"
BL_URL = "https://baselland.talus.ch/de/politik/cdws/geschaeft.php?gid={0}"
BL_QUESTIONS = ("Interpellation", "Schriftliche Anfrage", "Fragestunde")

# --- Basel-Stadt (via grosserrat.bs.ch) ---------------------------------------------
BS_NEW = "https://grosserrat.bs.ch/ratsbetrieb/neue-vorstoesse"
BS_VERSAND = "https://grosserrat.bs.ch/ratsbetrieb/neue-berichte-und-schreiben"
BS_URL = "https://grosserrat.bs.ch/ratsbetrieb/geschaefte/{0}"
BS_KINDS = ("Interpellation", "Schriftliche Anfrage", "Kleine Anfrage", "Motion", "Anzug",
            "Budgetpostulat", "Vorgezogenes Budgetpostulat", "Planungsanzug", "Planungsauftrag",
            "Petition", "Ratschlag", "Bericht", "Schreiben", "Standesinitiative", "Resolution")
BS_QUESTIONS = ("Interpellation", "Schriftliche Anfrage")

# --- Thurgau (via grgeko.tg.ch) -------------------------------------------------------
TG_PENDING = "https://grgeko.tg.ch/de/web/grgeko/pendente-geschaefte"
TG_QUESTIONS = ("Interpellation", "Einfache Anfrage")

# --- Aargau (via gesetzessammlungen.ag.ch) ----------------------------------------------
AG_INDEX = "https://gesetzessammlungen.ag.ch/api/de/change_documents/lightweight_index"
AG_URL = "https://gesetzessammlungen.ag.ch/app/de/change_documents/{0}"
AG_SINCE = "2025-01-01"      # the Grosser Rat's legislature began in January 2025

# --- Basel-Stadt and Thurgau open data (written permission, 13 October 2026) ------
# Both portals' robots.txt disallows /api/; both owners wrote to say targeted
# API use is welcome (src/robots_guard.PERMISSIONS, docs/robots-runtime.md,
# "Written permissions"). Basel-Stadt: CC BY 4.0, the data source must be
# linked; Thurgau: CC0. Every act and vote read here carries its dataset link
# (ch_canton_acts.source_url / ch_canton_divisions.source_url). Exports,
# filtered server-side to the window and fetched in date batches (Basel-Stadt
# asked for batches if the API is slow); about one weekly run's volume.
BS_ODS = "https://data.bs.ch/api/explore/v2.1/catalog/datasets/"
POLITE_HOSTS = ("data.bs.ch", "data.tg.ch", "data.bl.ch", "grosserrat.bs.ch")
POLITE_S = 3.0              # seconds between two requests to one of these hosts
BS_SETS = {"geschaefte": "100311", "dokumente": "100313", "vorgaenge": "100314",
           "abstimmungen": "100186"}
# Dataset links go straight to the page (15 October 2026): data.bs.ch and
# data.bl.ch answer /explore/dataset/<id>/ with a 302 to /explore/assets/<id>/.
BS_DATASET = "https://data.bs.ch/explore/assets/{0}/"
BS_ITEM = "https://data.bs.ch/explore/assets/100311/?refine=signatur_ges%3A{0}"
BS_LICENCE = "CC BY 4.0, Parlamentsdienst des Grossen Rates Basel-Stadt"
BS_API_DAYS = 45            # businesses begun or ended, documents and steps since then
BS_VOTE_DAYS = 60           # votes: the first read; later runs start at the newest stored
BS_BATCH_DAYS = 14          # one export per fortnight of votes
BS_SKIP = ("Wahl", "Rücktritt", "Abbitte", "Urteil", "Mutation", "Personal", "Anlass")
BS_API_QUESTIONS = ("Interpellation", "Schriftliche Anfrage", "Kleine Anfrage")
BS_POSITIONS = {"J": "Ja", "N": "Nein", "E": "Enthaltung", "A": "Abwesend", "P": "Präsident"}
BS_VOTE_SKIP = ("Anwesenheit", "ungültig")
BS_GES_FIELDS = ("beginn_ges,ende_ges,signatur_ges,status_ges,titel_ges,ga_rr_gr,url_ges,"
                 "name_urheber,vorname_urheber,name_vorname_urheber,partei_kname_urheber,"
                 "gremientyp_urheber,name_vorname_miturheber")
BS_VOTE_FIELDS = ("datum,anr,abst_nr,typ,traktandum,subtraktandum,geschaeft,signatur_ges,"
                  "signatur_dok,anz_j,anz_n,anz_e,anz_a,anz_p,mitglied_vorname,"
                  "mitglied_nachname,mitglied_name,fraktion,entscheid_mitglied,gr_uni_nr,"
                  "url_abstimmung_dok")

# --- Basel-Stadt: the Grand Council's own raw data exports (13 October 2026) ---------
# Peter Frankenbach, IT lead and webmaster of the Parlamentsdienst des Grossen
# Rates Basel-Stadt, offered these exports of the Grand Council's business
# system (GRIBS) on 13 October 2026 in place of data.bs.ch, whose robots.txt
# is outside his control. grosserrat.bs.ch's robots.txt allows /component/ to
# every agent but the AI crawlers it names, so the run-time guard asks it and
# no exemption is needed. Each table is the whole table, one request a run:
# ges (Geschaefte, the primary business list), dok (Dokumente, dated) and vor
# (Vorgaenge, the Grosser Rat's steps) with siz (Sitzungen, the sitting
# dates vor refers to by number). JSON first, the CSV of the same table if
# the JSON fails. The rows are diffed against the store: only business begun,
# ended or touched in the window, or closed since we stored it, is kept.
# The exporter has no votes table: votes stay on data.bs.ch 100186.
BS_GRIBS = ("https://grosserrat.bs.ch/component/gribs?chosentable={0}&view=exporter"
            "&Itemid=105&format={1}")
BS_GRIBS_TABLES = {"geschaefte": "ges", "dokumente": "dok", "vorgaenge": "vor", "sitzungen": "siz",
                   "zuweisungen": "zuw", "personen": "adr", "gremien": "gre"}
# 15 October 2026: Peter Frankenbach's further exports (email of 13 October
# 2026; daily download allowed, the data are refreshed nightly about 03:00):
# zuw (Zuweisungen an Gremien: which committee a business is assigned to,
# and when that assignment was completed) and adr (Personen / Adressen: the
# Grand Council's members, for authors' and voters' parties). gre (Gremien,
# listed on the same public exporter) names the committees zuw refers to by
# number. adr also carries addresses, phone numbers and e-mail addresses:
# only the member number, the name and the party are read, in memory, never
# stored (the exports are not archived either).
BS_GES_URL = "https://grosserrat.bs.ch/?gnr={0}"      # the Grand Council's page of a business
BS_GRIBS_STATUS = {"A": "Abgeschlossen", "B": "In Bearbeitung"}

TG_ODS = "https://data.tg.ch/api/explore/v2.1/catalog/datasets/"
TG_SETS = {"geschaefte": "sk-stat-140", "urheber": "sk-stat-141", "abstimmungen": "sk-stat-136"}
TG_DATASET = "https://data.tg.ch/explore/dataset/{0}/"
TG_ITEM = "https://data.tg.ch/explore/dataset/sk-stat-140/table/?q={0}"
TG_LICENCE = "CC0 1.0, Staatskanzlei Kanton Thurgau"
TG_API_DAYS = 45
TG_VOTE_SINCE = "2024-06-01"   # the 2024-2028 legislature: the first read's start
TG_BATCH_DAYS = 92             # one export per quarter of votes
TG_SKIP = ("Wahlgeschäft", "Einbürgerungsgesuch", "Begnadigungsgesuch")
TG_API_QUESTIONS = ("Interpellation", "Einfache Anfrage", "Fragestunde")
TG_STEPS = (("datum_beantwortung", "vom Regierungsrat beantwortet"),
            ("datum_erheblicherklaerung", "erheblich erklärt"),
            ("datum_behoerdenreferendum", "Behördenreferendum"),
            ("datum_volksabstimmung", "Volksabstimmung"),
            ("datum_geschaeft_abschluss", "Abschluss"))
TG_FLAGS = (("erheblichkeitserklaerung", "Erheblicherklärung"),
            ("teilerheblicherklaerung", "Teilerheblicherklärung"),
            ("rueckzug", "Rückzug"), ("abschreibung", "Abschreibung"))
# A member's vote that is not Ja, Nein, Enthaltung or an absence names an
# option of a vote between motions ('Antrag GFK', 'Kommissionsfassung').
TG_PLAIN = ("Ja", "Nein", "Enthaltung", "Abwesend", "Abwesend/Keine Stimmabgabe",
            "Keine Stimmabgabe")

# --- Basel-Landschaft: data.bl.ch (written permission, 13 October 2026) ------------
# Johannes Hool, Statistisches Amt (Office for Data and Statistics, Finance and
# Church Directorate) wrote that CitizenGO-ParlMonitor/1.0 may retrieve the
# Landrat's open data, votes included, through the data.bl.ch API, at scale;
# robots.txt's /api/ rule is for generic crawlers. The Landeskanzlei's datasets
# (opendata.swiss terms_by: free use, the source must be cited):
BL_ODS = "https://data.bl.ch/api/explore/v2.1/catalog/datasets/"
BL_SETS = {"geschaefte": "13090", "urheber": "13140", "dokumente": "13130",
           "abstimmungen": "13080"}
BL_DATASET = "https://data.bl.ch/explore/assets/{0}/"
BL_LICENCE = ("free use, source must be cited (opendata.swiss terms_by), "
              "Landeskanzlei des Kantons Basel-Landschaft")
BL_API_DAYS = 45               # business begun or ended, documents since then
BL_VOTE_SINCE = "2023-07-01"   # the 2023-2027 legislature: the first read's start
BL_BATCH_DAYS = 92             # one export per quarter of votes (about 90 rows a vote)
BL_SKIP = ("Begnadigung",)
BL_API_QUESTIONS = ("Interpellation", "Schriftliche Anfrage", "Fragestunde")
BL_AUTHORS = ("Urheber", "Urheberin")
BL_COSIGNERS = ("Mitunterzeichner", "Mitunterzeichnerin")
BL_POSITIONS = {"abwesend": "Abwesend"}
BL_GES_FIELDS = ("titel,laufnummer,status,komission,beginn,ende,stand_lr,geschaeft_id,"
                 "ueberweisungsdatum,geschaeftstyp,vorstossart")
BL_VOTE_FIELDS = ("person_name,person_vorname,geschaeft_titel,abstimmung_gegenstand,"
                  "abstimmung_datum,abstimmung_art,person_fraktion,person_partei,person_id,"
                  "abstimmung_id,geschaeft_id,traktandum_id")
BL_CHUNK = 60                  # business numbers or ids per "in (...)" filter


# --- small helpers -------------------------------------------------------------

def text(s):
    """Tags dropped, entities decoded, whitespace folded."""
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def iso(s):
    """'2026-10-02T00:00:00.000', '2026-10-02' or '08.10.2026' / '08.10.26' -> '2026-10-02'."""
    s = (s or "").strip()
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)", s)
    if m:
        return "-".join(m.groups())
    m = re.match(r"(\d\d?)\.(\d\d?)\.(\d{4}|\d\d)\b", s)
    if m:
        y = m.group(3) if len(m.group(3)) == 4 else "20" + m.group(3)
        return "{0}-{1:02d}-{2:02d}".format(y, int(m.group(2)), int(m.group(1)))
    return None


def epoch_day(ms):
    """Bern's dates are epoch milliseconds at local midnight: the day in Bern."""
    if ms in (None, ""):
        return None
    if isinstance(ms, str):
        return iso(ms)
    return datetime.datetime.utcfromtimestamp(ms / 1000 + 43200).date().isoformat()


# --- parsers (pure: text in, acts out) -----------------------------------------

def zh_url(query, start=1, size=ZH_PAGE):
    return ZH_API + "?" + urllib.parse.urlencode(
        {"q": query, "l": "de-CH", "s": start, "m": size}, quote_via=urllib.parse.quote)


def zh_query_new(today, days=ZH_NEW_DAYS):
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()
    return 'beginn_start > "{0} 00:00:00" sortBy beginn_start/sort.descending'.format(since)


def zh_query_changed(seq):
    return "seq > {0} sortBy seq/sort.ascending".format(int(seq))


def _zh(el, path):
    got = el.findtext("g:" + path.replace("/", "/g:"), namespaces=ZH_NS)
    return re.sub(r"\s+", " ", got or "").strip()


def parse_zuerich(raw):
    """(acts, numHits) from one searchdetails page (bytes or str)."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    root = ET.fromstring(raw)
    out = []
    for g in root.iter(ZH_G + "Geschaeft"):
        guid = g.get("OBJ_GUID")
        number = _zh(g, "KRNr") or _zh(g, "VorlageNr")
        if not guid or not number:
            continue
        kind = _zh(g, "Geschaeftsart") or "Geschäft"
        steps = []
        for s in g.findall("g:Ablaufschritte/g:Ablaufschritt", ZH_NS):
            when = iso(_zh(s, "Sitzungsdatum/Start")) or iso(_zh(s, "Sitzungsdatum/Text"))
            steps.append((when or "", _zh(s, "StatusText") or _zh(s, "AblaufschrittTyp")))
        steps.sort(key=lambda x: x[0])
        status, status_date = (steps[-1][1] or None, steps[-1][0] or None) if steps else (None, None)
        signers = []
        for b in g.findall("g:Beteiligungen/g:Beteiligung", ZH_NS):
            name = " ".join(x for x in (_zh(b, "Vorname"), _zh(b, "Name")) if x)
            party = _zh(b, "ParteiKurzname")
            role = _zh(b, "Rolle")
            signers.append(("{0} ({1})".format(name, party) if party else name, role))
        first = [n for n, r in signers if r.lower().startswith("erst")] or [n for n, _ in signers[:1]]
        initiative = first[0] if first else None
        if initiative and len(signers) > 1:
            initiative = "{0} and {1} other(s)".format(initiative, len(signers) - 1)
        out.append({
            "key": "zh/" + number, "canton": "zh", "kind": kind, "number": number,
            "label": "{0} {1}".format(kind, number) if kind != "Vorlage" else "Vorlage " + number,
            "title": _zh(g, "Titel"), "title_fr": None,
            "presented": iso(_zh(g, "Beginn/Start")) or iso(_zh(g, "Beginn/Text")),
            "status": status, "status_date": status_date, "dated": True,
            "initiative": initiative, "committee": _zh(g, "BehandelndeKommission") or None,
            "url": ZH_URL.format(guid), "seq": int(g.get("SEQ") or 0) or None,
            "question": kind in ZH_QUESTIONS})
    return out, int(root.get("numHits") or 0)


def parse_bern(data, since=BE_SINCE):
    """Acts from Bern's geschaeft.json (the decoded dict)."""
    out = []
    for r in data.get("data") or []:
        kind = r.get("geschaeft_typ_deutsch") or "Geschäft"
        if kind in BE_SKIP or not r.get("geschaeft_nr"):
            continue
        presented = epoch_day(r.get("geschaeft_vorstoss_eingereicht_datum"))
        last = iso(r.get("geschaeft_letzte_behandlung_datum") or "")
        if max(presented or "", last or "") < since:
            continue
        decision = r.get("geschaeft_beschluss_deutsch")
        detail = r.get("geschaeft_beschlussdetail_deutsch")
        status = None
        if decision:
            status = decision + (" ({0})".format(detail) if detail else "")
            # The export runs a point-by-point decision together: '...)Ziffer 2: ...'.
            status = re.sub(r"\)(?=[A-ZÄÖÜ])", ") ", status)
        elif epoch_day(r.get("geschaeft_vorstoss_zurueckgezogen_datum")):
            status = "Zurückgezogen"
        status_date = last or epoch_day(r.get("geschaeft_vorstoss_zurueckgezogen_datum"))
        who = " ".join(x for x in (r.get("geschaeft_vorstoss_hauptvorstoesser_vorname"),
                                   r.get("geschaeft_vorstoss_hauptvorstoesser_name")) if x)
        if who and r.get("geschaeft_vorstoss_fraktion_name_deutsch"):
            who += " ({0})".format(r["geschaeft_vorstoss_fraktion_name_deutsch"])
        if not who and r.get("geschaeft_vorstoss_kommission_name_deutsch"):
            who = r["geschaeft_vorstoss_kommission_name_deutsch"]
        if not who and r.get("geschaeft_federfuehrung_name_deutsch"):
            who = "Regierungsrat ({0})".format(r["geschaeft_federfuehrung_name_deutsch"])
        if r.get("geschaeft_vorstoss_dringlichkeit_gewaehrt") == "J":
            kind_label = kind + " (dringlich)"
        else:
            kind_label = kind
        number = r["geschaeft_nr"]
        out.append({
            "key": "be/" + number, "canton": "be", "kind": kind, "number": number,
            "label": "{0} {1}".format(kind_label, number + (" ({0})".format(
                r["geschaeft_vorstoss_nummer"]) if r.get("geschaeft_vorstoss_nummer") else "")),
            "title": (r.get("geschaeft_titel_deutsch") or "").strip(),
            "title_fr": (r.get("geschaeft_titel_franz") or "").strip() or None,
            "presented": presented, "status": status, "status_date": status_date,
            "dated": True, "initiative": who or None,
            "committee": r.get("geschaeft_vorberatende_kommission_deutsch") or None,
            "url": BE_URL.format(r["geschaeft_uid"]) if r.get("geschaeft_uid") else None,
            "seq": None, "question": kind in BE_QUESTIONS})
    return out


_BE_NR = re.compile(r"(\d{4}\.[A-Z]+\.\d+)")
_BE_DECISION = re.compile(r"(?:Annahme|Ablehnung|Zustimmung|Nichteintreten|Eintreten|Rückweisung)")


def parse_bern_votes(data, since=BE_SINCE):
    """Votes from Bern's abstimmung_tagblatt.json: the business number, what
    was voted on and the result are read off the published description."""
    out = []
    for r in data.get("data") or []:
        when = (r.get("abstimmung_datum_uhrzeit") or "")[:10]
        if not r.get("abstimmung_uid") or when < since:
            continue
        desc = re.sub(r"\s+", " ", r.get("abstimmung_beschreibung") or "").strip()
        nr = _BE_NR.search(desc)
        rest = desc[nr.end():] if nr else desc
        head = rest.split("Ja / Oui")[0]
        # The result is the LAST decision word before the tally ('Annahme /
        # Adoption'); what precedes it is what was voted on, which can itself
        # name a decision ('Annahme mit Auflagen der BaK / adoption ...').
        found = list(_BE_DECISION.finditer(head))
        cut = found[-1].start() if found else len(head)
        subject = head[:cut].strip(" :,")
        # German and French run together: 'Antrag 2, BaKProposition 2, CIAT'.
        subject = re.sub(r"(?<=\S)(Proposition|Amendement)\b", r" / \1", subject)
        result = head[cut:].strip() if found else None

        def num(v):
            try:
                return int(float(v)) if v not in (None, "") else None
            except (TypeError, ValueError):
                return None
        out.append({
            "key": "be/v/" + r["abstimmung_uid"], "canton": "be",
            "act_key": "be/" + nr.group(1) if nr else None, "date": when,
            "subject": subject or None, "result": result,
            "yes": num(r.get("abstimmung_resultat_anzahl_ja")),
            "no": num(r.get("abstimmung_resultat_anzahl_nein")),
            "abstain": num(r.get("abstimmung_resultat_anzahl_enthalten")),
            "url": r.get("abstimmung_url")})
    return out


_GE_BLOCK = re.compile(r'<div class="lighter">(.*?)</div>', re.S)
_GE_LABEL = re.compile(r"^([A-Z]{1,4})\s+(\d+)(?:-([A-Z]\d?))?\s*(.*)$", re.S)


def ge_month(s):
    """'Janv. 2026' -> '2026-01'."""
    m = re.match(r"([A-Za-zéèûôà]+)\.?\s+(\d{4})", (s or "").strip())
    if not m:
        return None
    month = GE_MONTHS.get(m.group(1).lower()[:4].rstrip(".")) or GE_MONTHS.get(m.group(1).lower()[:3])
    return "{0}-{1:02d}".format(m.group(2), month) if month else None


def ge_day(s):
    """'23 janv. 2026' -> '2026-01-23'."""
    m = re.match(r"(\d{1,2})\s+([A-Za-zéèûôà]+)\.?\s+(\d{4})", (s or "").strip())
    if not m:
        return None
    month = GE_MONTHS.get(m.group(2).lower()[:4].rstrip(".")) or GE_MONTHS.get(m.group(2).lower()[:3])
    return "{0}-{1:02d}-{2:02d}".format(m.group(3), month, int(m.group(1))) if month else None


def parse_geneva(page):
    """Documents from one page of the Grand Conseil's search: one dict per
    document, keyed on its object (merge_geneva folds them)."""
    out = []
    for block in _GE_BLOCK.findall(page):
        link = re.search(r'<a href="([^"]+\.pdf)"[^>]*class="pdf-link"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        label = text(link.group(2))
        m = _GE_LABEL.match(label)
        if not m:
            continue
        kind, number, suffix, title = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        month = ge_month(text((re.search(r'class="smaller date">(.*?)</span>', block, re.S)
                               or [None, ""])[1]))
        deci = re.search(r'<span class="smaller">\s*(.*?)<span class="date-deci">(.*?)</span>',
                         block, re.S)
        decision = text(deci.group(1)) if deci else None
        decision_day = ge_day(text(deci.group(2))) if deci else None
        out.append({"kind": kind, "number": number, "suffix": suffix, "title": title,
                    "month": month, "decision": decision or None, "decision_day": decision_day,
                    "pdf": link.group(1)})
    return out


_GE_OBJECT = re.compile(r"(?:la |le |l.)?(proposition de motion|proposition de résolution|"
                        r"projet de loi constitutionnelle|projet de loi|pétition|"
                        r"initiative populaire(?: cantonale)?)\s+(.*)$", re.I | re.S)
_GE_VERB = re.compile(r"\s(demandant|modifiant|sur|pour|visant|concernant|instituant|"
                      r"ouvrant|accordant|abrogeant|approuvant|relatif|relative|contre|en faveur)\b",
                      re.I)


def ge_split_title(title):
    """(the object's own words, its authors) from a document title. A
    report's or an answer's title names the object it is about ('Rapport de
    la commission ... chargée d'étudier la proposition de motion de A, B :
    Title'); the object's words are what is classified and shown."""
    title = (title or "").strip()
    m = _GE_OBJECT.search(title) if title.lower().startswith(("rapport", "réponse")) else None
    rest = m.group(2).strip() if m else title
    authors = None
    cde = re.match(r"du Conseil d.Etat\s+(.*)$", rest, re.S)
    if cde:
        authors, rest = "Conseil d'Etat", cde.group(1).strip()
    elif rest.lower().startswith("de "):
        colon = rest.find(" : ")
        verb = _GE_VERB.search(rest)
        if colon > 0 and (not verb or colon < verb.start()):
            authors, rest = rest[3:colon].strip(), rest[colon + 3:].strip()
        elif verb:
            authors, rest = rest[3:verb.start()].strip(), rest[verb.start():].strip()
    elif not m:
        q = re.match(r"(?:Question écrite|Question écrite urgente|Interpellation urgente écrite)"
                     r" de ([^:]+?)\s*:\s*(.*)$", rest, re.S)
        if q:
            authors, rest = q.group(1).strip(), q.group(2).strip()
    if authors and authors.lower().startswith(("la commission", "le conseil", "la ")):
        authors = None
    return (rest if len(rest) > 15 else title), authors


def merge_geneva(docs):
    """One act per object: the base document's title where we saw it, the
    latest document's decision and month."""
    acts = {}
    for d in docs:
        key = "ge/{0}{1}".format(d["kind"], d["number"])
        a = acts.setdefault(key, {"docs": [], "kind": d["kind"], "number": d["number"]})
        a["docs"].append(d)
    out = []
    for key, a in acts.items():
        docs = sorted(a["docs"], key=lambda d: (d["suffix"] or "", d["month"] or ""))
        base = [d for d in docs if not d["suffix"]]
        latest = max(docs, key=lambda d: (d["decision_day"] or "", d["month"] or "",
                                          d["suffix"] or ""))
        title, authors = ge_split_title((base or docs)[0]["title"])
        status = latest["decision"]
        if not status and latest["suffix"]:
            status = "Rapport {0} {1}-{2} publié".format(a["kind"], a["number"], latest["suffix"])
        label = "{0} {1}{2}".format(a["kind"], a["number"],
                                    "-" + latest["suffix"] if latest["suffix"] else "")
        if latest["month"]:
            label += " ({0})".format(latest["month"])
        out.append({
            "key": key, "canton": "ge", "kind": a["kind"], "number": a["number"],
            "label": label, "title": title, "title_fr": None, "presented": None,
            "status": status, "status_date": latest["decision_day"],
            "dated": bool(latest["decision_day"]), "initiative": authors,
            "committee": None,
            "url": GE_DETAIL.format(urllib.parse.quote_plus("{0} {1}".format(a["kind"], a["number"]))),
            "seq": None, "question": a["kind"] in GE_QUESTIONS})
    return out


_VD_ID = re.compile(r"\((\d\d_[A-Z]+_\d+)\)")


def parse_vaud(page):
    """Acts from one of Vaud's lists of objects awaiting treatment."""
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", page, re.S):
        m = _VD_ID.search(text(p))
        if not m or not re.search(r'href="[^"]*' + re.escape(m.group(1)), p):
            continue
        ident = m.group(1)
        parts = re.split(r"<br\s*/?>", p)
        head = text(re.sub(r"\(pdf,[^)]*\)", "", text(parts[0]))).replace("(" + ident + ")", "").strip()
        head = re.sub(r"^\s*\)?\s*", "", head)
        kind_code = ident.split("_")[1]
        kind = VD_KINDS.get(kind_code, kind_code)
        author, title = None, head
        hm = re.match(r"(Motion|Postulat|Initiative|Interpellation|Pétition|Simple question|"
                      r"Question|Rapport|Exposé des motifs[^-]*?)\s+(.*?)\s+-\s+(.*)$", head, re.S)
        if hm:
            author, title = hm.group(2).strip(), hm.group(3).strip()
            title = re.sub(r"^(Motion|Postulat)\s*:\s*", "", title)
        committee = text(parts[1]) if len(parts) > 1 and "commission" in parts[1].lower() else None
        steps = [text(x) for x in parts[2:]] if committee else [text(x) for x in parts[1:]]
        status = re.sub(r"\s*\(pdf,[^)]*\)", "", "; ".join(s for s in steps if s)).strip() or None
        year = "20" + ident[:2]
        out.append({
            "key": "vd/" + ident, "canton": "vd", "kind": kind, "number": ident,
            "label": "{0} ({1})".format(kind, ident), "title": title, "title_fr": None,
            "presented": None, "status": status, "status_date": None, "dated": False,
            "initiative": author, "committee": committee,
            "url": "https://www.vd.ch" + re.search(r'href="([^"]*' + re.escape(ident) + r'[^"]*)"',
                                                    p).group(1),
            "seq": None, "question": kind_code in ("INT", "SIMP", "QUE"), "year": year})
    return out


_TI_DAY = re.compile(r"((?:Luned|Marted|Mercoled|Gioved|Venerd|Sabato|Domenica)\S*)\s+(\d{1,2})\s+"
                     r"([a-z]+)\s+(\d{4})")


def ti_session(page):
    """'Lunedì 05 ottobre 2026 - 14:00' -> ('2026-10-05', 'lunedì 5 ottobre 2026')."""
    m = _TI_DAY.search(text(page))
    if not m or m.group(3) not in TI_MONTHS:
        return None, None
    return ("{0}-{1:02d}-{2:02d}".format(m.group(4), TI_MONTHS[m.group(3)], int(m.group(2))),
            "{0} {1} {2} {3}".format(m.group(1).lower(), int(m.group(2)), m.group(3), m.group(4)))


def parse_ticino(page):
    """Points of the Gran Consiglio's order of the day that carry an act."""
    session, session_words = ti_session(page)
    out = []
    rows = re.split(r'<div class="row odgOggetto">', page)[1:]
    for row in rows:
        num = re.search(r'numOggetto">\s*(\d+)', row)
        dept = re.search(r'<div class="col-xs-2">\s*([A-Z]+)', row)
        body = re.search(r'<div class="col-xs-7">(.*?)</div>', row, re.S)
        if not body:
            continue
        acts = re.findall(r"\[attid\]=(\d+)&amp;user_gcparlamento_pi8\[tatid\]=(\d+)", body.group(1))
        if not acts:
            continue
        paras = [text(p) for p in re.findall(r"<p>(.*?)</p>", body.group(1), re.S)]
        paras = [p.lstrip("•").strip() for p in paras if p]
        heads = [p for p in paras if not p.startswith("-") and not p.isupper()]
        procedure = [p for p in paras if p.isupper()]
        title = heads[0] if heads else paras[0]
        kind = re.match(r"(Mozione|Iniziativa parlamentare|Iniziativa cantonale|"
                        r"Risoluzione generale|Petizione|Interpellanza|Interrogazione|Messaggio|"
                        r"Rapporto)", title)
        if not kind:
            msg = re.search(r"(Messaggio|Rapporto)\b", " ".join(paras))
            kind_text = msg.group(1) if msg else "Oggetto"
        else:
            kind_text = kind.group(1)
        attid, tatid = acts[0]
        status = "All'ordine del giorno del Gran Consiglio{0}".format(
            ", seduta di " + session_words if session_words else "")
        if procedure:
            status += " ({0})".format(", ".join(p.lower() for p in procedure))
        out.append({
            "key": "ti/" + attid, "canton": "ti", "kind": kind_text, "number": attid,
            "label": "{0}, punto {1} dell'ordine del giorno".format(
                kind_text, num.group(1) if num else "?"),
            "title": title, "title_fr": None, "body": " ".join(heads[1:]),
            "presented": None, "status": status, "status_date": session,
            "dated": bool(session), "initiative": None,
            "committee": dept.group(1) if dept else None,
            "url": TI_ACT.format(attid, tatid), "seq": None, "question": False})
    return out


# --- the alternative routes (access-routes, 13 October 2026) ----------------------

def sg_names(items):
    """{id: title} from the RIS's business_types or process_states list."""
    return {x.get("id"): re.sub(r"^(?:KR|PräsKR|stäKo|voKo)\s+", "", (x.get("title") or "").strip())
            for x in items or []}


def parse_sg_businesses(data, types, states):
    """(acts, the oldest 'touched' day on the page) from one /api/businesses page."""
    out, oldest = [], None
    for r in (data or {}).get("results") or []:
        if r.get("is_confidential") or not r.get("number"):
            continue
        kind = types.get(r.get("type_id")) or "Geschäft"
        touched = (r.get("touched") or "")[:10] or None
        oldest = min(oldest or touched or "9", touched or "9")
        status = states.get(r.get("process_state_id"))
        if r.get("end_date") and status:
            status += " ({0})".format(r["end_date"])
        number = r["number"]
        out.append({
            "key": "sg/" + number, "canton": "sg", "kind": kind, "number": number,
            "label": "{0} {1}".format(kind, number), "title": (r.get("title") or "").strip(),
            "title_fr": None, "presented": iso(r.get("begin_date") or ""), "status": status,
            "status_date": None, "dated": False, "initiative": None, "committee": None,
            "url": SG_URL.format(r["id"]), "seq": None, "question": kind in SG_QUESTIONS})
    return out, oldest


def parse_sg_votings(data):
    """[{id, date, title, act_key}] from one /api/votings page (no tallies)."""
    out = []
    for r in (data or {}).get("results") or []:
        item = r.get("agenda_item") or {}
        biz = item.get("business") or {}
        out.append({"id": r.get("id"), "date": (r.get("date") or "")[:10],
                    "title": (r.get("title") or "").strip() or (item.get("title") or "").strip(),
                    "act_key": "sg/" + biz["number"] if biz.get("number") else None,
                    "act_title": biz.get("title")})
    return out


def parse_sg_voting(detail, summary=None):
    """A ch_canton_divisions row from /api/votings/<id>: the published tally
    (yes, no, abstentions; absences are not a vote)."""
    res = (detail or {}).get("results") or {}
    yes, no = res.get("yes"), res.get("no")
    result = None
    if yes is not None and no is not None:
        result = "Angenommen" if yes > no else ("Abgelehnt" if no > yes else "Stimmengleichheit")
    summary = summary or {}
    return {"key": "sg/v/{0}".format(detail.get("id")), "canton": "sg",
            "act_key": summary.get("act_key"),
            "date": (detail.get("date") or summary.get("date") or "")[:10],
            "subject": (detail.get("title") or summary.get("title") or "").strip() or None,
            "result": result, "yes": yes, "no": no, "abstain": res.get("abstention"),
            "url": SG_VOTE_URL.format(detail.get("id"))}


_BL_ROW = re.compile(r'<tr>\s*<td>(\d\d\.\d\d\.\d{4})</td>\s*<td>\s*<a[^>]*gid=(\w+)"[^>]*>([^<]*)</a>\s*'
                     r'</td>\s*<td>\s*<a[^>]*>(.*?)</a>\s*</td>\s*<td>\s*(?:<a[^>]*>(.*?)</a>)?', re.S)
_BL_TEXT = re.compile(r"^Text (Motion|Postulat|Interpellation|Schriftliche Anfrage|Fragestunde|"
                      r"Verfahrenspostulat|Parlamentarische Initiative|Petition)")


def parse_bl(page):
    """Acts from the Landrat's newest documents: one act per business, its
    kind from its text or Vorlage, its status the newest document."""
    docs = {}
    for date, gid, number, title, doc in _BL_ROW.findall(page or ""):
        number = text(number)
        if not re.match(r"\d{4}/\d+", number):
            continue
        docs.setdefault(number, {"gid": gid, "title": text(title), "docs": []})
        docs[number]["docs"].append((iso(date), text(doc or "") or "Dokument"))
    out = []
    for number, d in docs.items():
        steps = sorted(d["docs"])
        kind, presented = "Geschäft", None
        for when, doc in steps:
            m = _BL_TEXT.match(doc)
            if m:
                kind, presented = m.group(1), when
                break
            if doc.startswith("Vorlage"):
                kind, presented = "Vorlage", when
                break
        when, doc = steps[-1]
        if _BL_TEXT.match(doc) or doc.startswith("Vorlage"):
            doc = "Eingereicht ({0})".format(doc)
        out.append({
            "key": "bl/" + number, "canton": "bl", "kind": kind, "number": number,
            "label": "{0} {1}".format(kind, number), "title": d["title"], "title_fr": None,
            "presented": presented, "status": doc, "status_date": when, "dated": True,
            "initiative": None, "committee": None, "url": BL_URL.format(d["gid"]), "seq": None,
            "question": kind in BL_QUESTIONS})
    return out


def bs_split(title):
    """(kind, author, words) from 'Interpellation Nr. 114 Franziska Stier
    betreffend Entsiegeln ...' (author None where the title names none)."""
    title = re.sub(r"\s+", " ", title or "").strip()
    kind = next((k for k in BS_KINDS if title.startswith(k)), None)
    if not kind:
        return None, None, title
    m = re.match(re.escape(kind) + r"(?:\s+Nr\.\s*\d+)?\s+(.*?)\s+betreffend\s+(.*)$", title)
    if m and kind not in ("Ratschlag", "Bericht", "Schreiben"):
        return kind, m.group(1).strip(), m.group(2).strip()
    return kind, None, title


_BS_ROW = re.compile(r'href="/ratsbetrieb/geschaefte/(\d+)"[^>]*>\s*(?:<span[^>]*>[^<]*</span>)?\s*'
                     r'(\d\d\.\d{4})\s*</a>\s*</td>\s*<td[^>]*>(.*?)</td>', re.S)


def parse_bs_new(page):
    """Acts from the new parliamentary motions page, one section per sitting
    they were lodged for."""
    out = []
    parts = re.split(r"Eingegangen für die Session des Grossen Rates vom (\d\d\.\d\d\.\d{4})", page or "")
    sections = [(parts[k], parts[k + 1]) for k in range(1, len(parts) - 1, 2)] or [(None, page or "")]
    for session, body in sections:
        status = "Eingereicht für die Sitzung vom {0}".format(session) if session else "Eingereicht"
        for gid, number, raw in _BS_ROW.findall(body):
            title = text(raw)
            kind, author, words = bs_split(title)
            kind = kind or "Vorstoss"
            out.append({
                "key": "bs/" + number, "canton": "bs", "kind": kind, "number": number,
                "label": "{0} {1}".format(kind, number), "title": words, "title_fr": None,
                "presented": None, "status": status, "status_date": None, "dated": False,
                "initiative": author, "committee": None, "url": BS_URL.format(gid), "seq": None,
                "question": kind in BS_QUESTIONS})
    return out


def parse_bs_versand(page):
    """[(date, category, number, business id, text)] from the Grossratsversand page."""
    out = []
    parts = re.split(r"Grossratsversand vom (\d\d\.\d\d\.\d{4})", page or "")
    for k in range(1, len(parts) - 1, 2):
        date = iso(parts[k])
        for table in re.findall(r'<table[^>]*summary="([^"]*)"[^>]*>(.*?)</table>', parts[k + 1], re.S):
            summary = html.unescape(table[0])
            if "Antworten" in summary:
                cat = "Schriftliche Antwort des Regierungsrates"
            elif "Ratschl" in summary:
                cat = "Ratschlag, Bericht oder Schreiben des Regierungsrates"
            else:
                cat = "Bericht oder Schreiben einer Kommission"
            for gid, number, raw in _BS_ROW.findall(table[1]):
                out.append((date, cat, number, gid, text(raw)))
    return out


def merge_bs(new_acts, versand):
    """One act per business: the motion page's entry where there is one,
    each business's newest Versand document as its dated status."""
    acts = {a["key"]: dict(a) for a in new_acts}
    for date, cat, number, gid, words in sorted(versand):
        key = "bs/" + number
        a = acts.get(key)
        if a is None:
            kind, author, title = bs_split(words)
            if kind in ("Bericht", "Schreiben") or not kind:
                kind = "Geschäft"
            a = acts[key] = {
                "key": key, "canton": "bs", "kind": kind, "number": number,
                "label": "{0} {1}".format(kind, number), "title": title, "title_fr": None,
                "presented": None, "initiative": author, "committee": None,
                "url": BS_URL.format(gid), "seq": None, "question": kind in BS_QUESTIONS}
        a["status"] = "{0}: {1}".format(cat, words)[:300]
        a["status_date"], a["dated"] = date, True
    return list(acts.values())


_TG_ROW = re.compile(r'<tr data-ri="\d+" data-rk="(\d+)".*?tg-legislatur">(.*?)</td>.*?'
                     r'tg-eingangsDatum">(.*?)</td>.*?tg-laufNummer">(.*?)</td>.*?'
                     r'tg-grgNummer">(.*?)</td>.*?tg-titel">(.*?)</td>', re.S)
_TG_KIND = re.compile(r"^(Motion|Interpellation|Einfache Anfrage|Parlamentarische Initiative|"
                      r"Standesinitiative|Leistungsmotion|Petition|Volksinitiative)\s+von\s+(.*?)\s+vom\s+"
                      r"\d{1,2}\.\s*\S+\s+\d{4}\s*[\"„“«](.*?)[\"“”»]?\s*$", re.S)


def parse_tg(page):
    """Acts from the Grosser Rat's list of pending business."""
    out = []
    for rk, leg, date, _lauf, grg, raw in _TG_ROW.findall(page or ""):
        title, leg, grg = text(raw), text(leg), text(grg)
        if not grg:
            continue
        m = _TG_KIND.match(title)
        if m:
            kind, author, words = m.group(1), m.group(2), m.group(3).strip()
        else:
            kind, author, words = ("Gesetz" if re.match(r"(Änderung des |Gesetz)", title) else
                                   "Geschäft"), None, title
        number = "{0}/{1}".format(leg, grg)
        out.append({
            "key": "tg/" + number, "canton": "tg", "kind": kind, "number": number,
            "label": "{0} (GRG-Nr. {1}, Legislatur {2})".format(kind, grg, leg),
            "title": words, "title_fr": None, "presented": iso(text(date)),
            "status": "Im Grossen Rat pendent", "status_date": None, "dated": False,
            "initiative": author, "committee": None, "url": TG_PENDING, "seq": None,
            "question": kind in TG_QUESTIONS})
    return out


def ag_kind(title):
    """The kind of act the title names first ('Verordnung zum EG
    Familienzulagengesetz' is an ordinance, not a law)."""
    low, best = (title or "").lower(), None
    for word, kind in (("verfassung", "Verfassung"), ("dekret", "Dekret"), ("gesetz", "Gesetz"),
                       ("verordnung", "Verordnung"), ("vereinbarung", "Vereinbarung"),
                       ("konkordat", "Konkordat"), ("abkommen", "Abkommen"),
                       ("richtlinie", "Richtlinien"), ("reglement", "Reglement")):
        at = low.find(word)
        if at >= 0 and (best is None or at < best[0]):
            best = (at, kind)
    return best[1] if best else "Erlass"


def parse_ag(data, since=AG_SINCE):
    """Acts from the Aargauische Gesetzessammlung's chronological index."""
    out = []
    for docs in (data or {}).values():
        for d in docs or []:
            day = iso(d.get("date_string") or "")
            if not day or day < since or not d.get("number"):
                continue
            title = (d.get("document_title") or "").strip()
            kind = ag_kind(title)
            out.append({
                "key": "ag/" + d["number"], "canton": "ag", "kind": kind, "number": d["number"],
                "label": "{0}, AGS {1}".format(kind, d["number"]), "title": title,
                "title_fr": None, "presented": day,
                "status": "In der Aargauischen Gesetzessammlung veröffentlicht",
                "status_date": day, "dated": True, "initiative": None, "committee": None,
                "url": AG_URL.format(d.get("id")), "seq": None, "question": False})
    return out


# --- Basel-Stadt and Thurgau, open-data APIs (written permission) ------------------

def ods_export(base, dataset, where, select=None, order_by=None):
    """An Opendatasoft v2.1 JSON export, filtered server-side (ODSQL)."""
    params = {"where": where, "timezone": "Europe/Zurich"}
    if select:
        params["select"] = select
    if order_by:
        params["order_by"] = order_by
    return base + dataset + "/exports/json?" + urllib.parse.urlencode(
        params, quote_via=urllib.parse.quote)


def batches(since, until, days):
    """[(start, end)] inclusive ISO-date windows of `days` covering since..until."""
    out, a = [], datetime.date.fromisoformat(since)
    end = datetime.date.fromisoformat(until)
    while a <= end:
        b = min(end, a + datetime.timedelta(days=days - 1))
        out.append((a.isoformat(), b.isoformat()))
        a = b + datetime.timedelta(days=1)
    return out


def _dmy(day):
    return "{2}.{1}.{0}".format(*day.split("-")) if day else ""


def _num(v):
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def parse_bs_api(rows, docs=(), steps=(), today=None, since=None, source=BS_ITEM, keep=(),
                 assignments=(), committees=None):
    """Acts from data.bs.ch: Geschaefte (100311, one row per co-author), each
    with its newest dated document (100313) or Grosser Rat step (100314) up
    to today as its status, in the dataset's own words. The Grand Council's
    own exports are mapped to the same rows (gribs_*) and read here too, with
    `source` their item link; `keep` names business numbers kept whatever
    the window (closed since we stored them). `assignments` (gribs_zuweisungen
    events) are steps too, and `committees` gives each business its committee."""
    today = today or datetime.date.today().isoformat()
    committees = committees or {}
    biz = {}
    for r in rows or []:
        sig = (r.get("signatur_ges") or "").strip()
        if not sig:
            continue
        b = biz.setdefault(sig, {"row": r, "co": set()})
        if r.get("name_vorname_miturheber"):
            b["co"].add(r["name_vorname_miturheber"])
    events, first = {}, {}
    for d in docs or []:
        sig, day = d.get("signatur_ges"), iso(d.get("dokudatum") or "")
        if not sig or not day or day > today:
            continue
        events.setdefault(sig, []).append((day, "Dokument: " + (text(d.get("titel_dok")) or "?")))
        if (d.get("signatur_dok") or "").endswith(".01"):
            first[sig] = min(first.get(sig, day), day)
    for v in steps or []:
        sig, day = v.get("signatur_ges"), iso(v.get("siz_datum") or "")
        if not sig or not day or day > today:
            continue
        events.setdefault(sig, []).append(
            (day, "Grosser Rat, Sitzung vom {0}: {1}".format(_dmy(day),
                                                           text(v.get("vermerk")) or "traktandiert")))
    for z in assignments or []:
        sig, day = z.get("signatur_ges"), z.get("datum")
        if sig and day and day <= today:
            events.setdefault(sig, []).append((day, z["text"]))
    out = []
    for sig, b in biz.items():
        r = b["row"]
        kind = (r.get("ga_rr_gr") or "").strip() or "Geschäft"
        if kind in BS_SKIP:
            continue
        begun, ended = iso(r.get("beginn_ges") or ""), iso(r.get("ende_ges") or "")
        if ended and ended > today:
            ended = None
        ev = sorted(events.get(sig, []))
        if since and not ev and sig not in keep and not any(
                x and since <= x <= today for x in (begun, ended)):
            continue          # pending, but nothing happened to it in the window
        presented = first.get(sig) or (begun if begun and begun <= today else None)
        state = (r.get("status_ges") or "").strip()
        if ev:
            status, status_date = "{0} ({1})".format(ev[-1][1], state) if state else ev[-1][1], ev[-1][0]
            if ended and ended > status_date:
                status, status_date = state or "Abgeschlossen", ended
        else:
            status, status_date = state or None, ended or presented
        _k, author, words = bs_split(r.get("titel_ges"))
        who = r.get("name_vorname_urheber") or author or ""
        if r.get("vorname_urheber") and r.get("name_urheber"):
            who = "{0} {1}".format(r["vorname_urheber"], r["name_urheber"])
        if who and r.get("partei_kname_urheber"):
            who += " ({0})".format(r["partei_kname_urheber"])
        if who and b["co"]:
            who += " and {0} other(s)".format(len(b["co"]))
        out.append({
            "key": "bs/" + sig, "canton": "bs", "kind": kind, "number": sig,
            "label": "{0} {1}".format(kind, sig), "title": words or text(r.get("titel_ges")),
            "title_fr": None, "presented": presented, "status": (status or "")[:300] or None,
            "status_date": status_date, "dated": True, "initiative": who or None,
            "committee": committees.get(sig), "url": r.get("url_ges") or BS_URL.format(sig),
            "source_url": source.format(sig), "seq": None,
            "question": kind in BS_API_QUESTIONS})
    return out


def parse_bs_api_votes(rows):
    """Divisions from data.bs.ch 100186 (one row per member and vote): the
    published counts and every member's vote."""
    votes = {}
    for r in rows or []:
        anr = (r.get("anr") or "").strip()
        if not anr or r.get("typ") in BS_VOTE_SKIP:
            continue
        v = votes.get(anr)
        if v is None:
            sig = (r.get("signatur_ges") or "").strip()
            subject = r.get("typ") or "Abstimmung"
            if r.get("abst_nr"):
                subject += ", Abstimmung Nr. {0}".format(r["abst_nr"])
            v = votes[anr] = {
                "key": "bs/v/" + anr, "canton": "bs", "act_key": "bs/" + sig if sig else None,
                "date": iso(r.get("datum") or ""), "subject": subject, "result": None,
                "yes": _num(r.get("anz_j")), "no": _num(r.get("anz_n")),
                "abstain": _num(r.get("anz_e")), "url": r.get("url_abstimmung_dok"),
                "source_url": BS_DATASET.format(BS_SETS["abstimmungen"]),
                "counts_from": "published", "positions": [], "act_title": r.get("geschaeft")}
        name = " ".join(x for x in (r.get("mitglied_vorname"), r.get("mitglied_nachname")) if x)
        name = name or r.get("mitglied_name")
        if not name:
            continue
        pos = r.get("entscheid_mitglied")
        v["positions"].append({"member": name, "member_id": r.get("gr_uni_nr"),
                               "parl_group": r.get("fraktion"),
                               "position": BS_POSITIONS.get(pos, pos)})
    return list(votes.values())


def gribs_rows(body):
    """The rows of one Grand Council export: its JSON (a list of objects), or
    its CSV (a header line, then one line per row) if `body` is not JSON."""
    if isinstance(body, bytes):
        body = body.decode("utf-8-sig", "replace")
    if isinstance(body, list):
        return body
    body = (body or "").lstrip("\ufeff")
    try:
        got = json.loads(body)
    except ValueError:
        got = None
    if isinstance(got, list):
        return got
    if got is not None or not body.strip():
        raise ValueError("the Grand Council export is neither a JSON list nor a CSV table")
    rows = list(csv.DictReader(io.StringIO(body)))
    if not rows or "idnr" not in rows[0]:
        raise ValueError("the Grand Council export is neither a JSON list nor a CSV table")
    return rows


def gribs_day(v):
    """An export date: epoch seconds at midnight UTC ('1791936000', or an int;
    0 or '' is none), or '12.10.2026' -> ISO date."""
    if v in (None, "", 0, "0"):
        return None
    s = str(v).strip()
    if re.fullmatch(r"-?\d+", s):
        return datetime.datetime.utcfromtimestamp(int(s)).date().isoformat()
    return iso(s)


def gribs_roster(rows):
    """The adr export -> {member number: (first name, name, party)}. Only
    those three fields are read: adr also prints addresses, phone numbers
    and e-mail addresses, which are never kept."""
    out = {}
    for r in rows or []:
        nr = str(r.get("uni_nr") or "").strip()
        first, name = (r.get("vorname") or "").strip(), (r.get("name") or "").strip()
        if nr and name:
            party = (r.get("partei_kname") or "").strip()
            out[nr] = (first, name, party if party and party.lower() != "keine" else None)
    return out


def gribs_committees(rows):
    """The gre export -> {body number: name} ('Gesundheits- und Sozialkommission')."""
    return {str(r.get("uni_nr")): re.sub(r"\s+", " ", r.get("name") or "").strip()
            for r in rows or [] if r.get("uni_nr") and (r.get("name") or "").strip()}


def gribs_zuweisungen(rows, sigs, committees, since=None, today=None):
    """The zuw export -> ({signatur: committee}, [assignment events]).

    A business's committee is the one its open assignment (status B) names,
    else the last committee it was assigned to; only assignments to a body
    the gre export names as a Gremium count (the Regierungsrat and the
    plenary are not committees). An assignment completed (erledigt) since..
    today is an event, in parse_bs_api's step rows: the committee's name and
    the assignment's own words. zuw carries no date of assignment."""
    today = today or datetime.date.today().isoformat()
    by_sig, events = {}, []
    for r in rows or []:
        sig = sigs.get(str(r.get("ges_laufnr") or ""))
        body = committees.get(str(r.get("uni_nr_an") or ""))
        if not sig or not body:
            continue
        try:
            order = int(r.get("idnr") or 0)
        except ValueError:
            order = 0
        by_sig.setdefault(sig, []).append((order, (r.get("status") or "").strip(), body))
        done = gribs_day(r.get("erledigt"))
        if _in(done, since, today):
            words = re.sub(r"\s+", " ", r.get("titel") or "").strip()
            events.append({"signatur_ges": sig, "datum": done,
                           "text": "Zuweisung an {0}{1}: erledigt".format(
                               body, " ({0})".format(words) if words else "")})
    committee = {}
    for sig, got in by_sig.items():
        got.sort()
        open_ = [b for _o, st, b in got if st == "B"]
        committee[sig] = open_[-1] if open_ else got[-1][2]
    return committee, events


def gribs_geschaefte(rows, roster=None):
    """The ges export as rows of data.bs.ch 100311 (for parse_bs_api). With
    the adr roster, the first author's name and party (gr_urheber)."""
    roster = roster or {}
    out = []
    for r in rows or []:
        sig = (r.get("signatur") or "").strip()
        if not sig:
            continue
        title = re.sub(r"\s+", " ", r.get("titel") or "").strip()
        kind = (r.get("ga_rr_gr") or "").strip() or bs_split(title)[0] or ""
        out.append({"signatur_ges": sig, "laufnr": str(r.get("laufnr") or ""),
                    "beginn_ges": gribs_day(r.get("beginn")), "ende_ges": gribs_day(r.get("ende")),
                    "status_ges": BS_GRIBS_STATUS.get((r.get("status") or "").strip(),
                                                      (r.get("status") or "").strip() or None),
                    "titel_ges": title, "ga_rr_gr": kind, "url_ges": BS_GES_URL.format(sig)})
        who = roster.get(str(r.get("gr_urheber") or "").strip())
        if who:
            out[-1].update({"vorname_urheber": who[0], "name_urheber": who[1],
                            "partei_kname_urheber": who[2]})
    return out


def _in(day, since, today):
    return bool(day) and (since is None or since <= day) and day <= today


def gribs_dokumente(rows, sigs, since=None, today=None):
    """The dok export as rows of 100313, those dated since..today."""
    today = today or datetime.date.today().isoformat()
    out = []
    for r in rows or []:
        sig, day = sigs.get(str(r.get("ges_laufnr") or "")), gribs_day(r.get("datum"))
        if sig and _in(day, since, today):
            out.append({"signatur_ges": sig, "dokudatum": day, "titel_dok": r.get("titel"),
                        "signatur_dok": r.get("signatur")})
    return out


def gribs_vorgaenge(rows, sittings, sigs, since=None, today=None):
    """The vor export as rows of 100314, dated by the siz export (sitting
    number -> date), those since..today."""
    today = today or datetime.date.today().isoformat()
    days = {str(s.get("siz_nr") or s.get("idnr")): gribs_day(s.get("datum")) for s in sittings or []}
    out = []
    for r in rows or []:
        sig, day = sigs.get(str(r.get("ges_laufnr") or "")), days.get(str(r.get("siz_nr") or ""))
        if sig and _in(day, since, today):
            out.append({"signatur_ges": sig, "siz_datum": day, "vermerk": r.get("vermerk"),
                        "beschlnr": r.get("beschlnr")})
    return out


def gribs_closed_since_stored(ges, stored):
    """Business numbers the export shows closed whose stored row was not:
    the diff against the store a whole-table export allows."""
    return {r["signatur_ges"] for r in ges
            if r.get("status_ges") == "Abgeschlossen" and "bs/" + r["signatur_ges"] in stored
            and "Abgeschlossen" not in (stored["bs/" + r["signatur_ges"]] or "")}


_TG_NR = re.compile(r"^(\d\d)/.*?/\s*(\d+)\s*$")


def tg_key(number):
    """'24/MO 14/115' -> 'tg/2024/115' (the key the pending list gives it too)."""
    m = _TG_NR.match((number or "").strip())
    if not m:
        return None
    yy = int(m.group(1))
    return "tg/{0}/{1}".format(1900 + yy if yy > 50 else 2000 + yy, int(m.group(2)))


def tg_authors(rows):
    """{Geschaeftsnummer: [(name (party), first signatory?)]} from sk-stat-141."""
    out = {}
    for r in rows or []:
        nr = r.get("geschaeftsnummer")
        name = " ".join(x for x in (r.get("vorname"), r.get("nachname")) if x)
        if not nr or not name:
            continue
        if r.get("partei"):
            name += " ({0})".format(r["partei"])
        out.setdefault(nr, []).append((name, (r.get("erstunterzeichner") or "").lower() == "ja"))
    return out


def parse_tg_api(rows, authors=None, today=None):
    """Acts from data.tg.ch sk-stat-140, with the signatories of sk-stat-141.
    Status: the dataset's own state, where it is pending, and its newest
    dated step; flags (Erheblicherklaerung ...) printed as the dataset has them."""
    today = today or datetime.date.today().isoformat()
    authors = authors or {}
    out = []
    for r in rows or []:
        kind = (r.get("geschaftsart") or "").strip() or "Geschäft"
        nr = (r.get("geschaeftsnummer") or "").strip()
        key = tg_key(nr)
        if kind in TG_SKIP or not key:
            continue
        title = text(r.get("geschaftstitel"))
        m = _TG_KIND.match(title)
        words = m.group(3).strip() if m else title
        firsts = [n for n, f in authors.get(nr, []) if f]
        others = len(authors.get(nr, [])) - len(firsts)
        initiative = ", ".join(firsts) or (m.group(2).strip() if m else None)
        if initiative and others > 0:
            initiative += " and {0} other(s)".format(others)
        steps = sorted((iso(r.get(f) or ""), what) for f, what in TG_STEPS
                       if iso(r.get(f) or "") and iso(r.get(f) or "") <= today)
        state = {"inbearbeitung": "In Bearbeitung", "abgeschlossen": "Abgeschlossen"}.get(
            (r.get("status") or "").lower(), r.get("status") or "")
        bits = [state] if state else []
        if r.get("pendent_bei"):
            bits.append("pendent bei: {0}".format(r["pendent_bei"]))
        if steps:
            bits.append("{0} am {1}".format(steps[-1][1], _dmy(steps[-1][0])))
        bits += ["{0}: {1}".format(label, {"true": "ja", "false": "nein"}.get(
                     str(r.get(f)).lower(), r.get(f)))
                 for f, label in TG_FLAGS if r.get(f) not in (None, "")]
        presented = iso(r.get("datum_geschaeft_eingang") or "")
        out.append({
            "key": key, "canton": "tg", "kind": kind, "number": nr,
            "label": "{0} {1}".format(kind, nr), "title": words, "title_fr": None,
            "presented": presented, "status": "; ".join(bits) or None,
            "status_date": steps[-1][0] if steps else presented, "dated": True,
            "initiative": initiative or None, "committee": r.get("kommission") or None,
            "url": TG_ITEM.format(urllib.parse.quote('"{0}"'.format(nr))),
            "source_url": TG_DATASET.format(TG_SETS["geschaefte"]), "seq": None,
            "question": kind in TG_API_QUESTIONS})
    return out


def parse_tg_api_votes(rows):
    """Divisions from data.tg.ch sk-stat-136 (one row per member and vote; a
    vote is its day and agenda item). The dataset prints no totals: they are
    tallied from the members' votes. A vote between options names them."""
    import hashlib
    votes = {}
    for r in rows or []:
        day, item = iso(r.get("datum") or ""), re.sub(r"\s+", " ", r.get("traktandum") or "").strip()
        if not day or not item:
            continue
        key = "tg/v/{0}/{1}".format(day, hashlib.sha1(item.encode("utf-8")).hexdigest()[:12])
        v = votes.get(key)
        if v is None:
            cut = re.search(r"\)\s*:\s*", item)
            subject = item[cut.end():] if cut else re.sub(r"^\d+\.\s*", "", item)
            head = re.sub(r"\s*\(\d\d/[^)]*\)\s*:.*$", "", item)
            head = re.sub(r"^\d+\.\s*", "", head).strip(" \"„“”«»")
            v = votes[key] = {"key": key, "canton": "tg", "act_key": tg_key(r.get("geschaeftsnummer")),
                              "date": day, "subject": subject, "act_title": head, "result": None,
                              "url": TG_DATASET.format(TG_SETS["abstimmungen"]),
                              "source_url": TG_DATASET.format(TG_SETS["abstimmungen"]),
                              "counts_from": "tallied", "positions": []}
        name = (r.get("name_vorname") or "").strip()
        if name:
            v["positions"].append({"member": name, "member_id": str(r["nr"]) if r.get("nr") else None,
                                   "parl_group": r.get("fraktion"),
                                   "position": (r.get("stimme") or "").strip() or None})
    for v in votes.values():
        got = [p["position"] for p in v["positions"]]
        options = sorted({p for p in got if p and p not in TG_PLAIN})
        if options:
            counts = sorted(((got.count(o), o) for o in options), reverse=True)
            v["yes"] = v["no"] = None
            v["abstain"] = got.count("Enthaltung") or None
            v["result"] = "Stimmen je Antrag (gezählt): " + ", ".join(
                "{0} {1}".format(o, n) for n, o in counts)
        else:
            v["yes"], v["no"], v["abstain"] = got.count("Ja"), got.count("Nein"), got.count("Enthaltung")
    return list(votes.values())



# --- Basel-Landschaft, data.bl.ch (written permission) ---------------------------

def bl_authors(rows):
    """{Laufnummer: ([author, ...], co-signatories)} from data.bl.ch 13140.
    The 'Zustaendig' rows (the member of government in charge) are not authors."""
    out = {}
    for r in rows or []:
        nr = (r.get("geschaeft_laufnummer") or "").strip()
        name = " ".join(x for x in (r.get("person_vorname"), r.get("person_name")) if x)
        role = (r.get("person_rolle") or "").strip()
        if not nr or not name or role not in BL_AUTHORS + BL_COSIGNERS:
            continue
        got = out.setdefault(nr, ([], [0]))
        if role in BL_AUTHORS:
            if name not in got[0]:
                got[0].append(name)
        else:
            got[1][0] += 1
    return {nr: (names, n[0]) for nr, (names, n) in out.items()}


def bl_newest_docs(rows, today=None):
    """{Laufnummer: (day, title)}: each business's newest document from
    data.bl.ch 13130 (on one day, a decision before the text it decides)."""
    today = today or datetime.date.today().isoformat()
    out = {}
    for r in rows or []:
        nr, day = (r.get("geschaeft_laufnummer") or "").strip(), iso(r.get("dokument_datum") or "")
        title = text(r.get("dokument_titel")) or "Dokument"
        if not nr or not day or day > today:
            continue
        rank = (day, not title.startswith("Text "), title)
        if nr not in out or rank > out[nr][0]:
            out[nr] = (rank, (day, title))
    return {nr: v[1] for nr, v in out.items()}


def parse_bl_api(rows, authors=None, docs=None, today=None):
    """Acts from data.bl.ch 13090 (the Landeskanzlei's business database),
    with the authors of 13140 and the newest document of 13130. Status: the
    dataset's own state and Landrat standing, the newest document; dated by
    the newest of that document, the referral (Ueberweisung) and the close."""
    today = today or datetime.date.today().isoformat()
    authors, docs = authors or {}, docs or {}
    out = []
    for r in rows or []:
        nr = (r.get("laufnummer") or "").strip()
        kind = (r.get("vorstossart") or r.get("geschaeftstyp") or "").strip() or "Geschäft"
        if not re.match(r"^\d{4}/\d+$", nr) or kind in BL_SKIP \
                or (r.get("geschaeftstyp") or "") in BL_SKIP:
            continue
        presented = iso(r.get("beginn") or "")
        state = (r.get("status") or "").strip()
        closed = iso(r.get("ende") or "") if state == "Abgeschlossen" else ""
        bits = ["{0} am {1}".format(state, _dmy(closed)) if closed and closed <= today else state]
        if r.get("stand_lr"):
            bits.append(text(r["stand_lr"]))
        doc = docs.get(nr)
        if doc:
            bits.append("neuestes Dokument: {0} ({1})".format(doc[1], _dmy(doc[0])))
        dates = [d for d in (doc[0] if doc else "", iso(r.get("ueberweisungsdatum") or ""), closed)
                 if d and d <= today]
        names, others = authors.get(nr, ([], 0))
        initiative = ", ".join(names) or None
        if initiative and others:
            initiative += " and {0} other(s)".format(others)
        gid = (r.get("geschaeft_id") or "").strip()
        out.append({
            "key": "bl/" + nr, "canton": "bl", "kind": kind, "number": nr,
            "label": "{0} {1}".format(kind, nr), "title": text(r.get("titel")), "title_fr": None,
            "presented": presented or None, "status": "; ".join(b for b in bits if b) or None,
            "status_date": max(dates) if dates else (presented or None), "dated": True,
            "initiative": initiative, "committee": r.get("komission") or None,
            "url": BL_URL.format(gid) if gid else BL_DATASET.format(BL_SETS["geschaefte"]),
            "source_url": BL_DATASET.format(BL_SETS["geschaefte"]), "seq": None,
            "question": kind in BL_API_QUESTIONS})
    return out


def parse_bl_api_votes(rows, numbers=None):
    """Divisions from data.bl.ch 13080 (one row per member and vote; the
    row's abstimmung_id is the member's, so a vote is its agenda item, time
    and subject). No totals are printed: they are tallied from the members'
    votes. `numbers`: {geschaeft_id: Laufnummer}, for the act a vote is on."""
    import hashlib
    numbers = numbers or {}
    votes = {}
    for r in rows or []:
        when = (r.get("abstimmung_datum") or "").strip()
        subject = text(r.get("abstimmung_gegenstand"))
        day = iso(when[:10])
        if not day or not subject:
            continue
        ident = "|".join((r.get("traktandum_id") or r.get("geschaeft_id") or "", when, subject))
        key = "bl/v/{0}/{1}".format(day, hashlib.sha1(ident.encode("utf-8")).hexdigest()[:12])
        v = votes.get(key)
        if v is None:
            nr = numbers.get(r.get("geschaeft_id") or "")
            v = votes[key] = {"key": key, "canton": "bl", "act_key": "bl/" + nr if nr else None,
                              "date": day, "subject": subject,
                              "act_title": text(r.get("geschaeft_titel")) or None, "result": None,
                              "url": BL_DATASET.format(BL_SETS["abstimmungen"]),
                              "source_url": BL_DATASET.format(BL_SETS["abstimmungen"]),
                              "counts_from": "tallied", "positions": []}
        name = " ".join(x for x in (r.get("person_vorname"), r.get("person_name")) if x)
        if name and (r.get("abstimmung_id") or (name, r.get("person_id"))) not in v.setdefault(
                "_seen", set()):
            # a member's row read twice (overlapping exports) counts once
            v["_seen"].add(r.get("abstimmung_id") or (name, r.get("person_id")))
            pos = (r.get("abstimmung_art") or "").strip()
            v["positions"].append({"member": name, "member_id": r.get("person_id") or None,
                                   "parl_group": r.get("person_fraktion") or r.get("person_partei")
                                   or None,
                                   "position": BL_POSITIONS.get(pos, pos) or None})
    for v in votes.values():
        v.pop("_seen", None)
        got = [p["position"] for p in v["positions"]]
        v["yes"], v["no"], v["abstain"] = got.count("Ja"), got.count("Nein"), got.count("Enthaltung")
    return list(votes.values())

# --- classification and storing --------------------------------------------------

class Taxonomies:
    def __init__(self, de=None, fr=None, it=None):
        self.de = de if de is not None else filt.load_taxonomy(TAXONOMY_DE, country=TAXONOMY_COUNTRY)
        self.fr = fr if fr is not None else filt.load_taxonomy(TAXONOMY_FR, country=TAXONOMY_COUNTRY)
        if it is None and os.path.exists(TAXONOMY_IT):
            it = filt.load_taxonomy(TAXONOMY_IT, country=TAXONOMY_COUNTRY)
        self.it = it
        self.wl = filt.Watchlist(entities=[], bill_titles=[], act_shorts=[])


def classify(tax, a, watch_path=None):
    """(areas, matched terms, tier): the canton's language list on the title
    (Bern: German and French titles, unioned), plus watchlist-ch `cantons`."""
    passes = []
    lang = LANGUAGE.get(a["canton"], "de")
    body = a.get("body") or ""
    if lang == "de":
        passes.append((tax.de, a.get("title")))
        if a.get("title_fr"):
            passes.append((tax.fr, a["title_fr"]))
    elif lang == "fr":
        passes.append((tax.fr, a.get("title")))
    elif tax.it is not None:
        passes.append((tax.it, a.get("title")))
    areas, terms, tiers = set(), [], []
    for t, title in passes:
        if t is None or not title:
            continue
        res = filt.filter_item(t, tax.wl, title, body, title=title)
        areas |= set(res.issue_areas or [])
        terms += [x for x in res.matched_terms or [] if x not in terms]
        if res.tier:
            tiers.append(res.tier)
    w_areas, w_hit = ch_store.canton_watch_areas(a["key"], watch_path)
    if w_hit:
        areas |= set(w_areas)
        terms.append(w_hit)
    tier = min(tiers) if tiers else (2 if w_hit else None)
    return sorted(areas), terms, tier


def store_act(conn, a, cls, today, baseline=False):
    """Insert or update one act. Returns 'new', 'moved' or 'same'."""
    old = conn.execute("SELECT status, status_date, status_seen, baseline, seq FROM "
                       "ch_canton_acts WHERE act_key=?", (a["key"],)).fetchone()
    status_date, seen = a.get("status_date"), 0
    state = "new" if old is None else "same"
    base = 1 if (old is None and baseline) else (old[3] if old is not None else 0)
    if old is not None:
        if a.get("dated"):
            if (a.get("status_date") or None) != (old[1] or None):
                state = "moved"
        elif (a.get("status") or None) != (old[0] or None):
            status_date, seen, state = today, 1, "moved"
        else:
            status_date, seen = old[1], old[2] or 0
    areas, terms, tier = cls
    conn.execute(
        "INSERT INTO ch_canton_acts (act_key, canton, kind, number, label, title, title_fr, "
        "presented, status, status_date, status_seen, initiative, committee, url, seq, "
        "question, baseline, areas, matched_terms, tier, first_seen, last_seen, source_url) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(act_key) DO UPDATE SET kind=excluded.kind, number=excluded.number, "
        "label=excluded.label, title=excluded.title, title_fr=excluded.title_fr, "
        "presented=COALESCE(excluded.presented, ch_canton_acts.presented), "
        "status=excluded.status, status_date=excluded.status_date, "
        "status_seen=excluded.status_seen, initiative=COALESCE(excluded.initiative, "
        "ch_canton_acts.initiative), committee=COALESCE(excluded.committee, "
        "ch_canton_acts.committee), url=excluded.url, "
        "seq=COALESCE(excluded.seq, ch_canton_acts.seq), question=excluded.question, "
        "areas=excluded.areas, matched_terms=excluded.matched_terms, tier=excluded.tier, "
        "last_seen=excluded.last_seen, source_url=excluded.source_url",
        (a["key"], a["canton"], a["kind"], a.get("number"), a.get("label"), a.get("title"),
         a.get("title_fr"), a.get("presented"), a.get("status"), status_date, seen,
         a.get("initiative"), a.get("committee"), a.get("url"), a.get("seq"),
         1 if a.get("question") else 0, base, ch_store.dumps(areas), ch_store.dumps(terms),
         tier, today, today, a.get("source_url")))
    return state


def store_vote(conn, v, today, tax=None):
    row = conn.execute("SELECT areas, matched_terms, tier FROM ch_canton_acts WHERE act_key=?",
                       (v.get("act_key"),)).fetchone() if v.get("act_key") else None
    if row is None and tax is not None and v.get("act_title"):
        # A vote on business this run did not read: its areas from the title
        # the vote dataset prints for it.
        areas, terms, tier = classify(tax, {"key": v.get("act_key") or "", "canton": v["canton"],
                                            "title": v["act_title"]})
        row = (ch_store.dumps(areas), ch_store.dumps(terms), tier)
    conn.execute(
        "INSERT INTO ch_canton_divisions (vote_key, canton, act_key, date, subject, result, yes, "
        "no, abstain, url, areas, matched_terms, tier, first_seen, last_seen, source_url, "
        "counts_from) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(vote_key) DO UPDATE SET "
        "act_key=excluded.act_key, date=excluded.date, subject=excluded.subject, "
        "result=excluded.result, yes=excluded.yes, no=excluded.no, abstain=excluded.abstain, "
        "url=excluded.url, areas=excluded.areas, matched_terms=excluded.matched_terms, "
        "tier=excluded.tier, last_seen=excluded.last_seen, source_url=excluded.source_url, "
        "counts_from=excluded.counts_from",
        (v["key"], v["canton"], v.get("act_key"), v.get("date"), v.get("subject"),
         v.get("result"), v.get("yes"), v.get("no"), v.get("abstain"), v.get("url"),
         row[0] if row else "[]", row[1] if row else "[]", row[2] if row else None,
         today, today, v.get("source_url"), v.get("counts_from")))
    if v.get("positions"):
        # The members' votes: replaced whole, so a corrected export leaves no stale row.
        conn.execute("DELETE FROM ch_canton_votes WHERE vote_key=?", (v["key"],))
        conn.executemany(
            "INSERT OR REPLACE INTO ch_canton_votes (vote_key, member, member_id, parl_group, "
            "position, party) VALUES (?,?,?,?,?,?)",
            [(v["key"], p["member"], p.get("member_id"), p.get("parl_group"), p.get("position"),
              p.get("party")) for p in v["positions"] if p.get("member")])


def store_all(conn, acts, tax, today, baseline=False):
    """(read, on our ground, new, moved)."""
    n = ours = new = moved = 0
    for a in acts:
        cls = classify(tax, a)
        state = store_act(conn, a, cls, today, baseline=baseline)
        n += 1
        if [x for x in cls[0] if x != 11]:
            ours += 1
        new += state == "new"
        moved += state == "moved"
    conn.commit()
    return n, ours, new, moved


def _gap(conn, today, detail, log=print):
    log("  [gap] " + detail)
    conn.execute("INSERT OR IGNORE INTO gaps (edition, feed, detail) VALUES (?,?,?)",
                 (today, FEED, detail))
    conn.commit()


# --- fetching --------------------------------------------------------------------

def fetch_zuerich(client, conn=None, today=None, log=print, budget=None):
    today = today or datetime.date.today().isoformat()
    queries = [("new", zh_query_new(today))]
    top = None
    if conn is not None:
        got = conn.execute("SELECT MAX(seq) FROM ch_canton_acts WHERE canton='zh'").fetchone()
        top = got[0] if got else None
    if top:
        queries.append(("changed", zh_query_changed(top)))
    acts, gaps = {}, 0
    for name, q in queries:
        for page in range(ZH_MAX_PAGES):
            if budget is not None and budget.exhausted():
                log(budget.disclose("Zürich pages", page))
                return list(acts.values()), gaps + 1
            raw = client.get_bytes(zh_url(q, 1 + page * ZH_PAGE), FEED,
                                   "zh-{0}-p{1}".format(name, page))
            got, hits = parse_zuerich(raw)
            for a in got:
                acts[a["key"]] = a
            if len(got) < ZH_PAGE or (page + 1) * ZH_PAGE >= hits:
                break
        else:
            log("  ch-cantons: Zürich '{0}' query capped at {1} pages".format(name, ZH_MAX_PAGES))
    return list(acts.values()), gaps


def fetch_bern(client, conn=None, today=None, log=print, budget=None):
    data = client.get_json(BE_GESCHAEFT, FEED, "be-geschaeft", timeout=180)
    acts = parse_bern(data or {})
    votes = []
    if budget is None or not budget.exhausted():
        votes = parse_bern_votes(client.get_json(BE_VOTES, FEED, "be-abstimmung", timeout=180)
                                 or {})
    return acts, 0, votes


def fetch_geneva(client, conn=None, today=None, log=print, budget=None):
    docs, gaps = [], 0
    for i, term in enumerate(GE_TERMS):
        for page in range(1, GE_PAGES + 1):
            if budget is not None and budget.exhausted():
                log(budget.disclose("Geneva searches", i))
                return merge_geneva(docs), gaps + 1
            params = {"q": term, "m": 0, "date": "y1"}
            if page > 1:
                params["pdfPage"] = page
            url = GE_SEARCH + "?" + urllib.parse.urlencode(params)
            body = client.get_text(url, FEED, "ge-{0}-p{1}".format(i, page))
            got = parse_geneva(body)
            docs += got
            if "pdfPage={0}".format(page + 1) not in body.replace("&amp;", "&"):
                break
    return merge_geneva(docs), gaps


def fetch_vaud(client, conn=None, today=None, log=print, budget=None):
    acts, gaps = {}, 0
    for i, slug in enumerate(VD_PAGES):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Vaud lists", i))
            return list(acts.values()), gaps + 1
        for a in parse_vaud(client.get_text(VD_BASE + slug, FEED, "vd-" + slug[:40])):
            acts.setdefault(a["key"], a)
    return list(acts.values()), gaps


def fetch_ticino(client, conn=None, today=None, log=print, budget=None):
    return parse_ticino(client.get_text(TI_ODG, FEED, "ti-odg")), 0


def fetch_stgallen(client, conn=None, today=None, log=print, budget=None):
    """Business changed in the last SG_DAYS days, then the tallies of recent
    votes on business on our ground (via www.ratsinfo.sg.ch)."""
    today = today or datetime.date.today().isoformat()
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=SG_DAYS)).isoformat()
    types = sg_names(client.get_json(SG_API + "business_types", FEED, "sg-types"))
    states = sg_names(client.get_json(SG_API + "process_states", FEED, "sg-states"))
    acts, gaps = {}, 0
    for page in range(1, SG_MAX_PAGES + 1):
        if budget is not None and budget.exhausted():
            log(budget.disclose("St. Gallen pages", page - 1))
            return list(acts.values()), gaps + 1, []
        url = SG_API + "businesses?" + urllib.parse.urlencode(
            {"committee": SG_COMMITTEE, "ordering": "-touched", "page": page, "page_size": SG_PAGE})
        data = client.get_json(url, FEED, "sg-businesses-p{0}".format(page))
        got, oldest = parse_sg_businesses(data, types, states)
        for a in got:
            acts.setdefault(a["key"], a)
        if not (data or {}).get("next") or (oldest and oldest < since):
            break
    votes = []
    if conn is None:
        return list(acts.values()), gaps, votes
    vsince = (datetime.date.fromisoformat(today) - datetime.timedelta(days=SG_VOTE_DAYS)).isoformat()
    summaries = []
    for page in range(1, SG_VOTE_PAGES + 1):
        if budget is not None and budget.exhausted():
            break
        url = SG_API + "votings?" + urllib.parse.urlencode({"page": page, "page_size": 50})
        data = client.get_json(url, FEED, "sg-votings-p{0}".format(page))
        got = parse_sg_votings(data)
        summaries += [v for v in got if v["date"] >= vsince]
        if not got or got[-1]["date"] < vsince or not (data or {}).get("next"):
            break
    tax = getattr(client, "_ch_tax", None)
    details = 0
    for v in summaries:
        if details >= SG_VOTE_DETAILS or (budget is not None and budget.exhausted()):
            break
        if conn.execute("SELECT 1 FROM ch_canton_divisions WHERE vote_key=?",
                        ("sg/v/{0}".format(v["id"]),)).fetchone():
            continue
        ours = None
        if v["act_key"] in acts and tax is not None:
            ours = classify(tax, acts[v["act_key"]])[0]
        elif v["act_key"]:
            row = conn.execute("SELECT areas FROM ch_canton_acts WHERE act_key=?",
                               (v["act_key"],)).fetchone()
            ours = json.loads(row[0]) if row and row[0] else None
        if ours is None and tax is not None and v.get("act_title"):
            ours = classify(tax, {"key": v["act_key"] or "", "canton": "sg",
                                  "title": v["act_title"]})[0]
        if not [x for x in (ours or []) if x != 11]:
            continue
        detail = client.get_json(SG_API + "votings/{0}".format(v["id"]), FEED,
                                 "sg-voting-{0}".format(v["id"]))
        votes.append(parse_sg_voting(detail or {}, v))
        details += 1
    return list(acts.values()), gaps, votes


def fetch_baselland_pages(client, conn=None, today=None, log=print, budget=None):
    """The fallback: the Landrat's newest documents (baselland.talus.ch)."""
    return parse_bl(client.get_text(BL_NEW, FEED, "bl-neuste")), 0


def _bl_in(field, values):
    q = '"{0}"'.format
    return "{0} in ({1})".format(field, ", ".join(q(v.replace('"', "")) for v in values))


def _stored_bl(conn):
    """{act_key: (initiative, geschaeft_id)} of the stored Basel-Landschaft acts."""
    if conn is None:
        return {}
    out = {}
    for k, ini, url in conn.execute("SELECT act_key, initiative, url FROM ch_canton_acts "
                                    "WHERE canton='bl'").fetchall():
        m = re.search(r"gid=(\w+)", url or "")
        out[k] = (ini, m.group(1) if m else None)
    return out


def fetch_baselland_api(client, conn=None, today=None, log=print, budget=None):
    """data.bl.ch (written permission, 13 October 2026): business begun or
    ended in the last BL_API_DAYS days and everything in progress, the
    authors of the motions and questions not stored with them yet, the
    documents of the window, and every vote since the newest stored one,
    quarter by quarter, with each member's vote."""
    today = today or datetime.date.today().isoformat()
    since = _since(today, BL_API_DAYS)
    q = '"{0}"'.format
    rows = client.get_json(ods_export(
        BL_ODS, BL_SETS["geschaefte"],
        "beginn >= {0} or ende >= {0} or status = \"In Bearbeitung\"".format(q(since)),
        select=BL_GES_FIELDS), FEED, "bl-ods-geschaefte", timeout=180)
    if not isinstance(rows, list):
        raise ValueError("data.bl.ch answered with no list of Geschaefte")
    docs = client.get_json(ods_export(
        BL_ODS, BL_SETS["dokumente"],
        "dokument_datum >= {0} and dokument_datum <= {1}".format(q(since), q(today)),
        select="dokument_titel,dokument_datum,geschaeft_laufnummer"),
        FEED, "bl-ods-dokumente", timeout=180) or []
    stored = _stored_bl(conn)
    numbers = sorted({r["laufnummer"] for r in rows if r.get("laufnummer") and r.get("vorstossart")
                      and not (stored.get("bl/" + r["laufnummer"]) or (None,))[0]})
    signers = []
    for i in range(0, len(numbers), BL_CHUNK):
        signers += client.get_json(ods_export(
            BL_ODS, BL_SETS["urheber"], _bl_in("geschaeft_laufnummer", numbers[i:i + BL_CHUNK]),
            select="person_name,person_vorname,person_rolle,geschaeft_laufnummer"),
            FEED, "bl-ods-urheber-{0}".format(i // BL_CHUNK), timeout=180) or []
    acts = parse_bl_api(rows, bl_authors(signers), bl_newest_docs(docs, today), today=today)
    # The act a vote is on: its geschaeft_id, from this run's rows, the store,
    # or (for older business) one look-up in 13090.
    ids = {r["geschaeft_id"]: r["laufnummer"] for r in rows
           if r.get("geschaeft_id") and r.get("laufnummer")}
    ids.update({gid: k[3:] for k, (_ini, gid) in stored.items() if gid and gid not in ids})
    votes, part, got = [], 0, []
    for k, (a, b) in enumerate(batches(_vote_start(conn, "bl", BL_VOTE_SINCE), today, BL_BATCH_DAYS)):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Basel-Landschaft vote batches", k))
            part = 1
            break
        got += client.get_json(ods_export(
            BL_ODS, BL_SETS["abstimmungen"],
            # a datetime field: ODSQL compares it with a day by the day
            "abstimmung_datum >= {0} and abstimmung_datum <= {1}".format(q(a), q(b)),
            select=BL_VOTE_FIELDS), FEED, "bl-ods-abstimmungen-" + a, timeout=300) or []
    missing = sorted({r["geschaeft_id"] for r in got if r.get("geschaeft_id")} - set(ids))
    for i in range(0, len(missing), BL_CHUNK):
        if budget is not None and budget.exhausted():
            break
        for r in client.get_json(ods_export(
                BL_ODS, BL_SETS["geschaefte"], _bl_in("geschaeft_id", missing[i:i + BL_CHUNK]),
                select="laufnummer,geschaeft_id"), FEED,
                "bl-ods-geschaefte-ids-{0}".format(i // BL_CHUNK), timeout=180) or []:
            if r.get("geschaeft_id") and r.get("laufnummer"):
                ids[r["geschaeft_id"]] = r["laufnummer"]
    votes = parse_bl_api_votes(got, ids)
    return acts, part, votes


def fetch_baselland(client, conn=None, today=None, log=print, budget=None):
    return _api_or_pages(fetch_baselland_api, fetch_baselland_pages, CANTONS["bl"], client,
                         conn, today, log, budget)


def fetch_baselstadt_pages(client, conn=None, today=None, log=print, budget=None):
    """The fallback: the Grand Council's own pages (grosserrat.bs.ch)."""
    new = parse_bs_new(client.get_text(BS_NEW, FEED, "bs-vorstoesse"))
    versand = []
    if budget is None or not budget.exhausted():
        versand = parse_bs_versand(client.get_text(BS_VERSAND, FEED, "bs-versand"))
    return merge_bs(new, versand), 0


def _since(today, days):
    return (datetime.date.fromisoformat(today) - datetime.timedelta(days=days)).isoformat()


def _vote_start(conn, canton, default):
    """The newest stored vote's day (re-read: an export may have grown), else `default`."""
    if conn is None:            # a dry run: the last month only
        return max(default, (datetime.date.today() - datetime.timedelta(days=30)).isoformat())
    got = conn.execute("SELECT MAX(date) FROM ch_canton_divisions WHERE canton=? AND "
                       "counts_from IS NOT NULL", (canton,)).fetchone()
    return max(default, got[0]) if got and got[0] else default


def fetch_baselstadt_api(client, conn=None, today=None, log=print, budget=None):
    """data.bs.ch (written permission, 13 October 2026): Geschaefte begun or
    ended in the last BS_API_DAYS days or touched by a document or a Grosser
    Rat step in them, and every vote since the newest stored one, fortnight by
    fortnight, with each member's vote."""
    today = today or datetime.date.today().isoformat()
    since = _since(today, BS_API_DAYS)
    q = '"{0}"'.format
    ges = client.get_json(ods_export(
        BS_ODS, BS_SETS["geschaefte"],
        "beginn_ges >= {0} or ende_ges >= {0} or status_ges = \"In Bearbeitung\"".format(q(since)),
        select=BS_GES_FIELDS), FEED, "bs-ods-geschaefte", timeout=180)
    docs, steps = bs_api_docs_steps(client, since, today)
    if not isinstance(ges, list):
        raise ValueError("data.bs.ch answered with no list of Geschaefte")
    acts = parse_bs_api(ges, docs, steps, today=today, since=since)
    votes, part = bs_api_votes(client, conn, today, log=log, budget=budget)
    return acts, part, votes


def bs_api_docs_steps(client, since, today):
    """Documents (100313) and Grosser Rat steps (100314) dated since..today, from data.bs.ch."""
    q = '"{0}"'.format
    docs = client.get_json(ods_export(
        BS_ODS, BS_SETS["dokumente"], "dokudatum >= {0} and dokudatum <= {1}".format(q(since), q(today)),
        select="dokudatum,signatur_dok,titel_dok,signatur_ges"), FEED, "bs-ods-dokumente", timeout=180)
    steps = client.get_json(ods_export(
        BS_ODS, BS_SETS["vorgaenge"], "siz_datum >= {0} and siz_datum <= {1}".format(q(since), q(today)),
        select="beschlnr,vermerk,siz_datum,signatur_ges"), FEED, "bs-ods-vorgaenge", timeout=180)
    return docs, steps


def bs_api_votes(client, conn, today, log=print, budget=None):
    """(votes, read in part): every vote since the newest stored one, from
    data.bs.ch 100186, fortnight by fortnight, with each member's vote. The
    Grand Council's exporter has no votes table (13 October 2026)."""
    q = '"{0}"'.format
    votes, part = [], 0
    for k, (a, b) in enumerate(batches(_vote_start(conn, "bs", _since(today, BS_VOTE_DAYS)), today,
                                       BS_BATCH_DAYS)):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Basel-Stadt vote batches", k))
            part = 1
            break
        rows = client.get_json(ods_export(
            BS_ODS, BS_SETS["abstimmungen"], "datum >= {0} and datum <= {1}".format(q(a), q(b)),
            select=BS_VOTE_FIELDS), FEED, "bs-ods-abstimmungen-" + a, timeout=180)
        votes += parse_bs_api_votes(rows)
    return votes, part


def gribs_get(client, table):
    """One Grand Council export table's rows: the JSON, or the CSV if the JSON fails."""
    # Not archived under data/raw: whole tables (8 to 12 MB each), read again every week.
    try:
        return gribs_rows(client.get_text(BS_GRIBS.format(table, "json"), FEED,
                                          "bs-gribs-" + table, timeout=300, archive=False))
    except RobotsRefused:
        raise                           # robots.txt refused it: the CSV would be refused too
    except (FetchError, ValueError):
        return gribs_rows(client.get_text(BS_GRIBS.format(table, "csv"), FEED,
                                          "bs-gribs-" + table + "-csv", timeout=300,
                                          archive=False))


def gribs_vote_parties(votes, roster):
    """Each member's party (adr) on their position, by member number; the
    Fraktion at the vote stays as data.bs.ch printed it, and stands in for
    nothing: a member the roster lacks keeps no party."""
    for v in votes:
        for p in v.get("positions") or []:
            who = roster.get(str(p.get("member_id") or ""))
            if who and who[2]:
                p["party"] = who[2]
    return votes


def _stored_bs(conn):
    if conn is None:
        return {}
    return {k: st for k, st in conn.execute(
        "SELECT act_key, status FROM ch_canton_acts WHERE canton='bs'").fetchall()}


def fetch_baselstadt_gribs(client, conn=None, today=None, log=print, budget=None):
    """The Grand Council's own exports (offered by its Parlamentsdienst, 13
    October 2026): the whole Geschaefte table, diffed against the store,
    with its documents and Grosser Rat steps (dok, vor + siz; data.bs.ch's
    if those fail), and the votes from data.bs.ch 100186."""
    today = today or datetime.date.today().isoformat()
    since = _since(today, BS_API_DAYS)
    gaps = 0

    def missed(what, e):
        nonlocal gaps
        detail = "{0}: the Grand Council's {1} not read ({2})".format(CANTONS["bs"], what, str(e)[:160])
        if conn is not None:
            _gap(conn, today, detail, log=log)
        else:
            log("  [gap] " + detail)
        gaps += 1

    ges_rows = gribs_get(client, BS_GRIBS_TABLES["geschaefte"])
    # The members (adr, 15 October 2026): authors' and voters' parties.
    roster = {}
    try:
        roster = gribs_roster(gribs_get(client, BS_GRIBS_TABLES["personen"]))
    except (FetchError, ValueError) as e:
        missed("members export (adr); authors' and voters' parties left out", e)
    ges = gribs_geschaefte(ges_rows, roster)
    if not ges:
        raise ValueError("the Grand Council's Geschaefte export has no rows")
    sigs = {r["laufnr"]: r["signatur_ges"] for r in ges if r.get("laufnr")}
    # Committee assignments (zuw, named by gre, 15 October 2026).
    committees, assignments = {}, []
    try:
        committees, assignments = gribs_zuweisungen(
            gribs_get(client, BS_GRIBS_TABLES["zuweisungen"]),
            sigs, gribs_committees(gribs_get(client, BS_GRIBS_TABLES["gremien"])), since, today)
    except (FetchError, ValueError) as e:
        missed("committee assignments (zuw, gre); committees left out", e)
    try:
        docs = gribs_dokumente(gribs_get(client, BS_GRIBS_TABLES["dokumente"]), sigs, since, today)
        steps = gribs_vorgaenge(gribs_get(client, BS_GRIBS_TABLES["vorgaenge"]),
                                gribs_get(client, BS_GRIBS_TABLES["sitzungen"]), sigs, since, today)
    except (FetchError, ValueError) as e:
        detail = ("{0}: the Grand Council's document/step exports not read ({1}); "
                  "read from data.bs.ch instead").format(CANTONS["bs"], str(e)[:160])
        if conn is not None:
            _gap(conn, today, detail, log=log)
        else:
            log("  [gap] " + detail)
        gaps = 1
        try:
            docs, steps = bs_api_docs_steps(client, since, today)
        except (FetchError, ValueError) as e2:
            log("  ch-cantons: Basel-Stadt documents and steps not read ({0})".format(str(e2)[:160]))
            docs, steps = [], []
    keep = gribs_closed_since_stored(ges, _stored_bs(conn))
    acts = parse_bs_api(ges, docs, steps, today=today, since=since, source=BS_GES_URL, keep=keep,
                        assignments=assignments, committees=committees)
    votes, part = [], 0
    try:
        votes, part = bs_api_votes(client, conn, today, log=log, budget=budget)
        gribs_vote_parties(votes, roster)
    except (FetchError, ValueError, TypeError, AttributeError) as e:
        detail = "{0}: votes not read from data.bs.ch ({1})".format(CANTONS["bs"], str(e)[:160])
        if conn is not None:
            _gap(conn, today, detail, log=log)
        else:
            log("  [gap] " + detail)
        gaps += 1
    return acts, part, votes, gaps


def fetch_thurgau_pages(client, conn=None, today=None, log=print, budget=None):
    """The fallback: the Grosser Rat's list of pending business (grgeko.tg.ch)."""
    return parse_tg(client.get_text(TG_PENDING, FEED, "tg-pendente")), 0


TG_AUTHOR_CHUNK = 60


def fetch_thurgau_api(client, conn=None, today=None, log=print, budget=None):
    """data.tg.ch (written permission, 13 October 2026, "about weekly"):
    business received or closed in the last TG_API_DAYS days and
    everything pending, their signatories, and every vote since the newest
    stored one, quarter by quarter, with each member's vote."""
    today = today or datetime.date.today().isoformat()
    since = _since(today, TG_API_DAYS)
    q = '"{0}"'.format
    rows = client.get_json(ods_export(
        TG_ODS, TG_SETS["geschaefte"],
        # datum_beantwortung and the other step dates are text fields: ODSQL
        # cannot compare them, so pending business stands in for them.
        "datum_geschaeft_eingang >= {0} or datum_geschaeft_abschluss >= {0} or "
        "status = \"InBearbeitung\"".format(q(since))),
        FEED, "tg-ods-geschaefte", timeout=180)
    if not isinstance(rows, list):
        raise ValueError("data.tg.ch answered with no list of Geschaefte")
    numbers = sorted({r.get("geschaeftsnummer") for r in rows if r.get("geschaeftsnummer")
                      and (r.get("geschaftsart") or "") not in TG_SKIP})
    signers = []
    for i in range(0, len(numbers), TG_AUTHOR_CHUNK):
        chunk = numbers[i:i + TG_AUTHOR_CHUNK]
        signers += client.get_json(ods_export(
            TG_ODS, TG_SETS["urheber"], "geschaeftsnummer in ({0})".format(
                ", ".join(q(n.replace('"', "")) for n in chunk))),
            FEED, "tg-ods-urheber-{0}".format(i // TG_AUTHOR_CHUNK), timeout=180) or []
    acts = parse_tg_api(rows, tg_authors(signers), today=today)
    votes, part = [], 0
    for k, (a, b) in enumerate(batches(_vote_start(conn, "tg", TG_VOTE_SINCE), today, TG_BATCH_DAYS)):
        if budget is not None and budget.exhausted():
            log(budget.disclose("Thurgau vote batches", k))
            part = 1
            break
        got = client.get_json(ods_export(
            TG_ODS, TG_SETS["abstimmungen"], "datum >= {0} and datum <= {1}".format(q(a), q(b))),
            FEED, "tg-ods-abstimmungen-" + a, timeout=180)
        votes += parse_tg_api_votes(got)
    return acts, part, votes


def _api_or_pages(api, pages, name, client, conn, today, log, budget):
    """The open-data API; if it fails, the canton's own pages, and one gap
    saying so (the 4th element: gaps already recorded)."""
    today = today or datetime.date.today().isoformat()
    try:
        return api(client, conn, today, log=log, budget=budget)
    except (FetchError, ValueError, TypeError, AttributeError) as e:
        detail = "{0}: open-data API not read ({1}); read from its own site instead".format(
            name, str(e)[:160])
        if conn is not None:
            _gap(conn, today, detail, log=log)
        else:
            log("  [gap] " + detail)
        acts, g = pages(client, conn, today, log=log, budget=budget)
        return acts, g, [], 1


def fetch_baselstadt(client, conn=None, today=None, log=print, budget=None):
    """The Grand Council's exports; if they fail, data.bs.ch's API (written
    permission); if that fails too, the Grand Council's pages. A gap line
    for each step down."""
    today = today or datetime.date.today().isoformat()
    try:
        return fetch_baselstadt_gribs(client, conn, today, log=log, budget=budget)
    except (FetchError, ValueError, TypeError, AttributeError) as e:
        detail = ("{0}: the Grand Council's Geschaefte export not read ({1}); "
                  "read from data.bs.ch instead").format(CANTONS["bs"], str(e)[:160])
        if conn is not None:
            _gap(conn, today, detail, log=log)
        else:
            log("  [gap] " + detail)
    acts, g, votes, gaps = (list(_api_or_pages(fetch_baselstadt_api, fetch_baselstadt_pages,
                                               CANTONS["bs"], client, conn, today, log, budget))
                            + [0])[:4]
    return acts, g, votes, gaps + 1


def fetch_thurgau(client, conn=None, today=None, log=print, budget=None):
    return _api_or_pages(fetch_thurgau_api, fetch_thurgau_pages, CANTONS["tg"], client,
                         conn, today, log, budget)


def fetch_aargau(client, conn=None, today=None, log=print, budget=None):
    return parse_ag(client.get_json(AG_INDEX, FEED, "ag-ags-index", timeout=120)), 0


FETCH = {"zh": fetch_zuerich, "be": fetch_bern, "ge": fetch_geneva, "vd": fetch_vaud,
         "ti": fetch_ticino, "sg": fetch_stgallen, "bl": fetch_baselland, "bs": fetch_baselstadt,
         "tg": fetch_thurgau, "ag": fetch_aargau}


def reclassify(conn, tax, watch_path=None):
    n = 0
    for r in conn.execute("SELECT act_key, canton, title, title_fr FROM ch_canton_acts").fetchall():
        areas, terms, tier = classify(tax, {"key": r[0], "canton": r[1], "title": r[2],
                                            "title_fr": r[3]}, watch_path)
        conn.execute("UPDATE ch_canton_acts SET areas=?, matched_terms=?, tier=? WHERE act_key=?",
                     (ch_store.dumps(areas), ch_store.dumps(terms), tier, r[0]))
        n += 1
    # A vote whose act is not stored keeps the areas its own printed title gave it.
    conn.execute("UPDATE ch_canton_divisions SET areas=COALESCE((SELECT a.areas FROM ch_canton_acts a "
                 "WHERE a.act_key=ch_canton_divisions.act_key), '[]'), matched_terms=COALESCE(("
                 "SELECT a.matched_terms FROM ch_canton_acts a WHERE a.act_key="
                 "ch_canton_divisions.act_key), '[]'), tier=(SELECT a.tier FROM ch_canton_acts a "
                 "WHERE a.act_key=ch_canton_divisions.act_key) WHERE act_key IN (SELECT act_key "
                 "FROM ch_canton_acts) OR counts_from IS NULL")
    conn.commit()
    print("ch-cantons: reclassified {0} cantonal act(s)".format(n))


def summary(conn):
    for canton in ORDER:
        row = conn.execute("SELECT COUNT(*), SUM(CASE WHEN areas NOT IN ('[]','[11]') THEN 1 "
                           "ELSE 0 END), MAX(COALESCE(presented, first_seen)) FROM ch_canton_acts "
                           "WHERE canton=?", (canton,)).fetchone()
        print("ch-cantons: {0}: {1} act(s) stored, {2} on our ground, newest {3}".format(
            CANTONS[canton], row[0], row[1] or 0, row[2] or "-"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "data", "parl-monitor.db"))
    ap.add_argument("--canton", nargs="*", choices=ORDER, help="default: every canton read")
    ap.add_argument("--reclassify", action="store_true")
    ap.add_argument("--budget-seconds", type=float, default=BUDGET_S)
    ap.add_argument("--today", default=None, help=argparse.SUPPRESS)   # tests: a fixed day
    ap.add_argument("--dry-run", action="store_true",
                    help="read each canton once, print what was parsed, store nothing")
    args = ap.parse_args(argv)
    client = GuardedClient(HttpClient(raw_dir=os.path.join(ROOT, "data", "raw")), FEED)
    for host in POLITE_HOSTS:
        try:
            client.set_host_throttle(host, POLITE_S)
        except AttributeError:
            pass
    today = args.today or datetime.date.today().isoformat()
    cantons = args.canton or list(ORDER)
    if args.dry_run:
        for canton in cantons:
            try:
                got = FETCH[canton](client, None, today, budget=drain.Budget(90))
            except (FetchError, ValueError, ET.ParseError) as e:
                print("ch-cantons: {0}: FAILED {1}".format(CANTONS[canton], e))
                continue
            acts = got[0]
            print("ch-cantons: {0}: {1} act(s){2}".format(
                CANTONS[canton], len(acts),
                ", {0} vote(s)".format(len(got[2])) if len(got) > 2 else ""))
        return 0
    conn = db.init_db(db.connect(args.db))
    tax = Taxonomies()
    client._ch_tax = tax   # St. Gallen picks the votes whose tallies it reads
    print("ch-cantons: taxonomies taxonomy-atch v{0}, taxonomy-fr v{1}, taxonomy-it v{2}".format(
        tax.de.version, tax.fr.version, tax.it.version if tax.it else "-"))
    if args.reclassify:
        reclassify(conn, tax)
        summary(conn)
        conn.close()
        return 0
    budget = drain.Budget(args.budget_seconds)
    gaps = 0
    for canton in cantons:
        if budget.exhausted():
            print(budget.disclose("cantons", cantons.index(canton)))
            _gap(conn, today, "{0}: time budget spent before it was read".format(CANTONS[canton]))
            gaps += 1
            continue
        first_read = not conn.execute("SELECT 1 FROM ch_canton_acts WHERE canton=? LIMIT 1",
                                      (canton,)).fetchone()
        try:
            got = FETCH[canton](client, conn, today, budget=budget)
        except (FetchError, ValueError, ET.ParseError) as e:
            _gap(conn, today, "{0}: not read ({1})".format(CANTONS[canton], str(e)[:200]))
            gaps += 1
            continue
        acts, g = got[0], got[1]
        votes = got[2] if len(got) > 2 else []
        gaps += got[3] if len(got) > 3 else 0
        if g:
            _gap(conn, today, "{0}: read in part (time budget)".format(CANTONS[canton]))
        gaps += g
        if not acts:
            _gap(conn, today, "{0}: the source answered with no acts".format(CANTONS[canton]))
            gaps += 1
            continue
        # An undated canton's first read is a baseline; Basel-Stadt's API rows
        # (source_url) carry their own dates and never are.
        n, ours, new, moved = store_all(conn, acts, tax, today,
                                        baseline=first_read and canton in UNDATED
                                        and not any(a.get("source_url") for a in acts))
        for v in votes:
            store_vote(conn, v, today, tax=tax)
        conn.commit()
        npos = sum(len(v.get("positions") or []) for v in votes)
        print("ch-cantons: {0}: {1} act(s) read, {2} on our ground, {3} new to the store, "
              "{4} with a changed status{5}".format(
                  CANTONS[canton], n, ours, new, moved,
                  "; {0} vote(s){1}".format(len(votes), ", {0} member vote(s)".format(npos)
                                            if npos else "") if votes else ""))
    summary(conn)
    conn.close()
    return 3 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
