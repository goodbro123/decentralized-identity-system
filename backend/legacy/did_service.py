from web3 import Web3
from chain import get_contract


def get_latest(did_key):
    w3, contract = get_contract()
    result = contract.functions.getLatest(did_key).call()

    version, doc_hash, vh_latest, status_root, last_updated, block_number, exists = result

    return {
        "version": int(version),
        "docHash": Web3.to_hex(doc_hash),
        "vhLatest": Web3.to_hex(vh_latest),
        "statusRoot": Web3.to_hex(status_root),
        "lastUpdated": int(last_updated),
        "blockNumber": int(block_number),
        "exists": bool(exists),
    }


def update_state(did_key, version, doc_hash, vh_latest, status_root):
    w3, contract = get_contract()
    sender = w3.eth.accounts[0]

    tx_hash = contract.functions.updateState(
        did_key, version, doc_hash, vh_latest, status_root
    ).transact({"from": sender})

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    events = contract.events.DIDStateUpdated().process_receipt(receipt)
    parsed_events = []
    for evt in events:
        args = evt["args"]
        parsed_events.append({
            "didKey": Web3.to_hex(args["didKey"]),
            "version": int(args["version"]),
            "docHash": Web3.to_hex(args["docHash"]),
            "vhLatest": Web3.to_hex(args["vhLatest"]),
            "statusRoot": Web3.to_hex(args["statusRoot"]),
            "blockNumber": int(args["blockNumber"]),
            "timestamp": int(args["timestamp"]),
        })

    return {
        "txHash": tx_hash.hex(),
        "receipt": {
            "status": int(receipt.status),
            "blockNumber": int(receipt.blockNumber),
            "gasUsed": int(receipt.gasUsed),
        },
        "events": parsed_events,
    }