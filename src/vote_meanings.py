"""Plain-English vote meanings for the new countries: what a Yes and a No meant.

The UK has written `meaning_aye` / `meaning_no` lines for its divisions
(config/vote_tracker.yaml, tools/review_divisions.py, tools/prep_division.py,
tools/meaning_line_queue.py) and Switzerland's source publishes its own
("Bedeutung Ja / Nein", ch_divisions.meaning_yes / meaning_no). This module
gives every watched and tier-1 vote in every new country with recorded votes
(src/country5ca.COUNTRIES: the fifteen own editions' countries with votes and
Chile, Peru, Ecuador, the Dominican Republic, El Salvador and Guatemala) one
English line for each lobby, stored per division, with where it came from.

A MEANING IS NOT A STANCE. It says what each lobby voted FOR ("Yes: to pass
the bill as a whole"), never which side is CitizenGO's: that stays a signed
human reading in config/<cc>_stance.yaml (src/country5ca.py). A line that
names CitizenGO is refused.

WHERE A LINE COMES FROM, in this order (the first that has one wins):

1. A PERSON, file-based like the UK: config/vote-meanings-<cc>.yaml,

       meanings:
         "pl-10-65-11":
           meaning_yes: "To pass the cohabitation contracts bill again over the President's veto."
           meaning_no: "Against passing it again; the veto stands."
           by: "Christopher"
           "on": 2026-10-11

   (Not `yes:` / `no:`: YAML reads those as true and false.) Both lines are
   required (an entry with one is ignored and reported by
   `tools/vote_meanings.py --check`). Never rewritten by any tool.
2. THE FREE SESSION JUDGE (tools/vote_meanings.py --queue-out / --queue-in,
   run by tools/session_judge.sh in the Sunday editions-session-judge job,
   AFTER the editions' scores and within the same weekly budget of about 100
   items): Claude Code on the Mac Mini, plan allowance, no API spend. It is
   offered only what the rules could not do well, stored in `vote_meanings`
   with source 'judge'. "UNCLEAR" is stored too (source 'judge-unclear') so
   the item is not offered again; the rule line, if any, still shows.
3. THE RULES (`rule_meaning`), from the vote's own wording and the bill:
   the kind of vote (src/country5ca.vote_kind: the whole text, a motion to
   reject, an inverted vote, an amendment or article, procedure), a few
   named forms (Poland's re-passage over a veto, Spain's toma en
   consideración, Switzerland's Eintreten, the Latin American "en lo
   general" and "en lo particular", Austria's Bundesrat "kein Einspruch"),
   Switzerland's own Bedeutung lines translated by a fixed table, and the
   bill's English description from the watchlist or the stance file's
   `bill_directions` (written by Claude in English on 9-10 October). A bill
   with no English description is quoted verbatim in its own language
   (quality 'title'); such lines, and votes the rules cannot read (kind
   'other'), are what the session judge is offered, watched first, newest
   first. Rules are deterministic, so a vote newer than the last Sunday run
   still gets its rule line at render time (`lookup` computes it live).

WHERE IT IS SHOWN: the weekly editions and the Latam monitor
(src/country_edition.py, tools/latam_monitor.py: `annotate` puts
`meaning` on each watched or tier-1 vote item, `line` renders it), the
same-day vote briefs (src/country_vote_brief.py), member profiles
(src/member_profiles.py: what the member's own vote meant), debate packs
(src/country_debatepack.py) and the 5CA readings guide
(docs/5ca-<cc>-readings.md, src/country5ca.signoff_markdown).

No paid AI, no network. Reads the store; writes only `vote_meanings`
(tools/vote_meanings.py --rules / --queue-in).
"""

from __future__ import annotations

import datetime
import os
import re
import sqlite3

from src import country5ca as c5

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config")
TABLE = "vote_meanings"
SESSION_MODEL = "claude-code-session"
RULES = "rules (src/vote_meanings.py)"
MAX_LINE = 240
DESC_CHARS = 110
QUOTE_CHARS = 90

SCHEMA_SQL = """CREATE TABLE IF NOT EXISTS vote_meanings (
  cc TEXT NOT NULL,
  division_key TEXT NOT NULL,
  meaning_yes TEXT,
  meaning_no TEXT,
  source TEXT NOT NULL,      -- 'rule', 'judge', 'judge-unclear'
  basis TEXT,                -- the rule that made it, or the judge's model
  quality TEXT,              -- 'full' (all English) or 'title' (quotes the source)
  made_on TEXT,
  PRIMARY KEY (cc, division_key)
)"""

SOURCE_WORDS = {"person": "written by {by}", "judge": "read by the free session judge",
                "rule": "by rule, from the vote's wording and the bill"}


def ensure_table(conn):
    conn.execute(SCHEMA_SQL)


# --- small text helpers ---------------------------------------------------------------

def clean(text):
    text = " ".join(str(text or "").split())
    return text.replace(" — ", ", ").replace("—", ", ").replace("–", "-")


def clip(text, n):
    text = clean(text)
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",;:")
    return cut + "…"


