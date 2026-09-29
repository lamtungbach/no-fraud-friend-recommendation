from .base import LinkScorer


class JaccardScorer(LinkScorer):
    def score(self, u: int, v: int) -> float:
        left, right = self._neighbors(u), self._neighbors(v)
        union = left | right
        return len(left & right) / len(union) if union else 0.0
