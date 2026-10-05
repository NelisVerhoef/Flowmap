"""Build the hosted viewer: the change page with no data in it. It renders a `flowmap change --link`
link, whose fragment carries the page, or a change page dropped onto it, all inside the browser.

    python tools/flowmap/viewer.py <dir>

Writes <dir>/change.html. Host it anywhere static (S3, Cloudflare Pages, a public Pages repo) and
point `viewer` in flowmap.toml at its URL. The data never reaches the host: browsers do not send
the fragment, and the page's CSP forbids it from making any request.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from change import viewer_html  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    a = ap.parse_args()
    out = Path(a.dir) / "change.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(viewer_html())
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
