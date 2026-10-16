"""The countdown layout for the fifteen country editions (16 October 2026).

Chris asked for the UK weekly's "A · Countdown" layout (PRs #205-#210,
src/countdown.py) on every country edition rendered by
src/country_edition.py: Spain, Italy, France, the Netherlands, Belgium,
Austria, Switzerland, Poland, Portugal, Croatia, Slovakia, Hungary, Brazil,
Argentina and Mexico. Same structure per country, in this order:

  * the header (the edition's title and subtitle lines as before, the
    sample / draft / notice / review lines) and a SITTING-DAYS line built
    only from what each source says (sitting_line below);
  * BIG DATES: timeline rows the free session judge scored 3, inside the
    8-week horizon, at most three, nearest first, never a private or closed
    sitting, each with a Context line citing the last recorded vote on the
    same bill where the store has one (else the judge's why-line);
  * THIS WEEK (the edition day to the Sunday of the coming week) and
    FURTHER AFIELD (the next Monday to 8 weeks on) tables, columns When |
    Where | What | Issue, one date format ("Thu 22 Oct"), every row tagged
    with where it happens (WHERE below: the chamber, a regional parliament,
    GOVT, a regulator, DEADLINE);
  * KEY QUESTIONS: parliamentary questions on our ground from the last
    three weeks, ranked by the judge's score then recency (a question the
    judge has not read ranks by its tier: tier 1 counts 2, tier 2 counts 1;
    only 2 and 3 show), one member's questions of one day on one area as one
    row, at most six;
  * PETITIONS and CONSULTATIONS, from src/petitions.py's country_petitions
    (a consultation closing inside the horizon is a GOVT row of the tables
    instead, so nothing prints twice);
  * GOVERNMENT PUBLICATIONS from the `gov_docs` table (another collector,
    16 October 2026), skipped with a coverage line while it is absent;
  * REFERENCE: a board of the watched bills with Where, then every section
    the classic edition carried (in brief, recorded votes, new items, stage
    moves, reports, laws, courts, petitions, questions, speeches, the
    watchlist, the regional sections, coverage), demoted one level. No
    "Latest votes" block and no "Also announced, not on our issues" (Chris
    removed both from the UK); the window's recorded votes stay as the
    classic section they always were, under Reference.

WHERE THE ROWS COME FROM, read only: the latest run of each country's
agenda (src/agenda.py, country_agenda; the collector now reads 9 weeks
ahead where the source publishes that far), the adapter's
`timeline_extra` hook (France's scheduled dossier acts, Croatia's session
agenda), the regional parliaments' forward agendas (`regional_agenda`,
another collector; read when present), gov_docs consultations and
country_petitions closing dates. Every row is an edition item of kind
"agenda" (forward_items), so the session judge reads it with the watched
bill's why-line (tools/edition_judge.py) exactly as the UK judge reads
What's On rows with the board's "why we track it".

Nothing here writes to the store.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import json
import re

from src import countdown as cd
from src import country_edition as ce
from src import edition_judge

# Countries whose own adapter emits questions (the rest store theirs in the
# chamber layer's <cc>_questions, src/chamber_store.py).
ADAPTER_QUESTIONS = ("at", "be", "hu")
KEY_QUESTIONS_DAYS = 21
KEY_QUESTIONS_MAX = 6
PETITIONS_MAX = 6
CONSULTATIONS_MAX = 8
PUBLICATIONS_MAX = 5
VOTE_LOOKBACK_DAYS = 365
MAX_TITLE = 220
GOVT, DEADLINE, REGULATOR = "GOVT", "DEADLINE", "REGULATOR"
GOV_DOCS_NOTE = "Government publications: not collected yet (gov_docs)."
REGIONAL_NOTE = "Regional parliaments' forward agendas: not collected yet (regional_agenda)."

# The national chamber tags: (pattern on the agenda point's body, tag),
# first match wins, then the default.
WHERE = {
    "nl": ((r"eerste kamer", "EERSTE KAMER"),), "nl_default": "TWEEDE KAMER",
    "at": ((r"bundesrat", "BUNDESRAT"),), "at_default": "NATIONALRAT",
    "ch": ((r"st[äa]nderat|conseil des [ée]tats|consiglio degli stati", "STÄNDERAT"),
           (r"nationalrat|conseil national|consiglio nazionale", "NATIONALRAT")),
    "ch_default": "BUNDESVERSAMMLUNG",
    "pl": ((r"\bsenat", "SENAT"),), "pl_default": "SEJM",
    "br": ((r"^senado|senado federal", "SENADO"),), "br_default": "CÂMARA",
    "it": ((r"senato", "SENATO"),), "it_default": "CAMERA",
    "fr": ((r"s[ée]nat", "SÉNAT"),), "fr_default": "ASSEMBLÉE NATIONALE",
    "es": ((r"^senado|senado,", "SENADO"),), "es_default": "CONGRESO",
    "be": (), "be_default": "CHAMBER",
    "pt": (), "pt_default": "ASSEMBLEIA DA REPÚBLICA",
    "sk": (), "sk_default": "NÁRODNÁ RADA",
    "ar": ((r"diputados", "DIPUTADOS"),), "ar_default": "SENADO",
    "hr": (), "hr_default": "SABOR",
    "hu": (), "hu_default": "ORSZÁGGYŰLÉS",
    "mx": ((r"senado", "SENADO"),), "mx_default": "DIPUTADOS",
    # Germany (16 October 2026, tools/de_monitor.py): the shared agenda reads
    # the Bundestag only (src/agendas/de.py); a Bundesrat row would say so.
    "de": ((r"^bundesrat", "BUNDESRAT"),), "de_default": "BUNDESTAG",
}

# A regional parliament's tag: the template filled with the row's region
# (or body), upper case.
REGION_TAG = {"at": "LANDTAG {region}", "ch": "CANTON {region}", "it": "CONSIGLIO {region}",
              "es": "PARLAMENTO {region}", "pl": "SEJMIK {region}", "br": "ASSEMBLEIA {region}",
              "mx": "CONGRESO {region}", "ar": "LEGISLATURA {region}", "be": "{body}",
              "fr": "{body}", "nl": "PROVINCIE {region}", "pt": "{body}", "de": "LANDTAG {region}"}

# A body whose name says it is a regulator or agency, not the government.
_REGULATOR = re.compile(r"\b(autoriteit|authority|agentur|agence|ag[êe]ncia|agencia|beh[öo]rde|"
                        r"regulator|toezicht|r[ée]gulation|regulaci[óo]n|regula[çc][ãa]o|"
                        r"commissariaat|anvisa|ofcom)\b", re.I)


def chamber_tag(cc, body):
    for pattern, tag in WHERE.get(cc, ()):
        if re.search(pattern, body or "", re.I):
            return tag
    return WHERE.get(cc + "_default") or cc.upper()


def region_tag(cc, region, body):
    tmpl = REGION_TAG.get(cc, "{region}")
    text = tmpl.format(region=ce.clean(region) or ce.clean(body), body=ce.clean(body) or ce.clean(region))
    return text.upper().strip() or "REGION"


def govt_tag(body):
    """GOVT for a ministry or the government; the body's own name for a
    regulator or agency (short), REGULATOR when the name is long."""
    name = ce.clean(body)
    if name and _REGULATOR.search(name):
        return name.upper() if len(name) <= 30 else REGULATOR
    return GOVT


# --- windows ------------------------------------------------------------------

def windows(today):
    """(start, week_end, further_start, horizon_end) as dates. THIS WEEK runs
    from the edition day to the Sunday of the coming week (an edition dated
    Saturday 17 October covers Sat 17 to Sun 25); FURTHER AFIELD from the
    next Monday for 8 weeks, as the UK's (src/countdown.windows)."""
    t = datetime.date.fromisoformat(today)
    monday = t if t.weekday() == 0 else t + datetime.timedelta(days=7 - t.weekday())
    _ws, we, fs, he = cd.windows(monday.isoformat())
    return t, we, fs, he


