import hashlib

from .base import LinkScorer


class RandomScorer(LinkScorer):
    def __init__(self, graph, seed: int = 42):
        super().__init__(graph)
        self.seed = seed

    def score(self, u: int, v: int) -> float:
        digest = hashlib.blake2b(f"{self.seed}:{u}:{v}".encode(), digest_size=8).digest()
        return int.from_bytes(digest, "big") / 2**64
