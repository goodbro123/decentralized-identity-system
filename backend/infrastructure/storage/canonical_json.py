"""
规范化 JSON 序列化模块

本模块提供稳定的 JSON 序列化功能，通过对字典进行排序并移除多余空白字符，
确保相同语义的数据内容始终生成完全一致的字符串表示，为后续哈希计算提供可靠输入。
"""

import json
from typing import Any


def to_canonical_json(data: Any) -> str:
    """
    将数据转换为规范化的 JSON 字符串

    对输入的字典或 JSON 兼容对象进行序列化，采用以下策略保证输出稳定性：
    1. 按字典键的字母顺序排序（sort_keys=True）
    2. 移除分隔符后的多余空白字符（separators=(",", ":")）
    3. 允许非 ASCII 字符原样输出（ensure_ascii=False）

    该函数主要用于 DID 文档的哈希前预处理，确保同一文档内容即使字段顺序不同，
    也能生成相同的哈希摘要，从而保证链上链下一致性校验的准确性。

    Args:
        data: 待序列化的数据，通常为 dict 或 list

    Returns:
        str: 规范化的 JSON 字符串，不含换行符和多余空格

    Example:
        >>> doc = {"name": "Alice", "age": 30}
        >>> to_canonical_json(doc)
        '{"age":30,"name":"Alice"}'
    """
    return json.dumps(
        data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
