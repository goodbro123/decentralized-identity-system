"""
DID 状态合约交互模块

本模块封装了与 DIDState 智能合约的所有链上交互操作，包括：
- 查询 DID 最新状态（get_latest_state）
- 更新 DID 状态（update_state）
- 查询链上交易状态（get_transaction_status）

所有函数均返回规范化的字典数据，供上层应用服务和 API 层直接使用。
"""

from web3 import Web3

from domain.models.did_state import DidState
from infrastructure.blockchain.contract_loader import load_contract


def _to_bytes32(value: str | bytes) -> bytes:
    """
    将输入值转换为 bytes32 类型

    用于确保传递给合约的参数格式正确。若输入为字节序列则直接返回，
    否则视为十六进制字符串并转换为 32 字节的 bytes。

    Args:
        value: 十六进制字符串（可带 0x 前缀）或 bytes 对象

    Returns:
        bytes: 长度为 32 的字节序列
    """
    if isinstance(value, bytes):
        return value
    return Web3.to_bytes(hexstr=value)


def get_latest_state(did_key: str | bytes) -> dict:
    """
    查询指定 DID 在链上的最新状态

    调用合约的 getLatest 视图函数，从以太坊本地测试网络中获取
    该 DID 的最新版本摘要、默克尔根、哈希链值及更新时间等信息，
    并封装为 DidState 领域实体后以字典形式返回。

    Args:
        did_key: DID 的链上标识符（bytes32），支持十六进制字符串或 bytes 类型

    Returns:
        dict: 包含 exists、version、document_hash、merkle_root、
              version_hash 及 updated_at 等字段的字典
    """
    contract = load_contract()
    did_key_bytes = _to_bytes32(did_key)

    exists, version, document_hash, merkle_root, version_hash, updated_at = (
        contract.functions.getLatest(did_key_bytes).call()
    )

    state = DidState(
        exists=bool(exists),
        did_key=Web3.to_hex(did_key_bytes),
        version=int(version),
        document_hash=Web3.to_hex(document_hash),
        merkle_root=Web3.to_hex(merkle_root),
        version_hash=Web3.to_hex(version_hash),
        updated_at=int(updated_at),
    )
    return state.to_dict()


def update_state(
    sender: str,
    did_key: str | bytes,
    version: int,
    document_hash: str | bytes,
    merkle_root: str | bytes,
    version_hash: str | bytes,
) -> dict:
    """
    更新 DID 在链上的状态信息

    构建交易并调用合约的 updateState 方法，将新的版本摘要、默克尔根
    和版本哈希链值写入区块链。函数同时返回交易回执及解析后的合约事件。

    Args:
        sender: 交易发送方的以太坊地址（需已解锁）
        did_key: DID 的链上标识符（bytes32）
        version: 新版本号
        document_hash: 新版本 DID 文档的摘要（bytes32）
        merkle_root: 新版本属性级默克尔树的根哈希（bytes32）
        version_hash: 新版本哈希链值（bytes32）

    Returns:
        dict: 包含 tx_hash、block_number、status、gas_used 及 events 的字典
    """
    contract = load_contract()

    tx_hash = contract.functions.updateState(
        _to_bytes32(did_key),
        int(version),
        _to_bytes32(document_hash),
        _to_bytes32(merkle_root),
        _to_bytes32(version_hash),
    ).transact({"from": sender})

    receipt = contract.w3.eth.wait_for_transaction_receipt(tx_hash)

    events = []
    try:
        logs = contract.events.DIDStateUpdated().process_receipt(receipt)
        for log in logs:
            args = log["args"]
            events.append(
                {
                    "did_key": Web3.to_hex(args["didKey"]),
                    "version": int(args["version"]),
                    "document_hash": Web3.to_hex(args["documentHash"]),
                    "merkle_root": Web3.to_hex(args["merkleRoot"]),
                    "version_hash": Web3.to_hex(args["versionHash"]),
                    "updated_at": int(args["updatedAt"]),
                }
            )
    except Exception:
        pass

    return {
        "tx_hash": tx_hash.hex(),
        "block_number": int(receipt.blockNumber),
        "status": int(receipt.status),
        "gas_used": int(receipt.gasUsed),
        "events": events,
    }


def get_transaction_status(tx_hash: str | None) -> dict | None:
    """
    根据交易哈希查询链上交易状态

    若 tx_hash 为 None 则直接返回 None。否则查询交易回执并返回
    交易所在区块号、状态码及 Gas 消耗等基本信息。

    Args:
        tx_hash: 交易哈希字符串（可带 0x 前缀）

    Returns:
        dict 或 None: 包含 tx_hash、block_number、status 等字段的字典，
                      若 tx_hash 无效则返回 None
    """
    if not tx_hash:
        return None

    contract = load_contract()
    receipt = contract.w3.eth.get_transaction_receipt(tx_hash)

    return {
        "tx_hash": tx_hash,
        "block_number": int(receipt.blockNumber),
        "status": int(receipt.status),
        "gas_used": int(receipt.gasUsed),
    }