"""
DID 控制权认证服务模块

本模块负责 DID 操作前的身份认证，通过生成一次性挑战（challenge）并验证用户签名，
确认调用者拥有对应 DID 的控制权。支持的操作为：注册、绑定、更新、恢复。

核心流程：
1. 调用 create_auth_challenge 生成挑战并返回给客户端。
2. 客户端使用 DID 对应的私钥对挑战消息签名，并将签名、nonce、timestamp 等信息
   放入请求的 auth 字段。
3. 后端在执行业务逻辑前调用 verify_did_auth 验证签名、时效性和非重复使用，
   仅通过后才允许后续操作。

注意：
当前 did_recovery_blocks 已经改为“恢复块单元”结构：
- duplication replica 单独存储
- erasure_code data_shard / parity_shard 单独存储

因此恢复操作的控制权认证不能再从 did_recovery_blocks 读取完整 DID 文档。
恢复认证必须依赖 did_versions 中保存的历史 DID 文档。
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime
from typing import Any

from application.services.did_application_service import get_did_latest_service
from infrastructure.crypto.eth_signature_service import (
    is_same_address,
    recover_address_from_signature,
)
from persistence.repositories.auth_challenge_repository import (
    get_auth_challenge,
    mark_auth_challenge_used,
    save_auth_challenge,
)
from persistence.repositories.did_version_repository import get_latest_version_record
from shared.exceptions import AuthError, ValidationError


ALLOWED_OPERATIONS = {"register", "bind", "update", "recover",'proof'}


def create_auth_challenge(did: str, operation: str) -> dict:
    """
    为指定 DID 和操作生成一条身份认证挑战。

    挑战由随机 nonce、时间戳、DID 和操作类型组合而成，有效期默认为 300 秒。
    生成的挑战会存入 MongoDB 等待用户签名后回传验证。

    Args:
        did: 发起操作的 DID 标识符。
        operation: 操作类型，需在 {"register","bind","update","recover"} 内。

    Returns:
        dict: 包含 did, operation, challenge, nonce, timestamp, expires_in 的字典。
    """
    operation = _normalize_operation(operation)

    nonce = secrets.token_hex(16)
    timestamp = int(time.time())
    expires_in = 300

    challenge = build_challenge_message(
        did=did,
        operation=operation,
        nonce=nonce,
        timestamp=timestamp,
    )

    save_auth_challenge(
        did=did,
        operation=operation,
        nonce=nonce,
        challenge=challenge,
        timestamp=timestamp,
        expires_in=expires_in,
    )

    return {
        "did": did,
        "operation": operation,
        "challenge": challenge,
        "nonce": nonce,
        "timestamp": timestamp,
        "expires_in": expires_in,
    }


def verify_did_auth(
    did: str,
    operation: str,
    auth: dict | None,
    document: dict[str, Any] | None = None,
) -> dict:
    """
    验证用户是否拥有指定 DID 的控制权。

    根据操作类型不同，采用不同的方式确定合法的控制器地址，然后通过恢复签名
    地址并与控制器地址比对，同时校验挑战的时效性与一次性，防止重放攻击。

    Args:
        did: 待验证的 DID 标识符。
        operation: 操作类型。
        auth: 客户端提交的认证信息字典，应包含 nonce、timestamp、signature 等字段。
        document: 可选的 DID 文档，在注册等操作中用于提取控制器地址。

    Returns:
        dict: 认证结果，包含 did, operation, recovered_address, controller_address
              以及 authenticated=True。

    Raises:
        AuthError: 认证失败。
        ValidationError: 文档校验失败。
    """
    operation = _normalize_operation(operation)

    if not isinstance(auth, dict):
        raise AuthError("缺少 auth 签名认证信息")

    auth_operation = _normalize_operation(auth.get("operation"))
    nonce = auth.get("nonce")
    timestamp = auth.get("timestamp")
    signature = auth.get("signature")

    if auth_operation != operation:
        raise AuthError("auth.operation 与当前操作不一致")
    if not nonce:
        raise AuthError("缺少 auth.nonce")
    if timestamp is None:
        raise AuthError("缺少 auth.timestamp")
    if not signature:
        raise AuthError("缺少 auth.signature")

    challenge_record = get_auth_challenge(
        did=did,
        operation=operation,
        nonce=nonce,
    )
    if not challenge_record:
        raise AuthError("challenge 不存在或已过期")
    if challenge_record.get("used"):
        raise AuthError("challenge 已被使用，疑似重放请求")

    expires_at = challenge_record.get("expires_at")
    if expires_at and isinstance(expires_at, datetime):
        now = datetime.utcnow()
        if expires_at.tzinfo is not None:
            expires_at = expires_at.replace(tzinfo=None)
        if expires_at < now:
            raise AuthError("challenge 已过期")

    expected_timestamp = int(challenge_record["timestamp"])
    if int(timestamp) != expected_timestamp:
        raise AuthError("auth.timestamp 与 challenge 不一致")

    challenge = challenge_record["challenge"]
    recovered_address = recover_address_from_signature(
        message=challenge,
        signature=signature,
    )

    controller_address = resolve_controller_address_for_operation(
        did=did,
        operation=operation,
        document=document,
    )

    if not is_same_address(recovered_address, controller_address):
        raise AuthError("签名地址与 DID controller 不一致")

    mark_auth_challenge_used(
        did=did,
        operation=operation,
        nonce=nonce,
    )

    return {
        "did": did,
        "operation": operation,
        "recovered_address": recovered_address,
        "controller_address": controller_address,
        "authenticated": True,
    }


def build_challenge_message(did: str, operation: str, nonce: str, timestamp: int) -> str:
    """
    构造待签名的挑战消息字符串。

    消息格式为多行 key=value，确保其具备机器可解析性及用户友好性。

    Args:
        did: DID 标识符。
        operation: 操作类型。
        nonce: 随机数。
        timestamp: Unix 时间戳。

    Returns:
        str: 待签名的原始消息。
    """
    return (
        f"did={did}\n"
        f"operation={operation}\n"
        f"nonce={nonce}\n"
        f"timestamp={int(timestamp)}"
    )


def resolve_controller_address_for_operation(
    did: str,
    operation: str,
    document: dict[str, Any] | None = None,
) -> str:
    """
    根据操作类型解析应具有控制权的 Ethereum 地址。

    - register: 通过请求中的 document 提取 controller 地址。
    - bind/update: 从链下当前文档或最新历史版本中提取 controller 地址。
    - recover: 从 did_versions 历史版本中提取 controller 地址。

    Args:
        did: DID 标识符。
        operation: 操作类型。
        document: 可选的 DID 文档。

    Returns:
        str: 控制器以太坊地址。

    Raises:
        AuthError: 当无法解析或操作不支持时抛出。
    """
    if operation == "register":
        if not isinstance(document, dict):
            raise AuthError("注册时缺少 DID Document")
        _validate_register_document(did, document)
        return extract_controller_address_from_document(document)

    if operation in {"bind", "update","proof"}:
        controller_document = _load_current_or_latest_document(did)

        if operation == "update" and isinstance(document, dict):
            _validate_update_document(
                did=did,
                old_document=controller_document,
                new_document=document,
            )

        return extract_controller_address_from_document(controller_document)

    if operation == "recover":
        controller_document = _load_latest_document_for_recover(did)
        return extract_controller_address_from_document(controller_document)

    raise AuthError(f"不支持的认证操作：{operation}")


def extract_address_from_did(did: str) -> str:
    """
    从 did:ethr:<address> 格式的 DID 中提取以太坊地址。

    Args:
        did: DID 字符串，必须以 "did:ethr:" 开头且跟随有效的 Ethereum 地址。

    Returns:
        str: 十六进制以太坊地址。

    Raises:
        AuthError: 格式不正确时抛出。
    """
    prefix = "did:ethr:"
    if not isinstance(did, str) or not did.startswith(prefix):
        raise AuthError("DID 格式必须为 did:ethr:<address>")

    address = did[len(prefix):]
    if not address.startswith("0x"):
        raise AuthError("did:ethr 后必须是 Ethereum 地址")

    return address


def extract_controller_address_from_document(document: dict[str, Any]) -> str:
    """
    从 DID 文档中提取区块链控制器地址。

    解析 verificationMethod 列表中 authentication 引用的方法，
    并从其 blockchainAccountId 字段获取地址。

    blockchainAccountId 格式：
        eip155:chainId:address

    Args:
        document: DID 文档字典。

    Returns:
        str: 控制器以太坊地址。

    Raises:
        AuthError: 文档结构不完整或格式错误时抛出。
    """
    if not isinstance(document, dict):
        raise AuthError("DID Document 无效")

    verification_methods = document.get("verificationMethod") or []
    authentication = document.get("authentication") or []

    if not verification_methods:
        raise AuthError("DID Document 缺少 verificationMethod")
    if not authentication:
        raise AuthError("DID Document 缺少 authentication")

    auth_method_id = authentication[0]
    target_method = None

    for item in verification_methods:
        if isinstance(item, dict) and item.get("id") == auth_method_id:
            target_method = item
            break

    if target_method is None:
        raise AuthError("authentication 指向的 verificationMethod 不存在")

    blockchain_account_id = target_method.get("blockchainAccountId")
    if not blockchain_account_id:
        raise AuthError("verificationMethod 缺少 blockchainAccountId")

    parts = str(blockchain_account_id).split(":")
    if len(parts) != 3:
        raise AuthError("blockchainAccountId 格式应为 eip155:chainId:address")

    address = parts[2]
    if not address.startswith("0x"):
        raise AuthError("blockchainAccountId 中的 address 必须以 0x 开头")

    return address


def _load_current_or_latest_document(did: str) -> dict[str, Any]:
    """
    获取当前文档或最新历史版本的 DID 文档内容。

    优先级：
    1. did_documents 当前文档
    2. did_versions 最新历史版本

    Args:
        did: DID 标识符。

    Returns:
        dict: DID 文档字典。

    Raises:
        AuthError: 无法获取任何文档时抛出。
    """
    latest = get_did_latest_service(did)
    current_document = latest.get("current_document") or latest.get("currentDocument")

    if current_document and current_document.get("document"):
        return current_document["document"]

    latest_version = get_latest_version_record(did)
    if latest_version and latest_version.get("document"):
        return latest_version["document"]

    raise AuthError("无法找到 DID 当前文档或历史文档，无法验证控制权")


def _load_latest_document_for_recover(did: str) -> dict[str, Any]:
    """
    为恢复操作获取可验证控制权的历史 DID 文档。

    当前恢复块采用“块单元”结构：
    - duplication replica 单独保存
    - erasure_code data_shard / parity_shard 单独保存

    did_recovery_blocks 不再保存完整 DID 文档，因此恢复操作的控制权认证
    必须从 did_versions 中读取历史 DID 文档来解析 controller 地址。

    Args:
        did: DID 标识符。

    Returns:
        dict: DID 文档字典。

    Raises:
        AuthError: 无法获取任何可用于验证的历史文档时抛出。
    """
    latest_version = get_latest_version_record(did)

    if latest_version and latest_version.get("document"):
        return latest_version["document"]

    raise AuthError(
        "无法找到 DID 历史版本文档，无法验证恢复控制权；"
        "请确认 did_versions 未被删除"
    )


def _validate_register_document(did: str, document: dict[str, Any]) -> None:
    """
    校验注册时提交的 DID 文档的合法性。

    检查：
    1. document.id 必须等于 did。
    2. document.controller 必须等于 did。
    3. DID 中提取的地址必须与 document 中控制器地址一致。

    Args:
        did: 注册的 DID 标识符。
        document: 注册时提交的 DID 文档。

    Raises:
        ValidationError: 文档字段不符合预期。
        AuthError: 地址不匹配。
    """
    if document.get("id") != did:
        raise ValidationError("document.id 必须等于 did")

    if document.get("controller") != did:
        raise ValidationError("document.controller 必须等于 did")

    did_address = extract_address_from_did(did)
    controller_address = extract_controller_address_from_document(document)

    if not is_same_address(did_address, controller_address):
        raise AuthError("DID 地址与 document controller 地址不一致")


def _validate_update_document(
    did: str,
    old_document: dict[str, Any],
    new_document: dict[str, Any],
) -> None:
    """
    校验更新时提交的新 DID 文档的合法性。

    检查：
    1. document.id 不允许修改。
    2. document.controller 不允许修改。
    3. controller / verificationMethod 暂不允许更换控制地址。

    Args:
        did: DID 标识符。
        old_document: 文档当前版本。
        new_document: 提交的新版本文档。

    Raises:
        ValidationError: 不允许的字段被修改。
        AuthError: 控制器地址发生变化。
    """
    if new_document.get("id") != did:
        raise ValidationError("document.id 不允许修改")

    if new_document.get("controller") != did:
        raise ValidationError("document.controller 不允许修改")

    old_controller = extract_controller_address_from_document(old_document)
    new_controller = extract_controller_address_from_document(new_document)

    if not is_same_address(old_controller, new_controller):
        raise AuthError("当前版本暂不允许修改 DID controller / verificationMethod")


def _normalize_operation(operation: str | None) -> str:
    """
    清洗并验证操作类型。

    Args:
        operation: 原始操作字符串。

    Returns:
        str: 规范化后的操作类型。

    Raises:
        AuthError: 缺省或不在允许列表中。
    """
    if not operation:
        raise AuthError("缺少 operation")

    operation = str(operation).strip()

    if operation not in ALLOWED_OPERATIONS:
        raise AuthError(f"不支持的 operation：{operation}")

    return operation