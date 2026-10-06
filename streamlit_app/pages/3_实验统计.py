"""
实验统计

展示实验记录集合中的性能数据，包括：
1. 注册、更新、验证、恢复等场景的耗时统计
2. 链上消耗量统计
3. 多副本与纠删码恢复块数量、存储开销对比
4. 自动选择、多副本、纠删码恢复方式对比
5. 成功率、95 分位耗时、趋势图和散点图

该页面用于论文实验分析与答辩演示。
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None

from components.renderers import page_header
from services.data_service import experiment_summary, get_experiment_records


page_header(
    "实验统计",
    "展示实验记录集合中的耗时、链上消耗量、恢复方式、恢复块数量和存储开销，方便论文作图与答辩演示。",
)


# =============================
# 展示文本映射
# =============================

COLUMN_NAME_MAP = {
    "scene": "实验场景",
    "total": "记录总数",
    "count": "数量",
    "success": "是否成功",
    "success_count": "成功次数",
    "failed_count": "失败次数",
    "unknown_count": "未知次数",
    "success_rate": "成功率（%）",
    "avg_latency_ms": "平均耗时（毫秒）",
    "median_latency_ms": "中位数耗时（毫秒）",
    "p95_latency_ms": "95分位耗时（毫秒）",
    "min_latency_ms": "最小耗时（毫秒）",
    "max_latency_ms": "最大耗时（毫秒）",
    "latency_ms": "耗时（毫秒）",
    "gas_used": "链上消耗量",
    "avg_gas_used": "平均链上消耗量",
    "changed_attribute_count": "变更属性数量",
    "avg_changed_attribute_count": "平均变更属性数",
    "used_block_count": "使用块数",
    "avg_used_block_count": "平均使用块数",
    "did": "DID标识",
    "did_short": "DID简写",
    "version": "版本号",
    "created_at": "创建时间",
    "created_date": "创建日期",
    "updated_at": "更新时间",
    "success_text": "执行结果",
    "requested_recovery_method": "请求恢复方式",
    "actual_recovery_method": "实际恢复方式",
    "recovery_method": "恢复方式",
    "auto_verified": "自动验证通过",
    "transaction_verified": "交易验证通过",
    "duplication_block_count": "多副本块数量",
    "erasure_code_block_count": "纠删码块数量",
    "duplication_storage_size_bytes": "多副本存储大小（字节）",
    "erasure_code_storage_size_bytes": "纠删码存储大小（字节）",
    "error": "错误信息",
    "error_short": "错误摘要",
}

SCENE_NAME_MAP = {
    "register": "注册",
    "registration": "注册",
    "register_did": "DID注册",
    "did_register": "DID注册",
    "create": "创建",
    "create_did": "DID创建",
    "upsert": "创建或更新",
    "update": "更新",
    "update_did": "DID更新",
    "did_update": "DID更新",
    "verify": "验证",
    "verification": "验证",
    "verify_did": "DID验证",
    "recover": "恢复",
    "recovery": "恢复",
    "recover_did": "DID恢复",
    "restore": "恢复",
    "auth": "身份认证",
    "authenticate": "身份认证",
    "login": "登录认证",
    "delete": "删除",
    "tamper": "篡改检测",
    "rollback": "回滚检测",
    "normal": "正常流程",
}

RECOVERY_METHOD_MAP = {
    "auto": "自动选择",
    "manual": "手动指定",
    "duplication": "多副本",
    "erasure_code": "纠删码",
    "erasure": "纠删码",
    "unknown": "未知",
    "none": "无",
    "nan": "未知",
    "duplication_block_count": "多副本",
    "erasure_code_block_count": "纠删码",
    "duplication_storage_size_bytes": "多副本",
    "erasure_code_storage_size_bytes": "纠删码",
}

TOKEN_NAME_MAP = {
    "did": "DID",
    "register": "注册",
    "registration": "注册",
    "create": "创建",
    "upsert": "创建或更新",
    "update": "更新",
    "verify": "验证",
    "verification": "验证",
    "recover": "恢复",
    "recovery": "恢复",
    "restore": "恢复",
    "auth": "认证",
    "authenticate": "认证",
    "login": "登录",
    "delete": "删除",
    "tamper": "篡改",
    "tampered": "篡改",
    "rollback": "回滚",
    "normal": "正常",
    "success": "成功",
    "failed": "失败",
    "fail": "失败",
    "failure": "失败",
    "error": "错误",
    "transaction": "交易",
    "storage": "存储",
    "block": "块",
    "count": "数量",
    "document": "文档",
    "method": "方式",
    "requested": "请求",
    "actual": "实际",
    "latency": "耗时",
    "version": "版本",
    "hash": "哈希",
    "auto": "自动",
    "manual": "手动",
    "duplication": "多副本",
    "erasure": "纠删码",
    "code": "编码",
    "unknown": "未知",
    "none": "无",
}


# =============================
# 工具函数
# =============================

def _to_datetime_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


def _to_numeric(df: pd.DataFrame, col: str) -> None:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except Exception:
        return False


def _short_text(value, head: int = 18, tail: int = 8) -> str:
    if _is_empty_value(value):
        return "-"
    text = str(value)
    if len(text) <= head + tail + 3:
        return text
    return f"{text[:head]}...{text[-tail:]}"


def _success_text(value) -> str:
    if value is True:
        return "成功"
    if value is False:
        return "失败"
    return "未知"


def _bool_text(value) -> str:
    if value is True:
        return "是"
    if value is False:
        return "否"
    return "未知"


def _valid_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float((series == True).sum() / len(series) * 100)


def _translate_identifier(value: Any, exact_map: dict[str, str], fallback: str) -> str:
    """将数据库里的英文标识转成中文展示文本，不改变内部真实字段。"""
    if _is_empty_value(value):
        return fallback

    text = str(value).strip()
    if not text:
        return fallback

    lower_text = text.lower()
    if lower_text in exact_map:
        return exact_map[lower_text]

    tokens = [token for token in re.split(r"[_\-\s/]+", lower_text) if token]
    translated_tokens: list[str] = []

    for token in tokens:
        if token in exact_map:
            translated_tokens.append(exact_map[token])
        elif token in TOKEN_NAME_MAP:
            translated_tokens.append(TOKEN_NAME_MAP[token])
        elif token.isdigit():
            translated_tokens.append(token)

    if translated_tokens:
        return "".join(translated_tokens)

    # 无法识别的英文场景不直接展示原文，避免页面表格继续出现英文。
    if re.search(r"[A-Za-z]", text):
        return fallback
    return text


def _scene_text(value: Any) -> str:
    return _translate_identifier(value, SCENE_NAME_MAP, "其他场景")


def _recovery_method_text(value: Any) -> str:
    return _translate_identifier(value, RECOVERY_METHOD_MAP, "未知")


def _error_text(value: Any) -> str:
    if _is_empty_value(value):
        return "-"
    text = _short_text(value, 40, 20)
    # 表格中不展示英文异常栈或英文错误原文；需要原文时看后台日志。
    if re.search(r"[A-Za-z]", text):
        return "系统异常，详见后台日志"
    return text


def _localize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """生成只用于页面展示的中文表格，避免英文列名和英文枚举值直接出现在页面中。"""
    display_df = df.copy()

    for col in display_df.columns:
        if col in {"scene", "实验场景"}:
            display_df[col] = display_df[col].apply(_scene_text)
        elif col in {
            "requested_recovery_method",
            "actual_recovery_method",
            "recovery_method",
            "恢复方式",
            "请求恢复方式",
            "实际恢复方式",
        }:
            display_df[col] = display_df[col].apply(_recovery_method_text)
        elif col in {"auto_verified", "transaction_verified", "是否自动验证通过", "交易验证通过"}:
            display_df[col] = display_df[col].apply(_bool_text)
        elif col == "success":
            display_df[col] = display_df[col].apply(_success_text)
        elif col in {"error", "error_short", "错误信息", "错误摘要"}:
            display_df[col] = display_df[col].apply(_error_text)

    numeric_cols = display_df.select_dtypes(include="number").columns
    if len(numeric_cols) > 0:
        display_df[numeric_cols] = display_df[numeric_cols].round(2)

    return display_df.rename(columns=COLUMN_NAME_MAP)


def _localize_json_like(value: Any) -> Any:
    """调试摘要展示用：尽量把字典键中文化。"""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            zh_key = COLUMN_NAME_MAP.get(str(key), _translate_identifier(key, {}, "其他字段"))
            result[zh_key] = _localize_json_like(item)
        return result
    if isinstance(value, list):
        return [_localize_json_like(item) for item in value]
    if isinstance(value, bool):
        return _bool_text(value)
    return value


def _render_altair_or_bar(df: pd.DataFrame, index_col: str, value_col: str):
    if df.empty:
        st.info("暂无可视化数据")
        return

    if alt is not None:
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X(f"{index_col}:N", title=index_col, sort="-y"),
                y=alt.Y(f"{value_col}:Q", title=value_col),
                tooltip=list(df.columns),
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(df.set_index(index_col)[value_col])


# =============================
# 侧边栏
# =============================

with st.sidebar:
    st.subheader("筛选条件")
    limit = st.slider("读取实验记录数", min_value=50, max_value=2000, value=300, step=50)
    st.caption("读取更多记录可以获得更完整趋势，但页面加载会略慢。")

    show_raw_summary = st.toggle("显示调试摘要", value=False)
    show_detail_table = st.toggle("显示明细表", value=True)


# =============================
# 读取数据
# =============================

try:
    summary = experiment_summary()
except Exception:
    summary = {}

try:
    latest_rows = get_experiment_records(limit=limit)
except Exception as exc:
    st.error(f"读取实验记录失败：{exc}")
    st.stop()

if not latest_rows:
    st.info("暂无实验记录数据")
    st.stop()

df = pd.DataFrame(latest_rows)

df = _ensure_columns(
    df,
    [
        "scene",
        "did",
        "version",
        "success",
        "latency_ms",
        "gas_used",
        "created_at",
        "updated_at",
        "changed_attribute_count",
        "transaction_verified",
        "requested_recovery_method",
        "actual_recovery_method",
        "recovery_method",
        "auto_verified",
        "used_block_count",
        "duplication_block_count",
        "erasure_code_block_count",
        "duplication_storage_size_bytes",
        "erasure_code_storage_size_bytes",
        "error",
    ],
)

numeric_cols = [
    "version",
    "latency_ms",
    "gas_used",
    "changed_attribute_count",
    "used_block_count",
    "duplication_block_count",
    "erasure_code_block_count",
    "duplication_storage_size_bytes",
    "erasure_code_storage_size_bytes",
]

for col in numeric_cols:
    _to_numeric(df, col)

df["created_dt"] = _to_datetime_series(df["created_at"])
df["created_date"] = df["created_dt"].dt.date.astype("string")
df["did_short"] = df["did"].apply(_short_text)
df["success_text"] = df["success"].apply(_success_text)

# 兼容旧字段
df["actual_recovery_method"] = df["actual_recovery_method"].fillna(df["recovery_method"])
df["requested_recovery_method"] = df["requested_recovery_method"].fillna(df["recovery_method"])

# =============================
# 页面筛选
# =============================

all_scenes = sorted(df["scene"].dropna().unique().tolist())
all_success = ["全部", "成功", "失败", "未知"]

filter_col_1, filter_col_2, filter_col_3 = st.columns([2, 1, 1])

with filter_col_1:
    selected_scenes = st.multiselect(
        "实验场景",
        options=all_scenes,
        default=all_scenes,
        format_func=_scene_text,
    )

with filter_col_2:
    selected_success = st.selectbox("执行结果", options=all_success, index=0)

with filter_col_3:
    only_with_gas = st.toggle("仅看有链上消耗记录", value=False)

filtered_df = df.copy()

if selected_scenes:
    filtered_df = filtered_df[filtered_df["scene"].isin(selected_scenes)]

if selected_success == "成功":
    filtered_df = filtered_df[filtered_df["success"] == True]
elif selected_success == "失败":
    filtered_df = filtered_df[filtered_df["success"] == False]
elif selected_success == "未知":
    filtered_df = filtered_df[filtered_df["success"].isna()]

if only_with_gas:
    filtered_df = filtered_df[filtered_df["gas_used"].notna()]

if filtered_df.empty:
    st.warning("当前筛选条件下暂无实验记录")
    st.stop()


# =============================
# 总览指标
# =============================

st.subheader("实验总览")

total_count = len(filtered_df)
success_count = int((filtered_df["success"] == True).sum())
failed_count = int((filtered_df["success"] == False).sum())
unknown_count = int(filtered_df["success"].isna().sum())
success_rate = success_count / total_count * 100 if total_count else 0

avg_latency = filtered_df["latency_ms"].mean()
median_latency = filtered_df["latency_ms"].median()
p95_latency = filtered_df["latency_ms"].quantile(0.95)
avg_gas = filtered_df["gas_used"].mean()

m1, m2, m3, m4, m5, m6 = st.columns(6)

with m1:
    st.metric("记录总数", total_count)
with m2:
    st.metric("成功", success_count)
with m3:
    st.metric("失败", failed_count)
with m4:
    st.metric("成功率", f"{success_rate:.1f}%")
with m5:
    st.metric("平均耗时", f"{avg_latency:.2f} 毫秒" if pd.notna(avg_latency) else "-")
with m6:
    st.metric("95分位耗时", f"{p95_latency:.2f} 毫秒" if pd.notna(p95_latency) else "-")

metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)

with metric_col_1:
    st.metric("中位数耗时", f"{median_latency:.2f} 毫秒" if pd.notna(median_latency) else "-")
with metric_col_2:
    st.metric("平均链上消耗量", f"{avg_gas:.0f}" if pd.notna(avg_gas) else "-")
with metric_col_3:
    st.metric("未知结果", unknown_count)
with metric_col_4:
    recover_count = int(
        filtered_df["scene"].astype(str).str.contains("recover", case=False, na=False).sum()
    )
    st.metric("恢复实验记录", recover_count)


# =============================
# 按场景汇总
# =============================

st.subheader("按场景汇总")

scene_summary = (
    filtered_df.groupby("scene", dropna=False)
    .agg(
        total=("scene", "size"),
        success_count=("success", lambda s: int((s == True).sum())),
        failed_count=("success", lambda s: int((s == False).sum())),
        avg_latency_ms=("latency_ms", "mean"),
        median_latency_ms=("latency_ms", "median"),
        p95_latency_ms=("latency_ms", lambda s: s.quantile(0.95)),
        min_latency_ms=("latency_ms", "min"),
        max_latency_ms=("latency_ms", "max"),
        avg_gas_used=("gas_used", "mean"),
        avg_changed_attribute_count=("changed_attribute_count", "mean"),
        avg_used_block_count=("used_block_count", "mean"),
    )
    .reset_index()
)

scene_summary["success_rate"] = scene_summary.apply(
    lambda row: row["success_count"] / row["total"] * 100 if row["total"] else 0,
    axis=1,
)

scene_summary_display = _localize_dataframe(scene_summary)
st.dataframe(scene_summary_display, use_container_width=True, hide_index=True)


# =============================
# 场景数量与成功率
# =============================

st.subheader("场景分布与成功率")

chart_col_1, chart_col_2 = st.columns(2)

with chart_col_1:
    st.caption("场景记录数量占比")
    count_df = _localize_dataframe(scene_summary[["scene", "total"]].copy())

    if alt is not None:
        chart = (
            alt.Chart(count_df)
            .mark_arc(innerRadius=55)
            .encode(
                theta=alt.Theta("记录总数:Q"),
                color=alt.Color("实验场景:N", title="场景"),
                tooltip=["实验场景", "记录总数"],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(count_df.set_index("实验场景")["记录总数"])

with chart_col_2:
    st.caption("各场景成功率")
    if alt is not None:
        chart = (
            alt.Chart(scene_summary_display)
            .mark_bar()
            .encode(
                x=alt.X("实验场景:N", title="场景", sort="-y"),
                y=alt.Y("成功率（%）:Q", title="成功率（%）", scale=alt.Scale(domain=[0, 100])),
                tooltip=[
                    "实验场景",
                    "记录总数",
                    "成功次数",
                    "失败次数",
                    "成功率（%）",
                ],
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(scene_summary_display.set_index("实验场景")["成功率（%）"])


# =============================
# 恢复块生成开销分析
# =============================

st.subheader("恢复块生成与存储开销分析")

recovery_storage_cols = [
    "duplication_block_count",
    "erasure_code_block_count",
    "duplication_storage_size_bytes",
    "erasure_code_storage_size_bytes",
]

has_recovery_storage_data = any(
    col in filtered_df.columns and filtered_df[col].notna().any()
    for col in recovery_storage_cols
)

if not has_recovery_storage_data:
    st.info("暂无恢复块生成统计。执行注册或更新后，应记录多副本和纠删码的块数量及存储大小。")
else:
    storage_df = filtered_df[
        [
            "scene",
            "did_short",
            "version",
            "duplication_block_count",
            "erasure_code_block_count",
            "duplication_storage_size_bytes",
            "erasure_code_storage_size_bytes",
        ]
    ].dropna(
        how="all",
        subset=[
            "duplication_block_count",
            "erasure_code_block_count",
            "duplication_storage_size_bytes",
            "erasure_code_storage_size_bytes",
        ],
    )

    s1, s2 = st.columns(2)

    with s1:
        st.caption("多副本与纠删码块数量对比")

        block_count_compare = storage_df[
            ["scene", "did_short", "version", "duplication_block_count", "erasure_code_block_count"]
        ].melt(
            id_vars=["scene", "did_short", "version"],
            value_vars=["duplication_block_count", "erasure_code_block_count"],
            var_name="恢复方式",
            value_name="块数量",
        )
        block_count_chart = _localize_dataframe(block_count_compare.dropna(subset=["块数量"]))

        if alt is not None:
            chart = (
                alt.Chart(block_count_chart)
                .mark_bar()
                .encode(
                    x=alt.X("恢复方式:N", title="恢复方式"),
                    y=alt.Y("mean(块数量):Q", title="平均块数量"),
                    color=alt.Color("恢复方式:N", title="恢复方式"),
                    tooltip=[
                        alt.Tooltip("恢复方式:N", title="恢复方式"),
                        alt.Tooltip("块数量:Q", aggregate="mean", title="平均块数量"),
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            block_count_fallback = pd.DataFrame(
                {
                    "恢复方式": ["多副本", "纠删码"],
                    "平均块数量": [
                        storage_df["duplication_block_count"].mean(),
                        storage_df["erasure_code_block_count"].mean(),
                    ],
                }
            )
            st.bar_chart(block_count_fallback.set_index("恢复方式")["平均块数量"])

    with s2:
        st.caption("多副本与纠删码存储大小对比")

        storage_compare = storage_df[
            [
                "scene",
                "did_short",
                "version",
                "duplication_storage_size_bytes",
                "erasure_code_storage_size_bytes",
            ]
        ].melt(
            id_vars=["scene", "did_short", "version"],
            value_vars=[
                "duplication_storage_size_bytes",
                "erasure_code_storage_size_bytes",
            ],
            var_name="恢复方式",
            value_name="存储大小（字节）",
        )
        storage_chart = _localize_dataframe(storage_compare.dropna(subset=["存储大小（字节）"]))

        if alt is not None:
            chart = (
                alt.Chart(storage_chart)
                .mark_bar()
                .encode(
                    x=alt.X("恢复方式:N", title="恢复方式"),
                    y=alt.Y("mean(存储大小（字节）):Q", title="平均存储大小（字节）"),
                    color=alt.Color("恢复方式:N", title="恢复方式"),
                    tooltip=[
                        alt.Tooltip("恢复方式:N", title="恢复方式"),
                        alt.Tooltip("存储大小（字节）:Q", aggregate="mean", title="平均存储大小（字节）"),
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            storage_fallback = pd.DataFrame(
                {
                    "恢复方式": ["多副本", "纠删码"],
                    "平均存储大小（字节）": [
                        storage_df["duplication_storage_size_bytes"].mean(),
                        storage_df["erasure_code_storage_size_bytes"].mean(),
                    ],
                }
            )
            st.bar_chart(storage_fallback.set_index("恢复方式")["平均存储大小（字节）"])

    st.caption("恢复块生成记录明细")
    st.dataframe(_localize_dataframe(storage_df), use_container_width=True, hide_index=True)


# =============================
# 恢复实验对比
# =============================

st.subheader("恢复实验对比")

recover_df = filtered_df[
    (filtered_df["scene"].astype(str).str.contains("recover", case=False, na=False))
    | (filtered_df["actual_recovery_method"].notna())
    | (filtered_df["requested_recovery_method"].notna())
].copy()

if recover_df.empty:
    st.info("暂无恢复相关实验记录。执行恢复操作后会出现请求恢复方式、实际恢复方式、自动验证等字段。")
else:
    recover_df["requested_recovery_method"] = recover_df["requested_recovery_method"].fillna("unknown")
    recover_df["actual_recovery_method"] = recover_df["actual_recovery_method"].fillna("unknown")

    r1, r2, r3, r4, r5 = st.columns(5)

    with r1:
        st.metric("恢复实验数", len(recover_df))
    with r2:
        st.metric("自动验证通过", int((recover_df["auto_verified"] == True).sum()))
    with r3:
        st.metric("多副本实际使用", int((recover_df["actual_recovery_method"] == "duplication").sum()))
    with r4:
        st.metric("纠删码实际使用", int((recover_df["actual_recovery_method"] == "erasure_code").sum()))
    with r5:
        avg_used_block_count = recover_df["used_block_count"].mean()
        st.metric("平均使用块数", f"{avg_used_block_count:.2f}" if pd.notna(avg_used_block_count) else "-")

    recover_col_1, recover_col_2 = st.columns(2)

    with recover_col_1:
        st.caption("请求恢复方式与实际恢复方式")

        method_cross = (
            recover_df.groupby(["requested_recovery_method", "actual_recovery_method"])
            .size()
            .reset_index(name="count")
        )
        method_cross_display = _localize_dataframe(method_cross)

        if alt is not None:
            chart = (
                alt.Chart(method_cross_display)
                .mark_rect()
                .encode(
                    x=alt.X("请求恢复方式:N", title="请求方式"),
                    y=alt.Y("实际恢复方式:N", title="实际方式"),
                    color=alt.Color("数量:Q", title="数量"),
                    tooltip=["请求恢复方式", "实际恢复方式", "数量"],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            pivot = method_cross_display.pivot_table(
                index="实际恢复方式",
                columns="请求恢复方式",
                values="数量",
                fill_value=0,
            )
            st.dataframe(pivot, use_container_width=True)

    with recover_col_2:
        st.caption("不同恢复方式平均耗时")

        method_latency = (
            recover_df.groupby("actual_recovery_method")
            .agg(
                total=("actual_recovery_method", "size"),
                success_count=("success", lambda s: int((s == True).sum())),
                avg_latency_ms=("latency_ms", "mean"),
                median_latency_ms=("latency_ms", "median"),
                p95_latency_ms=("latency_ms", lambda s: s.quantile(0.95)),
                avg_used_block_count=("used_block_count", "mean"),
            )
            .reset_index()
        )

        method_latency["success_rate"] = method_latency.apply(
            lambda row: row["success_count"] / row["total"] * 100 if row["total"] else 0,
            axis=1,
        )
        method_latency_display = _localize_dataframe(method_latency)

        if alt is not None:
            chart = (
                alt.Chart(method_latency_display)
                .mark_bar()
                .encode(
                    x=alt.X("实际恢复方式:N", title="实际恢复方式"),
                    y=alt.Y("平均耗时（毫秒）:Q", title="平均耗时（毫秒）"),
                    tooltip=[
                        "实际恢复方式",
                        "记录总数",
                        "平均耗时（毫秒）",
                        "中位数耗时（毫秒）",
                        "95分位耗时（毫秒）",
                        "成功率（%）",
                        "平均使用块数",
                    ],
                )
                .properties(height=320)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.bar_chart(method_latency_display.set_index("实际恢复方式")["平均耗时（毫秒）"])

    st.caption("恢复方式汇总表")
    st.dataframe(method_latency_display, use_container_width=True, hide_index=True)




# =============================
# 失败原因分析
# =============================

st.subheader("失败原因分析")

failed_df = filtered_df[filtered_df["success"] == False].copy()

if failed_df.empty:
    st.success("当前筛选范围内没有失败实验记录")
else:
    failed_df["error_short"] = failed_df["error"].apply(lambda x: _short_text(x, 40, 20))

    error_summary = (
        failed_df.groupby(["scene", "error_short"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    st.dataframe(_localize_dataframe(error_summary), use_container_width=True, hide_index=True)


# =============================
# 调试摘要
# =============================

if show_raw_summary:
    st.subheader("调试摘要")
    st.json(_localize_json_like(summary))


# =============================
# 最近实验记录明细
# =============================

if show_detail_table:
    st.subheader("最近实验记录明细")

    display_cols = [
        "created_at",
        "scene",
        "success_text",
        "latency_ms",
        "gas_used",
        "did_short",
        "version",
        "requested_recovery_method",
        "actual_recovery_method",
        "auto_verified",
        "used_block_count",
        "transaction_verified",
        "changed_attribute_count",
        "duplication_block_count",
        "erasure_code_block_count",
        "duplication_storage_size_bytes",
        "erasure_code_storage_size_bytes",
        "error",
    ]

    existing_cols = [col for col in display_cols if col in filtered_df.columns]

    detail_df = filtered_df[existing_cols].sort_values("created_at", ascending=False)

    st.dataframe(
        _localize_dataframe(detail_df),
        use_container_width=True,
        hide_index=True,
    )
