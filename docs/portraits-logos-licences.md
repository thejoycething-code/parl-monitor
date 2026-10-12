# Member portraits and party logos: licences (12 October 2026)

Chris asked for member portraits and party logos on the country editions and
partner pages, "check photo licences first". This is that check, and the gate
for `src/portraits.py`: a country gets portraits only when its row below says
**OK** (or, since 12 October 2026, "Used on Chris's instruction, licence
unclear") and the code can find the photo from what the store keeps.

How it was checked: each legislature's own legal notice, copyright or
open-data page, read on 12 October 2026 (web fetches through an honest
client, a few requests per host, no bot check bypassed). Where a site refused
us (403, CAPTCHA, certificate error) the row says so and the class is
**unclear** unless a search-engine extract of the official page was clear;
those rows are marked "(extract)". Quotes are verbatim and under 15 words.
This is a reading of published terms, not legal advice.

## Classes

- **OK with attribution**: an open licence or an explicit permission to
  reuse with credit (CC BY, public domain, "free with the source cited").
- **OK internal-only**: reuse allowed only for non-commercial, informational,
  reporting or educational purposes. Chris decided on 12 October 2026 that
  the partner pages (behind the passphrase, shared with partners) count as
  allowed non-commercial/internal use, and enabled Italy, the Netherlands,
  Austria and Switzerland ("Yes for all four"; see "Chris's decisions").
- **Not allowed**: all rights reserved, prior consent required, or the site's
  robots.txt bars us. Never fetched, whatever else changes.
- **Used on Chris's instruction, licence unclear (12 Oct 2026)**: no terms
  found, or the terms could not be read; Chris said on 12 October 2026 "use
  the photos anyway where possible". Every page showing one credits it as
  "Photo: <institution> (official portrait)". `src/portraits.py` class
  `unclear_used`.
- **Unclear**: no terms found, or the terms could not be read, and no
  instruction yet. Empty since 12 October 2026 (all 21 moved to the class
  above).

## Summary

| Class | Count | Legislatures |
|---|---|---|
| OK with attribution | 9 | UK, Ireland (Houses-owned images), US (GPO set), European Parliament, Bundestag (per image), Spain Congreso, Croatia, Brazil (Câmara and Senado), Argentina Diputados |
| OK internal-only | 12 | Canada Senate, Ontario, Quebec, Alberta, Manitoba, New Brunswick, Nova Scotia, Italy (Camera and Senato), Netherlands, Austria, Switzerland, Belgian Senate (IT, NL, AT, CH enabled by Chris, 12 Oct 2026) |
| Not allowed | 8 | British Columbia, PEI, France (AN and Sénat), Slovakia, Bolivia Diputados, Honduras, Dominican Republic (Cámara; Senado by robots.txt), Congreso Visible (CO) |
| Used on Chris's instruction, licence unclear (12 Oct 2026) | 21 | Canada Commons, Saskatchewan, Australia, Spain Senado, Belgian Chamber, Poland (Sejm, Senat), Portugal, Hungary, Argentina Senado, Mexico (both), Chile (Cámara, Senado, BCN), Colombia (both), Peru, Ecuador (site), Bolivia Senado, Uruguay, Guatemala, Panama, El Salvador, Venezuela, Nicaragua |
| Unclear | 0 | (none since 12 Oct 2026) |

**Built (fetching) since 12 October 2026: Brazil and Croatia** (OK with
attribution), **Netherlands, Austria and Switzerland** (internal use, Chris's
decision), **Poland (Sejm) and Portugal** (licence unclear, used on Chris's
instruction): in each the store's member key leads to the official photo.
Enabled but **not mappable yet**: Italy, Spain's Congreso, the Belgian
Chamber, Hungary, Chile, Ecuador, El Salvador (reasons in "Mapping and
expected fill-in"). The other legislatures have no member vote page, or no
members on it yet (Argentina, Mexico, Peru, Guatemala, Colombia, Uruguay, the
Canadian and Australian trackers, the second chambers not stored), and so
get nothing yet.

**Party logos: not used anywhere.** No official source offers a party logo
under an open licence in any of these countries; they are party trademarks.
The pages show a party colour chip instead (below).

## Legislatures

### UK, Ireland, US, EU, Germany (own trackers; not built here)

| Legislature | Photo source | Terms | Quote | robots | Class | Credit |
|---|---|---|---|---|---|---|
| UK Commons and Lords | `members-api.parliament.uk/api/Members/{id}/Thumbnail` | https://www.parliament.uk/site-information/copyright-parliament/use-of-parliamentary-photographic-images/official-portraits-copyright-information/ | "released under an Attribution 3.0 Unported (CC BY 3.0) licence" (extract) | members-api: none (404) | OK with attribution | each portrait's own credit, e.g. "© House of Commons / photographer"; link CC BY 3.0 |
| Ireland Oireachtas | API reports `image: false` for the TDs sampled; photo path unverified | https://www.oireachtas.ie/en/open-data/license/ | "Images credited to others are not covered by the ... PSI Licence" (extract) | 403, unverified | OK with attribution (Houses-owned images; PSI Licence = CC BY 4.0) | "Houses of the Oireachtas" |
| US Congress | `unitedstates.github.io/images/congress/225x275/{bioguide}.jpg` | https://github.com/unitedstates/images | "Government Printing Office, which has assured us that all photos are public domain" | bioguide.congress.gov disallows all generic bots: use the mirror | OK with attribution (public domain) | "U.S. Government Publishing Office" |
| European Parliament | `europarl.europa.eu/mepphoto/{mepId}.jpg` | https://www.europarl.europa.eu/legal-notice/en/ | "the entire item is reproduced and the source is acknowledged" | allowed | OK with attribution | "© European Union, [year], Source: European Parliament" |
| Germany Bundestag | `bilddatenbank.bundestag.de` (per image) | https://www.bundestag.de/bildnutz | "für private und kommerzielle nicht-werbliche Zwecke genutzt werden" (per image) | allowed | OK with attribution, per image; election-campaign use banned | "Deutscher Bundestag/[photographer]" |

Note for the UK: `templates/vote-tracker.html` shows the Members API
thumbnail on `mp-votes.html` (partner and public builds), loaded from
Parliament's server. Since 12 October 2026 the page footer carries the
CC BY 3.0 credit, "Photos: UK Parliament (CC BY 3.0; terms)", linking the
licence and Parliament's portrait terms, and each photo has the same credit
as its title (tests/test_vote_tracker.py, PortraitCreditTests).

### Canada (federal and provinces; not on the new-country pages)

| Legislature | Photo source | Terms | Quote | robots | Class |
|---|---|---|---|---|---|
| House of Commons | `ourcommons.ca/Content/Parliamentarians/Images/OfficialMPPhotos/45/{SurnameGiven}_{Party}.jpg` | https://www.ourcommons.ca/en/important-notices | "does not extend to reproduction, distribution or use for commercial purpose" | allowed | Used, licence unclear (12 Oct 2026) (no photo licence; PhotoService@parl.gc.ca) |
| Senate | `sencanada.ca/media/...` | https://sencanada.ca/en/intellectual-property/ | "educational, private study, research, criticism, review or news reporting" | allowed | OK internal-only |
| Ontario | `ola.org/sites/default/files/member/profile-photo/...` | https://www.ola.org/en/office-assembly/copyright-privacy | "The use must be reasonable, fair and non-commercial" | `Disallow: /*?` (use files without a query) | OK internal-only, credit the Assembly |
| Quebec | `assnat.qc.ca/Media/Process.aspx?...` | https://www.assnat.qc.ca/fr/propos-site/droits-propriete-intellectuelle.html | "l'utilisation est raisonnable, équitable et non commerciale" | grey (case-sensitive rules) | OK internal-only |
| Alberta | `assembly.ab.ca/images/default-source/members/mla-photos/ph-mla{n}.jpg` | https://www.assembly.ab.ca/disclaimer | "personal or public non-commercial use" | allowed | OK internal-only; no political party advertising or election-period use |
| British Columbia | not found | https://www.leg.bc.ca/copyright | "No person may reproduce the material ... other than personal use" | allowed | Not allowed |
| Saskatchewan | `legassembly.sk.ca/media/...` | none found | none | none (404) | Used, licence unclear (12 Oct 2026) |
| Manitoba | `gov.mb.ca/legislature/img/mla/{surname}.jpg` | https://www.gov.mb.ca/legislature/copyright.html | "for non-commercial use only" | bars ClaudeBot and named AI bots | OK internal-only |
| New Brunswick | `legnb.ca/content/members/portraits/61-1/{Given}_{Surname}_sm.jpg` | https://www.legnb.ca/en/disclaimer | "may be reproduced for educational purposes, private study, research, reporting" | allowed, crawl-delay 10 | OK internal-only |
| Nova Scotia | `nslegislature.ca/.../mla-thumbnails/{Name}.jpg` | https://nslegislature.ca/node/121275 | "reproduce material on this site for non-commercial use only" | allowed | OK internal-only |
| Prince Edward Island | `assembly.pe.ca/.../MLA Photos/...` | https://www.assembly.pe.ca/copyright (bot wall; extract) | Speaker's written consent beyond personal use (paraphrase) | bot challenge, not attempted | Not allowed |

Australia (aph.gov.au) refused every fetch (403); secondary sources conflict
(CC BY-NC-ND 3.0 AU on sister sites; AUSPIC wording bars use "for
compensation" without permission). **Used on Chris's instruction, licence
unclear (12 Oct 2026)**, but nothing is built: the Australian pages are their
own tracker and aph.gov.au refuses us. The existing review cards
(`tools/review_photos.py`) embed Canadian portraits for Chris's own review
round only, not on a partner page.

### Europe (the new-country vote pages)

| Legislature | Photo source | Terms | Quote | robots | Class | Credit |
|---|---|---|---|---|---|---|
| Spain Congreso | `congreso.es/docu/imgweb/diputados/{id}_{leg}.jpg` | https://www.congreso.es/es/cem/aviso-legal | "Que se cite la fuente." | allowed | OK with attribution (unaltered, dated) | "Fuente: Congreso de los Diputados" |
| Spain Senado | `senado.es/legis15/senadores/fotos/S{n}.jpg` (extract) | https://www.senado.es/web/avisojuridico/index.html (403) | reuse "en los términos fijados en las condiciones de reutilización" (extract) | 403 | Used, licence unclear (12 Oct 2026) | |
| Italy Camera | `documenti.camera.it/_dati/leg{N}/schededeputatinuovosito/fotoDefinitivo/big/d{id}.jpg` | https://comunicazione.camera.it/policy/avvisolegale | "per finalità non commerciali, garantendo l'integrità degli elementi riprodotti" | allowed | OK internal-only | "Fonte: Camera dei deputati" |
| Italy Senato | senato.it (403) | https://www.senato.it/guida-al-sito/avviso-legale | CC-BY "nei limiti dell'interesse pubblico all'informazione" (extract) | 403 | OK internal-only (conservative) | source cited, image intact |
| France Assemblée nationale | `assemblee-nationale.fr/dyn/static/tribun/17/photos/carre/{id}.jpg` | https://www.assemblee-nationale.fr/dyn/info-site | "ne peuvent être reproduits sans accord préalable" | allowed, crawl-delay 30 | **Not allowed** (Licence Ouverte covers data, not photos) | |
| France Sénat | `senat.fr/senimg/{slug}_carre.jpg` | https://www.senat.fr/mentions-legales.html | "Les autres contenus sont couverts par le droit d'auteur." | allowed | **Not allowed** | |
| Netherlands Tweede Kamer | gegevensmagazijn OData `Persoon({Id})/resource` (some persons only); the store keys members by that Id | https://www.tweedekamer.nl/applicaties/disclaimer | "mogen worden gebruikt door derden onder de CC-BY-NC 4.0 licentie" | gegevensmagazijn robots.txt answers 500; the OData API is a documented API (`src/robots_guard.DOCUMENTED_APIS`, docs/robots-runtime.md), fetched as the collectors fetch it | OK internal-only (CC BY-NC 4.0); **enabled 12 Oct 2026** | "Tweede Kamer (CC BY-NC 4.0; non-commercial use)" |
| Belgium Chamber | WAF refused every request | none read | none | refused | Used, licence unclear (12 Oct 2026) | |
| Belgium Senate | senate.be | gallery credit line only | "Copyright : Guy Goossens - Sénat de Belgique" | allowed | OK internal-only (press use, credited) | as quoted |
| Austria Parlament | `parlament.gv.at/dokument/bild/{n}/{n}_384.jpg`, named on the member's page `/person/{PAD}` (checked 12 Oct 2026) | https://www.parlament.gv.at/services/hilfe/nutzungsbedingungen/ | "ausschließlich für folgende Zwecke" (reporting, political education, private use) | allowed | OK internal-only; CC BY 4.0 is the data only; **enabled 12 Oct 2026** | "Parlamentsdirektion (official portrait; non-commercial informational use)" |
| Switzerland | `parlament.ch/SiteCollectionImages/profil/portrait-260/{PersonNumber}.jpg` (checked 12 Oct 2026) | https://www.parlament.ch/de/services/mediathek/fotos-nutzungsbedingungen | commercial use "ohne vorgängige schriftliche Genehmigung ... untersagt" | allowed | OK internal-only; **enabled 12 Oct 2026** | "Parlamentsdienste / ParlCH (official portrait; non-commercial use)" |
| Poland Sejm | `api.sejm.gov.pl/sejm/term10/MP/{id}/photo` (checked 12 Oct 2026; https://api.sejm.gov.pl/) | none found (API docs carry no licence) | none | api: none (404); sejm.gov.pl shows a CAPTCHA | Used, licence unclear (12 Oct 2026) | |
| Poland Senat | senat.gov.pl (403) | none found | none | 403 | Used, licence unclear (12 Oct 2026) | |
| Portugal | `app.parlamento.pt/webutils/getimage.aspx?id={BID}&type=deputado` (checked 12 Oct 2026) | https://www.parlamento.pt/Cidadania/Paginas/DadosAbertos.aspx | "podem ser livremente reutilizados por qualquer instituição ou pessoa" (data; photos not named) | none (404) | Used, licence unclear (12 Oct 2026), leaning OK | "Assembleia da República" |
| Croatia Sabor | the member's page names the file: `sabor.hr/sites/default/files/uploads/sabor/{date}/{node}/{Surname, Name}.jpeg` | https://www.sabor.hr/hr/pravne-napomene | "mogu se preuzimati bez posebnog dopuštenja uz navođenje izvora" | allowed | **OK with attribution** (Sabor-authored, unaltered) | "Hrvatski sabor" |
| Slovakia NR SR | `nrsr.sk/web/dynamic/PoslanecPhoto.aspx?PoslanecID={id}` | site footer | "Všetky práva vyhradené." | none | **Not allowed** | |
| Hungary | parlament.hu (CAPTCHA, not attempted) | https://parlament.hu/documents/d/guest/jogi-nyilatkozat (extract: liability only) | none | CAPTCHA | Used, licence unclear (12 Oct 2026) | |

### Latin America

| Legislature | Photo source | Terms | Quote | robots | Class | Credit |
|---|---|---|---|---|---|---|
| Brazil Câmara | API `urlFoto`: `camara.leg.br/internet/deputado/bandep/{id}.jpg` | https://www2.camara.leg.br/termo-de-uso-e-politica-de-privacidade/termos-gerais and the journalists' guide | "podem ser livremente utilizadas, sem custo e sem necessidade de autorização" | bandep allowed (checked) | **OK with attribution** | "Arquivo/Câmara dos Deputados" |
| Brazil Senado | API `UrlFotoParlamentar`: `senado.leg.br/senadores/img/fotos-oficiais/senador{code}.jpg` | https://www12.senado.leg.br/assessoria-de-imprensa/politica-de-uso | "reprodução de matérias e fotografias é livre, mediante a citação da Agência Senado" | none (404) | **OK with attribution** | "Agência Senado" |
| Argentina Diputados | `parlamentaria.hcdn.gob.ar/image/{id}_{ts}_small.png` | https://www.hcdn.gob.ar/diputados/ (footer) | "es de dominio público y puede ser utilizada libremente" | www bars named AI bots; parlamentaria none | OK with attribution | "Fuente: Honorable Cámara de Diputados de la Nación" |
| Argentina Senado | `senado.gob.ar/bundles/senadosenadores/images/fsenaG/{id}.gif` | none found | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Mexico Diputados, Senado | SITL (refused connection); senado.gob.mx (403) | none found | none | unverified | Used, licence unclear (12 Oct 2026) | |
| Chile Cámara | `camara.cl/img.aspx?prmID=...` (extract) | https://www.camara.cl/camara/camara_tc.aspx (403) | none | bars AI bots; `ai-train=no` | Used, licence unclear (12 Oct 2026) | |
| Chile Senado | unverified | none found | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Chile BCN reseñas | `bcn.cl/historiapolitica/resenas_parlamentarias/getimagenbiografia/{Name}.jpg` | no licence on bcn.cl; Commons cites VRT permission | Commons: "Creative Commons Attribution-ShareAlike 3.0 Chile" (second-hand) | robots.txt unreadable | Used, licence unclear (12 Oct 2026) (second-hand; metadata says Cámara, "Editorial") | |
| Colombia Cámara | unverified | terms PDF, text not extractable | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Colombia Senado | `senado.gov.co/images/Fotos_Senadores_2022/{Name}.jpg` (2022 cohort) | none found | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Congreso Visible (CO) | no member photos | footer | "Todos los derechos reservados" | not checked | Not allowed | |
| Peru Congreso | WordPress uploads by name, irregular | privacy policy only | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Ecuador Asamblea | Drupal private files with tokens; official Flickr | https://www.flickr.com/photos/asambleanacional | Commons: Flickr files "licensed under the terms of the cc-by-sa-2.0" | allowed, crawl-delay 1 | Used, licence unclear (12 Oct 2026) (site); Flickr per photo OK with attribution | per Flickr page |
| Bolivia Diputados | WordPress uploads, irregular | footer | "Todo los derechos reservados." | none | Not allowed | |
| Bolivia Senado | `apisi.senado.gob.bo` `foto_perfil` | none found | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Uruguay | parlamento.gub.uy (403) | national open-data licence covers catalogue datasets only; no legislators dataset | none | 403 | Used, licence unclear (12 Oct 2026) | |
| Guatemala | congreso.gob.gt (403 everywhere) | none read (Commons' PD claim doubtful) | none | 403 | Used, licence unclear (12 Oct 2026) | |
| Panama | asamblea.gob.pa (certificate error) | not read | none | unreachable | Used, licence unclear (12 Oct 2026) | |
| Honduras | congresonacional.hn (pages by script) | footer | "Todos los derechos reservados." | none | Not allowed | |
| El Salvador | asamblea.gob.sv (certificate error) | not read | none | unreachable | Used, licence unclear (12 Oct 2026) | |
| Dominican Rep. Cámara | `camaradediputados.gob.do/wp-content/uploads/...` | footer (terms link 404) | "© 2024 Todos los derechos reservados" | uploads allowed | Not allowed | |
| Dominican Rep. Senado | `senadord.gob.do` | not read | none | bars ClaudeBot and others site-wide | Not allowed (robots opt-out) | |
| Venezuela | no official portraits found | none | none | allowed | Used, licence unclear (12 Oct 2026) | |
| Nicaragua | `verifica.asamblea.gob.ni/Images/{id}.jpg` | none found | none | none | Used, licence unclear (12 Oct 2026) | |

Wikimedia Commons holds portraits for many of these parliaments under
per-file licences (mostly CC BY or CC BY-SA). It is the realistic fallback
for the unclear and not-allowed countries, but each file must carry its own
author and licence; that is not built (coverage unmeasured).

## Chris's decisions, 12 October 2026

1. **Internal use.** "Yes for all four": the partner pages (behind the
   passphrase, shared with partners) count as allowed non-commercial/internal
   use, so Italy (Camera and Senato), the Netherlands, Austria and
   Switzerland are enabled. The Belgian Senate (not on a vote page) and the
   Canadian provinces (their own tracker) were not part of the decision and
   stay as they were.
2. **Unclear licences.** "Use the photos anyway where possible": the 21
   unclear legislatures moved to "Used on Chris's instruction, licence
   unclear (12 Oct 2026)", credited "Photo: <institution> (official
   portrait)".
3. **Not allowed stays off.** British Columbia, PEI, France (both houses),
   Slovakia, Bolivia Diputados, Honduras, the Dominican Republic and
   Congreso Visible: their terms forbid reuse or robots.txt bars us. Never
   fetched.

Unchanged rules: robots.txt obeyed through the per-run guard
(`src/robots_guard.py`, `src/prov_fetch.read_robots`; a robots.txt that
answers 5xx or not at all means no fetch from that host, and for photos a
401/403 answer too; documented machine APIs as in docs/robots-runtime.md);
member pages read to find a photo are checked too; no bot check or CAPTCHA
ever bypassed ("where possible" means where the site serves us); the
identified UA "CitizenGO-ParlMonitor/1.0 (contact: cjoyce@citizengo.net)";
the `src/http.py` per-host throttle and any Crawl-delay; at most 150 photos
a country a run; 96 px thumbnails; a credit line on every page that shows
them; never in DMs; party colour chips, no logos.

## Mapping and expected fill-in

Members on each vote page from the store on 12 October 2026. The fetch is
the existing Sunday step (`jobs/editions-session-judge.sh`, 16:45 London on
the Mini), at most 150 photos a country a run, so a page of N members fills
in ceil(N / 150) Sundays; the partner deploy on the Monday after ships them.
The first run is Sunday 18 October 2026. A member with no photo (404, not an
image) is rechecked after 30 days; a fetched photo is refreshed after 180.

| Country | Class | Store key leads to | Members on page | Expected complete |
|---|---|---|---|---|
| Brazil | OK with attribution | API photo by deputy id / senator code | 690 | already running (built 12 Oct) |
| Croatia | OK with attribution | member page names the file | 174 | already running (built 12 Oct) |
| Poland (Sejm) | licence unclear, used | `<term>/<id>` to `api.sejm.gov.pl/sejm/term{t}/MP/{id}/photo` | 461 | 4 Sundays: 8 November 2026 |
| Portugal | licence unclear, used | BID to `app.parlamento.pt/webutils/getimage.aspx?id={BID}&type=deputado` | 232 | 2 Sundays: 25 October 2026 |
| Netherlands | internal (Chris) | Persoon Id to OData `Persoon({Id})/resource` | 168 | 2 Sundays: 25 October 2026 (some persons have no photo) |
| Austria | internal (Chris) | PAD to `/person/{PAD}`, which names `/dokument/bild/.../{n}_384.jpg` (two requests a member) | 242 | 2 Sundays: 25 October 2026 |
| Switzerland | internal (Chris) | PersonNumber to `SiteCollectionImages/profil/portrait-260/{PersonNumber}.jpg` | 266 | 2 Sundays: 25 October 2026 |

**Not mappable yet** (enabled, nothing fetched; the page renders as before):

- **Italy, Camera**: the Camera files a photo by its own deputy id
  (`d{id}.jpg`); the store keys deputies by the Openpolis membership id
  (`C:207`) and `it_members.camera_id` is empty for all 415. Needs the Camera
  id stored (Openpolis identifiers or dati.camera.it).
- **Italy, Senato**: the store keys senators by the dati.senato.it id, but
  senato.it serves us empty pages (no photo path readable); nothing
  bypassed.
- **Spain, Congreso**: the store keys deputies by name ("Abascal Conde,
  Santiago"); the photo needs the Congreso's numeric id.
- **Belgium, Chamber**: the Chamber's firewall refuses every request.
- **Hungary**: parlament.hu answers with a CAPTCHA.
- **Chile, Cámara**: camara.cl answers 403 to the photo service and the
  member pages; **Senado**: the store keeps the PARLID, but no photo route
  from it was found.
- **Ecuador**: the store keys members by name; the site's photos are private
  files with tokens.
- **El Salvador**: asamblea.gob.sv is unreachable (certificate error).
- **No members on a vote page yet**: Argentina (no vote page with members),
  Mexico, Peru, Guatemala, Colombia, Uruguay. Slovakia and the Dominican
  Republic are not allowed.
- **Not on a new-country vote page**: Canada Commons and Saskatchewan (the
  Canadian tracker), Australia (its own tracker; aph.gov.au refuses us),
  Spain Senado, Poland Senat, Argentina Senado, Chile BCN, Bolivia Senado,
  Panama, Venezuela, Nicaragua.

## Party logos

Every research pass came to the same answer: no parliament, electoral body
(TSE, CNE, INE, Servel) or party publishes its logo under an open licence
for reuse. Logos are registered trademarks. Commons hosts some as
"PD-textlogo" (too simple for copyright), but that is Commons' copyright
judgement, not a licence, and trademark rights remain. Identifying a party by
its mark on a factual, non-commercial page is ordinarily defensible
(nominative use), but nothing here requires it and the risk is CitizenGO's
to take, as `partner_site/logos/README.md` already says for the UK. The
Camera dei deputati and the Assemblée nationale also forbid use of their own
institutional logos.

**Decision built: party colour chips everywhere, no logos.**
`config/party-colours.yaml` holds each party or group's colour from Wikidata
(P465, CC0), matched to the store's labels by `tools/party_colours.py`, with
the Wikidata item beside each; a label with no unambiguous colour gets no
chip (about half the labels, mostly parliamentary group abbreviations such
as Spain's GP or France's EPR). A person can add one with its source.

## What is built

- `src/portraits.py`: one `Source` per vote-page country with its class,
  terms URL and credit; only usable classes (OK with attribution, internal,
  used on Chris's instruction) with a photo route fetch.
- `tools/fetch_portraits.py`: members on each usable country's vote page,
  robots.txt checked per host through the per-run guard (an unreadable
  robots.txt means no fetch; member pages read for a photo are checked too),
  `src/http.py` throttle and UA, at most 150 photos a country a run, 96 px
  JPEG thumbnails (sips), cache `data/portraits/<cc>/` (gitignored), manifest
  `data/portraits/<cc>.json` (committed: image URL, page, licence, credit).
- `tools/make_country_votes.py`: copies only on-page thumbnails to
  `partner_site/portraits/<cc>/` (behind the passphrase; never hotlinked),
  shows them on the member card with "Photo: <credit> (source)" and a
  portraits line in the notes; colour chips in the member card and the party
  split table. DMs never carry a portrait.
- A step in `jobs/editions-session-judge.sh` (Sundays 16:45, Mini), before
  the vote pages. No new job.

## Waiting on Chris

1. **Internal-only countries**: decided 12 October 2026 for Italy, the
   Netherlands, Austria and Switzerland (above). Still open: the Belgian
   Senate (not on a vote page) and the Canadian provinces if the CA pages
   ever get portraits (Alberta bans party-political use). Italy and Spain
   need the member id stored before their photos can be found.
2. **Unclear countries**: decided 12 October 2026 ("use the photos anyway
   where possible"). Optional: ask the press offices (Poland's Sejm,
   Portugal, Chile, Mexico, Colombia) to firm the licence up, or allow
   Wikimedia Commons as a per-file fallback where a site refuses us.
3. **Party logos**: confirm colour chips only; logos would mean asking each
   party for its brand assets.
4. **UK tracker**: the CC BY 3.0 credit line is on the page (done 12 October
   2026); still to consider: caching the thumbnail instead of loading it
   from Parliament.
