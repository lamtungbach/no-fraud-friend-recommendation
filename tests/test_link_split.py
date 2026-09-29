import torch

from src.split import split_positive_links


def test_split_is_disjoint_and_reproducible():
    positive = torch.tensor([[i, i + 1] for i in range(20)])
    first = split_positive_links(positive, seed=42)
    second = split_positive_links(positive, seed=42)
    assert torch.equal(first.train_pos, second.train_pos)
    sets = [set(map(tuple, part.tolist())) for part in (first.train_pos, first.val_pos, first.test_pos)]
    assert sets[0].isdisjoint(sets[1])
    assert sets[0].isdisjoint(sets[2])
    assert sets[1].isdisjoint(sets[2])

