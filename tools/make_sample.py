"""Build a FABRICATED, fully-populated sample edition to preview the format.

Every line is illustrative and prefixed "(example)"; a SAMPLE banner is prepended.
Rendered through the real src/digest.py so the layout is authentic.
"""

import os
import sys

ROOT = "/Users/chrisjoyce/Downloads/Parliamenary Monitor"
sys.path.insert(0, ROOT)

from src import board, digest

L = digest.Line


def row(bill_id, title, house, stage, nkd, status, transition, areas, note=None, why=None):
    return board.BoardRow(bill_id, title, None, house, stage, nkd, status, transition,
                          closed_note=note, areas=areas, why=why)


e = digest.Edition(week_commencing="2026-09-14", number=6, mode="normal")

e.top_lines = [
    L("(example) Lords committee day 4 on the assisted dying bill Thursday; coercion-safeguard amendments expected. Supporter email primed for the outcome.", "ACT", owner="Christopher"),
    L("(example) Conversion Practices Bill gets its second reading Tuesday; drafting covers gender identity, a live risk to exploratory therapy and parental consent.", "ACT", owner="Maria"),
    L("(example) RSE statutory guidance consultation closes in 9 days; evidence submission in final review.", "WATCH"),
    L("(example) Home Office still gives no commencement date for revised safe-access-zone guidance; the delay itself is the story.", "NOTE"),
]

e.board_rows = [
    row(4157, "Terminally Ill Adults (End of Life) Bill", "Lords", "Committee", "2026-09-17", "live", board.MOVED, "2",
        why="(example) The assisted suicide bill; our core opposition priority"),
    row(4901, "Conversion Practices Bill", "Commons", "2nd reading", "2026-09-22", "live", board.NEW, "4,3,8",
        why="(example) Ban drafted to cover gender identity; therapy and parental freedom risk"),
    row(4178, "Hospice Funding Bill", "Commons", "2nd reading", "2026-11-27", "live", board.UNCHANGED, "2",
        why="(example) Palliative care funding; the positive alternative"),
    row(4171, "Relationships and Sex Education (FE Sector) Bill", "Commons", "2nd reading", "2026-12-04", "live", board.UNCHANGED, "6",
        why="(example) Extends RSE rules into further education"),
    row(4144, "Complications from Abortions (Annual Report) Bill [HL]", "Lords", "2nd reading", digest.TBA, "live", board.UNCHANGED, "1",
        why="(example) Abortion complications transparency; we back it"),
    row(3938, "Crime and Policing Act 2026", "Unassigned", "Royal Assent", "-", "closed", board.ROYAL_ASSENT, "1", note="Royal Assent 2026-05-11",
        why="(example) Carried abortion decriminalisation; implementation watch"),
]

e.week_ahead = [
    L("(example) 11.30am, Commons chamber. Justice oral questions: family court and parental involvement likely.", "NOTE", date="2026-09-15"),
    L("(example) 2.30pm, Women and Equalities Committee. Oral evidence: single-sex services guidance; EHRC witnesses.", "WATCH", url="https://committees.parliament.uk/event/EXAMPLE", date="2026-09-15"),
    L("(example) 9.30am, Commons. Conversion Practices Bill: second reading debate.", "ACT", owner="Maria", url="https://bills.parliament.uk/bills/EXAMPLE", date="2026-09-16"),
    L("(example) From 11am, Lords chamber. Terminally Ill Adults Bill, committee day 4: coercion-safeguard amendments.", "ACT", owner="Christopher", url="https://bills.parliament.uk/bills/4157", date="2026-09-17"),
    L("(example) 1.00pm, Westminster Hall. e-petition debate on surrogacy law reform.", "NOTE", date="2026-09-17"),
]

e.votes = [
    L("(example) Tabled: amendment 42 to the Conversion Practices Bill adding an explicit parental-conversation carve-out. Signatory count updating daily.", "WATCH", url="https://bills.parliament.uk/EXAMPLE"),
    L("(example) Last week: Lords amendment 7 to restore in-person consultation for abortion pills, agreed 214-188. 12 watched peers switched.", "WATCH", url="https://lordsvotes-api.parliament.uk/EXAMPLE"),
]

