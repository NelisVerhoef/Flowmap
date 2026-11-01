# Open questions from the flow map

Where independent runs disagreed. Each answer can be pinned in `decisions.json`.

## Split votes (placed by router-file affinity — please decide)


## Endpoints the runs put in different flows

- `CLI flowmap change` (`flowmap/change.py:__main__`): bu-1→review-a-change, bu-2→browse-the-map, td-1→review-a-change, td-2→review-a-change

## Endpoints at least one run could not place in any flow


## Busiest steps (hops ≥ 8)

- build-the-map / **Maintainer lists every entry point the repo exposes into inventory.json** — 9 hops over 4 files
- build-the-map / **Maintainer checks that every entry point's handler is a call-graph node** — 9 hops over 6 files
- build-the-map / **Maintainer votes the passes into one map with evidence levels and a list of open questions** — 9 hops over 1 files
- browse-the-map / **Maintainer generates Mermaid diagrams of the map at system, flow and step zoom** — 9 hops over 2 files
- browse-the-map / **Maintainer builds the interactive atlas page and browses flows, steps, merges and code** — 10 hops over 2 files
- review-a-change / **Reviewer runs lens on base..head to get the verdict, touched steps, reach and blind spots** — 13 hops over 2 files
- review-a-change / **Author pulls the change's deterministic facts as JSON to write the story from** — 12 hops over 3 files

## Observations ("fighting the system"), by run

### bu-1 (bottom-up)
- Three separate implementations of 'which symbols did this diff change': flowmap/lens.py:analyse (filters docstring/format-only edits via flowmap/lens.py:cosmetic), flowmap/change.py:facts (no cosmetic filter, adds new/deleted/modified status and class folding) and flowmap/atlas.py:overlay (no cosmetic filter, its own new-vs-changed split). change.facts then calls lens.analyse anyway just for the verdict, and flowmap/canvas.py:main calls lens.analyse again after atlas.overlay already walked the same diff, so a docstring-only edit can be 'changed' on the change page and canvas paint yet not count toward the lens verdict.
- The same bounded breadth-first 'code under a step' walk exists twice: flowmap/diagrams.py:Diagrams.step and flowmap/atlas.py:step_code (same MAX_NODES/MAX_DEPTH, same noise skip), differing only in output shape.
- State round-tripped through prose: reconcile records tie-broken split votes only in QUESTIONS.md (flowmap/reconcile.py:write_questions_md), and flowmap/atlas.py:split_votes regex-scrapes them back out of that markdown; flowmap/canvas.py:from_page likewise regex-scrapes JSON out of a rendered atlas HTML page; bin/flowmap-pr-hook:hook regex-scrapes counts from lens's markdown instead of using its --json mode.
- Building the static, data-free viewer (flowmap/viewer.py:main -> flowmap/change.py:viewer_html) imports change.py, which imports lens, atlas, diagrams, graphs and config at module level (lens compiles CODE from config.app_dirs(), atlas/diagrams read config.load()), so `flowmap viewer` needs a git repo and flowmap config even though the page it writes holds no repo data.
- flowmap/diagrams.py:Diagrams.write hard-codes text from the app this tool was extracted from ('workflow engine = `executor.run_workflow`') and tells the reader to override plumbing 'in decisions.json', while plumbing is actually read from flowmap.toml [flows].plumbing via flowmap/config.py:load.
- Reads with side effects: flowmap/lens.py:defs calls flowmap/graphs/codegraph.py:outline, which runs a full codegraph index into a temp dir and fills a module-level cache keyed by file text; flowmap/lens.py:endpoint_set records failures into the module-global INVENTORY_ERRORS that flowmap/lens.py:blind_spots later reads, so blind spots depend on what earlier calls in the same process happened to inventory.
- `flowmap callgraph` is three commands behind one entry point (check, impact, dump), and only impact needs map.json (flowmap/callgraph.py:endpoint_flows), so the reach check used during setup works before a map exists but impact does not.
- Every command is dispatched by bin/flowmap via runpy after flowmap's bin/flowmap:project_python may re-exec under the target repo's .venv; the inventory's handlers (`file:__main__`) hide that dispatcher, so it appears on no step's code path.

