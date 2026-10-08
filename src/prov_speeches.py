"""Provincial Hansard speeches: one engine, one small reader per legislature.

Christopher, 2 October 2026: provincial Hansard speeches, so that the
provincial 5CA sheets get speech evidence, not only votes. The federal
pattern (tools/ca_hansard.py, tools/ca_senate_debates.py) carried over:

  * A DAY (or a part of one: Alberta's afternoon and evening, British
    Columbia's morning and afternoon) is read from the legislature's own
    Hansard index, never from a URL built from a date. Every day READ gets a
    prov_speech_sittings row with its totals whatever it held, so a quiet
    day is never mistaken for one never read, and a run resumes.
  * WHAT A SPEECH IS: a TURN -- a paragraph opening with a speaker label and
    the paragraphs after it up to the next label or heading -- under the
    rubric (Oral Questions, Orders of the Day) and the subject heading it
    sits in. Each province's reader (src/ingest/prov_<code>_hansard.py)
    turns its markup into turns; everything below is shared.
  * THE CHAIR AND THE COLLECTIVE LABELS (The Speaker, Le Président, Mr.
    Chairperson, Some Hon. Members, Des voix, the Clerk) ARE COUNTED, NOT
    STORED.
  * ONLY SPEECHES ON OUR GROUND ARE STORED, with an excerpt. Matching is
    per passage (src/filter.match_passages through prov_classify.classify_text)
    against the English taxonomy plus config/watchlist-prov.yaml, or, for
    Quebec, the French layer config/taxonomy-qc.yaml. The subject heading,
    with the bill's titles when the heading names a bill, is a passage of its
    own, as the Senate collector's is. A watched bill KEY
    (watchlist-prov.yaml) lends its areas to the debate held under its
    heading; a bill's text classification does NOT -- an omnibus bill's
    passing citation would otherwise file every speech of a budget debate.
    Statute names are not masked here: a member who names an Act is talking
    about it.

WHO SPOKE. A label is resolved to a prov_members key with the province's
own resolver (src/prov_names.Resolver, wrapped as each vote collector wraps
it: reviewed aliases, Newfoundland's NameResolver, Quebec's member pages),
against the roster terms valid ON THE DAY -- unique-or-nothing. Two
allowances, both inside one sitting:
  * a riding or role in brackets ("Hon. Jon Gerrard (River Heights)",
    "Hon. Kelvin Goertzen (Government House Leader)") is tried as a riding
    first and dropped if it is not one;
  * a bare surname that is AMBIGUOUS on the day ("Mr. Smith") resolves to the
    one candidate the same sitting named in full ("Hon. Andrew Smith
    (Lagimodière)") -- learn-then-resolve over the whole sitting, as the
    Senate collector does. Never across sittings.
NEVER IS A NAME INVENTED. A label that resolves by none of these is stored
with speaker_label as printed and member_key NULL, and counted: per day in
prov_speech_sittings (members - resolved, and `unresolved` among the stored)
and per run in the log. A day where fewer than half the speakers resolve is
a GAP -- the roster for that day is missing, not the members -- and is read
again on a later run.

Separation guarantee: writes prov_speeches, prov_speech_sittings, the roster
terms a province's own cover reader writes (Saskatchewan, Manitoba and
Ontario read the day's Hansard member list, exactly as their vote collectors
do on a division day) and the shared gaps table. It never writes a
division, a vote, a bill or prov_sittings.
"""

from __future__ import annotations

import datetime
import html as _html
import json
import re

from src import prov_classify as pc, prov_names as pn, prov_store as ps

DEFAULT_WINDOW_DAYS = 60       # a first weekly on an empty store reads this far back, said out loud
RESUME_LOOKBACK_DAYS = 14
OWED_DAYS = 120
MIN_RESOLVED_SHARE = 0.5       # below this, a day with >= MIN_SPEAKERS speaker turns is a gap
# A broken roster leaves a whole day's debate unresolved; a short ceremonial
# day does not -- Saskatchewan's opening of 22 October 2025 had six turns by
# elders and guests who are rightly nobody's member key.
MIN_SPEAKERS = 20


