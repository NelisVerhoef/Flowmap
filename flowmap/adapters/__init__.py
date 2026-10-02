"""Entry-point adapters: one per framework, all returning the same shape.

Each adapter yields dicts:
    {"endpoint": "GET /users/{id}" | "PAGE /settings" | "ACTION app/actions.ts#save",
     "handler": "repo/relative/file:symbol", "line": int, "aliases": [str, ...] (optional)}

`endpoint` is the join key independent map passes are compared on, so it must be stable
and derived from code, never from a model. `aliases` are other spellings tests may use to
hit it (Rails path helpers, for instance).
"""

from . import cli, fastapi, nextjs, rails

ADAPTERS = {"fastapi": fastapi.entries, "rails": rails.entries, "nextjs": nextjs.entries, "cli": cli.entries}


def entries(cfg, read):
    out = []
    for spec in cfg["entry"]:
        out.extend(ADAPTERS[spec["adapter"]](spec, read))
    seen, unique = set(), []
    for e in sorted(out, key=lambda e: (e["endpoint"].split(" ", 1)[-1], e["endpoint"])):
        if e["endpoint"] not in seen:
            seen.add(e["endpoint"])
            unique.append(e)
    return unique
