"""Build the tools/ cases that are edits of the rendered documents: unapplied redactions, XFA,
a portfolio, duplicate pages, a right-to-left reading direction, a hybrid-reference file and
broken linearisation. ToolCases.java builds the signed and QR-separated files.

Needs qpdf and poppler's pdftotext. Usage: make_tool_cases.py RENDERED_DIR OUT_DIR
"""

import os
import re
import subprocess
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conformance"))
from pdfjson import Pdf  # noqa: E402

HELV = {"/Type": "/Font", "/Subtype": "/Type1", "/BaseFont": "/Helvetica", "/Encoding": "/WinAnsiEncoding"}


def word_boxes(path, words):
    xml = subprocess.run(["pdftotext", "-bbox", path, "-"], check=True, capture_output=True, text=True).stdout
    height = float(re.search(r'<page width="[\d.]+" height="([\d.]+)"', xml).group(1))
    boxes = []
    for m in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>', xml):
        if m.group(5) in words:
            x0, y0, x1, y1 = map(float, m.groups()[:4])
            boxes.append((x0, height - y1, x1, height - y0))
    return boxes


def redactions_unapplied(src, out):
    pdf = Pdf(src)
    page_ref = pdf.pages()[0]
    page = pdf.get(page_ref)
    annots = page.setdefault("/Annots", [])
    for x0, y0, x1, y1 in word_boxes(src, {"7,520", "6,880", "6,240", "heat", "pump"}):
        annots.append(pdf.add({
            "/Type": "/Annot", "/Subtype": "/Redact", "/P": page_ref, "/Rect": [x0, y0, x1, y1],
            "/QuadPoints": [x0, y1, x1, y1, x0, y0, x1, y0], "/IC": [0, 0, 0], "/OverlayText": "u:REDACTED",
            "/T": "u:Reviewer", "/Contents": "u:Commercially sensitive", "/F": 4}))
    pdf.save(out)


def page_object_listed_twice(src, out):
    pdf = Pdf(src)
    pages = pdf.get(pdf.root["/Pages"])
    first = pages["/Kids"][0]
    extra = pdf.add({**pdf.get(first)})
    pages["/Kids"] = [first, extra, first]
    pages["/Count"] = 3
    pdf.save(out)


def direction_r2l(src, out):
    pdf = Pdf(src)
    pdf.root.setdefault("/ViewerPreferences", {})["/Direction"] = "/R2L"
    pdf.root["/PageLayout"] = "/TwoPageRight"
    pdf.save(out)


XFA_TEMPLATE = b"""<template xmlns="http://www.xfa.org/schema/xfa-template/3.3/">
<subform name="form1" layout="tb" locale="en_GB">
<pageSet><pageArea name="Page1"><contentArea x="0.25in" y="0.25in" w="8in" h="10.5in"/><medium stock="a4" short="210mm" long="297mm"/></pageArea></pageSet>
<subform name="details" layout="tb">
<field name="applicant" w="80mm" h="9mm"><caption><value><text>Applicant name</text></value></caption><ui><textEdit/></ui></field>
<field name="amount" w="40mm" h="9mm"><caption><value><text>Amount</text></value></caption><ui><numericEdit/></ui></field>
<subform name="rows" layout="tb"><occur min="1" max="-1"/><field name="item" w="120mm" h="9mm"><ui><textEdit/></ui></field></subform>
</subform></subform></template>"""

XFA_DATASETS = b"""<xfa:datasets xmlns:xfa="http://www.xfa.org/schema/xfa-data/1.0/"><xfa:data>
<form1><details><applicant>Ana Example</applicant><amount>1250</amount><rows><item>Energy audit</item></rows><rows><item>Meter replacement</item></rows></details></form1>
</xfa:data></xfa:datasets>"""


def add_xfa(pdf, fields):
    parts = []
    for name, data in (("preamble", b'<xdp:xdp xmlns:xdp="http://ns.adobe.com/xdp/">'),
                       ("template", XFA_TEMPLATE), ("datasets", XFA_DATASETS), ("postamble", b"</xdp:xdp>")):
        parts += ["u:" + name, pdf.add_stream({}, data)]
    pdf.root["/AcroForm"] = {"/Fields": fields, "/XFA": parts, "/DA": "u:/Helv 0 Tf 0 g",
                             "/DR": {"/Font": {"/Helv": pdf.add(HELV)}}}