def feed(prov):
    return "prov-{0}-speeches".format(prov)


# -- labels ---------------------------------------------------------------------

_CHAIR = re.compile(
    r"^(?:the\s+|madam\s+|madame\s+|mister\s+|mr\.?\s+|mrs\.?\s+|ms\.?\s+|m\.\s+|mme\s+|le\s+|la\s+)?"
    r"(?:hon\.\s+the\s+)?(?:(?:deputy|acting|assistant|associate|second|third)\s+(?:deputy\s+)?)?"
    r"(?:speaker|chair(?:person|man|woman)?|(?:vice-)?presidente?|presiding\s+officer)\b"
    r"|^(?:the\s+|le\s+|la\s+)?(?:(?:deputy|assistant|acting|principal)\s+)?"
    r"(?:clerk|table\s+officer|sergeant|interpreter|secretaire|greffier|greffiere)\b"
    r"|^(?:his|her|son)\s+(?:honour|excellence)\b|^(?:the\s+)?(?:lieutenant|administrator)\b")
_COLLECTIVE = re.compile(
    r"^(?:(?:some|an|all|several|des|une|plusieurs)\s+)?(?:hon\.?\s+|honourable\s+)?"
    r"(?:members?|voix|deputes?|voices?|interjections?)$")


# Bold labels that open a paragraph but are nobody speaking (Saskatchewan
# prints a bold "Disclaimer:" on its opening-day HTML).
NOT_SPEAKERS = {"disclaimer", "note", "nota", "avis", "editor's note"}


def fold_label(label):
    return pn.fold(re.sub(r"[:\s—–\-]+$", "", label or "")).strip()


def is_chair(label):
    """The presiding officer, the table, or a collective label: counted, never stored."""
    f = fold_label(label or "")
    if not f:
        return True
    if _CHAIR.match(f) or _COLLECTIVE.match(f) or f in NOT_SPEAKERS:
        return True
    # pypdf's spacing ('The C hair'), tried only after the label as printed.
    g = fold_label(unsplit(label or ""))
    return g != f and bool(_CHAIR.match(g))


def clean_label(raw):
    """A printed label as the resolver wants it: no trailing colon or dash,
    entities and runs of space collapsed, the 'MPP'/'Député' prefix dropped
    (prov_names knows 'MLA', 'Member', 'Hon.' and the rest)."""
    s = _html.unescape(raw or "")
    s = re.sub("[\u00a0\u2000-\u200b\u202f\u205f\u3000]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[\s:—–\-]+$", "", s).strip()
    s = re.sub(r"^(?:MPP|Député|Députée)\s+", "", s, flags=re.I)
    return s


_PAREN = re.compile(r"\s*\(([^()]*)\)\s*$")


def _surname_tokens(label):
    lab = pn.parse_label(_PAREN.sub("", label))
    return tuple(lab.tokens)


