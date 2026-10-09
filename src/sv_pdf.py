"""Minimal stdlib text extractor for the Asamblea Legislativa's PDFs.

The Asamblea publishes one PDF per plenary vote (sesion-plenaria/votaciones)
and one session summary per plenary (resumen). Measured on 9 October 2026,
both are exported from Word: FlateDecode content streams, simple fonts in
WinAnsiEncoding (Aptos, Arial, Calibri, Bookman) with /Widths, plus the odd
Identity-H Type0 font carrying a /ToUnicode CMap; text is drawn with absolute
`Tm` positions and `TJ` arrays. That is simple enough to read without pypdf,
which keeps the El Salvador collector stdlib-only.

`pdf_lines(raw)` returns one list of lines per page, top to bottom. Fragments
on one baseline are concatenated as Word split them (a run boundary is not a
word boundary: "1" "2" ":15" is "12:15"), and joined with a tab only where
there is a real horizontal gap, which is what separates table cells in the
vote PDFs. Anything this reader does not understand (an image-only scan, an
unknown encoding) yields no text rather than an exception; the caller records
that as a gap.
"""

from __future__ import annotations

import re
import zlib

_OBJ = re.compile(rb"(\d+)\s+0\s+obj(.*?)endobj", re.S)
# InDesign (the Magyar Közlöny) ends a stream with a bare CR before
# "endstream"; Word with CRLF or LF.
_STREAM = re.compile(rb"stream\r?\n(.*?)(?:\r\n|\n|\r)?endstream", re.S)
_TOKEN = re.compile(
    rb"\((?:\\.|[^\\)])*\)"          # literal string (Word escapes its parens)
    rb"|<<|>>"
    rb"|<[0-9A-Fa-f\s]*>"            # hex string
    rb"|\[|\]"
    rb"|[-+]?\d*\.?\d+(?:[eE]-?\d+)?"
    rb"|/[^\s/\[\]()<>]+"
    rb"|[A-Za-z'\"*]+"
)
_ESC = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f",
        b"(": b"(", b")": b")", b"\\": b"\\"}


def _unescape(body):
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i:i + 1]
        if ch == b"\\" and i + 1 < len(body):
            nxt = body[i + 1:i + 2]
            if nxt in _ESC:
                out += _ESC[nxt]
                i += 2
                continue
            m = re.match(rb"[0-7]{1,3}", body[i + 1:i + 4])
            if m:
                out.append(int(m.group(0), 8) & 0xFF)
                i += 1 + len(m.group(0))
                continue
            i += 2 if nxt in (b"\n", b"\r") else 1
            continue
        out += ch
        i += 1
    return bytes(out)


def _string_bytes(tok):
    if tok.startswith(b"("):
        return _unescape(tok[1:-1])
    h = re.sub(rb"\s", b"", tok[1:-1])
    if len(h) % 2:
        h += b"0"
    return bytes.fromhex(h.decode())


class _Font:
    """Decoder and advance-width source for one font resource."""

    def __init__(self, cid=False, cmap=None, first_char=0, widths=None):
        self.cid = cid
        self.cmap = cmap or {}
        self.first_char = first_char
        self.widths = widths or []

    def codes(self, raw):
        if self.cid:
            return [int.from_bytes(raw[i:i + 2], "big") for i in range(0, len(raw) - 1, 2)]
        return list(raw)

    def text(self, raw):
        out = []
        for code in self.codes(raw):
            if code in self.cmap:
                out.append(self.cmap[code])
            elif self.cid:
                out.append("")              # no mapping: drop rather than invent
            else:
                out.append(bytes([code]).decode("cp1252", "replace"))
        return "".join(out)

    def width(self, raw):
        """Advance in text-space thousandths (0.5 em when unknown)."""
        total = 0.0
        for code in self.codes(raw):
            i = code - self.first_char
            total += self.widths[i] if 0 <= i < len(self.widths) and self.widths[i] else 500.0
        return total