# --- rows ---------------------------------------------------------------------

@dataclasses.dataclass
class CRow(cd.Row):
    """A countdown row with what a country row needs besides: the label for
    an undated row ("This session", "Pending"), the keys it names (bills,
    watchlist), the item it came from, and the takeaway."""
    when_text: str = None
    keys: list = dataclasses.field(default_factory=list)
    item: dict = None
    watched: bool = False
    board_keys: list = None     # every key of a folded meeting's points (the board's Next)

    @property
    def when(self):
        if self.running:
            return self.when_text or "Pending"
        return cd.day_label(self.date)


def _loads(raw):
    try:
        got = json.loads(raw) if isinstance(raw, str) else (raw or [])
    except (TypeError, ValueError):
        return []
    return list(got) if isinstance(got, list) else []


def _short(*parts):
    return hashlib.sha1("|".join(str(p or "") for p in parts).encode("utf-8")).hexdigest()[:12]


def _table(conn, name):
    return bool(ce.rows(conn, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)))


def _select(conn, table, cols, where="", params=()):
    have = {c[1] for c in ce.rows(conn, "PRAGMA table_info({0})".format(table))}
    sel = ", ".join(c if c in have else "NULL AS {0}".format(c) for c in cols)
    return ce.rows(conn, "SELECT {0} FROM {1} {2}".format(sel, table, where), params)


def _agenda_module(cc):
    try:
        from src import agenda
        return agenda.module(cc)
    except ImportError:
        return None


def agenda_items(conn, cc, today, until, wl):
    """The latest agenda run's points dated today to `until`, on our ground
    or watched: one item per point (kind "agenda", key the point's id), with
    where/detail/keys for the row."""
    from src import agenda
    if _agenda_module(cc) is None:
        return []
    run = agenda.latest_run(conn, cc)
    if not run:
        return []
    out = []
    for r in ce.rows(conn, "SELECT * FROM country_agenda WHERE cc = ? AND last_seen = ? AND date >= ? "
                           "AND date <= ? ORDER BY date, time, item_id", (cc, run[0], today, until)):
        refs = agenda.loads(r["refs"])
        bills = agenda.loads(r["bill_keys"])
        keys = list(dict.fromkeys(bills + refs))
        watched = [k for k in keys if k in wl]
        areas = ce.areas_of(r["areas"])
        if not areas and not watched:
            continue
        it = ce.item(cc, "agenda", r["item_id"], r["date"], r["title"], areas, r["tier"],
                     bool(watched), status=r["status"], url=r["url"], terms=r["matched_terms"],
                     body=r["detail"] or "",
                     own=(True if ce.areas_of(r["own_areas"]) else False if areas else None),
                     watch_key=watched[0] if watched else None)
        body = ce.clean(r["body"])
        it.update(where=chamber_tag(cc, body), detail=_detail(body, r["kind"]),
                  time=r["time"], keys=keys, session=r["status"])
        it["takeaway"] = "{0}, {1}".format(it["where"].title(), it["detail"] or "sitting")
        out.append(it)
    return out


def _detail(body, kind):
    """'plenary', or the committee's name, from an agenda point's body."""
    b = ce.clean(body)
    low = b.lower()
    if kind == "plenary" or low in ("plenary", "pleno", "plenário", "plenaire", "séance publique",
                                    "assembly", "plenum"):
        return "plenary" if low in ("plenary", "pleno", "plenário", "plenaire", "assembly", "plenum", "") \
            else b
    # 'Câmara, Comissão de ...' / 'Senado, committee': the chamber is the tag.
    b = re.sub(r"^(câmara|senado|camera|senato|nationalrat|bundesrat)\s*,\s*", "", b, flags=re.I)
    return b or kind or None


def regional_items(conn, cc, today, until):
    """regional_agenda rows (another collector, 16 October 2026) dated today
    to `until` on our ground; [] while the table is absent."""
    if not _table(conn, "regional_agenda"):
        return []
    out = []
    for r in _select(conn, "regional_agenda", ("cc", "region", "body", "dated", "business", "item_type",
                                               "url", "areas", "matched_terms"),
                     "WHERE cc = ? AND substr(dated,1,10) >= ? AND substr(dated,1,10) <= ? "
                     "ORDER BY dated", (cc, today, until)):
        areas = ce.areas_of(r["areas"])
        if not areas:
            continue
        key = "reg:" + _short(r["region"], r["dated"], r["business"])
        it = ce.item(cc, "agenda", key, (r["dated"] or "")[:10], r["business"], areas, 2, False,
                     url=r["url"], terms=r["matched_terms"])
        it.update(where=region_tag(cc, r["region"], r["body"]),
                  detail=", ".join(x for x in (ce.clean(r["item_type"]),
                                               ce.clean(r["body"]) if REGION_TAG.get(cc, "").find("{body}") < 0
                                               else "") if x) or None,
                  region=ce.clean(r["region"]) or ce.clean(r["body"]), keys=[])
        out.append(it)
    return out


