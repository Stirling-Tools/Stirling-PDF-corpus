"""Makes PDFs directly with ReportLab and PyMuPDF."""
import os, sys
import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem, PageBreak
from reportlab.pdfgen import canvas
from content import *

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
F = os.environ.get("FONT_DIR", "C:/Windows/Fonts/") + "/"
for name, file in (("LibSerif", "LiberationSerif-Regular.ttf"), ("LibSerif-B", "LiberationSerif-Bold.ttf"),
                   ("LibSans", "LiberationSans-Regular.ttf"), ("LibSans-B", "LiberationSans-Bold.ttf"), ("DejaVu", "DejaVuSans.ttf")):
    pdfmetrics.registerFont(TTFont(name, F + file))
ss = getSampleStyleSheet()
body = ParagraphStyle("b", parent=ss["BodyText"], fontName="LibSerif", fontSize=11, leading=14, alignment=4)
h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="LibSans-B")
h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="LibSans-B")


def page_no(c, d):
    c.saveState(); c.setFont("LibSans", 9); c.drawCentredString(A4[0] / 2, 12 * mm, str(d.page))
    c.drawString(20 * mm, A4[1] - 12 * mm, TITLE); c.restoreState()


def tbl(head, rows, ruled=True, repeat=0):
    t = Table([head] + rows, repeatRows=repeat)
    st = [("FONT", (0, 0), (-1, -1), "LibSans", 10), ("FONT", (0, 0), (-1, 0), "LibSans-B", 10), ("ALIGN", (1, 0), (-1, -1), "RIGHT")]
    if ruled:
        st.append(("GRID", (0, 0), (-1, -1), 0.5, colors.black))
    else:
        st.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black))
    t.setStyle(TableStyle(st))
    return t


def bullets():
    items = []
    for b, subs in BULLETS:
        items.append(ListItem(Paragraph(b, body)))
        if subs:
            items.append(ListFlowable([ListItem(Paragraph(s, body)) for s in subs], bulletType="bullet", start="-", leftIndent=24))
    return [ListFlowable(items, bulletType="bullet"), ListFlowable([ListItem(Paragraph(s, body)) for s in STEPS], bulletType="1")]


def report():
    doc = SimpleDocTemplate(os.path.join(OUT, "reportlab-report.pdf"), pagesize=A4, title=TITLE)
    s = [Paragraph(TITLE, h1), Paragraph("1 Summary", h2)] + [Paragraph(p, body) for p in PARAS]
    s += [Paragraph("2 Highlights", h2)] + bullets() + [Paragraph("3 Results", h2), tbl(TABLE_HEAD, TABLE_ROWS + [TABLE_TOTAL]), Spacer(1, 8)]
    s += [Paragraph('See the <a href="https://example.com/q3" color="blue">full figures</a> online.', body)] + [Paragraph(p, body) for p in PARAS * 2]
    doc.build(s, onFirstPage=page_no, onLaterPages=page_no)


def tables():
    doc = SimpleDocTemplate(os.path.join(OUT, "reportlab-tables.pdf"), pagesize=A4)
    merged = Table([["Region", "Orders", "", "Score"], ["", "Q2", "Q3", ""]] + [[r[0], r[3], r[1], r[4]] for r in TABLE_ROWS])
    merged.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("SPAN", (0, 0), (0, 1)), ("SPAN", (1, 0), (2, 0)),
                                ("SPAN", (3, 0), (3, 1)), ("FONT", (0, 0), (-1, -1), "LibSans", 10)]))
    doc.build([Paragraph("Tables", h1), Paragraph("Ruled", h2), tbl(TABLE_HEAD, TABLE_ROWS + [TABLE_TOTAL]), Paragraph("Borderless", h2),
               tbl(TABLE_HEAD, TABLE_ROWS + [TABLE_TOTAL], False), Paragraph("Merged header", h2), merged,
               Paragraph("Across pages", h2), tbl(LONG_HEAD, LONG_ROWS, repeat=1)])


