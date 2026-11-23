# sampler
from __future__ import annotations

import random
from typing import Any

from .data import Regime
from .utils.regime import (
    _range_validator,
    _rng,
    _sample_interval,
    _validate_integer,
    _validate_n,
    _validate_probability,
)


def _possible_ws_k(n: int) -> tuple[int, ...]:
    return tuple(range(2, min(8, n - 1) + 1, 2))


def _validate_ws_k(
    value: Any, values: dict[str, Any], *, maximum: int | None = None
) -> None:
    k = _validate_integer(value, name="k")
    n = int(values["n"])
    if k < 2 or k >= n or k % 2:
        raise ValueError(
            f"k must be even and satisfy 2 <= k < n; got {value!r} for n={n}."
        )
    if maximum is not None and k > maximum:
        raise ValueError(f"k must not exceed {maximum}; got {k}.")


def _add_ws_parameters(regime: Regime, *, named_maximum: int | None = None) -> None:
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=3)
    )
    regime.add_variable(
        "k",
        validate=lambda value, values: _validate_ws_k(
            value, values, maximum=named_maximum
        ),
    )
    regime.add_variable(
        "p",
        validate=lambda value, values: _validate_probability(value, values, name="p"),
    )


def _custom_watts_strogatz_regime() -> Regime:
    regime = Regime("custom", "Any valid Watts–Strogatz parameters.")
    _add_ws_parameters(regime)
    return regime


def _watts_strogatz_regime(
    name: str,
    description: str,
    display: str,
    low: float,
    high: float,
    *,
    include_low: bool = True,
    include_high: bool = False,
) -> Regime:
    regime = Regime(name, description, display=display)
    _add_ws_parameters(regime, named_maximum=8)
    regime.add_variable(
        "k",
        sample=lambda values: _rng(values).choice(_possible_ws_k(int(values["n"]))),
        validate=lambda value, values: _validate_ws_k(value, values, maximum=8),
        override=True,
    )
    regime.add_variable(
        "p",
        sample=lambda values: _sample_interval(
            values,
            low,
            high,
            include_low=include_low,
            include_high=include_high,
        ),
        validate=_range_validator(
            low,
            high,
            include_low=include_low,
            include_high=include_high,
            name="p",
        ),
        override=True,
        description="rewiring probability",
    )
    return regime


ARGS = {
    "n": {},
    "k": {},
    "p": {},
}
KWARGS = {}
PARAMS = {}

REGIMES = {
    "regular_lattice": lambda: _watts_strogatz_regime(
        "regular_lattice",
        "Preserves the initial ring lattice.",
        "p = 0",
        0.0,
        0.0,
        include_high=True,
    ),
    "small_world": lambda: _watts_strogatz_regime(
        "small_world",
        "Low rewiring; retains local structure.",
        "p ∈ [0.001, 0.1)",
        0.001,
        0.1,
    ),
    "randomized": lambda: _watts_strogatz_regime(
        "randomized",
        "Increasingly random connectivity.",
        "p ∈ [0.1, 1]",
        0.1,
        1.0,
        include_high=True,
    ),
    "custom": lambda: _custom_watts_strogatz_regime(),
}


def GENERATOR():
    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state(3)
    @nx._dispatchable(name="wattz_strogatz_generate", graphs=None, returns_graph=True)
    def generate(n, k, p, *, seed: random.Random):
        assert seed is not None

        if k > n:
            raise nx.NetworkXError("k>n, choose smaller k or larger n")

        G = nx.DiGraph()
        nodes = list(range(n))

        if k == n:
            for u in nodes:
                for v in nodes:
                    if u != v and seed.random() < 0.5:
                        G.add_edge(u, v)
            return G

        def add_random_edge(u, v):
            if seed.random() < 0.5:
                G.add_edge(u, v)
            else:
                G.add_edge(v, u)

        for j in range(1, k // 2 + 1):
            targets = nodes[j:] + nodes[0:j]
            for u, v in zip(nodes, targets):
                add_random_edge(u, v)

        for j in range(1, k // 2 + 1):
            targets = nodes[j:] + nodes[0:j]
            for u, v in zip(nodes, targets):
                if seed.random() < p:
                    candidates = [
                        w
                        for w in nodes
                        if w != u and not G.has_edge(u, w) and not G.has_edge(w, u)
                    ]

                    if not candidates:
                        continue

                    if G.has_edge(u, v):
                        G.remove_edge(u, v)
                    else:
                        G.remove_edge(v, u)

                    add_random_edge(u, seed.choice(candidates))

        return G

    return generate
