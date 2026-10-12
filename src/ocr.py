"""OCR for scanned parliamentary records, with Tesseract on the Mac Mini (X7).

Chris, 10 October 2026: "Tesseract OCR on the Mini: yes (PE, HR, CO later
phases)". DESIGN AND A GUARDED STEP ONLY: nothing is installed by this
module, and every caller must work exactly as before on a machine without
Tesseract (the laptop, GitHub's runners, the Mini until it is installed).
Install steps: docs/mac-mini.md, "OCR (Tesseract, X7)".

THE THREE SCANS IT IS FOR (measured in the scope documents):

  * Peru (docs/peru-scope.md): every SIGNED vote record of the plenary is a
    Lexmark scan with no text layer (14 of 24 files in the first sample); the
    provisional copies that carry text are replaced by the scans, and the
    installation week and the Diputados of 13 August exist only as scans.
    pe_vote_files.text_layer = 0 marks them. Language: Spanish.
  * Croatia (docs/croatia-scope.md): opposition and private members' bills
    are image-only PDFs from a Canon scanner (P.Z. 11, 59, 160, 241; 2 to 6
    pages). No document layer is collected yet (phase 3), so nothing calls
    this for Croatia today. Language: Croatian (`hrv`).
  * Colombia (docs/colombia-scope.md): the Gaceta del Congreso prints each
    plenary's electronic vote register as an embedded picture ("PUBLICACIÓN
    REGISTRO DE VOTACIÓN"), months late; the Gaceta is not collected yet
    (phase 3). Language: Spanish.

HOW (no new Python packages, no paid service, no network):

  1. A scanned PDF is one image per page. pypdf (already pinned for Peru,
     Canada and Panama) hands the embedded images back as JPEG or PNG bytes
     (`page.images`), so NO rasteriser (poppler, ghostscript) is needed.
  2. Each image goes to the `tesseract` command line (`tesseract <img> stdout
     -l spa --psm 6`, psm 6 = one uniform block of text, which suits a
     vote sheet's columns better than the automatic layout) through
     subprocess, with a timeout per page.
  3. The text is returned page by page; the CALLER decides what to parse
     and stores the text with the engine and its version, so OCR output is
     never mistaken for a text layer.

THE GUARD. available(lang) is True only when the `tesseract` binary is on
PATH (or at TESSERACT_CMD) AND its language data includes `lang`. Every
entry point returns None when it is not, and the callers print one
"[skip] OCR: tesseract not installed" line and carry on. Nothing fails.

ACCURACY, honestly. A 300 dpi office scan of a typed table usually reads
well; names with accents and column alignment are where it slips. OCR text
is therefore stored as evidence beside the scan, never parsed into member
positions without a separate, tested parser and a hand check of the first
sheets (that is a later step, one per country, not built here).
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile

PAGE_TIMEOUT_S = 120
MAX_PAGES = 40


def command():
    """The tesseract executable, or None. TESSERACT_CMD overrides PATH (the
    Mini's Homebrew puts it in /opt/homebrew/bin, which launchd's PATH may
    lack)."""
    explicit = os.environ.get("TESSERACT_CMD")
    if explicit:
        return explicit if os.path.exists(explicit) else None
    found = shutil.which("tesseract")
    if found:
        return found
    for guess in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if os.path.exists(guess):
            return guess
    return None


def languages(cmd=None, run=subprocess.run):
    cmd = cmd or command()
    if not cmd:
        return set()
    try:
        got = run([cmd, "--list-langs"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return set()
    lines = (got.stdout or "").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.lower().startswith("list of")}


def version(cmd=None, run=subprocess.run):
    cmd = cmd or command()
    if not cmd:
        return None
    try:
        got = run([cmd, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    first = ((got.stdout or got.stderr or "").splitlines() or [""])[0].strip()
    return first or None


def available(lang="spa", run=subprocess.run):
    """True only when tesseract exists and has `lang`'s data."""
    cmd = command()
    return bool(cmd) and lang in languages(cmd, run)


def why_not(lang="spa", run=subprocess.run):
    """One line for the log when available() is False."""
    cmd = command()
    if not cmd:
        return "tesseract not installed (docs/mac-mini.md, \"OCR (Tesseract, X7)\")"
    if lang not in languages(cmd, run):
        return "tesseract has no '{0}' language data (brew install tesseract-lang)".format(lang)
    return None


def page_images(pdf_bytes, max_pages=MAX_PAGES):
    """[(page number, [(name, image bytes)])] for a PDF's embedded images."""
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    out = []
    for n, page in enumerate(reader.pages[:max_pages], 1):
        imgs = []
        try:
            for img in page.images:
                imgs.append((img.name, img.data))
        except Exception:       # an unreadable image stream: that page is skipped
            imgs = []
        out.append((n, imgs))
    return out


def image_text(data, name="page.png", lang="spa", psm=6, run=subprocess.run):
    """Tesseract over one image; '' when it reads nothing."""
    cmd = command()
    if not cmd:
        return None
    suffix = os.path.splitext(name or "")[1] or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
        fh.write(data)
        path = fh.name
    try:
        got = run([cmd, path, "stdout", "-l", lang, "--psm", str(psm)],
                  capture_output=True, text=True, timeout=PAGE_TIMEOUT_S)
        return got.stdout or ""
    except (OSError, subprocess.SubprocessError):
        return ""
    finally:
        os.unlink(path)


def pdf_text(pdf_bytes, lang="spa", run=subprocess.run, max_pages=MAX_PAGES):
    """[(page, text)] for a scanned PDF, or None when OCR is unavailable."""
    if not available(lang, run):
        return None
    out = []
    for n, imgs in page_images(pdf_bytes, max_pages):
        text = "\n".join(image_text(data, name, lang, run=run) or "" for name, data in imgs)
        out.append((n, text))
    return out
