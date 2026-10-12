import argparse
import json

import numpy as np
from scipy.linalg import helmert

from qscm.cache import graph_files, read_graph, valid_name
from qscm.config import CACHE_DIR
from qscm.data import Vector, require_digraph
from qscm.fingerprint import VECTOR_BOUNDS, fingerprint_vectors, graph_fingerprint
from qscm.geometry import barycenter, distance_statistics, hypervolume


def geometry(args: argparse.Namespace) -> None:
    batch_path = CACHE_DIR / args.batch_name

    if not valid_name(args.batch_name) or not batch_path.is_dir():
        raise SystemExit(f"Batch not found: {batch_path}")

    paths = graph_files(batch_path)

    if not paths:
        raise SystemExit(f"No graph files found in {batch_path}")

    histograms: dict[str, list[Vector]] = {name: [] for name in VECTOR_BOUNDS}

    for path in paths:
        graph = read_graph(path)
        if require_digraph(graph):
            vectors = fingerprint_vectors(graph_fingerprint(graph))

            for name, vector in zip(VECTOR_BOUNDS, vectors, strict=True):
                histograms[name].append(vector)

    results = {}

    for name, vectors in histograms.items():
        points = np.asarray(vectors, dtype=np.float64)
        center: Vector = barycenter(points).tolist()

        # Normalized histograms lie in the sum-to-one hyperplane.
        # Helmert coordinates preserve distances and intrinsic volume
        # while removing the redundant dimension.
        basis = helmert(points.shape[1], full=False)
        intrinsic_points = points @ basis.T

        try:
            volume = hypervolume(intrinsic_points)
            volume_error = None
        except ValueError as exc:
            volume = None
            volume_error = str(exc)

        results[name] = {
            "dimensions": points.shape[1],
            "graphs": len(points),
            "hypervolume": volume,
            "hypervolume_error": volume_error,
            "barycenter": center,
            "distances": distance_statistics(points, center),
        }

    print(
        json.dumps(
            {
                "batch": args.batch_name,
                "graphs": len(paths),
                "histograms": results,
            },
            indent=2,
        )
    )


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "compute",
        help="Compute graph-batch metrics",
    )
    commands = parser.add_subparsers(dest="compute_command", required=True)

    geometry_parser = commands.add_parser(
        "geometry",
        help="Compute geometry for each fingerprint histogram",
    )
    geometry_parser.add_argument("batch_name")
    geometry_parser.set_defaults(func=geometry)
