import random
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import networkx as nx


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


DEGREE_REGIMES = {
    "subcritical": RangeRegime("Expected degree below 1.", (0.5, 0.9)),
    "critical": RangeRegime("Expected degree around 1.", (0.9, 1.1)),
    "supercritical": RangeRegime("Expected degree above 1.", (1.1, 2.0)),
    "sparse": RangeRegime("Relatively sparse graphs.", (2.0, 4.0)),
}

REGIMES = {
    "erdos_renyi": DEGREE_REGIMES,
    "gnm": DEGREE_REGIMES,
    "barabasi_albert": {
        "tree_like": ChoicesRegime(
            "Minimal attachment; produces tree-like structure.", (1,)
        ),
        "sparse_scale_free": ChoicesRegime(
            "Low attachment; favors hub formation.", (2, 3)
        ),
        "higher_attachment": ChoicesRegime("More edges per arriving node.", (4, 5, 6)),
    },
    "watts_strogatz": {
        "regular_lattice": RangeRegime(
            "Preserves the initial ring lattice.", (0.0, 0.0)
        ),
        "small_world": RangeRegime(
            "Low rewiring; retains local structure.", (0.001, 0.1)
        ),
        "randomized": RangeRegime("Increasingly random connectivity.", (0.1, 1.0)),
    },
    "random_regular": {
        "matching": ChoicesRegime("Every node has degree 1.", (1,)),
        "cycles": ChoicesRegime("Every node has degree 2.", (2,)),
        "moderate_degree": ChoicesRegime("Every node has degree 3 or 4.", (3, 4)),
        "higher_degree": ChoicesRegime("Every node has degree 5 or 6.", (5, 6)),
    },
    "random_tree": {
        "uniform_labeled_tree": ChoicesRegime("Uniformly sampled labeled trees.", ()),
    },
    "stochastic_block": {
        "weak_assortative": StochasticBlockRegime(
            "Within-block probability exceeds between-block probability modestly.",
            p_in=(0.15, 0.4),
            p_out_ratio=(0.4, 0.7),
        ),
        "strong_assortative": StochasticBlockRegime(
            "Within-block probability greatly exceeds between-block probability.",
            p_in=(0.35, 0.7),
            p_out=(0.01, 0.08),
        ),
        "near_uniform": StochasticBlockRegime(
            "Within-block and between-block probabilities are similar.",
            p_in=(0.05, 0.6),
            p_out_ratio=(0.9, 1.1),
        ),
        "disassortative": StochasticBlockRegime(
            "Between-block probability exceeds within-block probability.",
            p_in=(0.01, 0.08),
            p_out=(0.2, 0.5),
        ),
    },
}


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

    parts: list[str | tuple[str, object]] = [
        model,
        regime,
    ]

    for group in ("args", "kwargs"):
        for key, value in nx_arguments.get(group, {}).items():
            if key == "directed":
                continue

            if key == "p" and isinstance(value, (list, tuple)):
                # filename too long, plus the full metadata is contained within the pickled graph anyway
                continue

            parts.append((key, value))

    postprocessing = nx_arguments.get("postprocessing")
    if postprocessing:
        parts.append(("orient", postprocessing["kwargs"].get("seed")))

    return "_".join(format_value(value) for value in parts)


def _degree_regimes(model: str, n: int) -> list[tuple[str, float, float]]:
    max_degree = n - 1
    return [
        (name, regime.values[0], min(regime.values[1], max_degree))
        for name, regime in REGIMES[model].items()
        if isinstance(regime, RangeRegime)
        and regime.values[0] < min(regime.values[1], max_degree)
    ]


def _override(base: "SampledModel | None", group: str, name: str, default):
    """Use an explicit non-None override, otherwise retain the default."""
    if base is None:
        return default

    value = getattr(base, group).get(name)
    return default if value is None else value


def _seed(rng: random.Random, base: "SampledModel | None") -> int:
    value = _override(base, "kwargs", "seed", None)
    return rng.randrange(2**32) if value is None else value


