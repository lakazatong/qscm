import random

import networkx as nx


class DAG(nx.DiGraph):
    def __init__(self, incoming_graph_data=None, **attr):
        super().__init__(incoming_graph_data, **attr)
        if not nx.is_directed_acyclic_graph(self):
            raise ValueError("Graph must be acyclic")

    @classmethod
    def random(
        cls,
        n_features: int,
        n_hidden: int = 0,
        n_targets: int = 1,
        p: float = 0.3,
        seed: int | None = None,
    ) -> "DAG":
        rng = random.Random(seed)
        nodes = list(range(n_features + n_hidden + n_targets))
        rng.shuffle(nodes)

        features = nodes[:n_features]
        hidden = nodes[n_features : n_features + n_hidden]
        targets = nodes[n_features + n_hidden :]

        graph = cls()
        graph.add_nodes_from(nodes)

        for node in features:
            graph.nodes[node]["role"] = "feature"
        for node in hidden:
            graph.nodes[node]["role"] = "hidden"
        for node in targets:
            graph.nodes[node]["role"] = "target"

        sources = features + hidden
        destinations = hidden + targets

        for source in sources:
            for target in destinations:
                if source != target and rng.random() < p:
                    graph.add_edge(source, target)

        return graph

    @property
    def features(self) -> set:
        return {n for n, data in self.nodes(data=True) if data.get("role") == "feature"}

    @property
    def hidden(self) -> set:
        return {n for n, data in self.nodes(data=True) if data.get("role") == "hidden"}

    @property
    def targets(self) -> set:
        return {n for n, data in self.nodes(data=True) if data.get("role") == "target"}