e.pqs = [
    L("(example) Abortion: safe access zones, answered 2026-09-10. Home Office gives no commencement date for revised enforcement guidance.", "NOTE", url="https://questions-statements.parliament.uk/written-questions/detail/2026-09-01/HL2262"),
    L("(example) Gender identity services: waiting lists, answered 2026-09-09. DHSC confirms private-prescription route remains under review.", "WATCH", url="https://questions-statements.parliament.uk/EXAMPLE"),
    L("(example) Hospices: funding, answered 2026-09-09. No multi-year settlement; sector warns of closures.", "NOTE", url="https://questions-statements.parliament.uk/EXAMPLE"),
    L("(example) Online Safety Act: age assurance, answered 2026-09-08. Ofcom timetable slips to 2027.", "WATCH", url="https://questions-statements.parliament.uk/EXAMPLE"),
    L("(example) Surrogacy: Law Commission response, answered 2026-09-08. Government still to publish its response.", "WATCH", url="https://questions-statements.parliament.uk/EXAMPLE"),
]

e.committee = [
    L("(example) Health and Social Care Committee: palliative care inquiry, written evidence closes 2026-10-03. Submission drafted, needs sign-off.", "ACT", owner="Christopher", deadline="2026-10-03"),
    L("(example) Women and Equalities Committee: single-sex spaces inquiry, call for evidence open.", "WATCH", deadline="2026-10-17"),
]

e.consultations_si = [
    L("(example) DfE: RSE statutory guidance, closes 2026-09-23 (9 days). Supporter-response campaign live; 3,120 responses.", "ACT", owner="Christopher", deadline="2026-09-23"),
    L("(example) SEND reform: education otherwise than at school, closes 2026-09-18.", "WATCH", deadline="2026-09-18"),
    L("(example) SI laid: The Abortion (Safe Access Zones) Regulations, negative procedure, prayer deadline 2026-10-01.", "WATCH", deadline="2026-10-01"),
]

e.edms = [
    L("(example) EDM 603 (Antoniazzi): foetal viability and the 24-week limit, 6 signatures (+2 this week).", "NOTE", url="https://edm.parliament.uk/early-day-motion/603"),
    L("(example) EDM 536: single-sex wards in NHS hospitals, 41 signatures (+9).", "NOTE", url="https://edm.parliament.uk/early-day-motion/536"),
    L("(example) EDM 342: protection of freedom of religion for street preachers, 28 signatures (+3).", "NOTE", url="https://edm.parliament.uk/early-day-motion/342"),
]

e.devolved = [
    L("(example) Holyrood, Tuesday: members' debate on hospice funding in Scotland.", "WATCH", date="2026-09-15"),
    L("(example) Senedd: petition on parental rights in RSE reaches committee, 5,400 signatures.", "NOTE"),
]

e.statements = [
    L("(example) WMS, DHSC: Cass Review implementation update. Confirms private-prescription route remains under review.", "WATCH"),
    L("(example) WMS, MoJ: Tying the Knot weddings-law reform, government response timetable.", "NOTE"),
]

e.mp_notes = [
    L("(example) Baroness Grey-Thompson (Crossbench) spoke against broadening eligibility at Lords committee, citing coercion evidence. 5CA input flagged.", "NOTE"),
    L("(example) Danny Kruger (Con, East Wiltshire) led the Conversion Practices Bill opposition, parental-consent focus. Profile updated.", "NOTE"),
    L("(example) Andrew Snowden (Con, Fylde) tabled PATHWAYS follow-up questions on youth gender services.", "NOTE"),
]

e.gaps = [
    ("pq", "'Cass Review' sweep failed after 3 retries (upstream timeout); re-run scheduled."),
]

markdown = digest.render(e)
banner = ("> **SAMPLE / ILLUSTRATIVE EDITION. FABRICATED DATA.** Every entry below is a "
          "made-up example to preview the full-density format. None of it is real "
          "parliamentary data. Marked with (example) throughout.\n\n")
markdown = markdown.split("\n", 2)
# insert banner after the H1 title + subtitle lines
out = markdown[0] + "\n" + markdown[1] + "\n\n" + banner + markdown[2]

path = os.path.join(ROOT, "docs", "sample-edition.md")
with open(path, "w", encoding="utf-8") as h:
    h.write(out)
print(path)