def _choose_degree_regime(
    model: str, n: int, rng: random.Random, base: SampledModel | None
) -> tuple[str, float, float]:
    regimes = REGIMES[model]
    available = {name: (low, high) for name, low, high in _degree_regimes(model, n)}

    requested = _override(base, "parameters", "regime", None)

    if requested is None:
        name = rng.choice(list(available))
    else:
        if requested not in regimes:
            raise ValueError(
                f"Unknown {model} regime {requested!r}; choose from {tuple(regimes)}."
            )
        if requested not in available:
            raise ValueError(f"Regime {requested!r} is unavailable for n={n}.")
        name = requested

    low, high = available[name]
    return name, low, high


def random_edge_orientation(G: nx.Graph, seed: int) -> nx.DiGraph:
    """Randomly orient every undirected edge."""
    rng = random.Random(seed)
    result = nx.DiGraph()
    result.add_nodes_from(G.nodes(data=True))

    for u, v, data in G.edges(data=True):
        if rng.random() < 0.5:
            result.add_edge(u, v, **data)
        else:
            result.add_edge(v, u, **data)

    return result


def _sample_erdos_renyi(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)

    regime, low, high = _choose_degree_regime("erdos_renyi", n, rng, base)

    expected_degree = _override(base, "parameters", "expected_in_out_degree", None)
    p = _override(base, "args", "p", None)

    if expected_degree is None:
        if p is not None:
            expected_degree = p * (n - 1)
        else:
            expected_degree = rng.uniform(low, high)

    if p is None:
        p = expected_degree / (n - 1)

    return SampledModel(
        args={"n": n, "p": p},
        kwargs={"seed": nx_seed, "directed": True},
        parameters={
            "regime": regime,
            "expected_in_out_degree": expected_degree,
        },
    )


def _sample_gnm(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)

    regime, low, high = _choose_degree_regime("gnm", n, rng, base)

    target_mean_out = _override(base, "parameters", "target_mean_out", None)
    m = _override(base, "args", "m", None)

    if target_mean_out is None:
        target_mean_out = m / n if m is not None else rng.uniform(low, high)

    if m is None:
        m = round(n * target_mean_out)

    m = max(0, min(n * (n - 1), m))

    return SampledModel(
        args={"n": n, "m": m},
        kwargs={"seed": nx_seed, "directed": True},
        parameters={
            "regime": regime,
            "target_mean_out": target_mean_out,
            "mean_out": m / n,
        },
    )


def _sample_barabasi_albert(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)
    orientation_seed = _override(
        base, "postprocess_kwargs", "seed", rng.randrange(2**32)
    )

    available = {
        name: regime.values
        for name, regime in REGIMES["barabasi_albert"].items()
        if isinstance(regime, ChoicesRegime)
    }
    available = {name: values for name, values in available.items() if values}

    m = _override(base, "args", "m", None)
    regime = _override(base, "parameters", "regime", None)

    if regime is not None:
        if regime not in available:
            raise ValueError(f"Regime {regime!r} is unavailable for n={n}.")
        choices = available[regime]
    else:
        choices = ()

    if m is None:
        if not choices:
            regime = rng.choice(list(available))
            choices = available[regime]
        m = rng.choice(choices)
    elif regime is None:
        regime = next(
            (name for name, values in available.items() if m in values),
            "custom",
        )

    if not 1 <= m < n:
        raise ValueError("Barabási–Albert m must satisfy 1 <= m < n.")

    return SampledModel(
        args={"n": n, "m": m},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime},
        postprocess_kwargs={"seed": orientation_seed},
    )


