import random

import networkx as nx
import pytest

from qscm.generator.data import SampledModel
from qscm.generator.models import MODELS
from qscm.generator.parameter_dag import InsufficientInformation
from qscm.generator.regimes import get_regimes
from qscm.generator.samplers import (
    barabasi_albert,
    erdos_renyi,
    gnm,
    random_regular,
    random_tree,
    stochastic_block,
    watts_strogatz,
)

SAMPLERS = {
    "erdos_renyi": erdos_renyi,
    "gnm": gnm,
    "barabasi_albert": barabasi_albert,
    "watts_strogatz": watts_strogatz,
    "random_regular": random_regular,
    "random_tree": random_tree,
    "stochastic_block": stochastic_block,
}

assert SAMPLERS.keys() == MODELS.keys()


@pytest.mark.parametrize("model_name", SAMPLERS.keys())
def test_default_selection_never_chooses_custom(model_name):
    sampled = SAMPLERS[model_name](20, random.Random(123))
    assert sampled.parameters["regime"] != "custom"


def test_erdos_renyi_custom_deduces_all_related_parameters():
    by_probability = erdos_renyi(10, random.Random(1), SampledModel(args={"p": 0.2}))
    assert by_probability.args["p"] == pytest.approx(0.2)
    assert by_probability.parameters["branching_factor"] == pytest.approx(2)
    assert by_probability.parameters["mean_out"] == pytest.approx(1.8)

    by_branching_factor = erdos_renyi(
        10, random.Random(1), SampledModel(parameters={"branching_factor": 2})
    )
    assert by_branching_factor.args["p"] == pytest.approx(0.2)
    assert by_branching_factor.parameters["mean_out"] == pytest.approx(1.8)

    by_mean_out = erdos_renyi(
        10, random.Random(1), SampledModel(parameters={"mean_out": 1.8})
    )
    assert by_mean_out.args["p"] == pytest.approx(0.2)
    assert by_mean_out.parameters["branching_factor"] == pytest.approx(2)


def test_gnm_custom_deduces_between_m_and_mean_out():
    by_m = gnm(10, random.Random(1), SampledModel(args={"m": 20}))
    assert by_m.parameters["mean_out"] == pytest.approx(2)

    by_mean_out = gnm(10, random.Random(1), SampledModel(parameters={"mean_out": 2}))
    assert by_mean_out.args["m"] == 20


@pytest.mark.parametrize(
    ("sampler", "n", "base"),
    [
        (barabasi_albert, 10, SampledModel(args={"m": 4})),
        (watts_strogatz, 10, SampledModel(args={"k": 8, "p": 0.4})),
        (random_regular, 10, SampledModel(args={"d": 8})),
        (
            stochastic_block,
            10,
            SampledModel(
                args={
                    "sizes": [2, 3, 5],
                    "p": [[0.1, 0.2, 0.3], [0.2, 0.4, 0.5], [0.3, 0.5, 0.6]],
                }
            ),
        ),
    ],
)
def test_custom_regimes_only_validate_supplied_parameters(sampler, n, base):
    sampled = sampler(n, random.Random(2), base)
    assert sampled.parameters["regime"] == "custom"


def test_watts_strogatz_custom_requires_both_parameters():
    with pytest.raises(InsufficientInformation):
        watts_strogatz(10, random.Random(2), SampledModel(args={"k": 4}))


def test_stochastic_block_custom_requires_sizes_and_matrix():
    with pytest.raises(InsufficientInformation):
        stochastic_block(10, random.Random(2), SampledModel(args={"sizes": [5, 5]}))


def test_stochastic_block_custom_accepts_arbitrary_symmetric_matrix():
    sampled = stochastic_block(
        5,
        random.Random(2),
        SampledModel(args={"sizes": [2, 3], "p": [[0.1, 0.7], [0.7, 0.9]]}),
    )
    assert sampled.args["p"] == [[0.1, 0.7], [0.7, 0.9]]
    assert sampled.parameters == {
        "regime": "custom",
        "count": 2,
        "p_out": 0.7,
    }


def test_stochastic_block_custom_rejects_asymmetric_matrix():
    with pytest.raises(ValueError, match="symmetric"):
        stochastic_block(
            4,
            random.Random(2),
            SampledModel(args={"sizes": [2, 2], "p": [[0.1, 0.2], [0.3, 0.4]]}),
        )


