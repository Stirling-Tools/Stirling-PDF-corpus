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


OBLIQUE = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"


@case("regressions", "Oblique text where redacting 'e' takes the 'd' before it too ('a demand' becomes 'a mand')")
def redact_oblique_neighbour():
    return one_page({"F1": OBLIQUE}, "BT /F1 12 Tf 72 510 Td (a timing issue, not a demand issue.) Tj ET").serialize()


@case("regressions", "Emoji and astral-plane characters in page text, with ToUnicode, for text and Office exports")
def emoji_text_export():
    text = "Ship it 🚀 then celebrate 🎉 with 𝒜𝓁𝓅𝒽𝒶 and 😀"
    chars = sorted(set(text))
    codes = {c: i + 1 for i, c in enumerate(chars)}
    lines = [
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def",
        "1 begincodespacerange <0000> <FFFF> endcodespacerange",
        f"{len(chars)} beginbfchar",
    ] + [f"<{codes[c]:04X}> <{utf16_hex(c)}>" for c in chars] + ["endbfchar", "endcmap CMapName currentdict /CMap defineresource pop end end"]
    font = type0("NotoEmoji", tounicode="\n".join(lines).encode(), w="/DW 900")
    content = "".join(f"{codes[c]:04X}" for c in text)
    return one_page({"F1": font}, f"BT /F1 18 Tf 72 700 Td <{content}> Tj ET").serialize()


@case("regressions", "Control for typing into an unembedded font: typed letters keep their spacing here, unlike fonts-missing-latex/g-noembed-ptm where they overlap")
def typing_into_unembedded_serif():
    font = truetype_unembedded("TimesNewRomanPSMT", flags=34)
    return one_page({"F1": font}, "BT /F1 20 Tf 72 700 Td (Annual Inventory Report) Tj ET").serialize()


@case("edge", "/Rotate values outside 0-270: 450, -90 and 45 (invalid, readers round or ignore)")
def odd_rotate_values():
    pdf = Pdf()
    catalog, pages = pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    kids = []
    for rot in (450, -90, 45):
        c = pdf.stream(f"BT /F1 24 Tf 72 700 Td (Rotate {rot}) Tj ET")
        kids.append(pdf.add(f"<< /Type /Page /Parent {pages} 0 R /Rotate {rot} /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>"))
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count 3 /MediaBox [0 0 612 792] >>")
    return pdf.serialize()


@case("edge", "MediaBox written upper-right first ([612 792 0 0]) and a page with a zero-height MediaBox")
def reversed_and_empty_mediabox():
    pdf = Pdf()
    catalog, pages = pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    c1 = pdf.stream("BT /F1 24 Tf 72 700 Td (Reversed MediaBox) Tj ET")
    c2 = pdf.stream("BT /F1 24 Tf 72 700 Td (Zero height MediaBox) Tj ET")
    k1 = pdf.add(f"<< /Type /Page /Parent {pages} 0 R /MediaBox [612 792 0 0] /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c1} 0 R >>")
    k2 = pdf.add(f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 612 0] /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c2} 0 R >>")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{k1} 0 R {k2} 0 R] /Count 2 >>")
    return pdf.serialize()


@case("edge", "Page tree whose /Count says 5 but holds 2 pages")
def page_count_lies():
    pdf = Pdf()
    catalog, pages = pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    kids = []
    for i in range(2):
        c = pdf.stream(f"BT /F1 24 Tf 72 700 Td (Page {i + 1} of a tree that claims five) Tj ET")
        kids.append(pdf.add(f"<< /Type /Page /Parent {pages} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>"))
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{kids[0]} 0 R {kids[1]} 0 R] /Count 5 /MediaBox [0 0 612 792] >>")
    return pdf.serialize()


@case("edge", "Page tree with a cycle: a Pages node lists its own parent as a kid")
def page_tree_cycle():
    pdf = Pdf()
    catalog, root, mid = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    c = pdf.stream("BT /F1 24 Tf 72 700 Td (The only real page) Tj ET")
    leaf = pdf.add(f"<< /Type /Page /Parent {mid} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {root} 0 R >>")
    pdf.set(root, f"<< /Type /Pages /Kids [{mid} 0 R] /Count 1 /MediaBox [0 0 612 792] >>")
    pdf.set(mid, f"<< /Type /Pages /Parent {root} 0 R /Kids [{leaf} 0 R {root} 0 R] /Count 1 >>")
    return pdf.serialize()


@case("edge", "Outline (bookmarks) whose Next chain loops back to the first item")
def outline_cycle():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    outlines, a, b = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    c = pdf.stream("BT /F1 24 Tf 72 700 Td (Bookmarks loop) Tj ET")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R /Outlines {outlines} 0 R /PageMode /UseOutlines >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 /MediaBox [0 0 612 792] >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R >>")
    pdf.set(outlines, f"<< /Type /Outlines /First {a} 0 R /Last {b} 0 R /Count 2 >>")
    pdf.set(a, f"<< /Title (First) /Parent {outlines} 0 R /Next {b} 0 R /Dest [{page} 0 R /Fit] >>")
    pdf.set(b, f"<< /Title (Second) /Parent {outlines} 0 R /Prev {a} 0 R /Next {a} 0 R /Dest [{page} 0 R /Fit] >>")
    return pdf.serialize()


