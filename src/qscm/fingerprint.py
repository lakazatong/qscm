# qscm/fingerprint.py

from collections import Counter
from collections.abc import Mapping
from math import inf
from typing import TypeGuard

import networkx as nx

Histogram = dict[int | float, float]
Fingerprint = dict[str, Histogram]


def _histogram(values) -> Histogram:
    """Build a normalized histogram from observed values."""
    counts = Counter(values)
    total = sum(counts.values())

    if total == 0:
        return {}

    return {value: count / total for value, count in sorted(counts.items())}


def require_digraph(G: nx.Graph) -> TypeGuard[nx.DiGraph]:
    if not G.is_directed():
        raise TypeError("Expected a directed graph.")
    if G.is_multigraph():
        raise TypeError("MultiDiGraph is not supported.")
    return isinstance(G, nx.DiGraph)


# --- Connectivity ---


def in_degree_histogram(G: nx.DiGraph) -> Histogram:
    return _histogram(dict(G.in_degree()).values())


def out_degree_histogram(G: nx.DiGraph) -> Histogram:
    return _histogram(dict(G.out_degree()).values())


# --- Depth and height ---


def _depths_and_heights(
    G: nx.DiGraph,
) -> tuple[dict, dict]:
    """Compute longest-path distances, using infinity when cycles are reachable."""
    if len(G) == 0:
        return {}, {}

    components = list(nx.strongly_connected_components(G))
    component_of = {
        node: i for i, component in enumerate(components) for node in component
    }

    cyclic = {
        i
        for i, component in enumerate(components)
        if len(component) > 1 or any(G.has_edge(node, node) for node in component)
    }

    condensation = nx.condensation(G, components)
    infinite_depth = set()
    infinite_height = set()

    for component_id in condensation:
        descendants = nx.descendants(condensation, component_id)
        ancestors = nx.ancestors(condensation, component_id)

        if component_id in cyclic or descendants & cyclic:
            infinite_depth.add(component_id)

        if component_id in cyclic or ancestors & cyclic:
            infinite_height.add(component_id)

    depth = {node: inf for node in G if component_of[node] in infinite_depth}
    height = {node: inf for node in G if component_of[node] in infinite_height}

    finite_depth_nodes = set(G) - depth.keys()
    finite_depth_graph = G.subgraph(finite_depth_nodes)
    depth_order = list(nx.topological_sort(finite_depth_graph))

    for node in reversed(depth_order):
        depth[node] = max(
            (depth[neighbor] + 1 for neighbor in G.successors(node)),
            default=0,
        )

    finite_height_nodes = set(G) - height.keys()
    finite_height_graph = G.subgraph(finite_height_nodes)
    height_order = list(nx.topological_sort(finite_height_graph))

    for node in height_order:
        height[node] = max(
            (height[neighbor] + 1 for neighbor in G.predecessors(node)),
            default=0,
        )

    return depth, height


def depth_histogram(G: nx.DiGraph) -> Histogram:
    return _histogram(_depths_and_heights(G)[0].values())


def height_histogram(G: nx.DiGraph) -> Histogram:
    return _histogram(_depths_and_heights(G)[1].values())


def divergence_histogram(G: nx.DiGraph) -> Histogram:
    depth, _ = _depths_and_heights(G)
    return _histogram(G.out_degree(node) * depth[node] for node in G)


def convergence_histogram(G: nx.DiGraph) -> Histogram:
    _, height = _depths_and_heights(G)
    return _histogram(G.in_degree(node) * height[node] for node in G)


# --- Edge criticality / modularity ---


def edge_impact_histograms(
    G: nx.DiGraph,
) -> tuple[Histogram, Histogram, Histogram]:
    impacts = _edge_impacts(G)

    return (
        _histogram(upstream for upstream, _, _ in impacts),
        _histogram(downstream for _, downstream, _ in impacts),
        _histogram(pairs for _, _, pairs in impacts),
    )