def resolve_label(resolver, label, date, legislature, document=None):
    """(member_key, how) for one speech label, or (None, why). The bracket is
    tried as a riding, then dropped as a role."""
    lab = clean_label(label)
    if not lab:
        return None, "empty label"
    if " / " in lab:
        # 'Hon. Laanas / Tamara Davidson' (BC): a name in two languages. Each
        # side is tried; only one member may answer.
        hon = re.match(r"^((?:Hon\.|Mr\.|Ms\.|Mrs\.|Dr\.)\s+)", lab)
        sides = [s.strip() for s in lab.split(" / ") if s.strip()]
        found = {}
        for side in sides:
            if hon and not side.startswith(hon.group(1)):
                side = hon.group(1) + side
            k, h = resolve_label(resolver, side, date, legislature, document)
            if k:
                found[k] = h
        if len(found) == 1:
            k, h = next(iter(found.items()))
            return k, h + " (one side of a two-part name)"
        return None, "ambiguous: " + ", ".join(sorted(found)) if found else "unknown on {0}".format(date)
    key, how = _resolve(resolver, lab, date, legislature, document)
    if key:
        return key, how
    # Every bracket goes: a riding or role at the end, and a nickname inside
    # ('Mrs. Jennifer (Jennie) Stevens').
    bare = re.sub(r"\s*\([^()]*\)", "", lab).strip()
    if bare != lab and bare:
        key2, how2 = _resolve(resolver, bare, date, legislature, document)
        if key2:
            return key2, how2 + " (bracket is a role)"
        if str(how2).startswith("ambiguous"):
            return None, how2
    # pypdf's spacing ('Hon. Mr. Coc krill', 'Ms. Co nway'): a fragment that
    # starts lower-case is the end of the word before it, unless it is a
    # surname particle ('de Jonge').
    if str(how).startswith("unknown"):
        joined = unsplit(bare)
        if joined != bare:
            key4, how4 = _resolve(resolver, joined, date, legislature, document)
            if key4:
                return key4, how4 + " (a word split by the PDF rejoined)"
    # 'Hon. Mike Harris' where the roster prints Michael: retried as initial
    # plus surname, Newfoundland's allowance (prov_nl.NameResolver), still
    # unique-or-nothing. Never a bare surname.
    parsed = pn.parse_label(bare)
    if str(how).startswith("unknown") and len(parsed.tokens) >= 2 and not parsed.initials:
        key3, how3 = _resolve(resolver, "{0}. {1}".format(parsed.tokens[0][0].upper(), " ".join(parsed.tokens[1:])),
                              date, legislature, document)
        if key3:
            return key3, "initial (given name as printed differs)"
    return None, how


_PARTICLES = {"de", "da", "di", "du", "van", "von", "der", "den", "la", "le", "st", "mc", "mac"}


def unsplit(label):
    toks = label.split()
    out = []
    for t in toks:
        if out and t[:1].islower() and t.lower().rstrip(".,") not in _PARTICLES \
                and not out[-1].endswith(".") and out[-1][:1].isupper():
            out[-1] += t
        else:
            out.append(t)
    return " ".join(out)


def _resolve(resolver, label, date, legislature, document):
    try:
        return resolver.resolve(label, date, legislature, document=document)
    except TypeError:            # a wrapper without the document argument
        return resolver.resolve(label, date, legislature)


def resolve_turns(conn, prov, resolver, turns, date, legislature, document=None):
    """[(key, how)] per turn (chair turns get (None, 'chair')).

    Pass one resolves every label alone; pass two settles a bare surname that
    was AMBIGUOUS on the day by the one candidate the same sitting named in
    full -- by given name, initial or riding. A hint (Quebec prints the
    speaker's full name as a heading above the turn) is tried first when its
    surname is the label's."""
    surnames = {k: tuple(pn.fold(s or "").split()) for k, s in conn.execute(
        "SELECT member_key, surname FROM prov_members WHERE prov=?", (prov,))}
    out = []
    for t in turns:
        if is_chair(t["label"]):
            out.append((None, "chair"))
            continue
        key, how = None, None
        hint = t.get("hint")
        if hint:
            hk, hh = resolve_label(resolver, hint, date, legislature, document)
            toks = _surname_tokens(clean_label(t["label"]))
            if hk and toks and surnames.get(hk) and surnames[hk] == toks[-len(surnames[hk]):]:
                key, how = hk, hh + " (the heading above the turn)"
        if key is None:
            key, how = resolve_label(resolver, t["label"], date, legislature, document)
        out.append((key, how))
    named = {}
    for (key, how), t in zip(out, turns):
        # Named in full: by given name, initial, riding or heading -- anything
        # but a bare surname, and never a resolution this pass made itself.
        if key and how and how.split(" ")[0] != "surname" and "in-sitting" not in how:
            named.setdefault(surnames.get(key) or (), {}).setdefault(key, set()).add(
                honorific(t["label"]))
    final = []
    for (key, how), t in zip(out, turns):
        if key is None and how and how.startswith("ambiguous: "):
            cands = {c.strip() for c in how.split(": ", 1)[1].split(",")}
            toks = _surname_tokens(clean_label(t["label"]))
            seen = {}
            for sur, keys in named.items():
                if sur and toks[-len(sur):] == sur:
                    for k, hons in keys.items():
                        seen.setdefault(k, set()).update(hons)
            pick = cands & set(seen)
            hon = honorific(t["label"])
            if len(pick) > 1 and hon:
                # Two of the candidates were named in full today: the one
                # named with the SAME honorific ('Mrs. Bernadette Smith', so
                # 'Mrs. Smith'), if exactly one was.
                pick = {k for k in pick if hon in seen[k]}
            if len(pick) == 1:
                key, how = next(iter(pick)), "in-sitting (named in full earlier in the day; {0})".format(how)
        final.append((key, how))
    return final