def gov_consultation_items(conn, cc, today, until):
    """gov_docs consultations closing today to `until` (GOVT rows)."""
    if not _table(conn, "gov_docs"):
        return []
    out = []
    for r in _select(conn, "gov_docs", ("cc", "doc_id", "title", "doc_type", "body", "published",
                                        "closing_date", "url", "areas", "matched_terms"),
                     "WHERE cc = ? AND closing_date IS NOT NULL AND substr(closing_date,1,10) >= ? "
                     "AND substr(closing_date,1,10) <= ?", (cc, today, until)):
        areas = ce.areas_of(r["areas"])
        if not areas or "consult" not in (r["doc_type"] or "consultation").lower():
            continue
        it = ce.item(cc, "agenda", "gov:" + str(r["doc_id"]), r["closing_date"][:10], r["title"], areas,
                     2, False, url=r["url"], terms=r["matched_terms"])
        it.update(where=govt_tag(r["body"]), detail=cd.deadline_detail(r["title"], r["doc_type"]),
                  extra=ce.clean(r["body"]) or None, keys=[], deadline=True)
        out.append(it)
    return out


def petition_deadline_items(conn, cc, today, until, wl):
    """country_petitions closing today to `until`, on our ground or watched:
    a consultation is a GOVT row ("consultation closes"), a petition, an
    initiative or a referendum's signature period a DEADLINE row."""
    from src import petitions
    out = []
    for r in ce.rows(conn, "SELECT * FROM country_petitions WHERE cc = ? AND closes >= ? AND closes <= ? "
                           "ORDER BY closes", (cc, today, until)):
        watch = [k for k in _loads(r["watch_keys"]) + [r["item_id"], r["item_id"].split(":", 1)[-1]]
                 + _loads(r["refs"]) if k in wl]
        if not ce.on_ground(r["areas"], bool(watch)):
            continue
        consult = (r["kind"] or "") == "consultation"
        what = petitions.KINDS.get(r["kind"], (r["kind"] or "petition").capitalize())
        what = what[0] if isinstance(what, tuple) else what
        it = ce.item(cc, "agenda", "pet:" + r["item_id"], r["closes"][:10], r["title"],
                     ce.areas_of(r["areas"]), r["tier"], bool(watch), status=r["status"],
                     url=r["url"], terms=r["matched_terms"], body=r["summary"] or "",
                     watch_key=watch[0] if watch else None)
        it.update(where=govt_tag(r["body"]) if consult else DEADLINE,
                  detail=("consultation closes" if consult else
                          "{0} closes".format(str(what).lower())),
                  extra=ce.clean(r["body"]) or None, keys=_loads(r["refs"]), deadline=True,
                  petition_id=r["item_id"])
        out.append(it)
    return out


def forward_items(conn, country, today, wl, until=None):
    """Every forward item of the country's timeline, before the noise
    filters and the judge: agenda points, the adapter's extra items,
    regional agendas, government consultations and petition deadlines. The
    session judge's queue reads these (tools/edition_judge.py)."""
    cc = country.cc
    until = until or windows(today)[3].isoformat()
    got = agenda_items(conn, cc, today, until, wl)
    if country.timeline_extra:
        for it in country.timeline_extra(conn, today, until, wl) or []:
            it.setdefault("where", chamber_tag(cc, it.get("body_name") or ""))
            it.setdefault("keys", [k for k in (it.get("watch_key"), it["key"]) if k])
            got.append(it)
    got += regional_items(conn, cc, today, until)
    got += gov_consultation_items(conn, cc, today, until)
    got += petition_deadline_items(conn, cc, today, until, wl)
    for it in got:
        if not it.get("takeaway"):
            it["takeaway"] = "{0}{1}, {2}".format(
                _title(it.get("where") or "") or "Where not given",
                ", " + it["detail"] if it.get("detail") else "",
                "on " + cd.day_label(it["date"]) if it.get("date") else "not yet dated")
        it["takeaway"] = "Coming up: " + it["takeaway"] if it.get("date") and it["date"] >= today \
            and not it["takeaway"].startswith("Coming up") else it["takeaway"]
    return got


def timeline(conn, country, today, wl, config_dir=None, dropped=None):
    """The country's countdown rows: forward items noise-filtered (what the
    filters leave out goes to `dropped`), scored by the session judge where
    it has read them (an unwatched row it scored 0 leaves, counted), as
    CRow, deduplicated and folded, the big dates marked."""
    got = forward_items(conn, country, today, wl)
    kept, out = ce.noise_for(country).split(got, config_dir)
    scores = edition_judge.load(conn, {country.cc})
    for it in kept:
        if it.get("petition_id") and edition_judge.item_id(it) not in scores:
            alt = scores.get(edition_judge.item_id(dict(it, kind="petition", key=it["petition_id"])))
            if alt:
                scores[edition_judge.item_id(it)] = alt
    kept, judged_out = edition_judge.split(edition_judge.annotate(conn, kept, scores))
    if dropped is not None:
        dropped.extend(out + judged_out)
    rows = [row_of(it, wl) for it in kept]
    rows = fold(dedupe(rows), today)
    mark_big(rows, today)
    return rows


def row_of(it, wl):
    why = None
    if it.get("judge") is not None:
        why = ce.clean(it.get("judge_why")) or None
    elif it["watched"]:
        w = ce.why_watched(it, wl)
        why = "Watched: " + w if w else None
    running = bool(it.get("running")) or not it.get("date")
    return CRow(date=None if running else it["date"], where=it.get("where") or "",
                title=_title_cut(it["title"]), url=it.get("url"),
                detail=it.get("detail"), note=why, areas=list(it["areas"]), score=it.get("judge"),
                running=running, clock=cd._minutes(it.get("time")),
                kind="deadline" if it.get("deadline") else "event",
                extra_md=it.get("extra"), session=it.get("session"),
                when_text=it.get("running_label"), keys=list(it.get("keys") or []), item=it,
                watched=bool(it["watched"]))


def _title_cut(title, limit=MAX_TITLE):
    """A title shortened by sense, never with an ellipsis (src/countdown.compress)."""
    t = ce.clean(title)
    if not t:
        return "(no title published)"
    if len(t) <= limit:
        return t
    return cd.compress(t, limit)[0]