def first_sentence(text):
    text = clean(text)
    m = re.search(r"(?<=[a-z0-9\)\]'\"])\.\s+(?=[A-Z])", text)
    return text[:m.start()] if m else text.rstrip(".")


def gloss(text):
    """The English description from a watchlist or bill-direction line: its
    first sentence; after a short source title and a colon when what follows
    reads as English ('Kodeks karny: decriminalises abortion ...')."""
    s = first_sentence(text)
    if ": " in s:
        head, tail = s.split(": ", 1)
        if len(head) <= 70 and re.match(r"[a-z]", tail):
            s = tail
    return clip(s, DESC_CHARS)


# --- the bill: an English description where we have one ------------------------------

def _watch_entry(wl, key):
    e = (wl or {}).get(key) if key else None
    return e if isinstance(e, dict) else None


# Stores whose "subject" is the order paper's section heading, not the text's
# title (Spain: "Dictámenes de Comisiones sobre iniciativas legislativas."):
# the vote's own wording names the text better.
HEADING_SUBJECTS = ("es",)
WEAK_GLOSS = re.compile(r"^(the )?same (bill|text)\b|^merged into\b", re.I)


def describe(cc, r, wl, bills):
    """(what, english): how the lines name the text voted on. `what` is
    '10/2110 (registered cohabitation contracts)' from the watchlist or the
    stance file's bill_directions (a gloss that only says 'the same bill at
    the Senate' gives way to another key's), else the vote's subject quoted
    verbatim; a short section heading for a subject ('Proposiciones no de
    Ley.') gives way to the vote's own wording."""
    spec = c5.SPECS[cc]
    keys = []
    for k in [r.get("watch_key")] + [k for k in spec.refs(r) if k]:
        if k and k not in keys:
            keys.append(k)
    weak = None
    for k in keys:
        e = _watch_entry(wl, k)
        text = e and (e.get("why") or e.get("title") or e.get("note"))
        if not text and k in (bills or {}):
            text = bills[k].get("why") or bills[k].get("title")
        if not text:
            continue
        g = gloss(text)
        if WEAK_GLOSS.search(g):
            weak = weak or "{0} ({1})".format(k.replace("item:", "item "), g)
            continue
        return "{0} ({1})".format(k.replace("item:", "item "), g), True
    subject, question = clean(r.get("subject")), clean(r.get("question"))
    if subject and subject != question and len(subject) >= 45 and cc not in HEADING_SUBJECTS:
        return "the text \u201c{0}\u201d".format(clip(subject, QUOTE_CHARS)), False
    if weak:
        return weak, True
    if question:
        return "the text \u201c{0}\u201d".format(clip(question, QUOTE_CHARS)), False
    if subject:
        return "the text \u201c{0}\u201d".format(clip(subject, QUOTE_CHARS)), False
    return None, False


# --- Switzerland's own Bedeutung lines ------------------------------------------------

CH_PHRASES = (
    (r"^antrag der mehrheit und des bundesrates", "the committee majority's and the Federal Council's proposal"),
    (r"^antrag der mehrheit", "the committee majority's proposal"),
    (r"^antrag der minderheit", "the committee minority's proposal"),
    (r"^antrag des bundesrates", "the Federal Council's proposal"),
    (r"^antrag der kommission", "the committee's proposal"),
    (r"^antrag der einigungskonferenz", "the conciliation conference's proposal"),
    (r"^antrag der motionar\w*|^antrag des motionars", "the motion's author's proposal"),
    (r"^antrag der postulant\w*|^antrag des postulanten", "the postulate's author's proposal"),
    (r"^beschluss des nationalrates", "the National Council's decision"),
    (r"^beschluss des standerates", "the Council of States' decision"),
    (r"^geltendes recht", "current law (no change)"),
    (r"^nichteintreten", "not entering into the matter (rejecting it at this stage)"),
    (r"^eintreten", "entering into the matter"),
    (r"^ruckweisung", "sending it back"),
    (r"^ablehnung", "rejecting it"),
    (r"^annahme", "adopting it"),
    (r"^zustimmung", "agreeing to it"),
    (r"^proposition de la majorite et du conseil federal", "the committee majority's and the Federal Council's proposal"),
    (r"^proposition de la majorite", "the committee majority's proposal"),
    (r"^proposition de la minorite", "the committee minority's proposal"),
    (r"^proposition du conseil federal", "the Federal Council's proposal"),
    (r"^proposition de la commission", "the committee's proposal"),
    (r"^adopter (le projet|la loi)", "adopting the bill"),
    (r"^rejeter (le projet|la loi)", "rejecting the bill"),
    (r"^adopter (la motion|le postulat)", "adopting it"),
    (r"^rejeter (la motion|le postulat)", "rejecting it"),
    (r"^entrer en matiere", "entering into the matter"),
    (r"^ne pas entrer en matiere", "not entering into the matter (rejecting it at this stage)"),
    (r"^antrag [a-z]", "a member's proposal"),
)
CH_INNER = ((r"annahme", "to accept"), (r"ablehnung", "to reject"), (r"maintenir|festhalten", "to hold to it"),
            (r"selon ce|gem\w*\.? ?sr\b|gemass standerat", "as the Council of States decided"),
            (r"selon cn|gem\w*\.? ?nr\b|gemass nationalrat", "as the National Council decided"),
            (r"adhesion|zustimmung", "to agree"), (r"rejet", "to reject"), (r"adoption", "to adopt"))


