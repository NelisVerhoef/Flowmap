"""Mechanical spine for the flow map: every entry point the app exposes.

Entry points (HTTP endpoints, pages, server actions) are the join key between independent
map passes: two passes agree on where a step lives when they place the same entry point
under it, so nobody has to match prose. Found by framework adapters (adapters/), from
code, never by a model. Run from inside the repo being mapped.

    python <tools>/flowmap/inventory.py            # writes <out>/inventory.json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import adapters  # noqa: E402
import config  # noqa: E402


def read_worktree(rel):
    p = config.root() / rel
    return p.read_text(errors="replace") if p.is_file() else None


def endpoints(read=read_worktree):
    """`read(repo_relative_path) -> text | None` lets callers inventory any git revision."""
    return adapters.entries(config.load(), read)


if __name__ == "__main__":
    eps = endpoints()
    out = config.out()
    out.mkdir(parents=True, exist_ok=True)
    (out / "inventory.json").write_text(json.dumps({"endpoints": eps}, indent=1) + "\n")
    kinds = {}
    for e in eps:
        kinds[e["endpoint"].split(" ", 1)[0]] = kinds.get(e["endpoint"].split(" ", 1)[0], 0) + 1
    print(f"{len(eps)} entry points ({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}) "
          f"-> {(out / 'inventory.json').relative_to(config.root())}", file=sys.stderr)
