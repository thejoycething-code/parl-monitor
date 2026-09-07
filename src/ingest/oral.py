"""Oral statements and Urgent Questions: the minister's line, as a record.

Christopher, 2026-09-07. The Hansard sweep catches speeches that use our
vocabulary; it does not record that a minister stood up to make a
statement, or was summoned to answer an Urgent Question, on our ground.
The Hansard API's section tree for a sitting day tags each section by
kind -- hs_2cStatement for an oral statement, hs_2cUrgentQuestion for a
UQ -- and the debate call returns the contributions in order, so the
opener and the minister's first answer can be kept as the record of the
line taken. Both Houses.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass

API = "https://hansard-api.parliament.uk"
PUBLIC = "https://hansard.parliament.uk/{house}/{date}/debates/{ext}/"
TAGS = {"hs_2cStatement": "Oral statement", "hs_2cUrgentQuestion": "Urgent Question"}
_TAG = re.compile(r"<[^>]+>")
_MINISTER = re.compile(r"Minister|Secretary of State|Under-Secretary|Chancellor|Prime Minister|Attorney General|"
                       r"Solicitor General|Leader of the House|Paymaster|Lord Privy Seal|Advocate General|"
                       r"Parliamentary Secretary|Lord Chancellor", re.I)


@dataclass
class OralItem:
    ext_id: str
    house: str
    date: datetime.date
    title: str
    kind: str                   # Oral statement | Urgent Question
    opener_name: str = None
    opener_text: str = ""
    minister_name: str = None
    minister_text: str = ""

    @property
    def url(self):
        return PUBLIC.format(house=self.house, date=self.date.isoformat(), ext=self.ext_id)

    @property
    def text(self):
        return " ".join(x for x in (self.title, self.opener_text, self.minister_text) if x)


def sections(tree):
    """[(title, tag, ext_id)] for every statement or UQ node in a section tree."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("HRSTag") in TAGS and node.get("ExternalId"):
                out.append((node.get("Title"), node["HRSTag"], node["ExternalId"]))
            for c in node.get("SectionTreeItems") or []:
                walk(c)
        elif isinstance(node, list):
            for c in node:
                walk(c)
    walk(tree)
    return out


def _clean(s, cap=700):
    t = " ".join(_TAG.sub(" ", s or "").split())
    return t if len(t) <= cap else t[:cap].rsplit(" ", 1)[0] + "..."


LORDS_KINDS = {"statement": "Oral statement", "commons urgent question": "Urgent Question",
               "urgent question": "Urgent Question", "private notice question": "Private Notice Question"}


def classify_lords(payload):
    """The Lords tree carries no HRSTag: every item is 'NewDebate'. The debate
    itself says what it is in its first UNATTRIBUTED line -- "Statement",
    "Question", "Commons Urgent Question", "Private Notice Question"
    (measured 2026-09-07). -> kind, or None for anything else."""
    for i in payload.get("Items") or []:
        if i.get("ItemType") != "Contribution" or i.get("AttributedTo"):
            continue
        head = re.sub(r"<[^>]+>", "", i.get("Value") or "").strip().lower()
        if head in LORDS_KINDS:
            return LORDS_KINDS[head]
        if head:
            return None
    return None


def parse_debate(payload, house, date, title, tag, ext_id):
    """The opener and the first ministerial contribution of a section."""
    items = [i for i in (payload.get("Items") or []) if i.get("ItemType") == "Contribution" and i.get("Value")]
    item = OralItem(ext_id=ext_id, house=house, date=date, title=title,
                    kind=TAGS.get(tag) or LORDS_KINDS.get(str(tag).lower()) or tag)
    speakers = [(i.get("AttributedTo") or "", i.get("Value") or "") for i in items if i.get("AttributedTo")]
    speakers = [(n, v) for n, v in speakers if "Speaker" not in n and "Deputy Speaker" not in n and n.strip() != "Mr Speaker"]
    if speakers:
        item.opener_name, item.opener_text = speakers[0][0], _clean(speakers[0][1])
        minister = next(((n, v) for n, v in speakers if _MINISTER.search(n)), None)
        if minister and minister[0] != item.opener_name:
            item.minister_name, item.minister_text = minister[0], _clean(minister[1])
        elif minister:
            # A statement: the minister opens, so the line IS the opener.
            item.minister_name, item.minister_text = item.opener_name, item.opener_text
    return item


def fetch_day(client, house, date):
    """Every oral statement and UQ of one sitting day in one House."""
    out = []
    try:
        names = client.get_json("{0}/overview/sectionsforday.json?house={1}&date={2}".format(API, house, date.isoformat()),
                                "hansard", "sections-{0}-{1}".format(house, date.isoformat()), archive=False)
    except Exception:                                       # noqa: BLE001
        return out
    for sec in names or []:
        if sec not in ("Debate", "GEN"):
            continue
        tree = client.get_json("{0}/overview/sectiontrees.json?section={1}&date={2}&house={3}".format(
            API, sec, date.isoformat(), house), "hansard", "tree-{0}-{1}-{2}".format(house, date.isoformat(), sec), archive=False)
        if house == "Lords":
            # No tags in the Lords: read each chamber item and keep the
            # statements (repeats of Commons statements included) and the
            # urgent and private notice questions.
            for title, tag, ext in lords_sections(tree):
                payload = client.get_json("{0}/debates/debate/{1}.json".format(API, ext), "hansard",
                                          "debate-{0}".format(ext))
                kind = classify_lords(payload)
                if kind:
                    out.append(parse_debate(payload, house, date, title, kind, ext))
            continue
        for title, tag, ext in sections(tree):
            payload = client.get_json("{0}/debates/debate/{1}.json".format(API, ext), "hansard", "debate-{0}".format(ext))
            out.append(parse_debate(payload, house, date, title, tag, ext))
    return out


def lords_sections(tree):
    """[(title, tag, ext_id)] for every chamber item in a Lords tree."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("HRSTag") == "NewDebate" and node.get("ExternalId") and node.get("Title"):
                out.append((node["Title"], node["HRSTag"], node["ExternalId"]))
            for c in node.get("SectionTreeItems") or []:
                walk(c)
        elif isinstance(node, list):
            for c in node:
                walk(c)
    walk(tree)
    return out
