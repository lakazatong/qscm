from argparse import Namespace

from qscm.config import CACHE_DIR
from qscm.visualization.main import run_visualizer


def main(args: Namespace) -> int:
    run_visualizer(CACHE_DIR)
    return 0


def register_parser(subparsers) -> None:
    parser = subparsers.add_parser(
        "visualize",
        help="Browse cached graphs and graph batches.",
    )
    parser.set_defaults(func=main)
