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

1. From the repo root (if `flowmap` isn't on PATH, use `"${CLAUDE_PLUGIN_ROOT}/bin/flowmap"`), run `flowmap lens <base> <head>` (the repo you are reviewing must already have a map;
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
   It opens with a **verdict**: *contained* (no existing entry point runs changed code), *spreads*
   (names the entry points and flows it reaches) or *blind* (the change includes something it
   can't see: module-level code, model or settings classes, migrations, code with no call graph,
   files it couldn't parse, entry points it lost track of). Carry the verdict into your first lines. Never
   upgrade *blind* to *contained*: a blind spot is exactly where you read the diff yourself.
2. Read the PR description / commit messages (`git log --format=%B <base>..<head>`) for
   stated intent.
3. For each touched step and each off-map change, read *just enough* of the diff to say
   what behaviour changed. Do not summarise code; describe behaviour.
4. Write the output below. Keep it to one screen.

## Output

```
## <one line: what this change does, in user terms>

**Verdict:** <contained | spreads to N entry points in <flows> | blind: what lens can't see>
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

## The change page

Also write the change as a page people can read without the diff:

1. `flowmap change <base> <head> --facts` prints the deterministic facts:
   changed symbols with the map steps that run them (and a call path proving it), callers left
   unedited, call edges and module dependencies added or removed, reach that moved, flow spread.
2. Write `docs/flowmap/changes/<name>.story.json` (e.g. `pr-12`). It is the prose layer only;
   every claim in it must be backed by a fact from step 1 or a line of the diff:

   ```json
   {"title": "what the system now does, as a name (not the PR title if that says how)",
    "pr": "PR #12", "url": "<pr url>",
    "intent": "the author's stated intent, one sentence",
    "delta": "how the system moves, in 2-3 sentences of flow terms; say what did NOT change too",
    "chapters": [{
      "title": "one behaviour change, stated as what the system now does",
      "role": "core | supporting | refactor | outside", "kind": "free text, e.g. new capability",
      "symbols": ["path.py:Qual.name", "..."], "files": ["non-code files, e.g. a skill"],
      "before": "system behaviour before", "after": "system behaviour after",
      "claim": "one line", "why": "who/what runs through this and what it costs or risks them",
      "questions": [{"q": "concrete, cites a function or flow", "why": "what the answer decides",
                     "kind": "ask | check"}]}]}
   ```

   Order chapters core first (the change the others exist to support), then by how much an
   answer could change the verdict. Group by behaviour, not by file. A behaviour-preserving
   refactor gets its own `refactor` chapter so it can be read quickly. Prose that steers an
   agent (skills, prompts) is behaviour: give it a chapter. Two to five questions per chapter.
   "Ask" means only the author can answer; "check" means the reviewer can settle it themselves.
3. `flowmap change <base> <head> --name <name> --link` writes
   `docs/flowmap/changes/<name>.html` and prints a viewer link carrying the whole page, for the
   PR body. Symbols the story leaves out land in a "not in the story" chapter, so nothing
   changed is hidden. Without `viewer` in `flowmap.toml`, drop `--link` and link the committed page.

## After

If the change adds a step or moves one, say so and suggest re-running the map loop
(`docs/flowmap/README.md`) — don't edit `map.json` by hand.