@case("edge", "Text far outside the MediaBox, white text on white, and text drawn under an opaque rectangle")
def hidden_and_offpage_text():
    ops = (
        "BT /F1 14 Tf 72 700 Td (Visible line) Tj ET\n"
        "BT /F1 14 Tf 900 1200 Td (Off the page entirely) Tj ET\n"
        "BT /F1 14 Tf 1 1 1 rg 72 660 Td (White on white) Tj ET 0 g\n"
        "BT /F1 14 Tf 72 620 Td (Covered by a box) Tj ET 0.2 g 70 615 140 20 re f"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("edge", "A 4,000-character single line and text at 0.1pt and 400pt")
def extreme_sizes_and_long_line():
    long = ("Long line " * 400)[:4000]
    ops = (
        f"BT /F1 6 Tf 10 760 Td ({long}) Tj ET\n"
        "BT /F1 0.1 Tf 72 700 Td (Microscopic text) Tj ET\n"
        "BT /F1 400 Tf 20 200 Td (Hg) Tj ET"
    )
    return one_page({"F1": HELV}, ops).serialize()


@case("edge", "Document JavaScript, an OpenAction, a Launch action link and an embedded file attachment")
def actions_and_attachment():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    js = pdf.add("<< /S /JavaScript /JS (app.alert\\('corpus sample'\\);) >>")
    emb = pdf.stream("Attached plain text file for the corpus.\n", extra="/Type /EmbeddedFile /Subtype /text#2Fplain")
    spec = pdf.add(f"<< /Type /Filespec /F (notes.txt) /UF (notes.txt) /EF << /F {emb} 0 R >> >>")
    link = pdf.add(f"<< /Type /Annot /Subtype /Link /Rect [72 600 300 620] /Border [0 0 1] /A << /S /Launch /F (calc.exe) >> /P {page} 0 R >>")
    c = pdf.stream("BT /F1 16 Tf 72 700 Td (JavaScript, a Launch link and an attachment) Tj ET BT /F1 12 Tf 72 605 Td (Launch link) Tj ET")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R /OpenAction {js} 0 R /Names << /JavaScript << /Names [(init) {js} 0 R] >> /EmbeddedFiles << /Names [(notes.txt) {spec} 0 R] >> >> >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 /MediaBox [0 0 612 792] >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R /Annots [{link} 0 R] >>")
    return pdf.serialize()


@case("edge", "AcroForm with NeedAppearances true, a checkbox, a choice list and a field value in UTF-16")
def form_need_appearances():
    pdf = Pdf()
    catalog, pages, page = pdf.reserve(), pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    tx = pdf.add(f"<< /Type /Annot /Subtype /Widget /FT /Tx /T (city) /V <FEFF004D00FC006E006300680065006E> /Rect [72 650 300 672] /DA (/Helv 12 Tf 0 g) /P {page} 0 R /F 4 >>")
    cb = pdf.add(f"<< /Type /Annot /Subtype /Widget /FT /Btn /T (agree) /V /Yes /AS /Yes /Rect [72 610 90 628] /P {page} 0 R /F 4 /MK << /CA (4) >> /DA (/ZaDb 0 Tf 0 g) >>")
    ch = pdf.add(f"<< /Type /Annot /Subtype /Widget /FT /Ch /Ff 131072 /T (size) /Opt [(Small) (Medium) (Large)] /V (Medium) /Rect [72 570 200 590] /DA (/Helv 12 Tf 0 g) /P {page} 0 R /F 4 >>")
    c = pdf.stream("BT /F1 14 Tf 72 700 Td (Form fields with no appearance streams) Tj ET")
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R /AcroForm << /Fields [{tx} 0 R {cb} 0 R {ch} 0 R] /NeedAppearances true /DR << /Font << /Helv {font} 0 R >> >> /DA (/Helv 0 Tf 0 g) >> >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{page} 0 R] /Count 1 /MediaBox [0 0 612 792] >>")
    pdf.set(page, f"<< /Type /Page /Parent {pages} 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents {c} 0 R /Annots [{tx} 0 R {cb} 0 R {ch} 0 R] >>")
    return pdf.serialize()


@case("edge", "Two incremental updates where the second deletes the page the first added (Prev chain of three)")
def incremental_chain():
    base = simple_doc("Revision one.")
    first = base.serialize()
    prev1 = int(first[first.rindex(b"startxref\n") + 10 :].split(b"\n")[0])
    font = 4
    content = b"BT /F1 16 Tf 72 700 Td (Page added in revision two.) Tj ET"
    at6 = len(first)
    upd = f"6 0 obj\n<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream\nendobj\n"
    at7 = at6 + len(upd)
    upd += f"7 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 {font} 0 R >> >> /Contents 6 0 R >>\nendobj\n".encode()
    at2 = at6 + len(upd)
    upd += b"2 0 obj\n<< /Type /Pages /Kids [3 0 R 7 0 R] /Count 2 >>\nendobj\n"
    x1 = at6 + len(upd)
    upd += (
        f"xref\n0 1\n0000000000 65535 f \n2 1\n{at2:010d} 00000 n \n6 2\n{at6:010d} 00000 n \n{at7:010d} 00000 n \n"
        f"trailer\n<< /Size 8 /Root 1 0 R /Prev {prev1} >>\nstartxref\n{x1}\n%%EOF\n"
    ).encode()
    second = first + upd
    at2b = len(second)
    upd2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    x2 = at2b + len(upd2)
    upd2 += (
        f"xref\n0 1\n0000000000 65535 f \n2 1\n{at2b:010d} 00000 n \n7 1\n0000000000 00001 f \n"
        f"trailer\n<< /Size 8 /Root 1 0 R /Prev {x1} >>\nstartxref\n{x2}\n%%EOF\n"
    ).encode()
    return second + upd2


def new_doc(version="1.7"):
    pdf = Pdf(version)
    catalog, pages = pdf.reserve(), pdf.reserve()
    return pdf, catalog, pages, pdf.add(HELV)


def add_page(pdf, pages, font, content, extra="", media="[0 0 612 792]", res_extra="", num=None, parent=None):
    c = pdf.stream(content)
    body = (
        f"<< /Type /Page /Parent {parent or pages} 0 R /MediaBox {media} "
        f"/Resources << /Font << /F1 {font} 0 R >> {res_extra} >> /Contents {c} 0 R {extra} >>"
    )
    return pdf.set(num if num is not None else pdf.reserve(), body)