_HONORIFIC = {"mr": "mr", "mister": "mr", "m": "mr", "monsieur": "mr",
              "mrs": "f", "ms": "f", "miss": "f", "madam": "f", "mme": "f", "madame": "f", "mlle": "f"}


def honorific(label):
    """'mr' or 'f' from the label's first honorific, else None ('Hon.' and
    'MLA' say nothing)."""
    for tok in clean_label(label).split()[:3]:
        f = pn.fold(tok).rstrip(".,")
        if f in _HONORIFIC:
            return _HONORIFIC[f]
        if f not in ("hon", "honourable", "the", "l'hon", "lhon"):
            return None
    return None


# -- bills ------------------------------------------------------------------------

def bill_by_title(conn, prov, legislature, session, heading):
    """The bill whose title IS the heading, in the same session: Ontario and
    Manitoba head a resumed debate with the bill's short title only."""
    want = pn.fold(re.split(r"\s+/\s+", heading or "")[0])
    if not want or len(want) < 12:
        return None
    hits = [r[0] for r in conn.execute(
        "SELECT bill_key, title_en FROM prov_bills WHERE prov=? AND legislature=? AND session=?",
        (prov, legislature, session)) if r[1] and pn.fold(r[1]) == want]
    return hits[0] if len(hits) == 1 else None


def bill_for(conn, prov, legislature, session, number):
    """(bill_key, [titles]) for a bill number named in a heading, in the same
    session -- never another session's bill of the same number (the Senate
    lesson: a 2010 Museums Act debate tagged with a later bill's areas)."""
    if not number:
        return None, []
    key = ps.bill_key(prov, legislature, session, number)
    row = conn.execute("SELECT bill_key, title_en, title_fr FROM prov_bills WHERE bill_key=?",
                       (key,)).fetchone()
    if row:
        return row[0], [t for t in row[1:] if t]
    if pc.watched_bill(prov, key):
        return key, []
    return None, []


# -- the day -------------------------------------------------------------------------

def classify_turn(tax, wl, prov, turn, language, titles=(), bill_key=None):
    title = " — ".join(x for x in [turn.get("subject")] + list(titles or []) if x) or None
    body = "\n\n".join(p for p in turn.get("paras") or [] if p)
    res = pc.classify_text(tax, wl, title=title, body=body, mask=False, french=(language == "fr"))
    if title and res.excerpt and " ".join(title.split()).startswith(res.excerpt.rstrip(".")[:40]):
        # The heading matched best; the excerpt a sheet quotes should be the
        # member's own words: the best body passage, else the opening.
        own = pc.classify_text(tax, wl, title=None, body=body, mask=False, french=(language == "fr"))
        res.excerpt = own.excerpt or lead(body)
    entry = pc.watched_bill(prov, bill_key)
    if entry:
        res = res.merge(pc.Result(entry.get("areas") or [], [bill_key], 1))
    return res


