import torch

from src.candidates import DirectedCandidateConfig, generate_two_hop_candidates
from src.tasks.base_link_task import TaskGraph


def test_mutual_two_hop_candidates_exclude_self_and_current_neighbors():
    graph = TaskGraph(4, torch.tensor([[0, 1, 0], [1, 2, 3]]), torch.zeros(3, dtype=torch.long), torch.empty((0, 2), dtype=torch.long), False, "mutual")
    assert generate_two_hop_candidates(graph, 0) == {2}


def test_directed_out_out_candidate_strategy_is_explicit():
    graph = TaskGraph(3, torch.tensor([[0, 1], [1, 2]]), torch.zeros(2, dtype=torch.long), torch.empty((0, 2), dtype=torch.long), True, "directed")
    assert generate_two_hop_candidates(graph, 0, directed=True, directed_config=DirectedCandidateConfig("out", "out")) == {2}
