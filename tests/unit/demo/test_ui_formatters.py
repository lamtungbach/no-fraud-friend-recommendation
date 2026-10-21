from __future__ import annotations

from demo.ui_formatters import (
    abbreviate_version,
    format_milliseconds,
    format_number,
    index_safe_evidence,
)


def test_formatters_distinguish_missing_from_a_real_zero():
    assert format_number(None) == "—"
    assert format_number(0) == "0"
    assert format_number(True) == "—"
    assert format_milliseconds(None) == "Không thực thi"
    assert format_milliseconds(True) == "Không thực thi"
    assert format_milliseconds(0) == "0.0 ms"


def test_version_is_only_abbreviated_for_display():
    version = "mgtab-20261013T033921Z-d729a97c"

    assert abbreviate_version("short") == "short"
    assert abbreviate_version(version, limit=12) == "mgtab-20261…"


def test_evidence_index_never_includes_a_non_safe_candidate():
    indexed = index_safe_evidence(
        [
            {"candidate_id": 7, "common_neighbors": 4},
            {"candidate_id": 99, "common_neighbors": 8},
        ],
        {7},
    )

    assert indexed == {7: {"candidate_id": 7, "common_neighbors": 4}}
