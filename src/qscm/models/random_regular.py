# sampler
from __future__ import annotations

import random
from typing import Any

from .data import Regime
from .utils.regime import _rng, _validate_integer, _validate_n


def _validate_rr_d(value: Any, values: dict[str, Any]) -> None:
    degree = _validate_integer(value, name="d")
    n = int(values["n"])
    if not 1 <= degree < n or n * degree % 2:
        raise ValueError(f"Degree {degree} is not feasible for n={n}.")


def _add_rr_parameters(regime: Regime) -> None:
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=3)
    )
    regime.add_variable("d", validate=_validate_rr_d)


def _custom_random_regular_regime() -> Regime:
    regime = Regime("custom", "Any feasible regular degree.")
    _add_rr_parameters(regime)
    return regime


def _choice_regime(
    name: str,
    description: str,
    display: str,
    parameter: str,
    choices: tuple[int, ...],
) -> Regime:

    def validate_choice(value: Any, values: dict[str, Any]) -> None:
        _validate_rr_d(value, values)
        if int(value) not in choices:
            raise ValueError(f"{parameter} must be one of {choices}; got {value!r}.")

    def feasible(n: int) -> tuple[int, ...]:
        return tuple(d for d in choices if 1 <= d < n and n * d % 2 == 0)

    minimum_n = 3

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
    "d": {},
}
KWARGS = {}
PARAMS = {}


REGIMES = {
    "matching": lambda: _choice_regime(
        "matching",
        "Every node has degree 1.",
        "d ∈ {1}",
        "d",
        (1,),
    ),
    "cycles": lambda: _choice_regime(
        "cycles",
        "Every node has degree 2.",
        "d ∈ {2}",
        "d",
        (2,),
    ),
    "moderate_degree": lambda: _choice_regime(
        "moderate_degree",
        "Every node has degree 3 or 4.",
        "d ∈ {3, 4}",
        "d",
        (3, 4),
    ),
    "higher_degree": lambda: _choice_regime(
        "higher_degree",
        "Every node has degree 5 or 6.",
        "d ∈ {5, 6}",
        "d",
        (5, 6),
    ),
    "custom": lambda: _custom_random_regular_regime(),
}


def GENERATOR():
    from collections import defaultdict

    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state(2)
    @nx._dispatchable(name="random_regular_generate", graphs=None, returns_graph=True)
    def generate(n, d, *, seed: random.Random):
        if (n * d) % 2 != 0:
            raise nx.NetworkXError("n * d must be even")

        if not 0 <= d < n:
            raise nx.NetworkXError("the 0 <= d < n inequality must be satisfied")

        G = nx.empty_graph(n, create_using=nx.DiGraph())

        if d == 0:
            return G

        def _suitable(edges, potential_edges):
            if not potential_edges:
                return True
            for s1 in potential_edges:
                for s2 in potential_edges:
                    if s1 == s2:
                        break
                    if s1 > s2:
                        s1, s2 = s2, s1
                    if (s1, s2) not in edges:
                        return True
            return False

        def _try_creation():
            edges = set()
            stubs = list(range(n)) * d

            while stubs:
                potential_edges = defaultdict(lambda: 0)
                seed.shuffle(stubs)
                stubiter = iter(stubs)

                for s1, s2 in zip(stubiter, stubiter):
                    if s1 > s2:
                        s1, s2 = s2, s1
                    if s1 != s2 and (s1, s2) not in edges:
                        edges.add((s1, s2))
                    else:
                        potential_edges[s1] += 1
                        potential_edges[s2] += 1

                if not _suitable(edges, potential_edges):
                    return None

                stubs = [
                    node
                    for node, potential in potential_edges.items()
                    for _ in range(potential)
                ]

            return edges

        edges = _try_creation()
        while edges is None:
            edges = _try_creation()

        for u, v in edges:
            if seed.random() < 0.5:
                G.add_edge(u, v)
            else:
                G.add_edge(v, u)

        return G

    return generate
