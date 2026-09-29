from .base import LinkScorer


class PreferentialAttachmentScorer(LinkScorer):
    def score(self, u: int, v: int) -> float:
        return float(len(self._neighbors(u)) * len(self._neighbors(v)))
