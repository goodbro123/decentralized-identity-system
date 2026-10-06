"""
RPC 连通性测试模块

本模块用于测试后端与以太坊节点（Ganache）之间的 JSON-RPC 连接是否正常。
通过调用 Web3 实例获取连接状态、链 ID 和当前区块高度，验证区块链基础环境是否就绪。
"""

from infrastructure.blockchain.web3_provider import get_web3


def main() -> None:
    """
    主测试函数

    获取 Web3 单例实例，打印连接状态、链 ID 和当前区块号。
    若连接失败，将由 get_web3() 内部抛出 BlockchainConnectionError 异常。
    """
    w3 = get_web3()
    print("连接状态 =", w3.is_connected())
    print("链 ID =", w3.eth.chain_id)
    print("当前区块号 =", w3.eth.block_number)


if __name__ == "__main__":
    main()