def xfa_static(src, out):
    pdf = Pdf(src)
    page_ref = pdf.pages()[0]
    page = pdf.get(page_ref)
    field = pdf.add({"/FT": "/Tx", "/T": "u:form1[0].details[0].applicant[0]", "/V": "u:Ana Example",
                     "/Type": "/Annot", "/Subtype": "/Widget", "/Rect": [360, 60, 540, 80], "/P": page_ref,
                     "/F": 4, "/DA": "u:/Helv 10 Tf 0 g"})
    page.setdefault("/Annots", []).append(field)
    add_xfa(pdf, [field])
    pdf.save(out)


def xfa_dynamic(src, out):
    pdf = Pdf(src)
    page_ref = pdf.pages()[0]
    page = pdf.get(page_ref)
    page.pop("/Annots", None)
    page.pop("/StructParents", None)
    page["/Resources"] = {"/Font": {"/F1": pdf.add(HELV)}}
    text = (b"BT /F1 12 Tf 72 760 Td (Please wait...) Tj 0 -20 Td "
            b"(If this message is not eventually replaced by the proper contents of the document, your PDF) Tj "
            b"0 -15 Td (viewer may not be able to display this type of document.) Tj ET\n")
    page["/Contents"] = pdf.add_stream({}, text)
    for key in ("/StructTreeRoot", "/MarkInfo", "/Outlines"):
        pdf.root.pop(key, None)
    add_xfa(pdf, [])
    pdf.root["/NeedsRendering"] = True
    pdf.save(out)


def portfolio(cover, members, out):
    pdf = Pdf(cover)
    names = []
    for i, path in enumerate(members):
        raw = open(path, "rb").read()
        name = os.path.basename(path)
        ef = pdf.add_stream({"/Type": "/EmbeddedFile", "/Subtype": "/application/pdf",
                             "/Params": {"/Size": len(raw), "/ModDate": "u:D:20261115000000Z"}}, raw)
        spec = pdf.add({"/Type": "/Filespec", "/F": "u:" + name, "/UF": "u:" + name, "/EF": {"/F": ef, "/UF": ef},
                        "/CI": {"/Type": "/CollectionItem", "/Order": i + 1, "/Title": "u:Part %d" % (i + 1)}})
        names += ["u:%02d-%s" % (i, name), spec]
    pdf.root.setdefault("/Names", {})["/EmbeddedFiles"] = {"/Names": names}
    pdf.root["/Collection"] = {"/Type": "/Collection", "/View": "/D", "/D": "u:00-" + os.path.basename(members[0]),
                               "/Schema": {"/Type": "/CollectionSchema",
                                           "/Order": {"/Type": "/CollectionField", "/Subtype": "/N", "/N": "u:Order", "/O": 0},
                                           "/Title": {"/Type": "/CollectionField", "/Subtype": "/S", "/N": "u:Title", "/O": 1}},
                               "/Sort": {"/S": "/Order"}}
    pdf.root["/PageMode"] = "/UseAttachments"
    pdf.save(out)


