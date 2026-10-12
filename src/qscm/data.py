import random
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import TypeGuard

import networkx as nx

# fingerprint
Histogram = dict[int | float, float]
Fingerprint = dict[str, Histogram]

# geometry
Vector = Sequence[float]
Points = Iterable[Vector]


# generator
@dataclass(frozen=True)
class Regime(ABC):
    description: str

    @abstractmethod
    def format(self) -> str:
        """Human-readable definition of this regime."""


@dataclass(frozen=True)
class RangeRegime(Regime):
    values: tuple[float, float]

    def format(self) -> str:
        return f"[{self.values[0]}, {self.values[1]}]"


@dataclass(frozen=True)
class ChoicesRegime(Regime):
    values: tuple[int, ...]

    def format(self) -> str:
        return "{" + ", ".join(map(str, self.values)) + "}"


@dataclass(frozen=True)
class StochasticBlockRegime(Regime):
    p_in: tuple[float, float]
    p_out: tuple[float, float] | None = None
    p_out_ratio: tuple[float, float] | None = None

    def format(self) -> str:
        parts = [f"p_in ∈ {self.p_in}"]
        if self.p_out is not None:
            parts.append(f"p_out ∈ {self.p_out}")
        if self.p_out_ratio is not None:
            parts.append(f"p_out/p_in ∈ {self.p_out_ratio}")
        return ", ".join(parts)


@dataclass(frozen=True)
class SampledModel:
    args: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)
    postprocess_kwargs: dict | None = None


Sampler = Callable[
    [int, random.Random, SampledModel | None],
    SampledModel,
]


@dataclass(frozen=True)
class ModelSpec:
    nx_function: str
    sample: Sampler
    postprocess: Callable[..., nx.DiGraph] | None = None


# Misc


def require_digraph(G: nx.Graph) -> TypeGuard[nx.DiGraph]:
    if not G.is_directed():
        raise TypeError("Expected a directed graph.")
    if G.is_multigraph():
        raise TypeError("MultiDiGraph is not supported.")
    return isinstance(G, nx.DiGraph)
