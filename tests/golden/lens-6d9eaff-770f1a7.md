# Flow lens: `6d9eaff..770f1a7`

**Verdict: blind.** This change includes things this lens cannot see, so it can't call it contained; what it can see spreads to 5 existing entry point(s).

## Blind spots

- module-level code changed (constants, config, router registration): `flowmap/change.py`
- files outside the analysed code: `bin/flowmap`, `flowmap/atlas.template.html`, `flowmap/change.template.html`

11 files changed (3 app code, 0 tests, 8 other) · 20 code symbols changed · 4 map steps touched across 1 flows

## Endpoint changes

- **added** `CLI flowmap change` → `flowmap/change.py:__main__`

## Flows and steps touched

### new:review-change-on-map
- **Maintainer generates Mermaid diagrams at system, flow and step zoom** (agreed, busy 12/2) — changed: `flowmap/callgraph.py:Graph.__init__`
- **Reviewer places a base..head diff on the map (steps touched, call-graph reach, off-map code)** (agreed, busy 12/3) — changed: `flowmap/callgraph.py:Graph.__init__`, `flowmap/callgraph.py:Graph.callers`, `flowmap/lens.py:main`
- **Developer asks which entry points and flows can reach a file:symbol** (agreed, busy 8/1) — changed: `flowmap/callgraph.py:Graph.__init__`, `flowmap/callgraph.py:Graph.callers`
- **Maintainer builds the interactive atlas page and browses flows, steps and components** (agreed, busy 12/4) — changed: `flowmap/callgraph.py:Graph.__init__`

## Reach (call graph, deterministic)

Changed backend code can execute under **4 steps in 1 flows**; 0 of those steps the map's own anchors did not show (hidden blast radius).

Widest-reaching **modified** code (new code only inherits its caller's reach):

- `flowmap/callgraph.py:Graph.__init__` — reachable from 5 endpoints in 1 flows
- `flowmap/callgraph.py:Graph` — reachable from 5 endpoints in 1 flows
- `flowmap/callgraph.py:Graph.callers` — reachable from 4 endpoints in 1 flows
- `flowmap/lens.py:main` — reachable from 1 endpoints in 1 flows

## Reach diff (call graph, base → head)

36 call edges added, 2 removed. Existing code newly reachable from some endpoint: **0**; no longer reachable from some endpoint: **0**.

Edges added: `callgraph.Graph.callees` → `callgraph.Graph._closure`, `callgraph.Graph.callers` → `callgraph.Graph._closure`, `change.__main__` → `change.main`, `change.facts` → `atlas.step_keys`, `change.facts` → `callgraph.Graph.callees`, `change.facts` → `callgraph.Graph.edge_set`, `change.facts` → `callgraph.Graph.reaches`, `change.facts` → `change.facts.module`, … 28 more
Edges removed: `lens.main` → `callgraph.Graph`, `lens.main` → `lens.git`

## Off-map changes (code the map doesn't know)

New code, or a gap in the map. Either way: where does it sit in a flow?

**Modified** — existing code changed; shared modules first:

- `flowmap/callgraph.py`: `Graph`

**New** — didn't exist before:

- `flowmap/callgraph.py`: `Graph._closure`, `Graph.callees`, `Graph.edge_set`
- `flowmap/change.py`: `__main__`, `auto_chapters`, `facts`, `facts.module`, `facts.node_for`, `file_kind`, `hunks`, `main`, `merge`, `signature`
- `flowmap/lens.py`: `graph_at`, `reach_diff`

## Shape

- Steps touched: 4 · symbols changed: 20 · ratio 5.0 symbols per step
- Tests changed: 0 — **no tests changed**

