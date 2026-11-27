"""ReportLab page with a 45-degree text watermark, a 30-degree chart label and normal body text."""
import os, sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from content import PARAS, TITLE

pdfmetrics.registerFont(TTFont("LibSerif", os.environ.get("FONT_DIR", "C:/Windows/Fonts") + "/LiberationSerif-Regular.ttf"))
pdfmetrics.registerFont(TTFont("LibSans-B", os.environ.get("FONT_DIR", "C:/Windows/Fonts") + "/LiberationSans-Bold.ttf"))
c = canvas.Canvas(sys.argv[1], pagesize=A4)
w, h = A4
c.saveState(); c.setFillColorRGB(0.85, 0.85, 0.85); c.setFont("LibSans-B", 60)
c.translate(w / 2, h / 2); c.rotate(45); c.drawCentredString(0, 0, "CONFIDENTIAL"); c.restoreState()
c.setFont("LibSans-B", 16); c.drawString(60, h - 80, TITLE)
y = h - 120
for p in PARAS * 3:
    t = c.beginText(60, y); t.setFont("LibSerif", 11)
    line = ""
    for wd in p.split():
        if c.stringWidth(line + " " + wd, "LibSerif", 11) > w - 120:
            t.textLine(line); y -= 14; line = wd
        else:
            line = (line + " " + wd).strip()
    t.textLine(line); y -= 22; c.drawText(t)
for i, name in enumerate(["North region", "South region", "East region", "West region"]):
    c.saveState(); c.translate(90 + i * 120, 120); c.rotate(30); c.setFont("LibSerif", 10); c.drawString(0, 0, name); c.restoreState()
c.save()
