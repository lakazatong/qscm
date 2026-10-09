import random

import networkx as nx


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

    def _seed(self) -> int:
        return self._rng.randrange(2**32)

    def _orient(self, G: nx.Graph) -> nx.DiGraph:
        """Randomly orient each undirected edge."""
        result = nx.DiGraph()
        result.add_nodes_from(G.nodes(data=True))

        for u, v in G.edges:
            if self._rng.random() < 0.5:
                result.add_edge(u, v)
            else:
                result.add_edge(v, u)

        return result

    def _generate(self, model: str, n: int) -> tuple[nx.DiGraph, dict]:
        seed = self._seed()

        if model == "erdos_renyi":
            k_max = n - 1
            k = self._rng.uniform(0.5, min(6.0, k_max)) if k_max >= 0.5 else 0.0
            p = k / k_max if k_max else 0.0
            G = nx.gnp_random_graph(n, p, seed=seed, directed=True)
            return G, {"p": p}

        if model == "gnm":
            max_edges = n * (n - 1)
            mean_out = self._rng.uniform(0.5, min(6.0, n - 1)) if n > 1 else 0.0
            m = min(max_edges, round(n * mean_out))
            G = nx.gnm_random_graph(n, m, seed=seed, directed=True)
            return G, {"m": m}

        if model == "barabasi_albert":
            m = self._rng.randint(1, min(4, n - 1))
            G = self._orient(nx.barabasi_albert_graph(n, m, seed=seed))
            return G, {"m": m, "orientation": "random"}

        if model == "watts_strogatz":
            possible_k = [k for k in range(2, min(8, n - 1) + 1, 2)]
            k = self._rng.choice(possible_k)
            p = self._rng.uniform(0.05, 0.5)
            G = self._orient(nx.watts_strogatz_graph(n, k, p, seed=seed))
            return G, {"k": k, "p": p, "orientation": "random"}

        if model == "random_regular":
            possible_d = [d for d in range(1, min(6, n - 1) + 1) if n * d % 2 == 0]
            d = self._rng.choice(possible_d)
            G = self._orient(nx.random_regular_graph(d, n, seed=seed))
            return G, {"d": d, "orientation": "random"}

        if model == "random_tree":
            G = self._orient(nx.random_labeled_tree(n, seed=seed))
            return G, {"orientation": "random"}

        if model == "stochastic_block":
            count = self._rng.randint(2, min(5, n))
            sizes = [n // count] * count
            for i in range(n % count):
                sizes[i] += 1

            p_in = self._rng.uniform(0.15, 0.6)
            p_out = self._rng.uniform(0.01, 0.08)
            probabilities = [
                [p_in if i == j else p_out for j in range(count)] for i in range(count)
            ]

            G = self._orient(nx.stochastic_block_model(sizes, probabilities, seed=seed))
            return G, {
                "sizes": sizes,
                "p_in": p_in,
                "p_out": p_out,
                "orientation": "random",
            }

        raise ValueError(f"Unsupported model: {model}")

    def generate(self, n: int) -> nx.DiGraph:
        """Generate a directed graph with exactly n nodes."""
        if n < 1:
            raise ValueError("n must be at least 1.")

        eligible = [
            model
            for model in self.models
            if (
                model in {"erdos_renyi", "gnm"}
                or (model == "barabasi_albert" and n >= 2)
                or (model == "watts_strogatz" and any(k < n for k in range(2, 9, 2)))
                or (
                    model == "random_regular"
                    and any(n * d % 2 == 0 for d in range(1, min(6, n - 1) + 1))
                )
                or (model == "random_tree" and n >= 2)
                or (model == "stochastic_block" and n >= 2)
            )
        ]

        if not eligible:
            raise ValueError(f"No selected model supports n={n}.")

        model = self._rng.choice(eligible)
        G, parameters = self._generate(model, n)

        self.last_model = model
        self.last_parameters = parameters
        G.graph["model"] = model
        G.graph["parameters"] = parameters.copy()

        return G
