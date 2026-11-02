from __future__ import annotations

import math
import random
from collections.abc import Callable, Mapping
from numbers import Integral, Real
from typing import Any

from .parameter_dag import InsufficientInformation, ParameterDAG


class Regime(ParameterDAG):
    """A self-contained parameter DAG for one graph-generation regime."""

    def __init__(
        self,
        name: str,
        description: str,
        *,
        display: str | None = None,
        defined_for: Callable[[int], bool] | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.description = description
        self.display = display or description
        self._defined_for = defined_for

    def is_defined_for(self, n: int) -> bool:
        if self._defined_for is None:
            return True
        try:
            return bool(self._defined_for(n))
        except (TypeError, ValueError, OverflowError):
            return False

    def format(self) -> str:
        return self.display

    def resolve_regime(
        self,
        values: Mapping[str, Any],
        *,
        rng: random.Random,
    ) -> dict[str, Any]:
        unknown = values.keys() - self.parameter_names
        if unknown:
            raise ValueError(
                f"Unsupported parameter(s) for regime {self.name!r}: "
                f"{', '.join(sorted(unknown))}."
            )
        try:
            resolved = self.resolve(values, context={"_rng": rng})
        except InsufficientInformation:
            print(f"Resolving failed for regime {self.name}:")
            raise
        self.check(resolved)
        return resolved


def _rng(values: Mapping[str, Any]) -> random.Random:
    result = values["_rng"]
    if not isinstance(result, random.Random):
        raise TypeError("Regime sampling requires a random.Random in runtime context.")
    return result


def _validate_integer(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer; got {value!r}.")
    return int(value)


def _validate_n(value: object, values: Mapping[str, Any], *, minimum: int = 1) -> None:
    n = _validate_integer(value, name="n")
    if n < minimum:
        raise ValueError(f"n must be at least {minimum}; got {n}.")


def _validate_probability(
    value: object, values: Mapping[str, Any], *, name: str
) -> None:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValueError(
            f"{name} must be a finite probability in [0, 1]; got {value!r}."
        )


def _sample_interval(
    values: Mapping[str, Any],
    low: float,
    high: float,
    *,
    include_low: bool = True,
    include_high: bool = False,
    cap_at: str | None = None,
) -> float:
    upper = min(high, float(values[cap_at])) if cap_at is not None else high
    lower = low if include_low else math.nextafter(low, math.inf)
    if lower > upper:
        raise ValueError(
            f"No values are available in the regime interval [{lower}, {upper}]."
        )
    if lower == upper:
        return lower
    rng = _rng(values)
    if include_high or cap_at is not None:
        return rng.uniform(lower, upper)
    return lower + rng.random() * (upper - lower)


def _range_validator(
    low: float,
    high: float,
    *,
    include_low: bool = True,
    include_high: bool = False,
    name: str,
) -> Callable[[Any, dict[str, Any]], None]:
    def validate(value: Any, values: dict[str, Any]) -> None:
        if (
            not isinstance(value, Real)
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ValueError(f"{name} must be finite and numeric; got {value!r}.")
        number = float(value)
        if low == high:
            valid = number == low
        else:
            lower_ok = number >= low if include_low else number > low
            upper_ok = number <= high if include_high else number < high
            valid = lower_ok and upper_ok
        if not valid:
            left = "[" if include_low else "("
            right = "]" if include_high else ")"
            raise ValueError(
                f"{name} must be in {left}{low}, {high}{right}; got {value!r}."
            )

    return validate


def _validate_mean_out(value: Any, values: dict[str, Any]) -> None:
    maximum = int(values["n"]) - 1
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= maximum
    ):
        raise ValueError(
            f"mean_out must be finite and in [0, {maximum}]; got {value!r}."
        )


def _validate_er_branching_factor(value: Any, values: dict[str, Any]) -> None:
    if (
        not isinstance(value, Real)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0 <= float(value) <= int(values["n"])
    ):
        raise ValueError(
            f"branching_factor must be finite and in [0, {values['n']}]; got {value!r}."
        )


def _add_er_parameters(regime: Regime) -> None:
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=2)
    )
    regime.add(
        "p",
        validate=lambda value, values: _validate_probability(value, values, name="p"),
    )
    regime.add("branching_factor", validate=_validate_er_branching_factor)
    regime.add("mean_out", validate=_validate_mean_out)
    regime.equation("branching_factor = n * p")
    regime.equation("mean_out = (n - 1) * p")


def _custom_erdos_renyi_regime() -> Regime:
    regime = Regime("custom", "Any valid Erdős–Rényi parameters.")
    _add_er_parameters(regime)
    return regime