def finish(pdf, catalog, pages, kids, catalog_extra="", trailer_extra=""):
    pdf.set(catalog, f"<< /Type /Catalog /Pages {pages} 0 R {catalog_extra} >>")
    pdf.set(pages, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>")
    return pdf.serialize(trailer_extra=trailer_extra)


def form_xobject(pdf, w, h, ops, extra=""):
    return pdf.stream(ops, extra=f"/Type /XObject /Subtype /Form /BBox [0 0 {w} {h}] {extra}")


def text_string(text):
    return f"({esc(text)})" if all(ord(c) < 128 for c in text) else f"<FEFF{utf16_hex(text)}>"


def js(code):
    return f"<< /S /JavaScript /JS ({esc(code)}) >>"


@case("interactive", "Form with hierarchical field names (address.street), a radio group with appearance states, read-only, required, comb and calculated fields")
def form_hierarchical_and_radio():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    res = f"/Resources << /Font << /Helv {font} 0 R >> >>"

    def text_field(name, value, rect, extra="", parent=None):
        x0, y0, x1, y1 = rect
        ap = form_xobject(pdf, x1 - x0, y1 - y0, f"/Tx BMC q BT /Helv 11 Tf 2 5 Td ({esc(value)}) Tj ET Q EMC", res)
        owner = f"/Parent {parent} 0 R" if parent else "/FT /Tx"
        return pdf.add(
            f"<< /Type /Annot /Subtype /Widget {owner} /T ({name}) /V ({esc(value)}) /Rect [{x0} {y0} {x1} {y1}] "
            f"/DA (/Helv 11 Tf 0 g) /AP << /N {ap} 0 R >> /P {page} 0 R /F 4 {extra} >>"
        )

    address = pdf.reserve()
    street = text_field("street", "1 High Street", (160, 690, 400, 710), "/MaxLen 30", address)
    city = text_field("city", "Leeds", (160, 660, 400, 680), "/Q 1", address)
    pdf.set(address, f"<< /FT /Tx /T (address) /Kids [{street} 0 R {city} 0 R] >>")
    ref = text_field("ref", "R-0042", (160, 630, 400, 650), "/Ff 1")
    email = text_field("email", "", (160, 600, 400, 620), "/Ff 2")
    code = text_field("code", "AB12CD", (160, 570, 280, 590), "/Ff 16777216 /MaxLen 6")
    total = text_field("total", "30", (160, 540, 280, 560), f"/AA << /C {js('event.value = 10 + 20;')} >>")
    plan = pdf.reserve()
    on = form_xobject(pdf, 14, 14, "0 g 3 3 8 8 re f")
    off = form_xobject(pdf, 14, 14, "0 G 0.5 0.5 13 13 re S")
    radios = []
    for i, (state, y) in enumerate((("Basic", 510), ("Pro", 485))):
        radios.append(pdf.add(
            f"<< /Type /Annot /Subtype /Widget /Parent {plan} 0 R /Rect [160 {y} 174 {y + 14}] "
            f"/AS /{state if i == 1 else 'Off'} /AP << /N << /{state} {on} 0 R /Off {off} 0 R >> >> /MK << >> /P {page} 0 R /F 4 >>"
        ))
    pdf.set(plan, f"<< /FT /Btn /Ff 49152 /T (plan) /V /Pro /Kids [{radios[0]} 0 R {radios[1]} 0 R] >>")
    labels = [("Street", 695), ("City", 665), ("Reference", 635), ("Email", 605), ("Code", 575), ("Total", 545), ("Basic plan", 512), ("Pro plan", 487)]
    ops = "\n".join(f"BT /F1 11 Tf 72 {y} Td ({t}) Tj ET" for t, y in labels)
    widgets = [street, city, ref, email, code, total] + radios
    add_page(pdf, pages, font, ops, extra=f"/Annots [{' '.join(f'{w} 0 R' for w in widgets)}]", num=page)
    fields = [address, ref, email, code, total, plan]
    acro = f"/AcroForm << /Fields [{' '.join(f'{f} 0 R' for f in fields)}] /CO [{total} 0 R] /DR << /Font << /Helv {font} 0 R >> >> /DA (/Helv 0 Tf 0 g) >>"
    return finish(pdf, catalog, pages, [page], acro)


@case("interactive", "JavaScript in eight places: OpenAction with a Next chain, the name tree, catalog and page AA, a link, a field keystroke, an annotation and a stream-valued JS")
def javascript_everywhere():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    stream_js = pdf.stream("console.println('stream valued script');")
    named = pdf.add(f"<< /S /JavaScript /JS {stream_js} 0 R >>")
    chained = pdf.add(js("console.println('chained after open');"))
    link = pdf.add(f"<< /Type /Annot /Subtype /Link /Rect [72 640 260 660] /Border [0 0 0] /A {js('app.alert(1);')} /P {page} 0 R >>")
    field = pdf.add(
        f"<< /Type /Annot /Subtype /Widget /FT /Tx /T (name) /Rect [72 600 300 620] /DA (/Helv 11 Tf 0 g) "
        f"/AA << /K {js('event.rc = true;')} /F {js('event.value = event.value.toUpperCase();')} >> /P {page} 0 R /F 4 >>"
    )
    note = pdf.add(f"<< /Type /Annot /Subtype /Square /Rect [320 600 380 660] /C [1 0 0] /AA << /E {js('console.println(2);')} >> /P {page} 0 R >>")
    ops = "BT /F1 16 Tf 72 700 Td (JavaScript in eight places) Tj ET BT /F1 11 Tf 72 645 Td (Link that runs a script) Tj ET"
    add_page(pdf, pages, font, ops, extra=f"/Annots [{link} 0 R {field} 0 R {note} 0 R] /AA << /O {js('console.println(3);')} >>", num=page)
    extra = (
        f"/OpenAction << /S /GoTo /D [{page} 0 R /Fit] /Next {chained} 0 R >> "
        f"/AA << /WC {js('console.println(4);')} >> "
        f"/Names << /JavaScript << /Names [(init) {named} 0 R] >> >> "
        f"/AcroForm << /Fields [{field} 0 R] /DR << /Font << /Helv {font} 0 R >> >> >>"
    )
    return finish(pdf, catalog, pages, [page], extra)


@case("interactive", "Four pages linked by explicit, named (name tree and old Dests dict), URI and GoToR destinations, with bookmarks and page labels")
def links_and_named_destinations():
    pdf, catalog, pages, font = new_doc()
    p = [pdf.reserve() for _ in range(4)]
    links = [
        ((72, 640, 300, 660), f"/A << /S /GoTo /D [{p[2]} 0 R /Fit] >>", "Explicit link to page 3"),
        ((72, 610, 300, 630), "/Dest (chapter-2)", "Named link to chapter 2"),
        ((72, 580, 300, 600), "/Dest /appendix", "Old-style named link to the appendix"),
        ((72, 550, 300, 570), "/A << /S /URI /URI (https://example.com/corpus) >>", "Web link"),
        ((72, 520, 300, 540), "/A << /S /GoToR /F (other.pdf) /D [0 /Fit] >>", "Link into another file"),
    ]
    annots, ops = [], ["BT /F1 18 Tf 72 700 Td (Contents) Tj ET"]
    for (x0, y0, x1, y1), action, label in links:
        annots.append(pdf.add(f"<< /Type /Annot /Subtype /Link /Rect [{x0} {y0} {x1} {y1}] /Border [0 0 1] {action} /P {p[0]} 0 R >>"))
        ops.append(f"BT /F1 12 Tf {x0 + 2} {y0 + 5} Td ({label}) Tj ET")
    add_page(pdf, pages, font, "\n".join(ops), extra=f"/Annots [{' '.join(f'{a} 0 R' for a in annots)}]", num=p[0])
    for i, title in ((1, "Chapter 2"), (2, "Chapter 3")):
        add_page(pdf, pages, font, f"BT /F1 24 Tf 72 700 Td ({title}) Tj ET", num=p[i])
    back = pdf.add(f"<< /Type /Annot /Subtype /Link /Rect [72 640 300 660] /Border [0 0 1] /Dest [{p[0]} 0 R /XYZ 0 792 0] /P {p[3]} 0 R >>")
    add_page(pdf, pages, font, "BT /F1 24 Tf 72 700 Td (Appendix) Tj ET BT /F1 12 Tf 74 645 Td (Back to contents) Tj ET", extra=f"/Annots [{back} 0 R]", num=p[3])
    outlines = pdf.reserve()
    items = [pdf.reserve() for _ in range(3)]
    targets = [("Chapter 2", "/Dest (chapter-2)"), ("Chapter 3", "/Dest (chapter-3)"), ("Appendix", "/Dest (summary)")]
    for i, (title, dest) in enumerate(targets):
        prev = f"/Prev {items[i - 1]} 0 R" if i else ""
        nxt = f"/Next {items[i + 1]} 0 R" if i < 2 else ""
        pdf.set(items[i], f"<< /Title ({title}) /Parent {outlines} 0 R {prev} {nxt} {dest} >>")
    pdf.set(outlines, f"<< /Type /Outlines /First {items[0]} 0 R /Last {items[2]} 0 R /Count 3 >>")
    extra = (
        f"/Names << /Dests << /Names [(chapter-2) [{p[1]} 0 R /XYZ 72 720 0] (chapter-3) [{p[2]} 0 R /Fit] (summary) << /D [{p[3]} 0 R /FitH 700] >>] >> >> "
        f"/Dests << /appendix [{p[3]} 0 R /Fit] >> /Outlines {outlines} 0 R "
        "/PageLabels << /Nums [0 << /S /r >> 1 << /S /D /St 2 >> 3 << /P (App-) /S /A >>] >>"
    )
    return finish(pdf, catalog, pages, p, extra)


def outline_items(pdf, parent, items):
    nums = [pdf.reserve() for _ in items]
    visible = 0
    for i, (title, target, extra, children, opened) in enumerate(items):
        kids = ""
        if children:
            first, last, count = outline_items(pdf, nums[i], children)
            kids = f"/First {first} 0 R /Last {last} 0 R /Count {count if opened else -count}"
            visible += count if opened else 0
        prev = f"/Prev {nums[i - 1]} 0 R" if i else ""
        nxt = f"/Next {nums[i + 1]} 0 R" if i + 1 < len(items) else ""
        pdf.set(nums[i], f"<< /Title {text_string(title)} /Parent {parent} 0 R {prev} {nxt} {kids} {target} {extra} >>")
        visible += 1
    return nums[0], nums[-1], visible


@case("interactive", "Bookmarks four levels deep with UTF-16 and emoji titles, closed branches, colour and style flags, an item with no target and one aimed at a missing object")
def outline_deep_and_unicode():
    pdf, catalog, pages, font = new_doc()
    p = [pdf.reserve() for _ in range(3)]
    for i in range(3):
        add_page(pdf, pages, font, f"BT /F1 24 Tf 72 700 Td (Section page {i + 1}) Tj ET", num=p[i])
    tree = [
        ("Part One", f"/Dest [{p[0]} 0 R /Fit]", "", [
            ("Chapter 1 — Größe", f"/Dest [{p[0]} 0 R /XYZ 72 700 null]", "/C [1 0 0] /F 3", [
                ("Section 1.1 \U0001F680", f"/A << /S /GoTo /D [{p[1]} 0 R /XYZ null null null] >>", "", [
                    ("Subsection 1.1.1", f"/Dest [{p[1]} 0 R /FitR 0 0 300 300]", "", [], True),
                ], True),
            ], True),
        ], True),
        ("Part Two (closed)", f"/Dest [{p[2]} 0 R /Fit]", "/F 2", [
            ("Heading with no target", "", "", [], True),
            ("Heading aimed at a missing object", "/Dest [9999 0 R /Fit]", "", [], True),
        ], False),
        ("日本語の見出し", "/Dest [2 /Fit]", "", [], True),
    ]
    outlines = pdf.reserve()
    first, last, count = outline_items(pdf, outlines, tree)
    pdf.set(outlines, f"<< /Type /Outlines /First {first} 0 R /Last {last} 0 R /Count {count} >>")
    return finish(pdf, catalog, pages, p, f"/Outlines {outlines} 0 R /PageMode /UseOutlines")


@case("interactive", "Eleven annotation types, each with an appearance stream: highlight, ink, square, circle, line with arrows, polygon, stamp, sticky note with popup, free text, underline, caret")
def annotations_with_appearances():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    res = f"/Resources << /Font << /Helv {font} 0 R >> >>"
    meta = f"/P {page} 0 R /F 4 /M (D:20261115120000Z) /T (Corpus)"

    def annot(subtype, rect, ap_ops, extra=""):
        x0, y0, x1, y1 = rect
        ap = form_xobject(pdf, x1 - x0, y1 - y0, ap_ops, res)
        return pdf.add(f"<< /Type /Annot /Subtype /{subtype} /Rect [{x0} {y0} {x1} {y1}] /AP << /N {ap} 0 R >> /NM ({subtype.lower()}-1) {meta} {extra} >>")

    a = [
        annot("Highlight", (70, 696, 250, 716), "1 1 0 rg 0 0 180 20 re f", "/QuadPoints [70 716 250 716 70 696 250 696] /C [1 1 0] /Contents (Highlighted words)"),
        annot("Underline", (70, 664, 250, 670), "0 0 1 RG 1 w 0 3 m 180 3 l S", "/QuadPoints [70 684 250 684 70 666 250 666] /C [0 0 1]"),
        annot("Ink", (300, 640, 400, 720), "0 0 1 RG 2 w 5 5 m 50 75 l 95 5 l S", "/InkList [[305 645 350 715 395 645]] /C [0 0 1]"),
        annot("Square", (420, 640, 520, 720), "1 0 0 RG 2 w 1 1 98 78 re S", "/C [1 0 0] /Contents (A red box)"),
        annot("Circle", (70, 520, 170, 620), "0 0.6 0 RG 2 w 50 1 m 99 50 l 50 99 l 1 50 l h S", "/C [0 0.6 0]"),
        annot("Line", (200, 540, 400, 600), "0 G 2 w 5 5 m 195 55 l S 195 55 m 185 52 l 192 45 l h f", "/L [205 545 395 595] /LE [/None /ClosedArrow] /C [0 0 0]"),
        annot("Polygon", (420, 520, 520, 620), "0.5 0 0.5 RG 2 w 50 95 m 95 30 l 5 30 l h S", "/Vertices [470 615 515 550 425 550] /C [0.5 0 0.5]"),
        annot("Stamp", (70, 400, 270, 470), "0.8 0 0 RG 3 w 2 2 196 66 re S BT /Helv 36 Tf 0.8 0 0 rg 20 20 Td (APPROVED) Tj ET", "/Name /Approved"),
        annot("FreeText", (300, 400, 520, 470), "BT /Helv 12 Tf 5 45 Td (Free text comment with an) Tj 0 -16 Td (appearance stream) Tj ET", "/DA (/Helv 12 Tf 0 g) /Contents (Free text comment with an appearance stream)"),
        annot("Caret", (250, 700, 262, 716), "0 0 1 rg 0 0 m 6 16 l 12 0 l h f", "/Contents (Insert here)"),
    ]
    popup = pdf.reserve()
    note = annot("Text", (540, 700, 560, 720), "1 0.8 0 rg 0 0 20 20 re f", f"/Contents (Sticky note text) /Name /Comment /Popup {popup} 0 R /Open false")
    pdf.set(popup, f"<< /Type /Annot /Subtype /Popup /Rect [540 560 740 700] /Parent {note} 0 R /Open false /P {page} 0 R >>")
    a += [note, popup]
    ops = "BT /F1 14 Tf 72 700 Td (Highlighted words) Tj 0 -32 Td (Underlined words) Tj ET"
    add_page(pdf, pages, font, ops, extra=f"/Annots [{' '.join(f'{x} 0 R' for x in a)}]", num=page)
    return finish(pdf, catalog, pages, [page])


@case("interactive", "Signature field whose ByteRange is correct but whose Contents is a few bytes of junk DER, not a real PKCS#7 signature")
def signature_garbage_pkcs7():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    placeholder = "[0 PPPPPPPPPP PPPPPPPPPP PPPPPPPPPP]"
    contents = "3082" + "0" * 8188
    sig = pdf.add(
        f"<< /Type /Sig /Filter /Adobe.PPKLite /SubFilter /adbe.pkcs7.detached /ByteRange {placeholder} "
        f"/Contents <{contents}> /M (D:20261115120000Z) /Name (Corpus Test Signer) /Reason (Testing) >>"
    )
    widget = pdf.add(f"<< /Type /Annot /Subtype /Widget /FT /Sig /T (Signature1) /V {sig} 0 R /Rect [72 600 272 650] /P {page} 0 R /F 132 >>")
    add_page(pdf, pages, font, "BT /F1 14 Tf 72 700 Td (Signed with a signature that is not one) Tj ET", extra=f"/Annots [{widget} 0 R]", num=page)
    data = bytearray(finish(pdf, catalog, pages, [page], f"/AcroForm << /Fields [{widget} 0 R] /SigFlags 3 >>"))
    start = data.index(f"<{contents}>".encode())
    end = start + len(contents) + 2
    ranges = f"[0 {start:010d} {end:010d} {len(data) - end:010d}]".encode()
    at = data.index(placeholder.encode())
    data[at : at + len(placeholder)] = ranges
    return bytes(data)


@case("interactive", "Attachments with a UTF-16 name, wrong declared size, a file spec with no embedded stream, and a file-attachment annotation on the page")
def attachments_unicode_and_broken():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    plain = pdf.stream("Plain text attachment.\n", extra="/Type /EmbeddedFile /Subtype /text#2Fplain /Params << /Size 9999 /ModDate (D:2026) >>")
    csv = pdf.stream("name,value\nalpha,1\n", extra="/Type /EmbeddedFile /Subtype /text#2Fcsv")
    note = pdf.stream("Attached through an annotation.\n", extra="/Type /EmbeddedFile")
    s1 = pdf.add(f"<< /Type /Filespec /F (report.txt) /UF (report.txt) /EF << /F {plain} 0 R >> /Desc (Declared size is wrong) >>")
    uname = "\u00dcbersicht-M\u00fcller.csv"
    s2 = pdf.add(f"<< /Type /Filespec /F (Ubersicht-Muller.csv) /UF {text_string(uname)} /EF << /F {csv} 0 R >> /AFRelationship /Data >>")
    s3 = pdf.add("<< /Type /Filespec /F (missing.bin) /UF (missing.bin) >>")
    s4 = pdf.add(f"<< /Type /Filespec /F (annotation.txt) /UF (annotation.txt) /EF << /F {note} 0 R >> >>")
    icon = form_xobject(pdf, 16, 20, "0.3 g 0 0 16 20 re f")
    ann = pdf.add(f"<< /Type /Annot /Subtype /FileAttachment /Rect [72 600 88 620] /FS {s4} 0 R /Name /Paperclip /Contents (annotation.txt) /AP << /N {icon} 0 R >> /P {page} 0 R /F 4 >>")
    add_page(pdf, pages, font, "BT /F1 14 Tf 72 700 Td (Three attachments, one broken, plus one on the page) Tj ET", extra=f"/Annots [{ann} 0 R]", num=page)
    names = f"(missing.bin) {s3} 0 R (report.txt) {s1} 0 R <FEFF{utf16_hex(uname)}> {s2} 0 R"
    return finish(pdf, catalog, pages, [page], f"/Names << /EmbeddedFiles << /Names [{names}] >> >> /AF [{s2} 0 R]")


@case("pages", "Seven pages with mixed page labels: roman, arabic, a prefixed range, letters starting at AA, and a prefix-only label")
def page_labels_mixed():
    pdf, catalog, pages, font = new_doc()
    kids = [add_page(pdf, pages, font, f"BT /F1 24 Tf 72 700 Td (Physical page {i + 1}) Tj ET") for i in range(7)]
    labels = "/PageLabels << /Nums [0 << /S /r >> 2 << /S /D >> 4 << /P (A-) /S /D /St 1 >> 5 << /S /A /St 27 >> 6 << /P (Back) >>] >>"
    return finish(pdf, catalog, pages, kids, labels)


@case("pages", "300 small pages in a balanced page tree of 50-page nodes; stacking them on one page passes the 14,400-unit page size limit")
def many_small_pages():
    pdf = Pdf()
    catalog, root = pdf.reserve(), pdf.reserve()
    font = pdf.add(HELV)
    nodes = []
    for n in range(6):
        node = pdf.reserve()
        kids = []
        for i in range(50):
            c = pdf.stream(f"BT /F1 48 Tf 160 380 Td (Page {n * 50 + i + 1}) Tj ET", compress=True)
            kids.append(pdf.add(f"<< /Type /Page /Parent {node} 0 R /Contents {c} 0 R >>"))
        pdf.set(node, f"<< /Type /Pages /Parent {root} 0 R /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count 50 >>")
        nodes.append(node)
    pdf.set(catalog, f"<< /Type /Catalog /Pages {root} 0 R >>")
    pdf.set(root, f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in nodes)}] /Count 300 /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> >> >>")
    return pdf.serialize()


