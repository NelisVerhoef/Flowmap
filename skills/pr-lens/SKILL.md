---
name: pr-lens
description: Place a PR or commit range on the flow map (docs/flowmap/, built by the flowmap tools) and draft the questions a reviewer should ask — without asking them to read the diff first. Use when the user says "lens this PR", "what does this PR change", "/pr-lens <ref>", or wants to review a change at the flow level.
---

# PR lens

The reviewer does not want a code review. They want to know **where on the system this
change lands** and **what to ask the author**. They will drill into code only if the
flow-level picture looks wrong.

## Inputs

A PR number, a branch, or a commit range. Resolve to `<base> <head>`:
- commit `abc123` → `abc123^ abc123`
- branch → `$(git merge-base main <branch>) <branch>`
- PR number → fetch its head (GitHub MCP `pull_request_read`, or `git fetch origin pull/<n>/head`)
  and use the merge-base with its base branch.

## Steps

1. From the repo root, run `python3 <flowmap>/bin/flowmap lens <base> <head>` (the repo you are reviewing must already have a map;
   build one with the flowmap-build skill). This is the ground truth for
   placement — do not contradict it; if you think the map is wrong, say so separately.
   Its **Reach** section comes from the static call graph (`callgraph.py`), not from any
   model: it is the authority on blast radius. It over-reports (reachable ≠ executed:
   conditional branches, test doubles resolved by method name) and misses string/registry
   dispatch — so treat a reached step as "ask whether this path is affected", not "broken".
   Its **Reach diff** section compares the call graph at base and head: existing code an
   endpoint can newly reach, or no longer reaches, though that code itself may be unchanged.
   A map anchor or a check (auth, validation, audit) under "no longer reachable" is the first
   question to ask the author.
2. Read the PR description / commit messages (`git log --format=%B <base>..<head>`) for
   stated intent.
3. For each touched step and each off-map change, read *just enough* of the diff to say
   what behaviour changed. Do not summarise code; describe behaviour.
4. Write the output below. Keep it to one screen.

## Output

```
## <one line: what this change does, in user terms>

**Lands on:** <flow> → <step>, <step> · <flow> → <step>
**New on the map:** <endpoints added / off-map code that is really a new step — name the step you'd add>

### Before → after
- <step>: <old behaviour> → <new behaviour>     (one line per touched step)

### Shape
- <intent vs size: does the amount of code match the amount of behaviour change? name the
  busiest part and whether that busyness looks essential (domain is hard) or accidental>
- <blast radius line if any shared node was touched, else omit>
- <tests: changed / not changed, and whether the touched steps' evidence level moved>

### Questions to ask
1. ...   (3–5, ranked; each tied to a step or anchor)
```

Draw questions from these patterns, picking only the ones the change actually raises:
- **User-visible** — what does the user see differently, and in which flow?
- **State** — what new state is persisted, and who else reads it?
- **Failure** — if this new step/dependency fails (LLM down, background task dies), what does the user experience?
- **Blast radius** — N other steps share `<anchor>`; did any rely on the old behaviour?
- **Altitude** — why is this handled at this layer rather than where the data enters?
- **Alternatives** — what was the simpler version, and why didn't it work?
- **Reversibility** — if we roll this back, is the stored data still coherent?
- **Map gap** — this code isn't on the map; which flow does it belong to?

A question that's wrong because you misread the code is cheap (the author corrects it).
A question so vague the author can't be wrong ("is this tested?") is useless. Prefer
specific and occasionally wrong over safe and vague.

## After

If the change adds a step or moves one, say so and suggest re-running the map loop
(`docs/flowmap/README.md`) — don't edit `map.json` by hand.
