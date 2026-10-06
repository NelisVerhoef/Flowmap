"""Entry-point adapters: one per framework, all returning the same shape.

Each adapter yields dicts:
    {"endpoint": "GET /users/{id}" | "PAGE /settings" | "ACTION app/actions.ts#save",
     "handler": "repo/relative/file:symbol", "line": int, "aliases": [str, ...] (optional)}

`endpoint` is the join key independent map passes are compared on, so it must be stable
and derived from code, never from a model. `aliases` are other spellings tests may use to
hit it (Rails path helpers, for instance).
"""

import sys

from . import cli, fastapi, listed, nextjs, pattern, rails

ADAPTERS = {"fastapi": fastapi.entries, "rails": rails.entries, "nextjs": nextjs.entries, "cli": cli.entries,
            "pattern": pattern.entries, "list": listed.entries}


def entries(cfg, read):
    out = []
    for spec in cfg["entry"]:
        out.extend(ADAPTERS[spec["adapter"]](spec, read))
    first = {}
    for e in sorted(out, key=lambda e: (e["endpoint"].split(" ", 1)[-1], e["endpoint"])):
        kept = first.setdefault(e["endpoint"], e)
        if kept["handler"] != e["handler"]:  # two apps both serving GET /health: say which one the map uses
            print(f"flowmap: {e['endpoint']} is handled by both {kept['handler']} and {e['handler']}; "
                  f"keeping {kept['handler']}", file=sys.stderr)
    return list(first.values())