@case("pages", "Six page sizes in one file: A4, landscape Letter, a business card, A0, a Letter page with Rotate 90 and an offset MediaBox with a CropBox")
def mixed_page_sizes():
    pdf, catalog, pages, font = new_doc()
    specs = [
        ("A4 portrait", "[0 0 595 842]", ""),
        ("Letter landscape", "[0 0 792 612]", ""),
        ("Business card", "[0 0 252 144]", ""),
        ("A0", "[0 0 2384 3370]", ""),
        ("Letter rotated 90", "[0 0 612 792]", "/Rotate 90"),
        ("Offset box", "[100 100 712 892]", "/CropBox [150 150 662 842]"),
    ]
    kids = []
    for label, media, extra in specs:
        box = extra.split("/CropBox")[1] if "/CropBox" in extra else media
        x0, y0, x1, y1 = (int(v) for v in box.strip(" []").split())
        ops = f"0.6 G 4 w {x0 + 10} {y0 + 10} {x1 - x0 - 20} {y1 - y0 - 20} re S BT /F1 14 Tf {x0 + 24} {y1 - 40} Td ({label}) Tj ET"
        kids.append(add_page(pdf, pages, font, ops, extra=extra, media=media))
    return finish(pdf, catalog, pages, kids)


@case("text", "Tagged two-column page whose content stream draws the right column first; the structure tree gives the true order, plus a figure with no Alt and a table")
def tagged_reading_order():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    left = ["First column, first line.", "First column, second line."]
    right = ["Second column, first line.", "Second column, second line."]

    def column(mcid, x, lines):
        body = " ".join(f"({esc(t)}) '" if i else f"({esc(t)}) Tj" for i, t in enumerate(lines))
        return f"/P << /MCID {mcid} >> BDC BT /F1 11 Tf 14 TL {x} 700 Td {body} ET EMC"

    ops = "\n".join([
        column(1, 320, right),
        column(0, 72, left),
        "/Figure << /MCID 2 >> BDC 0.7 g 72 520 200 120 re f EMC",
        "/TD << /MCID 3 >> BDC BT /F1 11 Tf 320 600 Td (Cell A1) Tj ET EMC",
        "/TD << /MCID 4 >> BDC BT /F1 11 Tf 420 600 Td (Cell B1) Tj ET EMC",
        "0 G 315 590 200 25 re S 415 590 m 415 615 l S",
    ])
    root, doc, p0, p1, fig, table, tr, td0, td1 = (pdf.reserve() for _ in range(9))
    pdf.set(p0, f"<< /Type /StructElem /S /P /P {doc} 0 R /Pg {page} 0 R /K 0 >>")
    pdf.set(p1, f"<< /Type /StructElem /S /P /P {doc} 0 R /Pg {page} 0 R /K 1 >>")
    pdf.set(fig, f"<< /Type /StructElem /S /Figure /P {doc} 0 R /Pg {page} 0 R /K 2 >>")
    pdf.set(td0, f"<< /Type /StructElem /S /TD /P {tr} 0 R /Pg {page} 0 R /K 3 >>")
    pdf.set(td1, f"<< /Type /StructElem /S /TD /P {tr} 0 R /Pg {page} 0 R /K 4 >>")
    pdf.set(tr, f"<< /Type /StructElem /S /TR /P {table} 0 R /K [{td0} 0 R {td1} 0 R] >>")
    pdf.set(table, f"<< /Type /StructElem /S /Table /P {doc} 0 R /K [{tr} 0 R] >>")
    pdf.set(doc, f"<< /Type /StructElem /S /Document /P {root} 0 R /K [{p0} 0 R {p1} 0 R {fig} 0 R {table} 0 R] >>")
    pdf.set(root, f"<< /Type /StructTreeRoot /K [{doc} 0 R] /ParentTree << /Nums [0 [{p0} 0 R {p1} 0 R {fig} 0 R {td0} 0 R {td1} 0 R]] >> /ParentTreeNextKey 1 >>")
    add_page(pdf, pages, font, ops, extra="/StructParents 0 /Tabs /S", num=page)
    return finish(pdf, catalog, pages, [page], f"/StructTreeRoot {root} 0 R /MarkInfo << /Marked true >> /Lang (en-GB)")


