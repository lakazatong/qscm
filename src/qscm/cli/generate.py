import argparse
import json
import pickle
import random
import shutil
from argparse import Namespace
from pathlib import Path

from qscm.config import CACHE_DIR
from qscm.generator import (
    DEFAULT_MODELS,
    REGIMES,
    RandomGraphGenerator,
    SampledModel,
)

_SAMPLE_GROUPS = (
    "args",
    "kwargs",
    "parameters",
    "postprocess_kwargs",
)


def format_regime_help(model: str) -> str:
    return "\n".join(
        f"  {name:<22} {regime.format():<32} {regime.description}"
        for name, regime in REGIMES[model].items()
    )


def clear_cache(args: Namespace) -> int:
    path = Path(CACHE_DIR)

    if not path.exists():
        print("Cache directory does not exist.")
        return 0

    if not args.force:
        answer = input(f"Delete all cached batches in {path}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 0

    shutil.rmtree(path)
    print(f"Cleared cache: {path}")
    return 0


def cache_size(args: Namespace) -> int:
    path = Path(CACHE_DIR)

    if not path.exists():
        print("Cache directory does not exist.")
        return 0

    files = [file for file in path.rglob("*") if file.is_file()]
    total_bytes = sum(file.stat().st_size for file in files)
    disk_bytes = sum(file.stat().st_size for file in files)

    print(f"Cache: {path}")
    print(f"Graphs: {len(files):,}")
    print(f"Size: {total_bytes:,} bytes ({total_bytes / (1024**2):.2f} MiB)")
    print(f"Size on disk: {disk_bytes:,} bytes ({disk_bytes / (1024**2):.2f} MiB)")

    return 0


def _sample_defaults(model: str, n: int = 10) -> SampledModel:
    """Get a representative SampledModel to discover supported fields."""
    return DEFAULT_MODELS[model].sample(n, random.Random(0), None)


def _option_name(group: str, name: str) -> str:
    """Return the CLI spelling for a SampledModel field."""
    if group == "postprocess_kwargs":
        return f"--postprocess-{name.replace('_', '-')}"
    return f"--{name.replace('_', '-')}"


def _argument_type(default):
    if isinstance(default, bool):
        return bool
    if isinstance(default, (list, dict, tuple)):
        return json.loads
    if default is None:
        return str
    return type(default)


def _discover_fields(model: str):
    """Collect the CLI fields supported by one model."""
    sampled = _sample_defaults(model)
    fields = {}

    for group_name in _SAMPLE_GROUPS:
        group = getattr(sampled, group_name, None) or {}

        for name, default in group.items():
            if name in {"directed", "n"}:
                continue

            fields[(group_name, name)] = default

    return fields


def _add_model_options(parser: argparse.ArgumentParser, model: str) -> None:
    """Add only the options supported by the selected model."""
    fields = _discover_fields(model)

    for (group_name, name), default in fields.items():
        option = _option_name(group_name, name)

        if group_name == "parameters" and name == "regime":
            parser.add_argument(
                option,
                choices=sorted(REGIMES[model]),
            )
            parser.add_argument(
                "--list-regimes",
                action="store_true",
                help="List available regimes for this graph model and exit.",
            )
            continue

        parser.add_argument(
            option,
            dest=f"{name}",
            type=_argument_type(default),
            default=None,
            help=f"Override SampledModel.{group_name}[{name!r}]",
        )


def _make_base(args: argparse.Namespace, node_count: int) -> SampledModel:
    """Build a partial SampledModel from explicitly supplied CLI options."""
    defaults = _sample_defaults(args.model, node_count)
    overrides = {}

    for group_name in _SAMPLE_GROUPS:
        group_defaults = getattr(defaults, group_name, None) or {}
        group_overrides = {}

        for name in group_defaults:
            if name in {"directed", "n"}:
                continue

            value = getattr(args, name, None)

            if value is not None:
                group_overrides[name] = value

        overrides[group_name] = group_overrides

    base = SampledModel(
        args=overrides["args"],
        kwargs=overrides["kwargs"],
        parameters=overrides["parameters"],
        postprocess_kwargs=overrides["postprocess_kwargs"] or None,
    )

    # Validate the regime for this particular model.
    regime = base.parameters.get("regime")

    if regime is not None and regime not in REGIMES.get(args.model, {}):
        allowed = ", ".join(REGIMES.get(args.model, {}))
        raise ValueError(
            f"Regime {regime!r} is not supported by {args.model!r}. "
            f"Choose from: {allowed or '(no registered regimes)'}"
        )

    # Reject overrides that the selected model does not support.
    for group_name in _SAMPLE_GROUPS:
        supported = getattr(defaults, group_name, None) or {}
        supplied = getattr(base, group_name, None) or {}
        unknown = supplied.keys() - supported.keys()

        if unknown:
            raise ValueError(
                f"Unsupported {group_name} overrides for {args.model!r}: "
                f"{', '.join(sorted(unknown))}"
            )

    return base


def graph_main(args: argparse.Namespace) -> int:
    if args.list_regimes:
        print(format_regime_help(args.model))
        return 0

    if args.node_count is None:
        raise ValueError("node_count is required unless --list-regimes is used.")

    if args.model is None:
        generator = RandomGraphGenerator(seed=args.rng_seed)
        graph = generator.generate(args.node_count)
    else:
        base = _make_base(args, args.node_count)
        generator = RandomGraphGenerator(
            seed=args.rng_seed,
            models={args.model: DEFAULT_MODELS[args.model]},
        )
        graph = generator.generate(args.node_count, model=args.model, base=base)

    output_path = Path(CACHE_DIR) / f"{graph.graph['name']}.graph"

    if output_path.exists() and not args.force:
        raise FileExistsError(
            f"{output_path} already exists; pass --force to overwrite it."
        )

    with output_path.open("wb") as file:
        pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    print(output_path)
    return 0


def batch_main(args: Namespace) -> int:
    if args.list_regimes:
        print(format_regime_help(args.model))
        return 0

    if args.count < 1:
        raise ValueError("Graph count must be at least 1.")

    path = Path(CACHE_DIR) / args.name

    if path.exists() and not args.force and not args.append:
        raise FileExistsError(
            f"Graph batch already exists: {path}. "
            "Use --force to replace it or --append to extend it."
        )

    if path.exists() and args.force:
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)

    minimum, maximum = args.node_range
    node_rng = random.Random(args.rng_seed)

    models = (
        {args.model: DEFAULT_MODELS[args.model]} if args.model is not None else None
    )
    generator = RandomGraphGenerator(seed=args.rng_seed, models=models)

    for _ in range(args.count):
        node_count = node_rng.randint(minimum, maximum)

        if args.model is None:
            graph = generator.generate(node_count)
        else:
            base = _make_base(args, node_count)
            graph = generator.generate(node_count, model=args.model, base=base)

        graph_path = path / f"{graph.graph['name']}.graph"

        with graph_path.open("xb") as file:
            pickle.dump(graph, file, protocol=pickle.HIGHEST_PROTOCOL)

    node_description = (
        f"{minimum} nodes each"
        if minimum == maximum
        else f"{minimum}-{maximum} nodes each"
    )
    model_description = args.model or "random models"

    print(
        f"Generated batch {args.name!r}: {args.count} graphs, "
        f"{node_description} (model: {model_description})."
    )
    print(f"Saved to {path}")

    return 0


