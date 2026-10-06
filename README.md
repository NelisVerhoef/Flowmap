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
| anything else | `pattern`: a regex for its registrations (`@app.get(...)`, `@server.tool`, `app.get("/x", show)`), written into `flowmap.toml` at setup; the handler is the definition it sits on. `list` for registries no regex finds | yes for Python, including defs built in factory functions |
| Python CLI | `if __name__ == "__main__"` scripts in a commands dir (`CLI <prog> <cmd>`), or one `main` script | yes (the `__main__` block is a node, so runpy/importlib dispatch still has reach) |

## On a new machine

Python 3.11+ and `git`. In Claude Code, inside any session:

```
/plugin marketplace add NelisVerhoef/flowmap
/plugin install flowmap@flowmap
```

Claude Code clones over SSH when `ssh -T git@github.com` works, else over HTTPS; on a machine
without a GitHub SSH key, `export CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1` skips the probe.

For `flowmap` in your own terminal too (the plugin's copy is only on Claude Code's PATH):

```bash
git clone https://github.com/NelisVerhoef/flowmap.git ~/src/flowmap
echo 'export PATH="$HOME/src/flowmap/bin:$PATH"' >> ~/.zshrc && exec zsh
flowmap                          # prints the command list
```

To update: `git pull` in the clone, and `/plugin marketplace update flowmap` in Claude Code.
The plugin only refreshes when `version` in `.claude-plugin/plugin.json` changes, so bump it
on each release. The change viewer at `flowmap.testabl.ai` needs nothing on the machine.

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
flowmap lens <base> <head>                       # placement, reach, reach diff, off-map code
flowmap atlas --pr '<base>..<head>=PR #123'      # paint it on the map
flowmap change <base> <head> --name pr-123      # the change as chapters on the map (docs/flowmap/changes/)
```

GitHub shows committed HTML as source, not as a page. Add `--link` to also print a link that
renders the page in a browser without publishing it anywhere: the page's data rides in the link's
`#` fragment, which browsers never send to a server, and a hosted viewer (`flowmap viewer <dir>`,
one static file with no network access) renders it in the tab. Point `viewer` in `flowmap.toml`
at your hosted copy; this repo's is `https://flowmap.testabl.ai/v1/change.html`, deployed from
`fjall/flowmap/`. A PR body holds about 60 KB of link; past that, open the committed page in
the viewer by dropping the file on it.

## With Claude Code

This repo is also a Claude Code plugin with two skills:

- **flowmap-build** — runs the whole build: inventory, four independent passes as parallel
  agents, verify, reconcile, then hands you `QUESTIONS.md` to decide.
- **pr-lens** — turns `flowmap lens` output into before→after per step and the questions to
  ask the author, without you reading the diff first.

### Install

```
/plugin marketplace add NelisVerhoef/flowmap
/plugin install flowmap@flowmap
```

While the plugin is enabled, `bin/flowmap` is on the Bash tool's PATH, so the skills (and you,
inside Claude Code) just run `flowmap ...`. The skills show up as `/flowmap:flowmap-build` and
`/flowmap:pr-lens`.

To have teammates prompted to install it when they open your repo, commit this to the repo's
`.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "flowmap": { "source": { "source": "github", "repo": "NelisVerhoef/flowmap" } }
  },
  "enabledPlugins": { "flowmap@flowmap": true }
}
```

Without the plugin system: clone this repo, put its `bin/` on PATH, and copy `skills/*` into
the target repo's `.claude/skills/`.

### PR hook

`.claude/settings.json` runs `bin/flowmap-pr-hook` after every `git push` and `gh pr create` in a
Claude Code session. When the branch has an open PR and the repo has a map, it runs `flowmap lens`
on the PR and hands the output to Claude, which writes the pr-lens summary and posts it as one PR
comment (`flowmap-pr-hook post <pr> <file>` edits that comment on later pushes instead of adding
another). It stays silent otherwise, and runs once per head commit. Copy the hook block into
another repo's `.claude/settings.json`, pointing at this repo's `bin/flowmap-pr-hook`, to use it there.

## Does it tell the truth?

`bench/` plants 26 changes with known effects in the FastAPI full-stack template and checks what
lens says against the app's own tests, a seeded production database and runtime reach. 16 of the
20 changes that break production pass the template's CI. lens as first shipped said nothing
about existing code on 4 of those and crashed on 1. After the fixes it found (they are in lens
now), it says *contained* on none of them and flags 50 of 55 affected endpoints. An LLM review
with flowmap was right on 13 of 13 subtle cases, but one without flowmap was right on all 8 it
ran: the claim is a lens a reviewer can trust when it is quiet, not one that finds more bugs. Method and numbers:
[`bench/README.md`](bench/README.md), [`bench/fastapi-template/RESULTS.md`](bench/fastapi-template/RESULTS.md).

## flowmap.toml

See the docstring in `flowmap/config.py`. The parts you own: `[[flows.vocabulary]]` (the flow names,
the slow-moving top layer of the map), `plumbing` (components hidden from the system view)
and `engine` (an optional hub to fold into one node).

## Adding a stack

Most stacks need no code: a `pattern` entry in `flowmap.toml` (see `flowmap/adapters/pattern.py`)
turns a regex over the files that register entry points into endpoints, and the `flowmap-build`
skill writes those rules when it sets a repo up. Write an adapter only for what a regex can't
express: prefixes composed across files, names a framework derives.

Write `flowmap/adapters/<name>.py` with `entries(spec, read) -> [{"endpoint", "handler", "line",
"aliases"?}]`, register it in `adapters/__init__.py`, and add its guidance to `STACK` in
`flowmap/brief.py`. The `endpoint` string is the join key between passes, so derive it from code,
never from a model.

For deterministic reach, the language also needs a call-graph builder: `flowmap/graphs/<lang>.py`
with `EXT`, `build(files, read)`, `symbols(text)` and `signature(text, sym)` (see
`graphs/__init__.py`), registered in `BUILDERS`. Point `[code].graph` at its sources, then
`flowmap callgraph check` must report 0 broken: every handler the adapter emits has to be a node
the builder emits.

## License

Apache 2.0, see [LICENSE](LICENSE).