@case("metadata", "Info dictionary with an impossible date, a date in words, an emoji title, PDFDocEncoding bytes, a name and a number where strings belong, and an array value")
def info_dict_odd_values():
    pdf = simple_doc("Document information values of the wrong kinds.")
    title = text_string("Quarterly \U0001F4CA Report")
    info = pdf.add(
        f"<< /Title {title} /Author (Jos\\351 \\200 Example) /Subject <FEFF> "
        "/Keywords /NameNotString /Creator 42 /Producer (\\376\\377) "
        "/CreationDate (D:20261315256199+25'00') /ModDate (yesterday) /Trapped /Maybe /Custom [1 2 3] >>"
    )
    return pdf.serialize(trailer_extra=f"/Info {info} 0 R")


XMP_HEAD = '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n<x:xmpmeta xmlns:x="adobe:ns:meta/">\n<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
XMP_TAIL = '</rdf:RDF>\n</x:xmpmeta>\n<?xpacket end="w"?>'


def with_xmp(pdf, xmp, info_body):
    meta = pdf.stream(xmp.encode("latin-1"), extra="/Type /Metadata /Subtype /XML")
    pdf.objs[1] = pdf.objs[1].replace(b">>", f"/Metadata {meta} 0 R >>".encode(), 1)
    info = pdf.add(info_body)
    return pdf.serialize(trailer_extra=f"/Info {info} 0 R")


