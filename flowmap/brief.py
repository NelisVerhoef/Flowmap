"""Write the brief for one independent map pass, filled in for this repo.

    python <tools>/flowmap/brief.py <run-id> bottom-up|top-down   # prints the brief's path

Hand each agent "Read <that path> and follow it exactly". Run ≥2 passes per method, ideally
on different models: agreement only means something between different methods.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import config  # noqa: E402

TOOLS = Path(__file__).parent

METHODS = {
    "bottom-up": """Start from `inventory.json` and the server code. For each entry point, open its handler
and follow the calls into services/domain code to build `code_path` and `writes`. Then find
what in the UI reaches it (see *This stack* for where callers live) to fill `ui`. Also find
system/background work that isn't behind an entry point but runs as part of a flow. Only
after you have the per-entry-point picture, group entry points into steps and steps into flows.""",
    "top-down": """Start from what a person can do. Walk every screen, page, tab and modal (see *This stack*
for where they live) and list the actions available there, in the order a user would meet
them. For each action, find the entry point it calls and match it to `inventory.json`, then
trace its handler into services to build `code_path` and `writes`. After the walk, sweep the
inventory for entry points no screen reaches and place them (API clients, webhooks, CLIs,
admin) or mark them unplaced.""",
}

STACK = {
    "fastapi": """**FastAPI** (`{main}`): handlers are the decorated router functions. Dependencies
(`Depends(...)`) run first — auth lives there. Background work: `BackgroundTasks`,
`asyncio.create_task`, schedulers. If there is a separate JS frontend, its API client and
query hooks are where `ui` callers live.""",
    "rails": """**Rails** (root `{root}`): each entry point's handler is the controller action, resolved
through concerns and parent controllers (an entry marked `implicit` just renders its view).
Follow `before_action` callbacks — auth and loading live there — then into models
(`app/models`), service objects, jobs (`app/jobs`, `perform_later`) and model callbacks
(`after_commit` etc. are hidden steps). Screens are `app/views` (start from layouts and nav
partials); Stimulus controllers and Turbo frames are UI. Cite Ruby methods, not templates.""",
    "nextjs": """**Next.js** (root `{root}`): `PAGE` entries are the screens — start top-down passes there.
`GET/POST…` entries are route handlers; `ACTION` entries are server actions, usually called
from forms or client components. Server components fetch data directly — a page's own data
loading belongs in its step's `code_path`. Middleware (`middleware.ts`) runs before
everything; note it, don't make it a step.""",
}


def vocabulary_text(vocab):
    if not vocab:
        return ("**Discovery mode** — this repo has no flow vocabulary yet. Propose flows yourself, "
                "named `new:<kebab-slug>`, each one a thing a user is trying to get done (not a "
                "code module). Aim for 5–12 flows. The reconciler merges passes' proposals by the "
                "entry points they cover; the human then names the result in `flowmap.toml`.")
    rows = "\n".join(f"| `{f['id']}` | {f.get('scope', '')} |" for f in vocab)
    return ("Place steps under one of these flow ids (human-owned). If a real user-facing flow fits "
            "none of them, create `new:<kebab-slug>` — don't force it.\n\n| id | scope |\n|----|-------|\n" + rows)


def main(run_id, method):
    cfg, root = config.load(), config.root()
    out_rel = cfg["out"]
    stack = "\n\n".join(STACK[e["adapter"]].format(main=e.get("main", ""), root=e.get("root", "."))
                        for e in cfg["entry"]) or "No adapter configured — see flowmap.toml."
    output = f"{out_rel}/runs/{run_id}.json"
    fill = {
        "ROOT": str(root), "RUN_ID": run_id, "METHOD": method, "OUTPUT": output, "OUT": out_rel,
        "VOCABULARY": vocabulary_text(cfg["flows"]["vocabulary"]), "METHOD_TEXT": METHODS[method],
        "STACK": stack, "VERIFY": f"cd {root} && python3 {TOOLS / 'verify.py'} {output}",
    }
    text = (TOOLS / "RUN_SPEC.md").read_text().split("\n", 3)[3]  # drop the template note
    text = "# Flow map run — brief for one independent mapping pass\n" + text
    for k, v in fill.items():
        text = text.replace("{{" + k + "}}", v)
    path = config.out() / "runs" / f"{run_id}.brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(path)


if __name__ == "__main__":
    main(*sys.argv[1:3])
