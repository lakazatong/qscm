import random

import networkx as nx

from qscm.generator import samplers

from .data import ModelSpec
from .regimes import get_regimes


def random_edge_orientation(G: nx.Graph, seed: int) -> nx.DiGraph:
    """Randomly orient every undirected edge."""
    rng = random.Random(seed)
    result = nx.DiGraph()
    result.add_nodes_from(G.nodes(data=True))

    for u, v, data in G.edges(data=True):
        if rng.random() < 0.5:
            result.add_edge(u, v, **data)
        else:
            result.add_edge(v, u, **data)

    return result


MODELS = {
    "erdos_renyi": ModelSpec(
        nx_function="gnp_random_graph",
        sample=samplers.erdos_renyi,
        regimes=get_regimes("erdos_renyi"),
    ),
    "gnm": ModelSpec(
        nx_function="gnm_random_graph",
        sample=samplers.gnm,
        regimes=get_regimes("gnm"),
    ),
    "barabasi_albert": ModelSpec(
        nx_function="barabasi_albert_graph",
        sample=samplers.barabasi_albert,
        regimes=get_regimes("barabasi_albert"),
        postprocess=random_edge_orientation,
    ),
    "watts_strogatz": ModelSpec(
        nx_function="watts_strogatz_graph",
        sample=samplers.watts_strogatz,
        regimes=get_regimes("watts_strogatz"),
        postprocess=random_edge_orientation,
    ),
    "random_regular": ModelSpec(
        nx_function="random_regular_graph",
        sample=samplers.random_regular,
        regimes=get_regimes("random_regular"),
        postprocess=random_edge_orientation,
    ),
    "random_tree": ModelSpec(
        nx_function="random_labeled_tree",
        sample=samplers.random_tree,
        regimes=get_regimes("random_tree"),
        postprocess=random_edge_orientation,
    ),
    "stochastic_block": ModelSpec(
        nx_function="stochastic_block_model",
        sample=samplers.stochastic_block,
        regimes=get_regimes("stochastic_block"),
        postprocess=random_edge_orientation,
    ),
}