def ch_phrase(text):
    """A Swiss Bedeutung line in English, or None when the table has no entry.
    The bracket after it is a name ('Minderheit (Glarner)') or a gloss
    ('(Annahme der Motion)'), kept as the source spells it or translated."""
    original = clean(text).strip(" *.")
    t = c5.fold(original)
    if not t:
        return None
    named = re.match(r"(?i)^(?:proposition (?:du groupe |de l'|de la |du |des )|antrag der fraktion )"
                     r"([^(]+?)\s*(\(([^()]*)\)?)?$", original)
    rows = CH_PHRASES
    if named and not re.match(r"(majorit|minorit|commission|conseil)", c5.fold(named.group(1))):
        rows = ((r".", "the {0} proposal".format(named.group(1).strip() + "'s")),)
    for pat, words in rows:
        if not re.match(pat, t):
            continue
        inner = re.search(r"\(([^()]*)", original)
        if not inner:
            tail = re.match(r"(?i)^(?:antrag der minderheit|proposition de la minorit\S*)\s+(.+)$", original)
            if tail:
                return "{0} ({1})".format(words, tail.group(1).strip())
            return words
        bit = inner.group(1).strip().rstrip(")")
        fb = c5.fold(bit)
        for ipat, iwords in CH_INNER:
            if re.search(ipat, fb):
                return "{0} ({1})".format(words, iwords)
        if words.startswith(("a group's", "a member's")):
            return words
        if re.fullmatch(r"[ivx]+", fb):
            return "{0} {1}".format(words, bit.upper())
        return "{0} ({1})".format(words, bit)
    return None


# --- the rules ------------------------------------------------------------------------

AMEND_NUMBER = (r"amendements?(?:\s+(?:identiques|de suppression|de reecriture))?\s+n\s*[°ºo]?\.?\s*(\d+)", r"poprawk\w*\s+(?:nr\s*)?(\d+(?:\s*(?:i|,)\s*\d+)*)",
                r"\bemm?\.\s*(\d[\d.]*)", r"emendamento\s+(?:n\.\s*)?(\d[\d.]*)",
                r"enmienda\s+(?:num\.?|n\s*[°ºo]\.?)?\s*(\d+)", r"emenda\s+(?:n\s*[°ºo]\.?)?\s*(\d+)",
                r"\bem\s+(\d+)", r"amendement\s+(?:nr\.?\s*)?(?:van [^,]+?\s+)?(?:\(?(\d+)\)?)")
ARTICLE = r"^(?:sur )?(?:l')?(?:art\.?|articolo|articulo|article)\s*(\d+[\w-]*)"

# (pattern over the folded wording, yes line, no line). {what} is the text.
NAMED_FINAL = (
    (r"ponownym uchwaleni", "To pass {what} again, overriding the President's veto.",
     "Against passing it again, so the veto stands."),
    (r"toma en consideracion", "To take {what} into consideration, so it goes on to committee.",
     "Against taking it into consideration, which stops it at this stage."),
    (r"\beintreten\b", "To enter into the matter on {what}, opening its detailed reading.",
     "Against entering into it, which rejects it at this stage."),
    (r"en lo general y en lo particular|en general y en particular",
     "To approve {what} in general and in its articles, in one vote.",
     "Against approving it."),
    (r"en lo general|\ben general\b", "To approve {what} in general (its broad terms, before the "
     "articles).", "Against approving it in general."),
    (r"votacao na generalidade", "To approve {what} on the general principle (first stage).",
     "Against approving it in principle."),
    (r"keinen einspruch", "To raise no objection to {what}, letting the law proceed.",
     "For objecting to it, sending it back to the Nationalrat."),
    (r"entschliessungsantrag", "To adopt the resolution motion on {what}.",
     "Against adopting the resolution."),
    (r"aprovad\w*,? em primeiro turno", "To approve {what} in the first round.",
     "Against approving it in the first round."),
    (r"aprovad\w*,? em segundo turno", "To approve {what} in the second and final round.",
     "Against approving it."),
    (r"prvo citanje", "To accept {what} at first reading.", "Against accepting it at first reading."),
    (r"drugo citanje", "To pass {what} at second (final) reading.", "Against passing it."),
    (r"dritter lesung", "To pass {what} at third reading.", "Against passing it."),
    (r"zweiter lesung", "To pass {what} at second reading.", "Against passing it."),
    (r"^(gewijzigde |nader gewijzigde )?motie|^motie:|adopter (le postulat|la motion)|"
     r"annahme (der motion|des postulats)|abstimmung uber die motion|proposicion no de ley|"
     r"mocion consecuencia|navrhu uznesenia",
     "To adopt the motion {what}.", "Against adopting the motion."),
)

