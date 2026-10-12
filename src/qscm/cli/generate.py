import argparse
import json
import random
import shutil
from argparse import Namespace
from functools import cache
from typing import Any

from qscm.cache import GRAPH_SUFFIX, save_graph, valid_name
from qscm.config import CACHE_DIR, ensure_cache_dir
from qscm.data import SampledModel
from qscm.generator import DEFAULT_MODELS, REGIMES, RandomGraphGenerator

_SAMPLE_GROUPS = (
    "args",
    "kwargs",
    "parameters",
    "postprocess_kwargs",
)
_RESERVED_FIELDS = {"directed", "n"}


# --- Option discovery -------------------------------------------------------
#
# Every model's sampler returns a SampledModel. We sample one with default
# settings to learn which fields the model supports, and expose each field as
# a CLI option.


@cache
def _discover_fields(model: str) -> dict[tuple[str, str], Any]:
    """Map (group, name) -> default value for every option a model supports."""
    sampled = DEFAULT_MODELS[model].sample(10, random.Random(0), None)
    fields = {}

    for group in _SAMPLE_GROUPS:
        for name, default in (getattr(sampled, group, None) or {}).items():
            if name not in _RESERVED_FIELDS:
                fields[(group, name)] = default

    return fields


def _dest(group: str, name: str) -> str:
    # Namespaced by group: kwargs["seed"] and postprocess_kwargs["seed"] are
    # different options and must not share an argparse destination.
    return f"{group}__{name}"


def _option_name(group: str, name: str) -> str:
    """Return the CLI spelling for a SampledModel field."""
    prefix = "--postprocess-" if group == "postprocess_kwargs" else "--"
    return prefix + name.replace("_", "-")


def _argument_type(default):
    if isinstance(default, bool):
        return bool
    if isinstance(default, (list, dict, tuple)):
        return json.loads
    if default is None:
        return str
    return type(default)


def _add_model_options(parser: argparse.ArgumentParser, model: str) -> None:
    """Add only the options supported by the selected model."""
    for (group, name), default in _discover_fields(model).items():
        option = _option_name(group, name)
        dest = _dest(group, name)

        if group == "parameters" and name == "regime":
            parser.add_argument(
                option,
                dest=dest,
                choices=sorted(REGIMES[model]),
                help="Parameter regime to sample from (see --list-regimes).",
            )
            parser.add_argument(
                "--list-regimes",
                action="store_true",
                help="List available regimes for this graph model and exit.",
            )
            continue

        parser.add_argument(
            option,
            dest=dest,
            type=_argument_type(default),
            default=None,
            help=f"Override SampledModel.{group}[{name!r}]",
        )


def _make_base(args: Namespace) -> SampledModel:
    """Build a partial SampledModel from explicitly supplied CLI options."""
    overrides: dict[str, dict[str, Any]] = {group: {} for group in _SAMPLE_GROUPS}

    for group, name in _discover_fields(args.model):
        value = getattr(args, _dest(group, name), None)
        if value is not None:
            overrides[group][name] = value

    return SampledModel(
        args=overrides["args"],
        kwargs=overrides["kwargs"],
        parameters=overrides["parameters"],
        postprocess_kwargs=overrides["postprocess_kwargs"] or None,
    )


# --- Helpers ----------------------------------------------------------------


def format_regime_help(model: str) -> str:
    return "\n".join(
        f"  {name:<22} {regime.format():<32} {regime.description}"
        for name, regime in REGIMES[model].items()
    )


def _require(args: Namespace, *names: str) -> None:
    missing = [name for name in names if getattr(args, name) is None]
    if missing:
        raise ValueError(
            f"Missing required argument(s): {', '.join(missing)} "
            "(optional only when using --list-regimes)."
        )


def _size_on_disk(path) -> int:
    stat = path.stat()
    blocks = getattr(stat, "st_blocks", None)  # POSIX only
    return blocks * 512 if blocks is not None else stat.st_size


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


# --- Commands ---------------------------------------------------------------