def store_day(ctx, day, turns, resolver, tax, wl, language="en", problems=(), when=None):
    """Store one day's speeches on our ground and its prov_speech_sittings
    row. `day`: {key, date, legislature, session, url}. `turns`: [{label,
    paras, rubric, subject, bill, hint}]. Returns the totals."""
    when = when or ps.today()
    conn, prov = ctx.conn, ctx.prov
    keys = resolve_turns(conn, prov, resolver, turns, day["date"], day.get("legislature"),
                         document=day.get("document"))
    conn.execute("DELETE FROM prov_speeches WHERE sitting_key=?", (day["key"],))
    totals = {"turns": len(turns), "chair": 0, "members": 0, "resolved": 0,
              "stored": 0, "unresolved": 0, "chars": 0}
    bills = {}
    for seq, (t, (key, how)) in enumerate(zip(turns, keys), 1):
        text = "\n".join(p for p in t.get("paras") or [] if p)
        totals["chars"] += len(text)
        if how == "chair":
            totals["chair"] += 1
            continue
        totals["members"] += 1
        if key:
            totals["resolved"] += 1
        number = t.get("bill")
        cache = (number, t.get("subject"))
        if cache not in bills:
            bk, titles = bill_for(conn, prov, day.get("legislature"), day.get("session"), number)
            if bk is None and not number and t.get("subject"):
                bk = bill_by_title(conn, prov, day.get("legislature"), day.get("session"), t["subject"])
                titles = []
            bills[cache] = (bk, titles)
        bill_key, titles = bills[cache]
        res = classify_turn(tax, wl, prov, t, language, titles=titles, bill_key=bill_key)
        if not res.on_our_ground():
            continue
        if not key:
            totals["unresolved"] += 1
        conn.execute(
            "INSERT OR REPLACE INTO prov_speeches (speech_id, prov, sitting_key, date, subject, "
            "bill_key, member_key, speaker_label, language, text, areas, excerpt, first_seen, "
            "legislature, session, seq, rubric, how, matched_terms, tier, source_url) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("{0}-{1}".format(day["key"], seq), prov, day["key"], day["date"], t.get("subject"),
             bill_key, key, clean_label(t["label"]), language, text, json.dumps(res.areas),
             res.excerpt or lead(text), when, day.get("legislature"), day.get("session"), seq, t.get("rubric"),
             how, json.dumps(res.terms), res.tier, day.get("url")))
        totals["stored"] += 1
    problems = list(problems or [])
    if totals["members"] >= MIN_SPEAKERS and totals["resolved"] < MIN_RESOLVED_SHARE * totals["members"]:
        problems.append("only {0} of {1} speaker turns resolved: the roster for the day is "
                        "missing or the labels changed".format(totals["resolved"], totals["members"]))
    if not turns:
        problems.append("no speaker turns parsed")
    for p in problems:
        ctx.gap("{0} {1}: {2}".format(prov, day["key"], p))
    status = "ok" if not problems else ("unreadable" if not turns else "gap")
    store_sitting(conn, prov, day, totals, status, "; ".join(problems) or None, when)
    conn.commit()
    return dict(totals, status=status)


def lead(text, max_chars=260):
    """The excerpt of a speech stored for its debate (a watched bill's key)
    rather than for a passage of its own: its opening words."""
    t = " ".join((text or "").split())
    return t if len(t) <= max_chars else t[:max_chars].rsplit(" ", 1)[0] + "..."


def store_sitting(conn, prov, day, totals, status, note=None, when=None):
    conn.execute(
        "INSERT OR REPLACE INTO prov_speech_sittings (sitting_key, prov, legislature, session, "
        "date, record_url, turns, chair, members, resolved, stored, unresolved, chars, read_at, "
        "status, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (day["key"], prov, day.get("legislature"), day.get("session"), day.get("date"),
         day.get("url"), totals.get("turns"), totals.get("chair"), totals.get("members"),
         totals.get("resolved"), totals.get("stored"), totals.get("unresolved"),
         totals.get("chars"), when or ps.today(), status, note))


class NoSitting(Exception):
    """Raised by a reader's read_day when the page the listing links for a
    day is only the legislature's own notice that the House did not sit that
    day (NL, 29 March 2018: "The House of Assembly stands adjourned to the
    call of the Chair"). The day is stored 'ok' with no turns and the notice
    as its note, and logged: it is read, not owed, and never read again."""


def store_no_sitting(ctx, day, notice):
    ctx.log("  {0} {1}: no sitting, the page is the notice \"{2}\"".format(ctx.prov, day["key"], notice[:160]))
    store_sitting(ctx.conn, ctx.prov, day, {"turns": 0, "chair": 0, "members": 0, "resolved": 0,
                                            "stored": 0, "unresolved": 0, "chars": 0},
                  "ok", "no sitting: " + notice)
    ctx.conn.commit()


