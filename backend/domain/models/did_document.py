"""
DID 文档领域实体模块

本模块定义了链下 DID 文档的核心领域对象 DidDocument，
用于表示一个已注册 DID 的当前有效文档、版本摘要、默克尔根、哈希链值及相关元数据。
该对象在应用层与持久层之间传递，是系统业务逻辑的核心载体。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DidDocument:
    """
    DID 文档领域实体

    表示链下存储的一个 DID 文档的当前版本，包含文档内容、版本相关哈希值、
    变更记录及时间戳。该对象对应 MongoDB 中的 `did_documents` 集合，
    是领域驱动设计中的“实体”，其唯一标识为 `did` 字段。

    Attributes:
        did: DID 标识符，如 "did:ethr:alice"
        version: 当前文档版本号（从 1 开始递增）
        document: DID 文档的完整内容（JSON 兼容字典）
        document_hash: 全文档规范化序列化后的 Keccak-256 哈希
        merkle_root: 属性级默克尔树的根哈希
        version_hash: 当前版本的哈希链值
        previous_version_hash: 前一版本的哈希链值（首版本为全零哈希）
        transaction_hash: 上链锚定交易的哈希（可选）
        status: 文档状态，如 "active"
        changed_attributes: 本次更新变更的属性列表
        created_at: 文档创建时间（UTC）
        updated_at: 文档最后更新时间（UTC）
    """
    did: str
    version: int
    document: dict[str, Any]
    document_hash: str
    merkle_root: str
    version_hash: str
    previous_version_hash: str
    transaction_hash: str | None = None
    status: str = "active"
    changed_attributes: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """
        将 DidDocument 实例转换为普通字典

        用于序列化输出（如传递给 MongoDB 存储或 API 响应）。
        返回的字典包含所有字段，其中 version 强制转换为 int 确保类型一致。

        Returns:
            dict[str, Any]: 包含实体所有属性的字典表示
        """
        return {
            "did": self.did,
            "version": int(self.version),
            "document": self.document,
            "document_hash": self.document_hash,
            "merkle_root": self.merkle_root,
            "version_hash": self.version_hash,
            "previous_version_hash": self.previous_version_hash,
            "transaction_hash": self.transaction_hash,
            "status": self.status,
            "changed_attributes": self.changed_attributes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }