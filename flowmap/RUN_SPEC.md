# Flow map run — brief for one independent mapping pass

_Template: `brief.py` fills the {{…}} slots per repo and per pass. Don't hand a raw copy to an agent._

You are one of several **independent** passes that map this codebase into user
flows → steps → code paths. Other passes use a different method. Your output is
compared mechanically against theirs: where you agree, the map firms up; where you
disagree, a human looks. So **independence matters more than polish** — do not look
for or read other runs' output, and do not try to guess what they will say.

Repo: `{{ROOT}}` · your run id: `{{RUN_ID}}` · method: **{{METHOD}}** · output: `{{OUTPUT}}`

## Ground rules

- **Derive from code only.** Do NOT read anything under `{{OUT}}/` (earlier maps, other runs)
  except `{{OUT}}/inventory.json`, and do not read existing architecture, flow or design
  documents — they are a prior this map must stay independent of. A top-level README for
  orientation is fine. Code comments and docstrings are fine.
- **Every anchor is a citation**: `repo/relative/path.ext:symbol` where `symbol` is a
  function, class, method (`Class.method`), component, hook, or Ruby method that is *defined
  in that file* (`:default` is accepted for a default export). If you can't point at a
  definition, don't cite it.
- Entry points must be copied **exactly** from `{{OUT}}/inventory.json` — the `endpoint`
  field (`"GET /path"`, `"PAGE /path"`, `"ACTION file#fn"`). Each lists its `handler`.
- Do not modify any file except your own output file.

## Top-level flows

{{VOCABULARY}}

## Method: {{METHOD}}

{{METHOD_TEXT}}

## This stack

{{STACK}}

## Granularity

- A **step** is one thing an actor does, or one thing the system does in response, that
  you'd say out loud in one sentence ("Reviewer rejects a held run with reason chips").
  Usually 1–4 entry points. Steps with no entry point (background jobs, pure UI) are allowed
  but keep them rare.
- A step's **code_path** is the ordered server-side hops for that step: handler → services →
  domain functions → (models touched). Project code only, no framework/stdlib. Typically
  2–8 hops. If a step genuinely needs more, include them — busy-ness is signal.
- **writes**: the persistent state the step changes (`Model.field` or `Model` for inserts).
  Empty for reads.
- Background/system work (jobs, schedulers, ingestion, callbacks) counts as steps with actor
  `system`. External callers (CLIs, webhooks, API clients) are actor `external`.
- An entry point may appear in more than one step if it truly serves several. Every inventory
  entry point must appear at least once — in a step or in `unplaced_endpoints` with a reason
  (dead code, admin-only, can't find a caller…).

## Output

Write exactly one JSON file to `{{OUTPUT}}`, shaped:

```json
{
  "run_id": "{{RUN_ID}}",
  "method": "{{METHOD}}",
  "flows": [
    {
      "id": "flow-id",
      "summary": "one sentence: what this flow is for, in user terms",
      "steps": [
        {
          "id": "kebab-step-id",
          "name": "Actor does one thing, in one sentence",
          "actor": "user | admin | external | system  (or a role name the app uses)",
          "endpoints": ["exact entry points from inventory.json"],
          "ui": ["path/to/Component.tsx:Component"],
          "code_path": ["path/to/handler.ext:handler", "path/to/service.ext:Class.method"],
          "writes": ["Model.field", "Model"],
          "confidence": "high | medium | low",
          "notes": "optional: anything surprising"
        }
      ]
    }
  ],
  "unplaced_endpoints": [{ "endpoint": "…", "why": "…" }],
  "observations": [
    "places where the code seems to fight the system: a step far busier than its intent, two paths doing the same thing differently, state written in two places, reads that write. Cite anchors."
  ]
}
```

Order steps within a flow in the order a user would encounter them.

## Before you finish

Run `{{VERIFY}}` and fix every `BAD` citation and every `MISS` entry point until it exits 0.
Then reply with a 3-line summary: flows, steps, and the single most surprising thing you found.
