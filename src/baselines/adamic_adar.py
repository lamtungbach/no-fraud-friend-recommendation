import math

from .base import LinkScorer


class AdamicAdarScorer(LinkScorer):
    def score(self, u: int, v: int) -> float:
        total = 0.0
        for node in self._neighbors(u) & self._neighbors(v):
            degree = len(self._neighbors(node))
            if degree > 1:
                total += 1.0 / math.log(degree)
        return total
