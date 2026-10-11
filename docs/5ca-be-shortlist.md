# Belgium 5CA: sign these first

Written by `tools/country_5ca.py --shortlist` (src/shortlist5ca.py) on 2026-10-11, by rules, no AI call. **This list confirms nothing.** It ranks the 4 readings waiting in `config/be_stance.yaml` (3 proposed, 0 procedural, 1 need reading) so a signer starts with the votes that matter most: the decisive votes on watched bills, close margins, split groups, votes with a meaning line, votes feeding a campaign or a brief, recent first; procedural, near-unanimous and amendment-level votes sink. Read each item (the full reading is in `docs/5ca-be-readings.md`), then run its command. The full rules are at the end.

The commands sign as **Christopher** (no country signer is named yet; replace the name with whoever signs). `--confirm` refuses anyone not named in `config/stance_signers.yaml` (Chris signs for every country) and any reading that still needs reading.

**All the proposed ones below in one go**, once each is read and agreed (leave out any you do not accept):

    python3 tools/country_5ca.py --cc be --confirm 56/143/5 56/131/27 56/95/21 --by Christopher

## Top 4

### 1. `56/143/5` Geheel van het wetsvoorstel tot flexibilisering van de periode van rouwverlof in geval van geplande euthanasie en van de periode van palliat

- **Why first (90 points):** a vote on the whole text; the last such vote on its bill; watched bill 56/1338; values proposed: one tick to sign; near-unanimous (134-0, lower); meaning line ready; feeds brief be-wetsontwerp-tot-flexibilisering-van-de-periode-v-56-1338 (NOT READY until signed); recent.
- **When / result:** 2026-10-08; Kamer; adopted; Ja / Oui 134, Nee / Non 0, Abstain 1
- **On:** Wetsvoorstel tot flexibilisering van de periode van rouwverlof in geval van geplande euthanasie en van de periode van palliatief verlof.
- **Area:** assisted dying
- **Lobbies:** Ja / Oui: N-VA 22, VB 18, PS 14, MR 14, PVDA-PTB 14, Les Engagés 13, Vooruit 12, Ecolo-Groen 9, cd&v 9, Anders. 7, DéFI 1, INDEP 1. Abstain: PS 1
- Meaning: **Ja / Oui** = to pass 56/1338 (Bereavement leave around 'planned euthanasia' (and palliative leave)) as a whole; **Nee / Non** = against passing it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Ja / Oui -2, Nee / Non +2
  - Voted Ja / Oui on 56/1338 (Bereavement leave around 'planned euthanasia' (and palliative leave)): for passing it, against CitizenGO's position.
- **Flag:** On the bill's direction: Adopted 134-0-1: a near-unanimous vote tells few members apart.
- **Sign:** `python3 tools/country_5ca.py --cc be --confirm 56/143/5 --by Christopher`

### 2. `56/131/27` Voorstel tot verwerping door de commissie voor Justitie van het wetsvoorstel tot wijziging van de regelgeving met betrekking tot de vrijwill

- **Why first (85 points):** a motion to reject the text; the last such vote on its bill; watched bill 56/40; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2026-06-25; Kamer; adopted; Ja / Oui 93, Nee / Non 37
- **On:** Ontwerp tot wijziging van de regelgeving met betrekking tot de vrijwillige zwangerschapsafbreking.
- **Area:** abortion
- **Lobbies:** Ja / Oui: N-VA 23, VB 17, MR 15, Les Engagés 14, Vooruit 12, cd&v 11, ? 1. Nee / Non: PS 11, PVDA-PTB 11, Ecolo-Groen 8, Anders. 6, DéFI 1
- Meaning: **Ja / Oui** = to reject 56/40 (Bill amending the abortion rules) outright at this stage (a motion to reject); **Nee / Non** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Ja / Oui +2, Nee / Non -2
  - Voted Ja / Oui on 56/40 (Bill amending the abortion rules): for rejecting it, with CitizenGO's position.
- **Sign:** `python3 tools/country_5ca.py --cc be --confirm 56/131/27 --by Christopher`

### 3. `56/95/21` Voorstel tot verwerping door de commissie voor Binnenlandse Zaken, Veiligheid, Migratie en Bestuurszaken van het wetsvoorstel betreffende de

