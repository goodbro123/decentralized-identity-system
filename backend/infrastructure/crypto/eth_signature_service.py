"""
签名与地址工具模块

本模块提供 Ethereum 地址校验、地址比较以及从 personal_sign 签名中恢复地址的工具函数。
用于 DID 认证流程中验证用户对地址/私钥的控制权。
"""

from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3


def normalize_eth_address(address: str) -> str:
    """
    将输入的地址字符串规范化为校验和格式（checksummed）或小写形式。

    若输入为空，返回空字符串；若输入已经是合法的以太坊地址，则调用 Web3.to_checksum_address
    返回符合 EIP-55 的校验和地址；若转换过程中出现异常（如格式错误），则退回到返回小写地址。

    Args:
        address: 待规范化的以太坊地址字符串。

    Returns:
        str: 规范化后的地址。合法地址返回校验和形式；非法或空输入返回小写/空字符串。
    """
    if not address:
        return ""

    try:
      return Web3.to_checksum_address(address)
    except Exception:
      return address.lower()


def recover_address_from_signature(message: str, signature: str) -> str:
    """
    从 personal_sign / signMessage 风格的签名中恢复出 Ethereum 地址。

    该函数使用 eth_account 库的 encode_defunct 对消息进行标准编码，然后调用
    Account.recover_message 恢复签名者的地址，并返回校验和格式的地址。

    适用于前端使用 ethers.Wallet.signMessage(message) 生成的签名。

    Args:
        message: 原始签名的消息文本。
        signature: 十六进制签名字符串（通常以 0x 开头）。

    Returns:
        str: 校验和格式的签名者以太坊地址。
    """
    encoded_message = encode_defunct(text=message)
    recovered = Account.recover_message(encoded_message, signature=signature)
    return Web3.to_checksum_address(recovered)


def is_same_address(left: str, right: str) -> bool:
    """
    比较两个以太坊地址是否指向同一账户。

    若任一地址为空，直接返回 False。否则尝试将两者转换为校验和地址后比较。
    如果转换失败（如非法格式），退回使用小写字符串比较。

    Args:
        left: 第一个地址字符串。
        right: 第二个地址字符串。

    Returns:
        bool: 如果地址代表同一账户则返回 True，否则 False。
    """
    if not left or not right:
        return False

    try:
        return Web3.to_checksum_address(left) == Web3.to_checksum_address(right)
    except Exception:
        return left.lower() == right.lower()