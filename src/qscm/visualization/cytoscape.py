import pickle
import re
from pathlib import Path
from typing import Any

import networkx as nx

_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")

ROLE_COLORS = {
    "isolated": "#4CA866",
    "feature": "#4C78A8",
    "hidden": "#9AA0A6",
    "target": "#E45756",
}


def valid_name(name: str) -> bool:
    return bool(_NAME_PATTERN.fullmatch(name)) and name not in {".", ".."}


def discover_items(cache_dir: Path) -> list[dict[str, str]]:
    """Discover cached graphs and graph batches."""
    try:
        paths = list(cache_dir.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return []

    items = []
    for path in paths:
        if not valid_name(path.stem if path.is_file() else path.name):
            continue

        if path.is_file() and path.suffix == ".graph":
            items.append({"label": path.stem, "value": path.stem, "type": "graph"})
        elif path.is_dir():
            try:
                has_graphs = any(
                    child.is_file() and child.suffix == ".graph"
                    for child in path.iterdir()
                )
            except (FileNotFoundError, NotADirectoryError):
                continue

            if has_graphs:
                items.append(
                    {
                        "label": f"{path.name} (batch)",
                        "value": path.name,
                        "type": "batch",
                    }
                )

    return sorted(items, key=lambda item: item["label"].lower())


def graph_files(batch_path: Path) -> list[Path]:
    """Return batch graphs in numeric order where possible."""
    files = [
        path
        for path in batch_path.iterdir()
        if path.is_file() and path.suffix == ".graph"
    ]

    def sort_key(path: Path) -> tuple[int, int | str]:
        stem = path.stem
        return (0, int(stem)) if stem.isdigit() else (1, stem.lower())

    return sorted(files, key=sort_key)


def load_graph(cache_dir: Path, name: str, graph_name: str | None = None) -> nx.Graph:
    """Load a standalone graph or a graph within a batch."""
    if not valid_name(name):
        raise ValueError("Invalid graph or batch name.")

    if graph_name is not None:
        if not valid_name(graph_name):
            raise ValueError("Invalid graph name.")
        path = cache_dir / name / f"{graph_name}.graph"
    else:
        path = cache_dir / f"{name}.graph"
        if not path.is_file():
            batch_path = cache_dir / name
            if not batch_path.is_dir():
                raise FileNotFoundError(f"No graph or batch named {name!r}.")

            files = graph_files(batch_path)
            if not files:
                raise FileNotFoundError(f"Batch {name!r} contains no graphs.")
            path = files[0]

    with path.open("rb") as file:
        graph = pickle.load(file)

    if not isinstance(graph, nx.Graph):
        raise TypeError(f"{path} does not contain a NetworkX graph.")

    return graph


def graph_elements(
    graph: nx.Graph, graph_key: str | None = None
) -> list[dict[str, Any]]:
    """Convert a NetworkX graph into Cytoscape elements."""
    elements = []

    for node, _attributes in graph.nodes(data=True):
        if isinstance(graph, nx.DiGraph):
            if graph.degree(node) == 0:
                role = "isolated"
            elif graph.in_degree(node) == 0:
                role = "feature"
            elif graph.out_degree(node) == 0:
                role = "target"
            else:
                role = "hidden"
            # print(type(graph), isinstance(graph, nx.DiGraph))
            # print("node:", node, "degree:", graph.degree(node))
            # print("in:", graph.in_degree(node) if graph.is_directed() else None)
            # print("out:", graph.out_degree(node) if graph.is_directed() else None)
        else:
            role = (
                "isolated"
                if graph.degree(node) == 0
                else ("feature" if graph.degree(node) == 1 else "hidden")
            )

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
