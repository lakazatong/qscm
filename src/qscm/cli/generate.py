import pickle
import random
import shutil
from argparse import Namespace
from pathlib import Path

from qscm.config import CACHE_DIR
from qscm.generator import RandomGraphGenerator


def clear_cache(args: Namespace) -> int:
    cache_dir = Path(CACHE_DIR)
    if not cache_dir.exists():
        print("Cache is already empty.")
        return 0

    deleted = 0
    for path in cache_dir.rglob("*.graph"):
        if path.is_file():
            path.unlink()
            deleted += 1

    for path in sorted(cache_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()

    print(f"Cleared cache: deleted {deleted} graph files.")
    return 0


def cache_size(args: Namespace) -> int:
    cache_dir = Path(CACHE_DIR)
    graphs = (
        [path for path in cache_dir.rglob("*.graph") if path.is_file()]
        if cache_dir.exists()
        else []
    )

    total_size = sum(path.stat().st_size for path in graphs)
    total_disk_size = sum(
        getattr(path.stat(), "st_blocks", 0) * 512 or path.stat().st_size
        for path in graphs
    )

    def format_size(size: int) -> str:
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.2f} {unit}" if unit != "B" else f"{size} B"
            value /= 1024
        return f"{size} B"

    print(f"Graph files: {len(graphs)}")
    print(f"Combined file size: {format_size(total_size)}")
    print(f"Disk size: {format_size(total_disk_size)}")
    return 0


def parse_node_range(value: str) -> tuple[int, int]:
    try:
        parts = value.split("-")
        if len(parts) == 1:
            minimum = maximum = int(parts[0])
        elif len(parts) == 2:
            minimum, maximum = map(int, parts)
        else:
            raise ValueError
    except ValueError:
        raise ValueError(
            f"Invalid node range {value!r}. Expected N or MIN-MAX."
        ) from None

    if minimum < 3 or maximum < minimum:
        raise ValueError("Node counts must satisfy 3 <= MIN <= MAX.")

    return minimum, maximum


def batch_main(args: Namespace) -> int:
    if args.count < 1:
        print("Error: graph count must be at least 1.")
        return 2

    if args.model is not None and args.model not in RandomGraphGenerator.MODELS:
        print(f"Error: unknown model {args.model!r}.")
        return 2

    path = Path(CACHE_DIR) / args.name
    if path.exists() and not args.force and not args.append:
        raise FileExistsError(f"graph batch already exists: {path}")

    if path.exists() and args.force:
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)

    minimum, maximum = args.node_range
    node_rng = random.Random(args.seed)

    models = (args.model,) if args.model else None
    generator = RandomGraphGenerator(seed=args.seed, models=models)

    for _ in range(args.count):
        nodes = node_rng.randint(minimum, maximum)
        graph = generator.generate(nodes)
        graph_path = path / f"{graph.graph['name']}.graph"

        with graph_path.open("xb") as file:
            pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    node_description = (
        f"{minimum} nodes each"
        if minimum == maximum
        else f"{minimum}-{maximum} nodes each"
    )

    print(
        f"Generated batch '{args.name}': {args.count} graphs, "
        f"{node_description}"
        + (f" (model: {args.model})" if args.model else " (random models)")
        + "."
    )
    print(f"Saved to {path}")

    return 0


def graph_main(args: Namespace) -> int:
    if args.nodes < 3:
        print("Error: node count must be at least 3.")
        return 2

    generator = RandomGraphGenerator(seed=args.seed)
    graph = generator.generate(args.nodes)

    path = Path(CACHE_DIR) / f"{graph.graph['name']}.graph"

    if path.exists() and not args.force:
        raise FileExistsError(f"graph already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("wb" if args.force else "xb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    print(
        f"Generated '{graph.graph['name']}': "
        f"{graph.number_of_nodes()} nodes, "
        f"{graph.number_of_edges()} edges "
        f"(model: {graph.graph['model']})."
    )
    print(f"Saved to {path}")

    return 0


def register_graph_parser(commands) -> None:
    parser = commands.add_parser("graph", help="Generate a graph.")
    parser.add_argument("nodes", type=int, help="Number of nodes.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed.")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the graph if it already exists.",
    )
    parser.set_defaults(func=graph_main)


def register_batch_parser(commands) -> None:
    parser = commands.add_parser("batch", help="Generate a batch of graphs.")
    parser.add_argument("name", help="Name used for the batch directory.")
    parser.add_argument("count", type=int, help="Number of graphs to generate.")
    parser.add_argument(
        "node_range",
        type=parse_node_range,
        metavar="N[-M]",
        help="Number of nodes per graph, or inclusive minimum-maximum range.",
    )
    parser.add_argument(
        "--model",
        choices=RandomGraphGenerator.MODELS,
        default=None,
        help="Graph model to use. Defaults to random model selection.",
    )
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Replace the existing batch directory.",
    )
    group.add_argument(
        "-a",
        "--append",
        action="store_true",
        help="Append graphs to an existing batch directory.",
    )
    parser.set_defaults(func=batch_main)


def register_cache_parser(commands) -> None:
    parser = commands.add_parser("cache", help="Inspect or clear the graph cache.")
    subcommands = parser.add_subparsers(dest="cache_command", required=True)

    size_parser = subcommands.add_parser(
        "size", help="Show the combined size of cached graphs."
    )
    size_parser.set_defaults(func=cache_size)

    clear_parser = subcommands.add_parser(
        "clear", help="Delete cached graphs and empty directories."
    )
    clear_parser.set_defaults(func=clear_cache)


def register_parser(subparsers) -> None:
    parser = subparsers.add_parser("generate", help="Generate a random graph.")
    commands = parser.add_subparsers(dest="generate_command", required=True)

    register_graph_parser(commands)
    register_batch_parser(commands)
    register_cache_parser(commands)
