"""Next.js: the file tree is the route table.

- App router: app/**/route.{ts,js} exporting GET/POST/… -> "GET /path";
  app/**/page.{tsx,jsx,ts,js} -> "PAGE /path".
- Pages router: pages/api/** -> "ANY /api/path"; other pages/** -> "PAGE /path".
- Server actions: modules starting with "use server" -> "ACTION <file>#<export>".
Route groups "(x)", parallel slots "@x" and interceptors "(.)x" drop out of the URL;
[id] / [...slug] / [[...slug]] become {id} / {slug}.
"""

import re
import subprocess

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
CODE_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs")
SKIP_PAGES = {"_app", "_document", "_error", "404", "500"}


def _segments(parts):
    out = []
    for p in parts:
        if (p.startswith("(") and p.endswith(")")) or p.startswith("@") or re.match(r"^\(\.+\)", p):
            continue
        p = re.sub(r"^\[\[?\.\.\.(\w+)\]?\]$", r"{\1}", p)
        p = re.sub(r"^\[(\w+)\]$", r"{\1}", p)
        out.append(p)
    return "/" + "/".join(out)


def _default_name(text):
    m = re.search(r"export\s+default\s+(?:async\s+)?(?:function|class)\s+(\w+)", text) \
        or re.search(r"export\s+default\s+(\w+)\s*;?\s*$", text, re.M)
    return m[1] if m else "default"


def _line(text, pattern):
    m = re.search(pattern, text, re.M)
    return text[: m.start()].count("\n") + 1 if m else 1


def _files(base, ref=None):
    from config import root
    cmd = ["git", "ls-tree", "-r", "--name-only", ref, "--", base or "."] if ref else ["git", "ls-files", "--", base or "."]
    ls = subprocess.run(cmd, cwd=root(), capture_output=True, text=True)
    return [f for f in ls.stdout.splitlines() if f.endswith(CODE_EXT) and "node_modules/" not in f]


def entries(spec, read):
    base = spec.get("root", ".").strip("/")
    pre = "" if base in ("", ".") else base + "/"
    out = []
    for rel in _files(base, getattr(read, "ref", None)):
        local = rel[len(pre):]
        parts = local.split("/")
        if parts[0] == "src":
            parts = parts[1:]
        if not parts:
            continue
        stem = parts[-1].rsplit(".", 1)[0]
        text = read(rel) or ""
        if parts[0] == "app" and stem == "route":
            url = _segments(parts[1:-1])
            for m in METHODS:
                if re.search(rf"export\s+(?:async\s+)?function\s+{m}\b|export\s+const\s+{m}\b|\bas\s+{m}\b", text):
                    out.append({"endpoint": f"{m} {url}", "handler": f"{rel}:{m}",
                                "line": _line(text, rf"\b{m}\b")})
        elif parts[0] == "app" and stem == "page":
            name = _default_name(text)
            out.append({"endpoint": f"PAGE {_segments(parts[1:-1])}", "handler": f"{rel}:{name}",
                        "line": _line(text, r"export\s+default")})
        elif parts[0] == "pages" and stem not in SKIP_PAGES:
            segs = parts[1:-1] + ([] if stem == "index" else [stem])
            url = _segments(segs)
            name = _default_name(text)
            kind = "ANY" if parts[1:2] == ["api"] else "PAGE"
            out.append({"endpoint": f"{kind} {url}", "handler": f"{rel}:{name}",
                        "line": _line(text, r"export\s+default")})
        if re.match(r"\s*(?://[^\n]*\n\s*)*['\"]use server['\"]", text):
            for m in re.finditer(r"^export\s+(?:async\s+)?(?:function\s+(\w+)|const\s+(\w+)\s*=)", text, re.M):
                fn = m[1] or m[2]
                out.append({"endpoint": f"ACTION {rel}#{fn}", "handler": f"{rel}:{fn}",
                            "line": text[: m.start()].count("\n") + 1})
    return out
