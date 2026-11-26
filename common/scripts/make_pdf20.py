#!/usr/bin/env python3
"""Writes small PDF 2.0 samples: 2.0-only features, AES-256 (R6) encryption and two
invalid version and encryption pairings that validators should flag.

    python3 make_pdf20.py OUT_DIR    # writes OUT_DIR/<name>.pdf

Needs pikepdf. The unencrypted files and the RC4 file are byte-identical on every run.
The AES-256 ones are not, because qpdf picks a random salt, key and IV for each save.
The regression file in pdf20/ is a Stirling-PDF output and is not written here.
"""

import os
import sys

import pikepdf
from pikepdf import Array, Dictionary, Name, String

UTF8_BOM = b"\xef\xbb\xbf"


def xmp(title):
    return (
        b'<?xpacket begin="' + UTF8_BOM + b'" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">' + title.encode() + b"</rdf:li></rdf:Alt></dc:title>"
        b'</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>'
    )


def pages(pdf, count, marked=False):
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    for i in range(count):
        pdf.add_blank_page(page_size=(612, 792))
        page = pdf.pages[i]
        page.Resources = Dictionary(Font=Dictionary(F1=font))
        text = f"BT /F1 24 Tf 72 700 Td (PDF 2.0 page {i + 1}) Tj ET"
        if marked:
            text = f"/GS1 gs /P <</MCID 0>> BDC {text} EMC"
        page.Contents = pdf.make_stream(text.encode())


def page_output_intent(pdf):
    # OutputIntents on a page dictionary is new in PDF 2.0.
    pdf.pages[0].obj.OutputIntents = Array([Dictionary(
        Type=Name.OutputIntent, S=Name.GTS_PDFX, OutputConditionIdentifier=String("Custom"))])


def plain():
    pdf = pikepdf.new()
    pages(pdf, 3)
    pdf.docinfo = pdf.make_indirect(Dictionary(CreationDate=String("D:20260101000000Z")))
    pdf.Root.Metadata = pdf.make_stream(xmp("XMP Title 2.0"), Type=Name.Metadata, Subtype=Name.XML)
    title = String(UTF8_BOM + "UTF8 été ✓".encode())
    item = pdf.make_indirect(Dictionary(Title=title, Dest=Array([pdf.pages[0].obj, Name.Fit])))
    outlines = pdf.make_indirect(Dictionary(Type=Name.Outlines, First=item, Last=item, Count=1))
    item.Parent = outlines
    pdf.Root.Outlines = outlines
    data = pdf.make_stream(b"hello,world\n", Type=Name.EmbeddedFile, Subtype=Name("/text#2Fcsv"))
    spec = pdf.make_indirect(Dictionary(
        Type=Name.Filespec, F=String("data.csv"), UF=String("data.csv"),
        EF=Dictionary(F=data), AFRelationship=Name.Data))
    pdf.Root.AF = Array([spec])
    pdf.Root.Names = Dictionary(EmbeddedFiles=Dictionary(Names=Array([String("data.csv"), spec])))
    page_output_intent(pdf)
    return pdf


def rich():
    pdf = pikepdf.new()
    pages(pdf, 3, marked=True)
    gs = pdf.make_indirect(Dictionary(Type=Name.ExtGState, UseBlackPtComp=Name.ON))
    ns = pdf.make_indirect(Dictionary(Type=Name.Namespace, NS=String("http://iso.org/pdf2/ssn")))
    root = pdf.make_indirect(Dictionary(Type=Name.StructTreeRoot, Namespaces=Array([ns])))
    doc = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=Name.DocumentFragment, NS=ns, P=root, K=Array()))
    root.K = doc
    nums = Array()
    for i, page in enumerate(pdf.pages):
        page.Resources.ExtGState = Dictionary(GS1=gs)
        page.obj.StructParents = i
        tag = Name.Aside if i == 1 else Name.P
        elem = pdf.make_indirect(Dictionary(Type=Name.StructElem, S=tag, NS=ns, P=doc, Pg=page.obj, K=0))
        doc.K.append(elem)
        nums.extend([i, Array([elem])])
    root.ParentTree = pdf.make_indirect(Dictionary(Nums=nums))
    root.ParentTreeNextKey = len(pdf.pages)
    pdf.Root.StructTreeRoot = root
    pdf.Root.MarkInfo = Dictionary(Marked=True)
    pdf.Root.Lang = String("en-GB")
    name = "sóurce-数据.xml"
    data = pdf.make_stream(b"<xml/>", Type=Name.EmbeddedFile, Subtype=Name("/application#2Fxml"))
    spec = pdf.make_indirect(Dictionary(
        Type=Name.Filespec, F=String("source.xml"), UF=String(name),
        EF=Dictionary(F=data, UF=data), AFRelationship=Name.Source))
    pdf.pages[0].obj.AF = Array([spec])
    pdf.Root.AF = Array([spec])
    pdf.Root.Names = Dictionary(EmbeddedFiles=Dictionary(Names=Array([String(name), spec])))
    projection = pdf.make_indirect(Dictionary(
        Type=Name.Annot, Subtype=Name.Projection, Rect=Array([72, 600, 200, 650]), Contents=String("projection")))
    media = pdf.make_indirect(Dictionary(
        Type=Name.Annot, Subtype=Name.RichMedia, Rect=Array([72, 500, 200, 550]),
        RichMediaContent=Dictionary(Assets=Dictionary(Names=Array())), RichMediaSettings=Dictionary()))
    pdf.pages[0].obj.Annots = Array([projection, media])
    part = pdf.make_indirect(Dictionary(
        Type=Name.DPart, Start=pdf.pages[0].obj, End=pdf.pages[2].obj, DPM=Dictionary(Chapter=String("One"))))
    part_root = pdf.make_indirect(Dictionary(Type=Name.DPartRoot, DPartRootNode=part, NodeNameList=Array([Name.Chapter])))
    part.Parent = part_root
    for page in pdf.pages:
        page.obj.DPart = part
    pdf.Root.DPartRoot = part_root
    page_output_intent(pdf)
    pdf.Root.Metadata = pdf.make_stream(xmp("Rich 2.0"), Type=Name.Metadata, Subtype=Name.XML)
    return pdf


