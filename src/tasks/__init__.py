"""Task-specific link prediction semantics."""

from .base_link_task import TaskGraph
from .directed_connection import DirectedConnectionTask
from .mutual_connection import MutualConnectionTask

__all__ = ["TaskGraph", "DirectedConnectionTask", "MutualConnectionTask"]