def dedupe(rows):
    seen, out = set(), []
    for r in rows:
        k = (r.date, r.where, r.title.lower()[:80])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


MEETING_MORE = 3


def _rank(r):
    tier = (r.item or {}).get("tier") or 3
    return (not r.watched, -(r.score if r.score is not None else -1), tier, r.sort_key())


def fold_meetings(rows):
    """One row per meeting: a committee's procedure meeting with thirty
    points on our ground is one row, led by its best point (watched, then
    the judge's score), the next few named after "also on the agenda" and
    the rest counted. Areas are the union; the best score and note hold."""
    out, groups = [], {}
    for r in rows:
        if r.running or r.kind != "event" or not r.date:
            out.append(r)
            continue
        k = (r.date, r.where, r.detail or "", (r.url or "").split("#")[0])
        groups.setdefault(k, []).append(r)
        if len(groups[k]) == 1:
            out.append(k)
    final = []
    for x in out:
        if not isinstance(x, tuple):
            final.append(x)
            continue
        members = sorted(groups[x], key=_rank)
        lead = members[0]
        rest = members[1:]
        if rest:
            lead.areas = sorted({a for m in members for a in m.areas})
            lead.board_keys = list(dict.fromkeys(k for m in members for k in m.keys))
            named = "; ".join(_title_cut(m.title, 90) for m in rest[:MEETING_MORE])
            more = len(rest) - MEETING_MORE
            lead.detail = "{0}; also on the agenda: {1}{2}".format(
                lead.detail or "sitting", named,
                " and {0} more on our issues".format(more) if more > 0 else "")
            lead.watched = any(m.watched for m in members)
        final.append(lead)
    return final


def fold(rows, today):
    """One row per meeting (fold_meetings), then one row per bill (or per
    title) per table: a bill on three agendas in the coming week keeps its
    first sitting's row and the later dates ride on it ("then Wed 21 Oct,
    Thu 22 Oct"); the higher score wins."""
    _ws, we, _fs, _he = windows(today)
    out, groups = [], {}
    for r in fold_meetings(sorted(rows, key=lambda r: r.sort_key())):
        if r.running or r.kind == "deadline" or not r.date:
            out.append(r)
            continue
        table = "week" if datetime.date.fromisoformat(r.date) <= we else "further"
        ident = r.keys[0] if r.keys else ce.noise_mod.fold(r.title)[:80]
        k = (table, r.where, ident)
        first = groups.get(k)
        if first is None:
            groups[k] = r
            out.append(r)
            continue
        if r.date != first.date and r.date not in first.also:
            first.also.append(r.date)
        if (r.score or -1) > (first.score if first.score is not None else -1):
            first.score, first.note = r.score, r.note or first.note
        first.watched = first.watched or r.watched
    return out


def mark_big(rows, today, limit=cd.BIG_MAX):
    """Up to `limit` dated rows the judge scored 3 inside the horizon,
    nearest first; never a private or closed sitting (src/countdown.is_private)."""
    ws, _we, _fs, he = windows(today)
    for r in rows:
        r.big = False
    cands = sorted((r for r in rows if not r.running and r.score == cd.BIG_SCORE and r.date
                    and ws <= datetime.date.fromisoformat(r.date) <= he and not cd.is_private(r)),
                   key=lambda r: r.sort_key())
    for r in cands[:limit]:
        r.big = True
    return cands[:limit]


def split(rows, today):
    """(this_week, further_afield); pending rows close this week's table."""
    ws, we, fs, he = windows(today)
    this_week, further = [], []
    for r in sorted(rows, key=lambda r: r.sort_key()):
        if r.running:
            continue
        d = datetime.date.fromisoformat(r.date)
        if ws <= d <= we:
            this_week.append(r)
        elif fs <= d <= he:
            further.append(r)
    return this_week + [r for r in rows if r.running], further


# --- big-date context -----------------------------------------------------------

def votes_for_context(conn, country, today, wl):
    """The country's recorded votes over VOTE_LOOKBACK_DAYS, newest first."""
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=VOTE_LOOKBACK_DAYS)).isoformat()
    try:
        got = country.items(conn, since, today, wl) or []
    except Exception:                                   # noqa: BLE001 - context is optional
        return []
    votes = [v for v in got if v.get("kind") == "vote"]
    return sorted(votes, key=lambda v: (v.get("date") or "", v.get("key") or ""), reverse=True)


def context_for(row, votes, year):
    """The last recorded vote on a bill the row's own point names (not the
    other points of a folded meeting), else the row's note."""
    keys = {str(k) for k in (row.keys or []) if k}
    if row.item and row.item.get("watch_key"):
        keys.add(str(row.item["watch_key"]))
    if keys:
        for v in votes:
            vk = {str(x) for x in (v.get("key"), v.get("watch_key"), v.get("group"), v.get("division"))
                  if x}
            if not keys & vk:
                continue
            tally = next((ln for ln in v.get("lines") or [] if ln.startswith("Tally:")),
                         next(iter(v.get("lines") or []), ""))
            d = cd._date(v.get("date"))
            when = "{0} {1}".format(d.day, cd._MONTHS_LONG[d.month]) + ("" if d.year == year else
                                                                      " {0}".format(d.year)) if d else "?"
            title = ce.clip(v.get("title") or "", 140)
            text = "the last recorded vote on this was on {0}: “{1}”".format(when, title.rstrip("."))
            if tally:
                text += "; " + ce.clean(tally.replace("Tally: ", "")).rstrip(".")
            if v.get("url"):
                text += " ([vote]({0}))".format(v["url"])
            return text
    return row.note


# --- the sitting-days line ------------------------------------------------------

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _days_text(dates):
    ds = sorted(set(dates))
    bits = []
    for i, d in enumerate(ds):
        if i == len(ds) - 1:
            bits.append("{0} {1} {2}".format(_DAYS[d.weekday()], d.day, cd._MONTHS[d.month]))
        else:
            bits.append("{0} {1}".format(_DAYS[d.weekday()], d.day))
    return bits[0] if len(bits) == 1 else ", ".join(bits[:-1]) + " and " + bits[-1]


_SMALL = {"DA", "DE", "DEL", "DES", "DI", "LA", "DO", "DOS"}
_NAMES = {"ASSEMBLÉE NATIONALE": "Assemblée nationale", "NÁRODNÁ RADA": "Národná rada",
          "BUNDESVERSAMMLUNG": "Federal Assembly", "CHAMBER": "Chamber"}
