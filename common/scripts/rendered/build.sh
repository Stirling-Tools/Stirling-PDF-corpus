#!/bin/sh
# Render the sources from make_sources.py with LibreOffice and Chromium, offline in Docker.
# Usage: build.sh SOURCES_DIR OUT_DIR [IMAGE]
# IMAGE must provide soffice, chromium and the Liberation, DejaVu and Noto fonts; the files in
# this repository were built with LibreOffice 26.8.1 and Chromium 156 on Debian trixie.
set -eu
src=$(cd "$1" && pwd)
mkdir -p "$2"
out=$(cd "$2" && pwd)
image=${3:?name an image with soffice, chromium and the fonts}

docker run --rm --network=none -u root -v "$src:/src:ro" -v "$out:/out" --entrypoint sh "$image" -c '
set -eu
export HOME=/tmp/home
mkdir -p $HOME /tmp/work
cp -r /src/. /tmp/work/
cd /tmp/work
lo() {
  soffice --headless --norestore ${5:+"--infilter=$5"} --convert-to "pdf:$3:$2" --outdir /tmp/lo "$1" >/dev/null 2>&1
  mv "/tmp/lo/${1%.*}.pdf" "/out/$4.pdf"
}
W=writer_pdf_Export
H="HTML (StarWriter)"
lo report.html "{}" $W lo-plain "$H"
lo report.html "{\"SelectPdfVersion\":{\"type\":\"long\",\"value\":\"1\"},\"UseTaggedPDF\":{\"type\":\"boolean\",\"value\":\"false\"}}" $W lo-pdfa1b "$H"
for v in 2 3 4; do
  lo report.html "{\"SelectPdfVersion\":{\"type\":\"long\",\"value\":\"$v\"}}" $W lo-pdfa${v}b "$H"
done
mv /out/lo-pdfa4b.pdf /out/lo-pdfa4.pdf
lo report.html "{\"PDFUACompliance\":{\"type\":\"boolean\",\"value\":\"true\"},\"UseTaggedPDF\":{\"type\":\"boolean\",\"value\":\"true\"}}" $W lo-ua "$H"
lo table-merged-cells.html "{}" $W table-merged-cells-libreoffice "$H"
lo table-spreadsheet-wide-and-long.fods "{}" calc_pdf_Export table-spreadsheet-wide-and-long
for f in *.html; do
  [ "$f" = report.html ] && continue
  chromium --headless --no-sandbox --disable-gpu --no-pdf-header-footer --generate-pdf-document-outline \
    --print-to-pdf="/out/${f%.html}.pdf" "file:///tmp/work/$f" >/dev/null 2>&1
done
'
