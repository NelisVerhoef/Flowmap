# flowmap

Map a codebase as **user flows → steps → code**, by agreement between independent passes,
and review changes by where they land on that map instead of by reading diffs first.

The tools live anywhere; run them from inside the repo you're mapping (or set
`FLOWMAP_ROOT`). Output goes to `docs/flowmap/` in that repo unless `flowmap.toml` says otherwise.
Python 3.11+, no dependencies.

## Supported stacks

| stack | entry points come from | call graph (deterministic reach) |
|---|---|---|
| FastAPI | `@router.<verb>` + `include_router` prefixes | yes (Python AST) |
| Rails | `bin/rails routes` (or a saved dump), actions resolved through concerns and parent controllers | not yet: the map and anchor matching work, reach doesn't |
| Next.js | file tree: `app/**/route.ts`, `page.tsx`, `pages/**`, `"use server"` actions | not yet |
| React SPA | its backend's entry points; top-down passes start from its router | via the backend |
| Python CLI | `if __name__ == "__main__"` scripts in a commands dir (`CLI <prog> <cmd>`), or one `main` script | yes (the `__main__` block is a node, so runpy/importlib dispatch still has reach) |

## First time in a repo

```bash
export PATH="/path/to/flowmap/bin:$PATH"
cd your-repo

# 1. optional: flowmap.toml (no file = auto-detect adapters + discovery mode)
#    Rails: save routes once where the app boots:  bin/rails routes > tmp/routes.txt
#    and set routes_file = "tmp/routes.txt" under [[entry]] adapter = "rails"

flowmap inventory                 # every entry point -> docs/flowmap/inventory.json
for r in "bu-1 bottom-up" "bu-2 bottom-up" "td-1 top-down" "td-2 top-down"; do
  flowmap brief $r                # writes docs/flowmap/runs/<id>.brief.md
done
# 2. hand each brief to an agent ("Read <brief> and follow it exactly"), two models if you can
flowmap verify docs/flowmap/runs/*.json
flowmap reconcile docs/flowmap/runs/??-?.json
# 3. read docs/flowmap/QUESTIONS.md: name the proposed flows, paste them into flowmap.toml,
#    answer split votes in docs/flowmap/decisions.json, then reconcile again
flowmap diagrams                  # Mermaid at three zoom levels
flowmap atlas                     # the interactive map (docs/flowmap/atlas.html)
```

## Every PR

```bash
flowmap lens <base> <head>                       # placement, reach, off-map code
flowmap atlas --pr '<base>..<head>=PR #123'      # paint it on the map
```

## With Claude Code

This repo is also a Claude Code plugin with two skills:

- **flowmap-build** — runs the whole build: inventory, four independent passes as parallel
  agents, verify, reconcile, then hands you `QUESTIONS.md` to decide.
- **pr-lens** — turns `flowmap lens` output into before→after per step and the questions to
  ask the author, without you reading the diff first.

Install the plugin from this repo, or copy `skills/*` into `.claude/skills/`.

## flowmap.toml

See the docstring in `flowmap/config.py`. The parts you own: `[[flows.vocabulary]]` (the flow names,
the slow-moving top layer of the map), `plumbing` (components hidden from the system view)
and `engine` (an optional hub to fold into one node).

## Adding a stack

Write `flowmap/adapters/<name>.py` with `entries(spec, read) -> [{"endpoint", "handler", "line",
"aliases"?}]`, register it in `adapters/__init__.py`, and add its guidance to `STACK` in
`flowmap/brief.py`. The `endpoint` string is the join key between passes, so derive it from code,
never from a model.
