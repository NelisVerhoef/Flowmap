"""Mechanical check on one map run: every cited anchor exists, every endpoint is real.

A map step is only as good as its citations. This rejects invented files and
symbols (the cheapest ground truth there is) and reports inventory endpoints
the run never placed.

    python tools/flowmap/verify.py docs/flowmap/runs/<run>.json
"""

import json
import re
import sys
from functools import cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

ROOT = config.root()
DEF = r"(?:async\s+def|def|class|function|const|let|var|interface|type|export\s+default\s+function)"


@cache
def _text(rel):
    p = ROOT / rel
    return p.read_text(errors="replace") if p.is_file() else None


def anchor_ok(anchor):
    """'path/to/file.py:symbol' or 'file.py:Class.method' -> (ok, reason)."""
    if ":" not in anchor:
        return False, "no :symbol"
    rel, symbol = anchor.rsplit(":", 1)
    text = _text(rel)
    if text is None:
        return False, "file missing"
    if symbol == "default" and re.search(r"export\s+default\b", text):
        return True, ""
    if symbol == "__main__":
        ok = re.search(r"^if\s+__name__\s*==\s*['\"]__main__['\"]", text, re.M)
        return (True, "") if ok else (False, "no `if __name__ == \"__main__\"` block in file")
    for part in symbol.split("."):
        if not re.search(rf"\b{DEF}\s+(?:self\.)?{re.escape(part)}\b|\bas\s+{re.escape(part)}\b|^\s*{re.escape(part)}\s*[:=(]", text, re.M):
            return False, f"symbol {part!r} not defined in file"
    return True, ""


def endpoints_in(run):
    for flow in run["flows"]:
        for step in flow["steps"]:
            yield from step.get("endpoints", [])


def verify(run, inventory):
    known = {e["endpoint"] for e in inventory["endpoints"]}
    problems = []
    for flow in run["flows"]:
        for step in flow["steps"]:
            where = f"{flow['id']}/{step['id']}"
            for ep in step.get("endpoints", []):
                if ep not in known:
                    problems.append(f"{where}: unknown endpoint {ep!r}")
            for key in ("ui", "code_path"):
                for a in step.get(key, []):
                    ok, why = anchor_ok(a)
                    if not ok:
                        problems.append(f"{where}: {key} {a!r}: {why}")
    placed = set(endpoints_in(run)) | {u["endpoint"] for u in run.get("unplaced_endpoints", [])}
    missing = sorted(known - placed)
    return problems, missing


if __name__ == "__main__":
    inventory = json.loads((config.out() / "inventory.json").read_text())
    bad = 0
    for path in sys.argv[1:]:
        run = json.loads(Path(path).read_text())
        problems, missing = verify(run, inventory)
        anchors = sum(len(s.get("ui", [])) + len(s.get("code_path", []))
                      for f in run["flows"] for s in f["steps"])
        print(f"{path}: {len(run['flows'])} flows, "
              f"{sum(len(f['steps']) for f in run['flows'])} steps, {anchors} anchors, "
              f"{len(problems)} bad citations, {len(missing)} endpoints never placed")
        for p in problems:
            print("  BAD ", p)
        for m in missing:
            print("  MISS", m)
        bad += len(problems) + len(missing)
    sys.exit(1 if bad else 0)