@case("metadata", "XMP that is not well-formed XML (unclosed element, undeclared prefix) and claims PDF/A-2B, next to a valid Info dictionary")
def xmp_malformed():
    xmp = XMP_HEAD + (
        '<rdf:Description rdf:about="" xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" pdfaid:part="2" pdfaid:conformance="B">\n'
        "<dc:title><rdf:Alt><rdf:li xml:lang=\"x-default\">Broken XMP\n"
        "</rdf:Description>\n"
    ) + XMP_TAIL
    return with_xmp(simple_doc("XMP metadata that will not parse."), xmp, "<< /Title (Valid info title) /Author (Corpus) >>")


@case("metadata", "Well-formed XMP whose title, author and dates disagree with the Info dictionary")
def xmp_disagrees_with_info():
    xmp = XMP_HEAD + (
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
        'xmlns:pdf="http://ns.adobe.com/pdf/1.3/">\n'
        '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">XMP title</rdf:li></rdf:Alt></dc:title>\n'
        "<dc:creator><rdf:Seq><rdf:li>XMP Author</rdf:li></rdf:Seq></dc:creator>\n"
        "<xmp:CreateDate>2001-01-01T00:00:00Z</xmp:CreateDate>\n<xmp:ModifyDate>2001-01-02T00:00:00Z</xmp:ModifyDate>\n"
        "<pdf:Producer>XMP Producer</pdf:Producer>\n</rdf:Description>\n"
    ) + XMP_TAIL
    info = "<< /Title (Info title) /Author (Info Author) /CreationDate (D:20261115120000Z) /ModDate (D:20261115130000Z) /Producer (Info Producer) >>"
    return with_xmp(simple_doc("Info and XMP disagree."), xmp, info)


@case("graphics", "Page transparency group, constant alpha, Multiply blend, a luminosity soft mask and a knockout group")
def transparency_and_softmask():
    pdf, catalog, pages, font = new_doc()
    mask = form_xobject(pdf, 612, 792, "0.2 g 72 400 230 230 re f 0.9 g 302 400 230 230 re f", "/Group << /S /Transparency /CS /DeviceGray >>")
    knock = form_xobject(pdf, 612, 792, "0 0 1 rg 100 150 150 100 re f 1 0 0 rg 160 180 150 100 re f", "/Group << /S /Transparency /K true >>")
    gs = (
        f"/ExtGState << /GS1 << /ca 0.5 /CA 0.5 >> /GS2 << /BM /Multiply >> "
        f"/GS3 << /SMask << /S /Luminosity /G {mask} 0 R >> >> >> /XObject << /K1 {knock} 0 R >>"
    )
    ops = "\n".join([
        "1 0 0 rg 72 600 200 120 re f",
        "q /GS1 gs 0 0 1 rg 172 640 200 120 re f Q",
        "q /GS2 gs 0 0.8 0 rg 122 560 200 120 re f Q",
        "q /GS3 gs 1 0.5 0 rg 72 400 460 230 re f Q",
        "q /GS1 gs BT /F1 28 Tf 0 g 72 360 Td (Half-transparent text) Tj ET Q",
        "/K1 Do",
    ])
    page = add_page(pdf, pages, font, ops, extra="/Group << /S /Transparency /CS /DeviceRGB /I true >>", res_extra=gs)
    return finish(pdf, catalog, pages, [page])


