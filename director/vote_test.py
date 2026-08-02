from web3 import Web3


BLOCKCHAIN_URL = "http://127.0.0.1:8545"

CONTRACT_ADDRESS = "0xe78A0F7E598Cc8b0Bb87894B0F60dD2a88d6a8Ab"

APPROVE_DATA = (
    "0x4b9f5c980000000000000000000000000000000000000000000000000000000000000001"
)

VOTERS = [
    "0x90F8bf6A479f320ead074411a4B0e7944Ea8c9C1",
    "0xFFcf8FDEE72ac11b5c542428B35EEF5769C409f0"
]


web3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_URL))

if not web3.is_connected():
    raise RuntimeError("Could not connect to Ganache.")

for voter in VOTERS:
    voter = Web3.to_checksum_address(voter)

    transaction = {
        "from": voter,
        "to": Web3.to_checksum_address(CONTRACT_ADDRESS),
        "data": APPROVE_DATA,
        "gas": 200000,
        "gasPrice": web3.eth.gas_price,
        "nonce": web3.eth.get_transaction_count(voter),
        "chainId": web3.eth.chain_id
    }

    transaction_hash = web3.eth.send_transaction(transaction)

    receipt = web3.eth.wait_for_transaction_receipt(
        transaction_hash
    )

    print(
        "Vote sent from:",
        voter,
        "status:",
        receipt.status
    )