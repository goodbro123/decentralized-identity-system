"""
Streamlit 数据服务层

本模块封装了 Flask API 调用与 MongoDB 数据查询逻辑，供可视化平台各页面复用。
提供后端健康检查、DID 全生命周期 API 调用、各集合数据查询及实验统计等函数。
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pymongo import DESCENDING

from services import api_client
from services.mongo_client import get_database


COLLECTIONS = [
    "did_documents",
    "did_versions",
    "verification_records",
    "did_recovery_blocks",
    "experiment_records",
]


def backend_health() -> dict[str, Any]:
    """获取 Flask 后端健康检查结果。"""
    return api_client.health()


def api_latest(did: str) -> dict[str, Any]:
    """通过 API 查询指定 DID 的最新状态。"""
    return api_client.latest_data(did)


def api_register(did: str, document: dict[str, Any]) -> dict[str, Any]:
    """通过 API 注册一个新的 DID。"""
    return api_client.register_data(did, document)


def api_update(did: str, document: dict[str, Any], version: int | None = None) -> dict[str, Any]:
    """通过 API 更新已存在的 DID 文档。"""
    return api_client.update_data(did, document, version)


def api_verify(did: str, version: int | None = None) -> dict[str, Any]:
    """通过 API 对 DID 进行完整性验证。"""
    return api_client.verify_data(did, version)


def api_proof(did: str, attribute_path: str, version: int | None = None) -> dict[str, Any]:
    """通过 API 生成指定属性的默克尔包含证明。"""
    return api_client.proof_data(did, attribute_path, version)


def api_recover(
    did: str,
    version: int | None = None,
    force_method: str | None = None,
    missing_data_indexes: list[int] | None = None,
) -> dict[str, Any]:
    """通过 API 从恢复块重建 DID 文档。"""
    return api_client.recover_data(did, version, force_method, missing_data_indexes)


def collection_counts() -> dict[str, int]:
    """
    统计各业务集合的文档数量。

    Returns:
        dict[str, int]: 键为集合名称，值为文档数量
    """
    db = get_database()
    return {name: db[name].count_documents({}) for name in COLLECTIONS}


def list_current_documents(keyword: str = "", limit: int = 200) -> list[dict[str, Any]]:
    """
    检索当前有效 DID 文档列表，支持按关键字模糊搜索。

    Args:
        keyword: 搜索关键字（匹配 did、姓名、组织）
        limit: 最大返回条数

    Returns:
        list: 符合条件的文档列表（不含 _id）
    """
    db = get_database()
    query: dict[str, Any] = {}
    if keyword:
        query = {
            "$or": [
                {"did": {"$regex": keyword, "$options": "i"}},
                {"document.name": {"$regex": keyword, "$options": "i"}},
                {"document.profile.organization": {"$regex": keyword, "$options": "i"}},
            ]
        }
    cursor = db["did_documents"].find(query, {"_id": 0}).sort("updated_at", DESCENDING).limit(limit)
    return list(cursor)


def get_current_document(did: str) -> dict[str, Any] | None:
    """
    获取指定 DID 的当前有效文档。

    Args:
        did: DID 标识符

    Returns:
        dict 或 None: 文档字典（不含 _id），若不存在则返回 None
    """
    db = get_database()
    return db["did_documents"].find_one({"did": did}, {"_id": 0})


def get_version_history(did: str, limit: int = 100) -> list[dict[str, Any]]:
    """
    获取指定 DID 的历史版本记录，按版本降序。

    Args:
        did: DID 标识符
        limit: 最大返回条数

    Returns:
        list: 历史版本记录列表
    """
    db = get_database()
    cursor = db["did_versions"].find({"did": did}, {"_id": 0}).sort("version", DESCENDING).limit(limit)
    return list(cursor)


def get_verification_records(did: str = "", limit: int = 100) -> list[dict[str, Any]]:
    """
    获取验证记录，可按 DID 过滤。

    Args:
        did: 可选，指定 DID 标识符；为空则返回所有记录
        limit: 最大返回条数

    Returns:
        list: 验证记录列表
    """
    db = get_database()
    query = {"did": did} if did else {}
    cursor = db["verification_records"].find(query, {"_id": 0}).sort("created_at", DESCENDING).limit(limit)
    return list(cursor)


def get_recovery_blocks(did: str = "", limit: int = 100) -> list[dict[str, Any]]:
    """
    获取恢复块数据，可按 DID 过滤。

    Args:
        did: 可选，指定 DID 标识符；为空则返回所有记录
        limit: 最大返回条数

    Returns:
        list: 恢复块列表
    """
    db = get_database()
    query = {"did": did} if did else {}
    cursor = db["did_recovery_blocks"].find(query, {"_id": 0}).sort("version", DESCENDING).limit(limit)
    return list(cursor)


def get_experiment_records(limit: int = 300) -> list[dict[str, Any]]:
    """
    获取性能实验记录，按创建时间降序。

    Args:
        limit: 最大返回条数

    Returns:
        list: 实验记录列表
    """
    db = get_database()
    cursor = db["experiment_records"].find({}, {"_id": 0}).sort("created_at", DESCENDING).limit(limit)
    return list(cursor)


def experiment_summary() -> dict[str, Any]:
    """
    生成实验统计摘要。

    统计各场景的操作次数、平均延迟和平均 Gas 消耗。

    Returns:
        dict: 包含 total 和 scene_summary 的统计字典
    """
    records = get_experiment_records(limit=1000)
    if not records:
        return {"total": 0, "scene_summary": []}

    df = pd.DataFrame(records)
    result: dict[str, Any] = {"total": len(records), "scene_summary": []}

    if "scene" in df.columns:
        grouped = df.groupby("scene", dropna=False)
        for scene, sub in grouped:
            row = {
                "scene": scene,
                "count": int(len(sub)),
            }
            if "latency_ms" in sub.columns:
                row["avg_latency_ms"] = round(float(sub["latency_ms"].dropna().mean()), 3)
            if "gas_used" in sub.columns:
                valid_gas = sub["gas_used"].dropna()
                if not valid_gas.empty:
                    row["avg_gas_used"] = round(float(valid_gas.mean()), 3)
            result["scene_summary"].append(row)
    return result


def latest_verification_record() -> dict[str, Any] | None:
    """获取最新的一条验证记录。"""
    rows = get_verification_records(limit=1)
    return rows[0] if rows else None


def latest_experiment_record() -> dict[str, Any] | None:
    """获取最新的一条实验记录。"""
    rows = get_experiment_records(limit=1)
    return rows[0] if rows else None