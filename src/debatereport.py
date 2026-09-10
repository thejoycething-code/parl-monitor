"""The debate report and its social copy: one pass over a pack's speeches.

What this does NOT do: choose who was onside, invent a link, or post anything. The
onside list comes from checklist.md, which a person fills in; every URL comes from
speeches.md; and publishing is a separate, explicit step.

Shape of the output. One call returns a single markdown document with three fenced
sections, split apart here:

    <<<REPORT>>>    the 500-1000 word news report, to docs/debate-article-brief.md
    <<<SOCIAL>>>    lead posts per platform, one post per reel, a thread
    <<<SUMMARY>>>   two lines for the approval DM and the canvas's channel message

Splitting one reply beats three calls: the report and the posts have to agree about
which quotes carry the story, and a model that has just written the report is the
cheapest thing that knows.
"""

import datetime
import json
import os
import re

REPORT_MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000
WORDS_MIN, WORDS_MAX = 500, 1000
MARKERS = ("REPORT", "SOCIAL", "SUMMARY")

SYSTEM_PROMPT = """You write CitizenGO UK's report of a parliamentary debate, for our
supporters and for pick-up by friendly outlets. The house style is Right To Life UK's
debate reports: a declarative headline, the news peg in the first paragraph, MPs
introduced by party and constituency, long verbatim quotes, the Government's line, and
sources. Openly from our perspective -- the MPs who spoke for life, family and freedom
are the story -- but a news report, not a leaflet: no exhortation, no second person, no
rhetorical questions.

CitizenGO's positions: abortion (pro-life), assisted dying (opposed), youth gender
medicine (opposed to paediatric transition), conversion practices bans (concerned re
therapy, parental and religious freedom), single-sex spaces (defends sex-based rights),
parental rights in education (supports), free speech (defends, wary of online safety
overreach), freedom of religion or belief (defends), marriage and family (supports),
surrogacy (opposed to commercial surrogacy).

ABSOLUTE RULES
1. Every quotation must be copied VERBATIM from the speeches supplied. Never paraphrase
   inside quotation marks, never merge two sentences into one quote, never tidy grammar.
2. Never invent a URL, a name, a constituency, a number, a date or a vote result. Use
   only what the input gives you. If you do not have a figure, leave it out.
3. Quote and characterise as ONSIDE only the members marked confirmed onside. Members
   marked not onside may be named and summarised in the paragraph covering the other
   side, fairly, with at most one short quote each.
4. If a member's own words do not support a claim, do not make the claim.

STRUCTURE
* Headline: declarative, names the chamber's action. No colon-subtitle.
* First three paragraphs: who spoke against what and from which parties; the peg (the
  petition or bill, its number and signature count if supplied, what the law is now and
  what would change); how many spoke each way, and the Government's answer in one line.
* Body: the onside members, strongest quote first, not in speaking order. Party and
  constituency on first mention. Long block quotes for the two or three strongest.
* One paragraph for those who argued the other way, stating their best point fairly.
* One paragraph for the Minister, quoting the operative sentence.
* Continuous prose. NO subheadings. No organisation quote. No call to action.

Return EXACTLY this, and nothing outside it:

<<<REPORT>>>
(the report, %d-%d words of body text, markdown, speaker names as
[Name](hansard url) links using the urls supplied)
<<<SOCIAL>>>
(## Lead post, then ### X / ### Facebook / ### Instagram; then ## Per-speaker posts with
one short post per onside member naming the quote they are on; then ## Thread, numbered.
Use [ACTION LINK] where a link to our own page belongs -- never a real URL. Mark any MP
handle as unverified.)
<<<SUMMARY>>>
(two lines, plain text: line 1 a one-sentence summary for a Slack message; line 2 the
count of members each way)
""" % (WORDS_MIN, WORDS_MAX)


def stands_in_for_onside(speaker):
    """Provisional drafting only: the pass read 'With us' on a speaker the checklist has
    not decided either way. A checklist 'no' is never overridden."""
    return speaker.get("confirmed") not in ("yes", "no") and \
        (speaker.get("pass_read") or "").lower().startswith("with us")


