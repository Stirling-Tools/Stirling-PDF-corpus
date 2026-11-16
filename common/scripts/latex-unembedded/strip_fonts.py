import sys, pathlib, pikepdf
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
dst.mkdir(parents=True, exist_ok=True)
for f in sorted(src.glob("*.pdf")):
    with pikepdf.open(f) as pdf:
        n = 0
        for obj in pdf.objects:
            if isinstance(obj, pikepdf.Dictionary) and obj.get("/Type") == "/FontDescriptor":
                for k in ("/FontFile", "/FontFile2", "/FontFile3", "/CIDSet"):
                    if k in obj:
                        del obj[k]; n += 1
        pdf.save(dst / f.name)
    print(f.name, "stripped", n)