def annotations():
    pdf = pikepdf.new()
    pages(pdf, 2)
    link = pdf.make_indirect(Dictionary(
        Type=Name.Annot, Subtype=Name.Link, Rect=Array([72, 690, 300, 730]), Border=Array([0, 0, 0]),
        Dest=Array([pdf.pages[1].obj, Name.Fit])))
    note = pdf.make_indirect(Dictionary(
        Type=Name.Annot, Subtype=Name.Text, Rect=Array([300, 100, 320, 120]), Contents=String("note"), Name=Name.Comment))
    pdf.pages[0].obj.Annots = Array([link, note])
    return pdf


def save(pdf, path, version="2.0", encryption=None, object_streams=True):
    mode = pikepdf.ObjectStreamMode.generate if object_streams else pikepdf.ObjectStreamMode.disable
    # A fixed /ID keeps output identical; qpdf refuses deterministic_id when encrypting.
    # An empty version lets qpdf choose; forcing 1.7 would silently drop R6 encryption.
    pdf.save(path, force_version=version, object_stream_mode=mode, encryption=encryption,
             static_id=True, compress_streams=True)


def drop_extensions(path):
    # Blank out the ADBE extension qpdf adds for R6 in the same number of bytes, so offsets hold.
    with open(path, "rb") as f:
        data = f.read()
    start = data.find(b"/Extensions")
    end = data.find(b">> >>", start) + len(b">> >>")
    if not data.startswith(b"%PDF-1.7") or start < 0 or data.count(b"/Extensions") != 1:
        sys.exit(f"{path}: expected a 1.7 header and one plaintext /Extensions")
    data = data[:start] + b" " * (end - start) + data[end:]
    with open(path, "wb") as f:
        f.write(data)


def main(out):
    os.makedirs(out, exist_ok=True)
    p = lambda name: os.path.join(out, name + ".pdf")
    restricted = pikepdf.Permissions(modify_other=False, extract=False, print_highres=False)
    save(plain(), p("plain-features"))
    save(rich(), p("rich-features"))
    save(rich(), p("rich-aes-256-owner-restricted"),
         encryption=pikepdf.Encryption(owner="owner", user="", R=6, aes=True, allow=restricted))
    save(rich(), p("rich-aes-256-metadata-not-encrypted"),
         encryption=pikepdf.Encryption(owner="owner", user="", R=6, aes=True, metadata=False))
    save(rich(), p("rich-aes-256-user-password"),
         encryption=pikepdf.Encryption(owner="owner", user="user", R=6, aes=True))
    save(plain(), p("aes-256-unicode-user-password"),
         encryption=pikepdf.Encryption(owner="owner", user="pässwörd", R=6, aes=True))
    save(annotations(), p("link-and-text-annotations"))
    save(plain(), p("invalid-rc4-128-in-pdf-2-0"), object_streams=False,
         encryption=pikepdf.Encryption(owner="owner", user="user", R=3, aes=False, metadata=False))
    save(plain(), p("invalid-pdf-1-7-aes-256-no-extensions"), version="", object_streams=False,
         encryption=pikepdf.Encryption(owner="owner", user="", R=6, aes=True))
    drop_extensions(p("invalid-pdf-1-7-aes-256-no-extensions"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
