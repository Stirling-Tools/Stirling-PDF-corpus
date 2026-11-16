"""Edit a PDF as qpdf JSON v2: load it, change objects as Python values, write it back.

Strings are "u:text" or "b:hex", names "/Name", references "N 0 R". Streams are
{"stream": {"dict": {...}, "data": base64}} with the data already decoded. Writing keeps a
newline before every endstream, which PDF/A requires and qpdf otherwise omits.
"""

import base64
import json
import subprocess
import tempfile


class Pdf:
    def __init__(self, path):
        out = subprocess.run(
            ["qpdf", "--json-output", "--json-stream-data=inline",
             "--decode-level=generalized", path, "-"],
            check=True, capture_output=True).stdout
        self.json = json.loads(out)
        self.objects = self.json["qpdf"][1]

    @property
    def trailer(self):
        return self.objects["trailer"]["value"]

    @property
    def root(self):
        return self.get(self.trailer["/Root"])

    def entry(self, ref):
        return self.objects["obj:" + ref]

    def get(self, ref):
        e = self.entry(ref)
        return e["stream"]["dict"] if "stream" in e else e["value"]

    def data(self, ref):
        return base64.b64decode(self.entry(ref)["stream"]["data"])

    def set_data(self, ref, raw):
        self.entry(ref)["stream"]["data"] = base64.b64encode(raw).decode()

    def _next_ref(self):
        nums = [int(k.split()[0][4:]) for k in self.objects if k.startswith("obj:")]
        return "%d 0 R" % (max(nums) + 1)

    def add(self, value):
        ref = self._next_ref()
        self.objects["obj:" + ref] = {"value": value}
        return ref

    def add_stream(self, dictionary, raw):
        ref = self._next_ref()
        self.objects["obj:" + ref] = {"stream": {"dict": dictionary, "data": base64.b64encode(raw).decode()}}
        return ref

    def pages(self):
        found = []

        def walk(ref):
            node = self.get(ref)
            if node.get("/Type") == "/Pages" or "/Kids" in node:
                for kid in node["/Kids"]:
                    walk(kid)
            else:
                found.append(ref)

        walk(self.root["/Pages"])
        return found

    def find(self, predicate):
        return [k[4:] for k, e in self.objects.items()
                if k.startswith("obj:") and isinstance(self.get(k[4:]), dict) and predicate(self.get(k[4:]))]

    def xmp(self):
        return self.data(self.root["/Metadata"]).decode("utf-8")

    def set_xmp(self, text):
        self.set_data(self.root["/Metadata"], text.encode("utf-8"))

    def append_content(self, page_ref, raw, resources=None):
        page = self.get(page_ref)
        contents = page["/Contents"]
        contents = contents if isinstance(contents, list) else [contents]
        page["/Contents"] = contents + [self.add_stream({}, raw)]
        if resources:
            res = page["/Resources"]
            res = self.get(res) if isinstance(res, str) else res
            for key, entries in resources.items():
                group = res.setdefault(key, {})
                group = self.get(group) if isinstance(group, str) else group
                group.update(entries)

    def save(self, path, *qpdf_args):
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:
            json.dump(self.json, f)
            f.flush()
            ident = [] if "--encrypt" in qpdf_args else ["--deterministic-id"]
            subprocess.run(["qpdf", "--json-input", f.name, "--newline-before-endstream",
                            *ident, *qpdf_args, path], check=True)
