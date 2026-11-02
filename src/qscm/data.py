from collections.abc import Iterable, Sequence
from typing import TypeGuard

import networkx as nx

# fingerprint
Histogram = dict[int | float, float]
Fingerprint = dict[str, Histogram]

# geometry
Vector = Sequence[float]
Points = Iterable[Vector]


# Misc


def require_digraph(G: nx.Graph) -> TypeGuard[nx.DiGraph]:
    if not G.is_directed():
        raise TypeError("Expected a directed graph.")
    if G.is_multigraph():
        raise TypeError("MultiDiGraph is not supported.")
    return isinstance(G, nx.DiGraph)
