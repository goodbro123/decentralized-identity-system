"""
输入校验与解析工具模块

本模块提供 Streamlit 可视化平台中常用的输入校验与 JSON 解析函数，
统一处理用户输入错误并以中文异常消息反馈。
"""

from __future__ import annotations

import json


def validate_did(did: str) -> str:
    """
    校验并规范化 DID 字符串。

    要求 DID 不能为空且必须以 "did:" 开头，去除首尾空白后返回。

    Args:
        did: 用户输入的 DID 字符串

    Returns:
        str: 去除空白后的合法 DID

    Raises:
        ValueError: 当 DID 为空或不以 "did:" 开头时抛出
    """
    value = (did or "").strip()
    if not value:
        raise ValueError("DID 不能为空")
    if not value.startswith("did:"):
        raise ValueError("DID 必须以 did: 开头")
    return value


def parse_json_text(text: str):
    """
    将字符串解析为 JSON 对象。

    若解析失败，抛出包含原始错误信息的中文异常。

    Args:
        text: 待解析的 JSON 字符串

    Returns:
        解析后的 Python 对象（dict、list 等）

    Raises:
        ValueError: 当输入不是合法 JSON 时抛出
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误：{exc}") from exc