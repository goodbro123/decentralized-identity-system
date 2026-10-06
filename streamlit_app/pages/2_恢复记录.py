"""
恢复记录

展示 did_recovery_blocks 集合中的恢复块单元。

最终设计：
一条 did_recovery_blocks 记录 = 一个恢复块单元。

duplication:
    replica 0 / 1 / 2 分别一条记录

erasure_code:
    data_shard 0 / 1 / 2 / 3 分别一条记录
    parity_shard 一条记录
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None

from components.renderers import page_header, render_json_block
from services.data_service import get_recovery_blocks
from utils.formatters import short_hash


page_header(
    "恢复记录",
    "按恢复块单元展示多副本与纠删码分片，支持比较存储开销、块数量和可恢复状态。",
)


# =============================
# 展示层中文化工具
# =============================

METHOD_TEXT_MAP = {
    "duplication": "多副本",
    "erasure_code": "纠删码",
    "auto": "自动选择",
    "unknown": "未知",
    None: "未知",
}

BLOCK_TYPE_TEXT_MAP = {
    "replica": "副本块",
    "data_shard": "数据分片",
    "parity_shard": "校验分片",
    "shard": "分片块",
    "original": "原始块",
    "metadata": "元数据块",
    "unknown": "未知",
    None: "未知",
}

STATUS_TEXT_MAP = {
    "active": "有效",
    "inactive": "未启用",
    "missing": "缺失",
    "recovered": "已恢复",
    "corrupted": "损坏",
    "deleted": "已删除",
    "invalid": "异常",
    "unknown": "未知",
    None: "未知",
}

CODEC_TEXT_MAP = {
    "-": "-",
    "none": "未使用编码",
    "raw": "原始数据",
    "json": "结构化数据",
    "utf8": "文本编码",
    "utf-8": "文本编码",
    "base64": "字符编码",
    "reed_solomon": "纠删码编码",
    "erasure_code": "纠删码编码",
    "zlib": "压缩编码",
    "gzip": "压缩编码",
    "unknown": "未知",
    None: "未知",
}


def _normalize_key(value):
    if value is None:
        return None
    if pd.isna(value):
        return None
    return str(value).strip().lower()


def _display_text(value, mapping: dict) -> str:
    key = _normalize_key(value)
    if key in mapping:
        return mapping[key]
    return "其他"


def _method_text(value) -> str:
    return _display_text(value, METHOD_TEXT_MAP)


def _block_type_text(value) -> str:
    return _display_text(value, BLOCK_TYPE_TEXT_MAP)


def _status_text(value) -> str:
    return _display_text(value, STATUS_TEXT_MAP)


def _codec_text(value) -> str:
    return _display_text(value, CODEC_TEXT_MAP)


def _format_storage_size(value) -> str:
    try:
        if pd.isna(value):
            return "0 字节"
        return f"{int(value)} 字节"
    except Exception:
        return "0 字节"


def _short_text(value, head=18, tail=8):
    if value is None:
        return "-"
    text = str(value)
    if len(text) <= head + tail + 3:
        return text
    return f"{text[:head]}...{text[-tail:]}"


def _to_datetime_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


def _extract_row(item: dict) -> dict:
    return {
        "did": item.get("did"),
        "did_short": _short_text(item.get("did")),
        "version": item.get("version"),
        "method": item.get("method"),
        "block_type": item.get("block_type"),
        "block_index": item.get("block_index"),
        "codec": item.get("codec") or "-",
        "payload_hash": short_hash(item.get("payload_hash")),
        "storage_size_bytes": item.get("storage_size_bytes", 0),
        "status": item.get("status"),
        "document_hash": short_hash(item.get("document_hash")),
        "merkle_root": short_hash(item.get("merkle_root")),
        "version_hash": short_hash(item.get("version_hash")),
        "transaction_hash": short_hash(item.get("transaction_hash")),
        "shard_size": item.get("shard_size"),
        "original_length": item.get("original_length"),
        "data_shard_count": item.get("data_shard_count"),
        "recoverable_missing_count": item.get("recoverable_missing_count"),
        "created_at": str(item.get("created_at", "-")),
        "updated_at": str(item.get("updated_at", "-")),
        "raw": item,
    }


def _localize_detail_row(row: pd.Series) -> dict:
    return {
        "身份标识": row.get("identity_alias", "未知身份"),
        "版本号": row.get("version"),
        "恢复方式": row.get("method_text", "未知"),
        "块类型": row.get("block_type_text", "未知"),
        "块编号": row.get("block_index"),
        "编码方式": row.get("codec_text", "未知"),
        "存储大小": _format_storage_size(row.get("storage_size_bytes")),
        "状态": row.get("status_text", "未知"),
        "负载哈希": row.get("payload_hash"),
        "文档哈希": row.get("document_hash"),
        "默克尔根": row.get("merkle_root"),
        "版本哈希": row.get("version_hash"),
        "交易哈希": row.get("transaction_hash"),
        "分片大小": row.get("shard_size"),
        "原始长度": row.get("original_length"),
        "数据分片数量": row.get("data_shard_count"),
        "最大可恢复缺失块数": row.get("recoverable_missing_count"),
        "创建时间": row.get("created_at"),
        "更新时间": row.get("updated_at"),
    }


with st.sidebar:
    st.subheader("筛选条件")
    did = st.text_input("按身份标识过滤（可选）", placeholder="为空则显示最近恢复块")
    limit = st.slider("读取恢复块数量", min_value=20, max_value=1000, value=200, step=20)

try:
    rows = get_recovery_blocks(did=did.strip(), limit=limit)
except Exception:
    st.error("读取恢复块数据失败，请查看后台日志。")
    st.stop()

if not rows:
    st.info("暂无恢复块记录")
    st.stop()

df = pd.DataFrame([_extract_row(item) for item in rows])
df["updated_dt"] = _to_datetime_series(df["updated_at"])
df["updated_date"] = df["updated_dt"].dt.date.astype("string")

# 展示层字段：内部字段仍保留英文，所有页面可见内容使用中文字段。
df["method_text"] = df["method"].apply(_method_text)
df["block_type_text"] = df["block_type"].apply(_block_type_text)
df["status_text"] = df["status"].apply(_status_text)
df["codec_text"] = df["codec"].apply(_codec_text)

did_values = sorted(df["did"].dropna().astype(str).unique().tolist())
did_alias_map = {
    did_value: f"身份标识{index + 1}"
    for index, did_value in enumerate(did_values)
}
df["identity_alias"] = df["did"].apply(
    lambda value: did_alias_map.get(str(value), "未知身份") if pd.notna(value) else "未知身份"
)

methods = sorted(df["method"].dropna().unique().tolist(), key=_method_text)
block_types = sorted(df["block_type"].dropna().unique().tolist(), key=_block_type_text)
statuses = sorted(df["status"].dropna().unique().tolist(), key=_status_text)

f1, f2, f3 = st.columns(3)

with f1:
    selected_methods = st.multiselect(
        "恢复方式",
        options=methods,
        default=methods,
        format_func=_method_text,
    )

with f2:
    selected_block_types = st.multiselect(
        "块类型",
        options=block_types,
        default=block_types,
        format_func=_block_type_text,
    )

with f3:
    selected_statuses = st.multiselect(
        "状态",
        options=statuses,
        default=statuses,
        format_func=_status_text,
    )

filtered_df = df.copy()

if selected_methods:
    filtered_df = filtered_df[filtered_df["method"].isin(selected_methods)]

if selected_block_types:
    filtered_df = filtered_df[filtered_df["block_type"].isin(selected_block_types)]

if selected_statuses:
    filtered_df = filtered_df[filtered_df["status"].isin(selected_statuses)]

if filtered_df.empty:
    st.warning("当前筛选条件下暂无恢复块")
    st.stop()

st.subheader("恢复块单元总览")

total_count = len(filtered_df)
dup_count = int((filtered_df["method"] == "duplication").sum())
erasure_count = int((filtered_df["method"] == "erasure_code").sum())
active_count = int((filtered_df["status"] == "active").sum())
total_storage = int(filtered_df["storage_size_bytes"].fillna(0).sum())

m1, m2, m3, m4, m5 = st.columns(5)

with m1:
    st.metric("恢复块总数", total_count)
with m2:
    st.metric("多副本块", dup_count)
with m3:
    st.metric("纠删码块", erasure_count)
with m4:
    st.metric("有效块", active_count)
with m5:
    st.metric("总存储大小", _format_storage_size(total_storage))

st.subheader("恢复方式与块类型分布")

c1, c2 = st.columns(2)

method_count = (
    filtered_df.groupby("method_text")
    .size()
    .reset_index(name="数量")
    .rename(columns={"method_text": "恢复方式"})
)

with c1:
    st.caption("恢复方式占比")
    if alt is not None:
        chart = (
            alt.Chart(method_count)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("数量:Q"),
                color=alt.Color("恢复方式:N", title="恢复方式"),
                tooltip=["恢复方式", "数量"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(method_count.set_index("恢复方式")["数量"])

block_type_count = (
    filtered_df.groupby(["method_text", "block_type_text"])
    .size()
    .reset_index(name="数量")
    .rename(
        columns={
            "method_text": "恢复方式",
            "block_type_text": "块类型",
        }
    )
)

with c2:
    st.caption("不同恢复方式下的块类型数量")
    if alt is not None:
        chart = (
            alt.Chart(block_type_count)
            .mark_bar()
            .encode(
                x=alt.X("恢复方式:N", title="恢复方式"),
                y=alt.Y("数量:Q", title="数量"),
                color=alt.Color("块类型:N", title="块类型"),
                tooltip=["恢复方式", "块类型", "数量"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        pivot = block_type_count.pivot_table(
            index="恢复方式",
            columns="块类型",
            values="数量",
            fill_value=0,
        )
        st.bar_chart(pivot)

st.subheader("存储开销对比")

storage_by_method = (
    filtered_df.groupby("method_text")
    .agg(
        total_storage_size_bytes=("storage_size_bytes", "sum"),
        avg_storage_size_bytes=("storage_size_bytes", "mean"),
        block_count=("method", "size"),
    )
    .reset_index()
    .rename(
        columns={
            "method_text": "恢复方式",
            "total_storage_size_bytes": "总存储大小（字节）",
            "avg_storage_size_bytes": "平均单块大小（字节）",
            "block_count": "块数量",
        }
    )
)

c3, c4 = st.columns(2)

with c3:
    st.caption("不同恢复方式总存储大小")
    if alt is not None:
        chart = (
            alt.Chart(storage_by_method)
            .mark_bar()
            .encode(
                x=alt.X("恢复方式:N", title="恢复方式"),
                y=alt.Y("总存储大小（字节）:Q", title="总存储大小（字节）"),
                tooltip=["恢复方式", "总存储大小（字节）", "块数量"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(storage_by_method.set_index("恢复方式")["总存储大小（字节）"])

with c4:
    st.caption("不同恢复方式平均单块大小")
    if alt is not None:
        chart = (
            alt.Chart(storage_by_method)
            .mark_bar()
            .encode(
                x=alt.X("恢复方式:N", title="恢复方式"),
                y=alt.Y("平均单块大小（字节）:Q", title="平均单块大小（字节）"),
                tooltip=["恢复方式", "平均单块大小（字节）", "块数量"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(storage_by_method.set_index("恢复方式")["平均单块大小（字节）"])

st.subheader("块级存储大小散点图")

scatter_df = filtered_df.dropna(subset=["storage_size_bytes"]).copy()

scatter_display_df = scatter_df[
    [
        "identity_alias",
        "version",
        "method_text",
        "block_type_text",
        "block_index",
        "storage_size_bytes",
        "status_text",
    ]
].rename(
    columns={
        "identity_alias": "身份标识",
        "version": "版本号",
        "method_text": "恢复方式",
        "block_type_text": "块类型",
        "block_index": "块编号",
        "storage_size_bytes": "存储大小（字节）",
        "status_text": "状态",
    }
)

if alt is not None and not scatter_display_df.empty:
    chart = (
        alt.Chart(scatter_display_df)
        .mark_circle(size=100)
        .encode(
            x=alt.X("块编号:Q", title="块编号"),
            y=alt.Y("存储大小（字节）:Q", title="存储大小（字节）"),
            color=alt.Color("恢复方式:N", title="恢复方式"),
            shape=alt.Shape("块类型:N", title="块类型"),
            tooltip=[
                "身份标识",
                "版本号",
                "恢复方式",
                "块类型",
                "块编号",
                "存储大小（字节）",
                "状态",
            ],
        )
        .properties(height=340)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.scatter_chart(scatter_display_df, x="块编号", y="存储大小（字节）")

st.subheader("恢复块更新时间趋势")

timeline_df = (
    filtered_df.dropna(subset=["updated_dt"])
    .groupby(["updated_date", "method_text"])
    .size()
    .reset_index(name="数量")
    .rename(
        columns={
            "updated_date": "日期",
            "method_text": "恢复方式",
        }
    )
)

if not timeline_df.empty:
    if alt is not None:
        chart = (
            alt.Chart(timeline_df)
            .mark_area(opacity=0.65)
            .encode(
                x=alt.X("日期:T", title="日期"),
                y=alt.Y("数量:Q", title="恢复块数量"),
                color=alt.Color("恢复方式:N", title="恢复方式"),
                tooltip=["日期", "恢复方式", "数量"],
            )
            .properties(height=300)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        pivot = timeline_df.pivot_table(
            index="日期",
            columns="恢复方式",
            values="数量",
            fill_value=0,
        )
        st.area_chart(pivot)
else:
    st.info("暂无可用于时间趋势分析的数据")

