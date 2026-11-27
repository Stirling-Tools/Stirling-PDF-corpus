"""Writes LaTeX sources for the pdfLaTeX, XeLaTeX and LuaLaTeX producers."""
import os, sys
from content import *

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)


def esc(s):
    for a, b in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("_", r"\_"), ("#", r"\#"), ("$", r"\$")):
        s = s.replace(a, b)
    return s


def write(name, body, pre=r"\documentclass[11pt,a4paper]{article}" "\n" r"\usepackage[T1]{fontenc}"):
    with open(os.path.join(OUT, name + ".tex"), "w", encoding="utf-8") as f:
        f.write(pre + "\n" + body)


common = r"""\usepackage[margin=2cm]{geometry}
\usepackage{booktabs,longtable,multirow,enumitem,fancyhdr,xcolor,listings}
\usepackage[hidelinks]{hyperref}
\pagestyle{fancy}\fancyhead[L]{%s}\fancyfoot[C]{\thepage}
""" % TITLE
paras = "\n\n".join(esc(p) for p in PARAS)
items = "\\begin{itemize}\n" + "\n".join(
    "\\item " + esc(b) + ("\n\\begin{itemize}\n" + "\n".join("\\item " + esc(s) for s in subs) + "\n\\end{itemize}" if subs else "")
    for b, subs in BULLETS) + "\n\\end{itemize}\n\\begin{enumerate}\n" + "\n".join("\\item " + esc(s) for s in STEPS) + "\n\\end{enumerate}"
tab = ("\\begin{tabular}{lrrrr}\\toprule\n" + " & ".join(TABLE_HEAD) + "\\\\\\midrule\n"
       + "\n".join(" & ".join(esc(c) for c in r) + "\\\\" for r in TABLE_ROWS) + "\\midrule\n"
       + " & ".join(esc(c) for c in TABLE_TOTAL) + "\\\\\\bottomrule\\end{tabular}")
report_body = (common + "\\begin{document}\n\\section*{" + TITLE + "}\n\\section{Summary}\n" + paras
               + "\\footnote{Figures exclude returns processed after 30 September.}\n\\section{Highlights}\n" + items
               + "\n\\section{Results}\n\\begin{center}" + tab + "\\end{center}\nSee the \\href{https://example.com/q3}{full figures} online.\n\n"
               + paras + "\n\n" + paras + "\n\\end{document}\n")
write("report", report_body)
ruled = ("\\begin{tabular}{|l|r|r|r|r|}\\hline\n" + " & ".join(TABLE_HEAD) + "\\\\\\hline\n"
         + "\n".join(" & ".join(esc(c) for c in r) + "\\\\\\hline" for r in TABLE_ROWS) + "\\end{tabular}")
merged = ("\\begin{tabular}{|l|r|r|r|}\\hline\n\\multirow{2}{*}{Region} & \\multicolumn{2}{c|}{Orders} & \\multirow{2}{*}{Score}\\\\\\cline{2-3}\n"
          " & Q2 & Q3 & \\\\\\hline\n" + "\n".join(f"{r[0]} & {r[3]} & {r[1]} & {r[4]}\\\\\\hline" for r in TABLE_ROWS) + "\\end{tabular}")
longt = ("\\begin{longtable}{lllrr}\\toprule\n" + " & ".join(LONG_HEAD) + "\\\\\\midrule\\endhead\n"
         + "\n".join(" & ".join(r) + "\\\\" for r in LONG_ROWS) + "\\bottomrule\\end{longtable}")
write("tables", common + "\\begin{document}\n\\section*{Tables}\n\\subsection*{Booktabs}\n" + tab + "\n\\subsection*{Ruled}\n" + ruled
      + "\n\\subsection*{Merged header}\n" + merged + "\n\\subsection*{Across pages}\n" + longt + "\n\\end{document}\n")
chart = ("\\begin{tikzpicture}\\begin{axis}[ybar,width=7cm,height=4.5cm,symbolic x coords={" + ",".join(n for n, _ in CHART)
         + "},xtick=data,ymin=0]\\addplot coordinates {" + " ".join(f"({n},{v})" for n, v in CHART) + "};\\end{axis}\\end{tikzpicture}")
write("twocol", "\\usepackage[margin=2cm]{geometry}\n\\usepackage{pgfplots}\\pgfplotsset{compat=1.16}\n\\begin{document}\n\\title{"
      + TITLE + "}\\author{Operations}\\date{}\\maketitle\n" + paras + "\n\n\\begin{figure}[h]\\centering\\resizebox{\\columnwidth}{!}{"
      + chart + "}\\caption{Orders by region (thousands).}\\end{figure}\n\n" + paras + "\n" + items + "\n" + paras + "\n\\end{document}\n",
      r"\documentclass[10pt,a4paper,twocolumn]{article}" "\n" r"\usepackage[T1]{fontenc}")
write("code", common + "\\lstset{basicstyle=\\ttfamily\\small,numbers=left,frame=single,columns=fullflexible}\n\\begin{document}\n"
      "\\section*{Code listing}\nThe function \\texttt{load\\_orders} reads a CSV file:\n\\begin{lstlisting}[language=Python]\n" + CODE
      + "\n\\end{lstlisting}\nIt returns a list of dicts.\n\\end{document}\n")
fontspec = r"\documentclass[11pt,a4paper]{article}" "\n" r"\usepackage{fontspec}\setmainfont{Liberation Serif}\setsansfont{Liberation Sans}\setmonofont{Liberation Mono}"
write("report-opentype", report_body, fontspec)
write("i18n-latin", "\\usepackage[margin=2cm]{geometry}\n\\begin{document}\n\\section*{Accents}\n" + esc(LATIN) + "\n\n"
      + "{\\fontspec{Noto Sans SC}" + CHINESE + "}\n\\end{document}\n", fontspec)
