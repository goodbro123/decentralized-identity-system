"""
DID 文档哈希与默克尔树计算规则模块

本模块定义与 DID 文档相关的哈希计算规则，包括：
- 文档整体摘要计算（规范化 JSON 后 Keccak-256）
- 属性级默克尔树根计算
- 版本哈希链生成（用于防回滚校验）
- 版本状态统一计算
- 新旧文档差异属性识别

所有函数均返回规范化的十六进制字符串或结构化数据，供上层服务与链上锚点使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.crypto.hash_service import ZERO_HASH, keccak_text
from infrastructure.storage.attribute_merkle import AttributeMerkleTree, flatten_document
from infrastructure.storage.canonical_json import to_canonical_json


@dataclass(frozen=True)
class ComputedDidState:
    """
    计算得到的 DID 版本状态值对象（不可变）

    该对象包含一次 DID 文档更新后需要锚定到链上的所有哈希摘要信息，
    是智能合约 updateState 调用的参数来源。

    Attributes:
        document_hash: 当前文档整体内容的 Keccak-256 摘要
        merkle_root: 基于属性级默克尔树计算的根哈希
        version_hash: 当前版本的哈希链值（用于防回滚）
        previous_version_hash: 前一个版本的哈希链值（首个版本为全零哈希）
    """
    document_hash: str
    merkle_root: str
    version_hash: str
    previous_version_hash: str


def build_document_hash(document: dict[str, Any]) -> str:
    """
    构建 DID 文档的整体内容摘要

    对文档进行规范化 JSON 序列化，然后计算 Keccak-256 哈希，生成固定长度的文档指纹。
    该摘要用于检测文档整体是否被篡改。

    Args:
        document: DID 文档的完整内容字典

    Returns:
        str: 以 "0x" 开头的十六进制哈希字符串
    """
    canonical = to_canonical_json(document)
    return keccak_text(canonical)


def build_merkle_root(document: dict[str, Any]) -> str:
    """
    构建 DID 文档的属性级默克尔树根

    将文档按属性层级展开，构建默克尔树，返回根哈希。
    该根哈希可实现字段级的完整性验证，并支持选择性披露。

    Args:
        document: DID 文档的完整内容字典

    Returns:
        str: 默克尔树的根哈希（十六进制字符串）
    """
    return AttributeMerkleTree.from_document(document).root


def build_version_hash(
    did: str,
    version: int,
    document_hash: str,
    merkle_root: str,
    previous_version_hash: str = ZERO_HASH,
) -> str:
    """
    构建版本哈希链中的当前版本哈希

    将 DID 标识、版本号、文档摘要、默克尔根及前一版本哈希组合后计算哈希，
    形成链式依赖，从而实现版本序列的完整性校验与回滚检测。

    Args:
        did: DID 标识符
        version: 当前版本号
        document_hash: 当前文档整体摘要
        merkle_root: 当前文档的属性级默克尔根
        previous_version_hash: 前一版本的版本哈希，首版本使用全零哈希

    Returns:
        str: 当前版本的版本哈希链值（十六进制字符串）
    """
    material = to_canonical_json(
        {
            'did': did,
            'version': int(version),
            'document_hash': document_hash,
            'merkle_root': merkle_root,
            'previous_version_hash': previous_version_hash,
        }
    )
    return keccak_text(material)


def compute_document_state(
    did: str,
    version: int,
    document: dict[str, Any],
    previous_version_hash: str = ZERO_HASH,
) -> ComputedDidState:
    """
    一站式计算 DID 文档的完整版本状态

    同时计算文档哈希、默克尔根和版本哈希，打包为不可变的值对象，
    减少上层调用方重复计算，并确保各哈希值使用同一份输入数据。

    Args:
        did: DID 标识符
        version: 当前版本号
        document: DID 文档内容字典
        previous_version_hash: 前一版本的版本哈希，默认为全零哈希

    Returns:
        ComputedDidState: 包含所有计算结果的不可变对象
    """
    document_hash = build_document_hash(document)
    merkle_root = build_merkle_root(document)
    version_hash = build_version_hash(
        did=did,
        version=version,
        document_hash=document_hash,
        merkle_root=merkle_root,
        previous_version_hash=previous_version_hash,
    )
    return ComputedDidState(
        document_hash=document_hash,
        merkle_root=merkle_root,
        version_hash=version_hash,
        previous_version_hash=previous_version_hash,
    )


def compute_changed_attributes(
    old_document: dict[str, Any],
    new_document: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    比较两个版本的 DID 文档，找出发生变化的属性

    将文档扁平化为路径-值对，逐键对比，返回所有新增、删除或修改的属性详情。
    该结果可用于生成增量更新证明或展示给用户的变更摘要。

    Args:
        old_document: 旧版本的 DID 文档
        new_document: 新版本的 DID 文档

    Returns:
        list[dict]: 变更属性列表，每项包含 path（属性路径）、old_value（旧值）和 new_value（新值）
    """
    old_flat = dict(flatten_document(old_document))
    new_flat = dict(flatten_document(new_document))
    all_keys = sorted(set(old_flat.keys()) | set(new_flat.keys()))

    changed = []
    for path in all_keys:
        old_value = old_flat.get(path)
        new_value = new_flat.get(path)
        if old_value != new_value:
            changed.append(
                {
                    'path': path,
                    'old_value': old_value,
                    'new_value': new_value,
                }
            )
    return changed