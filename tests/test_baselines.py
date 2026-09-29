import math

import torch

from src.baselines import AdamicAdarScorer, CommonNeighborsScorer, JaccardScorer, PreferentialAttachmentScorer, RandomScorer
from src.tasks.base_link_task import TaskGraph


def graph():
    return TaskGraph(4, torch.tensor([[0, 1, 2], [1, 2, 3]]), torch.zeros(3, dtype=torch.long), torch.empty((0, 2), dtype=torch.long), False, "mutual")


def test_baseline_formula_values():
    task = graph()
    assert CommonNeighborsScorer(task).score(0, 2) == 1.0
    assert JaccardScorer(task).score(0, 2) == 0.5
    assert AdamicAdarScorer(task).score(0, 2) == 1 / math.log(2)
    assert PreferentialAttachmentScorer(task).score(0, 2) == 2.0


def test_random_scorer_is_deterministic():
    assert RandomScorer(graph(), seed=8).score(0, 2) == RandomScorer(graph(), seed=8).score(0, 2)