SPOT_FN = "{ 0 exch dup 0.91 mul exch dup 0.76 mul exch 0.02 mul }"


@case("graphics", "Separation spot colour and DeviceN through PostScript calculator (Type 4) functions, Lab, CalRGB and Indexed colour spaces")
def spot_colours_and_functions():
    pdf, catalog, pages, font = new_doc()
    fn1 = pdf.stream(SPOT_FN, extra="/FunctionType 4 /Domain [0 1] /Range [0 1 0 1 0 1 0 1]")
    fn2 = pdf.stream("{ pop 0 0 0 }", extra="/FunctionType 4 /Domain [0 1 0 1] /Range [0 1 0 1 0 1 0 1]")
    spaces = (
        f"/ColorSpace << /CS1 [/Separation /PANTONE#20185#20C /DeviceCMYK {fn1} 0 R] "
        f"/CS2 [/DeviceN [/Cyan /Spot#20Varnish] /DeviceCMYK {fn2} 0 R] "
        "/CS3 [/Lab << /WhitePoint [0.9505 1 1.089] /Range [-128 127 -128 127] >>] "
        "/CS4 [/CalRGB << /WhitePoint [0.9505 1 1.089] /Gamma [2.2 2.2 2.2] >>] "
        "/CS5 [/Indexed /DeviceRGB 2 <FF0000 00FF00 0000FF>] >>"
    )
    ops = "\n".join([
        "/CS1 cs 1 scn 72 600 100 100 re f /CS1 cs 0.4 scn 182 600 100 100 re f",
        "/CS2 cs 1 0.5 scn 292 600 100 100 re f",
        "/CS3 cs 50 60 -40 scn 402 600 100 100 re f",
        "/CS4 cs 0.2 0.6 0.9 scn 72 480 100 100 re f",
        "/CS5 cs 2 scn 182 480 100 100 re f",
        "BT /F1 24 Tf /CS1 cs 1 scn 72 420 Td (Spot colour text) Tj ET",
    ])
    page = add_page(pdf, pages, font, ops, res_extra=spaces)
    return finish(pdf, catalog, pages, [page])


@case("graphics", "Axial, radial and function-based shadings painted with sh and as patterns, coloured and uncoloured tiling patterns, and text filled with a pattern")
def shadings_and_patterns():
    pdf, catalog, pages, font = new_doc()
    ramp = pdf.add("<< /FunctionType 2 /Domain [0 1] /C0 [1 0 0] /C1 [0 0 1] /N 1 >>")
    calc = pdf.stream("{ add 2 div dup dup }", extra="/FunctionType 4 /Domain [0 1 0 1] /Range [0 1 0 1 0 1]")
    axial = pdf.add(f"<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [72 600 272 600] /Function {ramp} 0 R /Extend [true true] >>")
    radial = pdf.add(f"<< /ShadingType 3 /ColorSpace /DeviceRGB /Coords [400 650 0 400 650 60] /Function {ramp} 0 R /Extend [false true] >>")
    funcsh = pdf.add(f"<< /ShadingType 1 /ColorSpace /DeviceRGB /Domain [0 1 0 1] /Matrix [100 0 0 100 72 400] /Function {calc} 0 R >>")
    tile_c = pdf.stream("1 0 0 rg 0 0 5 5 re f 0 0 1 rg 5 5 5 5 re f", extra="/Type /Pattern /PatternType 1 /PaintType 1 /TilingType 1 /BBox [0 0 10 10] /XStep 10 /YStep 10 /Resources << >>")
    tile_u = pdf.stream("0 0 m 10 10 l S", extra="/Type /Pattern /PatternType 1 /PaintType 2 /TilingType 2 /BBox [0 0 10 10] /XStep 10 /YStep 10 /Resources << >>")
    shpat = pdf.add(f"<< /Type /Pattern /PatternType 2 /Shading {axial} 0 R /Matrix [1 0 0 1 0 -400] >>")
    res = (
        f"/Shading << /Sh1 {axial} 0 R /Sh2 {radial} 0 R /Sh3 {funcsh} 0 R >> "
        f"/Pattern << /P1 {tile_c} 0 R /P2 {tile_u} 0 R /P3 {shpat} 0 R >> /ColorSpace << /UP [/Pattern /DeviceRGB] >>"
    )
    ops = "\n".join([
        "q 72 600 200 100 re W n /Sh1 sh Q",
        "q 320 580 160 140 re W n /Sh2 sh Q",
        "q 72 400 100 100 re W n /Sh3 sh Q",
        "/Pattern cs /P1 scn 200 400 100 100 re f",
        "/UP cs 0 0.5 0 /P2 scn 320 400 100 100 re f",
        "BT /F1 48 Tf /Pattern cs /P3 scn 72 300 Td (Pattern text) Tj ET",
    ])
    page = add_page(pdf, pages, font, ops, res_extra=res)
    return finish(pdf, catalog, pages, [page])


@case("content", "Optional content: a layer hidden by default holding the word SECRET, a print-only layer, a locked layer, an OCMD visibility expression and a hidden annotation")
def optional_content_states():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    l1 = pdf.add("<< /Type /OCG /Name (Visible layer) >>")
    l2 = pdf.add("<< /Type /OCG /Name (Hidden layer) >>")
    l3 = pdf.add("<< /Type /OCG /Name (Print only) /Usage << /Print << /PrintState /ON >> /View << /ViewState /OFF >> >> >>")
    md = pdf.add(f"<< /Type /OCMD /VE [/And {l1} 0 R [/Not {l2} 0 R]] >>")
    hidden_form = form_xobject(pdf, 200, 40, "1 0 0 rg 0 0 200 40 re f", f"/OC {l2} 0 R")
    note = pdf.add(f"<< /Type /Annot /Subtype /Square /Rect [300 500 400 560] /C [1 0 0] /OC {l2} 0 R /Contents (SECRET note) /P {page} 0 R /F 4 >>")
    ops = "\n".join([
        "/OC /L1 BDC BT /F1 16 Tf 72 700 Td (Always visible) Tj ET EMC",
        "/OC /L2 BDC BT /F1 16 Tf 72 670 Td (SECRET text in a hidden layer) Tj ET EMC",
        "/OC /L3 BDC BT /F1 16 Tf 72 640 Td (Print only watermark) Tj ET EMC",
        "/OC /MD BDC BT /F1 16 Tf 72 610 Td (Shown by a visibility expression) Tj ET EMC",
        "q 1 0 0 1 72 520 cm /HF Do Q",
    ])
    res = f"/Properties << /L1 {l1} 0 R /L2 {l2} 0 R /L3 {l3} 0 R /MD {md} 0 R >> /XObject << /HF {hidden_form} 0 R >>"
    add_page(pdf, pages, font, ops, extra=f"/Annots [{note} 0 R]", res_extra=res, num=page)
    ocp = (
        f"/OCProperties << /OCGs [{l1} 0 R {l2} 0 R {l3} 0 R] /D << /Order [{l1} 0 R {l2} 0 R {l3} 0 R] "
        f"/OFF [{l2} 0 R {l3} 0 R] /Locked [{l1} 0 R] /AS [<< /Event /Print /OCGs [{l3} 0 R] /Category [/Print] >>] >> >>"
    )
    return finish(pdf, catalog, pages, [page], ocp)


