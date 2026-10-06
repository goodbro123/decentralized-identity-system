"""
DID 链上状态领域实体模块

本模块定义了从智能合约查询返回的 DID 链上状态实体 DidState，
用于表示一个 DID 在区块链上的最新锚定信息，包含版本号、各类哈希摘要及更新时间。
该对象作为链上可信锚点与链下文档校验之间的数据桥梁。
"""

from dataclasses import dataclass


@dataclass
class DidState:
    """
    DID 链上状态领域实体

    表示智能合约中存储的单个 DID 的最新状态，包含是否存在、版本号、
    文档摘要、默克尔根、版本哈希链值及更新时间戳。
    该对象通常由 `did_state_contract.get_latest_state` 函数返回，
    并可用于与链下计算的哈希值进行一致性比对。

    Attributes:
        exists: 该 DID 是否已在链上注册
        did_key: DID 的链上标识符（bytes32 的十六进制字符串）
        version: 当前最新版本号
        document_hash: 当前版本 DID 文档的整体摘要（bytes32 十六进制字符串）
        merkle_root: 当前版本的属性级默克尔树根哈希
        version_hash: 当前版本的哈希链值（用于防回滚检测）
        updated_at: 最后更新时间戳（Unix 秒）
    """
    exists: bool
    did_key: str
    version: int
    document_hash: str
    merkle_root: str
    version_hash: str
    updated_at: int

    def to_dict(self) -> dict:
        """
        将 DidState 实例转换为普通字典

        用于序列化输出（如 API 响应或日志记录）。
        返回的字典中 version 和 updated_at 强制转换为 int 以确保类型一致。

        Returns:
            dict: 包含实体所有属性的字典表示
        """
        return {
            "exists": self.exists,
            "did_key": self.did_key,
            "version": int(self.version),
            "document_hash": self.document_hash,
            "merkle_root": self.merkle_root,
            "version_hash": self.version_hash,
            "updated_at": int(self.updated_at),
        }