def _er_regime(
    name: str,
    description: str,
    display: str,
    low: float,
    high: float,
    *,
    include_low: bool = True,
    include_high: bool = False,
    cap_at_n: bool = False,
) -> Regime:
    regime = Regime(name, description, display=display)
    _add_er_parameters(regime)
    interval_validator = _range_validator(
        low,
        high,
        include_low=include_low,
        include_high=include_high,
        name="branching_factor",
    )

    def validate_branching_factor(value: Any, values: dict[str, Any]) -> None:
        interval_validator(value, values)
        _validate_er_branching_factor(value, values)

    regime.add(
        "branching_factor",
        sampler=lambda values: _sample_interval(
            values,
            low,
            high,
            include_low=include_low,
            include_high=include_high,
            cap_at="n" if cap_at_n else None,
        ),
        validate=validate_branching_factor,
        override=True,
        description="Erdős–Rényi branching factor n*p",
    )
    return regime


def _validate_gnm_m(value: Any, values: dict[str, Any]) -> None:
    m = _validate_integer(value, name="m")
    n = int(values["n"])
    maximum = n * (n - 1)
    if not 0 <= m <= maximum:
        raise ValueError(f"m must be in [0, {maximum}]; got {value!r}.")


def _add_gnm_parameters(regime: Regime) -> None:
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=2)
    )
    regime.add("m", validate=_validate_gnm_m)
    regime.add("mean_out", validate=_validate_mean_out)
    regime.equation("mean_out = m / n")


def _custom_gnm_regime() -> Regime:
    regime = Regime("custom", "Any valid G(n, m) parameters.")
    _add_gnm_parameters(regime)
    return regime


def _gnm_regime(name: str, description: str, display: str) -> Regime:
    regime = Regime(
        name,
        description,
        display=display,
        defined_for=(lambda n: n > 2) if name == "supercritical" else None,
    )
    _add_gnm_parameters(regime)

    def validate_m(value: Any, values: dict[str, Any]) -> None:
        _validate_gnm_m(value, values)
        m = int(value)
        if name == "subcritical" and m >= int(values["n"]):
            raise ValueError("Subcritical GNM requires m/n < 1.")
        if name == "critical" and m != int(values["n"]):
            raise ValueError("Critical GNM requires m/n = 1.")
        if name == "supercritical" and m <= int(values["n"]):
            raise ValueError("Supercritical GNM requires m/n > 1.")

    def sample_m(values: dict[str, Any]) -> int:
        n = int(values["n"])
        if name == "subcritical":
            return _rng(values).randrange(n)
        if name == "critical":
            return n
        maximum = n * (n - 1)
        if maximum <= n:
            raise ValueError(f"No supercritical m exists for n={n}.")
        return _rng(values).randrange(n + 1, maximum + 1)

    regime.add(
        "m",
        sampler=sample_m,
        validate=validate_m,
        override=True,
        description=display,
    )
    return regime


def _validate_ba_m(value: Any, values: dict[str, Any]) -> None:
    m = _validate_integer(value, name="m")
    if not 1 <= m < int(values["n"]):
        raise ValueError("Barabási–Albert m must satisfy 1 <= m < n.")


def _add_ba_parameters(regime: Regime) -> None:
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=2)
    )
    regime.add("m", validate=_validate_ba_m)


def _custom_barabasi_albert_regime() -> Regime:
    regime = Regime("custom", "Any valid Barabási–Albert attachment count.")
    _add_ba_parameters(regime)
    return regime


def _choice_regime(
    name: str,
    description: str,
    display: str,
    parameter: str,
    choices: tuple[int, ...],
    *,
    model: str,
) -> Regime:
    if model == "barabasi_albert":

        def validate_choice(value: Any, values: dict[str, Any]) -> None:
            _validate_ba_m(value, values)
            if int(value) not in choices:
                raise ValueError(
                    f"{parameter} must be one of {choices}; got {value!r}."
                )

        def feasible(n: int) -> tuple[int, ...]:
            return tuple(choice for choice in choices if choice < n)

        minimum_n = 2
    elif model == "random_regular":

        def validate_choice(value: Any, values: dict[str, Any]) -> None:
            _validate_rr_d(value, values)
            if int(value) not in choices:
                raise ValueError(
                    f"{parameter} must be one of {choices}; got {value!r}."
                )

        def feasible(n: int) -> tuple[int, ...]:
            return tuple(d for d in choices if 1 <= d < n and n * d % 2 == 0)

        minimum_n = 3
    else:
        raise ValueError(f"Unsupported choice-regime model {model!r}.")

    def sample_choice(values: dict[str, Any]) -> int:
        options = feasible(int(values["n"]))
        if not options:
            raise ValueError(
                f"No {parameter} choice from {choices} is feasible for n={values['n']}."
            )
        return _rng(values).choice(options)

    regime = Regime(
        name,
        description,
        display=display,
        defined_for=lambda n: n >= minimum_n and bool(feasible(n)),
    )
    regime.add(
        "n",
        validate=lambda value, values: _validate_n(value, values, minimum=minimum_n),
    )
    regime.add(
        parameter, sampler=sample_choice, validate=validate_choice, description=display
    )
    return regime


