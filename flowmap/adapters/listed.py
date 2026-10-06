"""Any stack, by hand: entry points no rule can find (dispatch tables, string registries).

    [[entry]]
    adapter = "list"
    entries = [{endpoint = "JOB nightly-sync", handler = "app/jobs.py:sync"}]

`flowmap callgraph check` says whether each handler is a real graph node.
"""


def entries(spec, read):
    import lens  # late: lens imports the adapters
    out = []
    for e in spec["entries"]:
        rel, _, sym = e["handler"].partition(":")
        line = next((s[0] for s in lens.defs(rel, read(rel)) if s[2] == sym), 1)
        out.append({"endpoint": e["endpoint"], "handler": e["handler"], "line": line})
    return out
