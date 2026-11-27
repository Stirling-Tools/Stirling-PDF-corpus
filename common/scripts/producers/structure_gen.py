"""Structure samples: QR codes and barcodes, sparse and single-character tables, heading levels, a title on every slide.

python structure_gen.py OUT_DIR writes reportlab-labels.pdf, reportlab-qrslip.pdf, reportlab-sparse.pdf, mupdf-slides.pdf,
finance.xlsx, cells.docx and tex/levels.tex; build.sh turns the last three into PDFs with LibreOffice and pdfLaTeX.
"""
import os, random, sys
import fitz
from docx import Document
from docx.shared import Mm, Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128, qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from content import *

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
F = os.environ.get("FONT_DIR", "C:/Windows/Fonts") + "/"

def barcodes():
    pdfmetrics.registerFont(TTFont("San", F + "LiberationSans-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("SanB", F + "LiberationSans-Bold.ttf"))
    c = canvas.Canvas(os.path.join(OUT, "reportlab-labels.pdf"), pagesize=A4)
    w, h = A4
    for i in range(4):
        x, y = 40 + (i % 2) * 270, h - 60 - (i // 2) * 210
        c.setStrokeColorRGB(0.6, 0.6, 0.6); c.roundRect(x, y - 180, 250, 180, 8)
        c.setFont("SanB", 13); c.drawString(x + 12, y - 24, f"Parcel {i + 1} of 4")
        c.setFont("San", 10)
        for k, line in enumerate(LETTER_TO):
            c.drawString(x + 12, y - 44 - k * 13, line)
        bc = code128.Code128(f"NWL{1042 + i:06d}", barHeight=34, barWidth=1.0)
        bc.drawOn(c, x + 8, y - 160)
        c.drawString(x + 20, y - 172, f"NWL{1042 + i:06d}")
        q = qr.QrCodeWidget(f"https://example.com/track/NWL{1042 + i}")
        dr = Drawing(70, 70); dr.add(q); renderPDF.draw(dr, c, x + 172, y - 120)
    c.showPage()
    c.setFillColorRGB(0.07, 0.08, 0.09); c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setFillColorRGB(0.85, 0.87, 0.9); c.setFont("SanB", 22); c.drawString(60, h - 90, "Night shift summary")
    c.setFont("San", 11)
    y = h - 130
    for p in PARAS:
        t = c.beginText(60, y); t.setFont("San", 11); line = ""
        for wd in p.split():
            if c.stringWidth(line + " " + wd, "San", 11) > w - 120:
                t.textLine(line); y -= 14; line = wd
            else:
                line = (line + " " + wd).strip()
        t.textLine(line); y -= 24; c.drawText(t)
    c.save()



def qr_slip():
    pdfmetrics.registerFont(TTFont("San", F + "LiberationSans-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("SanB", F + "LiberationSans-Bold.ttf"))
    c = canvas.Canvas(os.path.join(OUT, "reportlab-qrslip.pdf"), pagesize=A4)
    w, h = A4
    c.setFont("SanB", 16); c.drawString(50, h - 70, "Invoice INV-1042")
    c.setFont("San", 10)
    for k, line in enumerate(LETTER_FROM):
        c.drawString(50, h - 95 - k * 13, line)
    y = h - 170
    c.setFont("SanB", 10)
    for x, t in [(50, "Item"), (300, "Qty"), (380, "Unit"), (480, "Amount")]:
        c.drawString(x, y, t)
    c.line(50, y - 4, 545, y - 4)
    c.setFont("San", 10)
    for i, r in enumerate(LONG_ROWS[:6]):
        yy = y - 20 - i * 16
        c.drawString(50, yy, r[2]); c.drawRightString(320, yy, r[3]); c.drawRightString(410, yy, "3.25"); c.drawRightString(545, yy, r[4])
    c.setDash(3, 3); c.line(0, 300, w, 300); c.setDash()
    c.setFont("San", 7); c.drawString(20, 303, "Separate before paying in")
    c.line(178, 0, 178, 300)
    c.setFont("SanB", 11); c.drawString(15, 275, "Receipt"); c.drawString(190, 275, "Payment part")
    c.setFont("SanB", 7)
    for x0, y0 in [(15, 255), (370, 255)]:
        c.drawString(x0, y0, "Account / Payable to")
        c.setFont("San", 8)
        for k, t in enumerate(["CH44 3199 9123 0008 8901 2", "Northwind Logistics Ltd", "12 Harbour Road", "Bristol BS1 4AA"]):
            c.drawString(x0, y0 - 11 - k * 10, t)
        c.setFont("SanB", 7); c.drawString(x0, y0 - 60, "Reference")
        c.setFont("San", 8); c.drawString(x0, y0 - 71, "21 00000 00003 13947 14300 09017")
        c.setFont("SanB", 7)
    c.drawString(15, 110, "Currency"); c.drawString(70, 110, "Amount")
    c.drawString(190, 110, "Currency"); c.drawString(250, 110, "Amount")
    c.setFont("San", 9); c.drawString(15, 98, "GBP"); c.drawString(70, 98, "1 234.50"); c.drawString(190, 98, "GBP"); c.drawString(250, 98, "1 234.50")
    for x0, y0, ww, hh in [(15, 40, 150, 40), (250, 40, 100, 40)]:
        for cx, cy, dx, dy in [(x0, y0 + hh, 8, 0), (x0, y0 + hh, 0, -8), (x0 + ww, y0 + hh, -8, 0), (x0 + ww, y0 + hh, 0, -8),
                               (x0, y0, 8, 0), (x0, y0, 0, 8), (x0 + ww, y0, -8, 0), (x0 + ww, y0, 0, 8)]:
            c.line(cx, cy, cx + dx, cy + dy)
    q = qr.QrCodeWidget("SPC\n0200\n1\nCH4431999123000889012\nS\nNorthwind Logistics Ltd\n12 Harbour Road\n\nBS1 4AA\nBristol\nGB\n\n\n\n\n\n\n\n1234.50\nGBP")
    b = q.getBounds(); s = 130.0 / (b[2] - b[0])
    dr = Drawing(130, 130, transform=[s, 0, 0, s, 0, 0]); dr.add(q); renderPDF.draw(dr, c, 190, 125)
    c.setFillColorRGB(0, 0, 0); c.rect(247, 182, 16, 16, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1); c.rect(253, 186, 4, 8, fill=1, stroke=0); c.rect(251, 188, 8, 4, fill=1, stroke=0)
    c.save()



def finance():
    wb = Workbook(); ws = wb.active; ws.title = "P&L"
    wb._fonts[0] = Font(name="Liberation Sans", size=11)
    thin = Side(style="thin", color="999999")
    ws.merge_cells("A1:F1"); ws["A1"] = "Profit and loss, year to date (GBP thousands)"; ws["A1"].font = Font(name="Liberation Sans", bold=True, size=14)
    ws.merge_cells("B2:C2"); ws["B2"] = "2026"; ws.merge_cells("D2:E2"); ws["D2"] = "2025"; ws["F2"] = "Change"
    for c in ["B2", "D2", "F2"]:
        ws[c].alignment = Alignment(horizontal="center"); ws[c].font = Font(name="Liberation Sans", bold=True)
    ws.append(["", "H1", "H2", "H1", "H2", "%"])
    lines = [("Revenue", 4120, 4385, 3890, 4010), ("Cost of sales", -2610, -2702, -2480, -2551), ("Gross profit", None, None, None, None),
             ("Staff", -812, -840, -790, -801), ("Depreciation", -95, -97, -91, -92), ("Warehouse move", 0, -184, 0, 0),
             ("Operating profit", None, None, None, None)]
    r0 = 4
    for i, (n, *v) in enumerate(lines):
        r = r0 + i
        ws.cell(r, 1, n)
        for j in range(4):
            col = "BCDE"[j]
            if v[j] is None:
                src = f"{col}{r0}:{col}{r - 1}" if n == "Gross profit" else f"{col}{r0 + 2}:{col}{r - 1}"
                ws.cell(r, 2 + j, f"=SUM({src})").font = Font(name="Liberation Sans", bold=True)
            else:
                ws.cell(r, 2 + j, v[j])
            ws.cell(r, 2 + j).number_format = '#,##0;[Red](#,##0);"-"'
        ws.cell(r, 6, f"=IF(D{r}+E{r}=0,\"n/a\",(B{r}+C{r})/(D{r}+E{r})-1)").number_format = "0.0%"
        for j in range(6):
            ws.cell(r, 1 + j).border = Border(bottom=thin)
        if v[0] is None:
            for j in range(6):
                ws.cell(r, 1 + j).fill = PatternFill("solid", fgColor="EEF2F7")
    ws.column_dimensions["A"].width = 24
    ws2 = wb.create_sheet("Regions")
    ws2.append(TABLE_HEAD)
    for r in TABLE_ROWS + [TABLE_TOTAL]:
        ws2.append(r)
    ws.page_setup.orientation = "landscape"
    wb.save(os.path.join(OUT, "finance.xlsx"))



def tables():
    d = Document()
    st = d.styles["Normal"]; st.font.name = "Liberation Sans"; st.font.size = Pt(10)
    sec = d.sections[0]; sec.page_width, sec.page_height = Mm(210), Mm(297)
    d.styles["Heading 1"].font.name = "Liberation Sans"
    d.add_heading("Stock check", 1)
    d.add_paragraph("Counts by shelf. Empty cells mean the shelf was not counted.")
    rows = [["Shelf", "Mon", "Tue", "Wed", "Thu", "Fri"], ["A1", "12", "", "9", "", "7"], ["A2", "", "", "4", "", ""],
            ["B1", "30", "28", "", "25", ""], ["B2", "", "", "", "", "3"], ["C1", "5", "", "", "", ""]]
    t = d.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Table Grid"
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            t.cell(r, c).text = v
    d.add_heading("Defect tally", 1)
    d.add_paragraph("One digit per line and day; zero means no defects.")
    tally = [["Line"] + [str(i) for i in range(1, 11)]] + [[n] + [str((k * j) % 3 if n != "L3" else 0) for j in range(10)] for k, n in
                                                            enumerate(["L1", "L2", "L3", "L4"], 1)]
    t = d.add_table(rows=len(tally), cols=11); t.style = "Table Grid"
    for r, row in enumerate(tally):
        for c, v in enumerate(row):
            t.cell(r, c).text = v
    d.add_heading("Checklist", 1)
    marks = [["Task", "Done", "N/A"], ["Seal doors", "X", ""], ["Test alarm", "", "X"], ["Log temperature", "X", ""], ["Sign off", "", ""]]
    t = d.add_table(rows=len(marks), cols=3)
    for r, row in enumerate(marks):
        for c, v in enumerate(row):
            t.cell(r, c).text = v
    for para in d.paragraphs:
        for run in para.runs:
            run.font.name = "Liberation Sans"
    d.save(os.path.join(OUT, "cells.docx"))




def sparse():
    pdfmetrics.registerFont(TTFont("San", F + "LiberationSans-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("SanB", F + "LiberationSans-Bold.ttf"))
    random.seed(3)
    cases = {
        "Grouped": [["Region", "Branch", "Orders", "Late"], ["North", "Leeds", "410", "12"], ["", "York", "220", "4"], ["", "Hull", "130", ""],
                    ["South", "Bristol", "590", "9"], ["", "Bath", "180", ""], ["", "Exeter", "", "2"]],
        "Empty column": [["Code", "Name", "Notes", "Qty"], ["A1", "Paper", "", "12"], ["A2", "Toner", "", "3"], ["B1", "Labels", "", "800"],
                         ["B2", "Boxes", "", "40"], ["C1", "Tape", "", "9"]],
        "Very sparse": [["Day"] + [f"S{i}" for i in range(1, 9)]] + [[f"Day {r}"] + [(str(random.randint(1, 9)) if random.random() < 0.2 else "")
                                                                     for _ in range(8)] for r in range(1, 11)],
        "Blank header": [["", "Q1", "Q2", "Q3", "Q4"], ["Revenue", "4.1", "4.4", "", "4.6"], ["Costs", "", "2.7", "2.6", ""],
                         ["Profit", "1.5", "", "1.4", ""]],
    }
    c = canvas.Canvas(os.path.join(OUT, "reportlab-sparse.pdf"), pagesize=A4)
    y = 780
    for name, rows in cases.items():
        c.setFont("SanB", 13); c.drawString(60, y, name); y -= 22
        n = len(rows[0]); xs = [60 + j * (470 / n) for j in range(n)]
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                if v:
                    c.setFont("SanB" if i == 0 else "San", 10)
                    if j > 0:
                        c.drawRightString(xs[j] + 40, y, v)
                    else:
                        c.drawString(xs[j], y, v)
            if i == 0 and name != "Very sparse":
                c.line(xs[0], y - 4, xs[-1] + 45, y - 4)
            y -= 16
        y -= 20
    c.save()


def slides():
    d = fitz.open()
    for i in range(10):
        p = d.new_page(width=720, height=540)
        p.insert_text((54, 50), "Quarterly Business Review", fontsize=28, fontname="hebo")
        for k in range(4):
            p.insert_text((72, 140 + k * 45), f"Point {k + 1} of slide {i + 1} about the regional teams", fontsize=18, fontname="helv")
        p.insert_text((650, 520), str(i + 1), fontsize=10, fontname="helv")
    d.save(os.path.join(OUT, "mupdf-slides.pdf"))


LEVELS = r"""\documentclass[11pt,a4paper]{report}
\usepackage[T1]{fontenc}\usepackage{lmodern}\usepackage[margin=2.5cm]{geometry}
\begin{document}
\chapter{Operations}
""" + PARAS[0] + r"""
\section{Volumes}
""" + PARAS[1] + r"""
\subsection{North}
""" + PARAS[2] + r"""
\subsubsection{Warehouse move}
""" + PARAS[0] + r"""
\paragraph{Capacity.} """ + PARAS[1] + r"""
\subsection{South}
""" + PARAS[2] + r"""
\section{Satisfaction}
""" + PARAS[0] + r"""
\chapter{Plans}
\section{Winter peak}
""" + PARAS[1] + r"""
\end{document}
"""


def levels():
    os.makedirs(os.path.join(OUT, "tex"), exist_ok=True)
    open(os.path.join(OUT, "tex", "levels.tex"), "w", encoding="utf-8").write(LEVELS)


barcodes(); qr_slip(); finance(); tables(); sparse(); slides(); levels()