def _possible_ws_k(n: int) -> tuple[int, ...]:
    return tuple(range(2, min(8, n - 1) + 1, 2))


def _validate_ws_k(
    value: Any, values: dict[str, Any], *, maximum: int | None = None
) -> None:
    k = _validate_integer(value, name="k")
    n = int(values["n"])
    if k < 2 or k >= n or k % 2:
        raise ValueError(
            f"k must be even and satisfy 2 <= k < n; got {value!r} for n={n}."
        )
    if maximum is not None and k > maximum:
        raise ValueError(f"k must not exceed {maximum}; got {k}.")


def _add_ws_parameters(regime: Regime, *, named_maximum: int | None = None) -> None:
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=3)
    )
    regime.add(
        "k",
        validate=lambda value, values: _validate_ws_k(
            value, values, maximum=named_maximum
        ),
    )
    regime.add(
        "p",
        validate=lambda value, values: _validate_probability(value, values, name="p"),
    )


def _custom_watts_strogatz_regime() -> Regime:
    regime = Regime("custom", "Any valid Watts–Strogatz parameters.")
    _add_ws_parameters(regime)
    return regime


def _watts_strogatz_regime(
    name: str,
    description: str,
    display: str,
    low: float,
    high: float,
    *,
    include_low: bool = True,
    include_high: bool = False,
) -> Regime:
    regime = Regime(name, description, display=display)
    _add_ws_parameters(regime, named_maximum=8)
    regime.add(
        "k",
        sampler=lambda values: _rng(values).choice(_possible_ws_k(int(values["n"]))),
        validate=lambda value, values: _validate_ws_k(value, values, maximum=8),
        override=True,
    )
    regime.add(
        "p",
        sampler=lambda values: _sample_interval(
            values,
            low,
            high,
            include_low=include_low,
            include_high=include_high,
        ),
        validate=_range_validator(
            low,
            high,
            include_low=include_low,
            include_high=include_high,
            name="p",
        ),
        override=True,
        description="rewiring probability",
    )
    return regime


def _validate_rr_d(value: Any, values: dict[str, Any]) -> None:
    degree = _validate_integer(value, name="d")
    n = int(values["n"])
    if not 1 <= degree < n or n * degree % 2:
        raise ValueError(f"Degree {degree} is not feasible for n={n}.")


def _add_rr_parameters(regime: Regime) -> None:
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=3)
    )
    regime.add("d", validate=_validate_rr_d)


def _custom_random_regular_regime() -> Regime:
    regime = Regime("custom", "Any feasible regular degree.")
    _add_rr_parameters(regime)
    return regime


def _custom_random_tree_regime() -> Regime:
    regime = Regime("custom", "Any valid random-tree size.")
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    return regime


