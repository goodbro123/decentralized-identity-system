"""
合约读写测试脚本

测试目标：
1. 验证 backend 能连接 Ganache
2. 验证 DIDState 合约已经正确部署
3. 验证 getLatest 能读取 DID 链上状态
4. 验证 updateState 能写入 DID 链上状态
5. 验证写入后的链上状态与预期一致

运行方式：
    python tests/test_contract.py
"""

from web3 import Web3

from infrastructure.blockchain.did_state_contract import (
    get_latest_state,
    get_transaction_status,
    update_state,
)
from infrastructure.blockchain.contract_loader import load_contract_address
from infrastructure.blockchain.web3_provider import get_web3
from infrastructure.crypto.hash_service import did_to_key


def assert_equal(name: str, actual, expected):
    """
    简单断言工具，用于输出更清楚的错误信息。
    """
    if actual != expected:
        raise AssertionError(
            f"{name} 不一致: actual={actual}, expected={expected}"
        )


def print_section(title: str):
    print()
    print(f"--- {title} ---")


def main():
    print("=== test_contract.py ===")

    # 1. 测试 RPC 连接
    w3 = get_web3()

    print("RPC 连接状态      :", w3.is_connected())
    print("链 ID             :", w3.eth.chain_id)
    print("当前区块号        :", w3.eth.block_number)

    if not w3.is_connected():
        raise RuntimeError("Ganache RPC 连接失败")

    if not w3.eth.accounts:
        raise RuntimeError("Ganache 中没有可用账户")

    sender = w3.eth.accounts[0]
    print("发送方账户        :", sender)

    # 2. 检查合约地址是否真的有代码
    contract_address = load_contract_address()
    contract_code = w3.eth.get_code(contract_address)

    print("合约地址          :", contract_address)
    print("合约代码长度      :", len(contract_code))

    if len(contract_code) == 0:
        raise RuntimeError(
            f"合约地址上没有代码，请重新运行 python scripts/compile_deploy.py。address={contract_address}"
        )

    # 3. 构造测试 DID 和 didKey
    did = "did:ethr:alice"
    did_key = did_to_key(did)

    print("测试 DID          :", did)
    print("链上 didKey       :", did_key)

    # 4. 查询写入前链上状态
    print_section("写入前链上状态")
    before_state = get_latest_state(did_key)
    print(before_state)

    # 5. 构造本次写入数据
    old_version = int(before_state.get("version", 0))
    new_version = old_version + 1

    document_hash = Web3.keccak(
        text=f"{did}:document:{new_version}"
    ).hex()

    merkle_root = Web3.keccak(
        text=f"{did}:merkle-root:{new_version}"
    ).hex()

    version_hash = Web3.keccak(
        text=f"{did}:version-hash:{new_version}"
    ).hex()

    print_section("即将写入的数据")
    print("版本号            :", new_version)
    print("文档摘要          :", document_hash)
    print("默克尔根          :", merkle_root)
    print("版本哈希链值      :", version_hash)

    # 6. 调用 updateState 写入链上状态
    print_section("发送 updateState 交易")

    tx_result = update_state(
        sender=sender,
        did_key=did_key,
        version=new_version,
        document_hash=document_hash,
        merkle_root=merkle_root,
        version_hash=version_hash,
    )

    print(tx_result)

    if tx_result["status"] != 1:
        raise RuntimeError("updateState 交易失败")

    if not tx_result["tx_hash"]:
        raise RuntimeError("交易哈希为空")

    # 7. 查询交易状态
    print_section("交易状态查询")
    tx_status = get_transaction_status(tx_result["tx_hash"])
    print(tx_status)

    assert_equal("tx_hash", tx_status["tx_hash"], tx_result["tx_hash"])
    assert_equal("tx_status", tx_status["status"], 1)

    # 8. 查询写入后链上状态
    print_section("写入后链上状态")
    after_state = get_latest_state(did_key)
    print(after_state)

    # 9. 校验链上状态
    assert_equal("exists", after_state["exists"], True)
    assert_equal("did_key", after_state["did_key"], did_key)
    assert_equal("version", after_state["version"], new_version)
    assert_equal("document_hash", after_state["document_hash"], document_hash)
    assert_equal("merkle_root", after_state["merkle_root"], merkle_root)
    assert_equal("version_hash", after_state["version_hash"], version_hash)

    if int(after_state["updated_at"]) <= 0:
        raise AssertionError("updated_at 应该大于 0")

    # 10. 校验事件
    print_section("事件校验")

    events = tx_result.get("events", [])
    print("事件数量          :", len(events))
    print("事件内容          :", events)

    if not events:
        print("警告：未解析到 DIDStateUpdated 事件，但交易已成功。")
    else:
        event = events[0]
        assert_equal("event.did_key", event["did_key"], did_key)
        assert_equal("event.version", event["version"], new_version)
        assert_equal("event.document_hash", event["document_hash"], document_hash)
        assert_equal("event.merkle_root", event["merkle_root"], merkle_root)
        assert_equal("event.version_hash", event["version_hash"], version_hash)

    print()
    print("=== 合约测试通过 ===")
    print("getLatest / updateState / get_transaction_status 均正常")


if __name__ == "__main__":
    main()