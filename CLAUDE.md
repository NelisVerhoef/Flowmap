# flowmap

Every PR carries its flowmap, before it is opened:

- Commit `docs/flowmap/changes/pr-<n>.story.json` and the page `flowmap change <base> <head> --name pr-<n>`
  renders from it (`docs/flowmap/changes/pr-<n>.html`). Follow "The change page" in `skills/pr-lens/SKILL.md`.
- Write the PR body in the pr-lens output format, and link the rendered change page:
  `https://nelisverhoef.github.io/Flowmap/changes/pr-<n>.html` (published by
  `.github/workflows/flowmap-pages.yml`; GitHub itself shows committed HTML as source).
