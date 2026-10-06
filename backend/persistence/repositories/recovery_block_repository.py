"""
DID 恢复块仓储模块

最终设计：
一条 did_recovery_blocks 记录 = 一个恢复块单元。

duplication:
    每个 replica 单独一条记录

erasure_code:
    每个 data_shard 单独一条记录
    parity_shard 单独一条记录
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from infrastructure.mongo.mongo_client import get_database


COLLECTION_NAME = "did_recovery_blocks"


def _collection():
    db = get_database()
    collection = db[COLLECTION_NAME]

    collection.create_index(
        [
            ("did", 1),
            ("version", 1),
            ("method", 1),
            ("block_type", 1),
            ("block_index", 1),
        ],
        unique=True,
        background=True,
    )

    collection.create_index(
        [
            ("did", 1),
            ("version", 1),
            ("method", 1),
        ],
        background=True,
    )

    return collection


def _block_status(block: dict[str, Any]) -> str:
    payload = block.get("payload")
    payload_hash = block.get("payload_hash")

    if payload and payload_hash:
        return "active"

    return "missing"


def _storage_size(payload: str | None) -> int:
    if not payload:
        return 0
    return len(str(payload).encode("utf-8"))


def save_recovery_block_unit(
    did: str,
    version: int,
    block_unit: dict[str, Any],
    document_hash: str,
    merkle_root: str,
    version_hash: str,
    previous_version_hash: str,
    transaction_hash: str | None = None,
) -> dict | None:
    """
    保存一个恢复块单元。
    """
    collection = _collection()
    now = datetime.now(timezone.utc)

    payload = block_unit.get("payload")

    data = {
        "did": did,
        "version": int(version),
        "method": block_unit["method"],
        "block_type": block_unit["block_type"],
        "block_index": int(block_unit["block_index"]),
        "payload": payload,
        "payload_hash": block_unit.get("payload_hash"),
        "document_hash": document_hash,
        "merkle_root": merkle_root,
        "version_hash": version_hash,
        "previous_version_hash": previous_version_hash,
        "transaction_hash": transaction_hash,
        "codec": block_unit.get("codec"),
        "shard_size": block_unit.get("shard_size"),
        "original_length": block_unit.get("original_length"),
        "data_shard_count": block_unit.get("data_shard_count"),
        "recoverable_missing_count": block_unit.get("recoverable_missing_count"),
        "storage_size_bytes": _storage_size(payload),
        "status": _block_status(block_unit),
        "updated_at": now,
    }

    collection.update_one(
        {
            "did": did,
            "version": int(version),
            "method": data["method"],
            "block_type": data["block_type"],
            "block_index": data["block_index"],
        },
        {
            "$set": data,
            "$setOnInsert": {
                "created_at": now,
            },
        },
        upsert=True,
    )

    return get_recovery_block_unit(
        did=did,
        version=version,
        method=data["method"],
        block_type=data["block_type"],
        block_index=data["block_index"],
    )


def save_recovery_block_units(
    did: str,
    version: int,
    block_units: list[dict[str, Any]],
    document_hash: str,
    merkle_root: str,
    version_hash: str,
    previous_version_hash: str,
    transaction_hash: str | None = None,
) -> list[dict]:
    """
    批量保存恢复块单元。
    """
    saved = []

    for unit in block_units:
        item = save_recovery_block_unit(
            did=did,
            version=version,
            block_unit=unit,
            document_hash=document_hash,
            merkle_root=merkle_root,
            version_hash=version_hash,
            previous_version_hash=previous_version_hash,
            transaction_hash=transaction_hash,
        )
        if item:
            saved.append(item)

    return saved


def get_recovery_block_unit(
    did: str,
    version: int,
    method: str,
    block_type: str,
    block_index: int,
) -> dict | None:
    collection = _collection()

    return collection.find_one(
        {
            "did": did,
            "version": int(version),
            "method": method,
            "block_type": block_type,
            "block_index": int(block_index),
        },
        {"_id": 0},
    )


def list_recovery_block_units(
    did: str,
    version: int,
    method: str | None = None,
) -> list[dict]:
    """
    查询某个 DID 版本下的恢复块单元。

    method 为空时返回该版本所有恢复块。
    """
    collection = _collection()

    query: dict[str, Any] = {
        "did": did,
        "version": int(version),
    }

    if method:
        query["method"] = method

    return list(
        collection.find(
            query,
            {"_id": 0},
            sort=[("method", 1), ("block_type", 1), ("block_index", 1)],
        )
    )


def list_recovery_blocks(
    did: str | None = None,
    method: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    给 Streamlit 使用的恢复块列表查询。
    """
    collection = _collection()

    query: dict[str, Any] = {}

    if did:
        query["did"] = did

    if method:
        query["method"] = method

    return list(
        collection.find(
            query,
            {"_id": 0},
            sort=[("updated_at", -1)],
            limit=int(limit),
        )
    )


def get_latest_recovery_version(did: str) -> int | None:
    """
    获取 DID 最新恢复块版本。
    """
    collection = _collection()

    item = collection.find_one(
        {"did": did},
        {"_id": 0, "version": 1},
        sort=[("version", -1), ("updated_at", -1)],
    )

    if not item:
        return None

    return int(item["version"])


def delete_recovery_block_unit(
    did: str,
    version: int,
    method: str,
    block_type: str,
    block_index: int,
) -> int:
    """
    删除一个恢复块单元，主要用于实验。
    """
    collection = _collection()

    return collection.delete_one(
        {
            "did": did,
            "version": int(version),
            "method": method,
            "block_type": block_type,
            "block_index": int(block_index),
        }
    ).deleted_count


def delete_recovery_blocks_by_method(
    did: str,
    version: int,
    method: str,
) -> int:
    """
    删除某个 DID 版本下某一种恢复方式的所有块。
    """
    collection = _collection()

    return collection.delete_many(
        {
            "did": did,
            "version": int(version),
            "method": method,
        }
    ).deleted_count