def store_unreadable(ctx, day, why):
    ctx.gap("{0} {1}: {2}".format(ctx.prov, day["key"], why))
    store_sitting(ctx.conn, ctx.prov, day, {}, "unreadable", why)
    ctx.conn.commit()


def day_done(conn, key):
    row = conn.execute("SELECT status FROM prov_speech_sittings WHERE sitting_key=?", (key,)).fetchone()
    return bool(row) and row[0] == "ok"


def resume_since(conn, prov, today=None, log=print):
    """The weekly window's first day: the newest day read less two weeks, or
    the oldest day still owed in the last 120 days; on a province with
    nothing read, the last DEFAULT_WINDOW_DAYS (a backfill is a dispatch)."""
    today = today or datetime.date.today()
    newest = conn.execute("SELECT MAX(date) FROM prov_speech_sittings WHERE prov=? AND date IS NOT NULL",
                          (prov,)).fetchone()[0]
    if not newest:
        since = (today - datetime.timedelta(days=DEFAULT_WINDOW_DAYS)).isoformat()
        log("  {0}: no Hansard day read for speeches yet; reading the last {1} days (from {2}). "
            "Older days are the backfill".format(prov, DEFAULT_WINDOW_DAYS, since))
        return since
    since = (datetime.date.fromisoformat(newest[:10])
             - datetime.timedelta(days=RESUME_LOOKBACK_DAYS)).isoformat()
    floor = (today - datetime.timedelta(days=OWED_DAYS)).isoformat()
    owed = conn.execute("SELECT MIN(date) FROM prov_speech_sittings WHERE prov=? AND status != 'ok' "
                        "AND date >= ?", (prov, floor)).fetchone()[0]
    if owed and owed < since:
        since = owed
    log("  {0}: speeches resuming from {1} (newest day read {2}{3})".format(
        prov, since, newest, "; oldest still owed {0}".format(owed) if owed and owed == since else ""))
    return since


def collect_days(ctx, days, read_day, resolver_for, tax, wl, language="en"):
    """Read every listed day in the window not already read cleanly.
    read_day(day) -> (turns, problems) or raises prov_fetch.Unreadable, or
    NoSitting when the page is the House's own notice that it did not sit;
    resolver_for(day) -> the resolver for that day (built once a session)."""
    from src.prov_fetch import Unreadable
    stats = {"days_listed": len(days), "days_read": 0, "turns": 0, "members": 0, "resolved": 0,
             "speeches": 0, "unresolved_stored": 0, "day_gaps": 0}
    for day in days:
        if not ctx.in_window(day["date"]):
            continue
        if not ctx.refresh and day_done(ctx.conn, day["key"]):
            continue
        if ctx.stop():
            break
        ctx.records_read += 1
        if ctx.dry_run:
            stats["days_read"] += 1
            continue
        try:
            turns, problems = read_day(day)
        except Unreadable as exc:
            store_unreadable(ctx, day, str(exc))
            stats["day_gaps"] += 1
            continue
        except NoSitting as exc:
            store_no_sitting(ctx, day, str(exc))
            stats["no_sitting"] = stats.get("no_sitting", 0) + 1
            continue
        if turns is None:
            store_unreadable(ctx, day, "; ".join(problems or ["not fetched"]))
            stats["day_gaps"] += 1
            continue
        t = store_day(ctx, day, turns, resolver_for(day), tax, wl, language=language, problems=problems)
        stats["days_read"] += 1
        stats["turns"] += t["turns"]
        stats["members"] += t["members"]
        stats["resolved"] += t["resolved"]
        stats["speeches"] += t["stored"]
        stats["unresolved_stored"] += t["unresolved"]
        stats["day_gaps"] += 0 if t["status"] == "ok" else 1
        ctx.log("  {0} {1}: {2} turn(s), {3} chair, {4}/{5} speaker turn(s) resolved, {6} on our "
                "ground{7}".format(ctx.prov, day["key"], t["turns"], t["chair"], t["resolved"],
                                   t["members"], t["stored"],
                                   ", {0} of them unattributed".format(t["unresolved"]) if t["unresolved"] else ""))
    return stats


