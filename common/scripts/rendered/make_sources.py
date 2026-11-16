"""Write the HTML and spreadsheet sources that build.sh renders with Chromium and LibreOffice.

Every font is named explicitly so the renderer cannot fall back to a font we may not
redistribute: Liberation, DejaVu and the Noto families only.

Usage: make_sources.py OUT_DIR
"""

import os
import struct
import sys
import zlib

STYLE = """<style>
@page { size: A4; margin: 18mm }
body { font-family: "Liberation Serif"; font-size: 11pt }
h1, h2, th { font-family: "Liberation Sans" }
table { border-collapse: collapse; margin: 8pt 0 }
td, th { padding: 3px 6px }
.grid td, .grid th { border: 1px solid #333 }
</style>"""


def page(title, body, lang="en", direction="ltr", style=""):
    return """<!DOCTYPE html>
<html lang="%s" dir="%s"><head><meta charset="utf-8"><title>%s</title>%s%s</head>
<body>
%s
</body></html>
""" % (lang, direction, title, STYLE, "<style>%s</style>" % style if style else "", body)


def rows(cells, tag="td"):
    return "".join("<tr>%s</tr>" % "".join("<%s>%s</%s>" % (tag, c, tag) for c in r) for r in cells)


def chart_png(path):
    bars = [40, 75, 55, 90]

    def px(x, y):
        i, r = divmod(x - 10, 45)
        if 0 <= i < 4 and r < 30 and y > 110 - bars[i]:
            return (40 + 50 * i, 90, 160)
        return (60, 60, 60) if y == 111 else (255, 255, 255)

    raw = b"".join(b"\0" + b"".join(bytes(px(x, y)) for x in range(200)) for y in range(120))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 200, 120, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


REPORT = page("Quarterly Facilities Report", """<h1>Quarterly Facilities Report</h1>
<p>This report summarises energy use across four sites for the third quarter. Figures are in kilowatt hours unless stated otherwise.</p>
<h2>Summary</h2>
<ul><li>North site cut use by 12 percent.</li><li>East site added a heat pump in August.</li><li>West site figures are estimated.</li></ul>
<h2>Energy by site</h2>
<table class="grid"><caption>Energy use by site, July to September</caption>
<thead><tr><th scope="col">Site</th><th scope="col">July</th><th scope="col">August</th><th scope="col">September</th></tr></thead>
<tbody>""" + "".join('<tr><th scope="row">%s</th><td>%s</td><td>%s</td><td>%s</td></tr>' % r for r in [
    ("North", "4,100", "3,950", "3,610"), ("East", "7,520", "6,880", "6,240"),
    ("South", "5,010", "5,230", "5,180"), ("West", "2,890", "3,020", "2,970")]) + """</tbody></table>
<p><img src="chart.png" width="200" height="120" alt="Bar chart of September use: West lowest, East highest."></p>
<h2>Next steps</h2>
<p>Read the full method on the <a href="https://example.org/method" title="Project method page">project page</a>. Questions go to the facilities team.</p>""",
              lang="en-GB")

SITES = ["North", "East", "South", "West", "Harbour", "Airport", "Depot", "Library"]

