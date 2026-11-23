# sampler
from __future__ import annotations

import math
import random
from numbers import Integral
from typing import Any

from .data import Regime
from .utils.parameter_dag import InsufficientInformation
from .utils.regime import (
    _rng,
    _sample_interval,
    _validate_integer,
    _validate_n,
    _validate_probability,
)


def _validate_block_sizes(value: Any, values: dict[str, Any]) -> None:
    if (
        not isinstance(value, (list, tuple))
        or not value
        or any(
            isinstance(size, bool) or not isinstance(size, Integral) or size < 1
            for size in value
        )
        or sum(value) != int(values["n"])
    ):
        raise ValueError("sizes must contain positive integers summing to n.")


def _validate_block_matrix(value: Any, values: dict[str, Any]) -> None:
    sizes = values["sizes"]
    count = len(sizes)
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(
            "p must be a square len(sizes)-by-len(sizes) probability matrix."
        )
    if any(not isinstance(row, (list, tuple)) or len(row) != count for row in value):
        raise ValueError(
            "p must be a square len(sizes)-by-len(sizes) probability matrix."
        )
    for i, row in enumerate(value):
        for j, probability in enumerate(row):
            _validate_probability(probability, values, name=f"p[{i}][{j}]")
            if not math.isclose(
                float(probability), float(value[j][i]), rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError(
                    "p must be symmetric for an undirected stochastic block model."
                )


def _matrix_probability(
    matrix: Any,
    *,
    diagonal: bool,
    count: int,
) -> float:
    if (
        not isinstance(matrix, (list, tuple))
        or len(matrix) != count
        or any(
            not isinstance(row, (list, tuple)) or len(row) != count for row in matrix
        )
    ):
        raise ValueError("p must be a square count-by-count probability matrix.")

    entries = [
        float(matrix[i][j])
        for i in range(count)
        for j in range(count)
        if (i == j) == diagonal
    ]

    if not entries:
        raise ValueError("Cannot derive a probability from an empty matrix selection.")

    reference = entries[0]
    if not all(
        math.isclose(value, reference, rel_tol=0.0, abs_tol=1e-12) for value in entries
    ):
        label = "diagonal" if diagonal else "off-diagonal"
        raise ValueError(
            f"Cannot derive a single probability: p has non-uniform {label} entries."
        )

    return reference


def _custom_stochastic_block_regime() -> Regime:
    regime = Regime(
        "custom", "Any valid stochastic block sizes and probability matrix."
    )

    def sample_count(values: dict[str, Any]) -> int:
        if "sizes" in values:
            return len(values["sizes"])
        if "p" in values:
            return len(values["p"])
        raise InsufficientInformation

    def validate_count(value: Any, values: dict[str, Any]) -> None:
        count = _validate_integer(value, name="count")
        if not 1 <= count <= int(values["n"]):
            raise ValueError(f"count must satisfy 1 <= count <= n; got {count}.")

    def sample_sizes(values: dict[str, Any]) -> list[int]:
        n = int(values["n"])
        count = int(values["count"])
        sizes = [n // count] * count

        for i in range(n % count):
            sizes[i] += 1

        return sizes

    def validate_sizes(value: Any, values: dict[str, Any]) -> None:
        _validate_block_sizes(value, values)
        if len(value) != int(values["count"]):
            raise ValueError("The number of sizes must equal count.")

    def sample_probability(values: dict[str, Any], *, diagonal: bool) -> float:
        if "p" not in values:
            raise InsufficientInformation
        try:
            return _matrix_probability(
                values["p"],
                diagonal=diagonal,
                count=int(values["count"]),
            )
        except ValueError:
            return 0.0

    def sample_p_in(values: dict[str, Any]) -> float:
        return sample_probability(values, diagonal=True)

    def sample_p_out(values: dict[str, Any]) -> float:
        return sample_probability(values, diagonal=False)

    def sample_matrix(values: dict[str, Any]) -> list[list[float]]:
        if not {"count", "p_in", "p_out"} <= values.keys():
            raise InsufficientInformation

        count = int(values["count"])
        p_in = float(values["p_in"])
        p_out = float(values["p_out"])

        return [[p_in if i == j else p_out for j in range(count)] for i in range(count)]

    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    regime.add_variable("count", sample=sample_count, validate=validate_count, order=1)
    regime.add_variable("sizes", sample=sample_sizes, validate=validate_sizes, order=2)
    regime.add_variable(
        "p", sample=sample_matrix, validate=_validate_block_matrix, order=3
    )
    regime.add_variable(
        "p_in",
        sample=sample_p_in,
        validate=lambda value, values: _validate_probability(
            value, values, name="p_in"
        ),
        order=4,
    )
    regime.add_variable(
        "p_out",
        sample=sample_p_out,
        validate=lambda value, values: _validate_probability(
            value, values, name="p_out"
        ),
        order=5,
    )

    return regime


def _stochastic_block_regime(
    name: str,
    description: str,
    display: str,
    p_in: tuple[float, float],
    *,
    p_out: tuple[float, float] | None = None,
    p_out_ratio: tuple[float, float] | None = None,
) -> Regime:
    def validate_p_in(value: Any, values: dict[str, Any]) -> None:
        _validate_probability(value, values, name="p_in")
        if "p" in values:
            expected = matrix_probability(
                values["p"], diagonal=True, count=int(values["count"])
            )
            if not math.isclose(float(value), expected, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(
                    f"p_in={value!r} is inconsistent with p; expected {expected}."
                )
        if not p_in[0] <= float(value) <= p_in[1]:
            raise ValueError(f"p_in must be in {p_in}; got {value!r}.")

    def validate_p_out(value: Any, values: dict[str, Any]) -> None:
        _validate_probability(value, values, name="p_out")
        numeric = float(value)

        if "p" in values:
            expected = matrix_probability(
                values["p"], diagonal=False, count=int(values["count"])
            )
            if not math.isclose(float(value), expected, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError(
                    f"p_out={value!r} is inconsistent with p; expected {expected}."
                )

        if p_out is not None:
            if not p_out[0] <= numeric <= p_out[1]:
                raise ValueError(f"p_out must be in {p_out}; got {value!r}.")
            return

        assert p_out_ratio is not None
        within = float(values["p_in"])
        if within == 0:
            raise ValueError("p_in must be positive for a p_out/p_in ratio.")

        ratio = numeric / within
        if not p_out_ratio[0] <= ratio <= p_out_ratio[1]:
            raise ValueError(f"p_out/p_in must be in {p_out_ratio}; got {ratio!r}.")

    def matrix_probability(
        matrix: Any,
        *,
        diagonal: bool,
        count: int,
    ) -> float:
        if (
            not isinstance(matrix, (list, tuple))
            or len(matrix) != count
            or any(
                not isinstance(row, (list, tuple)) or len(row) != count
                for row in matrix
            )
        ):
            raise ValueError("p must be a square count-by-count probability matrix.")

        entries = [
            float(matrix[i][j])
            for i in range(count)
            for j in range(count)
            if (i == j) == diagonal
        ]

        if not entries:
            raise ValueError(
                "Cannot derive a probability from an empty matrix selection."
            )

        reference = entries[0]
        if not all(
            math.isclose(value, reference, rel_tol=0.0, abs_tol=1e-12)
            for value in entries
        ):
            label = "diagonal" if diagonal else "off-diagonal"
            raise ValueError(
                f"Cannot derive a single probability: "
                f"p has non-uniform {label} entries."
            )

        return reference

    def sample_count(values: dict[str, Any]) -> int:
        if "sizes" in values:
            return len(values["sizes"])
        if "p" in values:
            return len(values["p"])
        n = int(values["n"])
        return _rng(values).randint(2, max(2, math.isqrt(n)))

    def validate_count(value: Any, values: dict[str, Any]) -> None:
        count = _validate_integer(value, name="count")
        if not 2 <= count <= int(values["n"]):
            raise ValueError(f"count must satisfy 2 <= count <= n; got {count}.")

    def sample_sizes(values: dict[str, Any]) -> list[int]:
        n = int(values["n"])
        count = int(values["count"])
        sizes = [n // count] * count

        for i in range(n % count):
            sizes[i] += 1

        return sizes

    def validate_sizes(value: Any, values: dict[str, Any]) -> None:
        _validate_block_sizes(value, values)
        if len(value) != int(values["count"]):
            raise ValueError("The number of sizes must equal count.")

    def sample_p_in(values: dict[str, Any]) -> float:
        if "p" not in values:
            return _sample_interval(values, *p_in, include_high=True)

        try:
            return _matrix_probability(
                values["p"], diagonal=True, count=int(values["count"])
            )
        except ValueError:
            return 0.0

    def sample_p_out(values: dict[str, Any]) -> float:
        if "p" not in values:
            if p_out is not None:
                return _sample_interval(values, *p_out, include_high=True)

            assert p_out_ratio is not None
            within = float(values["p_in"])
            return within * _sample_interval(values, *p_out_ratio, include_high=True)

        try:
            return _matrix_probability(
                values["p"], diagonal=False, count=int(values["count"])
            )
        except ValueError:
            return 0.0

    def sample_matrix(values: dict[str, Any]) -> list[list[float]]:
        if not {"count", "p_in", "p_out"} <= values.keys():
            raise InsufficientInformation

        count = int(values["count"])
        p_in_value = float(values["p_in"])
        p_out_value = float(values["p_out"])

        return [
            [p_in_value if i == j else p_out_value for j in range(count)]
            for i in range(count)
        ]

    def validate_matrix(value: Any, values: dict[str, Any]) -> None:
        count = int(values["count"])

        if (
            not isinstance(value, (list, tuple))
            or len(value) != count
            or any(
                not isinstance(row, (list, tuple)) or len(row) != count for row in value
            )
        ):
            raise ValueError("p must be a square count-by-count probability matrix.")

        p_in_value = float(values["p_in"])
        p_out_value = float(values["p_out"])

        for i, row in enumerate(value):
            for j, probability in enumerate(row):
                _validate_probability(probability, values, name=f"p[{i}][{j}]")

                expected = p_in_value if i == j else p_out_value
                if not math.isclose(
                    float(probability),
                    expected,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                ):
                    raise ValueError(
                        f"p[{i}][{j}]={probability!r} is inconsistent "
                        f"with the regime's expected value {expected!r}."
                    )

    regime = Regime(name, description, display=display)
    regime.add_variable(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    regime.add_variable("count", sample=sample_count, validate=validate_count, order=1)
    regime.add_variable("sizes", sample=sample_sizes, validate=validate_sizes, order=2)
    regime.add_variable("p_in", sample=sample_p_in, validate=validate_p_in, order=3)
    regime.add_variable("p_out", sample=sample_p_out, validate=validate_p_out, order=4)
    regime.add_variable("p", sample=sample_matrix, validate=validate_matrix, order=5)

    return regime


ARGS = {
    "sizes": {},
    "p": {},
}
KWARGS = {}
PARAMS = {
    "count": {},
    "p_in": {
        "getter": lambda values: _matrix_probability(
            values.get("p", None),
            diagonal=True,
            count=values.get("count", 0),
        )
    },
    "p_out": {
        "getter": lambda values: _matrix_probability(
            values.get("p", None),
            diagonal=False,
            count=values.get("count", 0),
        )
    },
}

REGIMES = {
    "weak_assortative": lambda: _stochastic_block_regime(
        "weak_assortative",
        "Within-block probability modestly exceeds between-block probability.",
        "p_in ∈ [0.15, 0.4], p_out/p_in ∈ [0.4, 0.7]",
        (0.15, 0.4),
        p_out_ratio=(0.4, 0.7),
    ),
    "strong_assortative": lambda: _stochastic_block_regime(
        "strong_assortative",
        "Within-block probability greatly exceeds between-block probability.",
        "p_in ∈ [0.35, 0.7], p_out ∈ [0.01, 0.08]",
        (0.35, 0.7),
        p_out=(0.01, 0.08),
    ),
    "near_uniform": lambda: _stochastic_block_regime(
        "near_uniform",
        "Within-block and between-block probabilities are similar.",
        "p_in ∈ [0.05, 0.6], p_out/p_in ∈ [0.9, 1.1]",
        (0.05, 0.6),
        p_out_ratio=(0.9, 1.1),
    ),
    "disassortative": lambda: _stochastic_block_regime(
        "disassortative",
        "Between-block probability exceeds within-block probability.",
        "p_in ∈ [0.01, 0.08], p_out ∈ [0.2, 0.5]",
        (0.01, 0.08),
        p_out=(0.2, 0.5),
    ),
    "custom": lambda: _custom_stochastic_block_regime(),
}


def GENERATOR():
    import itertools
    import math

    import networkx as nx
    from networkx.utils import py_random_state

    @py_random_state(3)
    @nx._dispatchable(name="stochastic_block_generate", graphs=None, returns_graph=True)
    def generate(
        sizes, p, *, nodelist=None, selfloops=False, sparse=True, seed: random.Random
    ):
        if len(sizes) != len(p):
            raise nx.NetworkXException("'sizes' and 'p' do not match.")

        for row in p:
            if len(p) != len(row):
                raise nx.NetworkXException("'p' must be a square matrix.")

        for row in p:
            for prob in row:
                if prob < 0 or prob > 1:
                    raise nx.NetworkXException("Entries of 'p' not in [0,1].")

        if nodelist is not None:
            if len(nodelist) != sum(sizes):
                raise nx.NetworkXException("'nodelist' and 'sizes' do not match.")
            if len(nodelist) != len(set(nodelist)):
                raise nx.NetworkXException("nodelist contains duplicate.")
        else:
            nodelist = list(range(sum(sizes)))

        block_range = range(len(sizes))
        g = nx.DiGraph()
        block_iter = itertools.product(block_range, block_range)

        size_cumsum = [sum(sizes[0:x]) for x in range(len(sizes) + 1)]
        g.graph["partition"] = [
            set(nodelist[size_cumsum[x] : size_cumsum[x + 1]])
            for x in range(len(size_cumsum) - 1)
        ]

        for block_id, nodes in enumerate(g.graph["partition"]):
            for node in nodes:
                g.add_node(node, block=block_id)

        g.name = "stochastic_block_model"

        parts = g.graph["partition"]
        for i, j in block_iter:
            if i == j:
                if selfloops:
                    edges = itertools.product(parts[i], parts[i])
                else:
                    edges = itertools.permutations(parts[i], 2)
            else:
                edges = itertools.product(parts[i], parts[j])

            if sparse:
                if p[i][j] == 1:
                    for e in edges:
                        g.add_edge(*e)
                elif p[i][j] > 0:
                    while True:
                        try:
                            logrand = math.log(seed.random())
                            skip = math.floor(logrand / math.log(1 - p[i][j]))
                            next(itertools.islice(edges, skip, skip), None)
                            e = next(edges)
                            g.add_edge(*e)
                        except StopIteration:
                            break
            else:
                for e in edges:
                    if seed.random() < p[i][j]:
                        g.add_edge(*e)

        return g

    return generate
