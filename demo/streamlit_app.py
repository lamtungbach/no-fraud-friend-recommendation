"""PYMK Recommendation Command Center.

This Streamlit application is deliberately a thin, safe FastAPI client.  It
does not access PostgreSQL, Redis, artifacts, or Trust directly, and it never
receives or renders raw Top-M candidates.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

import streamlit as st

from demo.api_client import (
    DatasetJob,
    DemoApiError,
    PymkApiClient,
    RecommendationResult,
)
from demo.ui_formatters import (
    abbreviate_version,
    format_milliseconds,
    format_number,
    index_safe_evidence,
)
from demo.ui_state import (
    begin_recommendation_request,
    raw_cache_label,
    recommendation_snapshot,
    store_recommendation_result,
)

Result = TypeVar("Result")

_PAGES = ("Khám phá gợi ý", "Phân tích PYMK", "Hệ thống & Batch")
_EMPTY_RESULT_MESSAGES = {
    "ISOLATED_USER": "Tài khoản có trong graph nhưng chưa có kết nối phù hợp với retrieval hiện tại.",
    "NO_TWO_HOP_CANDIDATES": "Đã duyệt graph cục bộ nhưng không có ứng viên two-hop hợp lệ.",
    "NO_RANKED_CANDIDATES": "Có ứng viên retrieval nhưng ranking không tạo được kết quả thô.",
    "EMPTY_RAW_RESULT_UNSPECIFIED": "Raw cache không có candidate; backend không chạy lại retrieval để suy đoán nguyên nhân.",
    "SAFE_RESULT_EMPTY_UNSPECIFIED": "Không có đề xuất an toàn được trả về. UI không suy đoán rằng Trust đã lọc hết ứng viên.",
    "TRUST_UNAVAILABLE_FAIL_CLOSED": "Trust runtime không sẵn sàng; backend đã fail closed để không trả gợi ý không an toàn.",
}


def call_api(base_url: str, request: Callable[[PymkApiClient], Result]) -> Result:
    """Run one UI request and always close the locally owned HTTP client."""
    api = PymkApiClient(base_url)
    try:
        return request(api)
    finally:
        api.close()


def _safe_error(error: DemoApiError) -> str:
    if error.status_code == 403:
        return "Tác vụ quản trị đang tắt. Chỉ bật PHASE08_ADMIN_ENABLED trong môi trường development."
    return str(error)


def _refresh_health(api_url: str) -> None:
    """Explicitly refresh health; recommendation data is not fetched here."""
    started_at = time.perf_counter()
    live: dict[str, Any] | None = None
    ready: dict[str, Any] | None = None
    live_error: str | None = None
    ready_error: str | None = None
    try:
        live = call_api(api_url, lambda api: api.live())
    except DemoApiError as error:
        live_error = _safe_error(error)
    try:
        ready = call_api(api_url, lambda api: api.ready())
    except DemoApiError as error:
        ready_error = _safe_error(error)
    st.session_state.health = {
        "live": live,
        "ready": ready,
        "live_error": live_error,
        "ready_error": ready_error,
        "latency_ms": round((time.perf_counter() - started_at) * 1000, 1),
    }


def _reset_for_api_url(api_url: str) -> None:
    if st.session_state.get("_api_url") == api_url:
        return
    for key in (
        "health",
        "recommendation",
        "recommendation_latency_ms",
        "recommendation_query_id",
        "selected_candidate_id",
        "dataset_job",
    ):
        st.session_state.pop(key, None)
    st.session_state["_api_url"] = api_url


def _health_strip(recommendation: RecommendationResult | None = None) -> None:
    health = st.session_state.get("health")
    if not isinstance(health, dict):
        st.info("Chưa kiểm tra backend. Dùng nút “Kiểm tra API” ở thanh bên trước khi demo.")
        return

    if recommendation is None:
        recommendation = recommendation_snapshot(st.session_state)

    live = health.get("live")
    ready = health.get("ready")
    live_ok = isinstance(live, dict) and str(live.get("status", "")).lower() in {"live", "ok", "healthy"}
    ready_ok = isinstance(ready, dict) and str(ready.get("status", "")).lower() == "ready"
    graph = ready.get("graph_version") if isinstance(ready, dict) else None
    cache_label = raw_cache_label(recommendation)

    one, two, three, four = st.columns(4)
    one.metric("API live", "LIVE" if live_ok else "Không phản hồi")
    two.metric("Backend ready", "READY" if ready_ok else "Chưa sẵn sàng")
    three.metric("Graph active", abbreviate_version(str(graph)) if graph else "Chưa công bố")
    four.metric("Raw cache", cache_label)
    st.caption(
        f"Health round-trip từ UI: {health.get('latency_ms', '—')} ms. "
        "Giá trị này khác với các timing do backend đo trong Pipeline Diagnostics."
    )
    errors = [message for message in (health.get("live_error"), health.get("ready_error")) if message]
    if errors:
        st.warning(" · ".join(errors))


def _render_versions(result: RecommendationResult) -> None:
    with st.expander("Phiên kỹ thuật đang được backend trả về", expanded=False):
        st.code(
            "\n".join(
                (
                    f"graph_version        = {result.graph_version}",
                    f"trust_version        = {result.trust_version}",
                    f"trust_policy_version = {result.trust_policy_version}",
                )
            ),
            language="text",
        )


def _select_candidate(result: RecommendationResult) -> int | None:
    candidate_ids = [item.get("candidate_id") for item in result.recommendations]
    candidate_ids = [candidate_id for candidate_id in candidate_ids if isinstance(candidate_id, int)]
    selected = st.session_state.get("selected_candidate_id")
    if selected not in candidate_ids:
        selected = candidate_ids[0] if candidate_ids else None
        st.session_state["selected_candidate_id"] = selected
    return selected


def _render_recommendation_cards(result: RecommendationResult) -> None:
    if not result.recommendations:
        st.info("Không có Safe Top-K cho request này.")
        context = result.empty_result_context
        if isinstance(context, dict):
            status = str(context.get("status", "UNKNOWN"))
            st.caption(_EMPTY_RESULT_MESSAGES.get(status, "Backend không có phân loại chi tiết cho kết quả rỗng này."))
            st.caption(f"Backend evidence: {context.get('evidence', 'Không công bố')} · Status: {status}")
        else:
            st.caption("Không có empty-result context trong response; UI không suy đoán nguyên nhân hoặc công bố raw Top-M.")
        return

    safe_ids = {item["candidate_id"] for item in result.recommendations if isinstance(item.get("candidate_id"), int)}
    explanations = index_safe_evidence(result.explanations, safe_ids)
    paths = index_safe_evidence(result.path_summaries, safe_ids)
    selected_id = _select_candidate(result)
    cards, detail = st.columns((1.05, 0.95), gap="large")

    with cards:
        st.subheader("Safe Top-K")
        st.caption("Thứ tự # là vị trí trong danh sách Safe Top-K được backend trả về; “raw rank” là hạng trước Trust, không phải hạng an toàn.")
        for safe_position, recommendation in enumerate(result.recommendations, start=1):
            candidate_id = recommendation.get("candidate_id")
            if not isinstance(candidate_id, int):
                continue
            with st.container(border=True):
                title, action = st.columns((0.72, 0.28))
                title.markdown(f"**#{safe_position} · Candidate {candidate_id}**")
                if action.button("Xem chi tiết", key=f"candidate-{st.session_state.get('recommendation_query_id', 0)}-{candidate_id}"):
                    st.session_state["selected_candidate_id"] = candidate_id
                    selected_id = candidate_id
                first, second, third = st.columns(3)
                first.metric("PYMK score", format_number(recommendation.get("score"), 2))
                second.metric("Raw rank", format_number(recommendation.get("rank")))
                third.metric("Trust score", format_number(recommendation.get("trust_score"), 2))
                st.caption(f"{recommendation.get('eligibility', 'SAFE')} · {recommendation.get('reason_code', 'Không công bố reason code')}")

    chosen = next((item for item in result.recommendations if item.get("candidate_id") == selected_id), None)
    with detail:
        st.subheader("Chi tiết gợi ý")
        if not isinstance(chosen, dict) or not isinstance(selected_id, int):
            st.info("Chọn một candidate an toàn để xem evidence tổng hợp.")
            return
        st.markdown(f"**Candidate {selected_id}** · Safe Top-K position #{result.recommendations.index(chosen) + 1}")
        trust_left, trust_right = st.columns(2)
        trust_left.metric("Trust score", format_number(chosen.get("trust_score"), 2))
        trust_right.metric("Risk score", format_number(chosen.get("risk_score"), 4))
        st.caption(f"Trust decision: {chosen.get('eligibility', 'Không công bố')} · {chosen.get('reason_code', 'Không công bố')}")

        explanation = explanations.get(selected_id)
        st.markdown("#### Explainable PYMK")
        if explanation:
            st.caption(
                f"Topology evidence từ graph {explanation.get('graph_semantics', 'unknown')} · "
                f"ranking method: `{explanation.get('ranking_method', 'unknown')}`. "
                "Các chỉ số này là evidence topology, không phải probability hay lý do Trust."
            )
            one, two, three, four = st.columns(4)
            one.metric("Common neighbors", format_number(explanation.get("common_neighbors")))
            two.metric("Jaccard", format_number(explanation.get("jaccard"), 4))
            three.metric("Adamic-Adar", format_number(explanation.get("adamic_adar"), 4))
            four.metric("Preferential attach.", format_number(explanation.get("preferential_attachment"), 2))
            note = explanation.get("note")
            if note:
                st.caption(str(note))
        else:
            st.info("Request này không kèm explanation. Gửi request mới với “Evidence & diagnostics” để backend cung cấp evidence aggregate nếu hỗ trợ.")

        path = paths.get(selected_id)
        st.markdown("#### Aggregate graph evidence")
        if path:
            total = path.get("path_count_total")
            total_label = format_number(total) if isinstance(total, int) else "Không xác định (scan cap)"
            one, two, three = st.columns(3)
            one.metric("Two-hop paths", total_label)
            two.metric("Observed paths", format_number(path.get("path_count_observed")))
            three.metric("Sample budget", format_number(path.get("sampled_path_count")))
            st.caption(
                f"Graph semantics: {path.get('graph_semantics', 'unknown')} · "
                f"Edge-type evidence: {'có' if path.get('edge_type_evidence_available') else 'không'}"
            )
            if path.get("truncated") or path.get("scan_truncated"):
                st.info("Evidence được giới hạn bởi budget hoặc scan cap. UI chỉ hiển thị aggregate, không hiển thị node trung gian hay edge cụ thể.")
            if path.get("note"):
                st.caption(str(path["note"]))
        else:
            st.info("Request này không kèm path summary. Không có graph path trực quan hóa vì backend không công bố node trung gian.")


def _render_discover(api_url: str) -> None:
    st.header("PYMK · Safe Friend Recommendations")
    st.caption("Command Center chỉ trình bày Safe Top-K do FastAPI trả về sau Trust policy; không truy cập trực tiếp Redis hoặc PostgreSQL.")
    health_placeholder = st.empty()

    health = st.session_state.get("health", {})
    ready = health.get("ready") if isinstance(health, dict) else None
    configured_max = ready.get("max_top_k", 10) if isinstance(ready, dict) else 10
    configured_max = configured_max if isinstance(configured_max, int) and configured_max > 0 else 10
    default_top_k = min(5, configured_max)

    st.subheader("Tìm gợi ý")
    with st.form("recommendation-form", clear_on_submit=False):
        form_left, form_right = st.columns(2)
        user_id = form_left.number_input("User ID", min_value=0, value=0, step=1)
        top_k = form_right.number_input(
            "Safe Top-K",
            min_value=1,
            max_value=configured_max,
            value=default_top_k,
            step=1,
            help="Giới hạn được backend công bố qua /health/ready khi khả dụng.",
        )
        evidence_enabled = st.checkbox(
            "Evidence & diagnostics (P0/P1)",
            value=True,
            help="Chỉ yêu cầu counters và evidence aggregate cho Safe Top-K; không yêu cầu hay hiển thị raw candidates.",
        )
        submitted = st.form_submit_button("Tìm Safe Top-K", type="primary", use_container_width=True)

    if submitted:
        begin_recommendation_request(st.session_state)
        try:
            with st.spinner("Đang gọi FastAPI để lấy Safe Top-K…"):
                started_at = time.perf_counter()
                result = call_api(
                    api_url,
                    lambda api: api.recommend(
                        int(user_id),
                        int(top_k),
                        include_diagnostics=evidence_enabled,
                        include_explanations=evidence_enabled,
                        include_path_summaries=evidence_enabled,
                        include_empty_result_context=evidence_enabled,
                    ),
                )
            store_recommendation_result(
                st.session_state,
                result,
                round((time.perf_counter() - started_at) * 1000, 1),
            )
        except (DemoApiError, ValueError) as error:
            st.error(_safe_error(error) if isinstance(error, DemoApiError) else str(error))

    current_result = recommendation_snapshot(st.session_state)
    with health_placeholder.container():
        _health_strip(current_result)
    if current_result is None:
        st.info("Chưa có recommendation request trong phiên này. Việc mở trang không tự chạy retrieval/ranking.")
        return

    request_left, request_middle, request_right = st.columns(3)
    request_left.metric("Safe results", len(current_result.recommendations))
    request_middle.metric("UI round-trip", f"{st.session_state.get('recommendation_latency_ms', '—')} ms")
    request_right.metric("Raw cache", raw_cache_label(current_result))
    st.caption("UI round-trip bao gồm network/browser overhead; backend timings xem ở Phân tích PYMK.")
    _render_versions(current_result)
    _render_recommendation_cards(current_result)


def _render_diagnostics(result: RecommendationResult) -> None:
    diagnostics = result.diagnostics
    if not isinstance(diagnostics, dict):
        st.info("Request đang xem không kèm diagnostics. Hãy gửi lại từ Khám phá gợi ý với “Evidence & diagnostics” được bật.")
        return

    stage = str(diagnostics.get("stage_execution", "unknown"))
    st.caption("Các counter bên dưới do backend trả về. Đây không phải raw candidate list và không phải suy diễn của UI.")
    if stage == "cache_hit" or result.raw_cache_hit:
        st.info("Raw Top-M được đọc từ cache. Retrieval và scoring không chạy lại; Trust vẫn được backend áp dụng cho request này.")
    else:
        st.info("Pipeline computed cho request này. Cache lookup và retrieval/scoring timing được tách riêng khi backend có số liệu.")

    one, two, three, four, five = st.columns(5)
    one.metric("Stage", "Cache hit" if stage == "cache_hit" else "Computed")
    two.metric("Raw ranked", format_number(diagnostics.get("raw_ranked_count")))
    three.metric("Safe returned", format_number(diagnostics.get("returned_safe_count")))
    four.metric("Unique candidates", format_number(diagnostics.get("unique_candidates")))
    five.metric("Backend total", format_milliseconds(diagnostics.get("total_backend_ms")))

    st.markdown("#### Retrieval caps & observed counters")
    cap_rows = [
        {"Stage": "First-hop", "Observed": format_number(diagnostics.get("first_hop_seen")), "Used": format_number(diagnostics.get("first_hop_used")), "Cap": format_number(diagnostics.get("first_hop_cap"))},
        {"Stage": "Second-hop expansion", "Observed": format_number(diagnostics.get("second_hop_expansions")), "Used": format_number(diagnostics.get("second_hop_used")), "Cap": format_number(diagnostics.get("second_hop_cap"))},
        {"Stage": "Candidate set", "Observed": format_number(diagnostics.get("unique_candidates")), "Used": format_number(diagnostics.get("candidates_returned")), "Cap": format_number(diagnostics.get("candidate_cap"))},
    ]
    st.dataframe(cap_rows, use_container_width=True, hide_index=True)
    if diagnostics.get("retrieval_truncated"):
        st.warning("Backend đánh dấu retrieval đã bị giới hạn bởi cap. Counters phản ánh phần được quan sát/được dùng, không phải toàn bộ graph.")
    else:
        st.caption("Backend không đánh dấu retrieval_truncated cho request này.")

    st.markdown("#### Ranking & exclusions")
    rank_left, rank_middle, rank_right, rank_last = st.columns(4)
    rank_left.metric("Scored", format_number(diagnostics.get("scored_candidates")))
    rank_middle.metric("Excluded self", format_number(diagnostics.get("excluded_self")))
    rank_right.metric("Excluded existing", format_number(diagnostics.get("excluded_existing")))
    rank_last.metric("Excluded duplicates", format_number(diagnostics.get("excluded_duplicates")))

    st.markdown("#### Backend timing")
    time_left, time_middle, time_right, time_last = st.columns(4)
    time_left.metric("Cache lookup", format_milliseconds(diagnostics.get("cache_lookup_ms")))
    time_middle.metric("Retrieval", format_milliseconds(diagnostics.get("retrieval_ms")))
    time_right.metric("Scoring", format_milliseconds(diagnostics.get("scoring_ms")))
    time_last.metric("Total", format_milliseconds(diagnostics.get("total_backend_ms")))
    st.caption("“Không thực thi” là null/không có trong response, thường xảy ra ở cache hit; UI không thay bằng số 0.")


def _render_analysis() -> None:
    st.header("PYMK Pipeline Diagnostics")
    st.caption("Hiển thị dữ liệu từ recommendation request gần nhất; mở trang này không phát sinh lời gọi retrieval/ranking mới.")
    _health_strip()
    result = st.session_state.get("recommendation")
    if not isinstance(result, RecommendationResult):
        st.info("Chưa có request để phân tích. Vào Khám phá gợi ý, bật “Evidence & diagnostics”, rồi gửi Safe Top-K.")
        return
    _render_diagnostics(result)
    _render_versions(result)
    st.markdown("#### Sơ đồ xử lý (minh họa kiến trúc, không phải graph path)")
    st.code("FastAPI request → bounded retrieval → topology ranking → Trust policy → Safe Top-K response", language="text")
    st.caption("Không vẽ node/edge vì DTO chỉ công bố aggregate evidence, không công bố đường đi hoặc node trung gian.")


def _render_job(job: DatasetJob) -> None:
    status = job.status.upper()
    if status == "PENDING":
        st.info("Job đã được API nhận (PENDING). Điều này chưa khẳng định graph mới đã phục vụ recommendation.")
    elif status == "RUNNING":
        st.info("Job đang chạy. Dùng Làm mới job để đọc trạng thái mới nhất từ API.")
    elif status == "READY":
        st.warning("Job báo READY. Trước khi demo graph mới, kiểm tra /health/ready và graph active; trạng thái job không tự chứng minh serving reload đã hoàn tất.")
    elif status == "FAILED":
        st.error(f"Job FAILED. Error code: {job.error_code or 'không công bố'}")
    else:
        st.warning(f"Trạng thái job chưa được UI phân loại: {job.status}")
    with st.expander("Chi tiết Dataset Job", expanded=True):
        st.json({"job_id": job.job_id, "dataset_id": job.dataset_id, "status": job.status, "graph_version": job.graph_version, "graph_semantics": job.graph_semantics, "created_at": job.created_at, "updated_at": job.updated_at, "error_code": job.error_code})


def _render_system_batch(api_url: str) -> None:
    st.header("Graph & Batch Pipeline")
    st.caption("Trạng thái được đọc qua Phase 08 Dataset Job API. UI không kết nối trực tiếp PostgreSQL và không tự tạo job.")
    _health_strip()
    st.divider()
    left, right = st.columns(2)
    with left:
        st.subheader("Tạo MGTAB build job")
        st.caption("Chỉ dùng khi cần build graph mới trong development. Không bấm trong demo thông thường.")
        if st.button("Tạo MGTAB build job", type="primary", use_container_width=True):
            try:
                job = call_api(api_url, lambda api: api.create_mgtab_job())
                st.session_state["dataset_job"] = job
                st.session_state["tracked_job_id"] = job.job_id
                st.success(f"API đã nhận job {job.job_id} với trạng thái {job.status}.")
            except DemoApiError as error:
                st.warning(_safe_error(error))
    with right:
        st.subheader("Theo dõi job")
        default_job_id = getattr(st.session_state.get("dataset_job"), "job_id", "")
        entered_job_id = st.text_input("Job ID", value=default_job_id, key="tracked_job_id")
        if st.button("Làm mới job", use_container_width=True):
            if not entered_job_id.strip():
                st.warning("Nhập Job ID trước khi làm mới.")
            else:
                try:
                    st.session_state["dataset_job"] = call_api(api_url, lambda api: api.get_job(entered_job_id.strip()))
                except DemoApiError as error:
                    st.warning(_safe_error(error))
    job = st.session_state.get("dataset_job")
    if isinstance(job, DatasetJob):
        _render_job(job)
    else:
        st.info("Chưa theo dõi Dataset Job nào trong phiên này. Tạo job là thao tác tường minh; UI không tự gọi API này.")


st.set_page_config(page_title="PYMK Recommendation Command Center", page_icon="🛡️", layout="wide")

with st.sidebar:
    st.title("PYMK Command Center")
    st.caption("Safe friend recommendation · mentor demo")
    page = st.radio("Điều hướng", _PAGES, label_visibility="collapsed")
    st.divider()
    api_url = st.text_input("FastAPI URL", value=os.getenv("PYMK_API_URL", "http://127.0.0.1:8000"))
    if st.button("Kiểm tra API", use_container_width=True):
        _reset_for_api_url(api_url)
        _refresh_health(api_url)
    st.caption("UI chỉ gọi FastAPI. Không có kết nối trực tiếp đến Redis, PostgreSQL, artifact store hoặc Trust runtime.")
    st.info("Safe boundary: không hiển thị raw Top-M, blocked candidates, hoặc node trung gian.")

_reset_for_api_url(api_url)
if "health" not in st.session_state:
    _refresh_health(api_url)

if page == "Khám phá gợi ý":
    _render_discover(api_url)
elif page == "Phân tích PYMK":
    _render_analysis()
else:
    _render_system_batch(api_url)
