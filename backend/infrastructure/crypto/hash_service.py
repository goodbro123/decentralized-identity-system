"""
哈希服务模块

本模块提供基于 Keccak-256 算法的哈希计算工具函数，用于生成 DID 文档摘要、
构建默克尔树节点哈希、将 DID 映射为链上标识符（didKey）等。
所有哈希函数均返回十六进制字符串，与以太坊生态的哈希格式保持一致。
"""

from web3 import Web3

# 全零哈希值（bytes32），常用于默克尔树空节点占位
ZERO_HASH = '0x' + ('00' * 32)


def keccak_text(text: str) -> str:
    """
    对文本字符串进行 Keccak-256 哈希计算

    将输入的 UTF-8 字符串转换为字节后计算哈希，返回十六进制字符串。

    Args:
        text: 待哈希的文本字符串

    Returns:
        str: 以 "0x" 开头的十六进制哈希字符串
    """
    return Web3.keccak(text=text).hex()


def keccak_bytes(data: bytes) -> str:
    """
    对字节数据进行 Keccak-256 哈希计算

    直接对输入的字节序列计算哈希，返回十六进制字符串。

    Args:
        data: 待哈希的字节数据

    Returns:
        str: 以 "0x" 开头的十六进制哈希字符串
    """
    return Web3.keccak(data).hex()


def did_to_key(did: str) -> str:
    """
    将 DID 标识符转换为链上存储的 didKey

    通过对 DID 字符串进行 Keccak-256 哈希，生成固定长度的 bytes32 类型键值，
    用于在智能合约中作为身份标识的主键。

    Args:
        did: DID 标识符字符串，例如 "did:ethr:alice"

    Returns:
        str: 以 "0x" 开头的十六进制哈希字符串
    """
    return keccak_text(did)


def combine_hashes(left_hex: str, right_hex: str) -> str:
    """
    组合两个哈希值生成父节点哈希

    将两个十六进制哈希字符串还原为 bytes32，拼接后进行 Keccak-256 哈希，
    用于默克尔树的节点合并计算。

    Args:
        left_hex: 左子节点的哈希值（十六进制字符串）
        right_hex: 右子节点的哈希值（十六进制字符串）

    Returns:
        str: 父节点的哈希值（十六进制字符串）
    """
    left = Web3.to_bytes(hexstr=left_hex)
    right = Web3.to_bytes(hexstr=right_hex)
    return Web3.keccak(left + right).hex()


def is_same_hash(left: str, right: str) -> bool:
    """
    比较两个哈希值是否相等（忽略大小写）

    通常在链上哈希与链下计算哈希比对时使用，防止因 '0x' 前缀或大小写差异导致误判。

    Args:
        left: 第一个哈希字符串
        right: 第二个哈希字符串

    Returns:
        bool: 两者相等返回 True，否则返回 False
    """
    return str(left).lower() == str(right).lower()