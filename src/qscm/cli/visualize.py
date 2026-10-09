from __future__ import annotations

import pickle
import re
from argparse import Namespace
from pathlib import Path

import networkx as nx

from qscm.config import CACHE_DIR
from qscm.plotting import plot_graph_fingerprint


def _graph_path(name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError(
            "Graph names must start with a letter or digit and contain "
            "only letters, digits, underscores, dots, and hyphens."
        )

    if name in {".", ".."}:
        raise ValueError("Invalid graph name.")

    cache_dir = Path(CACHE_DIR)

    graph_path = cache_dir / f"{name}.graph"
    if graph_path.is_file():
        return graph_path

    legacy_path = cache_dir / f"{name}.dag"
    if legacy_path.is_file():
        return legacy_path

    raise FileNotFoundError(f"No cached graph named '{name}' was found in {cache_dir}.")


def main(args: Namespace) -> int:
    try:
        path = _graph_path(args.name)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        return 1

    with path.open("rb") as file:
        graph = pickle.load(file)

    if not isinstance(graph, nx.Graph):
        print(f"Error: cached object at {path} is not a NetworkX graph.")
        return 1

    plot_graph_fingerprint(
        graph,
        title=graph.graph.get("name", args.name),
        show=True,
    )

    return 0


def register_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "visualize",
        help="Visualize a cached graph and its fingerprint.",
    )
    commands = parser.add_subparsers(dest="visualize_command", required=True)

    graph_parser = commands.add_parser(
        "graph",
        help="Visualize a graph.",
    )
    graph_parser.add_argument("name", help="Name of the cached graph.")
    graph_parser.set_defaults(func=main)
