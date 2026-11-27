"""Shared content for the smoke-test generators: the same documents rendered by different producers."""

TITLE = "Quarterly Operations Report"
PARAS = [
    "This report summarises how the regional teams performed during the third quarter. It covers delivery volumes, "
    "customer satisfaction and the main risks for the coming months, and it closes with the actions agreed at the "
    "review meeting on 14 October.",
    "Volumes grew in every region except the north, where a warehouse move cut capacity for three weeks. The move is "
    "now finished, and the north is expected to recover its share by the end of November.",
    "Customer satisfaction stayed above target. The largest gains came from the new tracking page, which lets "
    "customers change a delivery slot without calling the support line.",
]
BULLETS = [("Delivery volume up 8.4% on the previous quarter", ["South and east grew fastest", "North fell 2.1% during the move"]),
           ("Average delivery time down from 2.6 to 2.3 days", []),
           ("Support calls per thousand orders down 12%", [])]
STEPS = ["Finish the north warehouse handover", "Extend the tracking page to business customers",
         "Review driver rotas before the winter peak"]
TABLE_HEAD = ["Region", "Orders", "On time", "Late", "Score"]
TABLE_ROWS = [["North", "41,250", "92.1%", "3,260", "4.4"], ["South", "58,940", "96.3%", "2,180", "4.7"],
              ["East", "47,615", "95.8%", "2,000", "4.6"], ["West", "39,870", "94.0%", "2,390", "4.5"]]
TABLE_TOTAL = ["Total", "187,675", "94.8%", "9,830", "4.6"]
LONG_ROWS = [[f"INV-{1000 + i}", f"2026-0{1 + i % 9}-{10 + i % 18:02d}", ["Paper", "Toner", "Labels", "Boxes"][i % 4],
              f"{(i * 37) % 90 + 5}", f"{((i * 37) % 90 + 5) * 3.25:,.2f}"] for i in range(60)]
LONG_HEAD = ["Invoice", "Date", "Item", "Qty", "Amount"]
CODE = '''def load_orders(path, region=None):
    """Read orders from a CSV file, optionally for one region."""
    orders = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            fields = line.rstrip("\\n").split(",")
            if region and fields[2] != region:
                continue
            orders.append({"id": fields[0], "total": float(fields[4])})
    return orders'''
ARABIC = "تقرير العمليات الفصلي يلخص أداء الفرق الإقليمية خلال الربع الثالث من السنة."
HEBREW = "הדוח הרבעוני מסכם את ביצועי הצוותים האזוריים ברבעון השלישי של השנה."
CHINESE = "本报告总结了各区域团队在第三季度的表现，包括配送量、客户满意度以及未来几个月的主要风险。"
LATIN = "Ça coûte 12,50 € — Größe: Straße, señor, øl, Łódź, Ærøskøbing, naïve café."
MIXED = "The product name is מרכז 2026 and the Arabic code is أبج-123 in this sentence."
LETTER_FROM = ["Northwind Logistics Ltd", "12 Harbour Road", "Bristol BS1 4AA"]
LETTER_TO = ["Ms Jane Porter", "Porter & Sons Ltd", "88 Mill Lane", "Leeds LS2 7EJ"]
LETTER_BODY = ["Thank you for your order of 3 November. Please find the invoice below. Payment is due within thirty days "
               "of the invoice date.",
               "If you have any questions about this invoice, please contact our accounts team quoting the invoice "
               "number."]
INVOICE = [["Copy paper A4, 80gsm (box of 5 reams)", "12", "24.50", "294.00"],
           ["Toner cartridge, black", "4", "61.20", "244.80"],
           ["Shipping labels, 100 sheets", "6", "9.95", "59.70"]]
SLIDES = [("Third quarter at a glance", ["Volumes up 8.4%", "On-time delivery 94.8%", "Satisfaction 4.6 out of 5"]),
          ("Risks for the winter peak", ["Driver availability in December", "Fuel prices", "North capacity after the move"]),
          ("Next steps", STEPS)]
CHART = [("North", 41), ("South", 59), ("East", 48), ("West", 40)]
