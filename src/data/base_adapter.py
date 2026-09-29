"""Abstract adapter contract."""

from abc import ABC, abstractmethod

from .canonical_graph import CanonicalGraph
from .validation import validate_canonical_graph


class DatasetAdapter(ABC):
    """Convert one raw dataset into the project-wide canonical contract."""

    @abstractmethod
    def load_raw(self):
        """Read raw dataset files without mutating them."""
        raise NotImplementedError

    @abstractmethod
    def transform(self) -> CanonicalGraph:
        """Load and transform raw data into a validated graph."""
        raise NotImplementedError

    def validate(self, graph: CanonicalGraph) -> None:
        validate_canonical_graph(graph)
