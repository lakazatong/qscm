import math
import random
from collections.abc import Callable, Mapping
from numbers import Integral, Real
from typing import Any


def _rng(values: Mapping[str, Any]) -> random.Random:
    result = values["_rng"]
    if not isinstance(result, random.Random):
        raise TypeError("Regime sampling requires a random.Random in runtime context.")
    return result


def _validate_integer(value: object, *, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer; got {value!r}.")
    return int(value)


def _validate_n(value: object, values: Mapping[str, Any], *, minimum: int) -> None:
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
