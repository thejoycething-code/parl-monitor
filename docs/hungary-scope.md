# Hungary: scoping the Országgyűlés monitor

Probed live on 9 October 2026, from the laptop (BT residential line, London)
and once from a GitHub runner. Every number below was measured, not
estimated. Groundwork only: **nothing is built, scheduled or stored**,
because the one source that carries recorded votes refuses every client
that is not a browser (see "The blocker"). National parliament only; the
county assemblies are listed at the end for later.

## Decisions already taken (Christopher, before this scope)

- Own edition, delivered to Christopher alone (Slack DM), as for the US.
- Shared taxonomy concept, but `config/taxonomy.yaml` and every existing
  taxonomy file are never edited. The Hungarian term list is PROPOSED below;
  Christopher approves it before a `config/taxonomy-hu.yaml` is generated.
- National parliament first; regions later.
- Mac Mini is the default runtime, GitHub Actions the backup (the Mini-first
  weekly pattern of `jobs/au-weekly.sh`). No new paid services. Never post
  publicly anywhere.

## The blocker

**www.parlament.hu answers every request from this project with an image
CAPTCHA.** Not a 403, not a rate limit: an HTTP 200 carrying a 33,022-byte
page titled "CAPTCHA Ellenőrzés" ("Validation needed due to: Policy
constraints. Number of attempts left: 5"), with a form posting to
`/captcha_resp` and `x-bni-ci` / `BNIS_x-bni-jas` cookies (a bot-management
layer in front of the whole host). Measured:

| Asked for | From | Got |
|---|---|---|
| `/`, `/robots.txt`, `/web/guest/w-api`, `/web/guest/szavazasok`, `/web/guest/iromanyok-lekerdezese`, `/documents/10181/0/`, `/cgi-bin/web-api-pub/kepviselok.cgi`, `/cgi-bin/web-api-pub/szavazasok.cgi` | laptop, honest UA | the same CAPTCHA page, 8 of 8 |
| `parlament.hu/` (no www), `konyvtar.parlament.hu/` (the library) | laptop | the same CAPTCHA page |
| `/`, then four more URLs | GitHub runner, `probe-hosts.yml` run 37881481912 | CAPTCHA on the first; `tools/probe_hosts.py` stopped the host, as it must |

Even `robots.txt` is behind it. Per the house rule (and
`tools/probe_hosts.py`), a challenge is recorded and never solved, retried
with another User-Agent, or worked around. **So no Phase 1 collector was
built**: the brief said to stop after the scope if the source needs a key or
is too hostile, and it is both.

### What sits behind the wall: the W-API

The Országgyűlés does publish a proper API, documented by a third party who
has a token (the `karzat` project, github.com/abognar-git/karzat, MIT, last
pushed 3 September 2026; read, not run):

- Base `https://www.parlament.hu/cgi-bin/web-api-pub/<service>.cgi`, XML,
  `access_token=<personal code>` as a GET parameter. "Manual v2.5" is handed
  to each registrant and not redistributed.
- **Registration by email to `api-reg2@parlament.hu`; free; the token is
  personal and every request is logged by the Office of the National
  Assembly (OGYH).** karzat's token took an unknown time to arrive and came
  on 18 August 2026.
- Twelve services, exactly what a vote monitor needs: `kepviselok` (sitting
  MPs), `kepviselo` (one MP, seat, faction history), `szavazasok` (votes in a
  date range, `p_datum_tol`/`p_datum_ig` as `ÉÉÉÉ.HH.NN`), `szavazas` (one
  vote, by faction and by name, keyed by timestamp `ÉÉÉÉ.HH.NN.ÓÓ:PP:MM`),
  `iromanyok` (all papers of the current term), `iromany` (one paper with its
  events, votes and promulgation), `bizottsagok`/`bizottsag`, `szoszolok`,
  `ulesnap` (sitting days), `felszolalasok`/`felszolalas` (speeches, full text).
- No stated rate limit (karzat paces itself at 0.6 s). karzat reports a
  400-row cap on some daily vote listings in old cycles, so a weekly pull
  should ask day by day.
- **UNVERIFIED: whether the CAPTCHA layer lets a token-bearing request
  through.** karzat syncs live with a plain `requests` client and a
  non-browser UA (`karzat/0.0.1`), which suggests the API path is exempt for
  valid tokens, but its host may sit on a Hungarian IP. The first thing to do
  with a token is one request from the Mini and one from a runner.

### What the record looks like (from karzat's derived data, CC BY 4.0)

karzat commits its derived tables. They are not a live source (the site
ogykarzat.hu returned SERVFAIL on 9 October, the data stops at 28 August
2026, and the underlying record "conveys no rights"), but they show the
shape of term 43 and let the taxonomy be measured on real titles:

| Term 43 (from 9 May 2026), to 28 August 2026 | Count |
|---|---|
| Papers (irományok) | 586: 183 written questions (K), 137 urgent questions (A), 117 interpellations (I), 71 bills (T), 35 resolutions (H), 22 appointments, 18 reports (B), 3 information papers |
| Recorded votes | 272 (271 decisions, 1 quorum call); 267 by name, 5 secret ballots |
| Sitting days | 25: Mondays 10, Tuesdays 11, one each Wednesday to Saturday |
| Factions in votes | TISZA 141, Fidesz 44, KDNP 8, Mi Hazánk 6 (of 199) |

Hungarian votes carry the majority rule they needed, and term 43 already
mixes them: 202 simple, 48 two-thirds of those present (cardinal laws), 9
two-thirds of all MPs (constitutional), 7 absolute, 5 four-fifths. Six
recorded positions, not three (igen, nem, tartózkodott, jelen nem szavazott,
nem szavazott, előre bejelentett hiányzó), and abstention is a real
political act here. Votes are keyed by timestamp, not number. **Interpellation
answers are voted on**: the House accepts or rejects the minister's reply,
so an interpellation on our ground produces a recorded vote.

## The finding that shapes everything

**The English taxonomy is blind to Hungarian, more completely than to
German.** `config/taxonomy.yaml`, unchanged:

| Corpus | English taxonomy | Draft Hungarian list (below) |
|---|---|---|
| Term 43 paper titles, 586 | **1** (`IHR`, a WHO-regulations question: not ours) | **59** (25 tier 1) |
| of which bills and resolutions, 106 | 0 | 14 |
| of which questions and interpellations, 437 | 1 | 43 |
| Recorded votes, 271, joined to their paper | 0 | **17**, on 15 papers |
| Magyar Közlöny contents, 55 issues 20 July to 8 October 2026, 389 entries | **0** | 19 (5 tier 1) |
| of which Acts, 21 | 0 | 2 (both tier 2) |

German shared a few loanwords with English ("Migration"); Hungarian shares
none that matter. Without a Hungarian list a Hungarian monitor collects
everything and sees nothing.

Draft-list hits by area on the 586 titles: parental rights and education 22,
marriage and family 14, free speech 10, migration 8, abortion 3, sex-based
rights 2, religion 2, prostitution and exploitation 2. What it caught that
belongs: an interpellation on making the abortion pill available (I/184),
the Fidesz-KDNP resolution rejecting the EU Migration Pact (H/179), the bill
abolishing the Sovereignty Protection Office (T/123), the chemical-castration
bill for paedophile offenders (T/573), questions on same-sex marriage (I/133),
on sex education and parents' rights (I/94), on the "Pride instead of
procession" row (A/77 and repeats), on pro-life groups shut out of a
ministry consultation (K/463), on keeping faith-and-ethics teaching (I/344).

### What the first cut missed, and why (fixed in the list below)

Measured misses, each now covered:

- **Hungarian stems change.** `védelem` (protection) becomes `védelm-`
  before a suffix: "gyermekvédelem" but "gyermekvédelmi". A stem of
  `gyermekvédelm*` missed H/58, the inquiry committee into the
  child-protection crisis. Every `-védelem` term is now `-védel*`. This is
  the Hungarian equivalent of the German `*` lesson, and it will recur
  (`-alom/-alm-`, `-elem/-elm-`, vowel-dropping stems).
- **T/294**, a bill banning symbols "referring to sexual and gender
  orientations" (the rainbow-flag ban): "szexuális és nemi irányultságokra"
  splits the phrase the list carried. Now `nemi irányultság*` plus a guarded
  `irányultság*`.
- **T/48**, protecting children from the harms of digital devices: now a
  guarded `digitális eszköz*`.
- **T/122**, curbing "hate-inciting" political advertising (enacted): now
  `gyűlöletkelt*`.
- Media law (T/200), the new public-media foundation (H/394) and the public
  education omnibus (T/340): now tier 2.

### Measured noise

- `család*` (family) at tier 2 caught "the Prime Minister and his family"
  (I/349). Replaced by `családok*`, `családi*`, `családügy*` and friends.
- `gyermekvédel*` is the child-welfare SYSTEM (residential care, the
  2024 Bicske pardon scandal that brought down a President, pay for care
  workers). It is high-volume in term 43 (8 papers). It stays tier 2: the
  scandal is about abuse of children in state care, which our audience
  reads, but most items are workforce and budget.
- Family benefits (CSOK, babaváró, GYED, GYES, the mothers' income-tax
  exemption) are tier 1 in the draft and are the single biggest Hungarian
  family-policy fight under the new government. Christopher should confirm
  they are our ground at that weight (see Waiting on Chris).

### Constitutional amendments

Term 43 has already passed **two amendments to the Fundamental Law**
(T/51, the sixteenth; T/324, the seventeenth, which the gazette shows is
being worked through other legislation as terminology changes, e.g. SZTFH
decree 10/2026 citing it). Their titles carry no subject ("Magyarország
Alaptörvényének tizenhetedik módosítása"), so no term can catch them. The
amendments of the previous terms are exactly CitizenGO ground: the ninth
(2020: "the mother is a woman, the father is a man"), the fifteenth (2025:
a person is a man or a woman; a child's right to physical, mental and moral
development overrides every other right but life; the basis of the Pride
ban). A two-thirds TISZA majority may amend or reverse them. **Proposal:
every paper whose title begins "Magyarország Alaptörvényének" goes to triage
with a minimum score of 2**, as a collector rule rather than a term, and is
read in full. Nothing else in Hungary is as likely to move our ground in one
vote.

## What Hungary publishes

| Source | What | Key? | Works for us? |
|---|---|---|---|
| parlament.hu W-API | members, votes by name, papers, events, sittings, speeches, committees | **personal token, free, by email** | **Not tested: CAPTCHA wall** (above) |
| parlament.hu web pages (szavazások, irományok, napirend, ülésnaplók) | the same, as HTML; agenda; verbatim record | no | **No: CAPTCHA wall, robots.txt included** |
| Magyar Közlöny, magyarkozlony.hu | official gazette: Acts, decrees, OGY resolutions, Constitutional Court (AB) decisions, presidential (KE) decisions | no | **Yes.** RSS `https://magyarkozlony.hu/feed` (100 items, all official journals, each with `mag:type`, `mag:serial`, `mag:year` and a PDF enclosure); `robots.txt` is `Disallow:` (empty). 55 Magyar Közlöny issues 20 July to 8 October 2026, 1,646 pages, 21.0 MB, fetched in 176 s at one per 2 s. PDFs have a clean text layer and a "Tartalomjegyzék" (contents) on page 1. In those issues: at least 21 Acts, 35 OGY resolutions, 5 AB decisions, 79 government decrees. No votes, so it is the "became law" leg only. |
| Wikidata SPARQL | members, party, term | no | **Yes.** 203 people hold "member of the National Assembly of Hungary" (Q17590876) with a start in 2026 and term "2026–2030-as parlamenti ciklus": TISZA 142, Fidesz 47, KDNP 8, Mi Hazánk 6 (replacements included). |
| njt.hu (Nemzeti Jogszabálytár, consolidated law) | in-force text of every law | no | **No from here: TCP reset after the TLS handshake**, every request. Not needed for Phase 1. |
| karzat (third party, GitHub) | derived tables of every vote since 1990 | no | Stale (28 August) and its site is down; useful for measurement and as a cross-check, not as a feed. |
| K-Monitor parldata (parlament.k-monitor.hu) | debates front-end | n/a | Front-end repository only; not a data source. |
| alkotmanybirosag.hu, kormany.hu | Constitutional Court, government | no | Both answer (301 and 200). Not probed further; AB decisions already arrive through the gazette. |

## Proposed phasing

**Phase 0 (needs nothing): the gazette leg.** A `tools/hu_gazette.py` that
reads the Magyar Közlöny RSS weekly, fetches only new issues, extracts the
contents page and stores each Act, OGY resolution and AB decision with its
official number (`2026. évi LVI. törvény`, `22/2026. (V. 27.) OGY
határozat`) as the key. It sees what became law, not who voted. Worth
building only if the token is refused or delayed for weeks: on its own it
reports a week late and without positions.

**Phase 1 (needs the token): `tools/hu_rollcalls.py`.** Weekly, day by day
since the last run: `szavazasok` for the week, `szavazas` for each new vote
(positions by name), `iromany` for every paper a vote names (joined by paper
number, e.g. `T/324`, **never by title**: a Hungarian vote often has no
title of its own, as in the US), `iromanyok` for new papers, `kepviselok`
for the roster. Store in `hu_members`, `hu_papers`, `hu_divisions`,
`hu_votes` (schema in a `src/hu_store.py`, declared in `db.TABLES`), with
the majority rule and the six positions kept as the record gives them.
Expected load: about 30 requests a sitting week. The weekly runs on the
Mini first, Wednesday early morning London (the House sits Monday and
Tuesday), with `.github/workflows/hu-weekly.yml` as the backup, gated by
`mini-check` with `HU_WEEKLY`, as `au-weekly.yml` is. The token goes in
`~/runner/env` on the Mini and as an Actions secret, never in the repo.

**Phase 2:** speeches (`felszolalasok`), passage-matched as Germany's are;
committee agendas; the gazette leg as the promulgation check.

**Later: regions.** Hungary is unitary. Below the Országgyűlés sit 19
county assemblies (vármegyei közgyűlések) and the Budapest General Assembly
(Fővárosi Közgyűlés), plus 23 cities with county rights. They pass local
decrees, not laws, and publish on their own sites. Not scoped.

## Proposed Hungarian term list (v0.1, for approval)

AI draft, measured on the corpora above, **not read by a Hungarian speaker**.
Same thirteen areas and keys as the English and German files. A measuring
copy sits in the local probe archive
(`data/raw/hu-probe-2026-10-09/taxonomy-hu-draft.yaml`); on approval it
becomes `docs/keyword-taxonomy-hu.md` and is generated into
`config/taxonomy-hu.yaml` with `tools/generate_taxonomy.py --lang hu`.

### Matching rules for Hungarian

- **Almost every term needs a trailing `*`.** Hungarian is agglutinative:
  `abortusz`, `abortuszt`, `abortuszról`, `abortusztabletta`. A bare noun
  matches only its dictionary form.
- **Stems alternate** (`védelem` / `védelm-`): cut the stem before the
  alternating vowel (`gyermekvédel*`).
- **Never bare: `nem`** (both "sex" and "not"), `meleg` ("gay" and "warm"),
  `élet` (life, inside `életmód`, `életpálya`), `család`, `gyermek`, `jog`,
  `egyház`, `védelem`. These go in the global exclusions and appear only in
  phrases.
- **Accents are letters.** `válás` (divorce) and `választás` (election)
  differ by an accent; the filter keeps accents, so terms must be typed with
  them.
- All-caps acronyms (`LMBT`, `CSOK`, `GYED`, `GYES`, `NMHH`, `NAT`, `IVF`,
  `DSA`) match case-sensitively, which is correct here.

### Mergeability

Hungarian is an official language only in Hungary (and in Vojvodina and
some Romanian and Slovak municipalities, whose legislatures we do not
monitor), so no parallel scope shares this list today. Terms marked **[HU]**
are Hungarian legal or institutional names; the rest are general Hungarian
and would serve a Hungarian-language text from anywhere.

### The list

**1 Abortion.** Tier 1: `abortusz*`, `terhességmegszakítás*`,
`terhesség-megszakítás*`, `magzati élet*` (Act LXXIX of 1992 "a magzati élet
védelméről" [HU]), `magzatvédel*`, `magzati szívhang*` (the 2022 heartbeat
decree [HU]), `fogantatás*` (Fundamental Law Art. II: life protected "from
conception"), `abortusztablett*`, `abortuszpirul*`, `Mifegyne`,
`mifepriszton*`, `életvédő*` (pro-life, the movement's own word). Tier 2:
`magzat*`, `reproduktív jog*`, `reproduktív egészség*`, `babamentő
inkubátor*` [HU], `inkubátor*`, `koraszülött*`, `várandósgondoz*`,
`születendő gyermek*`, `méhen belül*`, `prenatális*`, `magzatdiagnosztik*`.

**2 Assisted dying.** Tier 1: `eutanázi*`, `asszisztált öngyilkosság*`,
`asszisztált halál*`, `orvosi segítséggel történő`, `méltó halál*`,
`önrendelkezés az élet végén`, `életvégi döntés*`, `Karsai Dániel*` (the
2023-24 Constitutional Court and Strasbourg case [HU]). Tier 2:
`palliatív*`, `hospice*`, `életfenntartó kezelés*`, `ellátás
visszautasítás*` (refusal of treatment, Health Act s.20 [HU]),
`öngyilkosság-megelőzés*`, `öngyilkosságmegelőzés*`, `élet végén`,
`haldokló*`.

**3 Gender medicine and children.** Tier 1: `nemátalakító*`, `nemváltó
műtét*`, `nemi átalakít*`, `pubertásblokkol*`, `pubertásgátl*`, `nemi
diszfóri*`, `nemi inkongruenci*`, `detranzíci*`. Tier 2, guarded to
children: `hormonterápi*`, `nemi identitás*`, `tranzíci*`.

**4 Conversion practices.** Tier 1: `konverziós terápi*`, `konverziós
gyakorlat*`, `konverziós kezelés*`, `reparatív terápi*`, `átnevelő terápi*`.
Tier 2: `lelkigondoz*` (pastoral care) guarded with konverziós / tilalom /
szexuális irányultság.

**5 Sex-based rights.** Tier 1: `születési nem*` (sex at birth: the 2020
registry law and the 2025 amendment [HU]), `nem megváltoztatás*`,
`nemváltoztatás*`, `nem módosítás*`, `nemi hovatartozás*`, `biológiai nem*`,
`transznemű*`, `transz személy*`, `interszex*`, `nembinár*`, `nem binár*`,
`genderideológi*`, `gender-ideológi*`, `társadalmi nem*`, `isztambuli
egyezmény*` (Parliament refused ratification in 2020 [HU]), `férfi vagy nő`,
`LMBT*`. Tier 2: `homoszexualit*`, `homoszexuális*`, `szexuális
irányultság*`, `nemi irányultság*`, `irányultság*` guarded, `nemi
identitás*`, `egyenlő bánásmód*`, `Egyenlő Bánásmód Hatóság*` [HU, abolished
2021], `nők elleni erőszak*`, `kapcsolati erőszak*`, `femicid*`,
`nőgyilkosság*`, `női sport*` guarded.

**6 Parental rights and education.** Tier 1: `gyermekvédelmi törvény*` (the
2021 "child protection law", Act LXXIX of 2021 [HU]), `gyermekvédelmi
népszavazás*` (the 2022 referendum [HU]), `pedofilellenes*`, `pedofil
bűnelkövető*` (the 2021 law's own title [HU]), `szexuális nevelés*`,
`szexuális felvilágosítás*`, `érzékenyítő*`, `érzékenyítés*` (the
"sensitisation" programmes the 2021 law restricts in schools), `szülői
jog*`, `szülők joga*`, `nevelési jog*`, `otthonoktatás*`, `magántanuló*`,
`egyéni munkarend*` (home-education status [HU]), `testi, szellemi és
erkölcsi fejlődés*` and `megfelelő testi, szellemi` (the 2025 amendment's
words [HU]), `Pride*`. Tier 2: `gyermekvédel*`, `Nemzeti alaptanterv*` and
`NAT` (national curriculum [HU]), `tankönyv*`, `hit- és erkölcstan*` [HU],
`köznevelés*`, `közösségi média*` guarded to children, `mobiltelefon*`
guarded to school, `digitális eszköz*` guarded to children,
`korhatár-ellenőrzés*`, `életkor-ellenőrzés*`, `életkor-ellenőrző*`,
`kiskorúak védel*`, `gyermekek védel*`, `gyermekjog*`, `tankötelezettség*`.

**7 Free speech, privacy and civil liberties.** Tier 1: `szólásszabadság*`,
`véleménynyilvánítás szabadság*`, `véleménynyilvánítási szabadság*`,
`sajtószabadság*`, `gyűlöletbeszéd*`, `gyűlöletkelt*`, `közösség elleni
uszítás*` (Criminal Code s.332 [HU]), `rémhírterjesztés*` (scaremongering
offence [HU]), `Szuverenitásvédelmi Hivatal*` and `szuverenitásvédel*` (the
2023 Sovereignty Protection Act and Office [HU]), `közélet átláthatóság*`
(the 2025 foreign-funding bill [HU]), `külföldről támogatott szervezet*` (the
2017 NGO law [HU]), `cenzúr*`, `Pegasus*`, `kémprogram*`, `gyülekezési
jog*`, `gyülekezési törvény*`, `gyülekezési szabadság*` (the Pride ban runs
through the Assembly Act [HU]), `arcfelismer*` (facial recognition, used
against Pride attendees), `digitális szolgáltatásokról szóló`, `DSA`. Tier
2: `dezinformáci*`, `álhír*`, `gyűlöletbűncselekmény*`,
`gyűlölet-bűncselekmény*`, `megfigyel*`, `adatvédel*`, `titkos
információgyűjtés*`, `médiaszabályoz*`, `médiaszolgáltatás*`, `közmédia*`,
`Médiatanács*` and `NMHH` [HU], `politikai reklám*`, `platformszolgáltató*`,
`online platform*`, `chatkontroll*`, `külföldi befolyás*`, `külföldi
támogatás*`, `civil szervezet*`.

**8 Freedom of religion or belief.** Tier 1: `vallásszabadság*`,
`lelkiismereti és vallásszabadság*`, `lelkiismereti szabadság*`, `egyházi
törvény*`, `egyháztörvény*` (the 2011 Church Act [HU]), `bevett egyház*`,
`elismert egyház*`, `nyilvántartásba vett egyház*` (its tiers of
recognition [HU]), `keresztényüldözés*`, `üldözött keresztény*`,
`keresztények üldözés*`, `Hungary Helps` (the state programme for persecuted
Christians [HU]), `istenkáromlás*`, `vallási közösség*`, `vallási
kisebbség*`, `keresztény kisebbség*`. Tier 2: `egyházi*`, `egyház*`,
`hitoktatás*`, `hitélet*`, `vallási jelkép*`, `keresztény kultúr*` (the 2018
amendment's "Christian culture" [HU]), `zsidó közösség*`, `antiszemitizmus*`,
`iszlám*`, `muszlim*`, `lelkész*`.

**9 Marriage and family.** Tier 1: `házasság*`, `egy férfi és egy nő`
(Fundamental Law Art. L [HU]), `anya nő, az apa férfi` (2020 amendment
[HU]), `élettársi kapcsolat*`, `bejegyzett élettárs*` (registered
partnership [HU]), `azonos nemű*`, `örökbefogad*` (adoption, restricted to
married couples in 2020), `családtámogatás*`, `családpolitik*`,
`családvédel*`, `Családvédelmi Akcióterv*` [HU], `babaváró*` [HU], `CSOK`
and `családi otthonteremtési kedvezmény*` [HU], `családi adókedvezmény*`,
`gyermekgondozási díj*`, `GYED`, `GYES` [HU], `gyermeknevelési támogatás*`,
`családi pótlék*`. Tier 2: `családok*`, `családi*`, `családügy*`,
`családbarát*`, `sokgyermekes*`, `nagycsalád*`, `demográfi*`,
`népességfogy*`, `gyermekvállalás*`, `édesanyá*`, `anyák*`, `szülési
szabadság*`, `apasági szabadság*`, `gyermekgondozás*`, `gyermektartás*`,
`szülői felügyelet*`, `válás*`, `kapcsolattartás*`.

**10 Surrogacy and embryology.** Tier 1: `béranyaság*`, `dajkaterhesség*`,
`helyettesítő anyaság*`, `embrió*`, `lombik*` (IVF, colloquial; the state
took the clinics over in 2019 [HU]), `mesterséges megtermékenyítés*`,
`asszisztált reprodukci*`, `reprodukciós eljárás*`, `humán reprodukci*`,
`petesejt*`, `ivarsejt*`, `spermadonáci*`, `őssejt*`, `klónoz*`,
`génszerkeszt*`, `méhen kívüli megtermékenyítés*`, `IVF`. Tier 2:
`meddőség*`, `termékenység*`, `reprodukciós*`, `Humánreprodukciós*` (the
National Human Reproduction Institute [HU]).

**11 Migration.** Tier 1: `migráci*`, `migráns*`, `bevándorl*`,
`menedékjog*`, `menekült*`, `határzár*`, `tranzitzón*` [HU],
`illegális határátlép*`, `migrációs paktum*`, `embercsempész*`,
`kitoloncol*`, `kiutasít*`. Tier 2: `vendégmunkás*` (guest workers, a live
term-43 fight), `harmadik országbeli*`, `idegenrendészet*`, `Országos
Idegenrendészeti*` [HU], `tartózkodási engedély*`, `letelepedés*`,
`határvédel*`, `határőrizet*`, `kvót*` guarded, `áttelepítés*`.

**12 Prostitution, trafficking and sexual exploitation.** Tier 1:
`prostitúci*`, `prostituált*`, `emberkereskedelem*`, `emberkereskedő*`,
`kéjelgés*` [HU offence], `szexmunk*`, `szexuális kizsákmányol*`,
`gyermekpornográf*`, `gyermekek szexuális*`, `szexuális bántalmaz*`. Tier 2:
`pornográf*`, `pedofil*`, `szexuális visszaélés*`, `szexuális erőszak*`,
`szexuális zaklatás*`, `kényszermunk*`, `Nemzeti Koordinátor az
emberkereskedelem*` [HU]. NOT used: `kerítés` (pimping, but also "fence")
and `futtatás` (pimping, but also "running").

**13 Organ donation.** Tier 1: `szervadományoz*`, `szervátültet*`,
`szervdonáci*`, `szervdonor*`, `transzplantáci*`, `feltételezett
beleegyezés*` (presumed consent, Hungary's system), `agyhalál*`,
`szervkereskedelem*`, `szerv- és szövetátültet*`. Tier 2:
`szövetadományoz*`, `donor*`, `halott ember szerv*`.

**Global exclusions:** `nem`, `család`, `élet`, `gyermek`, `jog`, `egyház`,
`védelem`.

## Shared files touched

**None.** No collector was built, so `src/db.py`, `tools/coverage.py`,
`.github/workflows/alert.yml` and every other shared file are untouched.
The only new file is this one. When Phase 1 is built it will need, as for
Australia: `db.TABLES` and `db.init_db` (the `hu_*` tables),
`tools/coverage.py` (`PIPELINES`, `FEEDS`, `PIPELINE_FEEDS`,
`AWAITING_FIRST_RUN`), and the `alert.yml` workflow list.

One action outside this branch: `probe-hosts.yml` was dispatched once on
`main` (run 37881481912, read-only, no commit) to ask parlament.hu from a
runner IP. The raw probe archive is local to this worktree
(`data/raw/hu-probe-2026-10-09/`, git-ignored as all of `data/raw` is): the
CAPTCHA page and headers, the gazette RSS, one gazette PDF, the contents
extracts of 55 issues, the Wikidata member query and the measuring copy of
the term list.

## Waiting on Chris

1. **The W-API token.** Register by email to `api-reg2@parlament.hu`
   (address from karzat's `.env.example`; parlament.hu's own page could not
   be read to confirm it). The token is personal and every request is
   logged by the Office of the National Assembly. **Whose name it is in is
   your call**: CitizenGO is a known actor in Hungary, and the registration
   says who is reading. Once it arrives, it goes in `~/runner/env` on the
   Mini and as an Actions secret, never in the repo.
2. **Whether the token gets through the CAPTCHA wall** is unknown until
   tried. If it does not, the fallback is to write to the Office (OGYH IT)
   asking for the API path to be exempted for our User-Agent; that is a
   message in your name, so it waits for you.
3. **Approve the term list above**, ideally after a Hungarian reader has
   looked at it (does CitizenGO have one?). Specific calls:
   - family benefits (CSOK, babaváró, GYED, GYES, the mothers' tax
     exemption) at tier 1 in area 9, or tier 2?
   - the child-welfare system (`gyermekvédel*`, 8 papers in term 43): in at
     tier 2 as drafted, or out?
   - the Pride and assembly-ban terms: area 6 (children) as drafted for
     `Pride*`, area 7 (assembly) for the Assembly Act, or both?
   - civil-society and foreign-funding laws (Sovereignty Protection Office,
     the 2025 transparency bill) in area 7 as drafted?
4. **Constitutional amendments: approve the rule** that every paper titled
   "Magyarország Alaptörvényének ..." is triaged at minimum score 2 and read
   in full.
5. **Interpellation votes:** count the vote on accepting a minister's reply
   as a division on our ground when the interpellation is? Of the 17
   measured votes on our ground, 10 are interpellation votes; the other 7
   are on bills, resolutions and reports.
6. **Phase 0:** build the keyless gazette collector now, or wait for the
   token? Recommendation: wait two weeks for the token first.
7. **karzat's derived data (CC BY 4.0):** may it be used to backfill term
   43 from 9 May to the token's first run, with attribution? The record
   underneath is the House's own.

## Decisions of 10 October 2026 (applied at the countries merge)

Recorded in `docs/country-decisions-2026-10-10.md`. Shared: accents fold and non-ASCII letters are word characters in the filter (X3); member positions are stored for every vote (X15); the AI judge stays off (X16).

Applied on the `countries` branch:

- Term list approved (HU3, HU4 constitutional amendments always triaged, HU5 interpellation votes count); `config/taxonomy-hu.yaml` generated, ready for the collector.

Later phases and items for Chris (not built at the merge):

- Phase: the gazette collector (HU6, build now). **Built 10 October 2026, branch `hu-gazette`**: see "Phase 0, as built" below.
- W-API token registration (HU1, name to confirm) and a letter to the Office if the CAPTCHA persists (HU2): Chris. The CAPTCHA is never solved or bypassed.
- karzat's CC BY data with attribution (HU7) when the collector is written.
- Member profiles (handover item 3, built 10 October 2026, branch `parity-profiles`): `profiles/hu/` from the store each weekly run (`tools/member_profiles.py hu`, src/member_profiles.py): party, chamber, constituency, every recorded position on a vote on our ground as the edition classifies it, verbatim, with the basis of the party at the vote; no verdicts, no DM. Votes come from karzat (9 May to 28 August 2026), with its attribution.

## Phase 0, as built (10 October 2026, branch `hu-gazette`)

- **Collector:** `tools/hu_gazette.py`, tables `hu_gazette_issues` and
  `hu_gazette_entries` (`src/hu_store.py`, declared in `db.TABLES`). Reads
  the RSS feed (Magyar Közlöny issues only, by `mag:type`), and on the first
  run walks the front-page listing (`magyarkozlony.hu?page=N`, ten journals
  a page) back to the start of the term, 9 May 2026, because the feed holds
  only about eleven weeks. Each new issue's PDF is fetched once (one request
  every 2 s, the repo's UA), archived to `data/raw/<date>/hu-gazette_*`, and
  its contents page read with the stdlib reader `src/sv_pdf.py`, extended
  for InDesign PDFs (nested resource dictionaries, a bare CR before
  `endstream`, the Hungarian ő and ű in a font's own `/Differences`).
- **Keys:** the official designation, verbatim ("2026. évi LVI. törvény",
  "62/2026. (IX. 22.) OGY határozat"); an amendment to the Fundamental Law
  is its heading with its date; the consolidated text of the Fundamental
  Law, which recurs, is keyed on its issue.
- **Classification:** taxonomy-hu on the Hungarian TITLE only (accents fold,
  X3). The designation is left out because "NMHH rendelet" would file every
  telecoms decree. **HU4 applied:** an amendment is stored with rule `HU4`
  and shown as watched whatever its words. **A taxonomy fix for Chris:**
  with accents folded, `válás*` (divorce) matches "választás" (election);
  both of its hits in the term's gazette were elections. **Fixed at the
  source, 10 October 2026 (taxonomy-hu v0.2, branch `hu-karzat`):**
  `válás*` is replaced by its explicit forms (válás, válást, válási*,
  válásá*, válások*, válásr*, ...), none of which folds to "valasz", so
  neither "választás" (election) nor "válasz"/"választ" (answer, the word in
  every interpellation-answer vote) matches; a veto on `választ*` would have
  missed "válasz". The collector's `FALSE_FRIENDS` guard is gone. Measured
  on the backfill: the two election entries stay off area 9, nothing else
  changed, and the divorce forms still match.
- **Backfill measured** (laptop, 9 October 2026, scratch store, not
  published; the Mini's first scheduled run makes the real one): 108
  issues from No. 44 of 9 May to No. 151 of 9 October, 736 contents
  entries, every contents page read (after three layout fixes: the title's
  first letter left of the tab, a page number without its tab, the
  consolidated Fundamental Law). By type: 171 government resolutions, 153
  presidential (KE) decisions, 117 ministerial decrees, 110 government
  decrees, 61 Prime Minister's decisions, 55 OGY resolutions, 47 Acts, 5 AB
  decisions, 2 amendments to the Fundamental Law (the sixteenth, 15 June,
  paper T/51; the seventeenth, 13 July, paper T/324), 15 others. 41 on our
  ground (2 under HU4). Of those the edition would show 31 over the term:
  migration items are stored but never shown, appointments (KE, ME) are
  left out, and the noise rules drop 3 telecoms decrees.
- **Edition:** `src/editions/hu.py` ("Laws" and "Gazette notices", the
  Hungarian title verbatim, an English takeaway built from the designation
  and the title's legal formula, never a model), the standing notice that
  bills and votes await the token, `config/edition-noise-hu.yaml`,
  `config/edition-mute-hu.yaml`, `config/watchlist-hu.yaml` (the two
  amendments, Acts XX and XXIV of 2026, and the term's known papers for
  phase 1). DM to Chris alone. Sample: `editions/hu-monitor-2026-10-09.md`.
- **Schedule:** `hu-weekly`, Wednesdays 03:00 London on the Mini; GitHub
  backup Wednesdays 03:00 and 05:00 UTC, gated by `mini-check` with
  `HU_WEEKLY` (docs/mac-mini.md).

## HU7: karzat's data, how it would be loaded (the plan; built, see below)

karzat publishes a downloadable open dataset: its derived tables are files
in its GitHub repository, `data/derived/` (licensed CC BY 4.0 there; code
MIT), among them `votes_index.json` (every vote), `votes_positions.json`
(positions by member), `iromany_records.json` (papers), `mps.json`
(members) and `committees.json`, plus per-vote CSV and JSON on its site
(down on 9 October). Loading them reads only those files from GitHub, never
parlament.hu. When phase 1 is built:

- A one-off `tools/hu_karzat_backfill.py`, run as a Mini backfill job,
  reads those files at a pinned commit, keeps term 43 (from 9 May 2026 to
  the data's end, 28 August 2026) and writes `hu_members`, `hu_papers`,
  `hu_divisions` and `hu_votes`, keyed exactly as the W-API would (paper
  number, vote timestamp), with `source = 'karzat@<commit>'` on every row.
- The W-API's first run overwrites any karzat row it also returns: the
  House's record wins; karzat fills only the gap before the token.
- Attribution, wherever such a row is shown: "Votes before <date> from
  karzat (github.com/abognar-git/karzat), CC BY 4.0, derived from the
  Országgyűlés's record", in the edition's Coverage and in the store's
  provenance.
- Karzat's own caveat stands: the underlying record conveys no rights,
  which is why it is a bridge to our own token, not a substitute.

## HU7, as built (10 October 2026, branch `hu-karzat`)

- **Loader:** `tools/hu_karzat_backfill.py`, run by hand on the Mac Mini
  through `jobs/hu-karzat-backfill.sh` (docs/mac-mini.md; no plist, no
  workflow: the source is static). It asks the GitHub API for karzat's
  newest commit touching `data/derived/` (or takes `KARZAT_COMMIT`), reads
  `votes_index.json`, `votes_positions.json`, `iromany_records.json` and
  `mps.json` at that commit from raw.githubusercontent.com through
  `src/http.py`, archives them, and loads the term from 9 May 2026. Never
  parlament.hu, never karzat's site.
- **Tables** (`src/hu_store.py`, declared in `db.TABLES`): `hu_members`
  (p_azon), `hu_papers` (paper number, 'T/324'), `hu_divisions` (the vote's
  timestamp, '2026.07.13.18:19:08', as the W-API keys it), `hu_votes`
  (vote, member: the record's own position and the group at the vote),
  `hu_sources` (one row per load: commit, licence, attribution, window,
  counts). Every row has `source = 'karzat@<commit>'` and `as_of`. A vote's
  motion ('324/14', the consolidated text) is joined to its paper by the
  paper's number in the term, never by title. karzat's positions name
  members by p_azon (201 of 201 checked against `mps.json`). Upserts only,
  so a rerun (or a karzat update) is safe; a row from any other source
  (the W-API, later) is never overwritten.
- **Rules:** taxonomy-hu on the paper's title; a vote takes its paper's
  areas. HU4: every paper titled "Magyarország Alaptörvényének ...
  módosítása", and every vote on it, carries `rule = 'HU4'` and is shown
  whatever its words. HU5: a vote on accepting a minister's answer to an
  interpellation carries `rule = 'HU5'` and counts, on our ground when the
  interpellation is. Procedural votes (urgency, the exceptional procedure,
  departures from the standing orders, hearing an out-of-scope amendment)
  are left out by `config/edition-noise-hu.yaml` unless watched or HU4.
- **Attribution (CC BY 4.0):** "Votes, papers and members before the
  parliament's own feed from karzat (github.com/abognar-git/karzat, open
  data under CC BY 4.0), derived from the Országgyűlés's record", in
  `hu_sources`; a line on every karzat-derived item in an edition, the full
  attribution with the data's date and commit under Coverage whenever such
  an item is shown, and in the standing notice and the DM's second line
  while karzat's rows are in the store.
- **Edition:** "Recorded votes" (tally, the majority needed, the record's
  words for the motion and result, the split by group at the vote, members
  against their group's majority; a bill's amendments and final vote as one
  group), "New on our ground" (bills, resolutions, reports) and "Questions"
  (interpellations, written and urgent questions), each only in the week of
  its own date: after 28 August the weekly editions carry the gazette
  alone. The one-off read, "since 9 May", is
  `tools/hu_karzat_backfill.py --summary`; the Mini job writes it to
  `editions/hu-karzat-backfill.md`.
- **Measured** (laptop, 10 October 2026, commit 4f932a3a0513 of 3 September
  2026, into a scratch copy of the gazette backfill store; not published):
  201 members, 586 papers (71 bills), 272 votes from 9 May to 28 August
  2026 (266 by name, 5 secret ballots, 1 quorum call), 53,084 positions,
  every member code placed and every motion joined to its paper. On our
  ground: 65 papers and 48 votes (8 under HU4, 12 interpellation answers
  under HU5; migration included, which is stored but not shown). The
  summary shows 43 votes, 18 bills and resolutions and 33 questions; 3
  procedural votes are left out.
- **Cross-checked against the gazette:** all 54 promulgated bills and
  resolutions agree with the gazette store (issue, date, and the Act's
  designation where karzat gives one). The two amendments: the sixteenth,
  T/51, passed 15 June 2026 by 135 to 50 with 6 abstaining (two-thirds of
  all MPs needed, 133), promulgated in No. 74 of 19 June, whose heading is
  dated 15 June; the seventeenth, T/324, passed 13 July 2026 by 139 to 6
  (motion 324/14, Fidesz and KDNP not voting), promulgated in No. 92 of 18
  July, heading dated 13 July. Acts XX (T/122, passed 23 June, published 26
  June) and XXIV (T/123, 30 June, 30 June) agree too. The watchlist's
  earlier "promulgated 15 June" and "13 July" were the vote dates, now
  corrected.

## 5CA and stance sign-off (built 10 October 2026, branch `parity-5ca`)

Phase list: **done** (docs/5ca-notes.md, "The new country editions"). `config/hu_stance.yaml` holds 2 bill direction(s) (Claude's drafts from the watchlist) and 24 vote reading(s): 2 with proposed values, 1 procedural, 21 need reading, 0 confirmed. Guide: `docs/5ca-hu-readings.md`; confirm with `python3 tools/country_5ca.py --cc hu --sign-from-doc --by NAME`. Sheets (`data/5ca/hu-5ca-*.csv`) appear only once a reading is confirmed. Waiting on Chris: who signs for Hungary (`config/stance_signers.yaml`). karzat records only (9 May to 28 August 2026) until the W-API token arrives; members are matched by name.