_RUN = re.compile(r"\((\d+) days?, to (\d{1,2}) ([A-Za-z]{3})", re.I)
_MON = {m.lower(): i for i, m in enumerate(cd._MONTHS) if m}


def _sitting_days(p):
    """The days a plenary point's sitting runs: its date, or the run its body
    prints ('Plenary, sitting 67 (4 days, to 23 Oct)', Poland)."""
    d = datetime.date.fromisoformat(p["date"])
    m = _RUN.search(p["body"] or "")
    if not m or m.group(3).lower() not in _MON:
        return [d]
    try:
        end = datetime.date(d.year, _MON[m.group(3).lower()], int(m.group(2)))
    except ValueError:
        return [d]
    if end < d:
        end = end.replace(year=d.year + 1)
    return [d + datetime.timedelta(days=i) for i in range(min((end - d).days, 14) + 1)]


def _title(tag):
    """'TWEEDE KAMER' -> 'Tweede Kamer'; 'ASSEMBLEIA DA REPÚBLICA' ->
    'Assembleia da República'."""
    if tag in _NAMES:
        return _NAMES[tag]
    words = tag.split()
    return " ".join(w.lower() if i and w in _SMALL else w.capitalize() for i, w in enumerate(words))


def sitting_line(conn, country, today, rows=None):
    """(line, missing): who sits this week, from the country's own agenda
    (country_agenda's latest run: the plenary days it lists this week per
    chamber, else the committee days, else the next sitting it names) and the
    regional parliaments shown in the edition (regional_agenda). A chamber
    the source does not cover is left out and named in `missing`; nothing
    is guessed."""
    from src import agenda
    cc = country.cc
    ws, we, _fs, _he = windows(today)
    parts, missing = [], []
    run = agenda.latest_run(conn, cc) if _agenda_module(cc) is not None else None
    if not run:
        missing.append("the national agenda" + ("" if _agenda_module(cc) is not None
                                                 else " (no agenda source is collected)"))
    else:
        run_date, _items, _ground, horizon, next_sitting, run_note = run
        pts = ce.rows(conn, "SELECT date, body, kind FROM country_agenda WHERE cc = ? AND last_seen = ?",
                      (cc, run_date))
        plenary_tags = {chamber_tag(cc, p["body"]) for p in ce.rows(
            conn, "SELECT DISTINCT body FROM country_agenda WHERE cc = ? AND kind = 'plenary'", (cc,))}
        tags = []
        for p in pts:
            t = chamber_tag(cc, p["body"])
            if t not in tags:
                tags.append(t)
        for t in sorted(plenary_tags):
            if t not in tags:
                tags.append(t)
        default = WHERE.get(cc + "_default")
        tags.sort(key=lambda t: t != default)          # the lower house (the default tag) first
        for tag in tags:
            mine = [p for p in pts if chamber_tag(cc, p["body"]) == tag and p["date"]]
            week = [datetime.date.fromisoformat(p["date"]) for p in mine
                    if ws.isoformat() <= p["date"] <= we.isoformat()]
            plen = [d for p in mine if p["kind"] == "plenary" for d in _sitting_days(p)
                    if ws <= d <= we]
            name = _title(tag)
            if plen:
                parts.append("{0} sitting (plenary {1})".format(name, _days_text(plen)))
            elif tag in plenary_tags:
                later = sorted(p["date"] for p in mine if p["kind"] == "plenary" and p["date"] > we.isoformat())
                nxt = later[0] if later else (next_sitting if next_sitting and next_sitting > we.isoformat()
                                              else None)
                text = "{0}: no plenary on the published agenda this week".format(name)
                if week:
                    text += " (committees meeting {0})".format(_days_text(week))
                if nxt:
                    text += ", next plenary {0}".format(cd.day_label(nxt))
                elif horizon and horizon < we.isoformat():
                    text += " (published to {0})".format(cd.day_label(horizon))
                parts.append(text)
            elif week:
                parts.append("{0}: committees meeting {1}".format(name, _days_text(week)))
            else:
                parts.append("{0}: nothing on the published agenda this week{1}".format(
                    name, " (published to {0})".format(cd.day_label(horizon))
                    if horizon and horizon < we.isoformat() else ""))
        if not tags:
            parts.append("{0}: nothing on the published agenda{1}".format(
                _title(WHERE.get(cc + "_default") or cc.upper()),
                "; " + ce.clean(run_note).rstrip(".")[:1].lower() + ce.clean(run_note).rstrip(".")[1:]
                if run_note else ""))
        if run_date < (ws - datetime.timedelta(days=14)).isoformat():
            parts = [p + " (agenda read {0})".format(cd.day_label(run_date)) for p in parts]
    regions = []
    for r in rows or []:
        reg = (r.item or {}).get("region")
        if reg and (reg, r.where) not in regions:
            regions.append((reg, r.where))
    if regions and _table(conn, "regional_agenda"):
        for reg, tag in regions:
            got = _select(conn, "regional_agenda", ("dated",),
                          "WHERE cc = ? AND (region = ? OR body = ?) AND substr(dated,1,10) >= ? "
                          "AND substr(dated,1,10) <= ?", (cc, reg, reg, ws.isoformat(), we.isoformat()))
            days = [datetime.date.fromisoformat(g["dated"][:10]) for g in got if g["dated"]]
            if days:
                parts.append("{0}: on its agenda {1}".format(_title(tag), _days_text(days)))
    return (" · ".join(parts) if parts else None), missing


# --- key questions --------------------------------------------------------------

def _q_score(it):
    if it.get("judge") is not None:
        return it["judge"]
    return 2 if it.get("tier") == 1 else 1


