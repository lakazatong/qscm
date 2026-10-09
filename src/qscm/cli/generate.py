from __future__ import annotations

import pickle
import re
from argparse import Namespace
from pathlib import Path

from qscm.config import CACHE_DIR
from qscm.generator import RandomGraphGenerator


def _graph_path(name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise ValueError(
            "Graph names must start with a letter or digit and contain "
            "only letters, digits, underscores, dots, and hyphens."
        )

    if name in {".", ".."}:
        raise ValueError("Invalid graph name.")

    return Path(CACHE_DIR) / f"{name}.graph"


def main(args: Namespace) -> int:
    try:
        path = _graph_path(args.name)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2

    if args.nodes < 1:
        print("Error: node count must be at least 1.")
        return 2

    if path.exists() and not args.force:
        raise FileExistsError(f"graph already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    generator = RandomGraphGenerator(seed=args.seed)
    graph = generator.generate(args.nodes)

    graph.graph["name"] = args.name

    with path.open("wb" if args.force else "xb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    model = graph.graph.get("model", generator.last_model)
    print(
        f"Generated '{args.name}': {graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges (model: {model})."
    )
    print(f"Saved to {path}")

    return 0


def register_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "generate",
        help="Generate a random graph.",
    )
    commands = parser.add_subparsers(dest="generate_command", required=True)

    graph_parser = commands.add_parser(
        "graph",
        help="Generate a graph.",
    )
    graph_parser.add_argument("name", help="Name used to save the graph.")
    graph_parser.add_argument(
        "nodes",
        type=int,
        help="Number of nodes.",
    )
    graph_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed.",
    )
    graph_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the graph if it already exists.",
    )
    graph_parser.set_defaults(func=main)
