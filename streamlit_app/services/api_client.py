"""
Streamlit 可视化平台 API 客户端模块

本模块封装了对 Flask 后端所有业务接口的 HTTP 请求，提供以下功能：
- 统一的请求发送与错误处理
- 健康检查、DID 查询、注册、更新、验证、属性证明、数据恢复等接口的调用
- 自动提取响应中的 `data` 字段

所有函数均可能抛出 `ApiClientError` 异常，调用方需自行捕获处理。
"""

from __future__ import annotations

import os
from typing import Any

import requests


BACKEND_BASE_URL = os.getenv("STREAMLIT_BACKEND_BASE_URL", "http://localhost:5000").rstrip("/")
DEFAULT_TIMEOUT = int(os.getenv("STREAMLIT_BACKEND_TIMEOUT", "20"))


class ApiClientError(RuntimeError):
    """
    API 客户端自定义异常类

    用于包裹所有因网络问题、后端错误或业务失败导致的请求异常。
    上游调用方可根据此异常类型进行统一错误处理。
    """
    pass


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    发送 HTTP 请求并处理响应。

    自动拼接基础 URL，请求超时时间由环境变量控制。
    对于 HTTP 状态码 >= 400 或业务 success 为 False 的响应，
    统一抛出 ApiClientError 异常。

    Args:
        method: HTTP 方法（GET/POST 等）
        path: 接口路径（如 /api/did/register）
        payload: 可选的 JSON 请求体

    Returns:
        dict: 解析后的 JSON 响应体

    Raises:
        ApiClientError: 当网络错误、状态码异常或业务失败时抛出
    """
    url = f"{BACKEND_BASE_URL}{path}"
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ApiClientError(f"请求后端失败：{exc}") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ApiClientError(f"后端返回了非 JSON 数据，HTTP={response.status_code}") from exc

    if response.status_code >= 400:
        raise ApiClientError(f"HTTP={response.status_code}，响应={data}")

    if isinstance(data, dict) and data.get("success") is False:
        raise ApiClientError(str(data))

    return data


def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
    """
    从标准 API 响应字典中提取 `data` 字段。

    若 `data` 不存在或为非字典类型，则返回原始 payload。

    Args:
        payload: API 返回的完整 JSON 字典

    Returns:
        dict: 提取出的业务数据字典
    """
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def health() -> dict[str, Any]:
    """调用健康检查接口，返回完整响应。"""
    return _request("GET", "/health")


def did_latest(did: str) -> dict[str, Any]:
    """查询指定 DID 的最新状态（链上 + 链下）。"""
    return _request("GET", f"/api/did/latest?did={did}")


def did_register(did: str, document: dict[str, Any]) -> dict[str, Any]:
    """注册一个新的 DID。"""
    return _request("POST", "/api/did/register", {"did": did, "document": document})


def did_update(did: str, document: dict[str, Any], version: int | None = None) -> dict[str, Any]:
    """更新已存在的 DID 文档。"""
    payload: dict[str, Any] = {"did": did, "document": document}
    if version is not None:
        payload["version"] = int(version)
    return _request("POST", "/api/did/update", payload)


def did_verify(did: str, version: int | None = None) -> dict[str, Any]:
    """对 DID 文档进行完整性验证。"""
    payload: dict[str, Any] = {"did": did}
    if version is not None:
        payload["version"] = int(version)
    return _request("POST", "/api/did/verify", payload)


def did_proof(did: str, attribute_path: str, version: int | None = None) -> dict[str, Any]:
    """生成指定属性的默克尔包含证明。"""
    payload: dict[str, Any] = {
        "did": did,
        "attribute_path": attribute_path,
    }
    if version is not None:
        payload["version"] = int(version)
    return _request("POST", "/api/did/proof", payload)


def did_recover(
    did: str,
    version: int | None = None,
    force_method: str | None = None,
    missing_data_indexes: list[int] | None = None,
) -> dict[str, Any]:
    """从恢复块重建 DID 文档。"""
    payload: dict[str, Any] = {"did": did}
    if version is not None:
        payload["version"] = int(version)
    if force_method:
        payload["force_method"] = force_method
    if missing_data_indexes is not None:
        payload["missing_data_indexes"] = missing_data_indexes
    return _request("POST", "/api/did/recover", payload)


def health_data() -> dict[str, Any]:
    """获取健康检查响应中的 data 字段。"""
    return _extract_data(health())


def latest_data(did: str) -> dict[str, Any]:
    """获取 DID 最新状态响应中的 data 字段。"""
    return _extract_data(did_latest(did))


def register_data(did: str, document: dict[str, Any]) -> dict[str, Any]:
    """获取注册响应中的 data 字段。"""
    return _extract_data(did_register(did, document))


def update_data(did: str, document: dict[str, Any], version: int | None = None) -> dict[str, Any]:
    """获取更新响应中的 data 字段。"""
    return _extract_data(did_update(did, document, version))


def verify_data(did: str, version: int | None = None) -> dict[str, Any]:
    """获取验证响应中的 data 字段。"""
    return _extract_data(did_verify(did, version))


def proof_data(did: str, attribute_path: str, version: int | None = None) -> dict[str, Any]:
    """获取属性证明响应中的 data 字段。"""
    return _extract_data(did_proof(did, attribute_path, version))


def recover_data(
    did: str,
    version: int | None = None,
    force_method: str | None = None,
    missing_data_indexes: list[int] | None = None,
) -> dict[str, Any]:
    """获取恢复响应中的 data 字段。"""
    return _extract_data(did_recover(did, version, force_method, missing_data_indexes))