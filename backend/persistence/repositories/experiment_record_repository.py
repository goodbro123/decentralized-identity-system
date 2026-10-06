"""
实验记录仓储模块

本模块负责 `experiment_records` 集合的持久化操作，用于记录各业务操作的性能实验数据，
包括操作场景、DID、版本、耗时、Gas 消耗等，为后续系统性能测试和论文实验分析提供数据支撑。
"""

from datetime import datetime

from infrastructure.mongo.mongo_client import get_database


COLLECTION_NAME = "experiment_records"


def save_experiment_record(record: dict) -> dict:
    """
    保存一条实验记录

    若记录中未包含 `created_at` 字段，则自动设置为当前 UTC 时间。
    保存成功后返回不含 MongoDB 内部 `_id` 的文档副本。

    Args:
        record: 待保存的实验记录字典，应至少包含 `scene` 字段

    Returns:
        dict: 保存成功后的记录（不含 _id）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    data = dict(record)
    data.setdefault("created_at", datetime.utcnow())

    collection.insert_one(data)
    data.pop("_id", None)
    return data


def list_experiment_records(scene: str | None = None, limit: int = 50) -> list[dict]:
    """
    查询实验记录列表

    可按操作场景过滤，按创建时间降序返回最近的若干条记录。

    Args:
        scene: 操作场景标识，如 "register"、"update"，若为 None 则返回所有场景的记录
        limit: 最大返回记录数，默认 50

    Returns:
        list[dict]: 实验记录字典列表（不含 _id）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    query = {"scene": scene} if scene else {}
    cursor = collection.find(
        query,
        {"_id": 0},
        sort=[("created_at", -1)],
        limit=limit,
    )
    return list(cursor)