def summary(conn, prov):
    one = lambda sql: conn.execute(sql, (prov,)).fetchone()[0]  # noqa: E731
    return {
        "days": one("SELECT COUNT(*) FROM prov_speech_sittings WHERE prov=?"),
        "days_owed": one("SELECT COUNT(*) FROM prov_speech_sittings WHERE prov=? AND status != 'ok'"),
        "turns": one("SELECT COALESCE(SUM(members), 0) FROM prov_speech_sittings WHERE prov=?"),
        "resolved": one("SELECT COALESCE(SUM(resolved), 0) FROM prov_speech_sittings WHERE prov=?"),
        "speeches": one("SELECT COUNT(*) FROM prov_speeches WHERE prov=?"),
        "unresolved": one("SELECT COUNT(*) FROM prov_speeches WHERE prov=? AND member_key IS NULL"),
        "speakers": one("SELECT COUNT(DISTINCT member_key) FROM prov_speeches WHERE prov=?"),
    }


class Primed:
    """The run's Context, with one document already in hand: a province's
    cover reader asking for the PDF just read for its speeches gets those
    bytes, not a second download of the same megabyte."""

    def __init__(self, ctx, url, raw):
        self._ctx, self._url, self._raw = ctx, url, raw

    def __getattr__(self, name):
        return getattr(self._ctx, name)

    def bytes(self, url, slug, archive=False):
        if url == self._url and self._raw is not None:
            return self._raw
        return self._ctx.bytes(url, slug, archive=archive)


# -- shared markup helpers -------------------------------------------------------------

_TAGS = re.compile(r"<[^>]+>")


def text_of(fragment):
    """Visible text: tags dropped WITHOUT a space (Word splits names across
    spans), <br> as a space, entities decoded, whitespace collapsed."""
    s = re.sub(r"(?is)<!--.*?-->", "", fragment or "")
    s = re.sub(r"(?i)<br[^>]*>", " ", s)
    s = _TAGS.sub("", s)
    s = _html.unescape(s).replace("\xa0", " ").replace("\xad", "")    # Word's soft hyphens: re\xadplace\xadment
    return re.sub(r"\s+", " ", s).strip()


_BOLD_OPEN = re.compile(r"<(?:b|strong)\b[^>]*>", re.I)
_BOLD_CLOSE = re.compile(r"</(?:b|strong)\s*>", re.I)
_LEAD = re.compile("^\\s*((?:\x01[^\x01\x02]*\x02[\\s:—–\\-]*)+)(.*)$", re.S)


def bold_label(fragment, max_len=140):
    """(label, rest) when a paragraph OPENS with bold text that is a speaker
    label -- Word splits one label over several bold runs ('<b>Mr. Jim </b>
    <b>Maloway</b><b> (Elmwood):</b>'), and the colon may sit inside or just
    after the bold ('<b>Hon. Mr. Cockrill</b>: —'). None when the bold run is
    not followed by a colon (a bold heading or an emphasised phrase)."""
    s = re.sub(r"(?is)<!--.*?-->", "", fragment or "")
    s = _BOLD_OPEN.sub("\x01", s)
    s = _BOLD_CLOSE.sub("\x02", s)
    s = re.sub(r"(?i)<br[^>]*>", " ", s)
    s = _TAGS.sub("", s)
    s = _html.unescape(s).replace("\xa0", " ").replace("\xad", "")
    m = _LEAD.match(s)
    if not m:
        return None
    head, rest = m.group(1), m.group(2)
    label = re.sub(r"\s+", " ", head.replace("\x01", "").replace("\x02", "")).strip()
    rest = rest.replace("\x01", "").replace("\x02", "")
    if not label.rstrip(" —–-").endswith(":") and not re.match(r"^\s*:", rest):
        return None
    label = re.sub(r"[\s:—–\-]+$", "", label).strip()
    if not label or len(label) > max_len:
        return None
    rest = re.sub(r"^\s*:?\s*[—–-]?\s*", "", rest)
    return label, re.sub(r"\s+", " ", rest).strip()


