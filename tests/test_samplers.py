import random

import networkx as nx
import pytest

from qscm.models import MODELS, Sampler
from qscm.models.data import SampledModel
from qscm.models.utils.parameter_dag import InsufficientInformation


@pytest.mark.parametrize("model_name", MODELS.keys())
def test_default_selection_never_chooses_custom(model_name):
    sampled = MODELS[model_name].sample(20, base=SampledModel(), rng=random.Random(123))
    assert sampled.parameters["regime"] != "custom"


def test_erdos_renyi_custom_deduces_all_related_parameters():
    sample = MODELS["erdos_renyi"].sample
    by_probability = sample(
        10, base=SampledModel(args={"p": 0.2}), rng=random.Random(1)
    )
    assert by_probability.args["p"] == pytest.approx(0.2)
    assert by_probability.parameters["branching_factor"] == pytest.approx(2)
    assert by_probability.parameters["mean_out"] == pytest.approx(1.8)

    by_branching_factor = sample(
        10,
        base=SampledModel(parameters={"branching_factor": 2}),
        rng=random.Random(1),
    )
    assert by_branching_factor.args["p"] == pytest.approx(0.2)
    assert by_branching_factor.parameters["mean_out"] == pytest.approx(1.8)

    by_mean_out = sample(
        10,
        base=SampledModel(parameters={"mean_out": 1.8}),
        rng=random.Random(1),
    )
    assert by_mean_out.args["p"] == pytest.approx(0.2)
    assert by_mean_out.parameters["branching_factor"] == pytest.approx(2)


def test_gnm_custom_deduces_between_m_and_mean_out():
    sample = MODELS["gnm"].sample
    by_m = sample(10, base=SampledModel(args={"m": 20}), rng=random.Random(1))
    assert by_m.parameters["mean_out"] == pytest.approx(2)

    by_mean_out = sample(
        10, base=SampledModel(parameters={"mean_out": 2}), rng=random.Random(1)
    )
    assert by_mean_out.args["m"] == 20


