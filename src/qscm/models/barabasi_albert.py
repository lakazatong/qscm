# sampler
from __future__ import annotations

import random
from typing import Any

from .data import Regime
from .utils.regime import _rng, _validate_integer, _validate_n


def _validate_ba_m(value: Any, values: dict[str, Any]) -> None:
    m = _validate_integer(value, name="m")
    if not 1 <= m < int(values["n"]):
        raise ValueError("Barabási–Albert m must satisfy 1 <= m < n.")


def _custom_barabasi_albert_regime() -> Regime:
    regime = Regime("custom", "Any valid Barabási–Albert attachment count.")
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=2)
    )
    regime.add_variable("m", validate=_validate_ba_m)
    return regime


def _choice_regime(
    name: str,
    description: str,
    display: str,
    parameter: str,
    choices: tuple[int, ...],
) -> Regime:
    def validate_choice(value: Any, values: dict[str, Any]) -> None:
        _validate_ba_m(value, values)
        if int(value) not in choices:
            raise ValueError(f"{parameter} must be one of {choices}; got {value!r}.")

    def feasible(n: int) -> tuple[int, ...]:
        return tuple(choice for choice in choices if choice < n)

    minimum_n = min(choices) + 1

    def sample_choice(values: dict[str, Any]) -> int:
        options = feasible(int(values["n"]))
        if not options:
            raise ValueError(
                f"No {parameter} choice from {choices} is feasible for n={values['n']}."
            )
        return _rng(values).choice(options)

    regime = Regime(
        name,
        description,
        display=display,
    )
    regime.add_variable(
        "n",
        validate=lambda value, values: _validate_n(value, values, minimum=minimum_n),
    )
    regime.add_variable(
        parameter, sample=sample_choice, validate=validate_choice, description=display
    )
    return regime


ARGS = {
    "n": {},
    "m": {},
}
KWARGS = {}
PARAMS = {}

REGIMES = {
    "tree_like": lambda: _choice_regime(
        "tree_like",
        "Minimal attachment; produces tree-like structure.",
        "m ∈ {1}",
        "m",
        (1,),
    ),
    "sparse_scale_free": lambda: _choice_regime(
        "sparse_scale_free",
        "Low attachment; favors hub formation.",
        "m ∈ {2, 3}",
        "m",
        (2, 3),
    ),
    "higher_attachment": lambda: _choice_regime(
        "higher_attachment",
        "More edges per arriving node.",
        "m ∈ {4, 5, 6}",
        "m",
        (4, 5, 6),
    ),
    "custom": lambda: _custom_barabasi_albert_regime(),
}


def _random_subset(repeated_nodes, m, seed):
    targets = set()
    while len(targets) < m:
        targets.add(seed.choice(repeated_nodes))
    return targets


def GENERATOR():
    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state(2)
    @nx._dispatchable(name="barabasi_albert_generate", graphs=None, returns_graph=True)
    def generate(n, m, *, seed: random.Random) -> nx.DiGraph:
        if m < 1 or m >= n:
            raise nx.NetworkXError(
                f"Barabási–Albert network must have m >= 1 and m < n, m = {m}, n = {n}"
            )

        G = nx.star_graph(m, create_using=nx.DiGraph)

        repeated_nodes = [node for node, degree in G.degree() for _ in range(degree)]

        source = len(G)
        while source < n:
            targets = _random_subset(repeated_nodes, m, seed)

            for target in targets:
                if seed.random() < 0.5:
                    G.add_edge(source, target)
                else:
                    G.add_edge(target, source)

            repeated_nodes.extend(targets)
            repeated_nodes.extend([source] * m)

            source += 1

        return G

    return generate
