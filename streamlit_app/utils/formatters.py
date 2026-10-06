"""
格式化工具模块

本模块提供 Streamlit 可视化平台使用的通用格式化函数，包括：
- 哈希值缩短显示
- 时间对象统一格式化
- 布尔值转中文
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def short_hash(value: str | None, head: int = 10, tail: int = 8) -> str:
    """
    将长哈希字符串缩短为“前缀...后缀”的形式，便于界面展示。

    若输入为空或长度不超过截取长度，则原样返回。

    Args:
        value: 原始哈希字符串（可能为 None）
        head: 保留的前缀字符数，默认 10
        tail: 保留的后缀字符数，默认 8

    Returns:
        str: 缩短后的哈希字符串，输入为空时返回 "-"
    """
    if not value:
        return "-"
    text = str(value)
    if len(text) <= head + tail + 3:
        return text
    return f"{text[:head]}...{text[-tail:]}"


def format_time(value: Any) -> str:
    """
    将时间对象或字符串统一转换为 "YYYY-MM-DD HH:MM:SS" 格式。

    若输入为 None，返回 "-"；对于 datetime 对象，使用指定格式；
    其他类型直接转为字符串。

    Args:
        value: 待格式化的值（datetime 对象、字符串或 None）

    Returns:
        str: 格式化后的时间字符串
    """
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def bool_text(value: Any) -> str:
    """
    将任意值转换为中文布尔提示。

    True/非零/非空对象返回“是”，否则返回“否”。

    Args:
        value: 待转换的值

    Returns:
        str: "是" 或 "否"
    """
    return "是" if bool(value) else "否"