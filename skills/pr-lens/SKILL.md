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
**Door:** <two-way: rolls back cleanly | one-way: what can't be walked back, e.g. stored data, a format others read, a removed entry point>
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
- **Alternatives** — what was the simpler version, and why didn't it work? (Only for someone
  else's PR: when you wrote the change, you know, so the story's `why` says it instead.)
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
    "no_longer": [{"was": "a belief a reader of the old system holds that this change makes false",
                   "cite": "the changed file, file:line or symbol that shows it",
                   "step": "optional: the map step key whose text still says it"}],
    "chapters": [{
      "title": "one behaviour change, stated as what the system now does",
      "role": "core | supporting | refactor | outside", "kind": "free text, e.g. new capability",
      "symbols": ["path.py:Qual.name", "..."], "files": ["non-code files, e.g. a skill"],
      "before": "system behaviour before", "after": "system behaviour after",
      "claim": "one line",
      "why": "who/what runs through this and what it costs or risks them; when there was another way, 'rather than X, because Y'",
      "verified": [{"how": "test | ran | looked | not checked",
                    "what": "test: tests/test_x.py:Name, which must exist at head; ran: the command and its result; looked: what you saw"}],
      "questions": [{"q": "concrete, cites a function or flow", "why": "what the answer decides",
                     "kind": "ask | check"}]}]}
   ```

   Order chapters core first (the change the others exist to support), then by how much an
   answer could change the verdict. Group by behaviour, not by file. A behaviour-preserving
   refactor gets its own `refactor` chapter so it can be read quickly. Prose that steers an
   agent (skills, prompts) is behaviour: give it a chapter. Two to five questions per chapter.
   "Ask" means only the author can answer; "check" means the reviewer can settle it themselves.

   `no_longer` is the part a reader most needs and most often misses: what they believed that is
   now false (a removed check, a view that is gone, a rule that moved). At most three, each citing
   the diff. A line that sounds right but is still true is worse than none: check each against the
   code at head. When the map's own step text says the old thing, name the step. The page adds what
   the facts show on their own (lost reach, removed entry points and module links, map anchors the
   change removed) and a "still true" line, so don't repeat those.

   `verified` says how each part's `after` was checked, so the reader can tell what is proven
   from what is claimed. "not checked" is a fine answer; leaving it out is not.
3. `flowmap change <base> <head> --name <name> --link` writes
   `docs/flowmap/changes/<name>.html` and prints a viewer link carrying the whole page, for the
   PR body. Symbols the story leaves out land in a "not in the story" chapter, so nothing
   changed is hidden. It checks the story against the facts (symbols and files the diff changes,
   cites in the diff, test names that exist at head) and prints no link until the story passes;
   the page shows anything that failed. The link opens `https://flowmap.testabl.ai/v1/change.html`
   unless `viewer` in `flowmap.toml` names another; put the printed link in the PR body as is
   (or, for a page too big for any link, the line it prints instead). Diff text of doc and other
   non-code files only rides along for files a chapter names in `files`.

   `flowmap change <base> <head> --name <name> --check` prints the story's problems as JSON, each
   with a `code`, the field it is about (`subject`, e.g. `no_longer[1].cite`) and a `fix`. A
   `file:line` cite must be a line the diff shows, at base or head. Repair the claim, not the
   check: cite what backs it, correct it, or mark it `not checked`; don't delete a claim only to
   pass. Two rounds; if it still fails, stop and show the user the remaining problems.
4. Reader test, before the PR opens: give a subagent with none of your context only the story file
   and the `--facts` output, and ask it: which flows changed; what is no longer true; what stayed
   the same; what breaks for the user if the core part fails. Compare its answers with the facts
   and your own understanding. Where it is wrong or has to guess, fix the story, not the reader,
   and render again. It is the same model as you, so it catches what the story leaves out, not
   what it gets subtly wrong.

## After

If the change adds a step or moves one, say so and suggest re-running the map loop
(`docs/flowmap/README.md`) — don't edit `map.json` by hand.