@pytest.mark.parametrize(
    ("sampler", "n", "base"),
    [
        (MODELS["barabasi_albert"].sample, 10, SampledModel(args={"m": 4})),
        (MODELS["watts_strogatz"].sample, 10, SampledModel(args={"k": 8, "p": 0.4})),
        (MODELS["random_regular"].sample, 10, SampledModel(args={"d": 8})),
        (
            MODELS["stochastic_block"].sample,
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
def test_custom_regimes_only_validate_supplied_parameters(
    sampler: Sampler, n: int, base: SampledModel
):
    sampled = sampler(n, base=base, rng=random.Random(2))
    assert sampled.parameters["regime"] == "custom"


def test_watts_strogatz_custom_requires_both_parameters():
    sample = MODELS["watts_strogatz"].sample
    with pytest.raises(InsufficientInformation):
        sample(10, base=SampledModel(args={"k": 4}), rng=random.Random(2))


def test_stochastic_block_custom_requires_sizes_and_matrix():
    sample = MODELS["stochastic_block"].sample
    with pytest.raises(InsufficientInformation):
        sample(10, base=SampledModel(args={"sizes": [5, 5]}), rng=random.Random(2))


def test_stochastic_block_custom_accepts_arbitrary_symmetric_matrix():
    sample = MODELS["stochastic_block"].sample
    sampled = sample(
        5,
        base=SampledModel(args={"sizes": [2, 3], "p": [[0.1, 0.7], [0.7, 0.9]]}),
        rng=random.Random(2),
    )
    assert sampled.args["p"] == [[0.1, 0.7], [0.7, 0.9]]
    assert sampled.parameters == {
        "regime": "custom",
        "count": 2,
        "p_out": 0.7,
    }


def test_stochastic_block_custom_rejects_asymmetric_matrix():
    sample = MODELS["stochastic_block"].sample
    with pytest.raises(ValueError, match="symmetric"):
        sample(
            4,
            base=SampledModel(args={"sizes": [2, 2], "p": [[0.1, 0.2], [0.3, 0.4]]}),
            rng=random.Random(2),
        )


@pytest.mark.parametrize(
    ("sampler", "n", "base"),
    [
        (
            MODELS["erdos_renyi"].sample,
            10,
            SampledModel(args={"p": 0.2}, parameters={"regime": "critical"}),
        ),
        (
            MODELS["gnm"].sample,
            10,
            SampledModel(args={"m": 10}, parameters={"regime": "critical"}),
        ),
        (
            MODELS["barabasi_albert"].sample,
            10,
            SampledModel(args={"m": 1}, parameters={"regime": "tree_like"}),
        ),
        (
            MODELS["watts_strogatz"].sample,
            10,
            SampledModel(args={"k": 4, "p": 0.2}, parameters={"regime": "randomized"}),
        ),
        (
            MODELS["random_regular"].sample,
            10,
            SampledModel(args={"d": 2}, parameters={"regime": "cycles"}),
        ),
    ],
)
def test_regime_and_model_parameters_are_rejected(
    sampler: Sampler, n: int, base: SampledModel
):
    with pytest.raises(ValueError, match="cannot be combined"):
        sampler(n, base=base, rng=random.Random(4))


def test_custom_cannot_be_requested_manually():
    sample = MODELS["barabasi_albert"].sample
    with pytest.raises(ValueError, match="selected automatically"):
        sample(
            10,
            base=SampledModel(parameters={"regime": "custom"}),
            rng=random.Random(1),
        )


@pytest.mark.parametrize("model_name", MODELS.keys())
def test_named_regimes_still_sample_their_own_parameters(model_name):
    sampler = MODELS[model_name].sample

    for regime_name in MODELS[model_name].regimes:
        if regime_name == "custom":
            continue

        sampled = sampler(
            20,
            base=SampledModel(parameters={"regime": regime_name}),
            rng=random.Random(42),
        )

        assert sampled.parameters["regime"] == regime_name


def test_er_custom_rejects_inconsistent_equation_values():
    sample = MODELS["erdos_renyi"].sample
    with pytest.raises(ValueError, match="Equation"):
        sample(
            10,
            base=SampledModel(
                args={"p": 0.2},
                parameters={"branching_factor": 3, "mean_out": 1.8},
            ),
            rng=random.Random(1),
        )


def test_gnm_custom_rejects_inconsistent_equation_values():
    sample = MODELS["gnm"].sample
    with pytest.raises(ValueError, match="Equation"):
        sample(
            10,
            base=SampledModel(args={"m": 20}, parameters={"mean_out": 3}),
            rng=random.Random(1),
        )


def test_custom_stochastic_block_rejects_invalid_probability():
    sample = MODELS["stochastic_block"].sample
    with pytest.raises(ValueError, match="probability"):
        sample(
            4,
            base=SampledModel(args={"sizes": [2, 2], "p": [[0.1, 1.2], [1.2, 0.1]]}),
            rng=random.Random(1),
        )


def test_custom_random_regular_has_no_arbitrary_degree_cap():
    sample = MODELS["random_regular"].sample
    sampled = sample(20, base=SampledModel(args={"d": 18}), rng=random.Random(1))
    assert sampled.args["d"] == 18


def test_custom_watts_strogatz_has_no_named_sampling_cap():
    sample = MODELS["watts_strogatz"].sample
    sampled = sample(
        20, base=SampledModel(args={"k": 18, "p": 0.5}), rng=random.Random(1)
    )
    assert sampled.args["k"] == 18


@pytest.mark.parametrize(
    ("model_name", "networkx_function"),
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
def test_every_available_named_regime_builds_a_networkx_graph(
    model_name, networkx_function
):
    sampler = MODELS[model_name].sample
    for name in MODELS[model_name].regimes:
        if name == "custom":
            continue
        sampled = sampler(
            20,
            base=SampledModel(parameters={"regime": name}),
            rng=random.Random(31),
        )
        graph = networkx_function(**sampled.args, **sampled.kwargs)
        assert graph.number_of_nodes() == 20