def key_questions(conn, country, today, config_dir=None, limit=KEY_QUESTIONS_MAX, review=None):
    """Questions (and answers) on our ground from the last three weeks:
    the country's own question kinds and the chamber layer's
    <cc>_questions, after the noise filters and the judge; score 2 or 3
    only; one member's questions of one day on one area as one row."""
    since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=KEY_QUESTIONS_DAYS)).isoformat()
    from src import chamber_store
    wl = ce.watchlist_of(country, config_dir)
    got = []
    if country.cc in ADAPTER_QUESTIONS and (country.kinds is None or "question" in country.kinds):
        got += [it for it in (country.items(conn, since, today, wl) or [])
                if it["kind"] in ("question", "answer")]
    got += [it for it in chamber_store.edition_items(conn, country.cc, since, today, wl)
            if it["kind"] == "question"]
    kept, _ = ce.noise_for(country).split(got, config_dir)
    kept, _ = edition_judge.split(edition_judge.annotate(conn, kept))
    from src import edition_review
    kept, _ = edition_review.apply(kept, review)       # an item cut in review stays out
    table = "{0}_questions".format(country.cc)
    have = _table(conn, table)
    qs = []
    for it in kept:
        s = _q_score(it)
        if s < 2:
            continue
        meta = {}
        if have:
            r = ce.rows(conn, "SELECT asker, party, addressee, answered FROM {0} WHERE question_id = ?"
                        .format(table), (it["key"],))
            meta = dict(r[0]) if r else {}
        qs.append((s, it, meta))
    clusters, index = [], {}
    for s, it, meta in sorted(qs, key=lambda x: (-x[0], x[1]["date"] or "")):
        asker = ce.clean(meta.get("asker"))
        k = (asker.lower() or it["key"], it["date"], (it["areas"] or [0])[0])
        c = index.get(k)
        if c is None:
            c = {"date": it["date"], "asker": asker, "party": ce.clean(meta.get("party")),
                 "addressee": ce.clean(meta.get("addressee")), "answered": meta.get("answered"),
                 "score": s, "url": it.get("url"), "why": ce.clean(it.get("judge_why")) or None,
                 "areas": list(it["areas"]), "refs": [], "titles": [], "where": chamber_tag(country.cc, "")}
            index[k] = c
            clusters.append(c)
        c["refs"].append(it["key"])
        t = _title_cut(it["title"], 160)
        if t and t not in c["titles"]:
            c["titles"].append(t)
    clusters.sort(key=lambda c: c["date"] or "", reverse=True)
    clusters.sort(key=lambda c: -c["score"])
    return clusters[:limit]


def render_key_questions(rows):
    if not rows:
        return None
    out = ["## Key questions", "",
           "*The most important questions on our issues from the last three weeks, several from "
           "one member on one day as one row. Titles are the source's own.*", "",
           "| Date | Where | Question | Asked / why it matters |", "|---|---|---|---|"]
    for c in rows:
        nums = cd._numbers(c["refs"]) if len(c["refs"]) > 1 else (c["refs"][0] if c["refs"] else "")
        label = "[{0}]({1})".format(nums, c["url"]) if c.get("url") and nums else nums
        theme = "; ".join("*{0}*".format(t) for t in c["titles"][:2]) + \
            ("; and more" if len(c["titles"]) > 2 else "")
        q = ", ".join(x for x in (label, c["asker"] + (" ({0})".format(c["party"]) if c["party"] else "")
                                  if c["asker"] else "") if x)
        if theme:
            q += ": " + theme
        bits = []
        if c["addressee"]:
            asked = [a.strip() for a in c["addressee"].split(";") if a.strip()]
            bits.append("to " + asked[0] + (" and {0} more".format(len(asked) - 1) if len(asked) > 1 else ""))
        ans = c.get("answered") or ""
        if re.match(r"\d{4}-\d{2}-\d{2}", ans):
            bits.append("answered " + cd.day_label(ans)[4:])
        elif ans and ans != "untracked":
            bits.append("answered")
        if c["why"]:
            bits.append(c["why"].rstrip(".") + ".")
        last = "; ".join(bits[:-1]) + ("; " if len(bits) > 1 else "") + bits[-1] if bits else "-"
        out.append("| {0} | {1} | {2} | {3} |".format(
            cd.day_label(c["date"]), c["where"], q.replace("|", "/"), last.replace("|", "/")))
    out.append("")
    return "\n".join(out)


# --- petitions, consultations, government publications ---------------------------

# A petition the source marks withdrawn, cancelled or archived is not open.
_GONE = re.compile(r"\b(geannuleerd|ingetrokken|annul\w*|retir\w*|cancel\w*|archiv\w*|withdrawn|"
                   r"zur[üu]ckgezogen|arquivad\w*|desistid\w*)\b", re.I)


def petitions_and_consultations(conn, country, today, wl, shown_ids=()):
    """(petitions, consultations): open items on our ground or watched in
    country_petitions, read within the last three weeks. Consultations whose
    deadline row is already in the tables (shown_ids) are left out."""
    from src import petitions
    seen_since = (datetime.date.fromisoformat(today) - datetime.timedelta(days=KEY_QUESTIONS_DAYS)).isoformat()
    pets, cons = [], []
    for r in ce.rows(conn, "SELECT * FROM country_petitions WHERE cc = ? AND (closes IS NULL OR closes >= ?) "
                           "AND last_seen >= ?", (country.cc, today, seen_since)):
        watch = [k for k in _loads(r["watch_keys"]) + [r["item_id"], r["item_id"].split(":", 1)[-1]]
                 + _loads(r["refs"]) if k in wl]
        areas = ce.areas_of(r["areas"])
        if not areas and not watch:
            continue
        if _GONE.search(r["status"] or "") or _GONE.search(r["title"] or ""):
            continue
        # Still news: a count to follow, a deadline ahead, or new in the last three weeks.
        if r["signatures"] is None and not r["closes"] and (r["first_seen"] or "") < seen_since \
                and not watch:
            continue
        thresholds = [t for t in _loads(r["thresholds"]) if isinstance(t, list) and t]
        entry = {"id": r["item_id"], "title": ce.clean(r["title"]), "url": r["url"],
                 "kind": r["kind"] or "petition", "status": ce.clean(r["status"]),
                 "closes": r["closes"], "opened": r["opened"], "signatures": r["signatures"],
                 "next": petitions.next_threshold(r["signatures"], thresholds) if r["signatures"] is not None
                 else None, "body": ce.clean(r["body"]), "areas": areas, "watched": bool(watch)}
        if entry["kind"] == "consultation":
            if r["item_id"] not in shown_ids:
                cons.append(entry)
        else:
            pets.append(entry)
    pets.sort(key=lambda p: (not p["watched"], -(p["signatures"] or 0), p["title"]))
    cons.sort(key=lambda c: (c["closes"] or "9999", c["title"]))
    return pets, cons


def _issue(areas):
    return cd.issue_label(areas, ce.AREA_LABELS) or "-"


