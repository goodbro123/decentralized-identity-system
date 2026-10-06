"""
系统全链路 HTTP 集成测试脚本（可见性验证版）

本脚本通过直接调用 Flask 后端提供的 REST API，完成以下流程的全自动回归验证：
1. 健康检查
2. DID 注册 / 创建（兼容 /api/did/register 与 /api/did/upsert）
3. DID 更新 / 升级（兼容 /api/did/update 与 /api/did/upsert）
4. 查询最新状态（/api/did/latest）
5. 完整性验证（/api/did/verify，选配）
6. 属性默克尔证明（/api/did/proof，选配）
7. 数据恢复测试（/api/did/recover，选配）

所有请求均使用 urllib，依赖项仅标准库。测试通过后将关键结果写入 JSON 文件，
并打印可在 MongoDB 中查询的 DID 与标记，方便人工核验数据。

可通过环境变量控制：
- BASE_URL：后端地址（默认 http://localhost:5000）
- ENABLE_VERIFY / ENABLE_PROOF / ENABLE_RECOVER：是否启用对应测试（1/0）
- TEST_OUTPUT_FILE：结果输出文件路径
- TEST_TIMEOUT_SECONDS：HTTP 超时时间
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000').rstrip('/')
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = Path(os.getenv('TEST_OUTPUT_FILE', str(SCRIPT_DIR / 'last_test_run.json')))
ENABLE_VERIFY = os.getenv('ENABLE_VERIFY', '1') == '1'
ENABLE_PROOF = os.getenv('ENABLE_PROOF', '1') == '1'
ENABLE_RECOVER = os.getenv('ENABLE_RECOVER', '0') == '1'
TIMEOUT = int(os.getenv('TEST_TIMEOUT_SECONDS', '20'))


def _request(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any] | str]:
    """
    发送 HTTP 请求并返回状态码及解析后的响应体。

    对 JSON 响应会自动解析；若非 JSON 则保留原始字符串。
    若连接失败则抛出 RuntimeError，提示无法到达后端。

    Args:
        method: HTTP 方法（GET/POST 等）
        path: 接口路径（如 /api/did/register）
        body: 可选的 JSON 请求体字典

    Returns:
        tuple: (HTTP 状态码, dict 或 str 类型的响应数据)
    """
    url = f"{BASE_URL}{path}"
    data = None
    headers = {}

    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib.request.Request(url=url, method=method.upper(), data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode('utf-8')
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload
    except urllib.error.URLError as exc:
        raise RuntimeError(f"无法连接到后端服务：{url}，错误详情：{exc}") from exc


def _must_success(status: int, payload: dict[str, Any] | str, action: str) -> dict[str, Any]:
    """
    强制要求请求成功，否则抛出 RuntimeError。

    Args:
        status: HTTP 状态码
        payload: 响应体（字典或字符串）
        action: 当前操作名称，用于错误消息标识

    Returns:
        dict: 成功情况下的响应数据字典
    """
    if status >= 400:
        raise RuntimeError(f"操作“{action}”失败，HTTP 状态码={status}，响应内容={payload}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"操作“{action}”返回了非 JSON 数据：{payload}")
    if payload.get('success') is False:
        raise RuntimeError(f"操作“{action}”返回 success=false：{payload}")
    return payload


def _optional_json(status: int, payload: dict[str, Any] | str, action: str) -> dict[str, Any] | None:
    """
    尝试获取成功的 JSON 响应，若失败则打印警告但不中断测试。

    Args:
        status: HTTP 状态码
        payload: 响应体（字典或字符串）
        action: 操作名称

    Returns:
        dict 或 None: 成功时返回解析后的字典，否则返回 None
    """
    if status in (404, 405):
        print(f"[跳过] {action}：接口不可用（HTTP 状态码={status}）")
        return None
    if status >= 400:
        print(f"[警告] {action}：HTTP 状态码={status}，响应内容={payload}")
        return None
    if not isinstance(payload, dict):
        print(f"[警告] {action}：返回非 JSON 数据：{payload}")
        return None
    if payload.get('success') is False:
        print(f"[警告] {action}：success=false，响应内容={payload}")
        return None
    return payload


def _extract_data(payload: dict[str, Any]) -> dict[str, Any]:
    """从标准响应中提取 data 字段，若无则返回原始 payload。"""
    data = payload.get('data')
    return data if isinstance(data, dict) else payload


def _build_v1_document(did: str, marker: str) -> dict[str, Any]:
    """构造用于版本 1 注册的 DID 文档（模拟初始用户数据）。"""
    return {
        'id': did,
        'name': 'Mongo Visible Test User V1',
        'publicKey': 'pk-visible-test-v1',
        'profile': {
            'organization': 'NJIT',
            'email': 'visible-test-v1@example.com',
            'test_marker': marker,
        },
        'meta': {
            'created_by': 'tests/test_http_flow_visible.py',
            'test_case': 'api_flow_and_mongo_visibility',
            'note': 'open MongoDB and search this did or marker',
        },
    }


def _build_v2_document(did: str, marker: str) -> dict[str, Any]:
    """构造用于版本 2 更新的 DID 文档（模拟属性变更）。"""
    return {
        'id': did,
        'name': 'Mongo Visible Test User V2',
        'publicKey': 'pk-visible-test-v2',
        'profile': {
            'organization': 'Nanjing Institute of Technology',
            'email': 'visible-test-v2@example.com',
            'test_marker': marker,
        },
        'attributes': {
            'role': 'student',
            'status': 'updated',
        },
        'meta': {
            'created_by': 'tests/test_http_flow_visible.py',
            'test_case': 'api_flow_and_mongo_visibility',
            'note': 'this is version 2 for Mongo verification',
        },
    }


def _upsert_or_register(did: str, version: int, document: dict[str, Any]) -> dict[str, Any]:
    """
    注册或创建 DID（兼容 /register 和 /upsert 接口）。

    优先尝试 /api/did/register，若接口 404/405 则回退到 /api/did/upsert。
    """
    register_status, register_payload = _request('POST', '/api/did/register', {'did': did, 'document': document})
    if register_status not in (404, 405):
        return _must_success(register_status, register_payload, 'register')

    upsert_status, upsert_payload = _request('POST', '/api/did/upsert', {
        'did': did,
        'version': version,
        'document': document,
    })
    return _must_success(upsert_status, upsert_payload, 'upsert(v1)')


def _update_or_upsert(did: str, version: int, document: dict[str, Any]) -> dict[str, Any]:
    """
    更新 DID（兼容 /update 和 /upsert 接口）。

    优先尝试 /api/did/update，若接口不可用则回退到 /api/did/upsert。
    """
    update_status, update_payload = _request('POST', '/api/did/update', {
        'did': did,
        'version': version,
        'document': document,
    })
    if update_status not in (404, 405):
        return _must_success(update_status, update_payload, 'update')

    upsert_status, upsert_payload = _request('POST', '/api/did/upsert', {
        'did': did,
        'version': version,
        'document': document,
    })
    return _must_success(upsert_status, upsert_payload, 'upsert(v2)')


def run() -> int:
    """
    测试主流程：依次执行健康检查、注册、更新、查询、验证、证明、恢复，
    并将关键数据写入输出文件。返回 0 表示全部通过。
    """
    run_id = str(int(time.time()))
    did = f'did:ethr:visible-test:{run_id}'
    marker = f'MONGO_VISIBLE_{run_id}'

    print(f'[信息] 后端地址={BASE_URL}')
    print(f'[信息] 测试 DID={did}')
    print(f'[信息] MongoDB 标识={marker}')

    health_status, health_payload = _request('GET', '/health')
    _must_success(health_status, health_payload, 'health')
    print('[通过] 健康检查')

    doc_v1 = _build_v1_document(did, marker)
    create_payload = _upsert_or_register(did, 1, doc_v1)
    create_data = _extract_data(create_payload)
    print('[通过] 创建/注册/upsert 版本 1')

    doc_v2 = _build_v2_document(did, marker)
    update_payload = _update_or_upsert(did, 2, doc_v2)
    update_data = _extract_data(update_payload)
    print('[通过] 更新/upsert 版本 2')

    latest_status, latest_payload = _request('GET', '/api/did/latest?' + urllib.parse.urlencode({'did': did}))
    latest_payload = _must_success(latest_status, latest_payload, 'latest')
    latest_data = _extract_data(latest_payload)
    print('[通过] 查询最新状态')

    verify_data = None
    if ENABLE_VERIFY:
        verify_status, verify_payload = _request('POST', '/api/did/verify', {'did': did})
        verify_payload = _optional_json(verify_status, verify_payload, 'verify')
        verify_data = _extract_data(verify_payload) if verify_payload else None
        if verify_payload:
            print('[通过] 完整性验证')

    proof_data = None
    if ENABLE_PROOF:
        proof_status, proof_payload = _request('POST', '/api/did/proof', {
            'did': did,
            'attribute_path': 'profile.organization',
        })
        proof_payload = _optional_json(proof_status, proof_payload, 'proof')
        proof_data = _extract_data(proof_payload) if proof_payload else None
        if proof_payload:
            print('[通过] 属性证明生成')

    recover_data = None
    if ENABLE_RECOVER:
        recover_status, recover_payload = _request('POST', '/api/did/recover', {'did': did})
        recover_payload = _optional_json(recover_status, recover_payload, 'recover')
        recover_data = _extract_data(recover_payload) if recover_payload else None
        if recover_payload:
            print('[通过] 数据恢复')

    result = {
        'base_url': BASE_URL,
        'did': did,
        'marker': marker,
        'collections_hint': [
            'did_documents',
            'did_versions',
            'verification_records',
            'did_recovery_blocks',
            'experiment_records',
        ],
        'create_data': create_data,
        'update_data': update_data,
        'latest_data': latest_data,
        'verify_data': verify_data,
        'proof_data': proof_data,
        'recover_data': recover_data,
        'documents': {
            'v1': doc_v1,
            'v2': doc_v2,
        },
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'[完成] 测试结果已保存至 {OUTPUT_FILE}')
    print('[下一步] 在 MongoDB 中按上述 DID 或 MARKER 查询数据')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(run())
    except Exception as exc:
        print(f'[失败] {exc}', file=sys.stderr)
        raise SystemExit(1)