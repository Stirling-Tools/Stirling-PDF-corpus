#!/usr/bin/env python3
import base64
import os
import shutil
import subprocess
import sys
import zlib

CASES = []

USAGE = """\
usage: make_optimizer_cases.py OUT_DIR          writes OUT_DIR/<group>/<name>.pdf
       make_optimizer_cases.py OUT_DIR --list   prints name, group and summary as TSV
"""

PALETTE_CODESTREAM = (
    "/0//UQApAAAAAAAIAAAABAAAAAAAAAAAAAAACAAAAAQAAAAAAAAAAAABBwEB/1IADAAAAAEAAAQEAAH/XAAEQED/ZAAl"
    "AAFDcmVhdGVkIGJ5IE9wZW5KUEVHIHZlcnNpb24gMi41LjT/kAAKAAAAAAAPAAH/k4D/2Q=="
)

TWO_COMPONENT_CODESTREAM = (
    "/0//UQAsAAAAAAAIAAAABAAAAAAAAAAAAAAACAAAAAQAAAAAAAAAAAACBwEBBwEB/1IADAAAAAEAAAQEAAH/XAAEQED"
    "/ZAAlAAFDcmVhdGVkIGJ5IE9wZW5KUEVHIHZlcnNpb24gMi41LjT/kAAKAAAAAAA9AAH/k9+AuBFmkPNGGh5r5C8UFX/tuQsTZ22Xl5lK"
    "34CQEozVB5RIvNX0L286pPpEuCJ//9k="
)

HELVETICA = b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding/WinAnsiEncoding>>"


def case(group, summary):
    def register(fn):
        CASES.append((fn.__name__.replace("_", "-"), group, summary, fn))
        return fn

    return register


class Pdf:
    def __init__(self, version="1.7"):
        self.version = version
        self.objects = []
        self.trailer_extra = b""

    def add(self, body=b""):
        self.objects.append(as_bytes(body))
        return len(self.objects)

    def set(self, num, body):
        self.objects[num - 1] = as_bytes(body)

    def stream(self, entries, data):
        data = as_bytes(data)
        return as_bytes(f"<<{entries}/Length {len(data)}>>\nstream\n") + data + b"\nendstream"

    def write(self, path, root=1):
        out = bytearray(f"%PDF-{self.version}\n%\xe2\xe3\xcf\xd3\n".encode("latin-1"))
        offsets = []
        for i, body in enumerate(self.objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(self.objects) + 1}\n0000000000 65535 f \n".encode()
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += f"trailer\n<</Size {len(self.objects) + 1}/Root {root} 0 R".encode()
        out += self.trailer_extra + f">>\nstartxref\n{xref}\n%%EOF\n".encode()
        with open(path, "wb") as f:
            f.write(out)


def as_bytes(value):
    return value.encode("latin-1") if isinstance(value, str) else bytes(value)


def one_page(pdf, content, resources="/Font<</F1 4 0 R>>", content_entries=""):
    pdf.add("<</Type/Catalog/Pages 2 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources<<{resources}>>/Contents 5 0 R>>")
    pdf.add(HELVETICA)
    pdf.add(pdf.stream(content_entries, content))


def brotli_stored(data):
    out = bytearray()
    state = {"bits": 0, "count": 0}

    def put(value, width):
        state["bits"] |= (value & ((1 << width) - 1)) << state["count"]
        state["count"] += width
        while state["count"] >= 8:
            out.append(state["bits"] & 0xFF)
            state["bits"] >>= 8
            state["count"] -= 8

    def align():
        if state["count"]:
            put(0, 8 - state["count"])

    put(0, 1)
    for at in range(0, len(data), 1 << 16):
        chunk = data[at : at + (1 << 16)]
        put(0, 1)
        put(0, 2)
        put(len(chunk) - 1, 16)
        put(1, 1)
        align()
        out += chunk
    put(1, 1)
    put(1, 1)
    align()
    return bytes(out)


def hex_encode(data):
    return data.hex().encode() + b">"


def gradient_rgb(width=40, height=20):
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            pixels += bytes(((x * 6) & 255, (y * 12) & 255, ((x + y) * 5) & 255))
    return bytes(pixels)


