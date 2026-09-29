"""Deterministic disjoint positive link splits and train graph construction."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from src.tasks.base_link_task import TaskGraph
from .leakage_mask import mask_task_graph_edges


@dataclass
class LinkSplit:
    train_pos: Tensor
    val_pos: Tensor
    test_pos: Tensor
    seed: int


def split_positive_links(positive_edges: Tensor, train_ratio: float = 0.70, val_ratio: float = 0.15, test_ratio: float = 0.15, seed: int = 42) -> LinkSplit:
    if positive_edges.ndim != 2 or positive_edges.shape[1] != 2:
        raise ValueError(f"positive_edges must have shape [P, 2], got {tuple(positive_edges.shape)}")
    if any(r < 0 for r in (train_ratio, val_ratio, test_ratio)) or abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-8:
        raise ValueError("train_ratio, val_ratio and test_ratio must be non-negative and sum to 1")
    generator = torch.Generator().manual_seed(seed)
    order = torch.randperm(positive_edges.shape[0], generator=generator)
    shuffled = positive_edges[order].clone()
    train_end = int(positive_edges.shape[0] * train_ratio)
    val_end = train_end + int(positive_edges.shape[0] * val_ratio)
    return LinkSplit(shuffled[:train_end], shuffled[train_end:val_end], shuffled[val_end:], seed)


def build_observed_graph(task_graph: TaskGraph, hidden_edges: Tensor) -> TaskGraph:
    """Remove hidden task edges and equivalent social representations."""
    return mask_task_graph_edges(task_graph, hidden_edges)