NAMED_PROCEDURE = (
    (r"de urgencia|urgenza|skrateni\w* lehot|skroceni\w* termin|surgossegi",
     "To speed up the handling of {what} (urgency or a shorter deadline).",
     "Against speeding it up."),
    (r"remitid\w*.*comision|vuelta a comision|baixa\w* (a |a )?comissao|ruckweisung",
     "To send {what} back to committee.", "Against sending it back."),
    (r"pristupeni k tretiemu citaniu ihned", "To move {what} straight to third reading.",
     "Against moving straight to third reading."),
    (r"niezwloczne przystapienie do drugiego czytania", "To move {what} straight to second reading.",
     "Against moving straight to second reading."),
    (r"avocacion por el pleno", "To have the full chamber, not the committee, take the final vote on "
     "{what}.", "Against bringing it to the full chamber."),
    (r"orden del dia|porzadk\w* dzienn|napirend", "To change the order of business to take {what}.",
     "Against that change to the order of business."),
    (r"dispensa\w* (de |da )?reda", "To skip the final drafting stage of {what}, so the final vote "
     "can follow at once.", "Against skipping it."),
    (r"requerimento", "To approve a procedural request (requerimento) on {what}.",
     "Against the request."),
    (r"prorroga", "To extend a deadline (on {what}).", "Against the extension."),
    (r"\bodroczeni|przerw\w* w posiedzeniu|suspension de seance",
     "To adjourn or pause the sitting (on {what}).", "Against adjourning or pausing."),
)


def _subst(text, what):
    if what.startswith("the text ") and re.search(r"(resolution or decision|motion) \{what\}", text):
        what = what[len("the text "):]
    return clean(text.replace("{what}", what))


def _amendment_label(question):
    q = c5.fold(question)[:c5.QUESTION_CHARS]
    for pat in AMEND_NUMBER:
        m = re.search(pat, q)
        if m and m.group(1):
            nums = [x for x in re.split(r"\s*(?:,|\bi\b|\be\b|\band\b)\s*", m.group(1).rstrip(".")) if x]
            if len(nums) > 1:
                return "amendments {0} and {1}".format(", ".join(nums[:-1]), nums[-1])
            if re.search(r"de suppression", q):
                return "amendment {0} (to delete the provision)".format(nums[0])
            return "amendment {0}".format(nums[0])
    m = re.search(ARTICLE, q)
    if m:
        return "article {0}".format(m.group(1))
    if re.search(r"wniosek mniejszosci", q):
        return "the committee minority's motion"
    return None


# Wordings the kind rules leave as 'other' that still say what was decided.
NAMED_OTHER = (
    (r"opposer la question prealable|exception d'irrecevabilite",
     "To reject {what} without further debate (a motion opposing the question préalable or "
     "the exception).", "Against the motion, so the debate goes on."),
    (r"renvoi en commission|renvoyer en commission", "To send {what} back to committee.",
     "Against sending it back."),
    (r"segundo debate", "To approve {what} at its second debate (the Assembly's final vote).",
     "Against approving it."),
    (r"proyecto de resolucion|^prijedlog (odluke|rezolucije|deklaracije)|^resolucao|^resolution",
     "To adopt the resolution or decision {what}.", "Against adopting it."),
)

MOTION_FIRST = (r"^proposicion no de ley|^mocion consecuencia|^(gewijzigde |nader gewijzigde )?motie\b|"
                r"^motie:|^(motie|amendement)?:? ?(gewijzigde )?motie")
# (pattern, label) for an amendment or part whose wording names what it is.
NAMED_PART = (
    (r"osszegzo modosito javaslat", "the Legislative Committee's consolidated amendments"),
    (r"modosito javaslat fenntartasa|fenntartott modosito", "a minority amendment (rejected in "
                                                             "committee, kept to a vote by its author)"),
    (r"\bodg\b|ordine del giorno", "the order of the day {n} (a non-binding motion)"),
    (r"mantido o texto", None),
    (r"abanderungsantrag der abgeordneten|zusatzantrag der abgeordneten", "the amendment moved by {mover}"),
    (r"entschliessungsantrag der abgeordneten", "the resolution moved by {mover}"),
    (r"aangehouden amendement", "the amendment and article held over from the earlier vote"),
    (r"pozmenujuc\w* navrh", "an amendment"),
)
TWO_THIRDS = r"minositett tobbseget igenylo"


def _mover(question):
    m = re.search(r"(?i)der Abgeordneten\s+(.+?)(?:,| und | Kolleginnen|$)", clean(question))
    return "{0} and others".format(m.group(1).strip()) if m else "members"


