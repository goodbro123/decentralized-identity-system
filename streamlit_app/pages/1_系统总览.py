"""
系统总览

本页面以网格布局实时展示系统关键运行指标，用于在答辩、演示或调试时
快速确认系统是否处于正常状态。

注意：
页面展示层会将数据库字段名、接口返回键名和常见枚举值转换为中文，
避免 Streamlit 页面中出现英文表格列名、英文枚举值或原始接口字段名。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.renderers import page_header, render_json_block
from services.data_service import (
    backend_health,
    collection_counts,
    experiment_summary,
    latest_experiment_record,
    latest_verification_record,
)


# =============================
# 展示层中文化工具
# =============================

FIELD_NAME_MAP: dict[str, str] = {
    # 通用字段
    "_id": "记录编号",
    "id": "编号",
    "did": "身份标识",
    "did_short": "身份标识",
    "did_key": "身份键",
    "didKey": "身份键",
    "version": "版本号",
    "current_version": "当前版本号",
    "latest_version": "最新版本号",
    "scene": "实验场景",
    "status": "状态",
    "success": "是否成功",
    "success_text": "执行结果",
    "message": "提示信息",
    "data": "数据",
    "error": "错误信息",
    "error_short": "错误摘要",
    "created_at": "创建时间",
    "updated_at": "更新时间",
    "created_dt": "创建时间",
    "updated_dt": "更新时间",
    "created_date": "创建日期",
    "updated_date": "更新日期",

    # 健康检查
    "service": "服务名称",
    "health": "健康状态",
    "backend": "后端服务",
    "database": "数据库状态",
    "blockchain": "区块链状态",
    "mongo": "数据库",
    "mongodb": "数据库",
    "chain": "区块链",
    "contract": "智能合约",
    "provider": "链节点地址",

    # 集合统计
    "did_documents": "当前身份文档",
    "did_versions": "历史版本记录",
    "verification_records": "验证记录",
    "did_recovery_blocks": "恢复块记录",
    "experiment_records": "实验记录",

    # 实验摘要常见字段
    "total": "记录总数",
    "total_count": "记录总数",
    "count": "数量",
    "scene_count": "场景数量",
    "success_count": "成功次数",
    "failed_count": "失败次数",
    "failure_count": "失败次数",
    "unknown_count": "未知次数",
    "success_rate": "成功率",
    "avg_success_rate": "平均成功率",
    "latency_ms": "耗时（毫秒）",
    "avg_latency_ms": "平均耗时（毫秒）",
    "median_latency_ms": "中位耗时（毫秒）",
    "p95_latency_ms": "百分之九十五耗时（毫秒）",
    "min_latency_ms": "最小耗时（毫秒）",
    "max_latency_ms": "最大耗时（毫秒）",
    "gas_used": "燃料消耗",
    "avg_gas_used": "平均燃料消耗",
    "min_gas_used": "最小燃料消耗",
    "max_gas_used": "最大燃料消耗",
    "transaction_hash": "交易哈希",
    "transaction_verified": "交易是否验证",
    "block_number": "区块高度",
    "changed_attribute_count": "变更属性数量",

    # 验证记录常见字段
    "verify_result": "验证结果",
    "verification_result": "验证结果",
    "verified": "是否通过验证",
    "is_valid": "是否有效",
    "valid": "是否有效",
    "document_hash": "文档哈希",
    "doc_hash": "文档哈希",
    "docHash": "文档哈希",
    "chain_doc_hash": "链上文档哈希",
    "local_doc_hash": "本地文档哈希",
    "merkle_root": "默克尔根",
    "latestRoot": "最新根哈希",
    "version_hash": "版本哈希",
    "vh_latest": "最新版本哈希",
    "vhLatest": "最新版本哈希",
    "status_root": "状态根",
    "statusRoot": "状态根",
    "hash_match": "哈希是否匹配",
    "version_match": "版本是否匹配",

    # 恢复与实验字段
    "requested_recovery_method": "请求恢复方式",
    "actual_recovery_method": "实际恢复方式",
    "recovery_method": "恢复方式",
    "auto_verified": "自动验证是否通过",
    "used_block_count": "使用块数量",
    "duplication_block_count": "多副本块数量",
    "erasure_code_block_count": "纠删码块数量",
    "duplication_storage_size_bytes": "多副本存储大小（字节）",
    "erasure_code_storage_size_bytes": "纠删码存储大小（字节）",
    "storage_size_bytes": "存储大小（字节）",
    "payload_hash": "负载哈希",
    "method": "恢复方式",
    "block_type": "块类型",
    "block_index": "块编号",
    "codec": "编码方式",
    "raw": "原始数据",
}

VALUE_TEXT_MAP: dict[str, str] = {
    # 布尔和状态
    "true": "是",
    "false": "否",
    "none": "-",
    "null": "-",
    "nan": "-",
    "ok": "正常",
    "running": "运行中",
    "healthy": "健康",
    "unhealthy": "异常",
    "success": "成功",
    "failed": "失败",
    "failure": "失败",
    "error": "错误",
    "unknown": "未知",
    "active": "有效",
    "inactive": "无效",
    "valid": "有效",
    "invalid": "无效",
    "passed": "通过",
    "rejected": "拒绝",

    # 服务/集合名称
    "did-backend": "后端服务",
    "backend is healthy": "后端服务健康",
    "did_documents": "当前身份文档",
    "did_versions": "历史版本记录",
    "verification_records": "验证记录",
    "did_recovery_blocks": "恢复块记录",
    "experiment_records": "实验记录",

    # 实验场景
    "register": "注册",
    "registration": "注册",
    "did_register": "身份注册",
    "create": "创建",
    "upsert": "创建或更新",
    "update": "更新",
    "did_update": "身份更新",
    "verify": "验证",
    "verification": "验证",
    "normal_verify": "正常验证",
    "tamper_verify": "篡改验证",
    "rollback_verify": "回滚验证",
    "recover": "恢复",
    "recovery": "恢复",
    "did_recover": "身份恢复",
    "delete": "删除",
    "delete_document": "删除文档",

    # 恢复方式和块类型
    "auto": "自动选择",
    "duplication": "多副本",
    "erasure_code": "纠删码",
    "replica": "副本块",
    "data_shard": "数据分片",
    "parity_shard": "校验分片",
    "json": "数据文本",
    "utf-8": "通用文本编码",
    "bytes": "字节",
    "byte": "字节",
}

COLLECTION_LABELS: dict[str, str] = {
    "did_documents": "当前身份文档",
    "did_versions": "历史版本记录",
    "verification_records": "验证记录",
    "did_recovery_blocks": "恢复块记录",
    "experiment_records": "实验记录",
}

ASCII_ALPHA_RE = re.compile(r"[A-Za-z]")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
HEX_RE = re.compile(r"^0x[a-fA-F0-9]{12,}$")
DID_RE = re.compile(r"^did:", re.IGNORECASE)


def _dedupe_labels(labels: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for label in labels:
        if label not in seen:
            seen[label] = 1
            result.append(label)
        else:
            seen[label] += 1
            result.append(f"{label}（{seen[label]}）")
    return result


def _localize_key(key: Any, index: int = 0) -> str:
    text = str(key)
    if text in FIELD_NAME_MAP:
        return FIELD_NAME_MAP[text]

    lower_text = text.lower()
    if lower_text in FIELD_NAME_MAP:
        return FIELD_NAME_MAP[lower_text]

    # 未知字段不直接展示原始英文字段名，避免页面露出英文。
    return f"字段{index + 1}"


def _format_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, str):
        try:
            parsed = pd.to_datetime(value, errors="coerce", utc=True)
            if pd.notna(parsed):
                return parsed.tz_convert(None).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    return None


def _localize_string(value: str) -> str:
    text = value.strip()
    lower_text = text.lower()

    if not text:
        return "-"

    if lower_text in VALUE_TEXT_MAP:
        return VALUE_TEXT_MAP[lower_text]

    dt_text = _format_datetime(text)
    if dt_text is not None:
        return dt_text

    if DID_RE.match(text):
        return "身份标识已隐藏"

    if HEX_RE.match(text):
        return "哈希摘要已隐藏"

    if URL_RE.match(text):
        return "接口地址已隐藏"

    # 如果仍包含英文字符，说明可能是原始接口字段值、英文异常、
    # 英文枚举、地址、标识符或其他调试内容。展示层统一隐藏。
    if ASCII_ALPHA_RE.search(text):
        return "文本内容已隐藏"

    return text


def _localize_value(value: Any) -> Any:
    if value is None:
        return "-"

    if isinstance(value, bool):
        return "是" if value else "否"

    if isinstance(value, (datetime, date)):
        return _format_datetime(value) or str(value)

    if isinstance(value, dict):
        return _localize_dict(value)

    if isinstance(value, list):
        return [_localize_value(item) for item in value]

    if isinstance(value, tuple):
        return [_localize_value(item) for item in value]

    if isinstance(value, str):
        return _localize_string(value)

    return value


def _localize_dict(data: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index, (key, value) in enumerate(data.items()):
        cn_key = _localize_key(key, index)
        # 避免递归后中文键重复导致覆盖。
        if cn_key in result:
            suffix = 2
            new_key = f"{cn_key}（{suffix}）"
            while new_key in result:
                suffix += 1
                new_key = f"{cn_key}（{suffix}）"
            cn_key = new_key
        result[cn_key] = _localize_value(value)
    return result


def _localize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    display_df = df.copy()

    for col in display_df.columns:
        display_df[col] = display_df[col].map(_localize_value)

    display_df.columns = _dedupe_labels(
        [_localize_key(col, index) for index, col in enumerate(display_df.columns)]
    )

    return display_df


# =============================
# 页面主体
# =============================

page_header(
    "系统总览",
    "用于查看后端健康状态、链下集合规模、最近一次验证与实验情况。",
)

col_a, col_b = st.columns([1, 1])

with col_a:
    st.subheader("后端状态")
    try:
        health = backend_health()
        st.success("后端服务可用")
        render_json_block("健康检查响应", _localize_value(health))
    except Exception:
        st.error("后端不可用，请检查服务日志")

with col_b:
    st.subheader("链下集合统计")
    try:
        counts = collection_counts()

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric(COLLECTION_LABELS["did_documents"], counts.get("did_documents", 0))
        c2.metric(COLLECTION_LABELS["did_versions"], counts.get("did_versions", 0))
        c3.metric(COLLECTION_LABELS["verification_records"], counts.get("verification_records", 0))
        c4.metric(COLLECTION_LABELS["did_recovery_blocks"], counts.get("did_recovery_blocks", 0))
        c5.metric(COLLECTION_LABELS["experiment_records"], counts.get("experiment_records", 0))
    except Exception:
        st.error("集合统计失败，请检查数据库连接")

st.subheader("实验摘要")

try:
    summary = experiment_summary()
    rows = summary.get("scene_summary", [])

    if rows:
        summary_df = pd.DataFrame(rows)
        st.dataframe(
            _localize_dataframe(summary_df),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("暂无实验记录")
except Exception:
    st.error("实验摘要读取失败，请检查实验记录集合")

left, right = st.columns(2)

with left:
    st.subheader("最近一次验证记录")
    try:
        record = latest_verification_record()
        if record:
            render_json_block("最近验证记录", _localize_value(record))
        else:
            st.info("暂无验证记录")
    except Exception:
        st.error("验证记录读取失败，请检查验证记录集合")

with right:
    st.subheader("最近一次实验记录")
    try:
        record = latest_experiment_record()
        if record:
            render_json_block("最近实验记录", _localize_value(record))
        else:
            st.info("暂无实验记录")
    except Exception:
        st.error("实验记录读取失败，请检查实验记录集合")
