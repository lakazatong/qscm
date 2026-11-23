# sampler
from __future__ import annotations

import random
from typing import Any

from .data import Regime
from .utils.regime import (
    _rng,
    _validate_integer,
    _validate_mean_out,
    _validate_n,
)


def _validate_gnm_m(value: Any, values: dict[str, Any]) -> None:
    m = _validate_integer(value, name="m")
    n = int(values["n"])
    maximum = n * (n - 1)
    if not 0 <= m <= maximum:
        raise ValueError(f"m must be in [0, {maximum}]; got {value!r}.")


def _add_gnm_parameters(regime: Regime) -> None:
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=2)
    )
    regime.add_variable("m", validate=_validate_gnm_m)
    regime.add_variable("mean_out", validate=_validate_mean_out)
    regime.add_equation("mean_out = m / n")


def _custom_gnm_regime() -> Regime:
    regime = Regime("custom", "Any valid G(n, m) parameters.")
    _add_gnm_parameters(regime)
    return regime


def _gnm_regime(name: str, description: str, display: str) -> Regime:
    regime = Regime(
        name,
        description,
        display=display,
    )
    _add_gnm_parameters(regime)

    def validate_m(value: Any, values: dict[str, Any]) -> None:
        _validate_gnm_m(value, values)
        n = int(values["n"])
        m = int(value)
        if name == "subcritical" and m >= n:
            raise ValueError("Subcritical GNM requires m/n < 1.")
        if name == "critical" and m != n:
            raise ValueError("Critical GNM requires m/n = 1.")
        if name == "supercritical" and m <= n:
            raise ValueError("Supercritical GNM requires m/n > 1.")

    def sample_m(values: dict[str, Any]) -> int:
        n = int(values["n"])
        if name == "subcritical":
            return _rng(values).randrange(n)
        if name == "critical":
            return n
        maximum = n * (n - 1)
        if maximum <= n:
            raise ValueError(f"No supercritical m exists for n={n}.")
        return _rng(values).randrange(n + 1, maximum + 1)

    regime.add_variable(
        "m",
        sample=sample_m,
        validate=validate_m,
        override=True,
        description=display,
    )
    return regime


ARGS = {
    "n": {},
    "m": {},
}
KWARGS = {}
PARAMS = {
    "mean_out": {},
}

REGIMES = {
    "subcritical": lambda: _gnm_regime(
        "subcritical", "Below the branching threshold.", "m/n < 1"
    ),
    "critical": lambda: _gnm_regime(
        "critical", "At the branching threshold.", "m/n = 1"
    ),
    "supercritical": lambda: _gnm_regime(
        "supercritical", "Above the branching threshold.", "m/n > 1"
    ),
    "custom": lambda: _custom_gnm_regime(),
}


def GENERATOR():
    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state(2)
    @nx._dispatchable(name="gnm_generate", graphs=None, returns_graph=True)
    def generate(n, m, *, seed: random.Random):
        if n == 1:
            return nx.empty_graph(n, create_using=nx.DiGraph())

        max_edges = n * (n - 1)
        if m >= max_edges:
            return nx.complete_graph(n, create_using=nx.DiGraph())

        G = nx.empty_graph(n, create_using=nx.DiGraph())
        nlist = list(G)
        edge_count = 0

        while edge_count < m:
            u = seed.choice(nlist)
            v = seed.choice(nlist)
            if u == v or G.has_edge(u, v):
                continue

            G.add_edge(u, v)
            edge_count += 1

        return G

    return generate