def png_up(data, row_bytes):
    out = bytearray()
    for start in range(0, len(data), row_bytes):
        out.append(2)
        for i in range(row_bytes):
            above = data[start - row_bytes + i] if start else 0
            out.append((data[start + i] - above) & 255)
    return bytes(out)


def jp2_box(kind, body):
    return (len(body) + 8).to_bytes(4, "big") + kind.encode() + body


def palette_jp2(codestream):
    pclr = bytes([1, 0, 3, 7, 7, 7]) + bytes(256 * 3)
    header = (
        jp2_box("ihdr", bytes([0, 0, 0, 4, 0, 0, 0, 8, 0, 1, 7, 7, 0, 0]))
        + jp2_box("colr", bytes([1, 0, 0, 0, 0, 0, 16]))
        + jp2_box("pclr", pclr)
        + jp2_box("cmap", bytes([0, 0, 1, 0, 0, 0, 1, 1, 0, 0, 1, 2]))
    )
    return (
        jp2_box("jP  ", bytes([0x0D, 0x0A, 0x87, 0x0A]))
        + jp2_box("ftyp", b"jp2 \x00\x00\x00\x00jp2 ")
        + jp2_box("jp2h", header)
        + jp2_box("jp2c", codestream)
    )


def xmp(extra=""):
    return (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/"'
        ' xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">' + extra + "</rdf:Description></rdf:RDF></x:xmpmeta>"
        '<?xpacket end="w"?>'
    )


@case("filters", "Page content compressed with BrotliDecode (stored meta-blocks); rewriting it must not need a Brotli encoder")
def brotli_content_stream(path):
    pdf = Pdf("2.0")
    content = b"0 0 1 rg 40 160 220 100 re f BT /F1 18 Tf 40 120 Td (Brotli content) Tj ET\n"
    one_page(pdf, brotli_stored(content), content_entries="/Filter/BrotliDecode")
    pdf.write(path)


@case("filters", "Brotli inside a filter chain on content and on an image whose PNG predictor sits on the Brotli stage")
def brotli_chained_filters_with_predictor(path):
    pdf = Pdf("2.0")
    content = b"0 0 1 rg 20 200 120 60 re f BT /F1 14 Tf 20 170 Td (Chained filters) Tj ET q 200 0 0 100 50 40 cm /Im Do Q\n"
    one_page(
        pdf,
        hex_encode(brotli_stored(content)),
        resources="/Font<</F1 4 0 R>>/XObject<</Im 6 0 R>>",
        content_entries="/Filter[/ASCIIHexDecode/BrotliDecode]",
    )
    image = hex_encode(brotli_stored(png_up(gradient_rgb(), 120)))
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 40/Height 20/ColorSpace/DeviceRGB/BitsPerComponent 8"
            "/Filter[/ASCIIHexDecode/BrotliDecode]/DecodeParms[null<</Predictor 15/Colors 3/Columns 40>>]",
            image,
        )
    )
    pdf.write(path)


@case("filters", "Content stream whose Flate data carries a PNG predictor in DecodeParms")
def flate_predictor_content_stream(path):
    pdf = Pdf()
    content = b"0 0.6 0 rg 40 160 220 100 re f BT /F1 18 Tf 40 120 Td (Predicted content) Tj ET\n"
    padded = content.ljust(2400, b" ")
    one_page(
        pdf,
        zlib.compress(png_up(padded, 120)),
        content_entries="/Filter/FlateDecode/DecodeParms<</Predictor 12/Colors 3/Columns 40>>",
    )
    pdf.write(path)


@case("colour", "One [/Pattern /DeviceRGB] colour space shared by two pages through indirect resources")
def pattern_space_shared_across_pages(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R 4 0 R]/Count 2>>")
    pdf.add("<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources 5 0 R/Contents 8 0 R>>")
    pdf.add("<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources 5 0 R/Contents 9 0 R>>")
    pdf.add("<</ColorSpace<</CS0 6 0 R>>/Pattern<</P0 7 0 R>>>>")
    pdf.add("[/Pattern/DeviceRGB]")
    pdf.add(
        pdf.stream(
            "/PatternType 1/PaintType 2/TilingType 1/BBox[0 0 10 10]/XStep 10/YStep 10/Resources<<>>",
            b"0 0 5 5 re f 5 5 5 5 re f",
        )
    )
    pdf.add(pdf.stream("", b"/CS0 cs 1 0 0 /P0 scn 20 20 260 260 re f"))
    pdf.add(pdf.stream("", b"/CS0 cs 0 0 1 /P0 scn 20 20 260 260 re f 0 1 0 rg 100 100 100 100 re f"))
    pdf.write(path)


