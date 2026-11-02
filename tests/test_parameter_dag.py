import random

import pytest

from qscm.generator.parameter_dag import (
    InsufficientInformation,
    ParameterDAG,
    ParameterError,
)
from qscm.generator.regimes import REGIMES


def test_resolve_deduces_in_both_directions_without_checking():
    dag = ParameterDAG()
    dag.add("x")
    dag.add("y")
    dag.equation("y = 2 * x")

    assert dag.resolve({"x": 3}) == {"x": 3, "y": 6}
    assert dag.resolve({"y": 8}) == {"x": 4, "y": 8}


def test_resolve_does_not_validate_result():
    dag = ParameterDAG()
    dag.add(
        "x", validate=lambda value, values: (_ for _ in ()).throw(ValueError("bad"))
    )

    result = dag.resolve({"x": 1})
    assert result == {"x": 1}
    with pytest.raises(ParameterError, match="Invalid variable 'x'"):
        dag.check(result)


def test_ambiguous_equations_are_rejected():
    dag = ParameterDAG()
    dag.add("x")
    with pytest.raises(ValueError, match="does not uniquely determine"):
        dag.equation("x**2 = 4")


def test_contradictory_equations_are_rejected_transactionally():
    dag = ParameterDAG()
    dag.add("x")
    dag.equation("x = 1")
    with pytest.raises(ValueError, match="contradictory"):
        dag.equation("x = 2")
    assert len(dag._equations) == 1


def test_sampling_retries_then_returns_to_deduction():
    dag = ParameterDAG()

    def sample_x(values):
        if "y" not in values:
            raise InsufficientInformation
        return values["y"] + 3

    dag.add("x", sample=sample_x)
    dag.add("y", sample=lambda values: 4, order=-1)
    dag.add("z")
    dag.equation("z = y + 1")

    assert dag.resolve({}) == {"x": 7, "y": 4, "z": 5}


def test_sampling_priority_and_unique_orders():
    dag = ParameterDAG()
    dag.add("first", sample=lambda values: "first", order=10)
    dag.add("second", sample=lambda values: "second", order=1)
    values = dag.resolve({})
    assert values == {"first": "first", "second": "second"}

    with pytest.raises(ValueError, match="already in use"):
        dag.add("third", sample=lambda values: "third", order=1)


def test_insufficient_information_is_propagated_when_sampling_stalls():
    dag = ParameterDAG()
    dag.add("x", sample=lambda values: (_ for _ in ()).throw(InsufficientInformation()))
    dag.add("y", sample=lambda values: (_ for _ in ()).throw(InsufficientInformation()))
    with pytest.raises(InsufficientInformation):
        dag.resolve({})


def test_variable_can_be_overridden_but_not_duplicated_by_default():
    dag = ParameterDAG()
    dag.add("x", sample=lambda values: 1)
    with pytest.raises(ValueError, match="already declared"):
        dag.add("x", sample=lambda values: 2)
    dag.add("x", sample=lambda values: 2, override=True)
    assert dag.resolve({}) == {"x": 2}


def test_regime_dags_resolve_and_check():
    for regimes in REGIMES.values():
        for get_regime in regimes.values():
            regime = get_regime()
            if regime.name == "custom":
                continue
            values = regime.resolve_regime({"n": 20}, rng=random.Random(4))
            # even tho resolve_regime checks itself
            regime.check(values)


def test_equation_and_variable_mutations_preserve_structure():
    dag = ParameterDAG()
    dag.add_variable("x")
    dag.add_variable("y", sample=lambda values: 3)
    dag.add_equation("y = x + 1")

    with pytest.raises(ValueError, match="still reference"):
        dag.remove_variable("x")

    dag.remove_equation("y = x + 1")
    dag.remove_variable("x")
    dag.add_variable("x", sample=lambda values: 2)
    assert dag.resolve({}) == {"x": 2, "y": 3}