TABLES = {
    "table-borderless-whitespace": page("Borderless table", "<h1>Stock levels</h1><p>Columns line up by position only: no rules, no shading.</p><table style='border:0'>"
        + rows([["Item", "Bin", "On hand", "Reorder at"]], "th")
        + rows([[n, "B-%02d" % (i * 3 + 1), str(40 + i * 17), str(20 + i * 5)] for i, n in enumerate(
            ["Bolts M6", "Washers", "Hinges", "Brackets", "Cable ties", "Fuses 5A", "Gaffer tape"])])
        + "</table><p>Counted on 3 November by the night shift.</p>",
        style="td,th{padding:2px 28px 2px 0;text-align:left} td:nth-child(n+3){text-align:right}"),
    "table-merged-cells": page("Merged cells", """<h1>Rota</h1><table class="grid">
<tr><th rowspan="2">Team</th><th colspan="3">Week 1</th><th colspan="2">Week 2</th></tr>
<tr><th>Mon</th><th>Tue</th><th>Wed</th><th>Mon</th><th>Tue</th></tr>
<tr><td rowspan="3">Blue</td><td colspan="2">Training (two days)</td><td>Site A</td><td rowspan="2">Leave</td><td>Site B</td></tr>
<tr><td>Site C</td><td colspan="2">Audit</td><td>Site A</td></tr>
<tr><td colspan="5">Bank holiday cover, all week</td></tr>
<tr><td>Green</td><td>Site B</td><td></td><td>Site D</td><td colspan="2" rowspan="1">Conference</td></tr>
</table>"""),
    "table-across-pages-repeated-header": page("Long table", "<h1>Meter readings</h1><table class='grid'><thead>"
        + rows([["Date", "Site", "Meter", "Reading (kWh)", "Change"]], "th") + "</thead><tbody>"
        + rows([["2026-%02d-%02d" % (1 + i // 28, 1 + i % 28), SITES[i % 8], "M-%04d" % (1000 + i * 7),
                 "{:,}".format(10000 + i * 137), "+%d" % (100 + (i * 37) % 90)] for i in range(90)])
        + "</tbody></table>"),
    "table-nested": page("Nested tables", """<h1>Contract summary</h1><table class="grid">
<tr><th>Party</th><th>Obligations</th></tr>
<tr><td>Supplier</td><td><table class="grid"><tr><th>Item</th><th>Due</th></tr><tr><td>Install meters</td><td>March</td></tr><tr><td>Monthly report</td><td>5th of each month</td></tr></table></td></tr>
<tr><td>Council</td><td><table class="grid"><tr><th>Item</th><th>Due</th></tr><tr><td>Site access</td><td>On request</td></tr></table><p>Payment within 30 days of invoice.</p></td></tr>
</table>"""),
    "table-zebra-no-rules": page("Zebra table", "<h1>Bookings</h1><table class='zebra'>"
        + rows([["Room", "Booked by", "From", "To"]], "th")
        + rows([["Room %d" % (i + 1), ["Ana", "Ben", "Chen", "Dina", "Eli", "Femi"][i % 6], "%02d:00" % (8 + i), "%02d:30" % (9 + i)] for i in range(12)])
        + "</table>", style=".zebra tr:nth-child(even){background:#dde6f0} .zebra th{background:#456;color:#fff} .zebra td,.zebra th{padding:4px 14px}"),
    "table-horizontal-rules-only": page("Rules only", "<h1>Results</h1><table class='bt'>"
        + rows([["Model", "Accuracy", "Recall", "F1"]], "th")
        + rows([["Baseline", "0.812", "0.774", "0.792"], ["With layout", "0.861", "0.840", "0.850"], ["With layout and fonts", "0.874", "0.858", "0.866"]])
        + "</table>", style=".bt{border-top:2px solid #000;border-bottom:2px solid #000} .bt th{border-bottom:1px solid #000} .bt td,.bt th{padding:3px 16px}"),
    "table-rotated-header-text": page("Rotated headers", "<h1>Feature matrix</h1><table class='grid rot'><tr><th></th>"
        + "".join("<th><div>%s</div></th>" % h for h in ["Merge", "Split", "Compress", "Redact", "OCR", "Sign", "Convert"])
        + "</tr>" + rows([[p] + ["&#10003;" if (i * 3 + j) % 4 else "" for j in range(7)] for i, p in enumerate(["Web", "Desktop", "Server", "Mobile"])])
        + "</table>", style=".rot th div{writing-mode:vertical-rl;transform:rotate(180deg);height:70px} .rot td{text-align:center;font-family:'DejaVu Sans'}"),
    "table-rtl-arabic": page("جدول", """<h1 style="font-family:'Noto Naskh Arabic'">استهلاك الطاقة حسب الموقع</h1>
<table class="grid" style="font-family:'Noto Naskh Arabic'">""" + rows([["الموقع", "يوليو", "أغسطس", "سبتمبر"]], "th")
        + rows([["الشمال", "٤٬١٠٠", "٣٬٩٥٠", "٣٬٦١٠"], ["الشرق", "٧٬٥٢٠", "٦٬٨٨٠", "٦٬٢٤٠"], ["الجنوب", "5,010", "5,230", "5,180"],
                ["الغرب (تقديري)", "2,890", "3,020", "2,970"]]) + "</table><p style=\"font-family:'Noto Naskh Arabic'\">الأرقام في أول صفين بالأرقام الهندية، وفي الصفين الأخيرين بالأرقام الغربية.</p>",
        lang="ar", direction="rtl", style="th{font-family:'Noto Naskh Arabic'}"),
    "table-financial-negatives": page("Statement", """<h1>Income statement</h1><table class="fin">
<tr><th></th><th>2026</th><th>2025</th></tr>
<tr><td>Revenue</td><td>1,204,330.00</td><td>1,098,412.50</td></tr>
<tr><td>Cost of sales</td><td>(612,018.25)</td><td>(587,903.10)</td></tr>
<tr class="sub"><td>Gross profit</td><td>592,311.75</td><td>510,509.40</td></tr>
<tr><td>Restructuring<sup>1</sup></td><td>(48,000.00)</td><td>&#8212;</td></tr>
<tr><td>Foreign exchange</td><td>-3,221.07</td><td>1,005.88</td></tr>
<tr><td>Tax at 19.0%</td><td>(102,516.00)</td><td>(97,196.79)</td></tr>
<tr class="tot"><td>Net profit</td><td>&#8364;438,574.68</td><td>&#8364;414,318.49</td></tr>
</table><p><sup>1</sup> One-off cost of closing the Depot site.</p>""",
        style=".fin td,.fin th{padding:2px 14px} .fin td:not(:first-child),.fin th{text-align:right;font-family:'DejaVu Sans Mono';font-size:10pt} .sub td{border-top:1px solid #000} .tot td{border-top:1px solid #000;border-bottom:3px double #000;font-weight:bold}"),
    "table-multiline-and-empty-cells": page("Notes table", """<h1>Defects log</h1><table class="grid" style="width:100%">
<tr><th style="width:12%">Ref</th><th style="width:48%">Description</th><th>Owner</th><th>Closed</th></tr>
<tr><td>D-101</td><td>Water ingress at the north stair. Ceiling tile stained over an area of about two square metres; source traced to a blocked gutter outlet on the roof.<br><br>Second visit: outlet cleared, monitoring for a month.</td><td>Estates</td><td></td></tr>
<tr><td>D-102</td><td></td><td></td><td>Yes</td></tr>
<tr><td>D-103</td><td>Door closer too strong for wheelchair users.</td><td>Facilities<br>(cover: Health and Safety)</td><td>No</td></tr>
<tr><td></td><td>Continued from D-103: replace with a delayed-action closer.</td><td></td><td></td></tr>
</table>"""),
    "table-ascii-pipes-monospace": page("Text table", """<h1>Console output</h1><pre style="font-family:'DejaVu Sans Mono';font-size:9pt">
+---------+--------+---------+----------+
| Site    |  July  | August  | Sept.    |
+---------+--------+---------+----------+
| North   |  4,100 |   3,950 |    3,610 |
| East    |  7,520 |   6,880 |    6,240 |
| South   |  5,010 |   5,230 |    5,180 |
| West *  |  2,890 |   3,020 |    2,970 |
+---------+--------+---------+----------+
* estimated
</pre>"""),
}

N = "font-family:'Noto Naskh Arabic'"
LANGUAGES = {
    "bidi-mirrored-brackets-and-numbers": page("Bidi", """<h1>Mixed direction text</h1>
<p dir="rtl" lang="ar" style="%s">بلغ الاستهلاك (في الربع الثالث) 12,450.75 كيلوواط ساعة [أي بزيادة 3.5%%] مقارنةً بالعام الماضي، حسب تقرير ISO 50001 على https://example.org/ar.</p>
<p dir="rtl" lang="he" style="font-family:'Noto Sans Hebrew'">הטלפון שלנו הוא ‎+44 20 7946 0958‎ (שלוחה 12), והמחיר הוא ₪1,299.90 [כולל מע״מ] לפי סעיף 4(ב).</p>
<p dir="ltr">An English sentence that quotes Arabic <span lang="ar" style="%s">مرحبا بالعالم (تجربة)</span> and Hebrew <span lang="he" style="font-family:'Noto Sans Hebrew'">שלום עולם</span> mid-line, then a number 1,234.</p>
<p dir="rtl" lang="ar" style="%s">‏رقم الطلب: A-2026/11-0042 والتاريخ ‎2026-11-15‎ – الحالة: <span dir="ltr">OK (200)</span>.</p>""" % (N, N, N)),
    "arabic-tashkeel-and-kashida": page("تشكيل", """<p style="%s;font-size:20pt">بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</p>
<p style="%s;font-size:16pt">يُولَدُ جَمِيعُ النَّاسِ أَحْرَارًا مُتَسَاوِينَ فِي الْكَرَامَةِ وَالْحُقُوقِ.</p>
<p style="%s;font-size:16pt">كلمـــــــة ممـــــــدودة بالكشيـــــــدة، والأرقام ١٢٣٤٥٦٧٨٩٠ و۱۲۳۴۵۶۷۸۹۰ (فارسية).</p>
<p style="font-family:'Noto Nastaliq Urdu';font-size:16pt" lang="ur">تمام انسان آزاد اور حقوق و عزت کے اعتبار سے برابر پیدا ہوئے ہیں۔</p>""" % (N, N, N), lang="ar", direction="rtl"),
    "hebrew-niqqud-and-cantillation": page("ניקוד", """<p style="font-family:'Noto Serif Hebrew';font-size:20pt">בְּרֵאשִׁ֖ית בָּרָ֣א אֱלֹהִ֑ים אֵ֥ת הַשָּׁמַ֖יִם וְאֵ֥ת הָאָֽרֶץ׃</p>
<p style="font-family:'Noto Sans Hebrew';font-size:14pt">כׇּל בְּנֵי הָאָדָם נוֹלְדוּ בְּנֵי חוֹרִין וְשָׁוִים בְּעֶרְכָּם וּבִזְכֻיּוֹתֵיהֶם.</p>
<p style="font-family:'Noto Sans Hebrew';font-size:14pt">אותו משפט בלי ניקוד: כל בני האדם נולדו בני חורין ושווים בערכם ובזכויותיהם.</p>""", lang="he", direction="rtl"),
    "thai-and-lao-no-word-spaces": page("ไทย", """<p style="font-family:'Noto Sans Thai';font-size:14pt" lang="th">มนุษย์ทั้งหลายเกิดมามีอิสระและเสมอภาคกันในเกียรติศักดิ์และสิทธิ ต่างมีเหตุผลและมโนธรรม และควรปฏิบัติต่อกันด้วยเจตนารมณ์แห่งภราดรภาพ ประโยคนี้ยาวพอที่จะต้องตัดบรรทัดกลางคำโดยไม่มีช่องว่างระหว่างคำเลยแม้แต่ตำแหน่งเดียว</p>
<p style="font-family:'Noto Sans Lao';font-size:14pt" lang="lo">ມະນຸດທຸກຄົນເກີດມາມີສິດເສລີພາບແລະສະເໝີພາບກັນໃນທາງກຽດຕິສັກ ແລະ ສິດທິ</p>
<p style="font-family:'Noto Sans Thai'">ตัวเลขไทย ๑๒๓๔๕ และเลขอารบิก 12345</p>""", lang="th"),
    "unicode-normalisation-and-case": page("Normalisation", """<h1>Same words, different code points</h1>
<p style="font-family:'DejaVu Serif';font-size:13pt">Precomposed (NFC): café résumé naïve Ångström Việt Nam<br>
Decomposed (NFD): cafe&#769; re&#769;sume&#769; nai&#776;ve A&#778;ngstro&#776;m Vie&#803;&#770;t Nam<br>
Ligature code point: &#64257;nance o&#64258;ce &#64256; and plain: finance office ff<br>
Full-width: &#65313;&#65314;&#65315; &#65297;&#65298;&#65299; and plain: ABC 123<br>
Turkish: İstanbul ıstakoz DİYARBAKIR, German: Straße STRASSE &#7838;, Greek: ΟΔΥΣΣΕΥΣ Οδυσσεύς σοφός<br>
Superscripts: x² m³ H₂O, fractions ½ ¾ and 1/2 3/4, roman: &#8546; and III<br>
Homoglyphs: p&#1072;yp&#1072;l (Cyrillic a), g&#959;&#959;gle (Greek o), plain: paypal google</p>"""),
    "invisible-characters-and-emoji-sequences": page("Invisible", """<h1>Characters you cannot see</h1>
<p style="font-family:'DejaVu Sans';font-size:13pt">Soft hyphen: super&#173;cali&#173;fragilistic, zero-width space: long&#8203;word&#8203;joined, word joiner: no&#8288;break<br>
No-break space: 10&#160;km, narrow no-break space (French): 10&#8239;000&#8239;€ et «&#8239;bonjour&#8239;»<br>
Persian with zero-width non-joiner: <span style="font-family:'Noto Naskh Arabic'" lang="fa" dir="rtl">می&#8204;خواهم</span> without: <span style="font-family:'Noto Naskh Arabic'" lang="fa" dir="rtl">میخواهم</span><br>
Left-to-right mark between Arabic words: <span style="font-family:'Noto Naskh Arabic'">كلمة&#8206;كلمة</span>, BOM in text: x&#65279;y</p>
<p style="font-family:'Noto Color Emoji';font-size:18pt">&#128104;&#8205;&#128105;&#8205;&#128103;&#8205;&#128102; &#128077;&#127997; &#127988;&#917607;&#917602;&#917605;&#917614;&#917607;&#917631; &#9764;&#65039; &#9764;&#65038; &#127475;&#127481; 1&#65039;&#8419;</p>""", lang="en"),
    "cjk-vertical-with-ruby-and-latin": page("縦書き", """<div style="writing-mode:vertical-rl;font-family:'Noto Serif CJK JP';font-size:15pt;height:230mm;line-height:1.9">
<p><ruby>人間<rt>にんげん</rt></ruby>は、<ruby>生<rt>う</rt></ruby>まれながらにして<ruby>自由<rt>じゆう</rt></ruby>であり、かつ、<ruby>尊厳<rt>そんげん</rt></ruby>と<ruby>権利<rt>けんり</rt></ruby>とについて<ruby>平等<rt>びょうどう</rt></ruby>である。</p>
<p>令和<span style="text-combine-upright:all">8</span>年<span style="text-combine-upright:all">11</span>月<span style="text-combine-upright:all">15</span>日、PDF と Stirling の試験。</p>
<p>横向きの英字 Unicode と <span style="text-orientation:upright">ABC</span> 縦向きの英字。「括弧」、句読点。……長音ー。</p>
<p lang="ko" style="font-family:'Noto Sans CJK KR'">모든 인간은 태어날 때부터 자유로우며</p>
</div>""", lang="ja"),
    "arabic-four-pages-right-to-left": page("كتيب", "".join(
        """<section style="page-break-after:always;%s;font-size:16pt"><h1>الصفحة %s</h1><p>هذه الصفحة رقم %s من كتيب يُقرأ من اليمين إلى اليسار. يجب أن تظهر الصفحة الأولى على اليمين عند الطباعة على شكل كتيب أو صفحتين في ورقة.</p><p style="font-size:60pt;text-align:center">%s</p></section>"""
        % (N, n, n, n) for n in ["١", "٢", "٣", "٤"]), lang="ar", direction="rtl"),
}

COMPARE_PARAS = [
    "The facilities team met on 4 November to review energy use across the four sites.",
    "North cut its use by 12 percent after the lighting upgrade, the largest saving this year.",
    "East added a heat pump in August. Its September figure is the first full month on the new system.",
    "South held steady. The boiler service is booked for January and should not affect supply.",
    "West figures are estimated because the meter was replaced in the middle of the quarter.",
    "The budget for next year is 48,000 euros, of which 30,000 is already committed.",
]


def compare_page(revised):
    p = list(COMPARE_PARAS)
    if revised:
        p[1] = p[1].replace("12 percent", "14 percent")
        p[2] = p[2].replace("heat pump", "ground-source heat pump")
        p[3], p[4] = p[4], p[3]
        p[5] = p[5].replace("48,000", "52,000")
        p.insert(5, "A fifth site, Harbour, joins the programme in April.")
        p[0] = p[0].replace("four sites", "four&#160;&#160;sites")
    body = "<h1>Facilities meeting notes</h1>" + "".join("<p>%s</p>" % t for t in p)
    body += "<h2>Actions</h2><ol><li>Confirm the West meter reading.</li><li>Book the South boiler service.</li></ol>"
    return page("Facilities meeting notes", body, lang="en-GB")


SPREADSHEET_COLS = 18
SPREADSHEET_ROWS = 60


def fods():
    def cell(v):
        if isinstance(v, (int, float)):
            return '<table:table-cell office:value-type="float" office:value="%s"><text:p>%s</text:p></table:table-cell>' % (v, v)
        return '<table:table-cell office:value-type="string"><text:p>%s</text:p></table:table-cell>' % v
    header = "<table:table-row>%s</table:table-row>" % "".join(cell(h) for h in ["Site"] + ["Week %d" % i for i in range(1, SPREADSHEET_COLS)])
    body = "".join("<table:table-row>%s</table:table-row>" % "".join(
        [cell("%s %d" % (SITES[r % 8], r // 8 + 1))] + [cell((r * 31 + c * 17) % 997 + 0.5 * (c % 2)) for c in range(1, SPREADSHEET_COLS)])
        for r in range(SPREADSHEET_ROWS))
    return """<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
 xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"
 xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
<office:font-face-decls><style:font-face style:name="Liberation Sans" svg:font-family="'Liberation Sans'" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"/></office:font-face-decls>
<office:styles><style:default-style style:family="table-cell"><style:text-properties style:font-name="Liberation Sans" fo:font-size="9pt"/></style:default-style></office:styles>
<office:body><office:spreadsheet><table:table table:name="Readings">%s%s</table:table>
<table:table table:name="Notes"><table:table-row>%s</table:table-row></table:table></office:spreadsheet></office:body></office:document>
""" % (header, body, cell("Second sheet: printed after the first one's pages"))


def main(out):
    os.makedirs(out, exist_ok=True)
    chart_png(os.path.join(out, "chart.png"))
    open(os.path.join(out, "report.html"), "w").write(REPORT)
    compare = {"compare-original": compare_page(False), "compare-revised": compare_page(True)}
    for name, html in {**TABLES, **LANGUAGES, **compare}.items():
        open(os.path.join(out, name + ".html"), "w").write(html)
    open(os.path.join(out, "table-spreadsheet-wide-and-long.fods"), "w").write(fods())


if __name__ == "__main__":
    main(sys.argv[1])
