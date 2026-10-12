"""Conversion of NetworkX graphs into data for the Cytoscape canvas."""

from typing import Any

import networkx as nx

from qscm.data import require_digraph

ROLE_COLORS = {
    "isolated": "#4CA866",
    "feature": "#4C78A8",
    "hidden": "#9AA0A6",
    "target": "#E45756",
}

STYLESHEET: list[dict[str, Any]] = [
    {
        "selector": "node",
        "style": {
            "label": "data(label)",
            "background-color": ROLE_COLORS["hidden"],
            "color": "#202124",
            "font-size": "10px",
            "text-valign": "top",
            "text-margin-y": -6,
            "width": 24,
            "height": 24,
            "border-width": 1,
            "border-color": "#FFFFFF",
        },
    },
    *[
        {"selector": f".{role}", "style": {"background-color": color}}
        for role, color in ROLE_COLORS.items()
    ],
    {
        "selector": "edge",
        "style": {
            "width": 1.5,
            "line-color": "#9AA0A6",
            "target-arrow-color": "#9AA0A6",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
        },
    },
]


def node_role(graph: nx.Graph, node: Any) -> str:
    if graph.degree(node) == 0:
        return "isolated"

    if not graph.is_directed():
        return "feature" if graph.degree(node) == 1 else "hidden"

    if require_digraph(graph):
        if graph.in_degree(node) == 0:
            return "feature"
        if graph.out_degree(node) == 0:
            return "target"
        return "hidden"

    raise RuntimeError("Impossible case")


def graph_elements(graph: nx.Graph, graph_key: str) -> list[dict[str, Any]]:
    """Convert a NetworkX graph into Cytoscape elements (nodes first)."""
    elements: list[dict[str, Any]] = []

    for node in graph.nodes:
        role = node_role(graph, node)
        elements.append(
            {
                "data": {
                    "id": str(node),
                    "label": str(node),
                    "role": role,
                    "details": (
                        f"Node: {node}\nRole: {role}\nDegree: {graph.degree(node)}"
                    ),
                    "graph_key": graph_key,
                },
                "classes": role,
            }
        )

    for index, (source, target) in enumerate(graph.edges()):
        elements.append(
            {
                "data": {
                    "id": f"edge-{index}",
                    "source": str(source),
                    "target": str(target),
                    "graph_key": graph_key,
                },
            }
        )

    return elements


def graph_payload(graph: nx.Graph, graph_key: str, token: int = 0) -> dict[str, Any]:
    """Everything the browser needs to show one graph.

    The browser replaces the canvas contents with `elements` and starts the
    layout in the same step. `token` changes on every reload so that reloading
    an unchanged graph still reaches the browser; the counts let it verify
    that every element made it onto the canvas.
    """
    return {
        "key": graph_key,
        "token": token,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "elements": graph_elements(graph, graph_key),
    }


def empty_payload(token: int = 0) -> dict[str, Any]:
    return {
        "key": "empty",
        "token": token,
        "node_count": 0,
        "edge_count": 0,
        "elements": [],
    }


def graph_status(graph: nx.Graph) -> str:
    metadata = graph.graph
    parameters = metadata.get("parameters", {})
    nx_arguments = metadata.get("nx_arguments", {})

    return (
        f"{graph.number_of_nodes()} nodes · {graph.number_of_edges()} edges\n"
        f"Model: {metadata.get('model', 'Unknown')}\n"
        f"Parameters: {parameters}\n"
        f"NetworkX arguments: {nx_arguments}"
    )
