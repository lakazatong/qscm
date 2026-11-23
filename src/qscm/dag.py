import random

import networkx as nx


def into_dag(graph: nx.DiGraph) -> nx.DiGraph:
    dag = nx.DiGraph()
    dag.add_nodes_from(graph.nodes(data=True))

    for component in nx.weakly_connected_components(graph):
        subgraph = graph.subgraph(component)
        remaining = set(component)
        order = []

        while remaining:
            min_degree = min(
                sum(pred in remaining for pred in subgraph.predecessors(node))
                for node in remaining
            )

            candidates = [
                node
                for node in remaining
                if sum(pred in remaining for pred in subgraph.predecessors(node))
                == min_degree
            ]

            node = random.choice(candidates)
            order.append(node)
            remaining.remove(node)

        positions = {node: i for i, node in enumerate(order)}

        dag.add_edges_from(
            (u, v, data)
            for u, v, data in subgraph.edges(data=True)
            if positions[u] < positions[v]
        )

    return dag
