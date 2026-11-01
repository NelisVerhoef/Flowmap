# build-the-map

_Map a repo as flows -> steps -> code by agreement: list its entry points, hand briefs to independent passes, check their citations, and vote them into one map a human settles._

[← system map](./README.md) · generated, do not hand-edit

Steps in the order a user meets them. Colour = evidence (dark green confirmed/tested → light green agreed → amber contested → red single-source). Each box lists the endpoints the step calls.

```mermaid
flowchart TD
    nbuild_the_map_list_entry_points_1["<b>1. Maintainer lists every entry point the repo exposes into inventory.js…</b><br/><i>user · agreed · busy 9</i><br/><code>CLI flowmap inventory</code>"]
    class nbuild_the_map_list_entry_points_1 agreed
    nbuild_the_map_check_handlers_are_nodes_2["<b>2. Maintainer checks that every entry point's handler is a call-graph no…</b><br/><i>user · agreed · busy 9</i><br/><code>CLI flowmap callgraph</code>"]
    class nbuild_the_map_check_handlers_are_nodes_2 agreed
    nbuild_the_map_list_entry_points_1 --> nbuild_the_map_check_handlers_are_nodes_2
    nbuild_the_map_write_pass_briefs_3["<b>3. Maintainer writes one brief per independent mapping pass (bottom-up o…</b><br/><i>user · agreed · busy 5</i><br/><code>CLI flowmap brief</code>"]
    class nbuild_the_map_write_pass_briefs_3 agreed
    nbuild_the_map_check_handlers_are_nodes_2 --> nbuild_the_map_write_pass_briefs_3
    nbuild_the_map_verify_pass_4["<b>4. Agent running a pass checks that every cited anchor exists and every …</b><br/><i>user · agreed · busy 5</i><br/><code>CLI flowmap verify</code>"]
    class nbuild_the_map_verify_pass_4 agreed
    nbuild_the_map_write_pass_briefs_3 --> nbuild_the_map_verify_pass_4
    nbuild_the_map_reconcile_passes_5["<b>5. Maintainer votes the passes into one map with evidence levels and a l…</b><br/><i>user · agreed · busy 9</i><br/><code>CLI flowmap reconcile</code>"]
    class nbuild_the_map_reconcile_passes_5 agreed
    nbuild_the_map_verify_pass_4 --> nbuild_the_map_reconcile_passes_5
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

### 1. Maintainer lists every entry point the repo exposes into inventory.json

`agreed` · actor user · `CLI flowmap inventory`
· writes `docs/flowmap/inventory.json`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["inventory.py"]
        nflowmap_inventory_py___main__["__main__"]
    end
    class nflowmap_inventory_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 2. Maintainer checks that every entry point's handler is a call-graph node

`agreed` · actor user · `CLI flowmap callgraph`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["callgraph.py"]
        nflowmap_callgraph_py___main__["__main__"]
        nflowmap_callgraph_py_classify["classify"]
        nflowmap_callgraph_py_impact["impact"]
        nflowmap_callgraph_py_endpoint_flows["endpoint_flows"]
    end
    nflowmap_callgraph_py___main__ --> nflowmap_callgraph_py_classify
    nflowmap_callgraph_py___main__ --> nflowmap_callgraph_py_impact
    nflowmap_callgraph_py_impact --> nflowmap_callgraph_py_endpoint_flows
    class nflowmap_callgraph_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 3. Maintainer writes one brief per independent mapping pass (bottom-up or top-down)

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

### 4. Agent running a pass checks that every cited anchor exists and every entry point is placed

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

### 5. Maintainer votes the passes into one map with evidence levels and a list of open questions

`agreed` · actor user · `CLI flowmap reconcile`
· writes `docs/flowmap/MAP.md`, `docs/flowmap/QUESTIONS.md`, `docs/flowmap/map.json`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["reconcile.py"]
        nflowmap_reconcile_py___main__["__main__"]
        nflowmap_reconcile_py_main["main"]
        nflowmap_reconcile_py_UnionFind_find["UnionFind.find"]
        nflowmap_reconcile_py_UnionFind_groups["UnionFind.groups"]
        nflowmap_reconcile_py_UnionFind_union["UnionFind.union"]
        nflowmap_reconcile_py_canonical_new_flows["canonical_new_flows"]
        nflowmap_reconcile_py_jaccard["jaccard"]
        nflowmap_reconcile_py_tested_endpoints["tested_endpoints"]
        nflowmap_reconcile_py_write_map_md["write_map_md"]
        nflowmap_reconcile_py_write_questions_md["write_questions_md"]
        nflowmap_reconcile_py_adopted_flows["adopted_flows"]
        nflowmap_reconcile_py_path_regex["path_regex"]
    end
    nflowmap_reconcile_py___main__ --> nflowmap_reconcile_py_main
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_UnionFind_find
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_UnionFind_groups
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_UnionFind_union
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_canonical_new_flows
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_jaccard
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_tested_endpoints
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_write_map_md
    nflowmap_reconcile_py_main --> nflowmap_reconcile_py_write_questions_md
    nflowmap_reconcile_py_UnionFind_groups --> nflowmap_reconcile_py_UnionFind_find
    nflowmap_reconcile_py_UnionFind_union --> nflowmap_reconcile_py_UnionFind_find
    nflowmap_reconcile_py_canonical_new_flows --> nflowmap_reconcile_py_UnionFind_find
    nflowmap_reconcile_py_canonical_new_flows --> nflowmap_reconcile_py_UnionFind_groups
    nflowmap_reconcile_py_canonical_new_flows --> nflowmap_reconcile_py_UnionFind_union
    nflowmap_reconcile_py_canonical_new_flows --> nflowmap_reconcile_py_adopted_flows
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

