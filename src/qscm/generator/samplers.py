from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from typing import Any

from .data import SampledModel
from .regimes import _matrix_probability, get_regimes


def _override(
    base: SampledModel | None,
    group: str,
    name: str,
    get_default: Callable[[], Any],
) -> Any:
    if base is not None:
        value = (getattr(base, group) or {}).get(name)
        if value is not None:
            return value
    return get_default()


def _collect_base_values(
    n: int,
    base: SampledModel | None,
    *,
    arg_names: tuple[str, ...] = (),
    kwarg_names: tuple[str, ...] = (),
    parameter_names: tuple[str, ...] = (),
    postprocess_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    supplied: dict[str, Any] = {"n": n}
    if base is None:
        return supplied

    args = base.args or {}
    kwargs = base.kwargs or {}
    parameters = base.parameters or {}
    postprocess_kwargs = base.postprocess_kwargs or {}

    if "n" in args and args["n"] != n:
        raise ValueError(f"Base model has n={args['n']}, but n={n} was requested.")

    unknown_groups = (
        (set(args) - {"n", *arg_names}, "arguments"),
        (set(kwargs) - {*kwarg_names, "directed"}, "keyword arguments"),
        (set(parameters) - {"regime", *parameter_names}, "parameters"),
        (
            set(postprocess_kwargs) - set(postprocess_names),
            "postprocessing keyword arguments",
        ),
    )
    for unknown, label in unknown_groups:
        if unknown:
            raise ValueError(f"Unsupported base {label}: {sorted(unknown)}.")

    supplied.update(
        {
            name: args[name]
            for name in arg_names
            if name in args and args[name] is not None
        }
    )
    supplied.update(
        {
            name: parameters[name]
            for name in parameter_names
            if name in parameters and parameters[name] is not None
        }
    )
    return supplied


def _resolve_model(
    model: str,
    supplied: Mapping[str, Any],
    rng: random.Random,
    base: SampledModel | None,
) -> tuple[str, dict[str, Any]]:
    regimes = get_regimes(model)
    requested = (base.parameters or {}).get("regime") if base is not None else None
    has_model_parameters = bool(supplied.keys() - {"n"})

    if requested is not None and has_model_parameters:
        raise ValueError("A regime cannot be combined with explicit model parameters.")

    if requested is not None:
        if not isinstance(requested, str) or requested not in regimes:
            raise ValueError(
                f"Unknown {model} regime {requested!r}; expected one of "
                f"{tuple(name for name in regimes if name != 'custom')}."
            )
        if requested == "custom":
            raise ValueError(
                "The custom regime is selected automatically from model parameters."
            )
        name = requested
        regime = regimes[name]()
    elif has_model_parameters:
        name = "custom"
        try:
            regime = regimes[name]()
        except KeyError as exc:
            raise ValueError(
                f"No custom parameter definition exists for {model}."
            ) from exc
    else:
        available = []
        for name, get_regime in regimes.items():
            regime = get_regime()
            if name != "custom" and regime.is_defined_for(int(supplied["n"])):
                available.append((name, regime))
        available = tuple(available)
        if not available:
            raise ValueError(
                f"No named {model} regime is defined for n={supplied['n']}."
            )
        name, regime = rng.choice(available)

    if not regime.is_defined_for(int(supplied["n"])):
        raise ValueError(f"Regime {name!r} is not defined for n={supplied['n']}.")

    values = regime.resolve_regime(supplied, rng=rng)
    return name, values


def _seeds(
    base: SampledModel | None,
    rng: random.Random,
    *,
    postprocess: bool,
) -> tuple[int, int | None]:
    nx_seed = _override(base, "kwargs", "seed", lambda: rng.randrange(2**32))
    orientation_seed = None
    if postprocess:
        orientation_seed = _override(
            base, "postprocess_kwargs", "seed", lambda: rng.randrange(2**32)
        )
    return nx_seed, orientation_seed


def erdos_renyi(
    n: int,
    rng: random.Random,
    base: SampledModel | None = None,
    *,
    mockup: bool = False,
) -> SampledModel:
    nx_seed, _ = _seeds(base, rng, postprocess=False)
    supplied = _collect_base_values(
        n,
        base,
        arg_names=("p",),
        kwarg_names=("seed",),
        parameter_names=("branching_factor", "mean_out"),
    )
    regime_name, values = (
        (None, {}) if mockup else _resolve_model("erdos_renyi", supplied, rng, base)
    )
    return SampledModel(
        args={"n": n, "p": values.get("p", None)},
        kwargs={"seed": nx_seed, "directed": True},
        parameters={
            "regime": regime_name,
            "branching_factor": values.get("branching_factor", None),
            "mean_out": values.get("mean_out", None),
        },
    )


def gnm(
    n: int,
    rng: random.Random,
    base: SampledModel | None = None,
    *,
    mockup: bool = False,
) -> SampledModel:
    nx_seed, _ = _seeds(base, rng, postprocess=False)
    supplied = _collect_base_values(
        n, base, arg_names=("m",), kwarg_names=("seed",), parameter_names=("mean_out",)
    )
    regime_name, values = (
        (None, {}) if mockup else _resolve_model("gnm", supplied, rng, base)
    )
    return SampledModel(
        args={"n": n, "m": values.get("m", None)},
        kwargs={"seed": nx_seed, "directed": True},
        parameters={"regime": regime_name, "mean_out": values.get("mean_out", None)},
    )


def barabasi_albert(
    n: int,
    rng: random.Random,
    base: SampledModel | None = None,
    *,
    mockup: bool = False,
) -> SampledModel:
    nx_seed, orientation_seed = _seeds(base, rng, postprocess=True)
    supplied = _collect_base_values(
        n, base, arg_names=("m",), kwarg_names=("seed",), postprocess_names=("seed",)
    )
    regime_name, values = (
        (None, {}) if mockup else _resolve_model("barabasi_albert", supplied, rng, base)
    )
    return SampledModel(
        args={"n": n, "m": values.get("m", None)},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime_name},
        postprocess_kwargs={"seed": orientation_seed},
    )