def _parse_cmap(data):
    cmap = {}

    def uni(hexstr):
        b = bytes.fromhex(hexstr.decode())
        try:
            return b.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            cmap[int(src, 16)] = uni(dst)
    for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
        for lo, hi, rest in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]*>|\[[^\]]*\])", block):
            lo, hi = int(lo, 16), int(hi, 16)
            if rest.startswith(b"["):
                for k, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", rest)):
                    cmap[lo + k] = uni(dst)
            else:
                base = bytes.fromhex(rest[1:-1].decode())
                start = int.from_bytes(base, "big")
                for k in range(hi - lo + 1):
                    v = (start + k).to_bytes(len(base), "big")
                    try:
                        cmap[lo + k] = v.decode("utf-16-be")
                    except UnicodeDecodeError:
                        pass
    return cmap


class _Doc:
    def __init__(self, data):
        self.objs = {int(m.group(1)): m.group(2) for m in _OBJ.finditer(data)}
        self._fonts = {}

    def stream(self, num):
        body = self.objs.get(num, b"")
        m = _STREAM.search(body)
        if not m:
            return b""
        raw = m.group(1)
        if b"FlateDecode" in body[:m.start()]:
            try:
                return zlib.decompressobj().decompress(raw)
            except zlib.error:
                return b""
        return raw

    def deref(self, body, key):
        """Value of /key in body, following one indirect reference. A direct
        dictionary is read to its balancing ">>" (InDesign nests them:
        /Resources << /ExtGState << ... >> /Font << ... >> >>)."""
        m = re.search(rb"/" + key + rb"\s*(\d+)\s+0\s+R", body)
        if m:
            return self.objs.get(int(m.group(1)), b"")
        m = re.search(rb"/" + key + rb"\s*(<<|\[)", body)
        if not m:
            return b""
        if m.group(1) == b"[":
            end = body.find(b"]", m.end())
            return body[m.start(1):end + 1] if end >= 0 else b""
        depth, i = 0, m.start(1)
        while i < len(body) - 1:
            two = body[i:i + 2]
            if two == b"<<":
                depth += 1
                i += 2
                continue
            if two == b">>":
                depth -= 1
                i += 2
                if depth == 0:
                    return body[m.start(1):i]
                continue
            i += 1
        return b""

    def font(self, num):
        if num in self._fonts:
            return self._fonts[num]
        body = self.objs.get(num, b"")
        cid = b"/Type0" in body
        cmap = {}
        m = re.search(rb"/ToUnicode\s*(\d+)\s+0\s+R", body)
        if m:
            cmap = _parse_cmap(self.stream(int(m.group(1))))
        first = 0
        widths = []
        if not cid:
            fm = re.search(rb"/FirstChar\s*(\d+)", body)
            first = int(fm.group(1)) if fm else 0
            warr = self.deref(body, b"Widths")
            widths = [float(x) for x in re.findall(rb"[-\d.]+", warr)]
            # WinAnsi text decodes faithfully; trust it over a subset CMap.
            # A font with its own /Differences (InDesign puts the Hungarian
            # ő and ű, and the ligatures, at codes 24-31) keeps the CMap.
            enc = self.deref(body, b"Encoding")
            if b"/Differences" not in enc:
                cmap = {}
        f = _Font(cid=cid, cmap=cmap, first_char=first, widths=widths)
        self._fonts[num] = f
        return f

    def pages(self):
        root = None
        for num, body in self.objs.items():
            if re.search(rb"/Type\s*/Pages\b", body) and b"/Parent" not in body:
                root = num
                break
        out = []

        def walk(num, seen):
            if num in seen:
                return
            seen.add(num)
            body = self.objs.get(num, b"")
            if re.search(rb"/Type\s*/Page(?!s)\b", body):
                out.append(num)
                return
            m = re.search(rb"/Kids\s*\[([^\]]*)\]", body)
            for k in re.findall(rb"(\d+)\s+0\s+R", m.group(1) if m else b""):
                walk(int(k), seen)

        if root is not None:
            walk(root, set())
        return out

    def page_content(self, num):
        body = self.objs[num]
        res = self.deref(body, b"Resources") or body
        fdict = self.deref(res, b"Font")
        fonts = {name.decode(): self.font(int(ref))
                 for name, ref in re.findall(rb"/([^\s/<>]+)\s*(\d+)\s+0\s+R", fdict)}
        m = re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+0\s+R)", body)
        refs = [int(x) for x in re.findall(rb"(\d+)\s+0\s+R", m.group(1))] if m else []
        return b"\n".join(self.stream(r) for r in refs), fonts


