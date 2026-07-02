# Quantifying the Blast Radius: Centrality-Based Criticality Modeling for Infrastructure Risk

> Which node's failure breaks the most? Graph centrality and node-removal simulation applied to a 90-node fintech infrastructure topology to rank structural risk and surface the failures that conventional inventories miss.

**Author:** Patrick Lefler </br>
**Published:** 2026-07-02 </br>
**Rendered:**

---

## Overview

NexaCore Financial Technologies' 90-node infrastructure estate is modeled as a directed dependency graph, where an edge from A to B means A depends on B. Three centrality measures -- betweenness, eigenvector, and PageRank -- are computed independently and compared rather than averaged, because agreement between metrics is a stronger finding than any single score, and divergence between them identifies *why* a node is critical, which determines the right remediation. Each centrality candidate is then validated through node-removal simulation: remove the node, count how many previously reachable node pairs are now disconnected. The simulation catches what centrality cannot -- nodes that are structurally peripheral but operationally blocking. A business impact layer maps structural blast radius to revenue exposure, producing a remediation backlog that is both graph-theoretically defensible and operationally grounded.

---

## Tech Stack

- **Language:** R, Python
- **Framework:** [Quarto](https://quarto.org/)
- **Primary Libraries:** tidyverse, igraph, tidygraph, ggraph, ggrepel, kableExtra, DT
- **Data generation and pre-computation:** Python (`generate_infra_data.py`, `compute_centrality.py`)
- **Output:** Self-contained HTML (`embed-resources: true`)

---

## Repository Structure

```
nexacore_blast_radius/
├── data/
│   ├── nodes.csv                # 90 infrastructure nodes with tier and business attributes
│   ├── edges.csv                # 155 directed dependency edges
│   ├── centrality_scores.csv   # Pre-computed betweenness, PageRank, eigenvector for all nodes
│   └── blast_radius.csv        # Node-removal simulation results
├── scripts/
│   ├── generate_infra_data.py  # Synthetic topology generator (random.seed(42))
│   └── compute_centrality.py   # Centrality and blast radius pre-computation
├── output/                     # Rendered HTML
├── _brand.yml
├── _quarto.yml
├── INSTRUCTIONS.md
└── index.qmd
```

---

## Key Findings

The Authentication Gateway has no redundant path and sits on every authenticated traffic route in the estate. Its removal disconnects 285 of the 566 reachable node pairs in the graph -- more than any other node by a factor of nearly three. It does not appear in NexaCore's formal single-point-of-failure register.

The Secrets Vault and Shared Message Queue rank at the top of PageRank/eigenvector and betweenness respectively, but for structurally different reasons. The Vault is a deep foundational dependency that every service relies on transitively for database credentials; the Message Queue is a routing chokepoint that 14 services publish and subscribe through. These are different risk profiles requiring different remediations -- a distinction that averaging the centrality scores into a single composite would have obscured.

The KYC/AML Vendor ranks 74th of 90 by composite centrality. Node-removal simulation breaks nine reachable pairs when it is removed: all paths from client onboarding, regulatory compliance reporting, and real-time fraud screening to their downstream dependencies. No fallback exists for any of the three. Centrality analysis would have sent this vendor to the bottom of the remediation backlog. Simulation moved it to the top ten.

---

## Reproducing the Analysis

```bash
# Step 1 — generate the synthetic topology
python3 scripts/generate_infra_data.py

# Step 2 — pre-compute centrality and blast radius
cd nexacore_blast_radius
python3 scripts/compute_centrality.py

# Step 3 — render the document
quarto render index.qmd
```

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.

---

## Contact

Patrick Lefler | [LinkedIn](https://www.linkedin.com/in/patricklefler/) | [patrick-lefler.github.io](https://patrick-lefler.github.io) | [Substack](https://substack.com/@pflefler)
