"""Build conformance/ from the LibreOffice exports that build_sources.sh writes.

Each control passes veraPDF. Each other file takes one control and breaks one rule, named in
the file's notes row, so a validator or converter that gets it wrong points at one cause.

Usage: make_conformance.py SOURCES_DIR OUT_DIR
"""

import os
import re
import subprocess
import sys

from pdfjson import Pdf

HERE = os.path.dirname(os.path.abspath(__file__))


def lzw_encode(data):
    table = {bytes([i]): i for i in range(256)}
    next_code, width = 258, 9
    out_bits = []

    def emit(code):
        out_bits.append((code, width))

    emit(256)
    w = b""
    for byte in data:
        wc = w + bytes([byte])
        if wc in table:
            w = wc
            continue
        emit(table[w])
        table[wc] = next_code
        next_code += 1
        if next_code + 1 > (1 << width) and width < 12:
            width += 1
        if next_code >= 4094:
            emit(256)
            table = {bytes([i]): i for i in range(256)}
            next_code, width = 258, 9
        w = bytes([byte])
    if w:
        emit(table[w])
    emit(257)
    acc, nbits, out = 0, 0, bytearray()
    for code, bits in out_bits:
        acc = (acc << bits) | code
        nbits += bits
        while nbits >= 8:
            nbits -= 8
            out.append((acc >> nbits) & 0xFF)
    if nbits:
        out.append((acc << (8 - nbits)) & 0xFF)
    return bytes(out)


def set_pdfaid(pdf, part=None, conformance=None):
    x = pdf.xmp()
    if part is not None:
        x = re.sub(r"<pdfaid:part>\d</pdfaid:part>", "<pdfaid:part>%s</pdfaid:part>" % part, x)
    if conformance is not None:
        x = re.sub(r"<pdfaid:conformance>\w</pdfaid:conformance>",
                   "<pdfaid:conformance>%s</pdfaid:conformance>" % conformance, x)
    pdf.set_xmp(x)


def add_xmp_description(pdf, xml):
    pdf.set_xmp(pdf.xmp().replace("</rdf:RDF>", xml + "</rdf:RDF>", 1))


def first_font_descriptor(pdf, name_part):
    for ref in pdf.find(lambda d: d.get("/Type") == "/FontDescriptor"):
        if name_part in pdf.get(ref)["/FontName"]:
            return ref
    raise LookupError(name_part)


def untag(pdf):
    pdf.root.pop("/StructTreeRoot", None)
    pdf.root.pop("/MarkInfo", None)
    for ref in pdf.find(lambda d: "/StructParents" in d or "/StructParent" in d):
        pdf.get(ref).pop("/StructParents", None)
        pdf.get(ref).pop("/StructParent", None)


def struct_elems(pdf, tag):
    return [r for r in pdf.find(lambda d: d.get("/Type") == "/StructElem" and d.get("/S") == tag)]


def embed_file(pdf, name, raw, subtype, relationship=None, in_af=False):
    params = {"/Size": len(raw), "/ModDate": "u:D:20261115000000Z"}
    ef = pdf.add_stream({"/Type": "/EmbeddedFile", "/Subtype": subtype, "/Params": params}, raw)
    spec = {"/Type": "/Filespec", "/F": "u:" + name, "/UF": "u:" + name, "/EF": {"/F": ef, "/UF": ef},
            "/Desc": "u:" + name}
    if relationship:
        spec["/AFRelationship"] = relationship
    spec_ref = pdf.add(spec)
    names = pdf.root.setdefault("/Names", {})
    names = pdf.get(names) if isinstance(names, str) else names
    names["/EmbeddedFiles"] = {"/Names": ["u:" + name, spec_ref]}
    if in_af:
        pdf.root["/AF"] = [spec_ref]
    return spec_ref


INVOICE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:example:corpus:invoice">
  <ID>INV-2026-0042</ID>
  <IssueDate>2026-11-15</IssueDate>
  <Seller>Example Facilities Ltd</Seller>
  <Buyer>Example Council</Buyer>
  <Line><Description>Quarterly energy audit</Description><Quantity>1</Quantity><Amount currency="EUR">1250.00</Amount></Line>
  <TaxTotal currency="EUR">250.00</TaxTotal>
  <PayableAmount currency="EUR">1500.00</PayableAmount>