def clear_cache(args: Namespace) -> int:
    if not CACHE_DIR.exists():
        print("Cache directory does not exist.")
        return 0

    if not args.force:
        answer = input(f"Delete all cached batches in {CACHE_DIR}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 0

    shutil.rmtree(CACHE_DIR)
    print(f"Cleared cache: {CACHE_DIR}")
    return 0


def cache_size(args: Namespace) -> int:
    if not CACHE_DIR.exists():
        print("Cache directory does not exist.")
        return 0

    files = [file for file in CACHE_DIR.rglob("*") if file.is_file()]
    graphs = sum(1 for file in files if file.suffix == GRAPH_SUFFIX)
    total_bytes = sum(file.stat().st_size for file in files)
    disk_bytes = sum(_size_on_disk(file) for file in files)

    print(f"Cache: {CACHE_DIR}")
    print(f"Graphs: {graphs:,}")
    print(f"Size: {total_bytes:,} bytes ({total_bytes / (1024**2):.2f} MiB)")
    print(f"Size on disk: {disk_bytes:,} bytes ({disk_bytes / (1024**2):.2f} MiB)")

    return 0


def graph_main(args: Namespace) -> int:
    if getattr(args, "list_regimes", False):
        print(format_regime_help(args.model))
        return 0

    _require(args, "node_count")

    if args.model is None:
        generator = RandomGraphGenerator(seed=args.rng_seed)
        graph = generator.generate(args.node_count)
    else:
        generator = RandomGraphGenerator(
            seed=args.rng_seed,
            models={args.model: DEFAULT_MODELS[args.model]},
        )
        graph = generator.generate(
            args.node_count, model=args.model, base=_make_base(args)
        )

    output_path = ensure_cache_dir() / f"{graph.graph['name']}{GRAPH_SUFFIX}"

    if output_path.exists() and not args.force:
        raise FileExistsError(
            f"{output_path} already exists; pass --force to overwrite it."
        )

    save_graph(graph, output_path)
    print(output_path)
    return 0


def batch_main(args: Namespace) -> int:
    if getattr(args, "list_regimes", False):
        print(format_regime_help(args.model))
        return 0

    _require(args, "name", "count", "node_range")

    if not valid_name(args.name):
        raise ValueError(
            f"Invalid batch name {args.name!r}: use letters, digits, '_', '-' or '.'."
        )

    if args.count < 1:
        raise ValueError("Graph count must be at least 1.")

    batch_path = ensure_cache_dir() / args.name

    if batch_path.exists() and not (args.force or args.append):
        raise FileExistsError(
            f"Graph batch already exists: {batch_path}. "
            "Use --force to replace it or --append to extend it."
        )

    if batch_path.exists() and args.force:
        shutil.rmtree(batch_path)

    batch_path.mkdir(parents=True, exist_ok=True)

    minimum, maximum = args.node_range
    node_rng = random.Random(args.rng_seed)

    models = {args.model: DEFAULT_MODELS[args.model]} if args.model else None
    generator = RandomGraphGenerator(seed=args.rng_seed, models=models)
    base = _make_base(args) if args.model else None

    for _ in range(args.count):
        node_count = node_rng.randint(minimum, maximum)
        graph = generator.generate(node_count, model=args.model, base=base)
        save_graph(
            graph, batch_path / f"{graph.graph['name']}{GRAPH_SUFFIX}", overwrite=False
        )

    node_description = (
        f"{minimum} nodes each"
        if minimum == maximum
        else f"{minimum}-{maximum} nodes each"
    )

    print(
        f"Generated batch {args.name!r}: {args.count} graphs, "
        f"{node_description} (model: {args.model or 'random models'})."
    )
    print(f"Saved to {batch_path}")
    return 0


# --- Parsers ----------------------------------------------------------------


def _add_graph_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("node_count", nargs="?", type=int, help="Number of nodes.")
    parser.add_argument(
        "--rng-seed",
        type=int,
        default=None,
        help="Seed for random parameter sampling.",
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="Overwrite an existing graph file."
    )


def _add_batch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", nargs="?", help="Name used for the batch directory.")
    parser.add_argument(
        "count", nargs="?", type=int, help="Number of graphs to generate."
    )
    parser.add_argument(
        "node_range",
        nargs="?",
        type=parse_node_range,
        metavar="N[-M]",
        help="Node count or inclusive minimum-maximum range.",
    )
    parser.add_argument(
        "--rng-seed",
        type=int,
        default=None,
        help="Seed for random parameter and node count sampling.",
    )
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


def _add_model_subparsers(subparsers, add_common_options, func) -> None:
    for model in DEFAULT_MODELS:
        model_parser = subparsers.add_parser(model)
        add_common_options(model_parser)
        _add_model_options(model_parser, model)
        model_parser.set_defaults(func=func, model=model)

    # Random selection uses model defaults and exposes no model options.
    random_parser = subparsers.add_parser(
        "random", help="Randomly select a model and use its default parameters."
    )
    add_common_options(random_parser)
    random_parser.set_defaults(func=func, model=None)


def register_graph_parser(commands) -> None:
    parser = commands.add_parser("graph", help="Generate one graph.")
    subparsers = parser.add_subparsers(dest="model_command", required=True)
    _add_model_subparsers(subparsers, _add_graph_options, graph_main)


def register_batch_parser(commands) -> None:
    parser = commands.add_parser("batch", help="Generate a batch of graphs.")
    subparsers = parser.add_subparsers(dest="model_command", required=True)
    _add_model_subparsers(subparsers, _add_batch_options, batch_main)


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
