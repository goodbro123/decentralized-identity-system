import json
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_DIR = ROOT / "deployments"
RPC = "http://ganache:8545"


def get_w3():
    w3 = Web3(Web3.HTTPProvider(RPC))
    if not w3.is_connected():
        raise RuntimeError("Cannot connect to Ganache")
    return w3


def load_abi():
    return json.loads((DEPLOY_DIR / "abi.json").read_text(encoding="utf-8"))


def load_address():
    data = json.loads((DEPLOY_DIR / "address.json").read_text(encoding="utf-8"))
    return data["contractAddress"]


def get_contract():
    w3 = get_w3()
    abi = load_abi()
    address = load_address()
    return w3, w3.eth.contract(address=w3.to_checksum_address(address), abi=abi)