def upstream_impact_histogram(G: nx.DiGraph) -> Histogram:
    return edge_impact_histograms(G)[0]


def downstream_impact_histogram(G: nx.DiGraph) -> Histogram:
    return edge_impact_histograms(G)[1]


def pair_impact_histogram(G: nx.DiGraph) -> Histogram:
    return edge_impact_histograms(G)[2]


def _reachability_pairs(G: nx.DiGraph) -> set[tuple]:
    """Return reachable ordered pairs, excluding self-pairs."""
    return {(source, target) for source in G for target in nx.descendants(G, source)}


def _edge_impacts(G: nx.DiGraph) -> list[tuple[int, int, int]]:
    """Return (upstream impact, downstream impact, pair impact) per edge."""
    original = _reachability_pairs(G)
    impacts = []

    for source, target in G.edges:
        reduced = G.copy()
        reduced.remove_edge(source, target)

        lost = original - _reachability_pairs(reduced)

        upstream = len({u for u, _ in lost})
        downstream = len({v for _, v in lost})
        pairs = len(lost)

        impacts.append((upstream, downstream, pairs))

    return impacts


# --- Cycles ---


def cycle_length_histogram(G: nx.DiGraph) -> Histogram:
    return _histogram(len(cycle) for cycle in nx.simple_cycles(G))


def node_cycle_participation_histogram(
    G: nx.DiGraph,
) -> Histogram:
    participation = dict.fromkeys(G.nodes, 0)

    for cycle in nx.simple_cycles(G):
        for node in cycle:
            participation[node] += 1

    return _histogram(participation.values())


def cycle_span_histogram(G: nx.DiGraph) -> Histogram:
    undirected = G.to_undirected()
    spans = []

    for cycle in nx.simple_cycles(G):
        span = 0

        for source in cycle:
            distances = nx.single_source_shortest_path_length(undirected, source)
            span = max(
                span,
                *(distances[target] for target in cycle),
            )

        spans.append(span)

    return _histogram(spans)


# --- Combined fingerprint ---


def graph_fingerprint(G: nx.DiGraph) -> Fingerprint:
    """Compute all graph fingerprint histograms."""

    upstream, downstream, pairs = edge_impact_histograms(G)

    return {
        "in_degree": in_degree_histogram(G),
        "out_degree": out_degree_histogram(G),
        "depth": depth_histogram(G),
        "height": height_histogram(G),
        "divergence": divergence_histogram(G),
        "convergence": convergence_histogram(G),
        "upstream_impact": upstream,
        "downstream_impact": downstream,
        "pair_impact": pairs,
        "cycle_length": cycle_length_histogram(G),
        "node_cycle_participation": node_cycle_participation_histogram(G),
        "cycle_span": cycle_span_histogram(G),
    }


# --- Fingerprint cropping ---


def crop_fingerprint(
    fingerprint: Fingerprint,
    bounds: Mapping[str, tuple[int | float, int | float]],
    *,
    discard: bool = True,
) -> Fingerprint:
    """
    Crop histogram value ranges.

    bounds maps histogram names to (minimum, maximum), inclusive.

    If discard=True, out-of-range bins are removed and the remaining
    probabilities renormalized.

    If discard=False, out-of-range probability mass is accumulated
    into the nearest boundary bin.
    """
    result = {}

    for name, histogram in fingerprint.items():
        if name not in bounds:
            result[name] = histogram.copy()
            continue

        minimum, maximum = bounds[name]

        if minimum > maximum:
            raise ValueError(f"Invalid bounds for {name!r}: {minimum} > {maximum}")

        cropped: dict[int | float, float] = {}

        for value, probability in histogram.items():
            if minimum <= value <= maximum:
                key = value
            elif not discard:
                key = minimum if value < minimum else maximum
            else:
                continue

            cropped[key] = cropped.get(key, 0.0) + probability

        total = sum(cropped.values())
        result[name] = (
            {
                value: probability / total
                for value, probability in sorted(cropped.items())
            }
            if total
            else {}
        )

    return result
