import argparse

from .cli import compute, generate, visualize


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="qscm",
        description="Generate and visualize structural causal models.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    generate.register_parser(subparsers)
    visualize.register_parser(subparsers)
    compute.register_parser(subparsers)

    args = parser.parse_args()

    try:
        return args.func(args)
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        # User-facing problems (bad arguments, name clashes) get a message,
        # not a traceback.
        raise SystemExit(f"qscm: error: {exc}") from None


if __name__ == "__main__":
    raise SystemExit(main())