</Invoice>
"""

PDFA = {}
PDFUA = {}


def case(table, name, base):
    def register(fn):
        table[name] = (base, fn)
        return fn
    return register


for level in ("1b", "2b", "3b", "4"):
    case(PDFA, "pdfa-%s-control" % level, "lo-pdfa%s" % level)(lambda pdf: None)


@case(PDFA, "pdfa-2u-control", "lo-pdfa2b")
def _(pdf):
    set_pdfaid(pdf, conformance="U")


@case(PDFA, "pdfa-2b-no-output-intent", "lo-pdfa2b")
def _(pdf):
    del pdf.root["/OutputIntents"]


@case(PDFA, "pdfa-2b-font-not-embedded", "lo-pdfa2b")
def _(pdf):
    descriptor = pdf.add({"/Type": "/FontDescriptor", "/FontName": "/Arial", "/Flags": 32, "/FontBBox": [-665, -325, 2000, 1040],
                          "/ItalicAngle": 0, "/Ascent": 905, "/Descent": -212, "/CapHeight": 716, "/StemV": 80})
    font = {"/Type": "/Font", "/Subtype": "/TrueType", "/BaseFont": "/Arial", "/Encoding": "/WinAnsiEncoding",
            "/FirstChar": 32, "/LastChar": 126, "/Widths": [556] * 95, "/FontDescriptor": descriptor}
    pdf.append_content(pdf.pages()[0], b"/Artifact BMC BT /FArial 9 Tf 57 40 Td (Printed 15 November 2026, page 1 of 1) Tj ET EMC\n",
                       {"/Font": {"/FArial": pdf.add(font)}})


@case(PDFA, "pdfa-2u-font-without-tounicode", "lo-pdfa2b")
def _(pdf):
    set_pdfaid(pdf, conformance="U")
    for ref in pdf.find(lambda d: d.get("/Type") == "/Font" and d.get("/BaseFont", "").endswith("+LiberationSerif")):
        del pdf.get(ref)["/ToUnicode"]


@case(PDFA, "pdfa-1b-transparency", "lo-pdfa1b")
def _(pdf):
    page = pdf.pages()[0]
    pdf.append_content(page, b"q /GSa gs 0.85 0.2 0.2 rg 380 690 150 60 re f Q\n",
                       {"/ExtGState": {"/GSa": {"/Type": "/ExtGState", "/ca": 0.5}}})


@case(PDFA, "pdfa-1b-info-disagrees-with-xmp", "lo-pdfa1b")
def _(pdf):
    pdf.get(pdf.trailer["/Info"])["/Title"] = "u:Draft - do not circulate"


@case(PDFA, "pdfa-2b-lzw-content", "lo-pdfa2b")
def _(pdf):
    page = pdf.get(pdf.pages()[0])
    raw = b"q 0.2 0.5 0.2 rg 380 690 150 60 re f Q\n"
    page["/Contents"] = (page["/Contents"] if isinstance(page["/Contents"], list) else [page["/Contents"]]) + [
        pdf.add_stream({"/Filter": "/LZWDecode"}, lzw_encode(raw))]


@case(PDFA, "pdfa-2b-annotation-without-appearance", "lo-pdfa2b")
def _(pdf):
    page = pdf.get(pdf.pages()[0])
    note = pdf.add({"/Type": "/Annot", "/Subtype": "/Text", "/Rect": [520, 760, 540, 780], "/F": 4,
                    "/Contents": "u:Check the West figures", "/P": pdf.pages()[0]})
    page["/Annots"] = page.get("/Annots", []) + [note]


@case(PDFA, "pdfa-1b-untagged-control", "lo-pdfa1b")
def _(pdf):
    untag(pdf)


@case(PDFA, "pdfa-1a-claim-untagged", "lo-pdfa1b")
def _(pdf):
    untag(pdf)
    set_pdfaid(pdf, conformance="A")


@case(PDFA, "pdfa-2b-javascript", "lo-pdfa2b")
def _(pdf):
    pdf.root["/OpenAction"] = {"/S": "/JavaScript", "/JS": "u:app.alert('Opened');"}


@case(PDFA, "pdfa-2b-non-pdfa-attachment", "lo-pdfa2b")
def _(pdf):
    embed_file(pdf, "appendix.pdf", open(os.path.join(SRC, "lo-plain.pdf"), "rb").read(), "/application/pdf")


@case(PDFA, "pdfa-3b-attachment-without-afrelationship", "lo-pdfa3b")
def _(pdf):
    embed_file(pdf, "invoice.xml", INVOICE_XML, "/text/xml")


@case(PDFA, "pdfa-3b-xml-invoice-attachment", "lo-pdfa3b")
def _(pdf):
    embed_file(pdf, "invoice.xml", INVOICE_XML, "/text/xml", relationship="/Alternative", in_af=True)


@case(PDFA, "pdfa-4-with-info-dictionary", "lo-pdfa4")
def _(pdf):
    pdf.trailer["/Info"] = pdf.add({"/Title": "u:Quarterly Facilities Report", "/Author": "u:Facilities team"})


@case(PDFA, "pdfa-2b-encrypted", "lo-pdfa2b")
def _(pdf):
    return ["--encrypt", "--user-password=", "--owner-password=corpus-owner", "--bits=256", "--"]


def fix_link(pdf):
    for ref in pdf.find(lambda d: d.get("/Subtype") == "/Link"):
        pdf.get(ref)["/Contents"] = "u:Project method page"


case(PDFUA, "pdfua-1-libreoffice-link-without-contents", "lo-ua")(lambda pdf: None)
case(PDFUA, "pdfua-1-control", "lo-ua")(fix_link)


def ua_case(name):
    def register(fn):
        def wrapped(pdf):
            fix_link(pdf)
            return fn(pdf)
        PDFUA[name] = ("lo-ua", wrapped)
        return fn
    return register


@ua_case("pdfua-1-no-display-doc-title")
def _(pdf):
    pdf.root["/ViewerPreferences"] = {"/DisplayDocTitle": False}


@ua_case("pdfua-1-no-title")
def _(pdf):
    del pdf.get(pdf.trailer["/Info"])["/Title"]
    pdf.set_xmp(re.sub(r"<dc:title>.*?</dc:title>", "", pdf.xmp(), flags=re.S))


@ua_case("pdfua-1-no-language")
def _(pdf):
    del pdf.root["/Lang"]


@ua_case("pdfua-1-figure-without-alt")
def _(pdf):
    for ref in struct_elems(pdf, "/Figure"):
        pdf.get(ref).pop("/Alt", None)


@ua_case("pdfua-1-untagged-content")
def _(pdf):
    pdf.append_content(pdf.pages()[0], b"q 0.8 0.1 0.1 rg 57 50 200 4 re f Q\n")


@ua_case("pdfua-1-heading-skips-level")
def _(pdf):
    pdf.get(struct_elems(pdf, "/H2")[0])["/S"] = "/H4"


@ua_case("pdfua-1-unmapped-custom-role")
def _(pdf):
    pdf.get(struct_elems(pdf, "/Text body")[0])["/S"] = "/Para"


@ua_case("pdfua-1-mcid-not-in-structure")
def _(pdf):
    elem = pdf.get(struct_elems(pdf, "/H1")[0])
    elem["/K"] = []


@ua_case("pdfua-1-marked-without-structure-tree")
def _(pdf):
    del pdf.root["/StructTreeRoot"]


@ua_case("pdfua-1-claim-without-pdfuaid")
def _(pdf):
    pdf.set_xmp(re.sub(r'<rdf:Description rdf:about="" xmlns:pdfuaid=.*?</rdf:Description>', "", pdf.xmp(), flags=re.S))


def drop_pdfaid(pdf):
    pdf.set_xmp(re.sub(r'<rdf:Description rdf:about="" xmlns:pdfaid=.*?</rdf:Description>', "", pdf.xmp(), flags=re.S))


PDFUA["pdfua-1-claim-on-untagged-file"] = ("lo-pdfa1b", lambda pdf: untag(pdf) or drop_pdfaid(pdf) or add_xmp_description(
    pdf, '<rdf:Description rdf:about="" xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">'
         '<pdfuaid:part>1</pdfuaid:part></rdf:Description>'))


def build(table, folder):
    os.makedirs(os.path.join(OUT, folder), exist_ok=True)
    for name, (base, fn) in table.items():
        pdf = Pdf(os.path.join(SRC, base + ".pdf"))
        extra = fn(pdf) or []
        if "lzw" in name:
            extra = ["--stream-data=preserve"] + extra
        pdf.save(os.path.join(OUT, folder, name + ".pdf"), *extra)


if __name__ == "__main__":
    SRC, OUT = sys.argv[1], sys.argv[2]
    build(PDFA, "pdfa")
    build(PDFUA, "pdfua")