@case("colour", "The same pattern colour space set twice in one content stream, with different underlying colours")
def pattern_space_reused_in_one_stream(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]"
        "/Resources<</ColorSpace<</CS0[/Pattern/DeviceRGB]>>/Pattern<</P0 4 0 R>>>>/Contents 5 0 R>>"
    )
    pdf.add(
        pdf.stream(
            "/PatternType 1/PaintType 2/TilingType 1/BBox[0 0 8 8]/XStep 8/YStep 8/Resources<<>>",
            b"0 0 4 4 re f",
        )
    )
    pdf.add(pdf.stream("", b"/CS0 cs 1 0 0 /P0 scn 10 10 130 280 re f /CS0 cs 0 0.5 1 /P0 scn 160 10 130 280 re f"))
    pdf.write(path)


@case("images", "Inline RGB image whose sample bytes spell ' EI ' and so look like the end of the image")
def inline_image_samples_spell_ei(path):
    pdf = Pdf()
    samples = bytes([200, 30, 30, 0x20, 0x45, 0x49, 0x20, 0x0A, 30, 30, 200, 30])
    content = b"q 200 0 0 50 50 125 cm BI /W 4 /H 1 /CS /RGB /BPC 8 ID " + samples + b" EI Q"
    one_page(pdf, content, resources="")
    pdf.write(path)


@case("images", "Indexed image over DeviceGray that already renders grey; re-encoding it only makes it bigger")
def indexed_image_over_gray(path):
    pdf = Pdf()
    one_page(pdf, b"q 200 0 0 200 50 50 cm /Im Do Q", resources="/XObject<</Im 6 0 R>>")
    indices = bytes((x // 16 + y // 16) % 4 for y in range(64) for x in range(64))
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 64/Height 64/BitsPerComponent 8"
            "/ColorSpace[/Indexed/DeviceGray 3<00557FFF>]/Filter/FlateDecode",
            zlib.compress(indices),
        )
    )
    pdf.write(path)


@case("images", "Image with a colour-key /Mask array; greying it would change which pixels the key hides")
def colour_key_masked_image(path):
    pdf = Pdf()
    one_page(pdf, b"0 0 1 rg 0 0 300 300 re f q 200 0 0 100 50 100 cm /Im Do Q", resources="/XObject<</Im 6 0 R>>")
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 40/Height 20/ColorSpace/DeviceRGB/BitsPerComponent 8"
            "/Mask[0 60 0 255 0 255]/Filter/FlateDecode",
            zlib.compress(gradient_rgb()),
        )
    )
    pdf.write(path)


@case("images", "Image in a Separation space whose alternate is DeviceGray, so it already renders grey")
def separation_over_gray_image(path):
    pdf = Pdf()
    one_page(pdf, b"q 200 0 0 100 50 100 cm /Im Do Q", resources="/XObject<</Im 6 0 R>>")
    tints = bytes((x * 6) & 255 for y in range(20) for x in range(40))
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 40/Height 20/BitsPerComponent 8"
            "/ColorSpace[/Separation/Spot/DeviceGray<</FunctionType 2/Domain[0 1]/C0[1]/C1[0]/N 1>>]"
            "/Filter/FlateDecode",
            zlib.compress(tints),
        )
    )
    pdf.write(path)


@case("jpeg2000", "JPX image with a pclr palette box, drawn through the PDF's own Indexed colour space")
def jpx_palette_indexed(path):
    pdf = Pdf()
    one_page(pdf, b"q 200 0 0 100 50 100 cm /Im Do Q", resources="/XObject<</Im 6 0 R>>")
    palette = bytes((i, 255 - i, (i * 3) & 255)[c] for i in range(256) for c in range(3))
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 8/Height 4/BitsPerComponent 8"
            f"/ColorSpace[/Indexed/DeviceRGB 255<{palette.hex()}>]/Filter/JPXDecode",
            palette_jp2(base64.b64decode(PALETTE_CODESTREAM)),
        )
    )
    pdf.write(path)


