"""
DID 应用服务模块

本模块作为业务用例的编排层，负责协调领域规则、持久化仓储、区块链交互、数据恢复及实验记录，
对外提供统一的 DID 注册、更新、查询、验证、属性证明及恢复服务。
所有接口均返回结构化的字典数据，供上层 API 路由直接使用。
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from domain.models.did_document import DidDocument
from domain.rules.hash_rules import (
    compute_changed_attributes,
    compute_document_state,
)
from domain.rules.version_rules import (
    ensure_document_changed,
    ensure_initial_or_incremental_version,
)
from infrastructure.blockchain.did_state_contract import (
    get_latest_state,
    get_transaction_status,
    update_state,
)
from infrastructure.blockchain.web3_provider import get_web3
from infrastructure.crypto.hash_service import ZERO_HASH, did_to_key, is_same_hash
from infrastructure.storage.attribute_merkle import AttributeMerkleTree
from infrastructure.storage.recovery_codec import (
    RecoveryCodecError,
    build_recovery_block_units,
    recover_document_from_block_units,
    summarize_recovery_units,
)
from persistence.repositories.did_document_repository import (
    get_current_document,
    save_current_document,
)
from persistence.repositories.did_version_repository import (
    get_latest_version_record,
    get_version_record,
    insert_version_record,
    list_version_history,
)
from persistence.repositories.experiment_record_repository import save_experiment_record
from persistence.repositories.recovery_block_repository import (
    get_latest_recovery_version,
    list_recovery_block_units,
    save_recovery_block_units,
)
from persistence.repositories.verification_record_repository import (
    save_verification_record,
)
from shared.exceptions import (
    NotFoundError,
    RecoveryError,
    ValidationError,
    VerificationError,
)


def _sender_account() -> str:
    """
    获取当前以太坊网络的默认发送账户地址

    从 Ganache 本地测试网络中获取 accounts[0]，用于为所有链上交易提供签名账户。

    Returns:
        str: 以太坊地址字符串（含校验和）
    """
    w3 = get_web3()
    return w3.eth.accounts[0]


def _record_experiment(
    scene: str,
    did: str,
    version: int | None,
    started_at: float,
    success: bool,
    extra: dict | None = None,
) -> None:
    """
    记录一次业务操作的实验数据

    用于性能测试和实验分析，记录操作场景、DID、版本、耗时及成败状态。
    若记录失败则静默忽略，不对主业务流程产生影响。

    Args:
        scene: 操作场景标识，如 "register"、"update"、"verify"
        did: 操作的 DID 标识
        version: 涉及的版本号（可选）
        started_at: 操作开始时刻（time.perf_counter()）
        success: 是否成功
        extra: 附加字段，如 gas 消耗、变更属性数量等
    """
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)
    payload = {
        "scene": scene,
        "did": did,
        "version": version,
        "success": success,
        "latency_ms": elapsed_ms,
        "created_at": datetime.utcnow(),
    }
    if extra:
        payload.update(extra)

    try:
        save_experiment_record(payload)
    except Exception:
        pass


def _save_recovery_blocks_for_version(
    did: str,
    version: int,
    document: dict[str, Any],
    document_hash: str,
    merkle_root: str,
    version_hash: str,
    previous_version_hash: str,
    transaction_hash: str | None,
) -> dict:
    """
    为 DID 某个版本生成并保存恢复块单元。

    最终会保存：
    - 3 条 duplication replica
    - 4 条 erasure_code data_shard
    - 1 条 erasure_code parity_shard
    """
    block_units = build_recovery_block_units(document)

    save_recovery_block_units(
        did=did,
        version=version,
        block_units=block_units,
        document_hash=document_hash,
        merkle_root=merkle_root,
        version_hash=version_hash,
        previous_version_hash=previous_version_hash,
        transaction_hash=transaction_hash,
    )

    return summarize_recovery_units(block_units)


def _ensure_local_current_matches_chain(
    did: str, current_doc: dict, chain_state: dict
) -> None:
    """
    校验本地当前文档与链上最新状态的一致性

    检查链下文档是否存在、链上是否已锚定、版本号及版本哈希是否一致。
    若不一致则抛出 VerificationError，阻止后续更新操作。

    Args:
        did: DID 标识
        current_doc: 本地当前文档字典
        chain_state: 链上状态字典

    Raises:
        NotFoundError: 本地文档不存在
        VerificationError: 链上未锚定或数据不一致
    """
    if current_doc is None:
        raise NotFoundError(f"链下当前文档不存在：did={did}")

    if not chain_state.get("exists"):
        raise VerificationError(f"该 DID 尚未链上锚定：did={did}")

    if int(current_doc["version"]) != int(chain_state["version"]):
        raise VerificationError("本地当前版本与链上最新版本不一致")

    if not is_same_hash(current_doc["version_hash"], chain_state["version_hash"]):
        raise VerificationError("本地当前版本哈希与链上最新版本哈希不一致")


def _validate_history_continuity(did: str) -> dict:
    """
    校验 DID 版本历史的连续性

    从数据库获取所有历史版本（按版本号升序），逐一重算各项哈希值，
    检测是否存在版本断层或哈希不匹配。

    Args:
        did: DID 标识

    Returns:
        dict: 包含 is_valid（是否连续）和 errors（错误消息列表）的字典
    """
    history = list_version_history(did, limit=1000, ascending=True)
    if not history:
        return {"is_valid": False, "errors": ["版本历史为空"]}

    errors = []
    previous_version_hash = ZERO_HASH

    for index, item in enumerate(history, start=1):
        expected_version = index
        if int(item["version"]) != expected_version:
            errors.append(
                f"版本断层：预期版本号={expected_version}，实际={item['version']}"
            )

        recomputed = compute_document_state(
            did=did,
            version=int(item["version"]),
            document=item["document"],
            previous_version_hash=previous_version_hash,
        )

        if not is_same_hash(item["document_hash"], recomputed.document_hash):
            errors.append(f"文档哈希不匹配：版本={item['version']}")
        if not is_same_hash(item["merkle_root"], recomputed.merkle_root):
            errors.append(f"默克尔根不匹配：版本={item['version']}")
        if not is_same_hash(item["version_hash"], recomputed.version_hash):
            errors.append(f"版本哈希链值不匹配：版本={item['version']}")

        previous_version_hash = recomputed.version_hash

    return {"is_valid": len(errors) == 0, "errors": errors}


def register_did_service(did: str, document: dict[str, Any]) -> dict:
    """
    注册一个新的 DID。

    执行首次 DID 注册流程：
    1. 校验 DID 不存在。
    2. 计算 document_hash、merkle_root、version_hash。
    3. 写入链上状态。
    4. 保存 did_documents 当前文档。
    5. 保存 did_versions 历史版本。
    6. 生成并保存 did_recovery_blocks。
    """
    started_at = time.perf_counter()
    version = 1

    chain_state = get_latest_state(did_to_key(did))
    current_doc = get_current_document(did)

    if chain_state.get("exists") or current_doc is not None:
        raise ValidationError(f"该 DID 已经存在，无法重复注册：did={did}")

    computed = compute_document_state(
        did=did,
        version=version,
        document=document,
        previous_version_hash=ZERO_HASH,
    )

    chain_result = update_state(
        sender=_sender_account(),
        did_key=did_to_key(did),
        version=version,
        document_hash=computed.document_hash,
        merkle_root=computed.merkle_root,
        version_hash=computed.version_hash,
    )

    record = DidDocument(
        did=did,
        version=version,
        document=document,
        document_hash=computed.document_hash,
        merkle_root=computed.merkle_root,
        version_hash=computed.version_hash,
        previous_version_hash=ZERO_HASH,
        transaction_hash=chain_result["tx_hash"],
        status="active",
        changed_attributes=[],
    ).to_dict()

    save_current_document(record)
    insert_version_record(record)

    recovery_blocks_summary = _save_recovery_blocks_for_version(
        did=did,
        version=version,
        document=document,
        document_hash=computed.document_hash,
        merkle_root=computed.merkle_root,
        version_hash=computed.version_hash,
        previous_version_hash=ZERO_HASH,
        transaction_hash=chain_result["tx_hash"],
    )


    _record_experiment(
        scene="register",
        did=did,
        version=version,
        started_at=started_at,
        success=True,
        extra={
            "gas_used": chain_result["gas_used"],
            "duplication_block_count": recovery_blocks_summary["duplication"]["block_count"],
            "erasure_code_block_count": recovery_blocks_summary["erasure_code"]["block_count"],
            "duplication_storage_size_bytes": recovery_blocks_summary["duplication"]["storage_size_bytes"],
            "erasure_code_storage_size_bytes": recovery_blocks_summary["erasure_code"]["storage_size_bytes"],
        },
    )

    return {
        "did": did,
        "version": version,
        "document_hash": computed.document_hash,
        "merkle_root": computed.merkle_root,
        "version_hash": computed.version_hash,
        "recovery_blocks": recovery_blocks_summary,
        "chain_result": chain_result,
    }


def update_did_service(
    did: str, document: dict[str, Any], version: int | None = None
) -> dict:
    """
    更新一个已存在的 DID 文档。

    更新流程：
    1. 校验 DID 已注册。
    2. 校验本地当前文档与链上状态一致。
    3. 校验版本号严格递增。
    4. 计算变更属性。
    5. 计算新版本 document_hash、merkle_root、version_hash。
    6. 写入链上状态。
    7. 保存 did_documents 和 did_versions。
    8. 生成并保存 did_recovery_blocks。
    """
    started_at = time.perf_counter()

    current_doc = get_current_document(did)
    if current_doc is None:
        raise NotFoundError(f"该 DID 尚未注册，请先注册：did={did}")

    chain_state = get_latest_state(did_to_key(did))
    _ensure_local_current_matches_chain(did, current_doc, chain_state)

    new_version = (
        int(version) if version is not None else int(current_doc["version"]) + 1
    )
    ensure_initial_or_incremental_version(
        int(current_doc["version"]), new_version
    )

    changed_attributes = compute_changed_attributes(current_doc["document"], document)
    ensure_document_changed(changed_attributes)

    previous_version_hash = current_doc["version_hash"]

    computed = compute_document_state(
        did=did,
        version=new_version,
        document=document,
        previous_version_hash=previous_version_hash,
    )

    chain_result = update_state(
        sender=_sender_account(),
        did_key=did_to_key(did),
        version=new_version,
        document_hash=computed.document_hash,
        merkle_root=computed.merkle_root,
        version_hash=computed.version_hash,
    )

    record = DidDocument(
        did=did,
        version=new_version,
        document=document,
        document_hash=computed.document_hash,
        merkle_root=computed.merkle_root,
        version_hash=computed.version_hash,
        previous_version_hash=previous_version_hash,
        transaction_hash=chain_result["tx_hash"],
        status="active",
        changed_attributes=changed_attributes,
    ).to_dict()

    save_current_document(record)
    insert_version_record(record)

    recovery_blocks_summary = _save_recovery_blocks_for_version(
    did=did,
    version=new_version,
    document=document,
    document_hash=computed.document_hash,
    merkle_root=computed.merkle_root,
    version_hash=computed.version_hash,
    previous_version_hash=previous_version_hash,
    transaction_hash=chain_result["tx_hash"],
    )

    _record_experiment(
        scene="update",
        did=did,
        version=new_version,
        started_at=started_at,
        success=True,
        extra={
            "gas_used": chain_result["gas_used"],
            "changed_attribute_count": len(changed_attributes),
            "duplication_block_count": recovery_blocks_summary["duplication"]["block_count"],
            "erasure_code_block_count": recovery_blocks_summary["erasure_code"]["block_count"],
            "duplication_storage_size_bytes": recovery_blocks_summary["duplication"]["storage_size_bytes"],
            "erasure_code_storage_size_bytes": recovery_blocks_summary["erasure_code"]["storage_size_bytes"],
        },
    )

    return {
        "did": did,
        "version": new_version,
        "document_hash": computed.document_hash,
        "merkle_root": computed.merkle_root,
        "version_hash": computed.version_hash,
        "changed_attributes": changed_attributes,
        "recovery_blocks": recovery_blocks_summary,
        "chain_result": chain_result,
    }


def create_or_update_did_service(
    did: str, version: int, document: dict[str, Any]
) -> dict:
    """
    统一入口：创建或更新 DID 文档

    根据 DID 是否已存在，自动路由到注册或更新服务。

    Args:
        did: DID 标识
        version: 请求的版本号
        document: DID 文档内容

    Returns:
        dict: 注册或更新操作的返回结果
    """
    current_doc = get_current_document(did)
    if current_doc is None:
        ensure_initial_or_incremental_version(None, version)
        return register_did_service(did=did, document=document)

    return update_did_service(did=did, document=document, version=version)


def get_did_latest_service(did: str) -> dict:
    """
    查询 DID 的最新状态（链上 + 链下）

    返回链上锚点信息、当前文档内容以及最新历史版本记录。

    Args:
        did: DID 标识

    Returns:
        dict: 包含 chain_state、current_document、latest_version_record 的字典
    """
    chain_state = get_latest_state(did_to_key(did))
    current_doc = get_current_document(did)
    latest_version = get_latest_version_record(did)

    return {
        "did": did,
        "chain_state": chain_state,
        "current_document": current_doc,
        "latest_version_record": latest_version,
    }


def build_attribute_proof_service(
    did: str, attribute_path: str, version: int | None = None
) -> dict:
    """
    为指定属性路径生成默克尔证明

    可用于向验证方选择性披露某一属性的真实性和包含关系。

    Args:
        did: DID 标识
        attribute_path: 属性路径（如 "name" 或 "credentialSubject.email"）
        version: 指定版本号（可选，默认使用当前最新版本）

    Returns:
        dict: 包含 did、版本、属性路径和默克尔证明路径的字典

    Raises:
        NotFoundError: 指定版本或文档不存在
        ValidationError: 属性路径无效
    """
    target = (
        get_version_record(did, int(version))
        if version is not None
        else get_current_document(did)
    )
    if target is None:
        raise NotFoundError(f"未找到目标版本：did={did}")

    tree = AttributeMerkleTree.from_document(target["document"])
    try:
        proof = tree.build_proof(attribute_path)
    except KeyError as exc:
        raise ValidationError(str(exc)) from exc

    result = {
        "did": did,
        "version": int(target["version"]),
        "attribute_path": attribute_path,
        "proof": proof,
    }

    save_verification_record(
        {
            "did": did,
            "version": int(target["version"]),
            "verify_type": "attribute_proof",
            "attribute_path": attribute_path,
            "result": result,
            "created_at": datetime.utcnow(),
        }
    )
    return result


def verify_did_service(did: str, version: int | None = None) -> dict:
    """
    对 DID 文档进行完整性验证

    验证目标版本和最新版本的文档哈希、默克尔根、版本哈希是否与重新计算一致，
    检查版本历史是否连续，并确认链上交易状态。

    Args:
        did: DID 标识
        version: 待验证的版本号（可选，默认验证当前版本）

    Returns:
        dict: 包含各项匹配结果及整体 is_valid 字段的验证报告

    Raises:
        NotFoundError: DID 未在链上注册或文档缺失
    """
    started_at = time.perf_counter()

    chain_state = get_latest_state(did_to_key(did))
    if not chain_state.get("exists"):
        raise NotFoundError(f"该 DID 未在链上注册：did={did}")

    target = (
        get_version_record(did, int(version))
        if version is not None
        else (get_current_document(did) or get_latest_version_record(did))
    )
    if target is None:
        raise NotFoundError(f"未找到链下目标文档：did={did}")

    recomputed_target = compute_document_state(
        did=did,
        version=int(target["version"]),
        document=target["document"],
        previous_version_hash=target.get("previous_version_hash", ZERO_HASH),
    )

    target_document_hash_match = is_same_hash(
        target["document_hash"], recomputed_target.document_hash
    )
    target_merkle_root_match = is_same_hash(
        target["merkle_root"], recomputed_target.merkle_root
    )
    target_version_hash_match = is_same_hash(
        target["version_hash"], recomputed_target.version_hash
    )

    latest_record = get_latest_version_record(did)
    if latest_record is None:
        raise NotFoundError(f"未找到最新历史版本记录：did={did}")

    recomputed_latest = compute_document_state(
        did=did,
        version=int(latest_record["version"]),
        document=latest_record["document"],
        previous_version_hash=latest_record.get("previous_version_hash", ZERO_HASH),
    )

    latest_chain_match = (
        int(latest_record["version"]) == int(chain_state["version"])
        and is_same_hash(recomputed_latest.document_hash, chain_state["document_hash"])
        and is_same_hash(recomputed_latest.merkle_root, chain_state["merkle_root"])
        and is_same_hash(recomputed_latest.version_hash, chain_state["version_hash"])
    )

    tx_status = get_transaction_status(latest_record.get("transaction_hash"))
    transaction_verified = tx_status is not None and int(tx_status["status"]) == 1

    history_check = _validate_history_continuity(did)

    result = {
        "did": did,
        "requested_version": int(target["version"]),
        "chain_state": chain_state,
        "recomputed_target": {
            "document_hash": recomputed_target.document_hash,
            "merkle_root": recomputed_target.merkle_root,
            "version_hash": recomputed_target.version_hash,
        },
        "target_document_hash_match": target_document_hash_match,
        "target_merkle_root_match": target_merkle_root_match,
        "target_version_hash_match": target_version_hash_match,
        "latest_chain_match": latest_chain_match,
        "history_chain_valid": history_check["is_valid"],
        "history_errors": history_check["errors"],
        "transaction_verified": transaction_verified,
        "transaction_status": tx_status,
        "is_valid": (
            target_document_hash_match
            and target_merkle_root_match
            and target_version_hash_match
            and latest_chain_match
            and history_check["is_valid"]
            and transaction_verified
        ),
    }

    save_verification_record(
        {
            "did": did,
            "version": int(target["version"]),
            "verify_type": "full_verify",
            "result": result,
            "created_at": datetime.utcnow(),
        }
    )

    _record_experiment(
        scene="verify",
        did=did,
        version=int(target["version"]),
        started_at=started_at,
        success=bool(result["is_valid"]),
        extra={"transaction_verified": transaction_verified},
    )

    return result


def recover_did_service(
    did: str,
    version: int | None = None,
    force_method: str | None = None,
    missing_data_indexes: list[int] | None = None,
) -> dict:
    """
    从恢复块单元中重建 DID 文档。

    恢复策略：
    - auto:
        先尝试 duplication，只要有一个 replica 可用就恢复。
        duplication 失败后尝试 erasure_code。
    - duplication:
        只使用 duplication replica 块。
    - erasure_code:
        只使用 erasure_code data_shard + parity_shard 块。

    新增自修复逻辑：
    - DID 文档恢复成功后，会基于恢复出的 DID 文档重新生成完整恢复块单元。
    - 如果之前删除了 duplication replica 或 erasure_code data_shard，
      只要本次还能恢复出 DID 文档，系统就会自动补回完整 did_recovery_blocks。
    """
    started_at = time.perf_counter()

    requested_recovery_method = force_method or "auto"

    method_order = (
        ["duplication", "erasure_code"]
        if requested_recovery_method == "auto"
        else [requested_recovery_method]
    )

    chain_state = get_latest_state(did_to_key(did))

    target_version = (
        int(version)
        if version is not None
        else (int(chain_state["version"]) if chain_state.get("exists") else None)
    )

    if target_version is None:
        latest_recovery_version = get_latest_recovery_version(did)
        if latest_recovery_version is None:
            raise RecoveryError(f"无法确定恢复版本：did={did}")
        target_version = latest_recovery_version

    errors: list[str] = []

    for method in method_order:
        blocks = list_recovery_block_units(
            did=did,
            version=target_version,
            method=method,
        )

        if not blocks:
            errors.append(f"未找到 {method} 恢复块")
            continue

        try:
            recovered_document, actual_recovery_method = recover_document_from_block_units(
                blocks=blocks,
                method=method,
                missing_data_indexes=missing_data_indexes or [],
            )
        except RecoveryCodecError as exc:
            errors.append(f"{method} 恢复失败：{exc}")
            continue
        except Exception as exc:
            errors.append(f"{method} 恢复过程发生未知错误：{exc}")
            continue

        # 从任意一个块中读取该版本的摘要信息。
        reference_block = blocks[0]

        recomputed = compute_document_state(
            did=did,
            version=int(reference_block["version"]),
            document=recovered_document,
            previous_version_hash=reference_block.get("previous_version_hash", ZERO_HASH),
        )

        local_integrity_ok = (
            is_same_hash(recomputed.document_hash, reference_block["document_hash"])
            and is_same_hash(recomputed.merkle_root, reference_block["merkle_root"])
            and is_same_hash(recomputed.version_hash, reference_block["version_hash"])
        )

        chain_integrity_ok = True

        if chain_state.get("exists") and int(reference_block["version"]) == int(
            chain_state["version"]
        ):
            chain_integrity_ok = (
                is_same_hash(recomputed.document_hash, chain_state["document_hash"])
                and is_same_hash(recomputed.merkle_root, chain_state["merkle_root"])
                and is_same_hash(recomputed.version_hash, chain_state["version_hash"])
            )

        if not local_integrity_ok or not chain_integrity_ok:
            errors.append(
                f"{method} 恢复后的文档未通过完整性校验："
                f"local_integrity_ok={local_integrity_ok}, "
                f"chain_integrity_ok={chain_integrity_ok}"
            )
            continue

        record = DidDocument(
            did=did,
            version=int(reference_block["version"]),
            document=recovered_document,
            document_hash=recomputed.document_hash,
            merkle_root=recomputed.merkle_root,
            version_hash=recomputed.version_hash,
            previous_version_hash=reference_block.get("previous_version_hash", ZERO_HASH),
            transaction_hash=reference_block.get("transaction_hash"),
            status="recovered",
            changed_attributes=[],
        ).to_dict()

        save_current_document(record)

        # 关键新增：
        # 恢复 DID 文档成功后，重新生成并写回完整恢复块单元。
        # 这样如果之前删除了 duplication replica 或 erasure_code data_shard，
        # 只要本次恢复成功，就会自动补回完整的恢复块集合。
        rebuilt_recovery_blocks_summary = _save_recovery_blocks_for_version(
            did=did,
            version=int(reference_block["version"]),
            document=recovered_document,
            document_hash=recomputed.document_hash,
            merkle_root=recomputed.merkle_root,
            version_hash=recomputed.version_hash,
            previous_version_hash=reference_block.get("previous_version_hash", ZERO_HASH),
            transaction_hash=reference_block.get("transaction_hash"),
        )

        auto_verify_result = verify_did_service(
            did=did,
            version=int(reference_block["version"]),
        )

        result = {
            "did": did,
            "version": int(reference_block["version"]),
            "requested_recovery_method": requested_recovery_method,
            "actual_recovery_method": actual_recovery_method,
            "recovery_method": actual_recovery_method,
            "document_hash": recomputed.document_hash,
            "merkle_root": recomputed.merkle_root,
            "version_hash": recomputed.version_hash,
            "local_integrity_ok": local_integrity_ok,
            "chain_integrity_ok": chain_integrity_ok,
            "is_valid": local_integrity_ok and chain_integrity_ok,
            "recovery_blocks_rebuilt": True,
            "rebuilt_recovery_blocks": rebuilt_recovery_blocks_summary,
            "auto_verified": bool(auto_verify_result.get("is_valid")),
            "auto_verify_result": auto_verify_result,
        }

        save_verification_record(
            {
                "did": did,
                "version": int(reference_block["version"]),
                "verify_type": "recover_verify",
                "result": result,
                "created_at": datetime.utcnow(),
            }
        )

        _record_experiment(
            scene="recover",
            did=did,
            version=int(reference_block["version"]),
            started_at=started_at,
            success=bool(result["is_valid"] and result["auto_verified"]),
            extra={
                "requested_recovery_method": requested_recovery_method,
                "actual_recovery_method": actual_recovery_method,
                "auto_verified": bool(result["auto_verified"]),
                "used_block_count": len(blocks),
                "recovery_blocks_rebuilt": True,
                "duplication_block_count": rebuilt_recovery_blocks_summary["duplication"]["block_count"],
                "erasure_code_block_count": rebuilt_recovery_blocks_summary["erasure_code"]["block_count"],
                "duplication_storage_size_bytes": rebuilt_recovery_blocks_summary["duplication"]["storage_size_bytes"],
                "erasure_code_storage_size_bytes": rebuilt_recovery_blocks_summary["erasure_code"]["storage_size_bytes"],
            },
        )

        return result

    _record_experiment(
        scene="recover",
        did=did,
        version=target_version,
        started_at=started_at,
        success=False,
        extra={
            "requested_recovery_method": requested_recovery_method,
            "error": "；".join(errors),
        },
    )

    raise RecoveryError(
        "所有恢复方式均失败："
        + ("；".join(errors) if errors else "未找到可用恢复块")
    )