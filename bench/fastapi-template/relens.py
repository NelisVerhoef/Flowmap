"""Re-run only `flowmap lens --json` for every branch, under a given Python, into results/lens-<label>/.

The deploy/holdout/CI results don't depend on flowmap, so a flowmap change only needs this.

    python relens.py /path/to/repo <label> [<python>]    # e.g. py311 /usr/bin/python3.11
    FLOWMAP_BIN=/old/checkout/bin/flowmap python relens.py ...  # score an older flowmap
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOWMAP = Path(os.environ.get("FLOWMAP_BIN", HERE.parent.parent / "bin" / "flowmap"))


def main(repo, label, python=sys.executable):
    out = HERE / "results" / f"lens-{label}"
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "FLOWMAP_REEXEC": "1"}   # run under exactly this Python
    branches = subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=repo, check=True,
                              capture_output=True, text=True).stdout.split()
    for ref in sorted(b for b in branches if b.startswith("pr-")):
        r = subprocess.run([python, str(FLOWMAP), "lens", "main", ref, "--json"], cwd=repo, env=env,
                           capture_output=True, text=True)
        facts = json.loads(r.stdout) if r.returncode == 0 else {"_error": r.stderr[-2000:]}
        (out / f"{ref}.json").write_text(json.dumps(facts, indent=1))
        md = subprocess.run([python, str(FLOWMAP), "lens", "main", ref], cwd=repo, env=env, capture_output=True, text=True)
        (out / f"{ref}.md").write_text(md.stdout if md.returncode == 0 else md.stderr)
        print(ref, facts.get("verdict", "ERROR"), len(facts.get("spreads_to", [])), flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