@pytest.mark.parametrize(
    ("sampler", "n", "base"),
    [
        (
            erdos_renyi,
            10,
            SampledModel(args={"p": 0.2}, parameters={"regime": "critical"}),
        ),
        (gnm, 10, SampledModel(args={"m": 10}, parameters={"regime": "critical"})),
        (
            barabasi_albert,
            10,
            SampledModel(args={"m": 1}, parameters={"regime": "tree_like"}),
        ),
        (
            watts_strogatz,
            10,
            SampledModel(args={"k": 4, "p": 0.2}, parameters={"regime": "randomized"}),
        ),
        (
            random_regular,
            10,
            SampledModel(args={"d": 2}, parameters={"regime": "cycles"}),
        ),
    ],
)
def test_regime_and_model_parameters_are_rejected(sampler, n, base):
    with pytest.raises(ValueError, match="cannot be combined"):
        sampler(n, random.Random(4), base)


def test_custom_cannot_be_requested_manually():
    with pytest.raises(ValueError, match="selected automatically"):
        barabasi_albert(
            10, random.Random(1), SampledModel(parameters={"regime": "custom"})
        )


def test_regime_applicability_matches_its_parameter_constraints():
    regimes = get_regimes("random_regular")
    assert not regimes["higher_degree"].is_defined_for(3)
    assert regimes["matching"].is_defined_for(4)

    regimes = get_regimes("barabasi_albert")
    assert not regimes["higher_attachment"].is_defined_for(4)
    assert regimes["tree_like"].is_defined_for(2)


def test_base_node_count_must_match_requested_node_count():
    with pytest.raises(ValueError, match="Base model has n=5"):
        barabasi_albert(10, random.Random(1), SampledModel(args={"n": 5, "m": 2}))


@pytest.mark.parametrize("model_name", SAMPLERS.keys())
def test_named_regimes_still_sample_their_own_parameters(model_name):
    sampler = SAMPLERS[model_name]

    for regime_name in get_regimes(model_name):
        if regime_name == "custom":
            continue

        sampled = sampler(
            20,
            random.Random(42),
            SampledModel(parameters={"regime": regime_name}),
        )

        assert sampled.parameters["regime"] == regime_name


def test_er_custom_rejects_inconsistent_equation_values():
    with pytest.raises(ValueError, match="Equation"):
        erdos_renyi(
            10,
            random.Random(1),
            SampledModel(
                args={"p": 0.2},
                parameters={"branching_factor": 3, "mean_out": 1.8},
            ),
        )


def test_gnm_custom_rejects_inconsistent_equation_values():
    with pytest.raises(ValueError, match="Equation"):
        gnm(
            10,
            random.Random(1),
            SampledModel(args={"m": 20}, parameters={"mean_out": 3}),
        )


def test_custom_stochastic_block_rejects_invalid_probability():
    with pytest.raises(ValueError, match="probability"):
        stochastic_block(
            4,
            random.Random(1),
            SampledModel(args={"sizes": [2, 2], "p": [[0.1, 1.2], [1.2, 0.1]]}),
        )


def test_custom_random_regular_has_no_arbitrary_degree_cap():
    sampled = random_regular(20, random.Random(1), SampledModel(args={"d": 18}))
    assert sampled.args["d"] == 18


def test_custom_watts_strogatz_has_no_named_sampling_cap():
    sampled = watts_strogatz(
        20, random.Random(1), SampledModel(args={"k": 18, "p": 0.5})
    )
    assert sampled.args["k"] == 18


@pytest.mark.parametrize(
    ("model", "networkx_function"),
    [
        ("erdos_renyi", nx.gnp_random_graph),
        ("gnm", nx.gnm_random_graph),
        ("barabasi_albert", nx.barabasi_albert_graph),
        ("watts_strogatz", nx.watts_strogatz_graph),
        ("random_regular", nx.random_regular_graph),
        ("random_tree", nx.random_labeled_tree),
        ("stochastic_block", nx.stochastic_block_model),
    ],
)
def test_every_available_named_regime_builds_a_networkx_graph(model, networkx_function):
    sampler = SAMPLERS[model]
    for name, regime in get_regimes(model).items():
        if name == "custom" or not regime.is_defined_for(20):
            continue
        sampled = sampler(
            20, random.Random(31), SampledModel(parameters={"regime": name})
        )
        graph = networkx_function(**sampled.args, **sampled.kwargs)
        assert graph.number_of_nodes() == 20
