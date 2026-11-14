#!/usr/bin/env python3
"""Writes small hand-built PDFs, one per font, layout or file-structure problem.

Standard library only, so every file can be rebuilt anywhere and each one carries
nothing but text written here: no font programs, no images from elsewhere. Files
meant to be damaged are damaged on purpose; the manifest says what each tests.

    python3 make_synthetic.py OUT_DIR        # writes OUT_DIR/<group>/<name>.pdf
    python3 make_synthetic.py OUT_DIR --list # prints name, group and summary as TSV

Encrypted variants need qpdf on PATH and are skipped without it.
"""

import os
import shutil
import subprocess
import sys
import zlib

HELVETICA_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]

PARAGRAPH = (
    "The quarterly figures arrived late on Thursday afternoon.",
    "Every region reported growth, led by the northern offices.",
    "Freight costs fell while staffing stayed level all year.",
    "The board will review the forecast at its next meeting.",
)

CASES = []


def case(group, summary):
    def register(fn):
        CASES.append((fn.__name__.replace("_", "-"), group, summary, fn))
        return fn

    return register


def esc(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def widths_array(first=32, last=126):
    return "[" + " ".join(str(w) for w in HELVETICA_WIDTHS[first - 32 : last - 32 + 1]) + "]"


def paragraph_ops(font="/F1", size=12, x=72, y=720, lead=16, lines=PARAGRAPH):
    out = [f"BT {font} {size} Tf {lead} TL {x} {y} Td"]
    for i, line in enumerate(lines):
        out.append(f"({esc(line)}) Tj" if i == 0 else f"({esc(line)}) '")
    out.append("ET")
    return "\n".join(out)


def utf16_hex(text):
    return text.encode("utf-16-be").hex().upper()


def identity_tounicode(codes_to_text):
    lines = [
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def",
        "1 begincodespacerange <0000> <FFFF> endcodespacerange",
        f"{len(codes_to_text)} beginbfchar",
    ]
    for code, text in codes_to_text:
        lines.append(f"<{code:04X}> <{utf16_hex(text)}>")
    lines += ["endbfchar", "endcmap CMapName currentdict /CMap defineresource pop end end"]
    return "\n".join(lines).encode()


def simple_tounicode(pairs):
    lines = [
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Simple-UCS def /CMapType 2 def",
        "1 begincodespacerange <00> <FF> endcodespacerange",
        f"{len(pairs)} beginbfchar",
    ]
    for code, text in pairs:
        lines.append(f"<{code:02X}> <{utf16_hex(text)}>")
    lines += ["endbfchar", "endcmap CMapName currentdict /CMap defineresource pop end end"]
    return "\n".join(lines).encode()


class Pdf:
    """Objects numbered from 1 in the order they are added; obj 1 is the catalog."""

    def __init__(self, version="1.7"):
        self.version = version
        self.objs = {}
        self.next = 1

    def reserve(self):
        num = self.next
        self.next += 1
        return num

    def set(self, num, body):
        self.objs[num] = body if isinstance(body, bytes) else body.encode("latin-1")
        return num

    def add(self, body):
        return self.set(self.reserve(), body)

    def stream(self, data, extra="", compress=False, num=None):
        data = data if isinstance(data, bytes) else data.encode("latin-1")
        if compress:
            data = zlib.compress(data)
            extra = f"/Filter /FlateDecode {extra}"
        body = f"<< /Length {len(data)} {extra} >>\nstream\n".encode() + data + b"\nendstream"
        return self.set(num if num is not None else self.reserve(), body)

    def serialize(self, root=1, trailer_extra="", header=None, offset_shift=0):
        out = bytearray(header if header is not None else f"%PDF-{self.version}\n%\xe2\xe3\xcf\xd3\n".encode("latin-1"))
        offsets = {}
        for num in sorted(self.objs):
            offsets[num] = len(out)
            out += f"{num} 0 obj\n".encode() + self.objs[num] + b"\nendobj\n"
        xref_at = len(out)
        size = max(self.objs) + 1
        out += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
        for num in range(1, size):
            if num in offsets:
                out += f"{offsets[num] + offset_shift:010d} 00000 n \n".encode()
            else:
                out += b"0000000000 65535 f \n"
        out += f"trailer\n<< /Size {size} /Root {root} 0 R {trailer_extra} >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
        return bytes(out)


def one_page(fonts, content, media="[0 0 612 792]", page_extra="", version="1.7", xobjects="", compress=False):
    """fonts: {name: font object body or callable(pdf) -> obj number}."""
    pdf = Pdf(version)
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font_refs = []
    for name, body in fonts.items():
        num = body(pdf) if callable(body) else pdf.add(body)
        font_refs.append(f"/{name} {num} 0 R")
    contents = pdf.stream(content, compress=compress)
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    resources = f"<< /Font << {' '.join(font_refs)} >> {xobjects} >>"
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /MediaBox {media} /Resources {resources} /Contents {contents} 0 R {page_extra} >>")
    return pdf


HELV = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"


def truetype_unembedded(base, flags=32, encoding="/WinAnsiEncoding", with_widths=True, with_descriptor=True, extra=""):
    def build(pdf):
        desc = ""
        if with_descriptor:
            d = pdf.add(
                f"<< /Type /FontDescriptor /FontName /{base} /Flags {flags} /FontBBox [-665 -325 2000 1006] "
                "/ItalicAngle 0 /Ascent 905 /Descent -212 /CapHeight 716 /StemV 80 >>"
            )
            desc = f"/FontDescriptor {d} 0 R"
        widths = f"/FirstChar 32 /LastChar 126 /Widths {widths_array()}" if with_widths else ""
        enc = f"/Encoding {encoding}" if encoding else ""
        return pdf.add(f"<< /Type /Font /Subtype /TrueType /BaseFont /{base} {widths} {enc} {desc} {extra} >>")

    return build


@case("fonts", "TrueType font named Arial, not embedded, WinAnsi with widths: the common office-export case")
def truetype_arial_not_embedded():
    return one_page({"F1": truetype_unembedded("Arial")}, paragraph_ops()).serialize()


@case("fonts", "TrueType font not embedded with no Widths and no FontDescriptor: advances must be guessed")
def truetype_no_widths_no_descriptor():
    return one_page({"F1": truetype_unembedded("Verdana", with_widths=False, with_descriptor=False)}, paragraph_ops()).serialize()


@case("fonts", "Bold and italic picked by BaseFont suffix only (Arial,Bold / Arial,Italic / Arial,BoldItalic), none embedded")
def truetype_style_suffixes():
    ops = "\n".join(
        f"BT /F{i} 14 Tf 72 {720 - i * 24} Td ({esc(PARAGRAPH[i % 4])}) Tj ET" for i in range(1, 5)
    )
    fonts = {
        "F1": truetype_unembedded("Arial"),
        "F2": truetype_unembedded("Arial,Bold", flags=32 | 262144),
        "F3": truetype_unembedded("Arial,Italic", flags=32 | 64),
        "F4": truetype_unembedded("Arial,BoldItalic", flags=32 | 64 | 262144),
    }
    return one_page(fonts, ops).serialize()


@case("fonts", "Subset tag on a font that is not embedded, with #20 escapes in the name")
def subset_tag_without_font_program():
    font = truetype_unembedded("ABCDEF+Times#20New#20Roman,BoldItalic", flags=34 | 64 | 262144)
    return one_page({"F1": font}, paragraph_ops()).serialize()


@case("fonts", "Type1 non-standard-14 font (Garamond) not embedded, StandardEncoding, no widths")
def type1_garamond_not_embedded():
    return one_page({"F1": "<< /Type /Font /Subtype /Type1 /BaseFont /Garamond >>"}, paragraph_ops()).serialize()


@case("fonts", "Base-14 aliases old generators write (Arial, TimesNewRoman, CourierNew,Bold) as Type1, not embedded")
def base14_aliases():
    names = ["Arial", "TimesNewRoman", "CourierNew,Bold", "Symbol"]
    fonts = {f"F{i}": f"<< /Type /Font /Subtype /Type1 /BaseFont /{n} >>" for i, n in enumerate(names, 1)}
    ops = "\n".join(f"BT /F{i} 14 Tf 72 {740 - i * 26} Td ({esc(PARAGRAPH[i - 1])}) Tj ET" for i in range(1, 4))
    ops += "\nBT /F4 14 Tf 72 620 Td (abgdp) Tj ET"
    return one_page(fonts, ops).serialize()


@case("fonts", "MacRomanEncoding font with accented letters, not embedded")
def macroman_accents():
    font = truetype_unembedded("Georgia", flags=34, encoding="/MacRomanEncoding")
    text = "Caf\\216 cr\\217me br\\236l\\216e, na\\225ve fa\\215ade, \\206bergr\\232\\247e"
    return one_page({"F1": font}, f"BT /F1 16 Tf 72 700 Td ({text}) Tj ET").serialize()


@case("fonts", "Differences array with uniXXXX, afii, Euro and made-up glyph names on a base-14 font")
def differences_odd_glyph_names():
    font = (
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding "
        "/BaseEncoding /WinAnsiEncoding /Differences [128 /Euro /uni20AC /afii10017 /afii10018 /g123 /uni0041.alt /f_f_i /fi] >> >>"
    )
    return one_page({"F1": font}, "BT /F1 18 Tf 72 700 Td (Price \\200 \\201 \\202\\203 \\204 \\205 \\206 \\207) Tj ET").serialize()


@case("fonts", "StandardEncoding ligatures fi and fl (codes 0xAE, 0xAF) with no ToUnicode")
def standard_encoding_ligatures():
    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>"
    return one_page({"F1": font}, "BT /F1 18 Tf 72 700 Td (\\256nal re\\256nement of the \\257oor \\256eld) Tj ET").serialize()


@case("fonts", "Symbolic TrueType (Wingdings) not embedded, no encoding, codes in the F0xx range")
def symbolic_truetype_not_embedded():
    font = truetype_unembedded("Wingdings-Regular", flags=4, encoding=None)
    return one_page({"F1": font}, "BT /F1 24 Tf 72 700 Td (\\154\\155\\156 \\247\\250) Tj ET").serialize()


def type0(base, cid_type="CIDFontType2", encoding="/Identity-H", ordering="(Identity)", registry="(Adobe)", supplement=0, tounicode=None, w="/DW 1000"):
    def build(pdf):
        d = pdf.add(
            f"<< /Type /FontDescriptor /FontName /{base} /Flags 32 /FontBBox [-1000 -300 2000 1100] "
            "/ItalicAngle 0 /Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 >>"
        )
        cid = pdf.add(
            f"<< /Type /Font /Subtype /{cid_type} /BaseFont /{base} "
            f"/CIDSystemInfo << /Registry {registry} /Ordering {ordering} /Supplement {supplement} >> "
            f"/FontDescriptor {d} 0 R {w} >>"
        )
        tu = f"/ToUnicode {pdf.stream(tounicode)} 0 R" if tounicode else ""
        return pdf.add(f"<< /Type /Font /Subtype /Type0 /BaseFont /{base} /Encoding {encoding} /DescendantFonts [{cid} 0 R] {tu} >>")

    return build


def cid_line(text):
    return "".join(f"{ord(c):04X}" for c in text)


@case("fonts", "Type0 Identity-H, CIDFontType2 not embedded, CIDs equal to code points, with ToUnicode")
def cid_identity_not_embedded_with_tounicode():
    text = "Revenue grew in every region."
    cmap = identity_tounicode([(ord(c), c) for c in sorted(set(text))])
    font = type0("ArialUnicodeMS", tounicode=cmap, w="/DW 556")
    return one_page({"F1": font}, f"BT /F1 16 Tf 72 700 Td <{cid_line(text)}> Tj ET").serialize()


@case("fonts", "Type0 Identity-H not embedded and no ToUnicode: the text cannot be recovered without OCR")
def cid_identity_not_embedded_no_tounicode():
    text = "Revenue grew in every region."
    font = type0("ArialUnicodeMS", w="/DW 556")
    return one_page({"F1": font}, f"BT /F1 16 Tf 72 700 Td <{cid_line(text)}> Tj ET").serialize()


@case("fonts", "Japanese with a predefined CMap (UniJIS-UCS2-H), Adobe-Japan1 CIDFontType0, not embedded")
def cjk_predefined_cmap_not_embedded():
    text = "日本語のテキストを表示します。"
    font = type0("KozMinPr6N-Regular", cid_type="CIDFontType0", encoding="/UniJIS-UCS2-H", ordering="(Japan1)", supplement=6)
    return one_page({"F1": font}, f"BT /F1 20 Tf 72 700 Td <{utf16_hex(text)}> Tj ET").serialize()


@case("fonts", "Vertical writing: Identity-V, not embedded, with ToUnicode")
def cid_vertical_identity_v():
    text = "縦書きの文章"
    cmap = identity_tounicode([(ord(c), c) for c in sorted(set(text))])
    font = type0("MSMincho", encoding="/Identity-V", tounicode=cmap)
    return one_page({"F1": font}, f"BT /F1 24 Tf 300 740 Td <{cid_line(text)}> Tj ET").serialize()


@case("fonts", "ToUnicode that maps codes to the wrong letters, as obfuscating generators do")
def tounicode_lies():
    shuffled = "zyxwvutsrqponmlkjihgfedcba"
    pairs = [(ord("a") + i, shuffled[i]) for i in range(26)] + [(32, " ")]

    def build(pdf):
        tu = pdf.stream(simple_tounicode(pairs))
        return pdf.add(f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /ToUnicode {tu} 0 R >>")

    return one_page({"F1": build}, "BT /F1 16 Tf 72 700 Td (what you see is not what you copy) Tj ET").serialize()


@case("fonts", "Widths array shorter than LastChar-FirstChar+1 and starting at the wrong code")
def widths_mismatch():
    def build(pdf):
        return pdf.add(
            "<< /Type /Font /Subtype /TrueType /BaseFont /Tahoma /FirstChar 40 /LastChar 126 "
            f"/Widths {widths_array(32, 90)} /Encoding /WinAnsiEncoding >>"
        )

    return one_page({"F1": build}, paragraph_ops()).serialize()


def type3_font(names, tounicode=None):
    def build(pdf):
        procs = []
        for i, name in enumerate(names):
            w = 500 + 60 * (i % 4)
            s = pdf.stream(f"{w} 0 d0 50 0 {w - 100} 700 re f".encode() if i % 2 == 0 else f"{w} 0 d0 50 0 m {w - 50} 700 l {w - 50} 0 l f".encode())
            procs.append(f"/{name} {s} 0 R")
        diffs = "[65 " + " ".join(f"/{n}" for n in names) + "]"
        tu = f"/ToUnicode {pdf.stream(tounicode)} 0 R" if tounicode else ""
        widths = " ".join(str(500 + 60 * (i % 4)) for i in range(len(names)))
        return pdf.add(
            "<< /Type /Font /Subtype /Type3 /FontBBox [0 0 800 750] /FontMatrix [0.001 0 0 0.001 0 0] "
            f"/CharProcs << {' '.join(procs)} >> /Encoding << /Type /Encoding /Differences {diffs} >> "
            f"/FirstChar 65 /LastChar {64 + len(names)} /Widths [{widths}] {tu} >>"
        )

    return build


@case("fonts", "Type3 font with glyph names g1..g6 and no ToUnicode: unmappable, like bitmap TeX fonts")
def type3_unmappable():
    font = type3_font([f"g{i}" for i in range(1, 7)])
    return one_page({"F1": font}, "BT /F1 24 Tf 72 700 Td (ABCDEF FEDCBA) Tj ET").serialize()


@case("fonts", "Type3 font with real glyph names (A..F) and a ToUnicode")
def type3_named_with_tounicode():
    names = list("ABCDEF")
    font = type3_font(names, simple_tounicode([(65 + i, n) for i, n in enumerate(names)]))
    return one_page({"F1": font}, "BT /F1 24 Tf 72 700 Td (ABCDEF FACADE) Tj ET").serialize()


@case("fonts", "Tf names a font resource the page does not have")
def font_resource_missing():
    return one_page({"F1": HELV}, paragraph_ops(font="/F9")).serialize()


@case("fonts", "Hex strings, octal escapes and a line continuation inside literal strings")
def string_escapes():
    ops = (
        "BT /F1 14 Tf 72 720 Td <48656C6C6F2C20776F726C64> Tj 0 -20 Td "
        "(Tab\\there, paren \\(inside\\), back\\\\slash) Tj 0 -20 Td "
        "(Continued \\\nline and \\101\\102\\103) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Font size 1 scaled by Tm to 12pt, the way many generators write every run")
def size_one_scaled_by_tm():
    lines = "\n".join(f"BT /F1 1 Tf 12 0 0 12 72 {720 - i * 16} Tm ({esc(t)}) Tj ET" for i, t in enumerate(PARAGRAPH))
    return one_page({"F1": HELV}, lines).serialize()


@case("text", "Negative font size and a mirrored text matrix")
def negative_size_and_mirror():
    ops = (
        "BT /F1 -14 Tf 300 700 Td (Drawn with a negative size) Tj ET\n"
        "BT /F1 14 Tf -1 0 0 1 400 650 Tm (Mirrored left to right) Tj ET\n"
        "BT /F1 14 Tf 1 0 0 -1 72 600 Tm (Upside down by the matrix) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Words separated only by TJ offsets, no space characters")
def words_by_tj_offsets_only():
    words = "The quarterly figures arrived late on Thursday".split()
    tj = " ".join(f"({esc(w)}) -280" for w in words)
    return one_page({"F1": HELV}, f"BT /F1 14 Tf 72 700 Td [{tj}] TJ ET").serialize()


@case("text", "Every character placed by its own Td, as OCR and some layout engines write text")
def one_td_per_character():
    text = "Every region reported growth"
    ops = ["BT /F1 14 Tf 72 700 Td"]
    for c in text:
        ops.append(f"({esc(c)}) Tj {HELVETICA_WIDTHS[ord(c) - 32] * 14 / 1000:.3f} 0 Td")
    ops.append("ET")
    return one_page({"F1": HELV}, "\n".join(ops)).serialize()


@case("text", "Tc, Tw, Tz and Ts on one line: spacing, word spacing, horizontal scale and rise")
def spacing_operators():
    ops = (
        "BT /F1 14 Tf 72 720 Td 2 Tc (Wide letters) Tj 0 Tc 0 -24 Td 10 Tw (Wide word gaps here) Tj 0 Tw "
        "0 -24 Td 60 Tz (Condensed to sixty percent) Tj 100 Tz 0 -24 Td (Base ) Tj 5 Ts (raised) Tj 0 Ts ( and back) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Fake bold by fill+stroke (Tr 2) and by drawing the run twice 0.4pt apart; fake italic by Tm skew")
def fake_bold_and_italic():
    ops = (
        "BT /F1 16 Tf 2 Tr 0.5 w 72 720 Td (Bold by stroking the outline) Tj ET\n"
        "BT /F1 16 Tf 0 Tr 72 690 Td (Bold by overprinting) Tj ET BT /F1 16 Tf 72.4 690 Td (Bold by overprinting) Tj ET\n"
        "BT /F1 16 Tf 1 0 0.21 1 72 660 Tm (Italic by skewing the matrix) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Invisible text (Tr 3) over drawn shapes, like an OCR layer over a scan")
def invisible_text_layer():
    shapes = "\n".join(f"0.2 g {72 + i * 9} 700 7 12 re f" for i in range(40))
    return one_page({"F1": HELV}, shapes + "\nBT /F1 12 Tf 3 Tr 72 701 Td (This line is only in the invisible layer) Tj ET").serialize()


@case("text", "Text used as a clip (Tr 7) with a fill painted through it")
def text_as_clip():
    ops = "BT /F1 48 Tf 7 Tr 72 650 Td (CLIPPED) Tj ET 0 0 1 rg 60 630 300 70 re f"
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Rotated text at 90, 45 and 180 degrees on an upright page")
def rotated_text_runs():
    ops = (
        "BT /F1 14 Tf 0 1 -1 0 100 400 Tm (Rotated ninety degrees) Tj ET\n"
        "BT /F1 14 Tf 0.7071 0.7071 -0.7071 0.7071 200 300 Tm (Rotated forty five) Tj ET\n"
        "BT /F1 14 Tf -1 0 0 -1 500 200 Tm (Rotated one eighty) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Hebrew stored in visual order (reversed) next to the same text in logical order, with ToUnicode")
def rtl_visual_vs_logical():
    logical = "שלום עולם"
    visual = logical[::-1]
    cmap = identity_tounicode([(ord(c), c) for c in sorted(set(logical))])
    font = type0("ArialHebrew", tounicode=cmap, w="/DW 600")
    ops = (
        f"BT /F1 20 Tf 72 700 Td <{cid_line(logical)}> Tj ET\n"
        f"BT /F1 20 Tf 72 660 Td <{cid_line(visual)}> Tj ET"
    )
    return one_page({"F1": font}, ops).serialize()


@case("text", "Soft hyphen and hard hyphen at line ends, and ActualText over a hyphenated word")
def hyphens_and_actualtext():
    ops = (
        "BT /F1 14 Tf 16 TL 72 720 Td (The quarterly fig\\255) Tj (ures arrived late.) ' "
        "(Every region re-) ' (ported growth.) ' ET\n"
        "/Span << /ActualText <FEFF0066006F007200650063006100730074> >> BDC BT /F1 14 Tf 72 640 Td (fore-) Tj 0 -16 Td (cast) Tj ET EMC"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("text", "Marked content with /Lang on a span, and text inside a hidden optional content layer")
def lang_span_and_hidden_layer():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    ocg = pdf.add("<< /Type /OCG /Name (Draft notes) >>")
    content = pdf.stream(
        "/Span << /Lang (fr-FR) >> BDC BT /F1 14 Tf 72 720 Td (Bonjour tout le monde) Tj ET EMC\n"
        "/OC /L1 BDC BT /F1 14 Tf 72 690 Td (Hidden draft note) Tj ET EMC\n"
        "BT /F1 14 Tf 72 660 Td (Visible body text) Tj ET"
    )
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R /Lang (en-GB) /OCProperties << /OCGs [{ocg} 0 R] /D << /OFF [{ocg} 0 R] >> >> >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> /Properties << /L1 {ocg} 0 R >> >> /Contents {content} 0 R >>")
    return pdf.serialize()


@case("layout", "A highlight rectangle painted between two words of one line, as word processors export it")
def highlight_between_words():
    ops = (
        "BT /F1 12 Tf 72 700 Td (Alpha ) Tj ET\n"
        "1 1 0 rg 106 696 30 14 re f 0 g\n"
        "BT /F1 12 Tf 108 700 Td (Beta ) Tj ET\nBT /F1 12 Tf 138 700 Td (Gamma) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("layout", "A watermark word tiled in a grid over ordinary body text: must not read as a table")
def tiled_watermark_over_text():
    tiles = "\n".join(
        f"BT /F1 20 Tf 0.85 g {80 + c * 190} {700 - r * 150} Td (CONFIDENTIAL) Tj ET" for r in range(5) for c in range(3)
    )
    body = "\n".join(f"BT /F2 11 Tf 0 g 72 {740 - i * 14} Td ({esc(PARAGRAPH[i % 4])}) Tj ET" for i in range(44))
    return one_page({"F1": HELV, "F2": HELV}, tiles + "\n" + body).serialize()


@case("layout", "A ruled table whose cell text runs across the grid lines")
def table_text_crossing_grid():
    grid = "0.5 w " + " ".join(f"{72 + c * 120} 600 m {72 + c * 120} 720 l S" for c in range(5))
    grid += " " + " ".join(f"72 {600 + r * 30} m 552 {600 + r * 30} l S" for r in range(5))
    cells = "\n".join(
        f"BT /F1 10 Tf {78 + c * 120} {700 - r * 30} Td (Row {r + 1} column {c + 1} overflowing) Tj ET" for r in range(4) for c in range(4)
    )
    return one_page({"F1": HELV}, grid + "\n" + cells).serialize()


@case("layout", "A real ruled table next to two-column running prose")
def table_beside_prose_columns():
    grid = "0.5 w " + " ".join(f"{72 + c * 80} 620 m {72 + c * 80} 720 l S" for c in range(4))
    grid += " " + " ".join(f"72 {620 + r * 25} m 312 {620 + r * 25} l S" for r in range(5))
    cells = "\n".join(
        f"BT /F1 10 Tf {78 + c * 80} {702 - r * 25} Td ({['Region', 'Q1', 'Q2'][c] if r == 0 else str(100 + r * 7 + c)}) Tj ET"
        for r in range(4)
        for c in range(3)
    )
    prose = "\n".join(
        f"BT /F1 10 Tf {72 + col * 270} {580 - i * 13} Td ({esc(PARAGRAPH[(i + col) % 4][:44])}) Tj ET" for col in range(2) for i in range(30)
    )
    return one_page({"F1": HELV}, grid + "\n" + cells + "\n" + prose).serialize()


@case("layout", "A table drawn on its side (text and rules rotated 90 degrees) on an upright page")
def sideways_table():
    rows = "\n".join(
        f"BT /F1 10 Tf 0 1 -1 0 {200 + r * 30} {150 + c * 120} Tm (R{r + 1} C{c + 1} value) Tj ET" for r in range(6) for c in range(4)
    )
    rules = "0.5 w " + " ".join(f"{185 + r * 30} 140 m {185 + r * 30} 640 l S" for r in range(7))
    return one_page({"F1": HELV}, rules + "\n" + rows).serialize()


@case("pages", "Pages rotated 90, 180 and 270 by /Rotate, each with an arrow and a label")
def page_rotate_values():
    pdf = Pdf()
    catalog, pages = pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    kids = []
    for rot in (0, 90, 180, 270):
        c = pdf.stream(f"BT /F1 24 Tf 72 700 Td (Rotate {rot}: this edge is the top) Tj ET 4 w 72 600 m 300 600 l 280 610 m 300 600 l 280 590 l S")
        kids.append(pdf.add(f"<< /Type /Page /Parent {pages} 0 R /Rotate {rot} /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>"))
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count 4 /MediaBox [0 0 612 792] >>")
    return pdf.serialize()


@case("pages", "MediaBox not at the origin, a smaller CropBox, a BleedBox and UserUnit 2")
def boxes_and_user_unit():
    ops = "BT /F1 18 Tf -150 200 Td (Origin is not at 0 0) Tj ET 0 0 1 RG -190 -290 590 770 re S"
    return one_page({"F1": HELV}, ops, media="[-200 -300 412 492]", page_extra="/CropBox [-150 -250 362 442] /BleedBox [-190 -290 402 482] /UserUnit 2").serialize()


@case("pages", "No MediaBox anywhere; readers must fall back to a default size")
def missing_mediabox():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    c = pdf.stream(paragraph_ops())
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>")
    return pdf.serialize()


@case("pages", "Three-level page tree; MediaBox, Rotate and Resources inherited from ancestors only")
def nested_page_tree_inheritance():
    pdf = Pdf()
    catalog, root, mid = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    leaves = []
    for i in range(3):
        c = pdf.stream(f"BT /F1 20 Tf 72 700 Td (Leaf page {i + 1} inherits everything) Tj ET")
        leaves.append(pdf.add(f"<< /Type /Page /Parent {mid} 0 R /Contents {c} 0 R >>"))
    pdf.set(catalog, f"<< /Type /Catalog /Pages {root} 0 R >>")
    pdf.set(root, f"<< /Type /Pages /Kids [{mid} 0 R] /Count 3 /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font} 0 R >> >> >>")
    pdf.set(mid, f"<< /Type /Pages /Parent {root} 0 R /Kids [{' '.join(f'{l} 0 R' for l in leaves)}] /Count 3 /Rotate 90 >>")
    return pdf.serialize()


@case("pages", "An empty page (no Contents), a page whose Contents is an empty stream, and one pointing at null")
def empty_pages():
    pdf = Pdf()
    catalog, pages = pdf.reserve(), pdf.reserve()
    empty = pdf.stream(b"")
    kids = [
        pdf.add(f"<< /Type /Page /Parent {pages} 0 R >>"),
        pdf.add(f"<< /Type /Page /Parent {pages} 0 R /Contents {empty} 0 R >>"),
        pdf.add(f"<< /Type /Page /Parent {pages} 0 R /Contents null >>"),
    ]
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count 3 /MediaBox [0 0 612 792] >>")
    return pdf.serialize()


@case("content", "Contents is an array of streams split in the middle of an operator and a string")
def contents_split_mid_token():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    a = pdf.stream("BT /F1 16 Tf 72 7")
    b = pdf.stream("00 Td (Split across two str")
    c = pdf.stream("eams) Tj ET")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> >> /Contents [{a} 0 R {b} 0 R {c} 0 R] >>")
    return pdf.serialize()


@case("content", "Form XObjects nested three deep, each with a Matrix; the innermost has no Resources")
def nested_form_xobjects():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    inner = pdf.stream("BT /F1 14 Tf 0 0 Td (Text three forms deep) Tj ET", extra="/Type /XObject /Subtype /Form /BBox [0 0 300 40] /Matrix [1 0 0 1 10 10]")
    middle = pdf.stream("/X3 Do", extra=f"/Type /XObject /Subtype /Form /BBox [0 0 400 100] /Matrix [1 0 0 1 20 20] /Resources << /XObject << /X3 {inner} 0 R >> /Font << /F1 {font} 0 R >> >>")
    outer = pdf.stream("/X2 Do", extra=f"/Type /XObject /Subtype /Form /BBox [0 0 500 200] /Matrix [1 0 0 1 72 600] /Resources << /XObject << /X2 {middle} 0 R >> >>")
    c = pdf.stream("/X1 Do BT /F1 12 Tf 72 500 Td (Text on the page itself) Tj ET")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> /XObject << /X1 {outer} 0 R >> >> /Contents {c} 0 R >>")
    return pdf.serialize()


@case("content", "Unbalanced q/Q and BDC/EMC, an unknown operator and an operator short of operands")
def unbalanced_operators():
    ops = (
        "q q 1 0 0 rg /P <</MCID 0>> BDC BT /F1 14 Tf 72 700 Td (After two q and a BDC) Tj ET Q\n"
        "BT /F1 14 Tf 72 670 Td 3 7 zzop (After an unknown operator) Tj ET\n"
        "BT /F1 14 Tf 72 640 Td 5 Td (After Td with one operand) Tj ET\nQ Q Q EMC EMC"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("content", "Inline image whose data contains the bytes EI before the real end")
def inline_image_with_ei_in_data():
    data = bytes([0x45, 0x49, 0x20, 0x00, 0xFF, 0x45, 0x49, 0x0A, 0x80, 0x40, 0xC0, 0x20])
    content = b"q 120 0 0 30 72 600 cm BI /W 4 /H 3 /BPC 8 /CS /G ID " + data + b" EI Q BT /F1 14 Tf 72 700 Td (Inline image below) Tj ET"
    return one_page({"F1": HELV}, content).serialize()


@case("content", "Content stream compressed with FlateDecode followed by trailing garbage bytes")
def flate_with_trailing_garbage():
    pdf = one_page({"F1": HELV}, b"")
    data = zlib.compress(paragraph_ops().encode()) + b"\x00garbage after the deflate stream"
    content_num = [n for n, b in pdf.objs.items() if b.startswith(b"<< /Length")][0]
    pdf.set(content_num, f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode() + data + b"\nendstream")
    return pdf.serialize()


@case("content", "Stream marked FlateDecode whose bytes are not compressed at all")
def flate_declared_not_compressed():
    pdf = one_page({"F1": HELV}, b"")
    data = paragraph_ops().encode()
    content_num = [n for n, b in pdf.objs.items() if b.startswith(b"<< /Length")][0]
    pdf.set(content_num, f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode() + data + b"\nendstream")
    return pdf.serialize()


@case("content", "Stream /Length too long on one page and too short on another")
def wrong_stream_lengths():
    pdf = Pdf()
    catalog, pages = pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    kids = []
    for delta, label in ((+40, "Length says 40 bytes more"), (-12, "Length says 12 bytes fewer")):
        data = f"BT /F1 18 Tf 72 700 Td ({label}) Tj ET".encode()
        c = pdf.set(pdf.reserve(), f"<< /Length {len(data) + delta} >>\nstream\n".encode() + data + b"\nendstream")
        kids.append(pdf.add(f"<< /Type /Page /Parent {pages} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>"))
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count 2 /MediaBox [0 0 612 792] >>")
    return pdf.serialize()


@case("annotations", "FreeText and a text-field widget with no appearance streams; the field's DA names a font not in DR")
def annotations_without_appearance():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    free = pdf.add(f"<< /Type /Annot /Subtype /FreeText /Rect [72 600 372 640] /Contents (A note with no appearance stream) /DA (/Helv 12 Tf 0 g) /P {page} 0 R >>")
    field = pdf.add(f"<< /Type /Annot /Subtype /Widget /FT /Tx /T (name) /V (Typed value) /Rect [72 500 372 524] /DA (/Missing 11 Tf 0 g) /P {page} 0 R /F 4 >>")
    c = pdf.stream("BT /F1 14 Tf 72 700 Td (Annotations below have no appearance streams) Tj ET")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R /AcroForm << /Fields [{field} 0 R] /DR << /Font << /Helv {font} 0 R >> >> /DA (/Helv 0 Tf 0 g) >> >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R /Annots [{free} 0 R {field} 0 R] >>")
    return pdf.serialize()


def simple_doc(text="Body text of a small structural sample.", version="1.7"):
    return one_page({"F1": HELV}, f"BT /F1 16 Tf 72 700 Td ({esc(text)}) Tj ET", version=version)


@case("structure", "Every xref offset shifted by 7 bytes: readers must rebuild the cross-reference table")
def xref_offsets_wrong():
    return simple_doc("The xref offsets are all wrong.").serialize(offset_shift=7)


@case("structure", "No xref table and no trailer at all, objects only")
def no_xref_no_trailer():
    data = simple_doc("There is no xref and no trailer.").serialize()
    return data[: data.index(b"xref\n")] + b"%%EOF\n"


@case("structure", "startxref points past the end of the file")
def startxref_past_eof():
    data = simple_doc("startxref points nowhere.").serialize()
    head, _, _ = data.rpartition(b"startxref\n")
    return head + b"startxref\n999999\n%%EOF\n"


@case("structure", "512 bytes of junk before %PDF and junk after %%EOF")
def junk_around_file():
    body = simple_doc("Junk sits before the header and after the end.").serialize()
    return b"JUNK" * 128 + body + b"\nTRAILING JUNK AFTER EOF\n"


@case("structure", "Bare CR line endings throughout")
def cr_line_endings():
    return simple_doc("Every line ends with a bare carriage return.").serialize().replace(b"\n", b"\r")


@case("structure", "The page's content object defined twice; the xref points at the second, which readers should use")
def duplicate_object_numbers():
    pdf = simple_doc("Object 5 is defined twice in this file.")
    data = pdf.serialize()
    stale_text = b"BT /F1 16 Tf 72 650 Td (STALE COPY) Tj ET"
    stale = f"5 0 obj\n<< /Length {len(stale_text)} >>\nstream\n".encode() + stale_text + b"\nendstream\nendobj\n"
    at = data.index(b"1 0 obj")
    out = data[:at] + stale + data[at:]
    shift = len(stale)
    head, _, rest = out.partition(b"xref\n")
    lines = rest.split(b"\n")
    fixed = [lines[0], lines[1]]
    for line in lines[2:]:
        if len(line) == 19 and line.endswith(b" n "):
            line = f"{int(line[:10]) + shift:010d}".encode() + line[10:]
        fixed.append(line)
    trailer = b"\n".join(fixed)
    xref_at = len(head)
    trailer = trailer[: trailer.rindex(b"startxref\n")] + f"startxref\n{xref_at}\n%%EOF\n".encode()
    return head + b"xref\n" + trailer


@case("structure", "An incremental update that replaces the page text and frees an unused object")
def incremental_update():
    pdf = simple_doc("Revision one text, replaced in revision two.")
    spare = pdf.add("<< /Unused true >>")
    first = pdf.serialize()
    prev = int(first[first.rindex(b"startxref\n") + 10 :].split(b"\n")[0])
    content_num = [n for n, b in pdf.objs.items() if b.startswith(b"<< /Length")][0]
    data = b"BT /F1 16 Tf 72 700 Td (Revision two replaced the text.) Tj ET"
    obj_at = len(first)
    update = f"{content_num} 0 obj\n<< /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream\nendobj\n"
    xref_at = obj_at + len(update)
    size = max(pdf.objs) + 1
    update += (
        f"xref\n0 1\n0000000000 65535 f \n{content_num} 1\n{obj_at:010d} 00000 n \n{spare} 1\n0000000000 00001 f \n"
        f"trailer\n<< /Size {size} /Root 1 0 R /Prev {prev} >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return first + update


@case("structure", "PDF 1.5 cross-reference stream with the font and page dictionaries inside an object stream")
def xref_stream_and_object_streams():
    font_body = HELV.encode()
    page_text = b"BT /F1 16 Tf 72 700 Td (Objects live in an object stream.) Tj ET"
    out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}

    def put(num, body):
        offsets[num] = len(out)
        out.extend(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

    put(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    put(5, f"<< /Length {len(page_text)} >>\nstream\n".encode() + page_text + b"\nendstream")
    packed = [(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"), (3, b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"), (4, font_body)]
    header, bodies, pos = [], b"", 0
    for num, body in packed:
        header.append(f"{num} {pos}")
        bodies += body + b" "
        pos += len(body) + 1
    head = (" ".join(header) + " ").encode()
    raw = zlib.compress(head + bodies)
    put(6, f"<< /Type /ObjStm /N 3 /First {len(head)} /Filter /FlateDecode /Length {len(raw)} >>\nstream\n".encode() + raw + b"\nendstream")
    xref_num = 7
    xref_at = len(out)
    rows = [(0, 0, 65535), (1, offsets[1], 0), (2, 6, 0), (2, 6, 1), (2, 6, 2), (1, offsets[5], 0), (1, offsets[6], 0), (1, xref_at, 0)]
    table = b"".join(t.to_bytes(1, "big") + f.to_bytes(4, "big") + g.to_bytes(2, "big") for t, f, g in rows)
    table = zlib.compress(table)
    out.extend(
        f"{xref_num} 0 obj\n<< /Type /XRef /Size 8 /W [1 4 2] /Root 1 0 R /Filter /FlateDecode /Length {len(table)} >>\nstream\n".encode()
        + table
        + f"\nendstream\nendobj\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(out)


ENCRYPTED = [
    ("encrypted-rc4-40-empty-user-password", "RC4 40-bit, empty user password, owner password set", ["--allow-weak-crypto", "--encrypt", "", "owner-secret", "40", "--"]),
    ("encrypted-aes-256-empty-user-password", "AES-256, empty user password, printing and copying refused", ["--encrypt", "", "owner-secret", "256", "--print=none", "--extract=n", "--"]),
    ("encrypted-aes-128-user-password", "AES-128 with user password 'corpus' required to open", ["--encrypt", "corpus", "owner-secret", "128", "--use-aes=y", "--"]),
]


def write_all(out_dir):
    written = []
    for name, group, summary, fn in CASES:
        path = os.path.join(out_dir, group, name + ".pdf")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(fn())
        written.append(path)
    qpdf = shutil.which("qpdf")
    if qpdf:
        base = os.path.join(out_dir, "structure", "_plain.pdf")
        with open(base, "wb") as f:
            f.write(simple_doc("This file is encrypted.").serialize())
        for name, _, args in ENCRYPTED:
            path = os.path.join(out_dir, "structure", name + ".pdf")
            subprocess.run([qpdf, "--static-id", *args, base, path], check=True)
            written.append(path)
        os.remove(base)
    return written


def listing():
    rows = [(name, group, summary) for name, group, summary, _ in CASES]
    rows += [(name, "structure", summary) for name, summary, _ in ENCRYPTED]
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if "--list" in sys.argv:
        for row in listing():
            print("\t".join(row))
    else:
        for path in write_all(sys.argv[1]):
            print(path)