- **Why first (85 points):** a motion to reject the text; the last such vote on its bill; watched bill 56/149; values proposed: one tick to sign; meaning line ready; this year.
- **When / result:** 2026-02-26; Kamer; adopted; Ja / Oui 92, Nee / Non 37, Abstain 3
- **On:** Wetsvoorstel betreffende de objectieve neutraliteit van de personeelsleden van het federaal openbaar ambt, waarbij het hun verboden is bij de uitoefening van hun ambt zichtbare tekens van een geloofs-
- **Area:** religious freedom, migration
- **Lobbies:** Ja / Oui: N-VA 23, Les Engagés 14, MR 13, Vooruit 11, PVDA-PTB 11, cd&v 10, Ecolo-Groen 9, ? 1. Nee / Non: VB 18, PS 13, Anders. 5, DéFI 1. Abstain: MR 1, Anders. 1, ? 1
- Meaning: **Ja / Oui** = to reject 56/149 (Ban on visible religious or philosophical symbols (signes convictionnels) for federal civil servants) outright at this stage (a motion to reject); **Nee / Non** = against rejecting it, so it goes on. _(by rule, from the vote's wording and the bill)_
- **Proposed:** Ja / Oui +2, Nee / Non -2
  - Voted Ja / Oui on 56/149 (Ban on visible religious or philosophical symbols (signes convictionnels) for federal civi): for rejecting it, with CitizenGO's position.
- **Flag:** On the bill's direction: Read as against: a ban on religious symbols reaches Christians too (area 8, religious freedom). CitizenGO supports Portugal's face-covering law (PT4), a different question: confirm.
- **Sign:** `python3 tools/country_5ca.py --cc be --confirm 56/95/21 --by Christopher`

### 4. `56/143/4` Aangehouden amendement en artikel van het wetsvoorstel tot flexibilisering van de periode van rouwverlof in geval van geplande euthanasie en

- **Why first (52 points):** amendment-level (lower); watched bill 56/1338; contested: 55-75; split MR (3 against their group); meaning line ready; feeds brief be-wetsontwerp-tot-flexibilisering-van-de-periode-v-56-1338 (NOT READY until signed); recent.
- **When / result:** 2026-10-08; Kamer; rejected; Ja / Oui 55, Nee / Non 75, Abstain 5
- **On:** Wetsvoorstel tot flexibilisering van de periode van rouwverlof in geval van geplande euthanasie en van de periode van palliatief verlof.
- **Area:** assisted dying
- **Lobbies:** Ja / Oui: VB 18, PVDA-PTB 14, PS 11, Ecolo-Groen 8, MR 3, DéFI 1. Nee / Non: N-VA 22, Les Engagés 13, Vooruit 12, MR 11, cd&v 9, Anders. 7, INDEP 1. Abstain: PS 4, Ecolo-Groen 1
- Meaning: **Ja / Oui** = to adopt the amendment and article held over from the earlier vote to 56/1338 (Bereavement leave around 'planned euthanasia' (and palliative leave)); **Nee / Non** = against adopting it. _(by rule, from the vote's wording and the bill)_
- **Proposed:** nothing: An amendment, an article or one point ('Aangehouden amendement en artikel van het wetsvoorstel tot flexibilisering van de periode van rouwverlof in geval van ge'): which side is ours depends on its text, which the store does not hold. Read it, then write yea/n
- **Sign:** first write `yea:`/`nay:` and the why lines (or `placeable: false` and a `reason:`) under `56/143/4` in config/be_stance.yaml and set `status: draft`, then `python3 tools/country_5ca.py --cc be --confirm 56/143/4 --by Christopher`

## By area (rank in the whole list)

- **abortion** (1 waiting): #2 `56/131/27` 2026-06-25, 85 pts
- **assisted dying** (2 waiting): #1 `56/143/5` 2026-10-08, 90 pts; #4 `56/143/4` 2026-10-08, 52 pts
- **religious freedom** (1 waiting): #3 `56/95/21` 2026-02-26, 85 pts
- **migration** (1 waiting): #3 `56/95/21` 2026-02-26, 85 pts

## How the points work

Kind of vote: whole text +30, motion to reject or inverted +25, amendment or article -10, procedure -30; the last such vote on its bill +10. Watched bill +15 (else tier 1 +5). Values already proposed +15. Margin within 5% +20, 10% +14, 20% +8; near-unanimous (smaller side under 5%) -15. Split groups +3 each (at most +15) and +1 per two members against their group (at most +10). Meaning line ready +10 (quoting the source +3). A campaign outcome +25, on a campaign's ground +10, feeding a brief +10. Within 90 days +15, a year +10, two years +5. Collated-only areas -100 (last: they place nobody). Ties: newer first.

