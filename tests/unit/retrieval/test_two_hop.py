import torch

from src.graph.graph_view import GraphView
from src.retrieval.two_hop import (
    retrieve_two_hop_candidates,
    retrieve_two_hop_candidates_reference,
)
from src.serving.graph_index import ServingGraphIndex


def _index() -> ServingGraphIndex:
    return ServingGraphIndex.from_graph_view(
        GraphView(
            torch.tensor([0, 1, 2, 3, 4]),
            torch.tensor([[0, 0, 1, 2, 2, 3], [1, 2, 3, 0, 4, 4]]),
            True,
        )
    )


def test_unbounded_retrieval_matches_exact_reference_and_excludes_existing_links():
    index = _index()
    actual = retrieve_two_hop_candidates(0, index)
    assert actual == frozenset({3, 4})
    assert actual == retrieve_two_hop_candidates_reference(0, index)
    assert 0 not in actual
    assert not actual.intersection(index.neighbors(0))


def test_retrieval_is_deterministic_and_rejects_unknown_user():
    index = _index()
    assert retrieve_two_hop_candidates(0, index) == retrieve_two_hop_candidates(
        0, index
    )
    try:
        retrieve_two_hop_candidates(99, index)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected unknown user retrieval to fail")
