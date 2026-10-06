"""
DID 当前文档仓储模块

本模块负责 `did_documents` 集合的持久化操作，提供当前有效 DID 文档的保存、查询与删除功能。
采用 MongoDB 作为底层存储，以 `did` 字段作为唯一标识，确保每条 DID 仅保留最新状态。
"""

from datetime import datetime, timezone

from infrastructure.mongo.mongo_client import get_database


COLLECTION_NAME = "did_documents"


def save_current_document(record: dict):
    """
    保存或更新当前有效的 DID 文档

    采用 upsert 模式：若指定 `did` 的文档已存在则更新，否则插入新文档。
    自动维护 `created_at`（首次创建时间）和 `updated_at`（最后更新时间）。
    成功保存后，返回更新后的完整文档。

    Args:
        record: 待保存的文档数据字典，至少应包含 `did` 字段及其他业务字段

    Returns:
        dict 或 None: 保存后从数据库重新读取的当前文档（不含 _id）
    """
    db = get_database()
    collection = db[COLLECTION_NAME]
    now = datetime.now(timezone.utc)

    existing = collection.find_one({"did": record["did"]}, {"_id": 0, "created_at": 1})
    created_at = existing["created_at"] if existing and "created_at" in existing else now

    data = dict(record)
    data["created_at"] = created_at
    data["updated_at"] = now

    collection.update_one(
        {"did": data["did"]},
        {"$set": data},
        upsert=True,
    )
    return get_current_document(data["did"])


def get_current_document(did: str):
    """
    根据 DID 获取当前有效的文档

    Args:
        did: DID 标识符

    Returns:
        dict 或 None: 若存在则返回文档字典（不含 _id），否则返回 None
    """
    db = get_database()
    collection = db[COLLECTION_NAME]
    return collection.find_one({"did": did}, {"_id": 0})


def delete_current_document(did: str) -> int:
    """
    删除指定 DID 的当前文档（物理删除）

    返回被删除的文档数量，通常为 0 或 1。

    Args:
        did: DID 标识符

    Returns:
        int: 已删除的文档计数
    """
    db = get_database()
    collection = db[COLLECTION_NAME]
    return collection.delete_one({"did": did}).deleted_count