def _sample_watts_strogatz(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)
    orientation_seed = _override(
        base, "postprocess_kwargs", "seed", rng.randrange(2**32)
    )

    possible_k = list(range(2, min(8, n - 1) + 1, 2))
    if not possible_k:
        raise ValueError(f"No valid Watts–Strogatz k for n={n}.")

    k = _override(base, "args", "k", None)
    p = _override(base, "args", "p", None)
    regime = _override(base, "parameters", "regime", None)

    if regime is not None:
        if regime not in REGIMES["watts_strogatz"]:
            raise ValueError(f"Unknown Watts–Strogatz regime {regime!r}.")
        low, high = REGIMES["watts_strogatz"][regime].values
    else:
        low, high = 0.0, 1.0

    if k is None:
        k = rng.choice(possible_k)
    if p is None:
        p = low if low == high else rng.uniform(low, high)

    if regime is None:
        regime = next(
            (
                name
                for name, definition in REGIMES["watts_strogatz"].items()
                if definition.values[0] <= p < definition.values[1]
                or (p == 1.0 and definition.values[1] == 1.0)
            ),
            "custom",
        )

    if not 2 <= k < n or k % 2:
        raise ValueError("Watts–Strogatz k must be even and satisfy 2 <= k < n.")
    if not 0.0 <= p <= 1.0:
        raise ValueError("Watts–Strogatz p must be in [0, 1].")

    return SampledModel(
        args={"n": n, "k": k, "p": p},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime},
        postprocess_kwargs={"seed": orientation_seed},
    )


def _sample_random_regular(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)
    orientation_seed = _override(
        base, "postprocess_kwargs", "seed", rng.randrange(2**32)
    )

    possible_d = [d for d in range(1, min(6, n - 1) + 1) if n * d % 2 == 0]
    available = {
        name: tuple(d for d in regime.values if d in possible_d)
        for name, regime in REGIMES["random_regular"].items()
        if isinstance(regime, ChoicesRegime)
    }
    available = {name: values for name, values in available.items() if values}

    d = _override(base, "args", "d", None)
    regime = _override(base, "parameters", "regime", None)

    if regime is not None:
        if regime not in available:
            raise ValueError(f"Regime {regime!r} is unavailable for n={n}.")
        choices = available[regime]
    else:
        choices = ()

    if d is None:
        if not choices:
            regime = rng.choice(list(available))
            choices = available[regime]
        d = rng.choice(choices)
    elif regime is None:
        regime = next(
            (name for name, values in available.items() if d in values),
            "custom",
        )

    if d not in possible_d:
        raise ValueError(
            f"d={d} is invalid for a {n}-node regular graph; "
            "n*d must be even and d < n."
        )

    return SampledModel(
        args={"d": d, "n": n},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime},
        postprocess_kwargs={"seed": orientation_seed},
    )


def _sample_random_tree(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)
    orientation_seed = _override(
        base, "postprocess_kwargs", "seed", rng.randrange(2**32)
    )
    regime = _override(base, "parameters", "regime", "uniform_labeled_tree")

    if regime != "uniform_labeled_tree":
        raise ValueError(f"Unknown random-tree regime {regime!r}.")

    return SampledModel(
        args={"n": n},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime},
        postprocess_kwargs={"seed": orientation_seed},
    )