def speaker_brief(speeches, max_words_each=900, max_speakers=16, provisional=False):
    """What the writer is shown: each speaker's longest contribution, their confirmed
    standing, and the Hansard url of that contribution.

    Longest contribution rather than everything they said: an intervention adds words
    and no argument, and the input is what costs money.

    `provisional` lets the stance pass stand in for a blank checklist, so a draft can
    exist the same evening (the Friday task, 2026-09-11). It is a draft and nothing
    else: publish_blockers refuses a provisional report until the checklist is confirmed
    and the report regenerated without the flag.
    """
    out = []
    for s in speeches[:max_speakers]:
        best = max(s.get("contributions") or [], key=lambda c: c.get("words") or 0, default=None)
        if not best or not (best.get("text") or "").strip():
            continue
        text = " ".join((best["text"] or "").split()[:max_words_each])
        out.append({
            "name": s["name"],
            "party": s.get("party") or "",
            "seat": s.get("seat") or "",
            "confirmed_onside": s.get("confirmed") == "yes" or (provisional and stands_in_for_onside(s)),
            "pass_read": s.get("pass_read") or "",
            "hansard_url": best.get("url") or "",
            "words": best.get("words"),
            "text": text,
        })
    return out


def build_payload(meta, speakers, model=REPORT_MODEL, provisional=False):
    user = {"debate": {"title": meta.get("title"), "date": meta.get("date"),
                       "house": meta.get("house"), "hansard_url": meta.get("hansard_url"),
                       "petition": meta.get("petition"), "signatures": meta.get("signatures"),
                       "onside_count": sum(1 for s in speakers if s["confirmed_onside"]),
                       "other_count": sum(1 for s in speakers if not s["confirmed_onside"]),
                       "provisional": bool(provisional)},
            "speakers": speakers}
    return {"model": model, "max_tokens": MAX_TOKENS, "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}]}


def split_sections(text):
    """{'REPORT': ..., 'SOCIAL': ..., 'SUMMARY': ...} from one reply.

    A missing marker is returned as None rather than guessed at: publishing a report
    that is actually the social copy would be worse than publishing nothing.
    """
    out = {}
    for i, name in enumerate(MARKERS):
        start = text.find("<<<%s>>>" % name)
        if start < 0:
            out[name] = None
            continue
        start += len(name) + 6
        ends = [text.find("<<<%s>>>" % nxt) for nxt in MARKERS[i + 1:]]
        ends = [e for e in ends if e > start]
        out[name] = text[start:min(ends) if ends else len(text)].strip()
    return out


def word_count(markdown):
    """Body words: link targets, markers and blockquote furniture do not count."""
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", markdown or "")
    body = re.sub(r"^\s*[>#*\-]+\s*", "", body, flags=re.M)
    return len(body.split())


# A quotation, for checking purposes: opens after whitespace or a line start, closes
# before whitespace or punctuation. Straight quotes are ambiguous -- there is no
# open/close distinction -- so a naive pairing treats the PROSE BETWEEN one closing
# quote and the next opening one as a quotation. On the first real report (2026-09-10)
# that produced four false alarms, three of them markdown links, against two genuine
# paraphrases. A candidate carrying link syntax is prose, not a quote.
_QUOTED = re.compile(r'(?:^|\s)[\"\u201c]([^\"\u201c\u201d]{40,}?)[\"\u201d](?=[\s.,;:!?)\]]|$)', re.M)


def quotations(markdown):
    """The passages a report presents as spoken words."""
    out = []
    for cand in _QUOTED.findall(markdown or ""):
        if "](" in cand or cand.lstrip()[:1] in (";", ",", ")"):
            continue                     # prose between two quotations, not a quotation
        out.append(cand)
    return out


# Named things whose wording must be exact: a garbled statute name is the kind of
# error that survives every other check and embarrasses us in print. The first real
# report (2026-09-10) wrote "Human Fertilehood and Embryology Act 2008" for
# "Human Fertilisation and Embryology Act 2008", and nothing caught it.
_NAMED = re.compile(r"\b((?:[A-Z][A-Za-z'’-]+ (?:and |of |for |the )?){1,6}"
                    r"(?:Act|Bill|Commission|Committee|Authority|Regulations|Review|Order)"
                    r"(?: \d{4})?)\b")


def named_entities(markdown):
    """Statutes, bills, commissions and committees a report names."""
    text = re.sub(r"\]\([^)]*\)", "", markdown or "")     # link targets are not prose
    return sorted({" ".join(m.split()) for m in _NAMED.findall(text)})


def _unquoted_parts(quote, floor=25):
    """A quotation split at its elisions. An ellipsis inside one sentence is ordinary
    journalism, so each side is checked separately rather than the whole span, which
    would never match."""
    parts = [p.strip(" .,;:") for p in re.split(r"\s*(?:\.\.\.|…)\s*", quote)]
    return [p for p in parts if len(p) >= floor] or [quote]


def check(sections, speakers):
    """Complaints about a generated report, worst first, or [] when it is fit to send.

    Checked because the writer is a language model and these are the four ways its
    output could embarrass us: wrong length, an invented link, a quote that is not in
    the speeches, or a member we did not confirm being presented as onside.
    """
    problems = []
    report = sections.get("REPORT")
    if not report:
        return ["no REPORT section in the reply"]
    n = word_count(report)
    if not (WORDS_MIN <= n <= WORDS_MAX):
        problems.append("report is %d words, outside %d-%d" % (n, WORDS_MIN, WORDS_MAX))
    allowed = set(s["hansard_url"] for s in speakers if s["hansard_url"])
    allowed_hosts = ("hansard.parliament.uk", "petition.parliament.uk", "parliamentlive.tv",
                     "bills.parliament.uk", "www.legislation.gov.uk", "legislation.gov.uk")
    for url in re.findall(r"\]\((https?://[^)]+)\)", report):
        if url in allowed:
            continue
        host = url.split("/")[2] if "://" in url else ""
        if host not in allowed_hosts:
            problems.append("invented or off-list link: %s" % url)
    spoken = " ".join(_norm(s["text"]) for s in speakers)
    for quote in quotations(report):
        for part in _unquoted_parts(quote):
            if _norm(part) not in spoken:
                problems.append("quote not found verbatim in the speeches: \"%s...\"" % part[:60])
                break
    for name in named_entities(report):
        if _norm(name) not in spoken and _norm(name) not in _norm(str(sections.get("_title", ""))):
            problems.append("named thing not found in the speeches (check the wording): %s" % name)
    not_onside = [s["name"] for s in speakers if not s["confirmed_onside"]]
    for name in not_onside:
        surname = name.split()[-1]
        window = _around(report, surname)
        if window and re.search(r"\b(warned|argued against|opposed the change|spoke out against)\b", window, re.I):
            problems.append("%s is not confirmed onside but reads as one of ours" % name)
    return problems


def _norm(text):
    text = (text or "").replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"[^a-z0-9' ]", "", text.lower())


