# browse-the-map

_See the settled map: Mermaid diagrams at system/flow/step zoom, the interactive atlas, and the left-to-right canvas of screens, steps, code and data._

[← system map](./README.md) · generated, do not hand-edit

Steps in the order a user meets them. Colour = evidence (dark green confirmed/tested → light green agreed → amber contested → red single-source). Each box lists the endpoints the step calls.

```mermaid
flowchart TD
    nbrowse_the_map_generate_diagrams_1["<b>1. Maintainer generates Mermaid diagrams of the map at system, flow and …</b><br/><i>user · agreed · busy 9</i><br/><code>CLI flowmap diagrams</code>"]
    class nbrowse_the_map_generate_diagrams_1 agreed
    nbrowse_the_map_build_atlas_2["<b>2. Maintainer builds the interactive atlas page and browses flows, steps…</b><br/><i>user · agreed · busy 10</i><br/><code>CLI flowmap atlas</code>"]
    class nbrowse_the_map_build_atlas_2 agreed
    nbrowse_the_map_generate_diagrams_1 --> nbrowse_the_map_build_atlas_2
    nbrowse_the_map_draw_canvas_3["<b>3. Maintainer draws the map as one left-to-right canvas, or redraws it f…</b><br/><i>user · agreed · busy 7</i><br/><code>CLI flowmap canvas</code>"]
    class nbrowse_the_map_draw_canvas_3 agreed
    nbrowse_the_map_build_atlas_2 --> nbrowse_the_map_draw_canvas_3
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

### 1. Maintainer generates Mermaid diagrams of the map at system, flow and step zoom

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
    end
    nflowmap_diagrams_py___main__ --> nflowmap_diagrams_py_Diagrams_write
    nflowmap_diagrams_py_Diagrams_write --> nflowmap_diagrams_py_Diagrams_flow
    nflowmap_diagrams_py_Diagrams_write --> nflowmap_diagrams_py_Diagrams_step
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

### 2. Maintainer builds the interactive atlas page and browses flows, steps, merges and code

`agreed` · actor user · `CLI flowmap atlas`
· writes `docs/flowmap/atlas.html`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["atlas.py"]
        nflowmap_atlas_py___main__["__main__"]
        nflowmap_atlas_py_build["build"]
        nflowmap_atlas_py_data["data"]
        nflowmap_atlas_py_functions["functions"]
        nflowmap_atlas_py_merges["merges"]
        nflowmap_atlas_py_overlay["overlay"]
        nflowmap_atlas_py_split_votes["split_votes"]
        nflowmap_atlas_py_step_code["step_code"]
    end
    subgraph f1["diagrams.py"]
        nflowmap_diagrams_py_Diagrams_component["Diagrams.component"]
    end
    subgraph f2["graphs/codegraph.py"]
        nflowmap_graphs_codegraph_py_doc["doc"]
    end
    subgraph f3["graphs/python.py"]
        nflowmap_graphs_python_py_doc["doc"]
    end
    nflowmap_atlas_py___main__ --> nflowmap_atlas_py_build
    nflowmap_atlas_py_build --> nflowmap_atlas_py_data
    nflowmap_atlas_py_data --> nflowmap_atlas_py_functions
    nflowmap_atlas_py_data --> nflowmap_atlas_py_merges
    nflowmap_atlas_py_data --> nflowmap_atlas_py_overlay
    nflowmap_atlas_py_data --> nflowmap_atlas_py_split_votes
    nflowmap_atlas_py_data --> nflowmap_atlas_py_step_code
    nflowmap_atlas_py_data --> nflowmap_diagrams_py_Diagrams_component
    nflowmap_atlas_py_functions --> nflowmap_graphs_codegraph_py_doc
    nflowmap_atlas_py_functions --> nflowmap_graphs_python_py_doc
    nflowmap_atlas_py_merges --> nflowmap_diagrams_py_Diagrams_component
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

### 3. Maintainer draws the map as one left-to-right canvas, or redraws it from an existing atlas page

`agreed` · actor user · `CLI flowmap canvas`
· writes `docs/flowmap/canvas.html`

<details><summary>code flow</summary>

```mermaid
flowchart LR
    subgraph f0["canvas.py"]
        nflowmap_canvas_py___main__["__main__"]
        nflowmap_canvas_py_main["main"]
        nflowmap_canvas_py_from_page["from_page"]
        nflowmap_canvas_py_graph["graph"]
        nflowmap_canvas_py_paint["paint"]
        nflowmap_canvas_py_data_label["data_label"]
        nflowmap_canvas_py_flow_title["flow_title"]
        nflowmap_canvas_py_graph_edge["graph.edge"]
        nflowmap_canvas_py_graph_walk["graph.walk"]
        nflowmap_canvas_py_screen_group["screen_group"]
        nflowmap_canvas_py_paint_file_of["paint.file_of"]
    end
    subgraph f1["atlas.py"]
        nflowmap_atlas_py_data["data"]
        nflowmap_atlas_py_functions["functions"]
        nflowmap_atlas_py_merges["merges"]
        nflowmap_atlas_py_overlay["overlay"]
        nflowmap_atlas_py_split_votes["split_votes"]
        nflowmap_atlas_py_step_code["step_code"]
    end
    subgraph f2["diagrams.py"]
        nflowmap_diagrams_py_Diagrams_component["Diagrams.component"]
    end
    subgraph f3["graphs/codegraph.py"]
        nflowmap_graphs_codegraph_py_doc["doc"]
    end
    subgraph f4["graphs/python.py"]
        nflowmap_graphs_python_py_doc["doc"]
    end
    nflowmap_canvas_py___main__ --> nflowmap_canvas_py_main
    nflowmap_canvas_py_main --> nflowmap_atlas_py_data
    nflowmap_canvas_py_main --> nflowmap_canvas_py_from_page
    nflowmap_canvas_py_main --> nflowmap_canvas_py_graph
    nflowmap_canvas_py_main --> nflowmap_canvas_py_paint
    nflowmap_atlas_py_data --> nflowmap_atlas_py_functions
    nflowmap_atlas_py_data --> nflowmap_atlas_py_merges
    nflowmap_atlas_py_data --> nflowmap_atlas_py_overlay
    nflowmap_atlas_py_data --> nflowmap_atlas_py_split_votes
    nflowmap_atlas_py_data --> nflowmap_atlas_py_step_code
    nflowmap_atlas_py_data --> nflowmap_diagrams_py_Diagrams_component
    nflowmap_canvas_py_graph --> nflowmap_canvas_py_data_label
    nflowmap_canvas_py_graph --> nflowmap_canvas_py_flow_title
    nflowmap_canvas_py_graph --> nflowmap_canvas_py_graph_edge
    nflowmap_canvas_py_graph --> nflowmap_canvas_py_graph_walk
    nflowmap_canvas_py_graph --> nflowmap_canvas_py_screen_group
    nflowmap_canvas_py_paint --> nflowmap_canvas_py_paint_file_of
    nflowmap_atlas_py_functions --> nflowmap_graphs_codegraph_py_doc
    nflowmap_atlas_py_functions --> nflowmap_graphs_python_py_doc
    nflowmap_atlas_py_merges --> nflowmap_diagrams_py_Diagrams_component
    class nflowmap_canvas_py___main__ handler
    classDef confirmed fill:#1f7a3d,stroke:#14532d,color:#fff
    classDef tested fill:#2f9e5a,stroke:#1f7a3d,color:#fff
    classDef agreed fill:#a7e3bd,stroke:#2f9e5a,color:#0b3d1f
    classDef contested fill:#fde68a,stroke:#b58105,color:#3d2c00
    classDef single-source fill:#fecaca,stroke:#b91c1c,color:#450a0a
    classDef endpoint fill:#eef2ff,stroke:#6366f1,color:#1e1b4b
    classDef handler fill:#1e293b,stroke:#0f172a,color:#fff
```

</details>

