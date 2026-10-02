# Open questions from the flow map

Where independent runs disagreed. Each answer can be pinned in `decisions.json`.

## Proposed flows (name them, then paste into flowmap.toml)

Passes proposed these flows independently; ones covering the same entry points were merged. Rename, merge or drop them, then paste the block into `flowmap.toml`. From then on they are your fixed vocabulary.

| proposed id | steps | entry points | seen by | summary |
|---|---|---|---|---|
| `new:discover-entry-points` | 1 | 1 | bu-1, bu-2, td-1, td-2 | Maintainer scans the repo being mapped and gets the list of every entry point, the join key for all later passes. |
| `new:review-change-on-map` | 4 | 4 | bu-1, bu-2, td-1, td-2 | See the map: flows, their steps and the code each step runs, as Mermaid diagrams and an interactive atlas page. |
| `new:run-mapping-passes` | 3 | 3 | bu-1, bu-2, td-1, td-2 | Turn a repo into a first flow map: list its entry points, brief independent mapping passes, check each pass, and vote them into one map. |

```toml
[[flows.vocabulary]]
id = "discover-entry-points"
scope = "Maintainer scans the repo being mapped and gets the list of every entry point, the join key for all later passes."
[[flows.vocabulary]]
id = "review-change-on-map"
scope = "See the map: flows, their steps and the code each step runs, as Mermaid diagrams and an interactive atlas page."
[[flows.vocabulary]]
id = "run-mapping-passes"
scope = "Turn a repo into a first flow map: list its entry points, brief independent mapping passes, check each pass, and vote them into one map."
```

## Split votes (placed by router-file affinity — please decide)


## Endpoints the runs put in different flows

- `CLI flowmap inventory` (`flowmap/inventory.py:__main__`): bu-1→new:run-mapping-passes, bu-2→new:discover-entry-points, td-1→new:discover-entry-points, td-2→new:discover-entry-points

## Endpoints at least one run could not place in any flow


## Busiest steps (hops ≥ 8)

- new:discover-entry-points / **Maintainer lists every entry point the repo exposes into inventory.json** — 11 hops over 4 files
- new:review-change-on-map / **Maintainer generates Mermaid diagrams at system, flow and step zoom** — 12 hops over 2 files
- new:review-change-on-map / **Reviewer places a base..head diff on the map (steps touched, call-graph reach, off-map code)** — 12 hops over 3 files
- new:review-change-on-map / **Developer asks which entry points and flows can reach a file:symbol** — 8 hops over 1 files
- new:review-change-on-map / **Maintainer builds the interactive atlas page and browses flows, steps and components** — 12 hops over 4 files
- new:run-mapping-passes / **Maintainer votes the passes into one map with evidence levels and a list of open questions** — 10 hops over 1 files

## Observations ("fighting the system"), by run

### bu-1 (bottom-up)
- Two implementations of 'place a diff on the map': flowmap/atlas.py:overlay re-derives changed/new symbols and call-graph reach itself using lens helpers, instead of sharing logic with flowmap/lens.py:main. They already differ: overlay skips test files and '<module>' hits, lens.main counts '<module>' as a changed symbol and classifies steps by anchor match first.
- flowmap/atlas.py:build calls flowmap/diagrams.py:Diagrams.system and throws away the Mermaid it returns, only to get self.matrix set as a side effect.
- flowmap/atlas.py:split_votes scrapes split votes back out of the human-facing QUESTIONS.md written by flowmap/reconcile.py:write_questions_md (regex on '→ placed'): a generated report doubles as a data interface, and the vote data is never written to map.json.
- The call graph is rebuilt from scratch in four places: flowmap/callgraph.py:__main__, flowmap/diagrams.py:Diagrams.__init__, flowmap/lens.py:main and once per --pr in flowmap/atlas.py:overlay (plus Diagrams again in flowmap/atlas.py:build).
- flowmap/adapters/cli.py:_files lists commands with git ls-files, so a new, untracked command script is invisible to inventory while every other tool reads the worktree; flowmap/config.py:detect_entries never auto-detects the cli adapter, so CLI repos depend on flowmap.toml.
- flowmap/verify.py:anchor_ok checks each dotted part of 'Class.method' independently anywhere in the file, so a method cited under the wrong class still passes.
- flowmap/reconcile.py:canonical_new_flows merges proposed flows transitively at Jaccard >= 0.3 via union-find, so a chain of partially overlapping proposals can collapse into one flow.
- Docstrings and messages still name another repo's layout ('tools/flowmap/...', 'backend/app' in flowmap/callgraph.py and flowmap/reconcile.py:write_map_md), though the real path is flowmap/ under config.root().

