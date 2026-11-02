from __future__ import annotations

import pytest

from qscm.generator import REGIMES, RandomGraphGenerator, Regime
from qscm.generator.data import SampledModel


def test_every_regime_is_a_parameter_dag() -> None:
    for regimes in REGIMES.values():
        assert all(isinstance(regime, Regime) for regime in regimes.values())


@pytest.mark.parametrize("model", tuple(REGIMES))
def test_all_models_generate_across_sizes(model: str) -> None:
    generator = RandomGraphGenerator(seed=732)
    for n in (3, 4, 8, 15):
        graph = generator.generate(n, model)
        assert graph.number_of_nodes() == n
        assert graph.graph["model"] == model
        assert graph.graph["parameters"]["regime"] in (*REGIMES[model], "custom")


@pytest.mark.parametrize(("model", "n"), [(model, 20) for model in REGIMES])
def test_each_declared_regime_can_be_sampled(model: str, n: int) -> None:
    # Every named regime is feasible for these test sizes.
    for regime_name in REGIMES[model]:
        if regime_name == "custom":
            continue
        graph = RandomGraphGenerator(seed=12).generate(
            n, model, SampledModel(parameters={"regime": regime_name})
        )
        assert graph.graph["parameters"]["regime"] == regime_name


def test_uniform_custom_sbm_matrix_retains_probability_metadata() -> None:
    base = SampledModel(args={"sizes": [5, 5], "p": [[0.3, 0.1], [0.1, 0.3]]})
    graph = RandomGraphGenerator(seed=9).generate(10, "stochastic_block", base)
    assert graph.graph["parameters"]["regime"] == "custom"
    assert graph.graph["parameters"]["p_in"] == 0.3
    assert graph.graph["parameters"]["p_out"] == 0.1


def test_nonuniform_sbm_matrix_is_marked_custom() -> None:
    base = SampledModel(args={"sizes": [5, 5], "p": [[0.3, 0.1], [0.1, 0.4]]})
    graph = RandomGraphGenerator(seed=9).generate(10, "stochastic_block", base)
    assert graph.graph["parameters"]["regime"] == "custom"
    assert "p_in" not in graph.graph["parameters"]
    assert graph.graph["parameters"]["p_out"] == 0.1