def _random_tree_regime() -> Regime:
    regime = Regime(
        "uniform_labeled_tree",
        "Uniformly sampled labeled trees.",
        display="uniform labeled tree",
    )
    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    return regime


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

    regime.add(
        "n", validate=lambda value, values: _validate_n(value, values, minimum=1)
    )
    regime.add("count", sample=sample_count, validate=validate_count, order=1)
    regime.add("sizes", sample=sample_sizes, validate=validate_sizes, order=2)
    regime.add("p", sample=sample_matrix, validate=_validate_block_matrix, order=3)
    regime.add(
        "p_in",
        sample=sample_p_in,
        validate=lambda value, values: _validate_probability(
            value, values, name="p_in"
        ),
        order=4,
    )
    regime.add(
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
        return _rng(values).randint(2, min(5, int(values["n"])))

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

    minimum_n = 2
    regime = Regime(
        name,
        description,
        display=display,
        defined_for=lambda n: n >= minimum_n,
    )
    regime.add(
        "n",
        validate=lambda value, values: _validate_n(value, values, minimum=minimum_n),
    )
    regime.add("count", sampler=sample_count, validate=validate_count, order=1)
    regime.add("sizes", sampler=sample_sizes, validate=validate_sizes, order=2)
    regime.add("p_in", sampler=sample_p_in, validate=validate_p_in, order=3)
    regime.add("p_out", sampler=sample_p_out, validate=validate_p_out, order=4)
    regime.add("p", sampler=sample_matrix, validate=validate_matrix, order=5)

    return regime


REGIMES: dict[str, dict[str, Regime]] = {
    "erdos_renyi": {
        "subcritical": _er_regime(
            "subcritical",
            "Below the branching threshold.",
            "branching_factor ∈ [0, 1)",
            0.0,
            1.0,
        ),
        "critical": _er_regime(
            "critical",
            "At the branching threshold.",
            "branching_factor = 1",
            1.0,
            1.0,
            include_high=True,
        ),
        "supercritical": _er_regime(
            "supercritical",
            "Above the branching threshold.",
            "branching_factor ∈ (1, n]",
            1.0,
            math.inf,
            include_low=False,
            cap_at_n=True,
        ),
        "custom": _custom_erdos_renyi_regime(),
    },
    "gnm": {
        "subcritical": _gnm_regime(
            "subcritical", "Below the branching threshold.", "m/n < 1"
        ),
        "critical": _gnm_regime("critical", "At the branching threshold.", "m/n = 1"),
        "supercritical": _gnm_regime(
            "supercritical", "Above the branching threshold.", "m/n > 1"
        ),
        "custom": _custom_gnm_regime(),
    },
    "barabasi_albert": {
        "tree_like": _choice_regime(
            "tree_like",
            "Minimal attachment; produces tree-like structure.",
            "m ∈ {1}",
            "m",
            (1,),
            model="barabasi_albert",
        ),
        "sparse_scale_free": _choice_regime(
            "sparse_scale_free",
            "Low attachment; favors hub formation.",
            "m ∈ {2, 3}",
            "m",
            (2, 3),
            model="barabasi_albert",
        ),
        "higher_attachment": _choice_regime(
            "higher_attachment",
            "More edges per arriving node.",
            "m ∈ {4, 5, 6}",
            "m",
            (4, 5, 6),
            model="barabasi_albert",
        ),
        "custom": _custom_barabasi_albert_regime(),
    },
    "watts_strogatz": {
        "regular_lattice": _watts_strogatz_regime(
            "regular_lattice",
            "Preserves the initial ring lattice.",
            "p = 0",
            0.0,
            0.0,
            include_high=True,
        ),
        "small_world": _watts_strogatz_regime(
            "small_world",
            "Low rewiring; retains local structure.",
            "p ∈ [0.001, 0.1)",
            0.001,
            0.1,
        ),
        "randomized": _watts_strogatz_regime(
            "randomized",
            "Increasingly random connectivity.",
            "p ∈ [0.1, 1]",
            0.1,
            1.0,
            include_high=True,
        ),
        "custom": _custom_watts_strogatz_regime(),
    },
    "random_regular": {
        "matching": _choice_regime(
            "matching",
            "Every node has degree 1.",
            "d ∈ {1}",
            "d",
            (1,),
            model="random_regular",
        ),
        "cycles": _choice_regime(
            "cycles",
            "Every node has degree 2.",
            "d ∈ {2}",
            "d",
            (2,),
            model="random_regular",
        ),
        "moderate_degree": _choice_regime(
            "moderate_degree",
            "Every node has degree 3 or 4.",
            "d ∈ {3, 4}",
            "d",
            (3, 4),
            model="random_regular",
        ),
        "higher_degree": _choice_regime(
            "higher_degree",
            "Every node has degree 5 or 6.",
            "d ∈ {5, 6}",
            "d",
            (5, 6),
            model="random_regular",
        ),
        "custom": _custom_random_regular_regime(),
    },
    "random_tree": {
        "uniform_labeled_tree": _random_tree_regime(),
        "custom": _custom_random_tree_regime(),
    },
    "stochastic_block": {
        "weak_assortative": _stochastic_block_regime(
            "weak_assortative",
            "Within-block probability modestly exceeds between-block probability.",
            "p_in ∈ [0.15, 0.4], p_out/p_in ∈ [0.4, 0.7]",
            (0.15, 0.4),
            p_out_ratio=(0.4, 0.7),
        ),
        "strong_assortative": _stochastic_block_regime(
            "strong_assortative",
            "Within-block probability greatly exceeds between-block probability.",
            "p_in ∈ [0.35, 0.7], p_out ∈ [0.01, 0.08]",
            (0.35, 0.7),
            p_out=(0.01, 0.08),
        ),
        "near_uniform": _stochastic_block_regime(
            "near_uniform",
            "Within-block and between-block probabilities are similar.",
            "p_in ∈ [0.05, 0.6], p_out/p_in ∈ [0.9, 1.1]",
            (0.05, 0.6),
            p_out_ratio=(0.9, 1.1),
        ),
        "disassortative": _stochastic_block_regime(
            "disassortative",
            "Between-block probability exceeds within-block probability.",
            "p_in ∈ [0.01, 0.08], p_out ∈ [0.2, 0.5]",
            (0.01, 0.08),
            p_out=(0.2, 0.5),
        ),
        "custom": _custom_stochastic_block_regime(),
    },
}


def get_regimes(model: str) -> Mapping[str, Regime]:
    try:
        return REGIMES[model]
    except KeyError as exc:
        raise ValueError(f"Unknown graph model {model!r}.") from exc
