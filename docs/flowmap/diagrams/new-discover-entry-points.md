# new:discover-entry-points

_Maintainer scans the repo being mapped and gets the list of every entry point, the join key for all later passes._

[← system map](./README.md) · generated, do not hand-edit

Steps in the order a user meets them. Colour = evidence (dark green confirmed/tested → light green agreed → amber contested → red single-source). Each box lists the endpoints the step calls.

```mermaid
flowchart TD
    nnew_discover_entry_points_list_entry_points_1["<b>1. Maintainer lists every entry point the repo exposes into inventory.js…</b><br/><i>user · agreed · busy 11</i><br/><code>CLI flowmap inventory</code>"]
    class nnew_discover_entry_points_list_entry_points_1 agreed
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

