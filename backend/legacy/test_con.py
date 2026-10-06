from web3 import Web3
from did_service import get_latest, update_state

did_key = Web3.keccak(text="did:example:alice")
doc_hash = Web3.keccak(text="doc-v1")
vh_latest = Web3.keccak(text="vh-v1")
status_root = Web3.keccak(text="status-v1")

print("=== 1. 获取更新前最新数据 ===")
print(get_latest(did_key))

print("\n=== 2. 更新数据 ===")
result = update_state(did_key, 1, doc_hash, vh_latest, status_root)
print(result)

print("\n=== 3. 获取更新后最新数据 ===")
print(get_latest(did_key))