# sampler

from __future__ import annotations

import random

from .data import Regime
from .utils.regime import _validate_n


def _custom_random_tree_regime() -> Regime:
    regime = Regime("custom", "Any valid random-tree size.")
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    return regime


def _random_tree_regime() -> Regime:
    regime = Regime(
        "uniform_labeled_tree",
        "Uniformly sampled labeled trees.",
        display="uniform labeled tree",
    )
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    return regime


ARGS = {
    "n": {},
}
KWARGS = {}
PARAMS = {}


REGIMES = {
    "uniform_labeled_tree": lambda: _random_tree_regime(),
    "custom": lambda: _custom_random_tree_regime(),
}


def GENERATOR():
    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state("seed")
    @nx._dispatchable(name="random_tree_generate", graphs=None, returns_graph=True)
    def generate(n, *, seed: random.Random):
        if n == 0:
            raise nx.NetworkXPointlessConcept("the null graph is not a tree")

        if n == 1:
            return nx.empty_graph(1, create_using=nx.DiGraph())

        prufer_sequence = [seed.choice(range(n)) for _ in range(n - 2)]
        tree = nx.from_prufer_sequence(prufer_sequence)

        G = nx.DiGraph()
        G.add_nodes_from(tree.nodes(data=True))
        G.add_edges_from(tree.edges(data=True))

        return G

    return generate
