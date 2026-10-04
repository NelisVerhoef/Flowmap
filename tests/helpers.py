"""Run flowmap as a user would (a subprocess per command, FLOWMAP_ROOT set) against this repo
or a throwaway fixture repo. Subprocesses because config caches the repo root per process."""

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FLOWMAP = REPO / "bin" / "flowmap"


def flowmap(*args, root=REPO):
    env = {**os.environ, "FLOWMAP_ROOT": str(root)}
    r = subprocess.run([sys.executable, str(FLOWMAP), *args], cwd=root, env=env, capture_output=True, text=True)
    if r.returncode:
        raise AssertionError(f"flowmap {' '.join(args)} exited {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=flowmap", "-c", "user.email=flowmap@example.com", *args],
                          cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def commit(root, files, message="change"):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text).lstrip())
    git(root, "add", "-A")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def fixture_repo(test, files):
    """A git repo holding `files`, deleted when the test ends. Returns (root, sha of that commit)."""
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name).resolve()  # macOS: /var -> /private/var, as config.root() resolves it
    git(root, "init", "-q")
    return root, commit(root, files, "base")


def cli_app(code='python = ["tool"]', extra=""):
    """A two-file Python CLI: `tool run` calls helpers.shout. `code` is the [code] body;
    `extra` is more TOML placed before [code] (another [[entry]], say)."""
    return {
        "flowmap.toml": f'[[entry]]\nadapter = "cli"\nprog = "tool"\ncommands = "tool"\n{extra}\n[code]\n{code}\n',
        "tool/run.py": '''
            from helpers import shout


            def main():
                print(shout("hi"))


            if __name__ == "__main__":
                main()
        ''',
        "tool/helpers.py": '''
            def shout(s):
                return s.upper()
        ''',
        "docs/flowmap/map.json": '{"flows": [], "runs": []}\n',
    }
