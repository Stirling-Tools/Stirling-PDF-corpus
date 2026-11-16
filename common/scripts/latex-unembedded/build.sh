#!/bin/sh
# Rebuilds every TeX sample: ./build.sh (runs the TeX Live image offline, writes samples/<variant>/<doc>.pdf)
set -e
W=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$W/samples"
docker run --rm --network=none --cpus 2 -m 2500m -v "$W/src":/src:ro -v "$W/samples":/out -v "$W/build-inner.sh":/build-inner.sh:ro \
  texlive/texlive:latest-medium sh /build-inner.sh
for v in _e-dvipdfmx-embed:e-dvipdfmx-stripped f-lualatex-embed:f-lualatex-stripped f-xelatex-embed:f-xelatex-stripped; do
  docker run --rm --network=none --cpus 2 -m 2500m -v "$W/samples":/s -v "$W/strip_fonts.py":/strip_fonts.py:ro --entrypoint /opt/venv/bin/python \
    docker.stirlingpdf.com/stirlingtools/stirling-pdf:3.2.0 -I /strip_fonts.py /s/${v%%:*} /s/${v#*:}
done
rm -rf "$W/samples/_e-dvipdfmx-embed"