### bu-2 (bottom-up)
- flowmap/atlas.py:overlay re-implements PR change detection (changed_lines/symbols_at/endpoint_set from lens.py) with its own changed/new classification, parallel to flowmap/lens.py:main.
- flowmap/atlas.py:build and flowmap/callgraph.py:__main__ import other command scripts as libraries (diagrams, lens), so 'commands' are also shared modules; flowmap/atlas.py:step_code duplicates flowmap/diagrams.py:Diagrams.step.
- flowmap/callgraph.py:endpoint_flows and flowmap/diagrams.py:Diagrams.__init__ each independently load inventory.json and map.json to build the endpoint-to-handler lookup.
- flowmap/verify.py:anchor_ok uses regex definition matching while flowmap/callgraph.py:Graph uses the AST, so what counts as a valid symbol can differ between verify and the call graph.
- flowmap/reconcile.py:main is one very large function doing voting, step clustering, evidence and file writing in one body.
- flowmap/inventory.py:endpoints is reused by lens.py via git revisions through a custom read callable; the 'inventory' command itself only writes the worktree view.

### td-1 (top-down)
- flowmap/bin/flowmap dispatches by runpy, so every command is a `__main__` block with business logic inline (flowmap/inventory.py:__main__, flowmap/diagrams.py:__main__) while others delegate to main(); inconsistent shape.
- flowmap/lens.py:main is a ~200-line function mixing diff parsing, map matching, call-graph reach and markdown rendering.
- flowmap/atlas.py:overlay duplicates the changed/new symbol computation from flowmap/lens.py:main instead of sharing it.
- flowmap/reconcile.py:main is very large and writes map.json, MAP.md and QUESTIONS.md in one pass (write_map_md, write_questions_md).
- flowmap/config.py:load is cached and also auto-detects entries (detect_entries), so a read of config can scan the filesystem with glob.
- flowmap/brief.py:main reads flowmap/RUN_SPEC.md and drops the first lines by split, so the template header layout is load-bearing.
- Commands lens, callgraph, diagrams and atlas require docs/flowmap/map.json (from reconcile) at import time (flowmap/lens.py MAP, flowmap/callgraph.py:endpoint_flows), so ordering between commands is implicit.

### td-2 (top-down)
- Two implementations of 'which symbols did this diff change': flowmap/lens.py:main (keeps <module>, tracks new_symbols vs base) and flowmap/atlas.py:overlay (drops <module>, splits new/changed) each re-derive it from flowmap/lens.py:changed_lines + flowmap/lens.py:symbols_at, and each rebuilds a head-revision flowmap/callgraph.py:Graph.__init__ separately.
- flowmap/atlas.py:split_votes reads split votes back out of the human-facing QUESTIONS.md with a regex instead of from map.json; the data written by flowmap/reconcile.py:write_questions_md becomes an implicit machine format.
- flowmap/atlas.py:overlay calls flowmap/lens.py:endpoint_set(head) twice, each re-running the whole inventory over git show.
- Stale/mismatched prose baked into outputs: flowmap/diagrams.py:Diagrams.write always prints '**workflow engine** = `executor.run_workflow`' and says plumbing is overridden in decisions.json, while plumbing actually comes from flowmap.toml via flowmap/config.py:load; flowmap/reconcile.py:write_map_md cites 'tools/flowmap/reconcile.py'; callgraph's docstring still says 'backend/app'.
- flowmap/callgraph.py:Graph.reaches has no callers in the repo (dead code).
- Importing flowmap/atlas.py pulls in flowmap/lens.py, whose module-level code compiles regexes from flowmap/config.py:app_dirs, so even a plain atlas build depends on lens's config side effects.
- flowmap/verify.py:anchor_ok treats any line matching `^\s*name\s*[:=(]` as a definition, so a local assignment or a call at line start satisfies a citation; verification is looser than 'defined in that file'.
- Nothing writes flowmap.toml or decisions.json; the human decision step between two reconcile runs is entirely off-CLI, and flowmap/callgraph.py:endpoint_flows and flowmap/diagrams.py:Diagrams.__init__ fail outright if map.json does not yet exist.