@case("fonts", "Two font resources with the same BaseFont but different encodings, plus an exact duplicate: only the duplicate may be merged")
def same_basefont_different_encodings():
    pdf, catalog, pages, font = new_doc()
    remapped = pdf.add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding << /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [97 /z] >> >>")
    duplicate = pdf.add(HELV)
    ops = "\n".join([
        "BT /F1 24 Tf 72 700 Td (banana with WinAnsi) Tj ET",
        "BT /F2 24 Tf 72 660 Td (banana with a reads as z) Tj ET",
        "BT /F3 24 Tf 72 620 Td (banana with an exact duplicate font) Tj ET",
    ])
    page = add_page(pdf, pages, font, ops, res_extra="")
    pdf.objs[page] = pdf.objs[page].replace(f"/F1 {font} 0 R".encode(), f"/F1 {font} 0 R /F2 {remapped} 0 R /F3 {duplicate} 0 R".encode())
    return finish(pdf, catalog, pages, [page])


@case("text", "Page whose only words live in annotations and form fields (free text, a stamp, a filled field): text tools and blank detection must look there too")
def text_only_in_annotations():
    pdf, catalog, pages, font = new_doc()
    page = pdf.reserve()
    res = f"/Resources << /Font << /Helv {font} 0 R >> >>"
    ft_ap = form_xobject(pdf, 260, 30, "BT /Helv 16 Tf 4 8 Td (Invoice total 1,234.00) Tj ET", res)
    st_ap = form_xobject(pdf, 160, 60, "0.8 0 0 RG 3 w 2 2 156 56 re S BT /Helv 32 Tf 0.8 0 0 rg 30 18 Td (PAID) Tj ET", res)
    tx_ap = form_xobject(pdf, 240, 22, "/Tx BMC BT /Helv 12 Tf 2 6 Td (ACME Widgets Ltd) Tj ET EMC", res)
    ft = pdf.add(f"<< /Type /Annot /Subtype /FreeText /Rect [72 650 332 680] /DA (/Helv 16 Tf 0 g) /Contents (Invoice total 1,234.00) /AP << /N {ft_ap} 0 R >> /P {page} 0 R /F 4 >>")
    st = pdf.add(f"<< /Type /Annot /Subtype /Stamp /Rect [380 640 540 700] /Name /Paid /AP << /N {st_ap} 0 R >> /P {page} 0 R /F 4 >>")
    tx = pdf.add(f"<< /Type /Annot /Subtype /Widget /FT /Tx /T (customer) /V (ACME Widgets Ltd) /Rect [72 600 312 622] /DA (/Helv 12 Tf 0 g) /AP << /N {tx_ap} 0 R >> /P {page} 0 R /F 4 >>")
    add_page(pdf, pages, font, "0.9 G 0.5 w 36 36 540 720 re S", extra=f"/Annots [{ft} 0 R {st} 0 R {tx} 0 R]", num=page)
    return finish(pdf, catalog, pages, [page], f"/AcroForm << /Fields [{tx} 0 R] /DR << /Font << /Helv {font} 0 R >> >> >>")


@case("content", "A page of vector drawing only (bar chart and a hand-drawn signature stroke), with no text and no images: blank-page detection must render it")
def vector_drawing_no_text():
    bars = " ".join(f"0.2 0.4 0.8 rg {100 + i * 60} 300 40 {80 + i * 70} re f" for i in range(5))
    ops = (
        "0 G 1.5 w 90 300 m 90 700 l S 90 300 m 420 300 l S\n"
        f"{bars}\n"
        "0 G 2 w 1 J 1 j 100 160 m 130 220 150 120 175 180 c 200 240 215 140 240 170 c 265 200 290 150 330 165 c S"
    )
    pdf, catalog, pages, font = new_doc()
    page = add_page(pdf, pages, font, ops)
    return finish(pdf, catalog, pages, [page])


ARABIC_FORMS = ["ﻣ", "ﺮ", "ﺣ", "ﺒ", "ﺎ", " ", "ﺑ", "ﺎ", "ﻟ", "ﻌ", "ﺎ", "ﻟ", "ﻢ"]


@case("text", "Arabic stored in visual order, once with a ToUnicode that maps to presentation forms (U+FExx) and once mapped to base letters")
def arabic_presentation_forms():
    base = "مرحبا بالعالم"
    chars = sorted(set(ARABIC_FORMS) | set(base))
    codes = {c: i + 1 for i, c in enumerate(chars)}
    pair = {f: b for f, b in zip(ARABIC_FORMS, base)}
    tounicode = identity_tounicode([(codes[c], c) for c in chars])
    font = type0("NotoNaskhArabic", tounicode=tounicode, w="/DW 500")
    visual = "".join(f"{codes[c]:04X}" for c in reversed(ARABIC_FORMS))
    logical = "".join(f"{codes[pair.get(c, c)]:04X}" for c in reversed(ARABIC_FORMS))
    ops = f"BT /F1 24 Tf 300 700 Td <{visual}> Tj ET\nBT /F1 24 Tf 300 650 Td <{logical}> Tj ET"
    return one_page({"F1": font}, ops).serialize()


@case("text", "fi and fl ligature glyphs whose ToUnicode maps one code to two letters, so search and redaction must match 'office' and 'flow' across a ligature")
def ligatures_in_tounicode():
    tu = simple_tounicode([(0xAE, "fi"), (0xAF, "fl")] + [(c, chr(c)) for c in range(32, 127)])

    def build(pdf):
        t = pdf.stream(tu)
        return pdf.add(f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /StandardEncoding /ToUnicode {t} 0 R >>")

    return one_page({"F1": build}, "BT /F1 20 Tf 72 700 Td (The of\\256ce cash \\257ow and \\256nancial pro\\256le) Tj ET").serialize()


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
