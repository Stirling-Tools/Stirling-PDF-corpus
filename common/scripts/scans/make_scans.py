"""Build scans/: scanned-looking pages made from our own rendered documents.

Needs pdftoppm (poppler), ImageMagick 7 (magick), jbig2enc (jbig2) and OCRmyPDF with
Tesseract's English data. Noise is seeded, but ImageMagick and Tesseract versions change
pixels and OCR output, so the files are reproducible in kind rather than byte for byte.

Usage: make_scans.py REPORT_PDF UDHR_DIR OUT_DIR
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zlib

A4 = (595.28, 841.89)


def run(*args, **kw):
    return subprocess.run(args, check=True, capture_output=True, **kw).stdout


def magick(*args):
    run("magick", *args)


def size_of(path):
    w, h = run("magick", "identify", "-format", "%w %h", path).split()
    return int(w), int(h)


class Writer:
    """Minimal PDF writer: one object per call, pages built from image XObjects."""

    def __init__(self):
        self.objects = [None]
        self.pages = []

    def obj(self, body):
        self.objects.append(body)
        return len(self.objects)

    def stream(self, dictionary, data):
        return self.obj(b"<<%s/Length %d>>\nstream\n%s\nendstream" % (dictionary, len(data), data))

    def image(self, w, h, data, filt, colour=b"/DeviceGray", bpc=8, extra=b""):
        d = b"/Type/XObject/Subtype/Image/Width %d/Height %d/ColorSpace%s/BitsPerComponent %d%s%s" % (
            w, h, colour, bpc, b"/Filter" + filt if filt else b"", extra)
        if colour is None:
            d = d.replace(b"/ColorSpace", b"")
        return self.stream(d, data)

    def page(self, size, content, images, rotate=0, extra=b""):
        xobj = b"".join(b"/%s %d 0 R" % (n.encode(), ref) for n, ref in images.items())
        c = self.stream(b"", content)
        rot = b"/Rotate %d" % rotate if rotate else b""
        self.pages.append(self.obj(
            b"<</Type/Page/Parent 1 0 R/MediaBox[0 0 %.2f %.2f]/Resources<</XObject<<%s>>>>/Contents %d 0 R%s%s>>"
            % (size[0], size[1], xobj, c, rot, extra)))

    def save(self, path, title):
        objs = [b"<</Type/Pages/Kids[%s]/Count %d>>" % (
            b" ".join(b"%d 0 R" % p for p in self.pages), len(self.pages))] + self.objects[1:]
        catalog = len(objs) + 1
        info = catalog + 1
        objs += [b"<</Type/Catalog/Pages 1 0 R>>", b"<</Title(%s)/Producer(make_scans.py)>>" % title.encode()]
        out = bytearray(b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += b"%d 0 obj\n%s\nendobj\n" % (i, body)
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
        out += b"trailer\n<</Size %d/Root %d 0 R/Info %d 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objs) + 1, catalog, info, xref)
        open(path, "wb").write(out)


def place(size):
    return b"q %.2f 0 0 %.2f 0 0 cm /Im0 Do Q\n" % size


def gray_jpeg(png, quality):
    out = png + ".jpg"
    magick(png, "-colorspace", "Gray", "-quality", str(quality), "-sampling-factor", "1x1", out)
    return open(out, "rb").read()


def g4(png):
    out = png + ".g4"
    magick(png, "-threshold", "55%", "-monochrome", "group4:" + out)
    return open(out, "rb").read()


def g4_image(png):
    w, h = size_of(png)
    return lambda wr: wr.image(w, h, g4(png), b"/CCITTFaxDecode", bpc=1,
                               extra=b"/DecodeParms<</K -1/Columns %d/Rows %d/BlackIs1 true>>" % (w, h))


def one_image_page(path, title, wr_image, size=A4, rotate=0):
    wr = Writer()
    wr.page(size, place(size), {"Im0": wr_image(wr)}, rotate=rotate)
    wr.save(path, title)


def scanned(src, out, seed, skew, dark_border=True, holes=True, noise=0.25, blur=0.6):
    w, h = size_of(src)
    args = [src, "-colorspace", "Gray", "-background", "white", "-rotate", str(skew),
            "-gravity", "center", "-extent", "%dx%d" % (w, h)]
    if blur:
        args += ["-blur", "0x%s" % blur]
    args += ["-seed", str(seed), "-attenuate", str(noise), "+noise", "Gaussian"]
    if holes:
        r = w // 60
        args += ["-fill", "gray15"] + sum(
            (["-draw", "circle %d,%d %d,%d" % (w // 22, y, w // 22 + r, y)] for y in (h // 4, 3 * h // 4)), [])
    if dark_border:
        args += ["-bordercolor", "gray20", "-border", "%dx%d" % (w // 70, h // 90),
                 "-resize", "%dx%d!" % (w, h)]
    magick(*args, out)
    return out


def ocr(src_pdf, out_pdf, *extra):
    run("ocrmypdf", "-l", "eng", "--output-type", "pdf", "-O0", "--quiet", *extra, src_pdf, out_pdf)


def rewrite_content(pdf_path, out_path, edit):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "conformance"))
    from pdfjson import Pdf
    pdf = Pdf(pdf_path)
    edit(pdf)
    pdf.save(out_path)


def main(report_pdf, udhr, out):
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp()
    try:
        build(report_pdf, udhr, out, tmp)
    finally:
        shutil.rmtree(tmp)


def build(report_pdf, udhr, out, t):
    def T(name):
        return os.path.join(t, name)

    def O(name):
        return os.path.join(out, name + ".pdf")

    run("pdftoppm", "-r", "150", "-gray", "-png", "-singlefile", report_pdf, T("report150"))
    run("pdftoppm", "-r", "200", "-gray", "-png", "-singlefile", report_pdf, T("report200"))
    run("pdftoppm", "-r", "150", "-png", "-singlefile", report_pdf, T("report150c"))
    run("pdftoppm", "-r", "200", "-gray", "-png", "-f", "1", "-singlefile", os.path.join(udhr, "arb.pdf"), T("arb200"))
    run("pdftoppm", "-r", "200", "-gray", "-png", "-f", "1", "-singlefile", os.path.join(udhr, "jpn.pdf"), T("jpn200"))
    r150, r200, c150 = T("report150.png"), T("report200.png"), T("report150c.png")

    skewed = scanned(r150, T("skewed.png"), 7, 2.4)
    one_image_page(O("scan-skewed-noisy-gray-jpeg"), "Skewed noisy scan",
                   lambda wr: wr.image(*size_of(skewed), gray_jpeg(skewed, 35), b"/DCTDecode"))

    clean = scanned(r150, T("clean.png"), 3, 0.4, dark_border=False, holes=False, noise=0.1)
    one_image_page(T("clean.pdf"), "Scan", lambda wr: wr.image(*size_of(clean), gray_jpeg(clean, 40), b"/DCTDecode"))
    ocr(T("clean.pdf"), O("scan-with-ocr-layer"))

    def offset_ocr(pdf):
        for ref in pdf.find(lambda d: True):
            e = pdf.entry(ref)
            if "stream" in e and b"3 Tr" in pdf.data(ref):
                pdf.set_data(ref, b"q 1 0 0 1 24 -38 cm\n" + pdf.data(ref) + b"\nQ")
    rewrite_content(O("scan-with-ocr-layer"), O("scan-ocr-layer-offset"), offset_ocr)

    def double_ocr(pdf):
        for page in pdf.pages():
            p = pdf.get(page)
            contents = p["/Contents"] if isinstance(p["/Contents"], list) else [p["/Contents"]]
            p["/Contents"] = contents + [pdf.add_stream({}, b"q 1 0 0 1 0.6 -0.4 cm\n" + b"\n".join(
                pdf.data(c) for c in contents) + b"\nQ")]
    rewrite_content(O("scan-with-ocr-layer"), O("scan-double-ocr-layer"), double_ocr)

    arb = scanned(T("arb200.png"), T("arb.png"), 11, -1.2, dark_border=False, holes=False, noise=0.15, blur=0.4)
    one_image_page(T("arb.pdf"), "Arabic scan", g4_image(arb))

    def swap_image(pdf):
        for ref in pdf.find(lambda d: d.get("/Subtype") == "/Image"):
            pdf.entry(ref)["stream"]["dict"] = {
                "/Type": "/XObject", "/Subtype": "/Image", "/Width": size_of(arb)[0], "/Height": size_of(arb)[1],
                "/ColorSpace": "/DeviceGray", "/BitsPerComponent": 8, "/Filter": "/DCTDecode"}
            pdf.set_data(ref, gray_jpeg(arb, 35))
    rewrite_content(O("scan-with-ocr-layer"), O("scan-ocr-layer-from-another-page"), swap_image)

    one_image_page(O("scan-arabic-bilevel-g4"), "Arabic scan, bilevel", g4_image(arb))

    upside = T("upside.png")
    magick(scanned(r200, T("u0.png"), 5, 0.8, holes=False, dark_border=False), "-rotate", "180", upside)
    one_image_page(O("scan-upside-down-no-rotate"), "Upside-down scan", g4_image(upside))

    sideways = T("sideways.png")
    magick(scanned(r150, T("s0.png"), 9, -0.6, holes=False, dark_border=False, noise=0.12), "-rotate", "-90", sideways)
    one_image_page(O("scan-sideways-image-with-rotate-90"), "Sideways scan corrected by Rotate",
                   lambda wr: wr.image(*size_of(sideways), gray_jpeg(sideways, 35), b"/DCTDecode"),
                   size=(A4[1], A4[0]), rotate=90)

    fax = T("fax.png")
    magick(r200, "-resize", "1728x1143!", "-threshold", "60%", fax)
    one_image_page(O("scan-fax-g4-204x98-dpi"), "Fax, normal resolution", g4_image(fax),
                   size=(1728 / 204 * 72, 1143 / 98 * 72))

    hi = T("hi.png")
    run("pdftoppm", "-r", "600", "-mono", "-png", "-singlefile", report_pdf, T("hi"))
    jdir = T("jb")
    os.makedirs(jdir)
    run("jbig2", "-s", "-p", "-b", os.path.join(jdir, "out"), hi, cwd=t)
    sym = open(os.path.join(jdir, "out.sym"), "rb").read()
    page_data = open(sorted(glob.glob(os.path.join(jdir, "out.0*")))[0], "rb").read()

    def jbig2(wr):
        g = wr.stream(b"", sym)
        return wr.image(*size_of(hi), page_data, b"/JBIG2Decode", bpc=1, extra=b"/DecodeParms<</JBIG2Globals %d 0 R>>" % g)
    one_image_page(O("scan-jbig2-symbol-mode-600dpi"), "JBIG2 symbol-mode scan", jbig2)

    spread = T("spread.png")
    left = scanned(r150, T("l.png"), 21, 0.9, holes=False, dark_border=False, noise=0.15)
    right = scanned(T("jpn200.png"), T("r.png"), 22, -0.7, holes=False, dark_border=False, noise=0.15)
    magick(right, "-resize", "%dx%d!" % size_of(left), T("right.png"))
    lw, lh = size_of(left)
    gutter = T("gutter.png")
    magick("(", "-size", "%dx60" % lh, "gradient:white-gray45", "-rotate", "-90", ")",
           "(", "-size", "%dx60" % lh, "gradient:white-gray45", "-rotate", "90", ")", "+append", gutter)
    magick(left, T("right.png"), "+append", gutter, "-gravity", "center", "-compose", "multiply", "-composite", spread)
    one_image_page(O("scan-two-page-spread"), "Book spread on one page",
                   lambda wr: wr.image(*size_of(spread), gray_jpeg(spread, 35), b"/DCTDecode"),
                   size=(2 * A4[0], A4[1]))

    strips = T("strips.gray")
    w, h = size_of(r150)
    magick(r150, "-depth", "8", "gray:" + strips)
    raw = open(strips, "rb").read()
    wr = Writer()
    n, images, content = 16, {}, b""
    rows = h // 16
    for i in range(n):
        top = i * rows
        rh = rows if i < n - 1 else h - top
        ref = wr.image(w, rh, zlib.compress(raw[top * w:(top + rh) * w], 9), b"/FlateDecode")
        images["S%d" % i] = ref
        y = A4[1] * (h - top - rh) / h
        content += b"q %.2f 0 0 %.4f 0 %.4f cm /S%d Do Q\n" % (A4[0], A4[1] * rh / h, y, i)
    wr.page(A4, content, images)
    wr.save(O("scan-in-16-strips"), "Scan stored as 16 strips")

    bg, fg = T("bg.jpg"), T("fg.png")
    magick(c150, "-resize", "33%", "-blur", "0x2", "-quality", "30", bg)
    magick(c150, "-colorspace", "Gray", "-threshold", "50%", "-monochrome", fg)
    fw, fh = size_of(fg)
    magick(fg, "-depth", "8", "gray:" + T("fg.raw"))
    bits = bytearray()
    raw = open(T("fg.raw"), "rb").read()
    for y in range(fh):
        row = raw[y * fw:(y + 1) * fw]
        for x in range(0, fw, 8):
            b = 0
            for k in range(8):
                b = (b << 1) | (1 if x + k < fw and row[x + k] > 127 else 0)
            bits.append(b)
    wr = Writer()
    bgw, bgh = size_of(bg)
    im_bg = wr.image(bgw, bgh, open(bg, "rb").read(), b"/DCTDecode", colour=b"/DeviceRGB")
    im_fg = wr.stream(b"/Type/XObject/Subtype/Image/Width %d/Height %d/ImageMask true/BitsPerComponent 1/Decode[0 1]/Filter/FlateDecode"
                      % (fw, fh), zlib.compress(bytes(bits), 9))
    wr.page(A4, place(A4) + b"q 0.1 0.1 0.35 rg %.2f 0 0 %.2f 0 0 cm /Fg Do Q\n" % A4, {"Im0": im_bg, "Fg": im_fg})
    wr.save(O("scan-mrc-mask-over-background"), "Mixed raster content: text mask over a blurred background")

    cmyk = T("cmyk.jpg")
    magick(scanned(c150, T("c0.png"), 31, 0.5, holes=False, dark_border=False, noise=0.1), "-colorspace", "CMYK",
           "-quality", "40", cmyk)
    one_image_page(O("scan-cmyk-jpeg-adobe-inverted"), "CMYK JPEG with an inverted Decode",
                   lambda wr: wr.image(*size_of(cmyk), open(cmyk, "rb").read(), b"/DCTDecode", colour=b"/DeviceCMYK",
                                       extra=b"/Decode[1 0 1 0 1 0 1 0]"))

    blank = T("blank.png")
    w, h = size_of(r150)
    magick("-size", "%dx%d" % (w, h), "xc:gray96", "(", r150, "-flop", "-level", "0%,100%,0.2", "+level", "88%,100%", ")",
           "-compose", "multiply", "-composite", "-seed", "41", "-attenuate", "0.2", "+noise", "Gaussian",
           "-fill", "gray30", "-draw", "circle %d,%d %d,%d" % (w // 3, h // 2, w // 3 + 2, h // 2),
           "-draw", "point %d,%d" % (2 * w // 3, h // 5), blank)
    one_image_page(O("scan-blank-page-with-bleed-through"), "Blank back of a sheet",
                   lambda wr: wr.image(*size_of(blank), gray_jpeg(blank, 30), b"/DCTDecode"))

    photo = T("photo.jpg")
    magick(c150, "-alpha", "set", "-virtual-pixel", "transparent", "-distort", "Perspective",
           "0,0 90,140 %d,0 %d,60 0,%d 30,%d %d,%d %d,%d" % (w, w - 70, h, h - 40, w, h, w - 20, h - 110),
           "-background", "rgb(92,80,64)", "-flatten",
           "(", "-size", "%dx%d" % (w, h), "radial-gradient:white-gray50", ")", "-compose", "multiply", "-composite", "-seed", "8", "-attenuate", "0.2",
           "+noise", "Gaussian", "-quality", "35", photo)
    one_image_page(O("scan-phone-photo-perspective"), "Phone photo of a page",
                   lambda wr: wr.image(*size_of(photo), open(photo, "rb").read(), b"/DCTDecode", colour=b"/DeviceRGB"))

    g16 = T("g16.raw")
    magick(r150, "-resize", "50%", T("half.png"))
    magick(T("half.png"), "-depth", "16", "-endian", "MSB", "gray:" + g16)
    w16, h16 = size_of(T("half.png"))
    one_image_page(O("scan-16-bit-gray"), "16-bit greyscale image",
                   lambda wr: wr.image(w16, h16, zlib.compress(open(g16, "rb").read(), 9), b"/FlateDecode", bpc=16))

    one_image_page(T("skew.pdf"), "x", lambda wr: wr.image(*size_of(skewed), gray_jpeg(skewed, 35), b"/DCTDecode"))
    one_image_page(T("up.pdf"), "x", g4_image(upside))
    ocr(T("clean.pdf"), T("ocrd.pdf"))
    run("qpdf", "--empty", "--pages", report_pdf, T("skew.pdf"), T("ocrd.pdf"), T("up.pdf"), "--", O("scan-mixed-born-digital-scan-and-ocr"))


if __name__ == "__main__":
    main(*sys.argv[1:4])
