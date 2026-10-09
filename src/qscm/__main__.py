import argparse

from qscm.cli import generate, visualize


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="qscm",
        description="Generate and visualize structural causal models.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    generate.register_parser(subparsers)
    visualize.register_parser(subparsers)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
