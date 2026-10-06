"""
Streamlit 通用渲染组件模块

本模块提供 Streamlit 页面中常用的展示组件，包括页面标题、JSON 数据块、
哈希值比对结果以及校验结果标记的统一渲染函数。
所有组件均以中文作为默认展示语言，适用于调试、演示和答辩场景。
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from utils.formatters import short_hash


def page_header(title: str, description: str = "") -> None:
    """
    渲染页面主标题和可选说明文字。

    Args:
        title: 页面标题文本
        description: 标题下方的描述性文字（可选）
    """
    st.title(title)
    if description:
        st.caption(description)


def render_json_block(title: str, data: Any) -> None:
    """
    以格式化 JSON 代码块的形式展示数据。

    使用 `ensure_ascii=False` 保证中文原样输出，并自动将非可序列化对象
    转为字符串，避免渲染出错。

    Args:
        title: 数据块的标题
        data: 待展示的字典、列表或其它可序列化对象
    """
    st.markdown(f"**{title}**")
    st.code(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        language="json",
    )


def render_hash_compare(label: str, left: str | None, right: str | None) -> None:
    """
    并排展示两个哈希值的对比结果。

    左侧显示标签和“一致/不一致”结论，右侧两列分别展示两个哈希值的
    缩短形式（通过 `short_hash` 函数处理）。

    Args:
        label: 比对项目的名称（如“文档哈希”）
        left: 第一个哈希值（可携带 0x 前缀）
        right: 第二个哈希值（可携带 0x 前缀）
    """
    matched = bool(left) and bool(right) and str(left).lower() == str(right).lower()
    col1, col2, col3 = st.columns([1.2, 3, 3])
    col1.metric(label, "一致" if matched else "不一致")
    col2.text(short_hash(left))
    col3.text(short_hash(right))


def render_result_flag(label: str, value: bool) -> None:
    """
    根据布尔值渲染“通过”或“未通过”状态标记。

    使用 Streamlit 的 `success` 和 `error` 组件，使得验证结果一目了然。

    Args:
        label: 校验项名称（如“版本哈希链”）
        value: True 表示通过，False 表示未通过
    """
    if value:
        st.success(f"{label}：通过")
    else:
        st.error(f"{label}：未通过")