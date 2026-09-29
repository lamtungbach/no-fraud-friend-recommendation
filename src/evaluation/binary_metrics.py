"""Binary link classification metrics."""

from __future__ import annotations

from sklearn.metrics import average_precision_score, roc_auc_score


def binary_metrics(positive_scores: list[float], negative_scores: list[float]) -> dict[str, float]:
    if not positive_scores or not negative_scores:
        raise ValueError("ROC-AUC and Average Precision require at least one positive and one negative score")
    labels = [1] * len(positive_scores) + [0] * len(negative_scores)
    scores = positive_scores + negative_scores
    return {"roc_auc": float(roc_auc_score(labels, scores)), "average_precision": float(average_precision_score(labels, scores))}
