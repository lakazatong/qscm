from __future__ import annotations

import random
from collections.abc import Callable, Mapping
from types import ModuleType
from typing import Any

from . import (
    barabasi_albert,
    erdos_renyi,
    gnm,
    random_regular,
    random_tree,
    stochastic_block,
    watts_strogatz,
)
from .data import ModelSpec, Regime, SampledModel, Sampler


def _resolve_model(
    model_name: str,
    regimes: Mapping[str, Callable[..., Regime]],
    supplied: Mapping[str, Any],
    rng: random.Random,
    requested_regime: str | None,
) -> tuple[str, dict[str, Any]]:

    has_model_parameters = bool(supplied.keys() - {"n"})

    if requested_regime is not None and has_model_parameters:
        raise ValueError("A regime cannot be combined with explicit model parameters.")

    if requested_regime is not None:
        if not isinstance(requested_regime, str) or requested_regime not in regimes:
            raise ValueError(
                f"Unknown {model_name} regime {requested_regime!r}; expected one of "
                f"{tuple(name for name in regimes if name != 'custom')}."
            )
        if requested_regime == "custom":
            raise ValueError(
                "The custom regime is selected automatically from model parameters."
            )
        regime_name = requested_regime
        regime = regimes[regime_name]()
    elif has_model_parameters:
        regime_name = "custom"
        try:
            regime = regimes[regime_name]()
        except KeyError as exc:
            raise ValueError(
                f"No custom parameter definition exists for {model_name}."
            ) from exc
    else:
        available = tuple(
            (regime_name, get_regime())
            for regime_name, get_regime in regimes.items()
            if regime_name != "custom"
        )
        if not available:
            raise ValueError(f"No named {model_name} regime is defined.")
        regime_name, regime = rng.choice(available)

    values = regime.resolve_regime(supplied, rng=rng)
    return regime_name, values


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
    base: SampledModel | None,
    *,
    arg_names: tuple[str, ...] = (),
    kwarg_names: tuple[str, ...] = (),
    parameter_names: tuple[str, ...] = (),
) -> dict[str, Any]:
    supplied: dict[str, Any] = {}
    if base is None:
        return supplied

    base_args = base.args or {}
    base_kwargs = base.kwargs or {}
    base_parameters = base.parameters or {}

    unknown_groups = (
        (set(base_args) - {*arg_names}, "arguments"),
        (set(base_kwargs) - {*kwarg_names}, "keyword arguments"),
        (set(base_parameters) - {"regime", *parameter_names}, "parameters"),
    )
    for unknown, label in unknown_groups:
        if unknown:
            raise ValueError(f"Unknown base {label}: {sorted(unknown)}.")

    for obj, ref in ((base_args, arg_names), (base_parameters, parameter_names)):
        supplied.update(
            {name: obj[name] for name in ref if name in obj and obj[name] is not None}
        )

    return supplied


def get_sample(module: ModuleType) -> Sampler:
    def sampler(
        n: int,
        rng: random.Random,
        *,
        base: SampledModel | None = None,
        mockup: bool = False,
    ) -> SampledModel:
        module_args_keys = tuple(module.ARGS.keys())
        module_kwargs_keys = tuple(module.KWARGS.keys())
        module_params_keys = tuple(module.PARAMS.keys())

        supplied = _collect_base_values(
            base,
            arg_names=module_args_keys,
            kwarg_names=module_kwargs_keys,
            parameter_names=module_params_keys,
        )
        if "n" in supplied:
            raise ValueError(
                "n from the base model is overwritten by the n argument of the sampler, use it instead"
            )
        supplied["n"] = n

        regime_name, values = (
            (None, supplied)
            if mockup
            else _resolve_model(
                module.__name__,
                module.REGIMES,
                supplied,
                rng,
                None if base is None else base.parameters.get("regime", None),
            )
        )

        def fill_up(obj, ref):
            for name, arg in ref.items():
                if "getter" not in arg:
                    obj[name] = values.get(name, None)
            for name, arg in ref.items():
                if "getter" in arg:
                    try:
                        obj[name] = arg["getter"](values)
                    except ValueError:
                        pass

        args = {}
        fill_up(args, module.ARGS)
        kwargs = {"seed": rng}
        fill_up(kwargs, module.KWARGS)
        parameters = {"regime": regime_name}
        fill_up(parameters, module.PARAMS)

        return SampledModel(
            args=args,
            kwargs=kwargs,
            parameters=parameters,
        )

    return sampler


MODELS = {
    "erdos_renyi": ModelSpec(
        nx_function=erdos_renyi.GENERATOR(),
        sample=get_sample(erdos_renyi),
        regimes=erdos_renyi.REGIMES,
    ),
    "gnm": ModelSpec(
        nx_function=gnm.GENERATOR(),
        sample=get_sample(gnm),
        regimes=gnm.REGIMES,
    ),
    "barabasi_albert": ModelSpec(
        nx_function=barabasi_albert.GENERATOR(),  # "barabasi_albert_graph",
        sample=get_sample(barabasi_albert),
        regimes=barabasi_albert.REGIMES,
    ),
    "watts_strogatz": ModelSpec(
        nx_function=watts_strogatz.GENERATOR(),  # "watts_strogatz_graph",
        sample=get_sample(watts_strogatz),
        regimes=watts_strogatz.REGIMES,
    ),
    "random_regular": ModelSpec(
        nx_function=random_regular.GENERATOR(),  # "random_regular_graph",
        sample=get_sample(random_regular),
        regimes=random_regular.REGIMES,
    ),
    "random_tree": ModelSpec(
        nx_function=random_tree.GENERATOR(),  # "random_labeled_tree",
        sample=get_sample(random_tree),
        regimes=random_tree.REGIMES,
    ),
    "stochastic_block": ModelSpec(
        nx_function=stochastic_block.GENERATOR(),  # "stochastic_block_model",
        sample=get_sample(stochastic_block),
        regimes=stochastic_block.REGIMES,
    ),
}

__all__ = ["Regime", "SampledModel"]