@case("jpeg2000", "Raw two-component JPX codestream drawn in a two-colorant DeviceN space")
def jpx_two_component_devicen(path):
    pdf = Pdf()
    one_page(pdf, b"q 200 0 0 100 50 100 cm /Im Do Q", resources="/XObject<</Im 6 0 R>>")
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 8/Height 4/BitsPerComponent 8"
            "/ColorSpace[/DeviceN[/Cyan/Magenta]/DeviceCMYK 7 0 R]/Filter/JPXDecode",
            base64.b64decode(TWO_COMPONENT_CODESTREAM),
        )
    )
    pdf.add(pdf.stream("/FunctionType 4/Domain[0 1 0 1]/Range[0 1 0 1 0 1 0 1]", b"{0 0}"))
    pdf.write(path)


@case("structure", "Claims PDF/A-2B, paints only in CalRGB and has no output intent; turning it grey needs a GTS_PDFA1 intent")
def pdfa_claim_without_output_intent(path):
    pdf = Pdf()
    meta = xmp("<pdfaid:part>2</pdfaid:part><pdfaid:conformance>B</pdfaid:conformance>").encode("utf-8")
    pdf.add("<</Type/Catalog/Pages 2 0 R/Metadata 5 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]"
        "/Resources<</ColorSpace<</CS0[/CalRGB<</WhitePoint[0.9505 1 1.089]>>]>>>>/Contents 4 0 R>>"
    )
    pdf.add(pdf.stream("", b"/CS0 cs 0.9 0.2 0.1 sc 30 30 240 240 re f"))
    pdf.add(pdf.stream("/Type/Metadata/Subtype/XML", meta))
    pdf.trailer_extra = b"/ID[<00112233445566778899AABBCCDDEEFF><00112233445566778899AABBCCDDEEFF>]"
    pdf.write(path)


@case("structure", "Page carries article beads (/B) but the catalog has no /Threads, so nothing can reach them")
def article_beads_without_threads(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources<</Font<</F1 4 0 R>>>>"
        "/Contents 5 0 R/B[6 0 R]>>"
    )
    pdf.add(HELVETICA)
    pdf.add(pdf.stream("", b"BT /F1 14 Tf 30 150 Td (Beads with no thread) Tj ET"))
    pdf.add("<</Type/Bead/T 7 0 R/N 6 0 R/V 6 0 R/P 3 0 R/R[20 20 280 280]>>")
    pdf.add("<</Type/Thread/F 6 0 R/I<</Title(Orphan thread)>>>>")
    pdf.write(path)


@case("structure", "Link, GoTo action and OpenAction pointing at a page object that is not in the page tree")
def links_to_orphan_page(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R/OpenAction[6 0 R/Fit]>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources<</Font<</F1 4 0 R>>>>"
        "/Contents 5 0 R/Annots[8 0 R 9 0 R]>>"
    )
    pdf.add(HELVETICA)
    pdf.add(pdf.stream("", b"BT /F1 14 Tf 30 200 Td (Two links to a lost page) Tj ET"))
    pdf.add("<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Contents 7 0 R>>")
    pdf.add(pdf.stream("", b"BT /F1 40 Tf 30 150 Td (Unreachable) Tj ET 1 0 0 rg 0 0 300 300 re f"))
    pdf.add("<</Type/Annot/Subtype/Link/Rect[30 180 270 220]/Border[0 0 1]/Dest[6 0 R/Fit]>>")
    pdf.add("<</Type/Annot/Subtype/Link/Rect[30 120 270 160]/Border[0 0 1]/A<</S/GoTo/D[6 0 R/XYZ 0 300 0]>>>>")
    pdf.write(path)


