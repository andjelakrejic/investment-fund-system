from pathlib import Path

from solcx import (
    compile_standard,
    get_installed_solc_versions,
    install_solc
)
from web3 import Web3


SOLC_VERSION = "0.8.20"


def get_web3(blockchain_url):
    web3 = Web3(
        Web3.HTTPProvider(blockchain_url)
    )

    if not web3.is_connected():
        raise ConnectionError(
            "Could not connect to the Ethereum blockchain."
        )

    return web3


def compile_voting_contract():
    installed_versions = {
        str(version)
        for version in get_installed_solc_versions()
    }

    if SOLC_VERSION not in installed_versions:
        install_solc(SOLC_VERSION)

    project_root = Path(__file__).resolve().parent.parent
    contract_path = project_root / "contracts" / "Voting.sol"

    contract_source = contract_path.read_text(
        encoding="utf-8"
    )

    compiled_contract = compile_standard(
        {
            "language": "Solidity",
            "sources": {
                "Voting.sol": {
                    "content": contract_source
                }
            },
            "settings": {
                "evmVersion": "paris",
                "outputSelection": {
                    "*": {
                        "*": [
                            "abi",
                            "evm.bytecode.object"
                        ]
                    }
                }
            }
        },
        solc_version=SOLC_VERSION
    )

    voting_contract = compiled_contract[
        "contracts"
    ]["Voting.sol"]["Voting"]

    abi = voting_contract["abi"]
    bytecode = voting_contract[
        "evm"
    ]["bytecode"]["object"]

    return abi, bytecode

def deploy_voting_contract(blockchain_url, voters):
    web3 = get_web3(blockchain_url)
    abi, bytecode = compile_voting_contract()

    deployer_account = web3.eth.accounts[0]

    voting_contract = web3.eth.contract(
        abi=abi,
        bytecode=bytecode
    )

    transaction_hash = voting_contract.constructor(
        voters
    ).transact({
        "from": deployer_account
    })

    transaction_receipt = web3.eth.wait_for_transaction_receipt(
        transaction_hash
    )

    deployed_contract = web3.eth.contract(
        address=transaction_receipt.contractAddress,
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

    contract = web3.eth.contract(
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
        serialize_transaction(approve_transaction),
        serialize_transaction(reject_transaction)
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