import torch

from src.candidates import TwoHopCandidateGenerator
from src.sampling import sample_hard_negatives, sample_random_negatives
from src.tasks.base_link_task import TaskGraph


def test_random_negatives_exclude_hidden_known_positives_and_are_deterministic():
    known = torch.tensor([[0, 1], [0, 2]])
    first = sample_random_negatives(4, known, True, 4, seed=9)
    second = sample_random_negatives(4, known, True, 4, seed=9)
    assert torch.equal(first, second)
    assert not ({tuple(row) for row in first.tolist()} & {tuple(row) for row in known.tolist()})


def test_hard_negatives_come_from_two_hop_candidate_pool():
    graph = TaskGraph(3, torch.tensor([[0, 1], [1, 2]]), torch.zeros(2, dtype=torch.long), torch.empty((0, 2), dtype=torch.long), True, "directed")
    sample = sample_hard_negatives(graph, torch.tensor([[0, 1]]), torch.tensor([[0, 1], [1, 2]]), TwoHopCandidateGenerator(graph), seed=2)
    assert sample.pairs.tolist() == [[0, 2]]
    assert sample.sources_without_enough_candidates == 0