def _fragments(stream, fonts):
    """(x, y, x_end, text) for every text-show in one content stream."""
    frags = []
    x = y = lx = ly = 0.0
    leading = 0.0
    size = 10.0
    scale = 1.0
    font = _Font()
    stack = []

    def show(parts):
        nonlocal x
        text = []
        start = x
        for p in parts:
            if isinstance(p, float):
                x -= p / 1000.0 * size * scale
            else:
                text.append(font.text(p))
                x += font.width(p) / 1000.0 * size * scale
        frags.append((start, y, x, "".join(text)))

    for tok in _TOKEN.findall(stream):
        if tok == b"BT":
            x = y = lx = ly = 0.0
            stack = []
        elif tok == b"Tf" and len(stack) >= 2:
            font = fonts.get(stack[-2].lstrip(b"/").decode("latin-1"), _Font())
            size = abs(float(stack[-1])) or 1.0
            stack = []
        elif tok == b"Tm" and len(stack) >= 6:
            vals = [float(v) for v in stack[-6:]]
            scale = (vals[0] ** 2 + vals[1] ** 2) ** 0.5 or 1.0
            x, y = vals[4], vals[5]
            lx, ly = x, y
            stack = []
        elif tok in (b"Td", b"TD") and len(stack) >= 2:
            lx += float(stack[-2]) * scale
            ly += float(stack[-1]) * scale
            if tok == b"TD":
                leading = -float(stack[-1]) * scale
            x, y = lx, ly
            stack = []
        elif tok == b"TL" and stack:
            leading = float(stack[-1])
            stack = []
        elif tok == b"T*":
            ly -= leading
            x, y = lx, ly
        elif tok in (b"Tj", b"'", b'"') and stack:
            if tok != b"Tj":
                ly -= leading
                x, y = lx, ly
            show([_string_bytes(stack[-1])])
            stack = []
        elif tok == b"TJ":
            parts = []
            for t in stack:
                if t.startswith((b"(", b"<")) and t not in (b"<<",):
                    parts.append(_string_bytes(t))
                elif re.match(rb"[-+]?\d*\.?\d+", t):
                    parts.append(float(t))
            show(parts)
            stack = []
        elif tok in (b"[", b"]"):
            continue
        elif re.match(rb"[A-Za-z'\"*]+$", tok):
            stack = []
        else:
            stack.append(tok)
    return frags


def pdf_lines(data, y_tolerance=2.0, cell_gap=4.0, max_pages=None):
    """List of pages, each a list of text lines top to bottom. max_pages
    reads only the first pages (the Magyar Közlöny's contents are on the
    first one or two of an issue that can run to 1,000)."""
    try:
        doc = _Doc(data)
        page_nums = doc.pages()
    except Exception:  # a damaged file is a gap, not a crash
        return []
    if max_pages:
        page_nums = page_nums[:max_pages]
    pages = []
    for num in page_nums:
        try:
            stream, fonts = doc.page_content(num)
            frags = [f for f in _fragments(stream, fonts) if f[3]]
        except Exception:
            pages.append([])
            continue
        frags.sort(key=lambda f: (-f[1], f[0]))
        rows = []
        for f in frags:
            if rows and abs(rows[-1][0] - f[1]) <= y_tolerance:
                rows[-1][1].append(f)
            else:
                rows.append([f[1], [f]])
        lines = []
        for _, parts in rows:
            parts.sort(key=lambda f: f[0])
            out = ""
            end = None
            for fx, _, fend, text in parts:
                if end is not None and fx - end > cell_gap:
                    out = out.rstrip() + "\t"
                out += text
                end = fend
            out = re.sub(r"[  ]+", " ", out).strip()
            if out:
                lines.append(out)
        pages.append(lines)
    return pages
