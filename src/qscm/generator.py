from __future__ import annotations

import random
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import networkx as nx

from .models import MODELS
from .models.data import ModelSpec, SampledModel

# --- Helpers ---


def graph_filename(model: str, regime: str, nx_arguments: Mapping) -> str:
    def format_value(value) -> str:
        if isinstance(value, float):
            return f"{value:.6g}"
        if isinstance(value, (list, tuple)):
            return "-".join(format_value(item) for item in value)
        if isinstance(value, dict):
            return "-".join(
                f"{format_value(key)}-{format_value(item)}"
                for key, item in value.items()
            )
        return str(value).replace("_", "-")

    parts: list[str | tuple[str, object]] = [model, regime]

    for group in ("args", "kwargs"):
        for key, value in nx_arguments.get(group, {}).items():
            if key == "directed":
                continue

            if key == "p" and isinstance(value, (list, tuple)):
                continue

            parts.append((key, value))

    return "_".join(format_value(value) for value in parts)


class RandomGraphGenerator:
    """Generate directed graphs from configurable random graph models."""

    def __init__(
        self, seed: int | None = None, models: dict[str, ModelSpec] | None = None
    ):
        self._rng = random.Random(seed)
        self.models = models or MODELS

        if not self.models:
            raise ValueError("At least one model is required.")

    def generate(
        self, n: int, model: str | None = None, base: SampledModel | None = None
    ) -> nx.DiGraph:
        if model is None:
            model = self._rng.choice(tuple(self.models.keys()))
        elif model not in self.models:
            raise ValueError(
                f"Model {model!r} is not enabled. Choose from: {self.models}"
            )

        spec = self.models[model]
        # this rng will be ignored if base contains everything this sampler needs
        sampled = spec.sample(n, base=base, rng=self._rng)

        nx_arguments = {
            "args": sampled.args.copy(),
            "kwargs": sampled.kwargs.copy(),
        }

        G = spec.nx_function(**sampled.args, **sampled.kwargs)

        parameters = sampled.parameters.copy()
        regime = parameters.get("regime", None)
        assert regime is not None
        metadata = {
            "name": graph_filename(model, regime, nx_arguments),
            "model": model,
            "nx_arguments": nx_arguments,
            "parameters": parameters,
        }

        G.graph.clear()
        G.graph.update(metadata)

        return G
