import random
from collections.abc import Mapping

import networkx as nx


def graph_filename(model: str, regime: str, nx_arguments: Mapping) -> str:
    def format_value(value) -> str:
        if isinstance(value, float):
            return f"{value:.6g}"
        if isinstance(value, (list, tuple)):
            return "-".join(format_value(item) for item in value)
        return str(value).replace("_", "-")

    parts = [
        model,
        regime,
        *nx_arguments.get("args", {}).items(),
        *nx_arguments.get("kwargs", {}).items(),
    ]

    postprocessing = nx_arguments.get("postprocessing")
    if postprocessing:
        orientation_seed = postprocessing["kwargs"]["seed"]
        parts.append(("orient", orientation_seed))

    return "_".join(format_value(v) for v in parts)


class RandomGraphGenerator:
    """Generate random directed graphs from varied graph model families."""

    MODELS = (
        "erdos_renyi",
        "gnm",
        "barabasi_albert",
        "watts_strogatz",
        "random_regular",
        "random_tree",
        "stochastic_block",
    )

    def __init__(
        self,
        seed: int | None = None,
        models: tuple[str, ...] | None = None,
    ):
        self._rng = random.Random(seed)
        self.models = tuple(models or self.MODELS)

        unknown = set(self.models) - set(self.MODELS)
        if unknown:
            raise ValueError(f"Unknown graph models: {sorted(unknown)}")
        if not self.models:
            raise ValueError("At least one model is required.")

        self.last_model: str | None = None
        self.last_parameters: dict = {}

    def random_edge_orientation(self, G: nx.Graph, seed: int) -> nx.DiGraph:
        """Randomly orient each undirected edge."""
        rng = random.Random(seed)
        result = nx.DiGraph()
        result.add_nodes_from(G.nodes(data=True))

        for u, v in G.edges:
            if rng.random() < 0.5:
                result.add_edge(u, v)
            else:
                result.add_edge(v, u)

        return result

    @staticmethod
    def _degree_regimes(n: int) -> list[tuple[str, float, float]]:
        max_degree = n - 1
        candidates = [
            ("subcritical", 0.5, 0.9),
            ("critical", 0.9, 1.1),
            ("supercritical", 1.1, 2.0),
            ("sparse", 2.0, 4.0),
        ]

        return [
            (name, low, min(high, max_degree))
            for name, low, high in candidates
            if low < min(high, max_degree)
        ]

    def generate_erdos_renyi(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)

        regimes = self._degree_regimes(n)
        regime, low, high = rng.choice(regimes)
        expected_in_out_degree = rng.uniform(low, high)
        p = expected_in_out_degree / (n - 1)

        nx_args = {"n": n, "p": p}
        nx_kwargs = {"seed": nx_seed, "directed": True}
        G = nx.gnp_random_graph(*nx_args.values(), **nx_kwargs)

        parameters = {
            "regime": regime,
            "expected_in_out_degree": expected_in_out_degree,
        }
        nx_arguments = {
            "function": "gnp_random_graph",
            "args": nx_args,
            "kwargs": nx_kwargs,
        }
        return G, parameters, nx_arguments

    def generate_gnm(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)

        regimes = self._degree_regimes(n)
        regime, low, high = rng.choice(regimes)
        target_mean_out = rng.uniform(low, high)

        m = max(1, min(n * (n - 1), round(n * target_mean_out)))
        mean_out = m / n

        nx_args = {"n": n, "m": m}
        nx_kwargs = {"seed": nx_seed, "directed": True}
        G = nx.gnm_random_graph(*nx_args.values(), **nx_kwargs)

        parameters = {
            "regime": regime,
            "target_mean_out": target_mean_out,
            "mean_out": mean_out,
        }
        nx_arguments = {
            "function": "gnm_random_graph",
            "args": nx_args,
            "kwargs": nx_kwargs,
        }
        return G, parameters, nx_arguments

    def generate_barabasi_albert(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)
        orientation_seed = rng.randrange(2**32)

        max_m = min(6, n - 1)
        regimes = [
            ("tree_like", [1]),
            ("sparse_scale_free", list(range(2, min(3, max_m) + 1))),
            ("higher_attachment", list(range(4, max_m + 1))),
        ]
        regimes = [(name, values) for name, values in regimes if values]

        regime, values = rng.choice(regimes)
        m = rng.choice(values)

        nx_args = {"n": n, "m": m}
        nx_kwargs = {"seed": nx_seed}
        G = self.random_edge_orientation(
            nx.barabasi_albert_graph(*nx_args.values(), **nx_kwargs),
            seed=orientation_seed,
        )

        parameters = {"regime": regime}
        nx_arguments = {
            "function": "barabasi_albert_graph",
            "args": nx_args,
            "kwargs": nx_kwargs,
            "postprocessing": {
                "function": "random_edge_orientation",
                "kwargs": {"seed": orientation_seed},
            },
        }
        return G, parameters, nx_arguments

    def generate_watts_strogatz(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)
        orientation_seed = rng.randrange(2**32)

        possible_k = list(range(2, min(8, n - 1) + 1, 2))
        k = rng.choice(possible_k)

        regimes = [
            ("regular_lattice", 0.0, 0.0),
            ("small_world", 0.001, 0.1),
            ("randomized", 0.1, 1.0),
        ]
        regime, low, high = rng.choice(regimes)
        p = low if low == high else rng.uniform(low, high)

        nx_args = {"n": n, "k": k, "p": p}
        nx_kwargs = {"seed": nx_seed}
        G = self.random_edge_orientation(
            nx.watts_strogatz_graph(*nx_args.values(), **nx_kwargs),
            seed=orientation_seed,
        )

        parameters = {"regime": regime}
        nx_arguments = {
            "function": "watts_strogatz_graph",
            "args": nx_args,
            "kwargs": nx_kwargs,
            "postprocessing": {
                "function": "random_edge_orientation",
                "kwargs": {"seed": orientation_seed},
            },
        }
        return G, parameters, nx_arguments

    def generate_random_regular(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)
        orientation_seed = rng.randrange(2**32)

        possible_d = [d for d in range(1, min(6, n - 1) + 1) if n * d % 2 == 0]
        regimes = [
            ("matching", [d for d in possible_d if d == 1]),
            ("cycles", [d for d in possible_d if d == 2]),
            ("moderate_degree", [d for d in possible_d if d in (3, 4)]),
            ("higher_degree", [d for d in possible_d if d in (5, 6)]),
        ]
        regimes = [(name, values) for name, values in regimes if values]

        regime, values = rng.choice(regimes)
        d = rng.choice(values)

        nx_args = {"d": d, "n": n}
        nx_kwargs = {"seed": nx_seed}
        G = self.random_edge_orientation(
            nx.random_regular_graph(*nx_args.values(), **nx_kwargs),
            seed=orientation_seed,
        )

        parameters = {"regime": regime}
        nx_arguments = {
            "function": "random_regular_graph",
            "args": nx_args,
            "kwargs": nx_kwargs,
            "postprocessing": {
                "function": "random_edge_orientation",
                "kwargs": {"seed": orientation_seed},
            },
        }
        return G, parameters, nx_arguments

    def generate_random_tree(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)
        orientation_seed = rng.randrange(2**32)

        nx_args = {"n": n}
        nx_kwargs = {"seed": nx_seed}
        G = self.random_edge_orientation(
            nx.random_labeled_tree(*nx_args.values(), **nx_kwargs),
            seed=orientation_seed,
        )

        parameters = {"regime": "uniform_labeled_tree"}
        nx_arguments = {
            "function": "random_labeled_tree",
            "args": nx_args,
            "kwargs": nx_kwargs,
            "postprocessing": {
                "function": "random_edge_orientation",
                "kwargs": {"seed": orientation_seed},
            },
        }
        return G, parameters, nx_arguments

    def generate_stochastic_block(self, n: int) -> tuple[nx.DiGraph, dict, dict]:
        rng = random.Random(self._rng.randrange(2**32))
        nx_seed = rng.randrange(2**32)
        orientation_seed = rng.randrange(2**32)

        count = rng.randint(2, min(5, n))
        sizes = [n // count] * count
        for i in range(n % count):
            sizes[i] += 1

        regimes = (
            "weak_assortative",
            "strong_assortative",
            "near_uniform",
            "disassortative",
        )
        regime = rng.choice(regimes)

        if regime == "weak_assortative":
            p_in = rng.uniform(0.15, 0.4)
            p_out = p_in * rng.uniform(0.4, 0.7)
        elif regime == "strong_assortative":
            p_in = rng.uniform(0.35, 0.7)
            p_out = rng.uniform(0.01, 0.08)
        elif regime == "near_uniform":
            p_in = rng.uniform(0.05, 0.6)
            p_out = p_in * rng.uniform(0.9, 1.1)
        else:
            p_in = rng.uniform(0.01, 0.08)
            p_out = rng.uniform(0.2, 0.5)

        probabilities = [
            [p_in if i == j else p_out for j in range(count)] for i in range(count)
        ]

        nx_args = {"sizes": sizes, "probabilities": probabilities}
        nx_kwargs = {"seed": nx_seed}
        G = self.random_edge_orientation(
            nx.stochastic_block_model(*nx_args.values(), **nx_kwargs),
            seed=orientation_seed,
        )

        parameters = {
            "regime": regime,
            "count": count,
            "p_in": p_in,
            "p_out": p_out,
        }
        nx_arguments = {
            "function": "stochastic_block_model",
            "args": nx_args,
            "kwargs": nx_kwargs,
            "postprocessing": {
                "function": "random_edge_orientation",
                "kwargs": {"seed": orientation_seed},
            },
        }
        return G, parameters, nx_arguments

    def generate(self, n: int, model: str | None = None) -> nx.DiGraph:
        if n < 3:
            raise ValueError("n must be at least 3.")

        if model is None:
            model = self._rng.choice(self.models)
        elif model not in self.models:
            raise ValueError(
                f"Model {model!r} is not enabled. Choose from: {self.models}"
            )

        generators = {
            "erdos_renyi": self.generate_erdos_renyi,
            "gnm": self.generate_gnm,
            "barabasi_albert": self.generate_barabasi_albert,
            "watts_strogatz": self.generate_watts_strogatz,
            "random_regular": self.generate_random_regular,
            "random_tree": self.generate_random_tree,
            "stochastic_block": self.generate_stochastic_block,
        }

        G, parameters, nx_arguments = generators[model](n)

        metadata = {
            "model": model,
            "parameters": parameters,
            "nx_arguments": nx_arguments,
        }
        metadata["name"] = graph_filename(model, parameters["regime"], nx_arguments)

        G.graph.clear()
        G.graph.update(metadata)

        self.last_model = model
        self.last_parameters = parameters

        return G