def _around(text, needle, width=140):
    i = text.find(needle)
    return text[max(0, i - width):i + width] if i >= 0 else ""


def generate(meta, speeches, api_key, conn=None, transport=None, dated=None, log=print,
             provisional=False):
    """One call: report, social copy, summary. Returns (sections, problems, usage)."""
    from src import spend, stance
    speakers = speaker_brief(speeches, provisional=provisional)
    if not speakers:
        raise SystemExit("no speaker has recoverable text: is speeches.md populated?")
    if not any(s["confirmed_onside"] for s in speakers):
        if provisional:
            raise SystemExit("no speaker is confirmed onside and the pass read nobody as With us; "
                             "there is no provisional report to write")
        raise SystemExit("no speaker is confirmed onside in checklist.md; confirm first, "
                         "then run tools/debate_pack.py --pack F --apply (or --provisional for a draft)")
    payload = build_payload(meta, speakers, provisional=provisional)
    reply = (transport or stance._default_transport)(payload, api_key)
    usage = reply.get("usage") or {}
    if conn is not None:
        spend.record(conn, "debate-report", reply.get("model") or REPORT_MODEL, usage, dated=dated)
    text = "".join(b.get("text", "") for b in (reply.get("content") or []) if b.get("type") == "text")
    if reply.get("stop_reason") == "max_tokens":
        log("[warn] the reply hit max_tokens; sections may be truncated")
    sections = split_sections(text)
    problems = check(sections, speakers)
    return sections, problems, usage


