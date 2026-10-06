from web3 import Web3

w3 = Web3(Web3.HTTPProvider("http://ganache:8545"))

print("connected:", w3.is_connected())
print("chain_id:", w3.eth.chain_id)

accounts = w3.eth.accounts
print("accounts:", accounts)

print("block_number:", w3.eth.block_number)

first_account = accounts[0]
balance_wei = w3.eth.get_balance(first_account)
print("first_account:", first_account)
print("balance_wei:", balance_wei)
print("balance_eth:", w3.from_wei(balance_wei, "ether"))