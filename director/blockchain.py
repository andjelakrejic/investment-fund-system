from pathlib import Path
import json

from web3 import Web3


def get_web3(blockchain_url): # pravi se Web3 objekat koji predstavlja vezu izmedju Python apl i Ethereum blockchaina - Ganache
    web3 = Web3(
        Web3.HTTPProvider(blockchain_url)
    )

    if not web3.is_connected():
        raise ConnectionError(
            "Could not connect to the Ethereum blockchain."
        )

    return web3

def load_voting_contract(): # Ucitavaju se Voting.abi (interfejs ugovora) i Voting.bin (kompajliran bajtkod ugovora)
    project_root = Path(__file__).resolve().parent.parent

    abi_path = (
        project_root
        / "solidity"
        / "output"
        / "Voting.abi"
    )

    bytecode_path = (
        project_root
        / "solidity"
        / "output"
        / "Voting.bin"
    )

    with abi_path.open("r", encoding="utf-8") as file:
        abi = json.load(file)

    bytecode = bytecode_path.read_text(
        encoding="utf-8"
    ).strip()

    return abi, bytecode


def deploy_voting_contract(blockchain_url, voters): #
    web3 = get_web3(blockchain_url)
    abi, bytecode = load_voting_contract()

    deployer_account = web3.eth.accounts[0] # prvi nalog iz Ganache ce deploy-ovati contract

    voting_contract = web3.eth.contract(
        abi=abi,
        bytecode=bytecode
    )

    transaction_hash = voting_contract.constructor(
        voters
    ).transact({
        "from": deployer_account
    })

    transaction_receipt = web3.eth.wait_for_transaction_receipt( # ceka se da Ganache obradi transakciju i vrati receipt
        transaction_hash
    )

    deployed_contract = web3.eth.contract(
        address=transaction_receipt.contractAddress, # adresa novog smart contracta
        abi=abi
    )

    return {
        "contract": deployed_contract,
        "contract_address": transaction_receipt.contractAddress,
        "abi": abi,
        "deployment_receipt": dict(transaction_receipt)
    }


def build_vote_transactions(
    blockchain_url,
    contract_address,
    abi
):
    web3 = get_web3(blockchain_url)

    contract = web3.eth.contract( # contract kreiran u deploy_voting_contract na contract_address
        address=Web3.to_checksum_address(contract_address),
        abi=abi
    )

    approve_transaction = contract.functions.vote(
        True
    ).build_transaction({
        "from": web3.eth.accounts[0],
        "gas": 200000,
        "gasPrice": web3.eth.gas_price,
        "nonce": web3.eth.get_transaction_count(
            web3.eth.accounts[0]
        ),
        "chainId": web3.eth.chain_id
    })

    reject_transaction = contract.functions.vote(
        False
    ).build_transaction({
        "from": web3.eth.accounts[0],
        "gas": 200000,
        "gasPrice": web3.eth.gas_price,
        "nonce": web3.eth.get_transaction_count(
            web3.eth.accounts[0]
        ),
        "chainId": web3.eth.chain_id
    })

    return (
        serialize_transaction(approve_transaction), # vote(True)
        serialize_transaction(reject_transaction)   # vote(False)
    )

def serialize_transaction(transaction):
    result = {}

    for key, value in transaction.items():
        if isinstance(value, bytes):
            result[key] = Web3.to_hex(value)
        else:
            result[key] = value

    return result


def get_voting_result(
    blockchain_url,
    contract_address,
    abi
):
    web3 = get_web3(blockchain_url)

    contract = web3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=abi
    )

    voting_ended = contract.functions.votingEnded().call()

    if not voting_ended:
        return {
            "finished": False,
            "approved": None
        }

    approved = contract.functions.approved().call()

    return {
        "finished": True,
        "approved": approved
    }