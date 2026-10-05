# flowmap bench: does it tell a reviewer the truth about a change?

The claim under test is not "flowmap finds bugs". It is: **a reviewer can trust what flowmap says
about which existing flows a change reaches, and it says so when it can't see.** A tool that
gives comfort has to be right when it is quiet. So the bench plants changes with known effects
in a real app and checks flowmap's output against independent ground truth.

## Ground truth, three ways

| layer | stands in for | how |
|---|---|---|
| the repo's own tests | CI | run on a fresh database migrated at the branch |
| holdout invariants | production | `fastapi-template/holdout/`: auth, ownership, contracts and existing-user checks, run against a database **seeded at main with raw SQL** (existing users with argon2 hashes, an item with a 200-char title, …) and then migrated to the branch |
| deploy replay | the deploy | `alembic upgrade head` on that populated database |

Plus **runtime reach** (`runtime_reach.py`): a pytest plugin using `sys.monitoring` that records
which app functions each endpoint actually executes on main, independent of flowmap's static
call graph. And the **answer key** (`fastapi-template/answer_key.json`): what each planted
change really does, which existing endpoints it affects, and the verdict an honest tool should
give. flowmap never sees the key; branches carry only a plausible commit message.

## What is scored

- **lens today**: what `flowmap lens main <branch>` reports now. *Quiet* (nothing about existing
  code) on a change that breaks production is false comfort.
- **verdict**: contained / spreads / blind, as `flowmap lens --json` reports it (the bench
  prototyped it; lens now ships it). *Blind* whenever the change includes something the call graph cannot
  see: module-level code, class bodies, migrations, non-Python files, vanished entry points.
- **endpoint recall**: of the existing endpoints a change affects, how many flowmap flags
  (static reach of modified code + base→head reach diff + removed endpoints).
- **LLM review** (`fastapi-template/llm/`): the pr-lens skill run blind on the subtlest
  changes, ending in a merge verdict.

## Reproduce

```bash
# the app: fastapi/full-stack-fastapi-template, Python 3.14, Postgres on :5432 (password changethis)
cd full-stack-fastapi-template && uv sync
# map it (flowmap.toml: fastapi adapter on backend/app/api/main.py), commit on main, then:
python3 bench/fastapi-template/plant.py <repo>      # branches pr-01 .. pr-26
python3 bench/fastapi-template/run.py <repo>        # deploy + holdout + CI + lens per branch
python3 bench/fastapi-template/relens.py <repo> v1-py314 <repo>/.venv/bin/python   # lens per branch
python3 bench/fastapi-template/score.py <repo>      # -> bench/fastapi-template/RESULTS.md
```
