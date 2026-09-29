from .base import LinkScorer


class CommonNeighborsScorer(LinkScorer):
    def score(self, u: int, v: int) -> float:
        return float(len(self._neighbors(u) & self._neighbors(v)))
