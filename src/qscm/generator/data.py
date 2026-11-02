from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from numbers import Real
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from typing import Protocol

from .regimes import Regime


@dataclass(frozen=True)
class SampledModel:
    args: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    postprocess_kwargs: dict | None = None


class Sampler(Protocol):
    def __call__(
        self,
        n: int,
        rng: random.Random,
        base: SampledModel | None = None,
        *,
        mockup: bool = False,
    ) -> SampledModel: ...


@dataclass(frozen=True)
class ModelSpec:
    nx_function: str
    sample: Sampler
    regimes: Mapping[str, Callable[..., Regime]]
    postprocess: Callable[..., nx.DiGraph] | None = None


def finite_real(value: object) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
