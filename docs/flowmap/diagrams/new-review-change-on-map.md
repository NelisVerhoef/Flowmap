# new:review-change-on-map

_See the map: flows, their steps and the code each step runs, as Mermaid diagrams and an interactive atlas page._

[← system map](./README.md) · generated, do not hand-edit

Steps in the order a user meets them. Colour = evidence (dark green confirmed/tested → light green agreed → amber contested → red single-source). Each box lists the endpoints the step calls.

```mermaid
flowchart TD
    nnew_review_change_on_map_generate_diagrams_1["<b>1. Maintainer generates Mermaid diagrams at system, flow and step zoom</b><br/><i>user · agreed · busy 12</i><br/><code>CLI flowmap diagrams</code>"]
    class nnew_review_change_on_map_generate_diagrams_1 agreed
    nnew_review_change_on_map_lens_place_change_2["<b>2. Reviewer places a base..head diff on the map (steps touched, call-gra…</b><br/><i>user · agreed · busy 12</i><br/><code>CLI flowmap lens</code>"]
    class nnew_review_change_on_map_lens_place_change_2 agreed
    nnew_review_change_on_map_generate_diagrams_1 --> nnew_review_change_on_map_lens_place_change_2
    nnew_review_change_on_map_callgraph_impact_3["<b>3. Developer asks which entry points and flows can reach a file:symbol</b><br/><i>user · agreed · busy 8</i><br/><code>CLI flowmap callgraph</code>"]
    class nnew_review_change_on_map_callgraph_impact_3 agreed
    nnew_review_change_on_map_lens_place_change_2 --> nnew_review_change_on_map_callgraph_impact_3
    nnew_review_change_on_map_build_atlas_4["<b>4. Maintainer builds the interactive atlas page and browses flows, steps…</b><br/><i>user · agreed · busy 12</i><br/><code>CLI flowmap atlas</code>"]
    class nnew_review_change_on_map_build_atlas_4 agreed
    nnew_review_change_on_map_callgraph_impact_3 --> nnew_review_change_on_map_build_atlas_4
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

### 1. Maintainer generates Mermaid diagrams at system, flow and step zoom

`agreed` · actor user · `CLI flowmap diagrams`
· writes `docs/flowmap/diagrams/<flow>.md`, `docs/flowmap/diagrams/README.md`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["diagrams.py"]
        nflowmap_diagrams_py___main__["__main__"]
        nflowmap_diagrams_py_Diagrams_write["Diagrams.write"]
        nflowmap_diagrams_py_Diagrams_flow["Diagrams.flow"]
        nflowmap_diagrams_py_Diagrams_step["Diagrams.step"]
        nflowmap_diagrams_py_Diagrams_system["Diagrams.system"]
        nflowmap_diagrams_py_label["label"]
        nflowmap_diagrams_py_nid["nid"]
        nflowmap_diagrams_py_short["short"]
        nflowmap_diagrams_py_Diagrams__forward_avoiding["Diagrams._forward_avoiding"]
    end
    nflowmap_diagrams_py___main__ --> nflowmap_diagrams_py_Diagrams_write
    nflowmap_diagrams_py_Diagrams_write --> nflowmap_diagrams_py_Diagrams_flow
    nflowmap_diagrams_py_Diagrams_write --> nflowmap_diagrams_py_Diagrams_step
    nflowmap_diagrams_py_Diagrams_write --> nflowmap_diagrams_py_Diagrams_system
    nflowmap_diagrams_py_Diagrams_flow --> nflowmap_diagrams_py_label
    nflowmap_diagrams_py_Diagrams_flow --> nflowmap_diagrams_py_nid
    nflowmap_diagrams_py_Diagrams_step --> nflowmap_diagrams_py_label
    nflowmap_diagrams_py_Diagrams_step --> nflowmap_diagrams_py_nid
    nflowmap_diagrams_py_Diagrams_step --> nflowmap_diagrams_py_short
    nflowmap_diagrams_py_Diagrams_system --> nflowmap_diagrams_py_Diagrams__forward_avoiding
    nflowmap_diagrams_py_Diagrams_system --> nflowmap_diagrams_py_label
    nflowmap_diagrams_py_Diagrams_system --> nflowmap_diagrams_py_nid
    class nflowmap_diagrams_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

### 2. Reviewer places a base..head diff on the map (steps touched, call-graph reach, off-map code)

`agreed` · actor user · `CLI flowmap lens`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["lens.py"]
        nflowmap_lens_py___main__["__main__"]
        nflowmap_lens_py_main["main"]
        nflowmap_lens_py_changed_lines["changed_lines"]
        nflowmap_lens_py_defs["defs"]
        nflowmap_lens_py_endpoint_set["endpoint_set"]
        nflowmap_lens_py_git["git"]
        nflowmap_lens_py_importers["importers"]
        nflowmap_lens_py_main_hits["main.hits"]
        nflowmap_lens_py_show["show"]
        nflowmap_lens_py_symbols_at["symbols_at"]
        nflowmap_lens_py_py_symbols["py_symbols"]
        nflowmap_lens_py_rb_symbols["rb_symbols"]
        nflowmap_lens_py_ts_symbols["ts_symbols"]
        nflowmap_lens_py_py_symbols_walk["py_symbols.walk"]
    end
    subgraph f1["config.py"]
        nflowmap_config_py_python_roots["python_roots"]
        nflowmap_config_py_module_name["module_name"]
    end
    subgraph f2["adapters/cli.py"]
        nflowmap_adapters_cli_py_main_guard["main_guard"]
    end
    nflowmap_lens_py___main__ --> nflowmap_lens_py_main
    nflowmap_lens_py_main --> nflowmap_config_py_python_roots
    nflowmap_lens_py_main --> nflowmap_lens_py_changed_lines
    nflowmap_lens_py_main --> nflowmap_lens_py_defs
    nflowmap_lens_py_main --> nflowmap_lens_py_endpoint_set
    nflowmap_lens_py_main --> nflowmap_lens_py_git
    nflowmap_lens_py_main --> nflowmap_lens_py_importers
    nflowmap_lens_py_main --> nflowmap_lens_py_main_hits
    nflowmap_lens_py_main --> nflowmap_lens_py_show
    nflowmap_lens_py_main --> nflowmap_lens_py_symbols_at
    nflowmap_lens_py_changed_lines --> nflowmap_lens_py_git
    nflowmap_lens_py_defs --> nflowmap_lens_py_py_symbols
    nflowmap_lens_py_defs --> nflowmap_lens_py_rb_symbols
    nflowmap_lens_py_defs --> nflowmap_lens_py_ts_symbols
    nflowmap_lens_py_endpoint_set --> nflowmap_lens_py_show
    nflowmap_lens_py_importers --> nflowmap_config_py_module_name
    nflowmap_lens_py_importers --> nflowmap_config_py_python_roots
    nflowmap_lens_py_importers --> nflowmap_lens_py_git
    nflowmap_lens_py_show --> nflowmap_lens_py_git
    nflowmap_lens_py_symbols_at --> nflowmap_lens_py_defs
    nflowmap_lens_py_py_symbols --> nflowmap_adapters_cli_py_main_guard
    nflowmap_lens_py_py_symbols --> nflowmap_lens_py_py_symbols_walk
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

### 3. Developer asks which entry points and flows can reach a file:symbol

`agreed` · actor user · `CLI flowmap callgraph`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["callgraph.py"]
        nflowmap_callgraph_py___main__["__main__"]
        nflowmap_callgraph_py_impact["impact"]
        nflowmap_callgraph_py_endpoint_flows["endpoint_flows"]
    end
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

### 4. Maintainer builds the interactive atlas page and browses flows, steps and components

`agreed` · actor user · `CLI flowmap atlas`
· writes `docs/flowmap/atlas.html`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["atlas.py"]
        nflowmap_atlas_py___main__["__main__"]
        nflowmap_atlas_py_build["build"]
        nflowmap_atlas_py_overlay["overlay"]
        nflowmap_atlas_py_split_votes["split_votes"]
        nflowmap_atlas_py_step_code["step_code"]
        nflowmap_atlas_py_step_keys["step_keys"]
    end
    subgraph f1["diagrams.py"]
        nflowmap_diagrams_py_Diagrams__forward_avoiding["Diagrams._forward_avoiding"]
        nflowmap_diagrams_py_Diagrams_system["Diagrams.system"]
        nflowmap_diagrams_py_short["short"]
        nflowmap_diagrams_py_label["label"]
        nflowmap_diagrams_py_nid["nid"]
    end
    subgraph f2["lens.py"]
        nflowmap_lens_py_git["git"]
        nflowmap_lens_py_changed_lines["changed_lines"]
        nflowmap_lens_py_defs["defs"]
        nflowmap_lens_py_endpoint_set["endpoint_set"]
        nflowmap_lens_py_show["show"]
        nflowmap_lens_py_symbols_at["symbols_at"]
        nflowmap_lens_py_py_symbols["py_symbols"]
        nflowmap_lens_py_rb_symbols["rb_symbols"]
        nflowmap_lens_py_ts_symbols["ts_symbols"]
    end
    subgraph f3["config.py"]
        nflowmap_config_py_python_roots["python_roots"]
    end
    nflowmap_atlas_py___main__ --> nflowmap_atlas_py_build
    nflowmap_atlas_py_build --> nflowmap_atlas_py_overlay
    nflowmap_atlas_py_build --> nflowmap_atlas_py_split_votes
    nflowmap_atlas_py_build --> nflowmap_atlas_py_step_code
    nflowmap_atlas_py_build --> nflowmap_atlas_py_step_keys
    nflowmap_atlas_py_build --> nflowmap_diagrams_py_Diagrams__forward_avoiding
    nflowmap_atlas_py_build --> nflowmap_diagrams_py_Diagrams_system
    nflowmap_atlas_py_build --> nflowmap_lens_py_git
    nflowmap_atlas_py_overlay --> nflowmap_atlas_py_step_keys
    nflowmap_atlas_py_overlay --> nflowmap_config_py_python_roots
    nflowmap_atlas_py_overlay --> nflowmap_diagrams_py_short
    nflowmap_atlas_py_overlay --> nflowmap_lens_py_changed_lines
    nflowmap_atlas_py_overlay --> nflowmap_lens_py_defs
    nflowmap_atlas_py_overlay --> nflowmap_lens_py_endpoint_set
    nflowmap_atlas_py_overlay --> nflowmap_lens_py_git
    nflowmap_atlas_py_overlay --> nflowmap_lens_py_show
    nflowmap_atlas_py_overlay --> nflowmap_lens_py_symbols_at
    nflowmap_atlas_py_step_code --> nflowmap_diagrams_py_short
    nflowmap_diagrams_py_Diagrams_system --> nflowmap_diagrams_py_Diagrams__forward_avoiding
    nflowmap_diagrams_py_Diagrams_system --> nflowmap_diagrams_py_label
    nflowmap_diagrams_py_Diagrams_system --> nflowmap_diagrams_py_nid
    nflowmap_lens_py_changed_lines --> nflowmap_lens_py_git
    nflowmap_lens_py_defs --> nflowmap_lens_py_py_symbols
    nflowmap_lens_py_defs --> nflowmap_lens_py_rb_symbols
    nflowmap_lens_py_defs --> nflowmap_lens_py_ts_symbols
    nflowmap_lens_py_endpoint_set --> nflowmap_lens_py_show
    nflowmap_lens_py_show --> nflowmap_lens_py_git
    nflowmap_lens_py_symbols_at --> nflowmap_lens_py_defs
    class nflowmap_atlas_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

