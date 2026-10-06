"""
恢复编解码与数据容灾模块

最终设计：
一条 did_recovery_blocks 记录表示一个独立恢复块单元。

duplication:
    replica 0 -> 一条记录
    replica 1 -> 一条记录
    replica 2 -> 一条记录

erasure_code:
    data_shard 0 -> 一条记录
    data_shard 1 -> 一条记录
    data_shard 2 -> 一条记录
    data_shard 3 -> 一条记录
    parity_shard -> 一条记录

当前 erasure_code 使用 XOR 单校验分片方案：
- data_shards = 4
- parity_shard = 1
- 最多支持恢复 1 个 data_shard 丢失
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from typing import Any

from infrastructure.storage.canonical_json import to_canonical_json


class RecoveryCodecError(Exception):
    """恢复编解码异常。"""
    pass


def normalize_recovery_method(method: str | None) -> str | None:
    """
    统一恢复方式名称。

    返回：
        None            -> auto
        duplication     -> 多副本
        erasure_code    -> 纠删码
    """
    if method in (None, "", "auto"):
        return None

    method_map = {
        "duplication": "duplication",
        "replica": "duplication",
        "erasure_code": "erasure_code",
        "erasure": "erasure_code",
    }

    if method not in method_map:
        raise RecoveryCodecError(f"未知的恢复方法：{method}")

    return method_map[method]


def payload_hash(payload: str) -> str:
    """
    计算单个恢复块 payload 的哈希，用于检测恢复块是否被篡改。
    """
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_recovery_block_units(
    document: dict[str, Any],
    replica_count: int = 3,
    data_shard_count: int = 4,
) -> list[dict[str, Any]]:
    """
    为 DID 文档生成所有恢复块单元。

    返回一个列表，每个元素代表一条 did_recovery_blocks 记录中的块数据。
    """
    units: list[dict[str, Any]] = []
    units.extend(build_duplication_block_units(document, replica_count=replica_count))
    units.extend(build_erasure_code_block_units(document, data_shard_count=data_shard_count))
    return units


def build_duplication_block_units(
    document: dict[str, Any],
    replica_count: int = 3,
) -> list[dict[str, Any]]:
    """
    构建 duplication 多副本恢复块单元。

    每个 replica 单独成为一条恢复块记录。
    """
    payload_bytes = to_canonical_json(document).encode("utf-8")
    encoded = base64.b64encode(payload_bytes).decode("ascii")

    units: list[dict[str, Any]] = []

    for index in range(replica_count):
        units.append(
            {
                "method": "duplication",
                "block_type": "replica",
                "block_index": index,
                "payload": encoded,
                "payload_hash": payload_hash(encoded),
                "codec": None,
                "shard_size": None,
                "original_length": len(payload_bytes),
                "data_shard_count": None,
                "recoverable_missing_count": None,
            }
        )

    return units


def build_erasure_code_block_units(
    document: dict[str, Any],
    data_shard_count: int = 4,
) -> list[dict[str, Any]]:
    """
    构建 erasure_code 纠删码恢复块单元。

    每个 data_shard 单独一条记录，parity_shard 也单独一条记录。
    """
    payload_bytes = to_canonical_json(document).encode("utf-8")
    encoded = encode_xor_parity(payload_bytes, data_shards=data_shard_count)

    units: list[dict[str, Any]] = []

    for index, shard_payload in enumerate(encoded["data_shards"]):
        units.append(
            {
                "method": "erasure_code",
                "block_type": "data_shard",
                "block_index": index,
                "payload": shard_payload,
                "payload_hash": payload_hash(shard_payload),
                "codec": encoded["codec"],
                "shard_size": encoded["shard_size"],
                "original_length": encoded["original_length"],
                "data_shard_count": encoded["data_shard_count"],
                "recoverable_missing_count": 1,
            }
        )

    parity_payload = encoded["parity_shard"]

    units.append(
        {
            "method": "erasure_code",
            "block_type": "parity_shard",
            "block_index": 0,
            "payload": parity_payload,
            "payload_hash": payload_hash(parity_payload),
            "codec": encoded["codec"],
            "shard_size": encoded["shard_size"],
            "original_length": encoded["original_length"],
            "data_shard_count": encoded["data_shard_count"],
            "recoverable_missing_count": 1,
        }
    )

    return units


def summarize_recovery_units(units: list[dict[str, Any]]) -> dict[str, Any]:
    """
    生成恢复块摘要，用于注册/更新接口返回和实验统计。
    """
    summary = {
        "duplication": {
            "block_count": 0,
            "storage_size_bytes": 0,
            "replica_count": 0,
        },
        "erasure_code": {
            "block_count": 0,
            "storage_size_bytes": 0,
            "data_shard_count": 0,
            "parity_shard_count": 0,
            "recoverable_missing_count": 1,
        },
    }

    for unit in units:
        method = unit["method"]
        size = len(str(unit.get("payload") or "").encode("utf-8"))

        if method == "duplication":
            summary["duplication"]["block_count"] += 1
            summary["duplication"]["replica_count"] += 1
            summary["duplication"]["storage_size_bytes"] += size

        elif method == "erasure_code":
            summary["erasure_code"]["block_count"] += 1
            summary["erasure_code"]["storage_size_bytes"] += size

            if unit.get("block_type") == "data_shard":
                summary["erasure_code"]["data_shard_count"] += 1

            if unit.get("block_type") == "parity_shard":
                summary["erasure_code"]["parity_shard_count"] += 1

            summary["erasure_code"]["recoverable_missing_count"] = (
                unit.get("recoverable_missing_count") or 1
            )

    return summary


def recover_document_from_block_units(
    blocks: list[dict[str, Any]],
    method: str,
    missing_data_indexes: list[int] | None = None,
) -> tuple[dict[str, Any], str]:
    """
    从恢复块单元列表恢复 DID 文档。

    Args:
        blocks: did_recovery_blocks 查询出来的单块记录列表
        method: duplication 或 erasure_code
        missing_data_indexes: 手动模拟缺失 data_shard 的索引

    Returns:
        (恢复后的 DID 文档, 实际恢复方式)
    """
    method = normalize_recovery_method(method)

    if method == "duplication":
        return recover_by_duplication_blocks(blocks), "duplication"

    if method == "erasure_code":
        return recover_by_erasure_code_blocks(
            blocks=blocks,
            missing_data_indexes=missing_data_indexes or [],
        ), "erasure_code"

    raise RecoveryCodecError("recover_document_from_block_units 必须指定具体恢复方式")


def _validate_block_payload(block: dict[str, Any]) -> bool:
    """
    校验单个恢复块 payload 是否被篡改。
    """
    payload = block.get("payload")
    expected_hash = block.get("payload_hash")

    if not payload or not expected_hash:
        return False

    return payload_hash(payload) == expected_hash


def recover_by_duplication_blocks(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """
    使用 duplication 副本块恢复。

    只要存在一个 payload_hash 正确且可解析的 replica，就可以恢复。
    """
    replica_blocks = [
        block
        for block in blocks
        if block.get("method") == "duplication"
        and block.get("block_type") == "replica"
    ]

    if not replica_blocks:
        raise RecoveryCodecError("未找到 duplication replica 块")

    last_error: Exception | None = None

    for block in sorted(replica_blocks, key=lambda x: int(x.get("block_index", 0))):
        if not _validate_block_payload(block):
            last_error = RecoveryCodecError(
                f"replica block_index={block.get('block_index')} payload_hash 校验失败"
            )
            continue

        try:
            raw = base64.b64decode(block["payload"])
            document = json.loads(raw.decode("utf-8"))

            if not isinstance(document, dict):
                raise RecoveryCodecError("replica 解码结果不是 DID 文档对象")

            return document

        except Exception as exc:
            last_error = exc
            continue

    if last_error:
        raise RecoveryCodecError(f"duplication 恢复失败：{last_error}")

    raise RecoveryCodecError("duplication 恢复失败：没有可用副本")


def recover_by_erasure_code_blocks(
    blocks: list[dict[str, Any]],
    missing_data_indexes: list[int] | None = None,
) -> dict[str, Any]:
    """
    使用 erasure_code 分片块恢复。
    """
    data_blocks = [
        block
        for block in blocks
        if block.get("method") == "erasure_code"
        and block.get("block_type") == "data_shard"
    ]

    parity_blocks = [
        block
        for block in blocks
        if block.get("method") == "erasure_code"
        and block.get("block_type") == "parity_shard"
    ]

    if not data_blocks and not parity_blocks:
        raise RecoveryCodecError("未找到 erasure_code 分片块")

    metadata_source = data_blocks[0] if data_blocks else parity_blocks[0]

    data_shard_count = int(metadata_source.get("data_shard_count") or 0)
    shard_size = int(metadata_source.get("shard_size") or 0)
    original_length = int(metadata_source.get("original_length") or 0)
    codec = metadata_source.get("codec")
    recoverable_missing_count = int(metadata_source.get("recoverable_missing_count") or 1)

    if data_shard_count <= 0:
        raise RecoveryCodecError("erasure_code.data_shard_count 无效")

    if shard_size <= 0:
        raise RecoveryCodecError("erasure_code.shard_size 无效")

    data_shards: list[str | None] = [None] * data_shard_count

    for block in data_blocks:
        index = int(block.get("block_index"))

        if index < 0 or index >= data_shard_count:
            raise RecoveryCodecError(f"非法 data_shard block_index={index}")

        if not _validate_block_payload(block):
            raise RecoveryCodecError(f"data_shard index={index} payload_hash 校验失败")

        data_shards[index] = block.get("payload")

    parity_payload = None
    if parity_blocks:
        parity_block = parity_blocks[0]

        if not _validate_block_payload(parity_block):
            raise RecoveryCodecError("parity_shard payload_hash 校验失败")

        parity_payload = parity_block.get("payload")

    erasure = {
        "codec": codec,
        "original_length": original_length,
        "data_shards": data_shards,
        "parity_shard": parity_payload,
        "shard_size": shard_size,
        "data_shard_count": data_shard_count,
        "recoverable_missing_count": recoverable_missing_count,
    }

    payload = decode_xor_parity(
        erasure=erasure,
        missing_data_indexes=missing_data_indexes or [],
    )

    try:
        document = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise RecoveryCodecError(f"erasure_code 恢复结果无法解析为 JSON：{exc}") from exc

    if not isinstance(document, dict):
        raise RecoveryCodecError("erasure_code 解码结果不是 DID 文档对象")

    return document


def encode_xor_parity(data: bytes, data_shards: int = 4) -> dict[str, Any]:
    """
    XOR 单校验分片编码。
    """
    if data_shards < 2:
        raise RecoveryCodecError("数据分片数必须大于等于 2")

    shard_size = int(math.ceil(len(data) / data_shards)) or 1
    padded = data + (b"\x00" * (shard_size * data_shards - len(data)))

    shards = [
        padded[i * shard_size:(i + 1) * shard_size]
        for i in range(data_shards)
    ]

    parity = bytearray(shard_size)
    for shard in shards:
        for idx, value in enumerate(shard):
            parity[idx] ^= value

    return {
        "codec": "xor_1",
        "original_length": len(data),
        "data_shards": [
            base64.b64encode(shard).decode("ascii")
            for shard in shards
        ],
        "parity_shard": base64.b64encode(bytes(parity)).decode("ascii"),
        "shard_size": shard_size,
        "data_shard_count": data_shards,
    }


def decode_xor_parity(
    erasure: dict[str, Any],
    missing_data_indexes: list[int] | None = None,
) -> bytes:
    """
    XOR 单校验分片解码。

    支持：
    - 0 个 data_shard 缺失：直接拼接恢复
    - 1 个 data_shard 缺失且 parity 存在：恢复
    - 超过 1 个 data_shard 缺失：失败
    """
    if erasure.get("codec") != "xor_1":
        raise RecoveryCodecError(f"不支持的纠删码编码方式：{erasure.get('codec')}")

    raw_shards = erasure.get("data_shards")
    if not isinstance(raw_shards, list) or not raw_shards:
        raise RecoveryCodecError("erasure_code.data_shards 为空")

    missing_data_indexes = set(missing_data_indexes or [])

    shard_size = int(erasure.get("shard_size") or 0)
    original_length = int(erasure.get("original_length") or 0)
    recoverable_missing_count = int(erasure.get("recoverable_missing_count") or 1)

    if shard_size <= 0:
        raise RecoveryCodecError("erasure_code.shard_size 无效")

    shards: list[bytearray | None] = []

    for index, shard in enumerate(raw_shards):
        if index in missing_data_indexes or not shard:
            shards.append(None)
            continue

        try:
            decoded = bytearray(base64.b64decode(shard))
        except Exception as exc:
            raise RecoveryCodecError(f"数据分片 {index} 无法解码：{exc}") from exc

        if len(decoded) != shard_size:
            raise RecoveryCodecError(
                f"数据分片 {index} 长度异常：expected={shard_size}, actual={len(decoded)}"
            )

        shards.append(decoded)

    missing_indexes = [
        index
        for index, shard in enumerate(shards)
        if shard is None
    ]

    if len(missing_indexes) > recoverable_missing_count:
        raise RecoveryCodecError(
            f"XOR 纠删码最多支持恢复 {recoverable_missing_count} 个丢失的数据分片"
        )

    if len(missing_indexes) == 1:
        parity_raw = erasure.get("parity_shard")
        if not parity_raw:
            raise RecoveryCodecError("缺少 parity_shard，无法恢复丢失分片")

        try:
            parity = bytearray(base64.b64decode(parity_raw))
        except Exception as exc:
            raise RecoveryCodecError(f"parity_shard 无法解码：{exc}") from exc

        if len(parity) != shard_size:
            raise RecoveryCodecError(
                f"parity_shard 长度异常：expected={shard_size}, actual={len(parity)}"
            )

        missing_index = missing_indexes[0]
        recovered = bytearray(shard_size)

        for byte_index in range(shard_size):
            value = parity[byte_index]

            for shard_index, shard in enumerate(shards):
                if shard_index == missing_index:
                    continue
                if shard is None:
                    raise RecoveryCodecError("存在多个缺失分片，无法恢复")
                value ^= shard[byte_index]

            recovered[byte_index] = value

        shards[missing_index] = recovered

    if any(shard is None for shard in shards):
        raise RecoveryCodecError("仍存在未恢复的数据分片")

    payload = b"".join(bytes(shard) for shard in shards if shard is not None)
    return payload[:original_length]