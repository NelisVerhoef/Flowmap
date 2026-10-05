# flowmap

Every PR carries its flowmap, before it is opened:

- Commit `docs/flowmap/changes/pr-<n>.story.json` and the page `flowmap change <base> <head> --name pr-<n>`
  renders from it (`docs/flowmap/changes/pr-<n>.html`). Follow "The change page" in `skills/pr-lens/SKILL.md`.
- Write the PR body in the pr-lens output format, and link the rendered change page with the link
  `flowmap change <base> <head> --name pr-<n> --link` prints (`https://flowmap.testabl.ai/v1/change.html#v1.…`;
  the page rides in the fragment, so nothing is published). GitHub itself shows committed HTML as source.