def rule_meaning(cc, r, wl=None, bills=None):
    """{'yes', 'no', 'basis', 'quality'} for one division row (country5ca's
    shape), or None when the rules cannot read it."""
    spec = c5.SPECS[cc]
    question = clean(r.get("question"))
    what, english = describe(cc, r, wl, bills)
    quality = "full" if english else "title"
    if cc == "ch" and (r.get("meaning_yes") or r.get("meaning_no")):
        subject = clean(r.get("subject"))
        on = what if english else ("the text \u201c{0}\u201d".format(clip(subject, QUOTE_CHARS))
                                   if subject and subject != question else None)
        got = _ch_rule(r, on, english)
        if got:
            return got
    kind, _ = c5.vote_kind(question, spec.hint(r))
    q = c5.fold(question)[:c5.QUESTION_CHARS]
    if what is None:
        return None
    if re.search(MOTION_FIRST, q):
        motion = what if english else "\u201c{0}\u201d".format(clip(question, QUOTE_CHARS))
        return _out("To adopt the motion {0}{1}.".format(
            motion, ", in the terms put to the vote" if re.search(r"enmienda", q) else ""),
            "Against adopting the motion.", "motion", quality)
    if kind == "other" and (re.search(ARTICLE, q) or re.search(AMEND_NUMBER[0], q)):
        kind = "amendment"
    if re.search(r"totalidad de texto alternativo", q):
        return _out("To replace {0} with an alternative text (an amendment to the whole).".format(what),
                    "Against the alternative text.", "texto alternativo", quality)
    if kind == "final":
        for pat, yes, no in NAMED_FINAL:
            if re.search(pat, q):
                return _out(_subst(yes, what), no, "final: " + pat.split("|")[0], quality)
        return _out("To pass {0} as a whole.".format(what), "Against passing it.", "final", quality)
    if kind == "reject":
        if re.search(r"totalidad de devolucion", q):
            return _out("To send {0} back to the government (an amendment to the whole).".format(what),
                        "Against sending it back, so it goes on.", "reject: totalidad", quality)
        if re.search(r"nichteintret", q):
            return _out("Not to enter into {0}, rejecting it at this stage.".format(what),
                        "To enter into it, so it goes on.", "reject: nichteintreten", quality)
        return _out("To reject {0} outright at this stage (a motion to reject).".format(what),
                    "Against rejecting it, so it goes on.", "reject", quality)
    if kind == "inverted":
        return _out("To reject {0} (the record says a Yes here rejects it).".format(what),
                    "Against rejecting it.", "inverted", quality)
    if kind == "amendment":
        if re.search(r"en lo particular|en particular", q):
            return _out("To approve {0} in its articles (after its approval in general).".format(what),
                        "Against approving those articles.", "amendment: en lo particular", quality)
        part = " (the part needing a two-thirds majority)" if re.search(TWO_THIRDS, q) else ""
        for pat, label in NAMED_PART:
            if not re.search(pat, q):
                continue
            if label is None:          # Brazil's destaque: "Mantido o texto"
                return _out("To keep the challenged part of {0} as drafted.".format(what),
                            "To strike the challenged part out.", "amendment: destaque", quality)
            n = re.search(r"\bodg\s+([\w.]+)|ordine del giorno\s+(?:n\.\s*)?([\w.]+)", q)
            label = label.format(n=(n.group(1) or n.group(2)).upper() if n else "",
                                 mover=_mover(question)).replace("  ", " ").replace(" (", " (", 1)
            label = re.sub(r"order of the day \(", "order of the day (", label)
            joiner = " on " if re.search(r"order of the day|resolution", label) else " to "
            return _out("To adopt {0}{1}{2}{3}.".format(label, part, joiner, what),
                        "Against adopting it.", "amendment: " + pat.split("|")[0], quality)
        label = _amendment_label(question)
        if label:
            joiner = " of " if label.startswith("article") else " to "
            return _out("To adopt {0}{1}{2}{3}.".format(label, part, joiner, what),
                        "Against adopting it, leaving the text as it stood.", "amendment", quality)
        quote = clip(question, 70)
        return _out("To adopt the amendment or part put to the vote (\u201c{0}\u201d) on {1}.".format(
            quote, what), "Against adopting it, leaving the text as it stood.", "amendment",
            "title")
    if kind == "other":
        for pat, yes, no in NAMED_OTHER:
            if re.search(pat, q):
                return _out(_subst(yes, what), no, "named: " + pat.split("|")[0], quality)
        return None
    if kind == "procedural":
        for pat, yes, no in NAMED_PROCEDURE:
            if re.search(pat, q):
                return _out(_subst(yes, what), no, "procedural: " + pat.split("|")[0], quality)
        return _out("To agree the procedural motion (\u201c{0}\u201d) on {1}: the handling, not the "
                    "substance.".format(clip(question, 60), what),
                    "Against that procedural motion.", "procedural", quality)
    return None


def _out(yes, no, basis, quality):
    return {"yes": clip(yes, MAX_LINE), "no": clip(no, MAX_LINE), "basis": basis,
            "quality": quality}


def _ch_rule(r, what, english):
    ys, ns = clean(r.get("meaning_yes")).strip(" *"), clean(r.get("meaning_no")).strip(" *")
    ye, ne = ch_phrase(ys), ch_phrase(ns)
    on = " on {0}".format(what) if what else ""
    if ye and ne:
        if what and ye.endswith((" it", " the bill")):
            return _out("For {0} {1}.".format(ye.rsplit(" ", 2 if ye.endswith(" the bill") else 1)[0],
                                               what), "For {0}.".format(ne),
                        "the Council's own meaning lines", "full" if english else "title")
        return _out("For {0}{1}.".format(ye, on), "For {0}.".format(ne),
                    "the Council's own meaning lines", "full" if english or not what else "title")
    if ys and ns:
        return _out("For “{0}”{1} (the Council's own words).".format(clip(ys, 80), on),
                    "For “{0}”.".format(clip(ns, 80)), "the Council's own meaning lines",
                    "title")
    return None