def parse_node_range(value: str) -> tuple[int, int]:
    """Parse N or MIN-MAX into an inclusive node-count range."""
    try:
        parts = value.split("-")

        if len(parts) == 1:
            minimum = maximum = int(parts[0])
        elif len(parts) == 2:
            minimum, maximum = map(int, parts)
        else:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid node range {value!r}. Expected N or MIN-MAX."
        ) from None

    if minimum < 3 or maximum < minimum:
        raise argparse.ArgumentTypeError("Node counts must satisfy 3 <= MIN <= MAX.")

    return minimum, maximum


def register_graph_parser(commands) -> None:
    parser = commands.add_parser("graph", help="Generate one graph.")
    subparsers = parser.add_subparsers(dest="model_command", required=True)

    def add_common_options(p):
        p.add_argument(
            "node_count",
            nargs="?",
            type=int,
            help="Number of nodes.",
        )
        p.add_argument(
            "--rng-seed",
            type=int,
            default=None,
            help="Seed for random parameter sampling.",
        )
        p.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Overwrite an existing graph file.",
        )

    for model in DEFAULT_MODELS:
        model_parser = subparsers.add_parser(model)
        add_common_options(model_parser)
        _add_model_options(model_parser, model)
        model_parser.set_defaults(func=graph_main, model=model)

    # Random selection uses model defaults and exposes no model options.
    random_parser = subparsers.add_parser(
        "random", help="Randomly select a model and use its default parameters."
    )
    add_common_options(random_parser)
    random_parser.set_defaults(func=graph_main, model=None)


def register_batch_parser(commands) -> None:
    parser = commands.add_parser("batch", help="Generate a batch of graphs.")
    subparsers = parser.add_subparsers(dest="model_command", required=True)

    def add_common_options(p):
        p.add_argument("name", nargs="?", help="Name used for the batch directory.")
        p.add_argument(
            "count", nargs="?", type=int, help="Number of graphs to generate."
        )
        p.add_argument(
            "node_range",
            nargs="?",
            type=parse_node_range,
            metavar="N[-M]",
            help="Node count or inclusive minimum-maximum range.",
        )
        p.add_argument(
            "--rng-seed",
            type=int,
            default=None,
            help="Seed for random parameter and node count sampling.",
        )
        group = p.add_mutually_exclusive_group()
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

    for model in DEFAULT_MODELS:
        model_parser = subparsers.add_parser(model)
        add_common_options(model_parser)
        _add_model_options(model_parser, model)
        model_parser.set_defaults(func=batch_main, model=model)

    # Random selection uses model defaults and exposes no model options.
    random_parser = subparsers.add_parser(
        "random", help="Randomly select a model and use its default parameters."
    )
    add_common_options(random_parser)
    random_parser.set_defaults(func=batch_main, model=None)


def register_cache_parser(commands) -> None:
    parser = commands.add_parser("cache", help="Manage the graph cache.")
    subcommands = parser.add_subparsers(dest="cache_command", required=True)

    size_parser = subcommands.add_parser(
        "size", help="Show the combined size of cached graphs."
    )
    size_parser.set_defaults(func=cache_size)

    clear_parser = subcommands.add_parser(
        "clear", help="Delete cached graphs and empty directories."
    )
    clear_parser.add_argument(
        "-f", "--force", action="store_true", help="Skip confirmation."
    )
    clear_parser.set_defaults(func=clear_cache)


def register_parser(subparsers) -> None:
    """Register all generation-related commands under 'generate'."""
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate graphs, batches, or manage the cache.",
    )
    generate_subparsers = generate_parser.add_subparsers(
        dest="generate_command",
        required=True,
    )

    register_graph_parser(generate_subparsers)
    register_batch_parser(generate_subparsers)
    register_cache_parser(generate_subparsers)
