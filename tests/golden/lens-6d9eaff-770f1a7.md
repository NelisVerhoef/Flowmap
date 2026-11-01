# Flow lens: `6d9eaff..770f1a7`

**Verdict: blind.** This change includes things this lens cannot see, so it can't call it contained; what it can see spreads to 5 existing entry point(s).

## Blind spots

- module-level code changed (constants, config, router registration): `flowmap/change.py`
- files outside the analysed code: `bin/flowmap`, `flowmap/atlas.template.html`, `flowmap/change.template.html`

11 files changed (3 app code, 0 tests, 8 other) · 21 code symbols changed · 4 map steps touched across 3 flows

## Endpoint changes

- **added** `CLI flowmap change` → `flowmap/change.py:__main__`

## Flows and steps touched

### build-the-map
- **Maintainer checks that every entry point's handler is a call-graph node** (agreed, busy 9/6) — changed: `flowmap/callgraph.py:Graph.__init__`

### browse-the-map
- **Maintainer generates Mermaid diagrams of the map at system, flow and step zoom** (agreed, busy 9/2) — changed: `flowmap/callgraph.py:Graph.__init__`

### review-a-change
- **Reviewer runs lens on base..head to get the verdict, touched steps, reach and blind spots** (agreed, busy 13/2) — changed: `flowmap/lens.py:graph_at`, `flowmap/lens.py:main`, `flowmap/lens.py:reach_diff`
- **Author pulls the change's deterministic facts as JSON to write the story from** (agreed, busy 12/3) — changed: `flowmap/change.py:__main__`, `flowmap/change.py:facts`, `flowmap/change.py:hunks`, `flowmap/change.py:main`, `flowmap/change.py:signature`, `flowmap/lens.py:graph_at`, `flowmap/lens.py:reach_diff`

## Reach (call graph, deterministic)

Changed backend code can execute under **5 steps in 3 flows**; 1 of those steps the map's own anchors did not show (hidden blast radius).

Widest-reaching **modified** code (new code only inherits its caller's reach):

- `flowmap/callgraph.py:Graph.__init__` — reachable from 5 endpoints in 3 flows
- `flowmap/callgraph.py:Graph` — reachable from 5 endpoints in 3 flows
- `flowmap/callgraph.py:Graph.callers` — reachable from 4 endpoints in 3 flows
- `flowmap/lens.py:main` — reachable from 1 endpoints in 1 flows

Steps reached but not anchored (look here):

- **browse-the-map**
  - Maintainer builds the interactive atlas page and browses flows, steps, merges and code — via `Graph.__init__`, `Graph.callers`, `Graph`

## Reach diff (call graph, base → head)

37 call edges added, 2 removed. Existing code newly reachable from some endpoint: **0**; no longer reachable from some endpoint: **0**.

Edges added: `callgraph.Graph.callees` → `callgraph.Graph._closure`, `callgraph.Graph.callers` → `callgraph.Graph._closure`, `change.__main__` → `change.main`, `change.facts` → `atlas.step_keys`, `change.facts` → `callgraph.Graph.callees`, `change.facts` → `callgraph.Graph.edge_set`, `change.facts` → `callgraph.Graph.reaches`, `change.facts` → `change.facts.module`, … 29 more
Edges removed: `lens.main` → `callgraph.Graph`, `lens.main` → `lens.git`

## Off-map changes (code the map doesn't know)

New code, or a gap in the map. Either way: where does it sit in a flow?

**Modified** — existing code changed; shared modules first:

- `flowmap/callgraph.py`: `Graph`, `Graph.callers`

**New** — didn't exist before:

- `flowmap/callgraph.py`: `Graph._closure`, `Graph.callees`, `Graph.edge_set`
- `flowmap/change.py`: `auto_chapters`, `facts.module`, `facts.node_for`, `file_kind`, `merge`
- `flowmap/lens.py`: `main.listing`

## Shape

- Steps touched: 4 · symbols changed: 21 · ratio 5.2 symbols per step
- Tests changed: 0 — **no tests changed**