def letter():
    c = canvas.Canvas(os.path.join(OUT, "reportlab-letter.pdf"), pagesize=A4)
    w, h = A4
    c.setFillColorRGB(0.12, 0.23, 0.36); c.rect(20 * mm, h - 35 * mm, 30 * mm, 15 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.setFont("LibSans-B", 12); c.drawString(23 * mm, h - 29 * mm, "NWL")
    c.setFillColorRGB(0, 0, 0); c.setFont("LibSerif", 11)
    y = h - 25 * mm
    for line in LETTER_FROM + ["", "4 November 2026"]:
        c.drawRightString(w - 20 * mm, y, line); y -= 14
    y -= 10
    for line in LETTER_TO + ["", "Dear Ms Porter,"]:
        c.drawString(20 * mm, y, line); y -= 14
    for p in LETTER_BODY:
        t = c.beginText(20 * mm, y); t.setFont("LibSerif", 11)
        words, line = p.split(), ""
        for wd in words:
            if c.stringWidth(line + " " + wd, "LibSerif", 11) > w - 40 * mm:
                t.textLine(line); y -= 14; line = wd
            else:
                line = (line + " " + wd).strip()
        t.textLine(line); y -= 22; c.drawText(t)
    for item, qty, unit, total in INVOICE + [["Total", "", "", "598.50"]]:
        c.setFont("LibSerif-B" if item == "Total" else "LibSerif", 11)
        c.drawString(20 * mm, y, item); c.drawRightString(125 * mm, y, qty); c.drawRightString(150 * mm, y, unit); c.drawRightString(w - 20 * mm, y, total)
        y -= 16
    c.line(20 * mm, y + 30, w - 20 * mm, y + 30)
    c.drawString(20 * mm, y - 20, "Yours sincerely,"); c.drawString(20 * mm, y - 50, "Accounts team")
    c.save()


def form():
    c = canvas.Canvas(os.path.join(OUT, "reportlab-form.pdf"), pagesize=A4)
    c.setFont("LibSans-B", 16); c.drawString(20 * mm, 270 * mm, "Delivery change request")
    c.setFont("LibSans", 11)
    f = c.acroForm
    for i, (label, name) in enumerate((("Order number", "order"), ("Customer name", "name"), ("New delivery date", "date"))):
        y = 250 * mm - i * 18 * mm
        c.drawString(20 * mm, y + 4, label)
        f.textfield(name=name, x=70 * mm, y=y, width=90 * mm, height=8 * mm, borderWidth=1)
    c.drawString(20 * mm, 190 * mm, "Leave at the door")
    f.checkbox(name="door", x=70 * mm, y=188 * mm, size=12)
    c.drawString(20 * mm, 175 * mm, "Delivery window")
    f.choice(name="window", value="Morning", options=["Morning", "Afternoon", "Evening"], x=70 * mm, y=172 * mm, width=50 * mm, height=8 * mm)
    c.save()


def mupdf():
    story_html = f"<h1>{TITLE}</h1>" + "".join(f"<p>{p}</p>" for p in PARAS) + "<ul>" + "".join(f"<li>{b}</li>" for b, _ in BULLETS) + "</ul>" + \
        "<table border='1'><tr>" + "".join(f"<th>{x}</th>" for x in TABLE_HEAD) + "</tr>" + "".join(
            "<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in TABLE_ROWS) + "</table>" + "".join(f"<p>{p}</p>" for p in PARAS * 2)
    story = fitz.Story(story_html, user_css="body{font-family:sans-serif;font-size:11pt}")
    w = fitz.DocumentWriter(os.path.join(OUT, "mupdf-report.pdf"))
    more = True
    while more:
        dev = w.begin_page(fitz.paper_rect("a4"))
        more, _ = story.place(fitz.paper_rect("a4") + (56, 56, -56, -56))
        story.draw(dev); w.end_page()
    w.close()
    d = fitz.open()
    p = d.new_page(width=842, height=595)
    p.insert_text((60, 80), "Rotated and placed text", fontsize=24, fontname="helv")
    p.insert_text((60, 300), "Upward label", fontsize=14, fontname="helv", rotate=90)
    p.insert_text((400, 200), "Tilted note", fontsize=14, fontname="tiro", morph=(fitz.Point(400, 200), fitz.Matrix(20)))
    for i, (n, v) in enumerate(CHART):
        r = fitz.Rect(500 + i * 60, 520 - v * 4, 540 + i * 60, 520)
        p.draw_rect(r, color=(0, 0, 0), fill=(0.23, 0.43, 0.65))
        p.insert_text((505 + i * 60, 540), n, fontsize=10, fontname="helv")
    d.save(os.path.join(OUT, "mupdf-rotated.pdf"))


for fn in (report, tables, letter, form, mupdf):
    fn()