### bu-2 (bottom-up)
- `CLI flowmap callgraph` (flowmap/callgraph.py:__main__) and `CLI flowmap change` (flowmap/change.py:main) are each one entry point that fronts several unrelated intents chosen by argv/flags (dump / check / impact / summary; --facts / --check / --link / render). The inventory cannot tell these apart, so I had to repeat the same endpoint in several steps.
- `--link` still renders and writes the change HTML (flowmap/change.py:main) although its documented job is only to print a link; `--facts` and `--check` return before writing. Same command, three different write behaviours.
- reconcile writes QUESTIONS.md as prose and atlas re-parses it with a regex to recover split votes (flowmap/reconcile.py:write_questions_md writes it; flowmap/atlas.py:split_votes parses it). State round-trips through Markdown.
- flowmap/atlas.py:data calls Diagrams.system() only for its side effect of filling d.matrix (comment: `fills d.matrix`), so the atlas depends on the Mermaid diagram generator's internal state; flowmap/diagrams.py:Diagrams.system reads as a pure render but mutates the object.
- flowmap/reconcile.py:main is one long function that votes flows, clusters steps, scores evidence, clusters endpoint-less steps, builds map.json and drives two renderers; by far the busiest single hop.
- Several modules evaluate config at import time (flowmap/lens.py MAP/CODE regex, flowmap/diagrams.py ENGINE_ROOT/PLUMBING/APP_DIRS, flowmap/atlas.py OUT, flowmap/verify.py ROOT), and flowmap/viewer.py imports flowmap/change.py:viewer_html, which drags in lens, atlas, graphs and config just to read a template. Running the viewer builder needs a valid repo config.
- flowmap/change.py:facts, flowmap/lens.py:analyse and flowmap/canvas.py:main all recompute overlapping facts (changed symbols, graph at base and head, endpoint sets); change.facts even calls lens.analyse for the verdict after recomputing most of it itself. lru_cache on lens.graph_at is what keeps this affordable.
- Three overlapping notions of 'app code': config.graph_files/graph_roots ([code].graph), config.app_dirs (adapter roots plus other) feeding lens.CODE, and the adapter-specific file listings in flowmap/adapters/cli.py:_files. A file can be in one and not the others (bin/ is `other` only, so bin/flowmap-pr-hook is not an entry point and is not in the call graph).
- Symbol-definition detection exists in multiple places with different rules: flowmap/verify.py:anchor_ok (regex), flowmap/lens.py:defs (builder.symbols or ts_symbols/rb_symbols regex outlines) and flowmap/graphs/python.py:symbols (AST). A citation verify accepts may not be a node the graph knows.
- flowmap/diagrams.py still hard-codes an app-specific `workflow engine` notion (ENGINE_ROOT from [flows].engine, text mentioning `executor.run_workflow`) in an otherwise generic tool; this repo sets no engine, so that branch is dead here.
- flowmap/callgraph.py:endpoint_flows reads docs/flowmap/map.json, so `callgraph impact` crashes before the first reconcile, while `callgraph check` and the plain/dump forms do not need it. The dependency on reconcile's output is invisible from the command list.

