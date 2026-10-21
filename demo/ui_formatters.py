"""Pure presentation helpers for the Streamlit Command Center."""

from __future__ import annotations

from typing import Any


def abbreviate_version(value: str, limit: int = 18) -> str:
    """Abbreviate only for display; callers retain the complete value elsewhere."""
    return value if len(value) <= limit else f"{value[:limit - 1]}…"


def format_number(value: Any, digits: int = 0) -> str:
    """Use an absent marker for missing values and never turn missing into zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    return f"{value:,.{digits}f}"


def format_milliseconds(value: Any) -> str:
    """Keep an unmeasured backend duration distinct from a measured zero."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "Không thực thi"
    return f"{float(value):.1f} ms"


def index_safe_evidence(
    items: list[dict[str, Any]] | None, safe_ids: set[int]
) -> dict[int, dict[str, Any]]:
    """Return optional evidence only when it belongs to an already safe ID."""
    indexed: dict[int, dict[str, Any]] = {}
    for item in items or []:
        candidate_id = item.get("candidate_id")
        if isinstance(candidate_id, int) and candidate_id in safe_ids:
            indexed[candidate_id] = item
    return indexed
