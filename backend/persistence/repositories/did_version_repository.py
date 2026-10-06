"""
DID 历史版本仓储模块

本模块负责 `did_versions` 集合的持久化操作，用于存储 DID 文档的每次更新快照，
支持版本追溯、回滚检测及一致性审计。每条记录对应一个历史版本，通过 `did` 和 `version` 唯一标识。
"""

from datetime import datetime

from infrastructure.mongo.mongo_client import get_database


COLLECTION_NAME = "did_versions"


def insert_version_record(record: dict) -> dict:
    """
    插入一条 DID 文档历史版本记录

    自动设置 `created_at`（若未提供）和 `updated_at` 为当前时间，
    保存成功后返回去除 `_id` 字段的文档副本。

    Args:
        record: 待插入的历史版本记录字典，应包含 `did`、`version` 等字段

    Returns:
        dict: 插入后的记录（不含 _id）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]

    data = dict(record)
    now = datetime.utcnow()
    data.setdefault("created_at", now)
    data["updated_at"] = now

    collection.insert_one(data)
    data.pop("_id", None)
    return data


def get_latest_version_record(did: str) -> dict | None:
    """
    获取指定 DID 的最新历史版本记录

    按版本号降序排列，返回版本号最大的一条记录。

    Args:
        did: DID 标识符

    Returns:
        dict 或 None: 最新版本记录（不含 _id），若不存在则返回 None
    """
    db = get_database()
    collection = db[COLLECTION_NAME]
    return collection.find_one(
        {"did": did},
        {"_id": 0},
        sort=[("version", -1)],
    )


def get_version_record(did: str, version: int) -> dict | None:
    """
    获取指定 DID 的某个特定版本记录

    Args:
        did: DID 标识符
        version: 版本号

    Returns:
        dict 或 None: 对应版本的记录（不含 _id），若不存在则返回 None
    """
    db = get_database()
    collection = db[COLLECTION_NAME]
    return collection.find_one(
        {"did": did, "version": int(version)},
        {"_id": 0},
    )


def list_version_history(did: str, limit: int = 20, ascending: bool = False) -> list[dict]:
    """
    获取指定 DID 的版本历史列表

    可按版本号升序或降序返回最近若干条版本记录，用于审计或展示变更轨迹。

    Args:
        did: DID 标识符
        limit: 返回记录的最大数量，默认 20
        ascending: 是否按版本号升序排列，默认为降序（False）

    Returns:
        list[dict]: 版本记录字典列表（不含 _id）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]
    sort_order = 1 if ascending else -1

    cursor = collection.find(
        {"did": did},
        {"_id": 0},
        sort=[("version", sort_order)],
        limit=limit,
    )
    return list(cursor)