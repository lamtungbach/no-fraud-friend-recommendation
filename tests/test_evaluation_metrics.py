import pytest
import math

from src.evaluation.binary_metrics import binary_metrics
from src.evaluation.ranking_metrics import candidate_coverage, ranking_metrics


def test_binary_metrics_perfect_separation():
    result = binary_metrics([0.9, 0.8], [0.2, 0.1])
    assert result["roc_auc"] == 1.0
    assert result["average_precision"] == 1.0


def test_binary_metrics_requires_two_classes():
    with pytest.raises(ValueError):
        binary_metrics([0.5], [])


def test_ranking_metrics_and_candidate_coverage():
    result = ranking_metrics([[False, True], [True]], ks=(1, 2))
    assert result["precision_at_1"] == 0.5
    assert result["recall_at_2"] == 1.0
    assert result["hits_at_1"] == 0.5
    assert result["mrr"] == 0.75
    assert result["ndcg_at_1"] == 0.5
    assert result["ndcg_at_2"] == pytest.approx((1 / math.log2(3) + 1) / 2)
    assert candidate_coverage([True, False, True]) == 2 / 3


def test_ranking_empty_edge_case():
    result = ranking_metrics([], ks=(5,))
    assert result["num_queries"] == 0
    assert result["mrr"] == 0.0
