"""
验证记录

查看 verification_records 集合中的完整性验证、属性证明、恢复后自动验证与认证审计记录。
支持按 DID、验证类型、验证结果过滤，并提供多维统计图表。
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None

from components.renderers import page_header, render_json_block
from services.data_service import get_verification_records


page_header(
    "验证记录",
    "查看 verification_records 集合，用于审计完整性验证、属性证明、恢复验证与认证结果。",
)


def _to_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "y", "valid", "success"}:
            return True
        if text in {"false", "0", "no", "n", "invalid", "fail", "failed"}:
            return False
    return None


def _bool_text(value):
    value = _to_bool(value)
    if value is True:
        return "通过"
    if value is False:
        return "失败"
    return "未知"


def _safe_get(result: dict, *keys, default=None):
    for key in keys:
        if isinstance(result, dict) and key in result:
            return result.get(key)
    return default


def _short_text(value, head=12, tail=8):
    if value is None:
        return "-"
    text = str(value)
    if len(text) <= head + tail + 3:
        return text
    return f"{text[:head]}...{text[-tail:]}"


def _to_datetime_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


def _build_summary_rows(rows: list[dict]) -> list[dict]:
    summary_rows = []

    for item in rows:
        result = item.get("result", {}) or {}
        verify_type = item.get("verify_type") or "unknown"

        # 不同 verify_type 的有效性字段不完全一致，这里统一做兼容。
        is_valid = _safe_get(
            result,
            "is_valid",
            "authenticated",
            "valid",
            default=None,
        )

        auto_verified = _safe_get(result, "auto_verified", default=None)
        local_integrity_ok = _safe_get(result, "local_integrity_ok", default=None)
        chain_integrity_ok = _safe_get(result, "chain_integrity_ok", default=None)

        summary_rows.append(
            {
                "did": item.get("did"),
                "did_short": _short_text(item.get("did"), 18, 8),
                "version": item.get("version"),
                "verify_type": verify_type,
                "is_valid": _to_bool(is_valid),
                "验证结果": _bool_text(is_valid),
                "target_document_hash_match": _to_bool(
                    result.get("target_document_hash_match")
                ),
                "target_merkle_root_match": _to_bool(
                    result.get("target_merkle_root_match")
                ),
                "target_version_hash_match": _to_bool(
                    result.get("target_version_hash_match")
                ),
                "latest_chain_match": _to_bool(result.get("latest_chain_match")),
                "history_chain_valid": _to_bool(result.get("history_chain_valid")),
                "transaction_verified": _to_bool(
                    result.get("transaction_verified")
                ),
                "local_integrity_ok": _to_bool(local_integrity_ok),
                "chain_integrity_ok": _to_bool(chain_integrity_ok),
                "auto_verified": _to_bool(auto_verified),
                "attribute_path": result.get("attribute_path")
                or result.get("proof", {}).get("attribute_path")
                if isinstance(result.get("proof"), dict)
                else result.get("attribute_path"),
                "created_at": str(item.get("created_at", "-")),
                "raw": item,
            }
        )

    return summary_rows


def _metric_card(label: str, value, help_text: str | None = None):
    st.metric(label, value, help=help_text)


def _valid_rate(series: pd.Series) -> float:
    known = series.dropna()
    if len(known) == 0:
        return 0.0
    return float((known == True).mean() * 100)


# =============================
# 侧边筛选
# =============================
with st.sidebar:
    st.subheader("筛选条件")
    did = st.text_input("按 DID 过滤（可选）", placeholder="为空则显示最近记录")
    limit = st.slider("读取记录数", min_value=20, max_value=500, value=100, step=20)

try:
    rows = get_verification_records(did=did.strip(), limit=limit)
except Exception as exc:
    st.error(f"读取 verification_records 失败：{exc}")
    st.stop()

if not rows:
    st.info("暂无验证记录")
    st.stop()

summary_rows = _build_summary_rows(rows)
df = pd.DataFrame(summary_rows)

df["created_dt"] = _to_datetime_series(df["created_at"])
df["created_date"] = df["created_dt"].dt.date.astype("string")

all_verify_types = sorted(df["verify_type"].dropna().unique().tolist())

col_filter_1, col_filter_2, col_filter_3 = st.columns([2, 2, 1])

with col_filter_1:
    selected_types = st.multiselect(
        "验证类型",
        options=all_verify_types,
        default=all_verify_types,
    )

with col_filter_2:
    result_filter = st.selectbox(
        "验证结果",
        options=["全部", "通过", "失败", "未知"],
        index=0,
    )

with col_filter_3:
    show_raw = st.toggle("显示原始 JSON", value=True)

filtered_df = df.copy()

if selected_types:
    filtered_df = filtered_df[filtered_df["verify_type"].isin(selected_types)]

if result_filter == "通过":
    filtered_df = filtered_df[filtered_df["is_valid"] == True]
elif result_filter == "失败":
    filtered_df = filtered_df[filtered_df["is_valid"] == False]
elif result_filter == "未知":
    filtered_df = filtered_df[filtered_df["is_valid"].isna()]

if filtered_df.empty:
    st.warning("当前筛选条件下暂无记录")
    st.stop()

# =============================
# 指标总览
# =============================
st.subheader("验证审计总览")

total_count = len(filtered_df)
valid_count = int((filtered_df["is_valid"] == True).sum())
invalid_count = int((filtered_df["is_valid"] == False).sum())
unknown_count = int(filtered_df["is_valid"].isna().sum())
valid_rate = _valid_rate(filtered_df["is_valid"])

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    _metric_card("记录总数", total_count)
with m2:
    _metric_card("通过数量", valid_count)
with m3:
    _metric_card("失败数量", invalid_count)
with m4:
    _metric_card("未知数量", unknown_count)
with m5:
    _metric_card("通过率", f"{valid_rate:.1f}%")

# =============================
# 图表分析
# =============================
st.subheader("验证类型与结果分布")

type_count_df = (
    filtered_df.groupby("verify_type", dropna=False)
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
)

type_rate_df = (
    filtered_df.groupby("verify_type", dropna=False)
    .agg(
        total=("verify_type", "size"),
        valid_count=("is_valid", lambda s: int((s == True).sum())),
        invalid_count=("is_valid", lambda s: int((s == False).sum())),
        auto_verified_count=("auto_verified", lambda s: int((s == True).sum())),
        tx_verified_count=("transaction_verified", lambda s: int((s == True).sum())),
    )
    .reset_index()
)

type_rate_df["valid_rate"] = type_rate_df.apply(
    lambda row: row["valid_count"] / row["total"] * 100 if row["total"] else 0,
    axis=1,
)

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    st.caption("各验证类型记录数量")
    if alt is not None:
        chart = (
            alt.Chart(type_count_df)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("count:Q"),
                color=alt.Color("verify_type:N", title="验证类型"),
                tooltip=["verify_type", "count"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(type_count_df.set_index("verify_type")["count"])

with chart_col_2:
    st.caption("各验证类型通过率对比")
    if alt is not None:
        chart = (
            alt.Chart(type_rate_df)
            .mark_bar()
            .encode(
                x=alt.X("verify_type:N", title="验证类型", sort="-y"),
                y=alt.Y("valid_rate:Q", title="通过率（%）"),
                tooltip=["verify_type", "total", "valid_count", "invalid_count", "valid_rate"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(type_rate_df.set_index("verify_type")["valid_rate"])

st.subheader("完整性校验维度对比")

integrity_cols = [
    "target_document_hash_match",
    "target_merkle_root_match",
    "target_version_hash_match",
    "latest_chain_match",
    "history_chain_valid",
    "transaction_verified",
    "local_integrity_ok",
    "chain_integrity_ok",
    "auto_verified",
]

integrity_summary = []
for col in integrity_cols:
    if col in filtered_df.columns:
        known = filtered_df[col].dropna()
        integrity_summary.append(
            {
                "check_item": col,
                "total_known": len(known),
                "passed": int((known == True).sum()),
                "failed": int((known == False).sum()),
                "pass_rate": float((known == True).mean() * 100) if len(known) else 0,
            }
        )

integrity_df = pd.DataFrame(integrity_summary)

if not integrity_df.empty:
    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.caption("各校验项通过率")
        if alt is not None:
            chart = (
                alt.Chart(integrity_df)
                .mark_bar()
                .encode(
                    x=alt.X("pass_rate:Q", title="通过率（%）", scale=alt.Scale(domain=[0, 100])),
                    y=alt.Y("check_item:N", title="校验项", sort="-x"),
                    tooltip=["check_item", "total_known", "passed", "failed", "pass_rate"],
                )
                .properties(height=360)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.bar_chart(integrity_df.set_index("check_item")["pass_rate"])

    with col_b:
        st.caption("通过 / 失败数量对比")
        compare_df = integrity_df.set_index("check_item")[["passed", "failed"]]
        st.bar_chart(compare_df)

st.subheader("时间趋势")

timeline_df = (
    filtered_df.dropna(subset=["created_dt"])
    .groupby(["created_date", "验证结果"], dropna=False)
    .size()
    .reset_index(name="count")
)

if not timeline_df.empty:
    if alt is not None:
        chart = (
            alt.Chart(timeline_df)
            .mark_area(opacity=0.65)
            .encode(
                x=alt.X("created_date:T", title="日期"),
                y=alt.Y("count:Q", title="记录数"),
                color=alt.Color("验证结果:N"),
                tooltip=["created_date", "验证结果", "count"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        pivot = timeline_df.pivot_table(
            index="created_date",
            columns="验证结果",
            values="count",
            aggfunc="sum",
            fill_value=0,
        )
        st.area_chart(pivot)
else:
    st.info("暂无可用于时间趋势分析的 created_at 数据")

# =============================
# 表格
# =============================
st.subheader("验证记录明细")

display_cols = [
    "did_short",
    "version",
    "verify_type",
    "验证结果",
    "history_chain_valid",
    "transaction_verified",
    "local_integrity_ok",
    "chain_integrity_ok",
    "auto_verified",
    "attribute_path",
    "created_at",
]

existing_display_cols = [col for col in display_cols if col in filtered_df.columns]

st.dataframe(
    filtered_df[existing_display_cols],
    use_container_width=True,
    hide_index=True,
)

# =============================
# 详情查看
# =============================
st.subheader("完整记录详情")

selected_options = list(filtered_df.index)
selected_index = st.selectbox(
    "选择记录",
    options=selected_options,
    format_func=lambda i: f"{filtered_df.loc[i, 'verify_type']} | v{filtered_df.loc[i, 'version']} | {filtered_df.loc[i, '验证结果']} | {filtered_df.loc[i, 'did_short']}",
)

selected_raw = filtered_df.loc[selected_index, "raw"]

detail_result = selected_raw.get("result", {}) or {}

detail_cols = st.columns(4)
with detail_cols[0]:
    st.metric("verify_type", selected_raw.get("verify_type", "-"))
with detail_cols[1]:
    st.metric("version", selected_raw.get("version", "-"))
with detail_cols[2]:
    st.metric("is_valid", _bool_text(detail_result.get("is_valid")))
with detail_cols[3]:
    st.metric("auto_verified", _bool_text(detail_result.get("auto_verified")))

if show_raw:
    render_json_block("verification_record", selected_raw)