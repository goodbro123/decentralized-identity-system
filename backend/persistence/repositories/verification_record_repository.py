"""
验证记录仓储模块

本模块负责 `verification_records` 集合的持久化操作，用于存储身份验证、
默克尔证明校验、数据恢复等场景下的审计记录。
所有记录均带有时间戳，支持按 DID 查询验证历史。
"""

from datetime import datetime, timezone

from infrastructure.mongo.mongo_client import get_database


COLLECTION_NAME = "verification_records"


def save_verification_record(record: dict) -> dict:
    """
    保存一条验证记录

    若记录中未包含 `created_at` 字段，则自动设置为当前 UTC 时间。
    保存成功后返回不含 `_id` 的文档副本。

    Args:
        record: 待保存的验证记录字典，应至少包含 `did` 字段

    Returns:
        dict: 保存成功后的记录（不含 `_id`）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    data = dict(record)
    data.setdefault("created_at", datetime.now(timezone.utc))

    collection.insert_one(data)
    data.pop("_id", None)
    return data


def list_verification_records(did: str, limit: int = 20) -> list[dict]:
    """
    查询指定 DID 的验证历史记录

    按创建时间降序返回最近的若干条验证记录。

    Args:
        did: DID 标识符
        limit: 返回记录的最大数量，默认 20

    Returns:
        list[dict]: 验证记录字典列表（不含 `_id`）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    cursor = collection.find(
        {"did": did},
        {"_id": 0},
        sort=[("created_at", -1)],
        limit=limit,
    )
    return list(cursor)