def turns_from_blocks(blocks):
    """Turns from a stream of blocks:
      ('rubric', text[, bill])   a top heading: Oral Questions, Orders of the Day
      ('subject', text[, bill])  the debate heading under it
      ('subsubject', text)       a heading inside that debate ('Questions')
      ('label', label, text)     a speaker label and the rest of its paragraph
      ('para', text)             a paragraph: the current turn's, or, before
                                 the subject's first turn, procedural text
      ('proc', text)             procedural text, never part of a speech
      ('hint', name)             the speaker's full name, printed above the turn
      ('break',)                 ends the current turn (a division list)
    THE BILL is read from the heading or from the procedural text between
    the heading and its first turn ("Bill 27, An Act to enact ..."), never
    from a speech, which can cite any bill it likes (ca_hansard.subject_bill)."""
    turns, cur = [], None
    rubric = subject = bill = hint = parent = None
    opening = False                  # between a heading and its first turn
    for b in blocks:
        kind = b[0]
        if kind == "rubric":
            rubric, subject, parent, cur, opening = b[1], None, None, None, True
            bill = b[2] if len(b) > 2 else None
        elif kind == "subject":
            subject, cur, opening = b[1], None, True
            bill = b[2] if len(b) > 2 and b[2] else None
            parent = subject
        elif kind == "subsubject":
            # 'Questions' and 'Debate' under a bill's heading (Manitoba's
            # private members' business): the same debate, the same bill.
            subject, cur = " — ".join(x for x in (parent, b[1]) if x), None
        elif kind == "hint":
            hint = b[1]
        elif kind == "label":
            cur = {"label": b[1], "paras": [b[2]] if b[2] else [], "rubric": rubric,
                   "subject": subject, "bill": bill, "hint": hint}
            hint, opening = None, False
            turns.append(cur)
        elif kind in ("para", "proc"):
            if kind == "para" and cur is not None:
                if b[1]:
                    cur["paras"].append(b[1])
            elif opening and bill is None:
                bill = bill_number(b[1])
        elif kind == "break":
            cur = None
    return turns


_HBLOCK = re.compile(r"<(h[1-6]|p)\b([^>]*)>(.*?)</\1\s*>", re.S | re.I)


def word_html_turns(html, rubric_tags, subject_tags, sub_headings=(), subject_text=None):
    """Turns from a Word-exported Hansard (Manitoba, Saskatchewan): headings
    by tag level, a turn wherever a paragraph opens with a bold label
    (bold_label). subject_text, if given, trims a heading (Saskatchewan's
    French title after the slash)."""
    i = (html or "").find("<body")
    body = (html or "")[i:] if i >= 0 else (html or "")
    blocks = []
    for tag, _attrs, inner in _HBLOCK.findall(body):
        tag = tag.lower()
        text = text_of(inner)
        if tag in rubric_tags:
            if text:
                blocks.append(("rubric", text))
        elif tag in subject_tags:
            if text in sub_headings:
                blocks.append(("subsubject", text))
            elif text:
                text = subject_text(text) if subject_text else text
                blocks.append(("subject", text, bill_number(text)))
        elif tag == "p":
            lab = bold_label(inner)
            if lab:
                blocks.append(("label", lab[0], lab[1]))
            elif text and text != "* * *":
                blocks.append(("para", text))
    return turns_from_blocks(blocks)


BILL_IN_HEADING = re.compile(r"\bBill\s+(?:No\.\s*)?(\d{1,3}|Pr\s?\d{1,3})\b", re.I)


def bill_number(heading):
    """'Bill 26', 'Bill No. 137', 'Bill (No. 207)', 'Bill Pr18' in a heading."""
    m = BILL_IN_HEADING.search(heading or "") or re.search(r"\bBill\s*\(No\.\s*(\d{1,3})\)", heading or "", re.I)
    return m.group(1).replace(" ", "") if m else None