PROVISIONAL_NOTE = ("PROVISIONAL: the onside list came from the stance pass, not the checklist. "
                    "Confirm ONSIDE in checklist.md, run --apply, then regenerate without --provisional.")


def publish_blockers(state, force=False):
    """Why report.json says this report may not go to the channel. Empty means go.

    --force clears failed checks (a person has read them and said why); it never
    clears provisional, because the fix for that is the checklist, not a flag.
    """
    out = []
    if state.get("provisional"):
        out.append(PROVISIONAL_NOTE)
    if state.get("problems") and not force:
        out.append("%d check(s) failed when this report was generated" % len(state["problems"]))
    return out


def canvas_body(meta, report, preview=False, provisional=False, problems=None):
    """report.md as a canvas. The preview says what it is at the top and does not
    claim approval at the foot; the published one is the approved text alone."""
    head = ""
    if preview:
        notes = ["PREVIEW, shared with you alone. Nothing is in the channel."]
        if provisional:
            notes.append(PROVISIONAL_NOTE)
        if problems:
            notes.append("Checks that failed: " + "; ".join(problems))
        head = "> " + "\n> ".join(notes) + "\n\n"
    foot = ("*Source: [Hansard](%s). Report generated by the Parliamentary Monitor%s.*\n"
            % (meta.get("hansard_url"), "" if preview else " and approved by hand"))
    return head + report.rstrip() + "\n\n---\n\n" + foot


def canvas_summary(meta, preview=False):
    if preview:
        return "*Preview of the canvas — %s*\nThis is how the report will render. To send it to #campaigns-en-gb run --publish." % meta.get("title")
    return ("*%s*\nOur report of %s's debate. Footage clips are in the pack; Parliamentary Recording "
            "Unit terms apply to campaign use." % (meta.get("title"), meta.get("date")))


def approval_dm(meta, sections, reels, problems, pack_dir, radar_note="", provisional=False):
    """The DM that asks for sign-off. It never says 'published'."""
    summary = (sections.get("SUMMARY") or "").strip().splitlines()
    head = summary[0] if summary else meta.get("title", "debate")
    lines = ["*%s — %s*" % ("PROVISIONAL debate report, not for publishing yet" if provisional
                            else "Debate report ready for approval", meta.get("date", "")),
             PROVISIONAL_NOTE if provisional else None,
             "",
             "*%s* (%s)" % (meta.get("title", "?"), meta.get("house", "")),
             meta.get("hansard_url", ""),
             "",
             head]
    if len(summary) > 1:
        lines.append(summary[1])
    report = sections.get("REPORT") or ""
    lines += ["", "*Report* — %d words." % word_count(report)]
    if reels:
        lines += ["", "*Reels cut* — %d, %s:" % (len(reels), "/".join("%ds" % round(r["duration"]) for r in reels))]
        lines += ["• %s (%s) %ds" % (r["name"], r.get("party", ""), round(r["duration"])) for r in reels]
    if problems:
        lines += ["", "*Checks that failed — read before publishing*"] + ["• %s" % p for p in problems]
    else:
        lines += ["", "All automatic checks passed (length, links, quotes verbatim, onside list)."]
    if radar_note:
        lines += ["", radar_note]
    if provisional:
        lines += ["", "*Before this can be published*",
                  "1. Fill ONSIDE yes/no in %s/checklist.md" % pack_dir,
                  "2. ```python3 tools/debate_pack.py --pack %s --apply```" % pack_dir,
                  "3. ```python3 tools/debate_report.py --pack %s```  (regenerates from the confirmed list)" % pack_dir,
                  "4. then ```python3 tools/debate_report.py --pack %s --publish```" % pack_dir,
                  "--publish refuses a provisional report; nothing reaches the channel until the confirmed one is run."]
    else:
        lines += ["", "*To see it as a canvas first (shared with you alone)*",
                  "```python3 tools/debate_report.py --pack %s --preview```" % pack_dir,
                  "*To publish as a canvas to #campaigns-en-gb*",
                  "```python3 tools/debate_report.py --pack %s --publish```" % pack_dir,
                  "Nothing reaches the channel until that is run."]
    return "\n".join(l for l in lines if l is not None)
