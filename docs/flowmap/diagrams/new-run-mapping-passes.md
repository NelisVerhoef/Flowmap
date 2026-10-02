# new:run-mapping-passes

_Turn a repo into a first flow map: list its entry points, brief independent mapping passes, check each pass, and vote them into one map._

[← system map](./README.md) · generated, do not hand-edit

Steps in the order a user meets them. Colour = evidence (dark green confirmed/tested → light green agreed → amber contested → red single-source). Each box lists the endpoints the step calls.

```mermaid
flowchart TD
    nnew_run_mapping_passes_write_pass_brief_1["<b>1. Maintainer writes one brief per independent pass (run id + bottom-up/…</b><br/><i>user · agreed · busy 5</i><br/><code>CLI flowmap brief</code>"]
    class nnew_run_mapping_passes_write_pass_brief_1 agreed
    nnew_run_mapping_passes_reconcile_runs_2["<b>2. Maintainer votes the passes into one map with evidence levels and a l…</b><br/><i>user · agreed · busy 10</i><br/><code>CLI flowmap reconcile</code>"]
    class nnew_run_mapping_passes_reconcile_runs_2 agreed
    nnew_run_mapping_passes_write_pass_brief_1 --> nnew_run_mapping_passes_reconcile_runs_2
    nnew_run_mapping_passes_verify_pass_citations_3["<b>3. Maintainer checks each pass's anchors exist and every entry point is …</b><br/><i>user · agreed · busy 6</i><br/><code>CLI flowmap verify</code>"]
    class nnew_run_mapping_passes_verify_pass_citations_3 agreed
    nnew_run_mapping_passes_reconcile_runs_2 --> nnew_run_mapping_passes_verify_pass_citations_3
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

### 1. Maintainer writes one brief per independent pass (run id + bottom-up/top-down method)

`agreed` · actor user · `CLI flowmap brief`
· writes `docs/flowmap/runs/<run-id>.brief.md`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["brief.py"]
        nflowmap_brief_py___main__["__main__"]
        nflowmap_brief_py_main["main"]
        nflowmap_brief_py_vocabulary_text["vocabulary_text"]
    end
    nflowmap_brief_py___main__ --> nflowmap_brief_py_main
    nflowmap_brief_py_main --> nflowmap_brief_py_vocabulary_text
    class nflowmap_brief_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 2. Maintainer votes the passes into one map with evidence levels and a list of open questions

`agreed` · actor user · `CLI flowmap reconcile`
· writes `docs/flowmap/MAP.md`, `docs/flowmap/QUESTIONS.md`, `docs/flowmap/map.json`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["reconcile.py"]
        nflowmap_reconcile_py___main__["__main__"]
        nflowmap_reconcile_py_main["main"]
        nflowmap_reconcile_py_canonical_new_flows["canonical_new_flows"]
        nflowmap_reconcile_py_jaccard["jaccard"]
        nflowmap_reconcile_py_tested_endpoints["tested_endpoints"]
        nflowmap_reconcile_py_write_map_md["write_map_md"]
        nflowmap_reconcile_py_write_questions_md["write_questions_md"]
        nflowmap_reconcile_py_path_regex["path_regex"]
    end
    nflowmap_reconcile_py___main__ --> nflowmap_reconcile_py_main
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_canonical_new_flows
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_jaccard
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_tested_endpoints
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_write_map_md
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_write_questions_md
    nflowmap_reconcile_py_canonical_new_flows --> nflowmap_reconcile_py_jaccard
    nflowmap_reconcile_py_tested_endpoints --> nflowmap_reconcile_py_path_regex
    class nflowmap_reconcile_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 3. Maintainer checks each pass's anchors exist and every entry point is placed

`agreed` · actor user · `CLI flowmap verify`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["verify.py"]
        nflowmap_verify_py___main__["__main__"]
        nflowmap_verify_py_verify["verify"]
        nflowmap_verify_py_anchor_ok["anchor_ok"]
        nflowmap_verify_py_endpoints_in["endpoints_in"]
        nflowmap_verify_py__text["_text"]
    end
    nflowmap_verify_py___main__ --> nflowmap_verify_py_verify
    nflowmap_verify_py_verify --> nflowmap_verify_py_anchor_ok
    nflowmap_verify_py_verify --> nflowmap_verify_py_endpoints_in
    nflowmap_verify_py_anchor_ok --> nflowmap_verify_py__text
    class nflowmap_verify_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

