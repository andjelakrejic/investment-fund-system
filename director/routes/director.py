import json
from functools import wraps
from pymongo import MongoClient
from datetime import datetime, timezone
from uuid import UUID

from bson import ObjectId

from flask import Blueprint, jsonify, current_app, request
from flask_jwt_extended import jwt_required, get_jwt
from redis import Redis
from web3 import Web3

from director.blockchain import (
    deploy_voting_contract,
    build_vote_transactions
)


director_blueprint = Blueprint(
    "director",
    __name__
)

def is_valid_uuid(value):
    if not isinstance(value, str):
        return False

    try:
        UUID(value)
        return True
    except ValueError:
        return False


def get_redis_client():
    return Redis(
        host=current_app.config["REDIS_HOST"],
        port=current_app.config["REDIS_PORT"],
        decode_responses=True
    )

def get_assets_collection():
    mongo_client = MongoClient(
        current_app.config["MONGO_URI"]
    )

    mongo_database = mongo_client[
        current_app.config["MONGO_DATABASE"]
    ]

    return mongo_database["assets"]

def director_required(function):
    @wraps(function)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()

        if claims.get("role") != "director":
            return jsonify(msg="Missing Authorization Header"), 401

        return function(*args, **kwargs)

    return wrapper


@director_blueprint.route(
    "/pending_orders",
    methods=["GET"]
)
@director_required
def pending_orders():
    redis_client = get_redis_client()

    keys = redis_client.keys("order:*")

    orders = []

    for key in keys:
        stored_order = redis_client.get(key)

        if stored_order is not None:
            orders.append(json.loads(stored_order))

    return jsonify({
        "orders": orders
    }), 200

@director_blueprint.route(
    "/report",
    methods=["GET"]
)
@director_required
def report():
    assets = get_assets_collection()

    pipeline = [
        {
            "$unwind": "$categories"
        },
        {
            "$group": {
                "_id": "$categories",
                "spent": {
                    "$sum": "$buying_price"
                },
                "earned": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {
                                        "$ne": [
                                            {
                                                "$ifNull": [
                                                    "$selling_price",
                                                    None
                                                ]
                                            },
                                            None
                                        ]
                                    },
                                    {
                                        "$ne": [
                                            {
                                                "$ifNull": [
                                                    "$selling_date",
                                                    None
                                                ]
                                            },
                                            None
                                        ]
                                    }
                                ]
                            },
                            "$selling_price",
                            0
                        ]
                    }
                }
            }
        },
        {
            "$sort": {
                "earned": -1,
                "spent": 1,
                "_id": 1
            }
        }
    ]

    aggregation_result = assets.aggregate(pipeline)

    statistics = []

    for result in aggregation_result:
        statistics.append({
            "category": result["_id"],
            "spent": result["spent"],
            "earned": result["earned"]
        })

    return jsonify({
        "statistics": statistics
    }), 200

@director_blueprint.route(
    "/decision",
    methods=["POST"]
)
@director_required
def decision():
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    # 1. Field uuid is missing.
    if (
        "uuid" not in body
        or not isinstance(body["uuid"], str)
        or len(body["uuid"]) == 0
    ):
        return jsonify({
            "message": "Field uuid is missing."
        }), 400

    order_uuid = body["uuid"]
    redis_client = get_redis_client()
    redis_key = f"order:{order_uuid}"

    # 2. Invalid uuid.
    if (
        not is_valid_uuid(order_uuid)
        or not redis_client.exists(redis_key)
    ):
        return jsonify({
            "message": "Invalid uuid."
        }), 400

    # 3. Field voters is missing.
    if (
        "voters" not in body
        or not isinstance(body["voters"], list)
        or len(body["voters"]) == 0
    ):
        return jsonify({
            "message": "Field voters is missing."
        }), 400

    voters = body["voters"]

    # 4. Invalid voter address.
    normalized_voters = []

    for voter in voters:
        if (
            not isinstance(voter, str)
            or not Web3.is_address(voter)
        ):
            return jsonify({
                "message": "Invalid voter address."
            }), 400

        normalized_voters.append(
            Web3.to_checksum_address(voter)
        )

    # 5. Even number of voters.
    if len(normalized_voters) % 2 == 0:
        return jsonify({
            "message": "Even number of voters."
        }), 400

    deployment = deploy_voting_contract(
        current_app.config["BLOCKCHAIN_URL"],
        normalized_voters
    )

    contract_address = deployment["contract_address"]
    abi = deployment["abi"]

    approve_transaction, reject_transaction = (
        build_vote_transactions(
            current_app.config["BLOCKCHAIN_URL"],
            contract_address,
            abi
        )
    )

    # Zahtev još ne brišemo.
    # Čuvamo podatke o njegovom ugovoru u Redis-u.
    redis_client.hset(
        f"voting:{order_uuid}",
        mapping={
            "contract_address": contract_address,
            "abi": json.dumps(abi),
            "finished": "false"
        }
    )

    return jsonify({
        "approve_transaction": approve_transaction,
        "reject_transaction": reject_transaction
    }), 200