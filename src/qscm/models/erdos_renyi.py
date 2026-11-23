# sampler
from __future__ import annotations

import math
import random
from numbers import Real
from typing import Any

from .data import Regime
from .utils.regime import (
    _range_validator,
    _sample_interval,
    _validate_mean_out,
    _validate_n,
    _validate_probability,
)


def _validate_er_branching_factor(value: Any, values: dict[str, Any]) -> None:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= int(values["n"])
    ):
        raise ValueError(
            f"branching_factor must be finite and in [0, {values['n']}]; got {value!r}."
        )


def _add_er_parameters(regime: Regime) -> None:
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=2)
    )
    regime.add_variable(
        "p",
        validate=lambda value, values: _validate_probability(value, values, name="p"),
    )
    regime.add_variable("branching_factor", validate=_validate_er_branching_factor)
    regime.add_variable("mean_out", validate=_validate_mean_out)
    regime.add_equation("branching_factor = n * p")
    regime.add_equation("mean_out = (n - 1) * p")


def _custom_erdos_renyi_regime() -> Regime:
    regime = Regime("custom", "Any valid Erdős–Rényi parameters.")
    _add_er_parameters(regime)
    return regime


def _er_regime(
    name: str,
    description: str,
    display: str,
    low: float,
    high: float,
    *,
    include_low: bool = True,
    include_high: bool = False,
    cap_at_n: bool = False,
) -> Regime:
    regime = Regime(name, description, display=display)
    _add_er_parameters(regime)
    interval_validator = _range_validator(
        low,
        high,
        include_low=include_low,
        include_high=include_high,
        name="branching_factor",
    )

    def validate_branching_factor(value: Any, values: dict[str, Any]) -> None:
        interval_validator(value, values)
        _validate_er_branching_factor(value, values)

    regime.add_variable(
        "branching_factor",
        sample=lambda values: _sample_interval(
            values,
            low,
            high,
            include_low=include_low,
            include_high=include_high,
            cap_at="n" if cap_at_n else None,
        ),
        validate=validate_branching_factor,
        override=True,
        description="Erdős–Rényi branching factor n*p",
    )
    return regime


ARGS = {
    "n": {},
    "p": {},
}
KWARGS = {}
PARAMS = {
    "branching_factor": {},
    "mean_out": {},
}


REGIMES = {
    "subcritical": lambda: _er_regime(
        "subcritical",
        "Below the branching threshold.",
        "branching_factor ∈ [0, 1)",
        0.0,
        1.0,
    ),
    "critical": lambda: _er_regime(
        "critical",
        "At the branching threshold.",
        "branching_factor = 1",
        1.0,
        1.0,
        include_high=True,
    ),
    "supercritical": lambda: _er_regime(
        "supercritical",
        "Above the branching threshold.",
        "branching_factor ∈ (1, n]",
        1.0,
        math.inf,
        include_low=False,
        cap_at_n=True,
    ),
    "custom": lambda: _custom_erdos_renyi_regime(),
}


def GENERATOR():

    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state(2)
    @nx._dispatchable(name="erdos_renyi_generate", graphs=None, returns_graph=True)
    def generate(n, p, *, seed: random.Random) -> nx.DiGraph:
        import itertools

        from networkx.generators.classic import complete_graph

        if p >= 1:
            return complete_graph(n, create_using=nx.DiGraph())

        G = nx.empty_graph(n, create_using=nx.DiGraph())
        if p <= 0:
            return G

        for e in itertools.permutations(range(n), 2):
            if seed.random() < p:
                G.add_edge(*e)
        return G

    return generate
