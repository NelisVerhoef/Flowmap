# review-a-change

_Turn a PR into a change page: chapters anchored to the map saying where it sits, what it changes, why, and what to ask, backed by facts and linkable from the PR body._

[← system map](./README.md) · generated, do not hand-edit

Steps in the order a user meets them. Colour = evidence (dark green confirmed/tested → light green agreed → amber contested → red single-source). Each box lists the endpoints the step calls.

```mermaid
flowchart TD
    nreview_a_change_run_lens_1["<b>1. Reviewer runs lens on base..head to get the verdict, touched steps, r…</b><br/><i>user · agreed · busy 13</i><br/><code>CLI flowmap lens</code>"]
    class nreview_a_change_run_lens_1 agreed
    nreview_a_change_pull_change_facts_2["<b>2. Author pulls the change's deterministic facts as JSON to write the st…</b><br/><i>user · agreed · busy 12</i><br/><code>CLI flowmap change</code>"]
    class nreview_a_change_pull_change_facts_2 agreed
    nreview_a_change_run_lens_1 --> nreview_a_change_pull_change_facts_2
    nreview_a_change_build_viewer_3["<b>3. Maintainer builds the empty hosted viewer page to deploy on a static …</b><br/><i>admin · agreed · busy 3</i><br/><code>CLI flowmap viewer</code>"]
    class nreview_a_change_build_viewer_3 agreed
    nreview_a_change_pull_change_facts_2 --> nreview_a_change_build_viewer_3
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

## Code flow per step

Call graph from the step's endpoint handler(s) (dark), grouped by file, depth ≤ 4, plumbing hidden. More boxes and files = a busier step.

### 1. Reviewer runs lens on base..head to get the verdict, touched steps, reach and blind spots

`agreed` · actor user · `CLI flowmap lens`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["lens.py"]
        nflowmap_lens_py___main__["__main__"]
        nflowmap_lens_py_main["main"]
    end
    nflowmap_lens_py___main__ --> nflowmap_lens_py_main
    class nflowmap_lens_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 2. Author pulls the change's deterministic facts as JSON to write the story from

`agreed` · actor user · `CLI flowmap change`
· writes `docs/flowmap/changes/<name>.html`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["change.py"]
        nflowmap_change_py___main__["__main__"]
        nflowmap_change_py_main["main"]
        nflowmap_change_py_facts["facts"]
        nflowmap_change_py_fitted_link["fitted_link"]
        nflowmap_change_py_merge["merge"]
        nflowmap_change_py_facts_causes["facts.causes"]
        nflowmap_change_py_facts_module["facts.module"]
        nflowmap_change_py_facts_node_for["facts.node_for"]
        nflowmap_change_py_file_kind["file_kind"]
        nflowmap_change_py_hunk_lines["hunk_lines"]
        nflowmap_change_py_hunks["hunks"]
        nflowmap_change_py_opens_class["opens_class"]
        nflowmap_change_py_signature["signature"]
        nflowmap_change_py_link["link"]
        nflowmap_change_py_auto_chapters["auto_chapters"]
        nflowmap_change_py_lint_story["lint_story"]
        nflowmap_change_py_facts_causes_below["facts.causes.below"]
        nflowmap_change_py_cite_in_diff["cite_in_diff"]
        nflowmap_change_py_problem["problem"]
    end
    subgraph f1["callgraph.py"]
        nflowmap_callgraph_py_Graph_reaches["Graph.reaches"]
    end
    nflowmap_change_py___main__ --> nflowmap_change_py_main
    nflowmap_change_py_main --> nflowmap_change_py_facts
    nflowmap_change_py_main --> nflowmap_change_py_fitted_link
    nflowmap_change_py_main --> nflowmap_change_py_merge
    nflowmap_change_py_facts --> nflowmap_callgraph_py_Graph_reaches
    nflowmap_change_py_facts --> nflowmap_change_py_facts_causes
    nflowmap_change_py_facts --> nflowmap_change_py_facts_module
    nflowmap_change_py_facts --> nflowmap_change_py_facts_node_for
    nflowmap_change_py_facts --> nflowmap_change_py_file_kind
    nflowmap_change_py_facts --> nflowmap_change_py_hunk_lines
    nflowmap_change_py_facts --> nflowmap_change_py_hunks
    nflowmap_change_py_facts --> nflowmap_change_py_opens_class
    nflowmap_change_py_facts --> nflowmap_change_py_signature
    nflowmap_change_py_fitted_link --> nflowmap_change_py_link
    nflowmap_change_py_merge --> nflowmap_change_py_auto_chapters
    nflowmap_change_py_merge --> nflowmap_change_py_lint_story
    nflowmap_change_py_facts_causes --> nflowmap_change_py_facts_causes_below
    nflowmap_change_py_lint_story --> nflowmap_change_py_cite_in_diff
    nflowmap_change_py_lint_story --> nflowmap_change_py_problem
    nflowmap_change_py_cite_in_diff --> nflowmap_change_py_hunk_lines
    class nflowmap_change_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 3. Maintainer builds the empty hosted viewer page to deploy on a static host

`agreed` · actor admin · `CLI flowmap viewer`
· writes `<dir>/change.html`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["viewer.py"]
        nflowmap_viewer_py___main__["__main__"]
        nflowmap_viewer_py_main["main"]
    end
    subgraph f1["change.py"]
        nflowmap_change_py_viewer_html["viewer_html"]
    end
    nflowmap_viewer_py___main__ --> nflowmap_viewer_py_main
    nflowmap_viewer_py_main --> nflowmap_change_py_viewer_html
    class nflowmap_viewer_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