### td-1 (top-down)
- Changed-symbol detection is done three times with near-identical loops: flowmap/lens.py:analyse, flowmap/change.py:facts and flowmap/atlas.py:overlay each call changed_lines/symbols_at/defs and classify new vs modified separately, so lens, change and atlas --pr can disagree on what 'changed' means.
- flowmap/atlas.py:split_votes reads generated Markdown (QUESTIONS.md) back with a regex to recover data that reconcile.py:main already had in memory; an edit to reconcile.py:write_questions_md silently breaks atlas.
- flowmap/canvas.py:from_page scrapes `const DATA = {...};` out of a rendered atlas.html, coupling canvas to the atlas template's exact text.
- The `CLI flowmap callgraph` entry point serves four unrelated jobs (summary, dump, check, impact) in one __main__ block (flowmap/callgraph.py:__main__); check is a setup step while impact is a review step, so one inventory endpoint has to appear in two flows.
- Module-level side effects at import: flowmap/lens.py reads config and compiles CODE/MAP, flowmap/diagrams.py reads ENGINE_ROOT/PLUMBING/APP_DIRS, flowmap/atlas.py fixes OUT, flowmap/verify.py fixes ROOT. atlas, canvas and change all import these, so config is frozen at first import (config.load/root are also @cache).
- flowmap/diagrams.py:Diagrams.system is called by flowmap/atlas.py:data purely for its side effect of filling d.matrix ('d.system()  # fills d.matrix'), a read that writes hidden state.
- flowmap/reconcile.py:tested_endpoints has a special CLI heuristic that greps test text for the module's file name or 'import <module>', a much weaker notion of 'tested' than the path match used for HTTP endpoints.
- bin/flowmap-pr-hook and bin/flowmap are shell/script entry points a person or Claude Code hook runs but they are not in inventory.json (the cli adapter only scans flowmap/*.py), so the PR hook flow described in README is invisible to the map.

### td-2 (top-down)
- Three separate derivations of 'which symbols changed': flowmap/lens.py:analyse (drops docstring/format-only edits via flowmap/lens.py:cosmetic), flowmap/change.py:facts (no cosmetic filter, adds new/deleted/modified status) and flowmap/atlas.py:overlay (no cosmetic filter, new vs changed by base defs). A change page can list a symbol whose edit the verdict on the same page ignored.
- flowmap/change.py:facts calls flowmap/lens.py:analyse in full just to read verdict/blind/spreads_to, after already recomputing changed lines, graphs and endpoint sets itself; flowmap/canvas.py:main does the same per --change on top of flowmap/atlas.py:overlay. `flowmap change` is busier than its intent ('render a page') because it is lens plus a second lens.
- flowmap/atlas.py:data builds the call graph from the working tree (flowmap/diagrams.py:Diagrams.__init__ -> flowmap/callgraph.py:Graph.__init__) while flowmap/atlas.py:overlay uses flowmap/lens.py:graph_at(head) from git; one atlas page can mix two graphs when the worktree differs from head.
- flowmap/atlas.py:split_votes reads the reconciler's split votes back by regex-parsing the generated QUESTIONS.md prose instead of structured data from flowmap/reconcile.py:main: a markdown wording change in flowmap/reconcile.py:write_questions_md silently empties the atlas's split badges.
- flowmap/change.py imports flowmap/atlas.py:step_keys, which pulls in flowmap/diagrams.py (module-level config reads, Diagrams) just for a tiny key helper: the change command depends on the atlas/diagram stack.
- flowmap/lens.py:endpoint_set records failures into the module-global INVENTORY_ERRORS that flowmap/lens.py:blind_spots later reads; since flowmap/change.py:facts calls endpoint_set itself and then lens.analyse, state from one call leaks into the next analysis in the same process.
- flowmap/diagrams.py:Diagrams.write hardcodes '`executor.run_workflow`' in the generated README text regardless of the configured [flows].engine, and generated docs still say 'tools/flowmap/...'; leftovers from the app the tool was first built in.
- Two lists of commands must stay in sync: bin/flowmap's COMMANDS set dispatches via runpy, while the inventory derives commands from every flowmap/*.py with a __main__ block (flowmap/adapters/cli.py:entries); bin/flowmap-pr-hook, the only automatic caller, is not an entry point at all.
- flowmap/change.py:main writes the HTML page before refusing --link on story lint problems, so a 'refused' run still overwrites docs/flowmap/changes/<name>.html.
