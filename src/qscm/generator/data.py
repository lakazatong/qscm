import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from numbers import Real

import networkx as nx

from .regimes import Regime


@dataclass(frozen=True)
class SampledModel:
    args: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    postprocess_kwargs: dict | None = None


Sampler = Callable[[int, random.Random, SampledModel | None], SampledModel]


@dataclass(frozen=True)
class ModelSpec:
    nx_function: str
    sample: Sampler
    regimes: Mapping[str, Regime]
    postprocess: Callable[..., nx.DiGraph] | None = None


def finite_real(value: object) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
