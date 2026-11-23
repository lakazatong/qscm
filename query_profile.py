import argparse
import pstats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("function", nargs="?")
    parser.add_argument("--top", type=int)

    args = parser.parse_args()

    stats = pstats.Stats("profile.prof")
    total = stats.total_tt

    entries = sorted(
        stats.stats.items(),
        key=lambda item: item[1][2],
        reverse=True,
    )

    if args.top is not None:
        entries = entries[: args.top]
    elif args.function is not None:
        entries = [
            entry for entry in entries if args.function.lower() in entry[0][2].lower()
        ]
    else:
        parser.error("Specify --top N or a function name.")

    name_width = max(
        len(f"{filename}:{line} ({func})") for (filename, line, func), _ in entries
    )
    name_width = max(name_width, len("Function"))

    print(f"{'Function':<{name_width}} {'Self %':>9} {'Cum %':>9}")
    print("-" * (name_width + 22))

    for (filename, line, func), (_, nc, tt, ct, _) in entries:
        name = f"{filename}:{line} ({func})"
        print(f"{name:<{name_width}} {tt / total:>8.2%} {ct / total:>8.2%}")


if __name__ == "__main__":
    main()