# --- people's lines (file-based, like the UK's) -------------------------------------

_OVERRIDES = {}


def override_path(cc, config_dir=None):
    return os.path.join(config_dir or CONFIG, "vote-meanings-{0}.yaml".format(cc))


def overrides(cc, config_dir=None):
    """({key: {'yes', 'no', 'by', 'on'}}, [problems]) from config/vote-meanings-<cc>.yaml
    (each entry's meaning_yes and meaning_no)."""
    path = override_path(cc, config_dir)
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return {}, []
    hit = _OVERRIDES.get(path)
    if hit and hit[0] == stamp:
        return hit[1], hit[2]
    import yaml
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    good, problems = {}, []
    for key, e in (cfg.get("meanings") or {}).items():
        e = c5.norm_entry(e) if isinstance(e, dict) else {}
        yes, no = clean(e.get("meaning_yes")), clean(e.get("meaning_no"))
        if not (yes and no):
            problems.append("{0}: needs both meaning_yes and meaning_no".format(key))
            continue
        bad = refusal(yes) or refusal(no)
        if bad:
            problems.append("{0}: {1}".format(key, bad))
            continue
        good[str(key)] = {"yes": yes, "no": no, "by": clean(e.get("by")) or None,
                          "on": str(e.get("on") or "") or None}
    _OVERRIDES[path] = (stamp, good, problems)
    return good, problems


def refusal(text):
    """Why a line may not be stored or shown, or None."""
    if "citizengo" in (text or "").lower():
        return "a meaning says what a lobby voted for; which side is CitizenGO's is the stance file's"
    if len(text or "") > 400:
        return "over 400 characters"
    return None


# --- the store ------------------------------------------------------------------------

def stored(conn, cc, keys=None):
    """{division key: row dict} from vote_meanings; {} when the table is missing."""
    try:
        if keys is None:
            got = conn.execute("SELECT * FROM {0} WHERE cc=?".format(TABLE), (cc,)).fetchall()
        else:
            keys = [str(k) for k in keys]
            got = []
            for i in range(0, len(keys), 500):
                part = keys[i:i + 500]
                got += conn.execute("SELECT * FROM {0} WHERE cc=? AND division_key IN ({1})".format(
                    TABLE, ",".join("?" * len(part))), [cc] + part).fetchall()
    except sqlite3.OperationalError:
        return {}
    cols = ("cc", "division_key", "meaning_yes", "meaning_no", "source", "basis", "quality",
            "made_on")
    return {str(r[1]): dict(zip(cols, tuple(r))) for r in got}


def division_rows(conn, cc, keys):
    """{key: country5ca division row} for these keys (watch_key filled)."""
    spec = c5.SPECS[cc]
    keys = [str(k) for k in keys]
    out = {}
    for i in range(0, len(keys), 400):
        part = keys[i:i + 400]
        sql = "SELECT * FROM ({0}) WHERE CAST(key AS TEXT) IN ({1})".format(
            spec.div_sql, ",".join("?" * len(part)))
        for r in c5._rows(conn, sql, part):
            r["key"] = str(r["key"])
            r["date"] = str(r.get("date") or "")[:10]
            out[r["key"]] = r
    return out


def watchlist(cc, config_dir=None):
    """The country's watchlist, read from `config_dir` when given."""
    try:
        if config_dir is None:
            spec = c5.SPECS[cc]
            return (spec.watchlist_fn() if spec.watchlist_fn else {}) or {}
        from src import edition_judge
        if cc in edition_judge.EDITION_CCS:
            from src import country_edition as ce
            return ce.watchlist_of(ce.adapter(cc), config_dir) or {}
        from src import latam
        return latam.watchlist(cc, config_dir) or {}
    except Exception:            # a missing or broken watchlist names nothing
        return {}


def _context(cc, config_dir=None, wl=None):
    if wl is None:
        wl = watchlist(cc, config_dir)
    try:
        _, bills, _ = c5.load(cc, config_dir)
    except Exception:
        bills = {}
    return wl or {}, bills


def resolve(cc, key, row=None, store_row=None, people=None, wl=None, bills=None):
    """The meaning shown for one division: {'yes', 'no', 'source', 'by',
    'basis', 'quality'} or None. A person's line, then the judge's, then the
    stored rule line, then the rule computed now."""
    key = str(key)
    if people and key in people:
        p = people[key]
        return {"yes": p["yes"], "no": p["no"], "source": "person", "by": p.get("by") or "a person",
                "basis": "config/vote-meanings-{0}.yaml".format(cc), "quality": "full"}
    if store_row and store_row.get("source") == "judge" and store_row.get("meaning_yes"):
        return {"yes": store_row["meaning_yes"], "no": store_row["meaning_no"], "source": "judge",
                "by": None, "basis": store_row.get("basis"), "quality": store_row.get("quality")}
    if row is not None:
        got = rule_meaning(cc, row, wl, bills)
        if got:
            return dict(got, source="rule", by=None)
    if store_row and store_row.get("source") == "rule" and store_row.get("meaning_yes"):
        return {"yes": store_row["meaning_yes"], "no": store_row["meaning_no"], "source": "rule",
                "by": None, "basis": store_row.get("basis"), "quality": store_row.get("quality")}
    return None


