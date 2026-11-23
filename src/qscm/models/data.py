from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import networkx as nx

from .utils.parameter_dag import InsufficientInformation, ParameterDAG


class Sampler(Protocol):
    def __call__(
        self,
        n: int,
        rng: random.Random,
        *,
        base: SampledModel | None = None,
        mockup: bool = False,
    ) -> SampledModel: ...


@dataclass(frozen=True)
class SampledModel:
    args: dict = field(default_factory=dict)
    kwargs: dict = field(default_factory=dict)
    parameters: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ModelSpec:
    nx_function: Callable[..., nx.DiGraph]
    sample: Sampler
    regimes: Mapping[str, Callable[..., Regime]]


class Regime(ParameterDAG):
    """A self-contained parameter DAG for one graph-generation regime."""

    def __init__(
        self, name: str, description: str, *, display: str | None = None
    ) -> None:
        super().__init__()
        self.name = name
        self.description = description
        self.display = display or description

    def format(self) -> str:
        return self.display

    def resolve_regime(
        self,
        values: Mapping[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:

        unknown = values.keys() - self.variables.keys()
        if unknown:
            raise ValueError(
                f"Unsupported parameter(s) for regime {self.name!r}: "
                f"{', '.join(sorted(unknown))}."
            )
        try:
            resolved = self.resolve(values, context={"_rng": rng})
        except InsufficientInformation:
            print(f"Resolving failed for regime {self.name}:")
            raise
        self.check(resolved)
        return resolved
