"""
合约加载模块

本模块负责从文件系统加载已部署智能合约的 ABI 接口定义和链上地址，
并提供统一的合约实例获取方法。所有加载操作均会进行存在性校验，
若文件缺失或格式错误将抛出 ContractLoadError 异常。
"""

import json
from pathlib import Path

from web3 import Web3

from infrastructure.blockchain.web3_provider import get_web3
from shared.config import settings
from shared.exceptions import ContractLoadError


def load_contract_abi() -> list:
    """
    加载智能合约 ABI 文件

    从配置指定的路径读取 ABI 文件，并解析为 Python 列表返回。

    Returns:
        list: 合约 ABI 接口定义列表

    Raises:
        ContractLoadError: 当 ABI 文件不存在或内容无法解析时抛出
    """
    path = Path(settings.contract_abi_path)
    if not path.exists():
        raise ContractLoadError(f"ABI 文件不存在：{path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise ContractLoadError(f"读取 ABI 文件失败：{e}") from e


def load_contract_address() -> str:
    """
    加载已部署合约的链上地址

    从配置指定的路径读取地址文件，提取其中的 contractAddress 字段，
    并转换为校验和格式的以太坊地址。

    Returns:
        str: 校验和格式的合约地址

    Raises:
        ContractLoadError: 当地址文件不存在、缺少字段或格式错误时抛出
    """
    path = Path(settings.contract_address_path)
    if not path.exists():
        raise ContractLoadError(f"合约地址文件不存在：{path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        address = data.get("contractAddress")
        if not address:
            raise ContractLoadError("地址文件中缺少 contractAddress 字段")
        return Web3.to_checksum_address(address)
    except Exception as e:
        raise ContractLoadError(f"读取合约地址失败：{e}") from e


def load_contract():
    """
    加载完整的合约实例

    组合调用 ABI 加载、地址加载和 Web3 实例，返回可直接调用的合约对象。

    Returns:
        web3.contract.Contract: 已绑定地址和 ABI 的合约实例

    Raises:
        BlockchainConnectionError: 当无法连接区块链节点时抛出
        ContractLoadError: 当 ABI 或地址加载失败时抛出
    """
    w3 = get_web3()
    abi = load_contract_abi()
    address = load_contract_address()
    return w3.eth.contract(address=address, abi=abi)