def render_petitions(pets, limit=PETITIONS_MAX):
    if not pets:
        return None
    out = ["## Petitions", "",
           "*Open petitions, citizens' initiatives and referendum drives on our issues "
           "(src/petitions.py).*", "",
           "| Petition | Signatures | Where it stands | Issue |", "|---|---|---|---|"]
    for p in pets[:limit]:
        title = "[{0}]({1})".format(p["title"], p["url"]) if p.get("url") else p["title"]
        bits = []
        if p["status"]:
            bits.append("“{0}”".format(ce.clip(p["status"], 60)))
        if p["closes"]:
            bits.append("closes " + cd.day_label(p["closes"]))
        if p["next"]:
            bits.append("{0:,} needed: {1}".format(p["next"][0], ce.clean(p["next"][1]) if len(p["next"]) > 1
                                                   else "the next threshold"))
        if p["watched"]:
            bits.append("watched")
        out.append("| {0} | {1} | {2} | {3} |".format(
            title.replace("|", "/"), "{0:,}".format(p["signatures"]) if p["signatures"] is not None else "-",
            ("; ".join(bits) or "-").replace("|", "/"), _issue(p["areas"])))
    if len(pets) > limit:
        out += ["", "*{0} more open, in the store.*".format(len(pets) - limit)]
    out.append("")
    return "\n".join(out)


def render_consultations(cons, in_tables=0, limit=CONSULTATIONS_MAX):
    if not cons and not in_tables:
        return None
    out = ["## Consultations", ""]
    intro = "*Open government consultations on our issues"
    if in_tables:
        intro += "; {0} closing inside the 8 weeks {1} rows of the tables above".format(
            in_tables, "is one of the" if in_tables == 1 else "are")
    out += [intro + ".*", ""]
    if cons:
        out += ["| Consultation | Body | Closes | Issue |", "|---|---|---|---|"]
        for c in cons[:limit]:
            title = "[{0}]({1})".format(c["title"], c["url"]) if c.get("url") else c["title"]
            out.append("| {0} | {1} | {2} | {3} |".format(
                title.replace("|", "/"), (c["body"] or "-").replace("|", "/"),
                cd.day_label(c["closes"]) if c["closes"] else "no date published", _issue(c["areas"])))
        if len(cons) > limit:
            out += ["", "*{0} more open, in the store.*".format(len(cons) - limit)]
    out.append("")
    return "\n".join(out)


def publications(conn, country, since, today):
    """(publications, note): gov_docs on our ground published in the
    edition's window (not consultations: those are rows), most matched
    terms first, at most PUBLICATIONS_MAX; note when the table is absent."""
    if not _table(conn, "gov_docs"):
        return [], GOV_DOCS_NOTE
    out = []
    for r in _select(conn, "gov_docs", ("doc_id", "title", "doc_type", "body", "published", "closing_date",
                                        "url", "areas", "matched_terms"),
                     "WHERE cc = ? AND substr(published,1,10) > ? AND substr(published,1,10) <= ?",
                     (country.cc, since, today)):
        areas = ce.areas_of(r["areas"])
        if not areas:
            continue
        if "consult" in (r["doc_type"] or "").lower() and r["closing_date"] and r["closing_date"][:10] >= today:
            continue
        out.append({"title": ce.clean(r["title"]), "url": r["url"], "type": ce.clean(r["doc_type"]).replace("_", " "),
                    "body": ce.clean(r["body"]), "date": (r["published"] or "")[:10], "areas": areas,
                    "weight": len(_loads(r["matched_terms"]))})
    out.sort(key=lambda p: p["date"], reverse=True)
    out.sort(key=lambda p: -p["weight"])
    if not out:
        return [], "Government publications (gov_docs): nothing on our ground in the window."
    return out[:PUBLICATIONS_MAX], None


def render_publications(pubs, country):
    if not pubs:
        return None
    out = ["## Government publications", "",
           "*{0} government and agency publications on our issues from this edition's window "
           "(titles verbatim).*".format(country.name), ""]
    for p in pubs:
        title = "[{0}]({1})".format(p["title"], p["url"]) if p.get("url") else p["title"]
        bits = [x for x in (p.get("body"), p.get("type")) if x]
        out.append("- {0} · {1}{2} · {3}".format(cd.day_label(p["date"])[4:] if p["date"] else "undated",
                                                 title, " ({0})".format(", ".join(bits)) if bits else "",
                                                 _issue(p["areas"])))
    out.append("")
    return "\n".join(out)


# --- the bills board -------------------------------------------------------------

def render_board(wl, rows, got):
    """Bills we track: each watchlist entry with Where (the tag of its rows
    in this edition), Next (its first row in the tables), Issue, Why, and
    Movement (its items in this edition's window)."""
    if not wl:
        return None
    nxt, where = {}, {}
    for r in sorted(rows, key=lambda r: r.sort_key()):
        for k in [(r.item or {}).get("watch_key")] + list(r.board_keys or r.keys or []):
            if k in wl:
                nxt.setdefault(k, r)
                where.setdefault(k, r.where)
    moved = {}
    for it in got:
        k = ce.watch_key(it)
        if k in wl:
            moved[k] = moved.get(k, 0) + 1
    out = ["## Bills we track", "",
           "| Bill or item | Where | Next | Issue | Why we track it | Movement |", "|---|---|---|---|---|---|"]
    def order(k):
        return (k not in nxt, k not in moved, str(k))
    for k in sorted(wl, key=order):
        e = wl[k] if isinstance(wl[k], dict) else {}
        n = nxt.get(k)
        why = ce.clip(ce.first_sentence(ce.clean(e.get("why") or "")), 200) or "-"
        areas = [int(a) for a in e.get("areas") or [] if str(a).isdigit()]
        out.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(
            str(k).replace("|", "/"), where.get(k, "-"),
            "{0}{1}".format(n.when, ", " + n.detail if n.detail else "") if n else "none set",
            _issue(areas), why.replace("|", "/"),
            "{0} item(s) this edition".format(moved[k]) if k in moved else "no change"))
    out.append("")
    return "\n".join(out)


# --- the edition ------------------------------------------------------------------

def _demote(lines):
    """The classic body under Reference: '## X' -> '### X', '### X' -> '#### X'."""
    out = []
    for ln in lines:
        m = re.match(r"^(#{2,5}) ", ln)
        out.append("#" + ln if m else ln)
    return out


