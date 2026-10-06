"""
Web3 提供者模块

本模块负责创建并管理 Web3 实例，提供与以太坊节点（Ganache）的连接。
通过单例模式确保全局仅有一个 Web3 实例，避免重复建立连接。
"""

from web3 import Web3

from shared.config import settings
from shared.exceptions import BlockchainConnectionError


_w3_instance: Web3 | None = None


def get_web3() -> Web3:
    """
    获取 Web3 单例实例

    若实例尚未创建，则根据配置中的 `web3_provider` 地址初始化新的 Web3 对象，
    并检查连接状态。若连接失败，抛出 BlockchainConnectionError 异常。

    Returns:
        Web3: 已连接至以太坊节点的 Web3 实例

    Raises:
        BlockchainConnectionError: 当无法连接到配置的 RPC 节点时抛出
    """
    global _w3_instance

    if _w3_instance is None:
        _w3_instance = Web3(Web3.HTTPProvider(settings.web3_provider))

    if not _w3_instance.is_connected():
        raise BlockchainConnectionError(
            f"无法连接到区块链节点：{settings.web3_provider}"
        )

    return _w3_instance