def hybrid_reference(out, in_update_section=False):
    font = b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"
    page = b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>"
    objstm_body = font + b" " + page
    header = b"5 0 6 %d " % (len(font) + 1)
    objstm = b"<</Type/ObjStm/N 2/First %d/Length %d>>" % (len(header), len(header) + len(objstm_body))
    content = (b"BT /F1 14 Tf 72 760 Td (Hybrid-reference file: the font and page live in an object stream) Tj "
               b"0 -20 Td (that only the cross-reference stream named by XRefStm can find.) Tj ET")
    out_b = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = {}

    def obj(n, body):
        offs[n] = len(out_b)
        out_b.extend(b"%d 0 obj\n%s\nendobj\n" % (n, body))

    obj(1, b"<</Type/Catalog/Pages 2 0 R>>")
    obj(2, b"<</Type/Pages/Kids[6 0 R]/Count 1>>")
    obj(3, objstm + b"\nstream\n" + header + objstm_body + b"\nendstream")
    obj(4, b"<</Length %d>>\nstream\n%s\nendstream" % (len(content), content))
    offs[7] = len(out_b)
    rows = [(0, 0, 255), (1, offs[1], 0), (1, offs[2], 0), (1, offs[3], 0), (1, offs[4], 0), (2, 3, 0), (2, 3, 1),
            (1, offs[7], 0)]
    data = b"".join(bytes([t]) + f.to_bytes(4, "big") + g.to_bytes(2, "big") for t, f, g in rows)
    xs = zlib.compress(data)
    out_b.extend(b"7 0 obj\n<</Type/XRef/Size 8/W[1 4 2]/Filter/FlateDecode/Length %d>>\nstream\n%s\nendstream\nendobj\n"
                 % (len(xs), xs))
    xref = len(out_b)
    out_b.extend(b"xref\n0 5\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % offs[n] for n in range(1, 5)))
    out_b.extend(b"7 1\n%010d 00000 n \n" % offs[7])
    if in_update_section:
        out_b.extend(b"trailer\n<</Size 8/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % xref)
        update = len(out_b)
        out_b.extend(b"xref\n0 0\ntrailer\n<</Size 8/Root 1 0 R/Prev %d/XRefStm %d>>\nstartxref\n%d\n%%%%EOF\n"
                     % (xref, offs[7], update))
    else:
        out_b.extend(b"trailer\n<</Size 8/Root 1 0 R/XRefStm %d>>\nstartxref\n%d\n%%%%EOF\n" % (offs[7], xref))
    open(out, "wb").write(bytes(out_b))


def linearized_then_updated(src, out, tmp):
    subprocess.run(["qpdf", "--linearize", "--deterministic-id", src, tmp], check=True)
    raw = open(tmp, "rb").read()
    pdf = Pdf(tmp)
    size = pdf.trailer["/Size"]
    root = pdf.trailer["/Root"].split()[0]
    prev = int(re.findall(rb"startxref\s+(\d+)", raw)[-1])
    body = b"%d 0 obj\n<</Title(Revised after linearisation)/Producer(make_tool_cases.py)>>\nendobj\n" % size
    off = len(raw) + 1
    upd = (b"\n" + body + b"xref\n0 1\n0000000000 65535 f \n%d 1\n%010d 00000 n \n" % (size, off)
           + b"trailer\n<</Size %d/Root %s 0 R/Info %d 0 R/Prev %d>>\nstartxref\n%d\n%%%%EOF\n"
           % (size + 1, root.encode(), size, prev, off + len(body)))
    open(out, "wb").write(raw + upd)


def linearized_wrong_length(src, out, tmp):
    subprocess.run(["qpdf", "--linearize", "--deterministic-id", src, tmp], check=True)
    raw = open(tmp, "rb").read()
    m = re.search(rb"/L (\d+)", raw[:1024])
    wrong = str(int(m.group(1)) // 2).rjust(len(m.group(1))).encode()
    open(out, "wb").write(raw[:m.start(1)] + wrong + raw[m.end(1):])


def main(rendered, out):
    os.makedirs(out, exist_ok=True)
    report = os.path.join(rendered, "lo-plain.pdf")
    tmp = os.path.join(out, ".tmp.pdf")
    redactions_unapplied(report, os.path.join(out, "redact-annotations-not-applied.pdf"))
    subprocess.run(["qpdf", "--empty", "--deterministic-id", "--pages", report, os.path.join(rendered, "table-zebra-no-rules.pdf"),
                    report, os.path.join(rendered, "table-nested.pdf"), report, "--",
                    os.path.join(out, "duplicate-pages-three-copies.pdf")], check=True)
    page_object_listed_twice(report, os.path.join(out, "page-object-listed-twice.pdf"))
    direction_r2l(os.path.join(rendered, "arabic-four-pages-right-to-left.pdf"),
                  os.path.join(out, "arabic-booklet-direction-r2l.pdf"))
    xfa_static(report, os.path.join(out, "xfa-static-with-acroform.pdf"))
    xfa_dynamic(report, os.path.join(out, "xfa-dynamic-please-wait.pdf"))
    portfolio(os.path.join(rendered, "table-nested.pdf"),
              [os.path.join(rendered, n + ".pdf") for n in ("table-zebra-no-rules", "bidi-mirrored-brackets-and-numbers", "compare-original")],
              os.path.join(out, "portfolio-collection.pdf"))
    hybrid_reference(os.path.join(out, "hybrid-reference-xrefstm.pdf"))
    hybrid_reference(os.path.join(out, "hybrid-reference-xrefstm-in-update-section.pdf"), in_update_section=True)
    linearized_then_updated(report, os.path.join(out, "linearized-then-incrementally-updated.pdf"), tmp)
    linearized_wrong_length(report, os.path.join(out, "linearized-wrong-file-length.pdf"), tmp)
    os.remove(tmp)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
