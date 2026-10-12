"""Access to the on-disk graph cache, shared by the CLI and the visualizer.

Layout of the cache directory:

    <cache>/<name>.graph          a standalone graph
    <cache>/<batch>/<name>.graph  a graph inside a batch
"""

import pickle
import re
from pathlib import Path

import networkx as nx

GRAPH_SUFFIX = ".graph"

_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")


def valid_name(name: str) -> bool:
    """Names are single path components: no separators, no leading dot."""
    return bool(_NAME_PATTERN.fullmatch(name))


def graph_files(batch_path: Path) -> list[Path]:
    """Return a batch's graph files, numeric stems first, then alphabetical."""
    files = [
        path
        for path in batch_path.iterdir()
        if path.is_file() and path.suffix == GRAPH_SUFFIX
    ]

    def sort_key(path: Path) -> tuple[int, int, str]:
        stem = path.stem
        if stem.isdigit():
            return (0, int(stem), "")
        return (1, 0, stem.lower())

    return sorted(files, key=sort_key)


def _has_graphs(directory: Path) -> bool:
    try:
        return any(
            child.is_file() and child.suffix == GRAPH_SUFFIX
            for child in directory.iterdir()
        )
    except (FileNotFoundError, NotADirectoryError):
        return False


def discover_items(cache_dir: Path) -> list[dict[str, str]]:
    """Discover cached graphs and graph batches (as dropdown options)."""
    try:
        paths = list(cache_dir.iterdir())
    except (FileNotFoundError, NotADirectoryError):
        return []

    items = []
    for path in paths:
        if path.is_file():
            if path.suffix == GRAPH_SUFFIX and valid_name(path.stem):
                items.append({"label": path.stem, "value": path.stem, "type": "graph"})
        elif path.is_dir() and valid_name(path.name) and _has_graphs(path):
            items.append(
                {"label": f"{path.name} (batch)", "value": path.name, "type": "batch"}
            )

    return sorted(items, key=lambda item: item["label"].lower())


def read_graph(path: Path) -> nx.Graph:
    with path.open("rb") as file:
        graph = pickle.load(file)

    if not isinstance(graph, nx.Graph):
        raise TypeError(f"{path} does not contain a NetworkX graph.")

    return graph


def save_graph(graph: nx.Graph, path: Path, *, overwrite: bool = True) -> None:
    """Pickle a graph. With overwrite=False an existing file raises FileExistsError."""
    with path.open("wb" if overwrite else "xb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)


def load_graph(cache_dir: Path, name: str, graph_name: str | None = None) -> nx.Graph:
    """Load a standalone graph, or a graph within a batch.

    With a batch name and no graph_name, the batch's first graph is loaded.
    """
    if not valid_name(name):
        raise ValueError("Invalid graph or batch name.")

    if graph_name is not None:
        if not valid_name(graph_name):
            raise ValueError("Invalid graph name.")
        return read_graph(cache_dir / name / f"{graph_name}{GRAPH_SUFFIX}")

    standalone = cache_dir / f"{name}{GRAPH_SUFFIX}"
    if standalone.is_file():
        return read_graph(standalone)

    batch_path = cache_dir / name
    if not batch_path.is_dir():
        raise FileNotFoundError(f"No graph or batch named {name!r}.")

    files = graph_files(batch_path)
    if not files:
        raise FileNotFoundError(f"Batch {name!r} contains no graphs.")

    return read_graph(files[0])