def _sample_stochastic_block(
    n: int, rng: random.Random, base: SampledModel | None = None
) -> SampledModel:
    nx_seed = _seed(rng, base)
    orientation_seed = _override(
        base, "postprocess_kwargs", "seed", rng.randrange(2**32)
    )

    regime = _override(base, "parameters", "regime", None)
    if regime is None:
        regime = rng.choice(list(REGIMES["stochastic_block"]))
    elif regime not in REGIMES["stochastic_block"]:
        raise ValueError(f"Unknown stochastic-block regime {regime!r}.")

    count = _override(base, "parameters", "count", None)
    if count is None:
        count = rng.randint(2, min(5, n))
    if not 2 <= count <= n:
        raise ValueError("Stochastic-block count must satisfy 2 <= count <= n.")

    definition = REGIMES["stochastic_block"][regime]
    assert isinstance(definition, StochasticBlockRegime)

    default_p_in = rng.uniform(*definition.p_in)
    if definition.p_out is not None:
        default_p_out = rng.uniform(*definition.p_out)
    else:
        assert definition.p_out_ratio is not None
        default_p_out = default_p_in * rng.uniform(*definition.p_out_ratio)

    p_in = _override(base, "parameters", "p_in", default_p_in)
    p_out = _override(base, "parameters", "p_out", default_p_out)

    sizes = _override(base, "args", "sizes", None)
    if sizes is None:
        sizes = [n // count] * count
        for i in range(n % count):
            sizes[i] += 1

    probabilities = _override(base, "args", "probabilities", None)
    if probabilities is None:
        probabilities = [
            [p_in if i == j else p_out for j in range(count)] for i in range(count)
        ]

    return SampledModel(
        args={
            "sizes": sizes,
            "p": probabilities,
        },
        kwargs={"seed": nx_seed},
        parameters={
            "regime": regime,
            "count": count,
            "p_in": p_in,
            "p_out": p_out,
        },
        postprocess_kwargs={"seed": orientation_seed},
    )


DEFAULT_MODELS = {
    "erdos_renyi": ModelSpec(
        nx_function="gnp_random_graph",
        sample=_sample_erdos_renyi,
    ),
    "gnm": ModelSpec(
        nx_function="gnm_random_graph",
        sample=_sample_gnm,
    ),
    "barabasi_albert": ModelSpec(
        nx_function="barabasi_albert_graph",
        sample=_sample_barabasi_albert,
        postprocess=random_edge_orientation,
    ),
    "watts_strogatz": ModelSpec(
        nx_function="watts_strogatz_graph",
        sample=_sample_watts_strogatz,
        postprocess=random_edge_orientation,
    ),
    "random_regular": ModelSpec(
        nx_function="random_regular_graph",
        sample=_sample_random_regular,
        postprocess=random_edge_orientation,
    ),
    "random_tree": ModelSpec(
        nx_function="random_labeled_tree",
        sample=_sample_random_tree,
        postprocess=random_edge_orientation,
    ),
    "stochastic_block": ModelSpec(
        nx_function="stochastic_block_model",
        sample=_sample_stochastic_block,
        postprocess=random_edge_orientation,
    ),
}


class RandomGraphGenerator:
    """Generate directed graphs from configurable random graph models."""

    def __init__(
        self, seed: int | None = None, models: dict[str, ModelSpec] | None = None
    ):
        self._rng = random.Random(seed)
        self.models = models or DEFAULT_MODELS

        if not self.models:
            raise ValueError("At least one model is required.")

    @staticmethod
    def random_edge_orientation(G: nx.Graph, seed: int) -> nx.DiGraph:
        return random_edge_orientation(G, seed)

    def generate(
        self, n: int, model: str | None = None, base: SampledModel | None = None
    ) -> nx.DiGraph:
        if n < 3:
            raise ValueError("n must be at least 3.")

        if model is None:
            model = self._rng.choice(tuple(self.models.keys()))
        elif model not in self.models:
            raise ValueError(
                f"Model {model!r} is not enabled. Choose from: {self.models}"
            )

        spec = self.models[model]
        # this rng will be ignored if base contains everything this sampler needs
        model_rng = random.Random(self._rng.randrange(2**32))
        sampled = spec.sample(n, model_rng, base)

        nx_arguments = {
            "function": spec.nx_function,
            "args": sampled.args.copy(),
            "kwargs": sampled.kwargs.copy(),
        }

        nx_function = getattr(nx, spec.nx_function)
        G = nx_function(**sampled.args, **sampled.kwargs)

        parameters = sampled.parameters.copy()
        regime = parameters.get("regime", "unspecified")
        metadata = {
            "name": graph_filename(model, regime, nx_arguments),
            "model": model,
            "parameters": parameters,
            "nx_arguments": nx_arguments,
        }

        if spec.postprocess is not None:
            postprocess_kwargs = sampled.postprocess_kwargs or {}
            G = spec.postprocess(G, **postprocess_kwargs)
            metadata["postprocessing"] = {
                "function": spec.postprocess.__name__,
                "kwargs": postprocess_kwargs.copy(),
            }

        G.graph.clear()
        G.graph.update(metadata)

        return G
