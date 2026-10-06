import json
from pathlib import Path

from solcx import compile_standard, install_solc
from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "contracts" / "DIDState.sol"
DEPLOY_DIR = ROOT / "deployments"
DEPLOY_DIR.mkdir(exist_ok=True)

RPC = "http://ganache:8545"
SOLC_VERSION = "0.8.20"


def main():
    install_solc(SOLC_VERSION)

    source = CONTRACT_FILE.read_text(encoding="utf-8")

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {
                "DIDState.sol": {"content": source}
            },
            "settings": {
                "outputSelection": {
                    "*": {
                        "*": ["abi", "evm.bytecode"]
                    }
                }
            },
        },
        solc_version=SOLC_VERSION,
    )

    contract_data = compiled["contracts"]["DIDState.sol"]["DIDState"]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    (DEPLOY_DIR / "abi.json").write_text(
        json.dumps(abi, indent=2), encoding="utf-8"
    )

    w3 = Web3(Web3.HTTPProvider(RPC))
    assert w3.is_connected(), "Ganache 未连接"

    sender = w3.eth.accounts[0]
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    tx_hash = contract.constructor().transact({"from": sender, "chainId": 1337})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    (DEPLOY_DIR / "address.json").write_text(
        json.dumps({"contractAddress": receipt.contractAddress}, indent=2),
        encoding="utf-8",
    )

    print("contractAddress =", receipt.contractAddress)
    print("txHash =", tx_hash.hex())
    print("status =", receipt.status)


if __name__ == "__main__":
    main()