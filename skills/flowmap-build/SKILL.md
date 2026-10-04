---
name: flowmap-build
description: Build or rebuild the flow map of the current repo (docs/flowmap/) — entry-point inventory, independent bottom-up and top-down passes, verification, reconciliation by agreement, diagrams and the interactive atlas. Use when the user asks to map the system, build/refresh the flow map, or set flowmap up in a new repo.
---

# Build the flow map

The map is built by **agreement between independent passes**, not by any single pass being
right. Agreement only means something between *different methods*, so never skip the mix.

`flowmap` is on PATH when this plugin is installed. If the bare command isn't found, use
`"${CLAUDE_PLUGIN_ROOT}/bin/flowmap"` (or wherever the flowmap repo is checked out).
Run everything from the root of the repo being mapped.

1. **Config.** If there is no `flowmap.toml`, run `flowmap inventory` and see what was
   auto-detected. Rails needs its routes dumped once where the app boots
   (`bin/rails routes > tmp/routes.txt`, then `routes_file` in `flowmap.toml`). Write a
   minimal `flowmap.toml` with `[code] tests = [...]` and, for Python, `python = [...]`.
2. **Inventory.** `flowmap inventory`. Sanity-check the count and a few handlers against
   the code before spending anything on passes.
3. **Briefs.** `flowmap brief bu-1 bottom-up`, `bu-2 bottom-up`, `td-1 top-down`,
   `td-2 top-down`. No flow vocabulary in `flowmap.toml` = discovery mode, handled by the brief.
4. **Passes.** Launch four agents in parallel, in the background, each with only:
   "Work in <repo>. Read <brief path> and follow it exactly." Use two different models
   across each method pair if you can. Do not give them each other's output or any summary
   of the system — independence is the point.
5. **Verify and reconcile.** `flowmap verify docs/flowmap/runs/??-?.json` (all must exit 0;
   send a failing pass back to fix its own file), then
   `flowmap reconcile docs/flowmap/runs/??-?.json`.
6. **The human layer.** Show the user `QUESTIONS.md`: proposed flows (discovery mode) to
   name and paste into `flowmap.toml`, split votes to settle in `decisions.json`. These are
   theirs to decide; don't decide them. Reconcile again after they answer.
7. **Views.** `flowmap diagrams` and `flowmap atlas`. Report: flows, steps, evidence mix,
   and the observations more than one pass reported independently (the strongest signal).

Rebuild weekly or after big merges, not per PR: the map should move slowly so its layout
stays familiar. Per PR, use the `pr-lens` skill.