def lookup_many(conn, cc, keys, config_dir=None, wl=None):
    """{key: meaning} for division keys of one country (see resolve)."""
    if cc not in c5.SPECS or not keys:
        return {}
    keys = sorted({str(k) for k in keys})
    people, _ = overrides(cc, config_dir)
    wl, bills = _context(cc, config_dir, wl)
    rows = division_rows(conn, cc, keys) if conn is not None else {}
    for r in rows.values():
        r["watch_key"] = c5.watched_key(c5.SPECS[cc], r, wl)
    st = stored(conn, cc, keys) if conn is not None else {}
    out = {}
    for k in keys:
        got = resolve(cc, k, rows.get(k), st.get(k), people, wl, bills)
        if got:
            out[k] = got
    return out


def lookup(conn, cc, key, config_dir=None, wl=None):
    return lookup_many(conn, cc, [key], config_dir, wl).get(str(key))


def entry_meaning(cc, e, config_dir=None, people=None, wl=None, bills=None):
    """A meaning for a stance-file entry without a store (the readings guide
    when no store is open): a person's line, else the rule over the entry's
    own wording, subject and watched key."""
    row = {"key": str(e.get("key")), "question": e.get("title"), "subject": e.get("on"),
           "watch_key": e.get("watched")}
    for col in ("bill_key", "bill_keys", "dossier_ref", "process_keys", "zaak_nummer", "dossiers",
                "dossier_key", "item_key", "ini_key", "initiative_key", "exp_keys", "exp_others",
                "ini_keys", "linked_bills", "former_keys", "boletin", "bill_refs", "expediente",
                "iniciativa", "paper_key", "tid", "short_number", "business_id", "is_final",
                "yes_means_reject", "procedural", "rule", "votaciont", "meaning_yes", "meaning_no"):
        row.setdefault(col, None)
    if e.get("vote_kind") in ("procedural",) and not row["question"]:
        return None
    if people is None:
        people, _ = overrides(cc, config_dir)
    if wl is None or bills is None:
        wl, bills = _context(cc, config_dir)
    return resolve(cc, row["key"], row, None, people, wl, bills)


# --- items: the editions, briefs and profiles -----------------------------------------

def item_key(it):
    return str(it.get("division") or it["key"])


def wants_meaning(it):
    return it.get("kind") == "vote" and (it.get("watched") or it.get("tier") == 1)


def annotate(conn, items, config_dir=None):
    """Put `meaning` on every watched or tier-1 vote item of a country with
    recorded votes. Returns items. Never fails an edition: a problem leaves
    the items as they were."""
    try:
        by_cc = {}
        for it in items:
            if wants_meaning(it) and it.get("cc") in c5.SPECS:
                by_cc.setdefault(it["cc"], []).append(it)
        for cc, its in by_cc.items():
            got = lookup_many(conn, cc, [item_key(it) for it in its], config_dir)
            for it in its:
                m = got.get(item_key(it))
                if m:
                    it["meaning"] = m
    except Exception:                       # pragma: no cover - a guard, logged nowhere
        pass
    return items


def source_text(m):
    words = SOURCE_WORDS.get(m.get("source"), m.get("source") or "")
    return words.format(by=m.get("by") or "a person")


def line(it_or_meaning, cc=None, prefix="Meaning"):
    """'Meaning: Za = to pass ...; Przeciw = against passing it (by rule, ...).'
    for an item with `meaning` (or a meaning dict and its country), else None."""
    if not it_or_meaning:
        return None
    m = it_or_meaning.get("meaning") if "meaning" in it_or_meaning else it_or_meaning
    cc = cc or it_or_meaning.get("cc")
    if not m or not m.get("yes"):
        return None
    yes_label, no_label = labels(cc)
    return "{0}: **{1}** = {2} **{3}** = {4} _({5})_".format(
        prefix, yes_label, lower_first(m["yes"]).rstrip(".") + ";", no_label,
        lower_first(m["no"]).rstrip(".") + ".", source_text(m))


def labels(cc):
    spec = c5.SPECS.get(cc)
    return spec.labels if spec else ("Yes", "No")


def lower_first(text):
    text = clean(text)
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


def for_position(m, cc, position):
    """The meaning of one member's recorded position: the yes or no line, or None."""
    if not m:
        return None
    side = c5.SPECS[cc].side(position) if cc in c5.SPECS else None
    if side == "yea":
        return m["yes"]
    if side == "nay":
        return m["no"]
    return None


# --- writing the rule lines; what the judge is offered ---------------------------------

