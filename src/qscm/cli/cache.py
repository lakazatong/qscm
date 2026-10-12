import argparse
import shutil

from qscm.cache import GRAPH_SUFFIX
from qscm.config import CACHE_DIR


def size(args: argparse.Namespace) -> int:
    if not CACHE_DIR.exists():
        print("Cache directory does not exist.")
        return 0

    files = [file for file in CACHE_DIR.rglob("*") if file.is_file()]
    graphs = sum(1 for file in files if file.suffix == GRAPH_SUFFIX)
    batches = sum(
        1
        for directory in CACHE_DIR.iterdir()
        if directory.is_dir()
        and any(
            file.is_file() and file.suffix == GRAPH_SUFFIX
            for file in directory.iterdir()
        )
    )
    total_bytes = sum(file.stat().st_size for file in files)

    print(f"Cache: {CACHE_DIR}")
    print(
        f"Standalone graphs: {sum(1 for file in CACHE_DIR.glob('*.graph') if file.is_file()):,}"
    )
    print(f"Batches: {batches:,}")
    print(f"Graphs: {graphs:,}")
    print(f"Files: {len(files):,}")
    print(f"Size: {total_bytes:,} bytes ({total_bytes / (1024**2):.2f} MiB)")

    return 0


def clear(args: argparse.Namespace) -> int:
    if not CACHE_DIR.exists():
        print("Cache directory does not exist.")
        return 0

    if not args.force:
        answer = input(f"Delete all cached data in {CACHE_DIR}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 0

    shutil.rmtree(CACHE_DIR)
    print(f"Cleared cache: {CACHE_DIR}")
    return 0


def register_parser(subparsers) -> None:
    parser = subparsers.add_parser("cache", help="Manage the shared cache.")
    commands = parser.add_subparsers(dest="cache_command", required=True)

    size_parser = commands.add_parser("size", help="Show cache contents and size.")
    size_parser.set_defaults(func=size)

    clear_parser = commands.add_parser("clear", help="Delete all cached data.")
    clear_parser.add_argument(
        "-f", "--force", action="store_true", help="Skip confirmation."
    )
    clear_parser.set_defaults(func=clear)
