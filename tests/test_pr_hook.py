"""The Claude Code PR hook, run as Claude Code runs it: hook JSON on stdin, a fake `gh` on PATH."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO, cli_app, commit, fixture_repo, git

HOOK = REPO / "bin" / "flowmap-pr-hook"
FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GH_LOG"], "a") as f:
    f.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "view"]:
    if not os.environ.get("FAKE_PR"):
        sys.exit(1)
    print(os.environ["FAKE_PR"])
elif args[:1] == ["api"] and "--jq" in args:
    print(os.environ.get("FAKE_COMMENT_IDS", ""))
elif args[:2] == ["pr", "comment"] or "PATCH" in args:
    print("https://github.com/acme/app/pull/7#issuecomment-1")
'''


class PrHookTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name)
        (self.bin / "gh").write_text(FAKE_GH)
        (self.bin / "gh").chmod(0o755)
        self.log = self.bin / "gh.log"
        self.log.write_text("")

    def repo(self, files=None):
        root, base = fixture_repo(self, files or cli_app())
        git(root, "update-ref", "refs/remotes/origin/main", base)
        commit(root, {"tool/helpers.py": "def shout(s):\n    return s.upper() + '!'\n"})
        return root

    def run_hook(self, *args, stdin="", pr=None, ids="", cwd=None):
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log),
               "FAKE_PR": json.dumps(pr) if pr else "", "FAKE_COMMENT_IDS": ids}
        env.pop("FLOWMAP_ROOT", None)
        r = subprocess.run([sys.executable, str(HOOK), *args], input=stdin, cwd=cwd, env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def push(self, root, command="git push", **kw):
        event = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(root),
                 "tool_input": {"command": command}, "tool_response": {}}
        return self.run_hook(stdin=json.dumps(event), cwd=root, **kw)

    PR = {"number": 7, "url": "https://github.com/acme/app/pull/7", "baseRefName": "main"}

    def test_unrelated_command_does_nothing(self):
        root = self.repo()
        self.assertEqual(self.push(root, "ls -la", pr=self.PR), "")
        self.assertEqual(self.log.read_text(), "")  # did not even ask GitHub

    def test_push_without_a_pr_does_nothing(self):
        self.assertEqual(self.push(self.repo()), "")

    def test_repo_without_a_map_does_nothing(self):
        files = cli_app()
        del files["docs/flowmap/map.json"]
        self.assertEqual(self.push(self.repo(files), pr=self.PR), "")

    def test_push_to_a_pr_hands_the_lens_to_claude(self):
        out = json.loads(self.push(self.repo(), "git push -u origin feature", pr=self.PR))
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("PR #7", ctx)
        self.assertIn("# Flow lens:", ctx)
        self.assertIn("tool/helpers.py:shout", ctx)
        self.assertIn(f"{HOOK} post 7 ", ctx)
        self.assertIn("PR #7", out["systemMessage"])

    def test_mentioning_a_push_is_not_a_push(self):
        root = self.repo()
        for command in ('echo "remember to git push"',
                        "cat > s.json <<'EOF'\n{\"if\": \"Bash(git push*)\"}\nEOF\njq . s.json",
                        'git commit -m "then git push it"'):
            with self.subTest(command=command):
                self.assertEqual(self.push(root, command, pr=self.PR), "")

    def test_push_inside_a_compound_command_counts(self):
        for command in ("cd sub && git push -q", "git -C . push", "make test; git push origin HEAD",
                        "git -c push.default=current push", "GIT_TRACE=1 git push"):
            with self.subTest(command=command):
                self.assertIn("additionalContext", self.push(self.repo(), command, pr=self.PR))

    def test_two_hooks_firing_at_once_run_lens_once(self):
        root = self.repo()
        event = json.dumps({"tool_name": "Bash", "cwd": str(root), "tool_input": {"command": "git push"}})
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}", "FAKE_GH_LOG": str(self.log),
               "FAKE_PR": json.dumps(self.PR)}
        procs = [subprocess.Popen([sys.executable, str(HOOK)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  cwd=root, env=env, text=True) for _ in range(2)]
        for p in procs:  # both get their input before either is read: they really overlap
            p.stdin.write(event)
            p.stdin.close()
        outs = [p.stdout.read() for p in procs]
        for p in procs:
            p.wait()
            p.stdout.close()
        self.assertEqual(sorted(bool(o) for o in outs), [False, True])

    def test_pr_create_triggers_too(self):
        out = self.push(self.repo(), 'gh pr create --base main --title "x" --body "y"', pr=self.PR)
        self.assertIn("additionalContext", out)

    def test_same_head_twice_runs_once(self):
        root = self.repo()
        self.assertNotEqual(self.push(root, pr=self.PR), "")
        self.assertEqual(self.push(root, pr=self.PR), "")
        commit(root, {"tool/helpers.py": "def shout(s):\n    return s.lower()\n"})
        self.assertNotEqual(self.push(root, pr=self.PR), "")

    def test_post_creates_the_comment_once_then_edits_it(self):
        root = self.repo()
        body = root / "summary.md"
        body.write_text("## lands on x\n")
        self.run_hook("post", "7", str(body), cwd=root)
        created = [json.loads(line) for line in self.log.read_text().splitlines()][-1]
        self.assertEqual(created[:3], ["pr", "comment", "7"])
        self.log.write_text("")
        self.run_hook("post", "7", str(body), ids="99", cwd=root)
        edited = [json.loads(line) for line in self.log.read_text().splitlines()][-1]
        self.assertIn("repos/{owner}/{repo}/issues/comments/99", edited)
        self.assertIn("PATCH", edited)
