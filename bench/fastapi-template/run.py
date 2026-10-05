"""Run the bench: for main and every planted branch, record what CI, production and flowmap see.

Per branch:
  deploy  — a database migrated and seeded at main (existing users, existing items) is
            migrated to the branch, as a deploy would. Did the migration succeed?
  holdout — the holdout invariants run against that database with the branch's code.
  ci      — the repo's own tests run on a fresh database migrated at the branch.
  lens    — `flowmap lens main <branch> --json` (relens.py re-runs only this, per flowmap version and
            Python, into results/lens-<label>/; score.py reads those).
On main, both suites also run under the runtime-reach recorder (ground truth for reach).

    python run.py /path/to/full-stack-fastapi-template [pr-01 pr-02 ...]
"""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOWMAP = HERE.parent.parent / "bin" / "flowmap"
UV = os.environ.get("UV", "uv")
OUT = HERE / "results"


def sh(cmd, cwd, env=None, check=False):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"{cmd} failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}")
    return r


def dotenv(repo):
    env = {}
    for line in (Path(repo) / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return env


def make_env(repo, db, **extra):
    env = {**os.environ, **dotenv(repo), "FASTAPI_ENV": "development",
           "DATABASE_URL": f"postgresql://postgres:changethis@localhost:5432/{db}", **extra}
    env.pop("VIRTUAL_ENV", None)
    return env


def reset_db(name):
    for q in (f"DROP DATABASE IF EXISTS {name} WITH (FORCE)", f"CREATE DATABASE {name}"):
        sh(["psql", "-q", "-h", "localhost", "-U", "postgres", "-c", q], cwd="/", check=True)


def junit_failures(path):
    failed = []
    for case in ET.parse(path).iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            mod = case.get("classname", "").replace(".", "/")
            failed.append(f"{mod}.py::{case.get('name')}")
    return failed


def run_one(repo, ref, scratch):
    backend = Path(repo) / "backend"
    git = lambda *a: sh(["git", *a], cwd=repo, check=True)  # noqa: E731
    is_base = ref == "main"
    trace = {"PYTHONPATH": str(HERE.parent), "REACH_APP": "backend/app"}
    res = {"ref": ref}

    # deploy onto existing data, then the holdout invariants against it
    git("checkout", "-q", "main")
    reset_db("app_prod")
    prod = make_env(repo, "app_prod")
    sh([UV, "run", "--frozen", "alembic", "upgrade", "head"], backend, prod, check=True)
    sh([UV, "run", "--frozen", "python", str(HERE / "seed.py")], backend, prod, check=True)
    git("checkout", "-q", ref)
    up = sh([UV, "run", "--frozen", "alembic", "upgrade", "head"], backend, prod)
    res["deploy"] = {"ok": up.returncode == 0, "log": (up.stderr or up.stdout)[-600:] if up.returncode else ""}
    hold = scratch / f"{ref}.holdout.json"
    extra = {"HOLDOUT_OUT": str(hold), **(trace | {"REACH_OUT": str(scratch / "reach.holdout.json")} if is_base else {})}
    cmd = [UV, "run", "--frozen", "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-W", "ignore",
           str(HERE / "holdout"), "--rootdir", str(HERE / "holdout")] + (["-p", "runtime_reach"] if is_base else [])
    sh(cmd, backend, make_env(repo, "app_prod", **extra))
    res["holdout"] = json.loads(hold.read_text()) if hold.exists() else {"_error": "holdout did not run"}

    # CI: the repo's own tests on a fresh database at the branch
    reset_db("app_test")
    ci_env = make_env(repo, "app_test", **(trace | {"REACH_OUT": str(scratch / "reach.ci.json")} if is_base else {}))
    mig = sh([UV, "run", "--frozen", "alembic", "upgrade", "head"], backend, ci_env)
    xml = scratch / f"{ref}.junit.xml"
    xml.unlink(missing_ok=True)
    cmd = [UV, "run", "--frozen", "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-W", "ignore",
           "tests/", f"--junitxml={xml}"] + (["-p", "runtime_reach"] if is_base else [])
    t = sh(cmd, backend, ci_env)
    res["ci"] = {"migrate_ok": mig.returncode == 0, "failed": junit_failures(xml) if xml.exists() else ["_did_not_run"],
                 "summary": t.stdout.strip().splitlines()[-1] if t.stdout.strip() else t.stderr[-300:]}

    git("checkout", "-q", "main")
    prev = OUT / f"{ref}.json"
    if not is_base and os.environ.get("BENCH_KEEP_LENS") and prev.exists():
        res["lens"] = json.loads(prev.read_text()).get("lens", {})   # keep the lens result recorded earlier
    elif not is_base:
        lens = sh([sys.executable, str(FLOWMAP), "lens", "main", ref, "--json"], repo)
        res["lens"] = json.loads(lens.stdout) if lens.returncode == 0 else {"_error": lens.stderr[-2000:]}
        md = sh([sys.executable, str(FLOWMAP), "lens", "main", ref], repo)
        (OUT / f"{ref}.lens.md").write_text(md.stdout if md.returncode == 0 else md.stderr)
    else:
        reach = {"endpoints": {}, "tests": {}}
        for part in ("holdout", "ci"):
            f = scratch / f"reach.{part}.json"
            if f.exists():
                d = json.loads(f.read_text())
                for k, v in d["endpoints"].items():
                    reach["endpoints"][k] = sorted(set(reach["endpoints"].get(k, [])) | set(v))
                reach["tests"].update(d["tests"])
        (OUT / "runtime_reach.json").write_text(json.dumps(reach, indent=1))
    (OUT / f"{ref}.json").write_text(json.dumps(res, indent=1))
    ci_n, hold_n = len(res["ci"]["failed"]), sum(v.get("outcome") == "failed" for v in res["holdout"].values()
                                                 if isinstance(v, dict))
    print(f"{ref}: deploy {'ok' if res['deploy']['ok'] else 'FAILED'} · holdout failures {hold_n} · "
          f"ci failures {ci_n}", flush=True)


def main(repo, refs):
    OUT.mkdir(exist_ok=True)
    scratch = Path(os.environ.get("BENCH_SCRATCH", "/tmp/flowmap-bench"))
    scratch.mkdir(parents=True, exist_ok=True)
    if not refs:
        branches = sh(["git", "branch", "--format=%(refname:short)"], cwd=repo, check=True).stdout.split()
        refs = ["main"] + sorted(b for b in branches if b.startswith("pr-"))
    for ref in refs:
        run_one(repo, ref, scratch)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