def render(conn, country, today, since=None, sample=False, config_dir=None, directory=None,
           review=None, draft_until=None):
    """The countdown edition's Markdown (see the module docstring)."""
    parts = ce.render_classic(conn, country, today, since, sample, config_dir, directory, review,
                              draft_until, parts=True)
    wl, got, dropped = parts["wl"], parts["got"], parts["dropped"]
    ws, we, fs, he = windows(today)
    gone = []
    rows = timeline(conn, country, today, wl, config_dir, gone)
    big = sorted((r for r in rows if r.big), key=lambda r: r.sort_key())
    if big:
        votes = votes_for_context(conn, country, today, wl)
        for r in big:
            r.context = context_for(r, votes, ws.year)
    line, missing = sitting_line(conn, country, today, rows)

    out = list(parts["header"])
    if line:
        out += ["*Sitting this week:* {0}".format(line), ""]
    block = cd.render_big_dates(big, ce.AREA_LABELS)
    if block:
        out.append(block)
    this_week, further = split(rows, today)
    out += ["## This week · {0}".format(cd.span_label(ws, we)), ""]
    if this_week:
        out += cd.render_table(this_week, ce.AREA_LABELS)
    else:
        out.append("*Nothing on our issues in the published agendas this week.*")
    out.append("")
    out += ["## Further afield · {0}".format(cd.span_label(fs, he, long=True)), ""]
    if further:
        out += cd.render_table(further, ce.AREA_LABELS)
    else:
        out.append("*Nothing on our issues in the published agendas yet.*")
    out.append("")

    kq = key_questions(conn, country, today, config_dir, review=review)
    block = render_key_questions(kq)
    if block:
        out.append(block)
    shown = {(r.item or {}).get("petition_id") for r in rows if (r.item or {}).get("petition_id")}
    pets, cons = petitions_and_consultations(conn, country, today, wl, shown)
    in_tables = sum(1 for r in rows if (r.item or {}).get("petition_id") and r.detail == "consultation closes")
    for block in (render_petitions(pets), render_consultations(cons, in_tables)):
        if block:
            out.append(block)
    pubs, pub_note = publications(conn, country, parts["since"], today)
    block = render_publications(pubs, country)
    if block:
        out.append(block)

    out += ["## Reference", ""]
    board = render_board(wl, rows, got)
    body = list(parts["body"])
    if body and body[0].startswith("**A quiet"):
        body = ["## In brief", ""] + body
    if board:
        body = board.split("\n") + body
    notes = countdown_notes(conn, country, today, rows, gone, missing, pub_note, kq)
    body = _with_notes(body, notes)
    text = ce.finish(conn, country, today, out + body, wl)
    head, sep, tail = text.partition("\n## Reference\n")
    if not sep:
        return text
    return head + sep + "\n".join(_demote(tail.split("\n")))


def countdown_notes(conn, country, today, rows, gone, missing, pub_note, kq):
    """Coverage lines for the countdown's own blocks."""
    from src import agenda
    _ws, _we, _fs, he = windows(today)
    notes = []
    if _agenda_module(country.cc) is not None:
        notes.append("Countdown: the tables read the latest agenda run (country_agenda), "
                     "{0} row(s) on our ground or watched to {1}; the collector reads {2} days "
                     "ahead where the source publishes that far.".format(
                         len(rows), cd.day_label(he.isoformat()), agenda.FETCH_DAYS))
    else:
        notes.append("Countdown: no national agenda is collected for {0}, so the tables hold only "
                     "what other sources date (regional agendas, consultations, deadlines).".format(
                         country.name))
    if missing:
        notes.append("Sitting days: no published calendar read for {0}, so the line leaves it out."
                     .format(" or ".join(missing)))
    if not _table(conn, "regional_agenda"):
        notes.append(REGIONAL_NOTE)
    if pub_note:
        notes.append(pub_note)
    if gone:
        notes.append("Left out of the tables: {0}.".format(ce.dropped_text(gone)))
    judged = sum(1 for r in rows if r.score is not None)
    notes.append("Big dates are rows the free session judge scored 3 ({0} of {1} row(s) read so far); "
                 "a row it has not read shows on its tier and is never a big date.".format(judged, len(rows)))
    if not kq:
        notes.append("Key questions: none on our ground scored 2 or 3 (or tier 1 while unread) in "
                     "the last three weeks.")
    return notes


def _with_notes(body, notes):
    """The countdown's coverage lines at the head of the classic Coverage
    section (or appended when the body is the quiet-week form)."""
    lines = ["- " + ce.clean(n) for n in notes]
    if "## Coverage" in body:
        i = body.index("## Coverage")
        j = i + 1
        while j < len(body) and body[j] == "":
            j += 1
        return body[:j] + lines + body[j:]
    return body + ["## Coverage notes", ""] + lines + [""]


# --- the DM ------------------------------------------------------------------------

DM_WEEK_ROWS = 4


def dm_lines(conn, country, today, config_dir=None):
    """The countdown's lines for the DM (src/country_edition.dm_summary):
    the sitting-days line, each BIG DATE, and THIS WEEK's rows (the first
    few, then a count), as the UK's channel post (src/countdown.slack_post)."""
    wl = ce.watchlist_of(country, config_dir)
    rows = timeline(conn, country, today, wl, config_dir)
    line, _missing = sitting_line(conn, country, today, rows)
    out = []
    if line:
        out.append("_Sitting this week: {0}_".format(line))
    for r in sorted((r for r in rows if r.big), key=lambda r: r.sort_key()):
        out.append("*{0}* *{1}* · `{2}` {3}".format(cd.BIG_LABEL, cd.day_label(r.date), r.where,
                                                     cd._mrkdwn_link(_title_cut(r.title, 90), r.url)))
    this_week, further = split(rows, today)
    if this_week:
        out.append("*This week*: {0} row(s) on our issues.".format(len(this_week)))
        for r in this_week[:DM_WEEK_ROWS]:
            out.append("• {0} · `{1}` {2}".format(r.when, r.where, _title_cut(r.title, 90)))
        if len(this_week) > DM_WEEK_ROWS:
            out.append("+ {0} more this week, in the edition".format(len(this_week) - DM_WEEK_ROWS))
    if further:
        _ws, _we, _fs, he = windows(today)
        out.append("*Further afield*: {0} row(s) to {1}.".format(len(further), cd.day_label(he.isoformat())))
    return out
