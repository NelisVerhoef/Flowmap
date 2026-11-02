"""Build the hosted viewer: the change and canvas pages with no data in them. They render a
`flowmap change --link` or `flowmap canvas --link` link, whose fragment carries the data, all inside
the browser; the change page also takes a page dropped onto it.

    python tools/flowmap/viewer.py <dir>

Writes <dir>/change.html and <dir>/canvas.html. Host them anywhere static (S3, Cloudflare Pages, a
public Pages repo) and point `viewer` in flowmap.toml at change.html's URL; canvas.html sits beside it.
The data never reaches the host: browsers do not send the fragment, and each page's CSP forbids it
from making any request.
"""

import argparse
import base64
import json
import os
import re
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

VIEWER = "https://flowmap.testabl.ai/v1/change.html"  # public; the data stays in the fragment
BUDGET = 60000  # a PR body holds 65536 characters; leave room for the prose around the link


def viewer_url():
    return os.environ.get("FLOWMAP_VIEWER") or config.load().get("viewer") or VIEWER


def locked(html):
    """A template as a page with no fonts or other requests, and a CSP that forbids any, so a reader
    can see their data stays in the tab."""
    csp = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
           "base-uri 'none'; form-action 'none'")
    return re.sub(r"<!--fonts-->.*?<!--/fonts-->", f'<meta http-equiv="Content-Security-Policy" content="{csp}">',
                  html, count=1, flags=re.S)


def link(data, viewer):
    """The viewer URL with the data in its fragment: #v1.<base64url of raw-deflated JSON>."""
    z = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = z.compress(json.dumps(data, separators=(",", ":")).encode()) + z.flush()
    return f"{viewer}#v1.{base64.urlsafe_b64encode(packed).rstrip(b'=').decode()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    a = ap.parse_args()
    import canvas  # the pages import this module for its helpers
    import change
    for name, html in (("change.html", change.viewer_html()), ("canvas.html", canvas.viewer_html())):
        out = Path(a.dir) / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