@case("structure", "XMP metadata streams on the catalog, a page and an image, outside any PDF/A claim")
def metadata_streams_on_page_and_image(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R/Metadata 7 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources<</XObject<</Im 6 0 R>>>>"
        "/Contents 5 0 R/Metadata 8 0 R>>"
    )
    pdf.add(HELVETICA)
    pdf.add(pdf.stream("", b"q 200 0 0 100 50 100 cm /Im Do Q"))
    pdf.add(
        pdf.stream(
            "/Type/XObject/Subtype/Image/Width 40/Height 20/ColorSpace/DeviceRGB/BitsPerComponent 8"
            "/Filter/FlateDecode/Metadata 9 0 R",
            zlib.compress(gradient_rgb()),
        )
    )
    for title in ("Catalog", "Page one", "Gradient"):
        body = xmp(f"<dc:title><rdf:Alt><rdf:li xml:lang=\"x-default\">{title}</rdf:li></rdf:Alt></dc:title>")
        pdf.add(pdf.stream("/Type/Metadata/Subtype/XML", body.encode("utf-8") + b" " * 2048))
    pdf.write(path)


@case("colour", "Free-form triangle mesh shading (type 4) in DeviceRGB, stored with a Flate PNG predictor")
def mesh_shading_with_predictor(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources<</Shading<</Sh0 4 0 R>>>>/Contents 5 0 R>>"
    )
    vertices = [
        (0, 20, 20, 255, 0, 0),
        (0, 280, 20, 0, 255, 0),
        (0, 150, 280, 0, 0, 255),
    ]
    mesh = b"".join(bytes([flag]) + x.to_bytes(2, "big") + y.to_bytes(2, "big") + bytes([r, g, b])
                    for flag, x, y, r, g, b in vertices)
    pdf.add(
        pdf.stream(
            "/ShadingType 4/ColorSpace/DeviceRGB/BitsPerCoordinate 16/BitsPerComponent 8/BitsPerFlag 8"
            "/Decode[0 65535 0 65535 0 1 0 1 0 1]/Filter/FlateDecode"
            "/DecodeParms<</Predictor 12/Columns 8/Colors 1/BitsPerComponent 8>>",
            zlib.compress(png_up(mesh.ljust(24, b"\x00"), 8)),
        )
    )
    pdf.add(pdf.stream("", b"/Sh0 sh"))
    pdf.write(path)


@case("structure", "Signature field with a filled /V dictionary; rewriting the file would invalidate it")
def signature_field_present(path):
    pdf = Pdf()
    pdf.add("<</Type/Catalog/Pages 2 0 R/AcroForm<</Fields[6 0 R]/SigFlags 3>>>>")
    pdf.add("<</Type/Pages/Kids[3 0 R]/Count 1>>")
    pdf.add(
        "<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Resources<</Font<</F1 4 0 R>>>>"
        "/Contents 5 0 R/Annots[6 0 R]>>"
    )
    pdf.add(HELVETICA)
    pdf.add(pdf.stream("", b"0 0 1 rg 20 20 260 60 re f BT /F1 14 Tf 30 150 Td (Signed in colour) Tj ET"))
    pdf.add(
        "<</Type/Annot/Subtype/Widget/FT/Sig/T(Signature1)/Rect[0 0 0 0]/F 132/P 3 0 R/V 7 0 R>>"
    )
    pdf.add(
        "<</Type/Sig/Filter/Adobe.PPKLite/SubFilter/adbe.pkcs7.detached"
        "/ByteRange[0 0 0 0]/Contents<" + "00" * 64 + ">/M(D:20260101000000Z)>>"
    )
    pdf.write(path)


@case("encryption", "AES-256 with an owner password only; AES output gets a new IV on every run, so bytes never repeat")
def owner_password_aes256(path):
    if shutil.which("qpdf") is None:
        return False
    plain = path + ".plain.pdf"
    pdf = Pdf()
    one_page(pdf, b"0 0 1 rg 30 160 240 100 re f BT /F1 18 Tf 30 120 Td (Owner password only) Tj ET")
    pdf.write(plain)
    try:
        subprocess.run(
            ["qpdf", "--static-id", "--encrypt", "", "owner", "256", "--", plain, path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        os.remove(plain)
    return True


def main(argv):
    if len(argv) < 2:
        print(USAGE, end="", file=sys.stderr)
        return 2
    if "--list" in argv:
        for name, group, summary, _ in CASES:
            print(f"{name}\t{group}\t{summary}")
        return 0
    out = argv[1]
    for name, group, _, build in CASES:
        folder = os.path.join(out, group)
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, name + ".pdf")
        if build(target) is False:
            print(f"skipped {group}/{name}: qpdf not found", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
