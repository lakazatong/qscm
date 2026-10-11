from collections.abc import Iterable, Sequence

import numpy as np
import numpy.typing as npt
from scipy.spatial import ConvexHull, QhullError

Vector = Sequence[float]
Points = Iterable[Vector]


def _points_array(points: Points) -> npt.NDArray[np.float64]:
    array = np.asarray(list(points), dtype=np.float64)

    if array.ndim != 2 or array.shape[0] == 0 or array.shape[1] == 0:
        raise ValueError("Expected a non-empty collection of non-empty vectors.")

    if not np.isfinite(array).all():
        raise ValueError("Coordinates must be finite.")

    return array


def hypervolume(points: Points) -> float:
    """Compute the N-dimensional volume of the points' convex hull."""
    array = _points_array(points)
    count, dimension = array.shape

    if dimension == 1:
        return float(np.ptp(array[:, 0]))

    if count < dimension + 1:
        raise ValueError(
            f"At least {dimension + 1} points are required in {dimension}D."
        )

    if np.linalg.matrix_rank(array[1:] - array[0]) < dimension:
        return 0.0

    try:
        return float(ConvexHull(array).volume)
    except QhullError as exc:
        raise ValueError("Could not compute the convex hull.") from exc


def barycenter(points: Points) -> npt.NDArray[np.float64]:
    """Compute the arithmetic mean of the points' coordinates."""
    return np.mean(_points_array(points), axis=0)


def distance_statistics(
    points: Points,
    center: Vector,
) -> dict[str, float]:
    """Compute Euclidean distance statistics relative to a center."""
    array = _points_array(points)
    center_array = np.asarray(center, dtype=np.float64)

    if center_array.shape != (array.shape[1],):
        raise ValueError("Center dimension must match point dimension.")

    if not np.isfinite(center_array).all():
        raise ValueError("Center coordinates must be finite.")

    distances = np.linalg.norm(array - center_array, axis=1)

    return {
        "min": float(np.min(distances)),
        "max": float(np.max(distances)),
        "avg": float(np.mean(distances)),
        "median": float(np.median(distances)),
        "std": float(np.std(distances)),
    }