def qualifying(conn, cc, config_dir=None, wl=None):
    """The watched and tier-1 divisions (country5ca's selection), newest first."""
    wl, _ = _context(cc, config_dir, wl)
    rows = c5.qualifying(conn, cc, wl)
    rows.sort(key=lambda r: (str(r.get("date") or ""), r["key"]), reverse=True)
    return rows


def write_rules(conn, cc, today=None, config_dir=None, log=print, wl=None):
    """Store the rule line of every qualifying division of one country, never
    over a judge's row; a stale rule row is refreshed. Returns counts."""
    ensure_table(conn)
    today = today or datetime.date.today().isoformat()
    wl, bills = _context(cc, config_dir, wl)
    st = stored(conn, cc)
    counts = {"divisions": 0, "rule": 0, "title": 0, "none": 0, "judge": 0, "written": 0}
    for r in qualifying(conn, cc, config_dir, wl):
        counts["divisions"] += 1
        old = st.get(r["key"])
        if old and old["source"] in ("judge", "judge-unclear"):
            counts["judge"] += 1
            if old["source"] == "judge":
                continue
        got = rule_meaning(cc, r, wl, bills)
        if not got:
            counts["none"] += 1
            continue
        counts["rule"] += 1
        if got["quality"] == "title":
            counts["title"] += 1
        if old and old["source"] == "judge-unclear":
            continue
        if old and (old["meaning_yes"], old["meaning_no"], old["quality"]) == (
                got["yes"], got["no"], got["quality"]):
            continue
        conn.execute("INSERT OR REPLACE INTO {0} (cc, division_key, meaning_yes, meaning_no, source, "
                     "basis, quality, made_on) VALUES (?,?,?,?,?,?,?,?)".format(TABLE),
                     (cc, r["key"], got["yes"], got["no"], "rule", got["basis"], got["quality"], today))
        counts["written"] += 1
    conn.commit()
    log("{0}: {1} watched or tier-1 vote(s): {2} with a rule line ({3} quoting the source), "
        "{4} the rules cannot read, {5} read by the judge; {6} row(s) written".format(
            c5.SPECS[cc].name, counts["divisions"], counts["rule"], counts["title"], counts["none"],
            counts["judge"], counts["written"]))
    return counts


def pending(conn, ccs=None, config_dir=None, wls=None):
    """What the session judge is offered: qualifying divisions with no
    person's line and no judge row, whose rule line is missing or quotes the
    source. Order: no rule line first, then watched, then newest."""
    out = []
    for cc in ccs or c5.COUNTRIES:
        people, _ = overrides(cc, config_dir)
        wl, bills = _context(cc, config_dir, (wls or {}).get(cc))
        st = stored(conn, cc)
        for r in qualifying(conn, cc, config_dir, wl):
            if r["key"] in people:
                continue
            old = st.get(r["key"])
            if old and old["source"] in ("judge", "judge-unclear"):
                continue
            got = rule_meaning(cc, r, wl, bills)
            if got and got["quality"] == "full":
                continue
            out.append({"cc": cc, "row": r, "rule": got, "wl": wl})
    out.sort(key=lambda p: (p["rule"] is not None, p["row"].get("watch_key") is None,
                            _neg(p["row"].get("date")), p["cc"], p["row"]["key"]))
    return out


def _neg(iso):
    try:
        return -datetime.date.fromisoformat(str(iso)[:10]).toordinal()
    except ValueError:
        return 0


def item_id(cc, key):
    return re.sub(r"\s+", "_", "{0}:{1}".format(cc, key).strip())


def write_judged(conn, cc, key, yes, no, today, unclear=False):
    ensure_table(conn)
    conn.execute("INSERT OR REPLACE INTO {0} (cc, division_key, meaning_yes, meaning_no, source, basis, "
                 "quality, made_on) VALUES (?,?,?,?,?,?,?,?)".format(TABLE),
                 (cc, key, None if unclear else yes, None if unclear else no,
                  "judge-unclear" if unclear else "judge", SESSION_MODEL, "full", today))


def judged_on(conn, today):
    """Country codes with a judge line written on `today`."""
    try:
        return {r[0] for r in conn.execute("SELECT DISTINCT cc FROM {0} WHERE source='judge' AND "
                                           "made_on=?".format(TABLE), (today,))}
    except sqlite3.OperationalError:
        return set()


def counts(conn, cc, config_dir=None, wl=None):
    """{'votes', 'person', 'judge', 'rule_full', 'rule_title', 'none'} for one country."""
    people, _ = overrides(cc, config_dir)
    wl, bills = _context(cc, config_dir, wl)
    st = stored(conn, cc)
    out = {"votes": 0, "person": 0, "judge": 0, "rule_full": 0, "rule_title": 0, "none": 0}
    for r in qualifying(conn, cc, config_dir, wl):
        out["votes"] += 1
        m = resolve(cc, r["key"], r, st.get(r["key"]), people, wl, bills)
        if not m:
            out["none"] += 1
        elif m["source"] in ("person", "judge"):
            out[m["source"]] += 1
        else:
            out["rule_full" if m["quality"] == "full" else "rule_title"] += 1
    return out
