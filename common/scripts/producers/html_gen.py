"""Writes HTML sources for the Chrome producer."""
import html, os, sys
from content import *

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
CSS = """
@page { size: A4; margin: 20mm 18mm; }
body { font-family: 'Liberation Serif'; font-size: 11pt; line-height: 1.35; }
h1 { font-family: 'Liberation Sans'; font-size: 20pt; } h2 { font-family: 'Liberation Sans'; font-size: 14pt; }
table { border-collapse: collapse; } td, th { padding: 3px 8px; }
.ruled td, .ruled th { border: 1px solid #444; } .num { text-align: right; }
code, pre, tt { font-family: 'Liberation Mono'; }
"""
e = html.escape


def page(name, body, css=""):
    with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as f:
        f.write(f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}{css}</style></head><body>{body}</body></html>")


def bullets():
    out = "<ul>"
    for b, subs in BULLETS:
        out += f"<li>{e(b)}" + ("<ul>" + "".join(f"<li>{e(s)}</li>" for s in subs) + "</ul>" if subs else "") + "</li>"
    return out + "</ul><ol>" + "".join(f"<li>{e(s)}</li>" for s in STEPS) + "</ol>"


def table(cls="ruled"):
    t = f"<table class='{cls}'><tr>" + "".join(f"<th>{e(h)}</th>" for h in TABLE_HEAD) + "</tr>"
    for r in TABLE_ROWS + [TABLE_TOTAL]:
        t += "<tr>" + "".join(f"<td class='{'num' if i else ''}'>{e(c)}</td>" for i, c in enumerate(r)) + "</tr>"
    return t + "</table>"


def chart():
    bars = "".join(f"<rect x='{30 + i * 50}' y='{120 - v * 2}' width='30' height='{v * 2}' fill='#3a6ea5'/>"
                   f"<text x='{45 + i * 50}' y='138' font-size='10' text-anchor='middle'>{n}</text>" for i, (n, v) in enumerate(CHART))
    return f"<svg width='240' height='145' viewBox='0 0 240 145'><line x1='25' y1='120' x2='235' y2='120' stroke='#000'/>{bars}</svg>"


paras = "".join(f"<p style='text-align:justify'>{e(p)}</p>" for p in PARAS)
page("report", f"<h1>{TITLE}</h1><h2>1 Summary</h2>{paras}<h2>2 Highlights</h2>{bullets()}"
     f"<h2>3 Results</h2>{table()}<p>See the <a href='https://example.com/q3'>full figures</a> online.</p>{paras}{paras}")
long = "<table class='ruled'><thead><tr>" + "".join(f"<th>{h}</th>" for h in LONG_HEAD) + "</tr></thead><tbody>" + "".join(
    "<tr>" + "".join(f"<td class='{'num' if i > 2 else ''}'>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in LONG_ROWS) + "</tbody></table>"
merged = ("<table class='ruled'><tr><th rowspan='2'>Region</th><th colspan='2'>Orders</th><th rowspan='2'>Score</th></tr>"
          "<tr><th>Q2</th><th>Q3</th></tr>" + "".join(f"<tr><td>{r[0]}</td><td class='num'>{r[3]}</td><td class='num'>{r[1]}</td><td class='num'>{r[4]}</td></tr>" for r in TABLE_ROWS) + "</table>")
page("tables", f"<h1>Tables</h1><h2>Ruled</h2>{table()}<h2>Borderless</h2>{table('plain')}<h2>Merged header</h2>{merged}<h2>Across pages</h2>{long}")
page("twocol", f"<h1>{TITLE}</h1><div style='columns:2; column-gap:8mm'>{paras}<figure>{chart()}<figcaption>Figure 1: Orders by region (thousands)."
     f"</figcaption></figure>{paras}{bullets()}{paras}</div>")
addr = lambda lines, align: f"<div style='text-align:{align}'>" + "<br>".join(e(x) for x in lines) + "</div>"
inv = "<table style='width:100%'><tr><th style='text-align:left'>Item</th><th>Qty</th><th>Unit</th><th>Total</th></tr>" + "".join(
    f"<tr><td>{e(r[0])}</td><td class='num'>{r[1]}</td><td class='num'>{r[2]}</td><td class='num'>{r[3]}</td></tr>" for r in INVOICE) + \
    "<tr><td></td><td></td><td class='num'><b>Total</b></td><td class='num'><b>598.50</b></td></tr></table>"
page("letter", addr(LETTER_FROM, "right") + "<p style='text-align:right'>4 November 2026</p>" + addr(LETTER_TO, "left") +
     "<p>Dear Ms Porter,</p>" + "".join(f"<p>{e(p)}</p>" for p in LETTER_BODY) + inv + "<p>Yours sincerely,</p><p>Accounts team</p>")
page("i18n", f"<h1>Languages</h1><p>{e(LATIN)}</p><p dir='rtl' style=\"font-family:'Noto Naskh Arabic'\">{ARABIC}</p>"
     f"<p dir='rtl' style=\"font-family:'Noto Sans Hebrew'\">{HEBREW}</p><p style=\"font-family:'Noto Sans SC'\">{CHINESE}</p><p>{e(MIXED)}</p>")
code = "".join(f"<div><span style='color:#888;display:inline-block;width:2em'>{i + 1}</span>{e(l).replace(' ', '&nbsp;')}</div>" for i, l in enumerate(CODE.split(chr(10))))
page("code", f"<h1>Code listing</h1><p>The function <code>load_orders</code> reads a CSV file:</p>"
     f"<div style=\"font-family:'Liberation Mono';font-size:9pt;background:#f4f4f4;padding:6px\">{code}</div><p>It returns a list of dicts.</p>")
slides = "".join(f"<section style='page-break-after:always;height:170mm;padding:15mm;background:{'#1f3b5c' if i == 0 else '#fff'};"
                 f"color:{'#fff' if i == 0 else '#000'};font-family:\"Liberation Sans\"'><h1 style='font-size:30pt'>{e(t)}</h1><ul style='font-size:20pt'>"
                 + "".join(f"<li>{e(b)}</li>" for b in bs) + "</ul></section>" for i, (t, bs) in enumerate(SLIDES))
page("slides", slides, "@page { size: 297mm 210mm; margin: 0; }")
