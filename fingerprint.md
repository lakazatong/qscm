# Graph Fingerprint

A graph fingerprint composed of normalized histograms describing structural properties. Each histogram represents a probability distribution over observed values, making it interpretable and suitable for comparing graphs.

## 1. Connectivity

* **In-degree:** Distribution of incoming edges per node.
* **Out-degree:** Distribution of outgoing edges per node.

Describe local connectivity and degree heterogeneity.

## 2. Directed Depth

* **Depth:** Maximum distance from each node to a reachable node, following edge directions.
* **Height:** Maximum distance from each node to a node that can reach it, following reversed edge directions.
* **Divergence:** Distribution of `out_degree(node) × depth(node)`. Combines local branching with downstream reach.
* **Convergence:** Distribution of `in_degree(node) × height(node)`. Combines incoming connectivity with upstream reach.

For cyclic graphs, depth and height are infinite when arbitrarily long walks are possible. Use an explicit infinity bin. Define how products involving infinity and zero are handled.

## 3. Modularity / Edge Criticality

For each directed edge `e`, compute the reachability pairs lost when removing it:

`L_e = R − R_e`

Where `R` is the set of reachable ordered node pairs before removal and `R_e` is the set afterward.

* **Upstream impact:** Number of distinct source nodes appearing in `L_e`. Measures how many sources lose at least one reachable destination.
* **Downstream impact:** Number of distinct destination nodes appearing in `L_e`. Measures how many destinations become unreachable from at least one source.
* **Pair impact:** Number of ordered source–destination pairs in `L_e`. Measures the total reachability loss.

These histograms characterize edge criticality and bottlenecks. Pair impact captures information not retained by upstream and downstream counts individually.

Exclude self-pairs from reachability, or explicitly handle them to avoid hiding lost cyclic reachability.

## 4. Cycle Structure

* **Cycle length:** Distribution of the lengths of simple directed cycles. Distinguishes short loops from long cycles.
* **Node cycle participation:** Distribution of the number of simple directed cycles containing each node. Captures whether cycles are concentrated around a few nodes or spread across the graph.
* **Cycle span:** For each cycle, maximum shortest-path distance between any two of its nodes in the underlying undirected graph. Captures how widely a cycle extends through the graph, independently of its length.

Count cycles differing only by their starting point as the same cycle.

## Conventions

* Normalize each histogram so its bins sum to 1.
* Retain total counts separately where useful, since normalization discards scale.
* Use consistent bins when comparing graphs, including an infinity bin where applicable.
* Define empty-histogram behavior explicitly, especially when a graph has no cycles.
* Treat the fingerprint as a structural descriptor, not a unique graph identifier: non-isomorphic graphs may share the same fingerprint.