def watts_strogatz(
    n: int,
    rng: random.Random,
    base: SampledModel | None = None,
    *,
    mockup: bool = False,
) -> SampledModel:
    nx_seed, orientation_seed = _seeds(base, rng, postprocess=True)
    supplied = _collect_base_values(
        n,
        base,
        arg_names=("k", "p"),
        kwarg_names=("seed",),
        postprocess_names=("seed",),
    )
    regime_name, values = (
        (None, {}) if mockup else _resolve_model("watts_strogatz", supplied, rng, base)
    )
    return SampledModel(
        args={"n": n, "k": values.get("k", None), "p": values.get("p", None)},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime_name},
        postprocess_kwargs={"seed": orientation_seed},
    )


def random_regular(
    n: int,
    rng: random.Random,
    base: SampledModel | None = None,
    *,
    mockup: bool = False,
) -> SampledModel:
    nx_seed, orientation_seed = _seeds(base, rng, postprocess=True)
    supplied = _collect_base_values(
        n, base, arg_names=("d",), kwarg_names=("seed",), postprocess_names=("seed",)
    )
    regime_name, values = (
        (None, {}) if mockup else _resolve_model("random_regular", supplied, rng, base)
    )
    return SampledModel(
        args={"n": n, "d": values.get("d", None)},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime_name},
        postprocess_kwargs={"seed": orientation_seed},
    )


def random_tree(
    n: int,
    rng: random.Random,
    base: SampledModel | None = None,
    *,
    mockup: bool = False,
) -> SampledModel:
    nx_seed, orientation_seed = _seeds(base, rng, postprocess=True)
    supplied = _collect_base_values(
        n, base, kwarg_names=("seed",), postprocess_names=("seed",)
    )
    regime_name, values = (
        (None, {}) if mockup else _resolve_model("random_tree", supplied, rng, base)
    )
    return SampledModel(
        args={"n": values.get("n", None)},
        kwargs={"seed": nx_seed},
        parameters={"regime": regime_name},
        postprocess_kwargs={"seed": orientation_seed},
    )


def stochastic_block(
    n: int, rng: random.Random, base: SampledModel | None = None, *, mockup=False
) -> SampledModel:
    nx_seed, orientation_seed = _seeds(base, rng, postprocess=True)

    supplied = _collect_base_values(
        n,
        base,
        arg_names=("sizes", "p"),
        kwarg_names=("seed",),
        parameter_names=("count", "p_in", "p_out"),
        postprocess_names=("seed",),
    )

    regime_name, values = (
        (None, {})
        if mockup
        else _resolve_model("stochastic_block", supplied, rng, base)
    )

    parameters = {"regime": regime_name, "count": values.get("count", None)}

    for key, diagonal in (("p_in", True), ("p_out", False)):
        try:
            parameters[key] = _matrix_probability(
                values.get("p", None),
                diagonal=diagonal,
                count=values.get("count", 0),
            )
        except ValueError:
            pass

    return SampledModel(
        args={"sizes": values.get("sizes", None), "p": values.get("p", None)},
        kwargs={"seed": nx_seed},
        parameters=parameters,
        postprocess_kwargs={"seed": orientation_seed},
    )
