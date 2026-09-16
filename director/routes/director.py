import json
from functools import wraps
from pymongo import MongoClient
from uuid import UUID

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

def get_assets_collection(): # vraca mongo kolekciju assets - stvarne investicije
    mongo_client = MongoClient(
        current_app.config["MONGO_URI"]
    )
    mongo_database = mongo_client[
        current_app.config["MONGO_DATABASE"]
    ]
    return mongo_database["assets"]

def director_required(function): # provera da li je poslat JWT token
    @wraps(function)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()

        if claims.get("role") != "director":
            return jsonify(msg="Missing Authorization Header"), 401

        return function(*args, **kwargs)

    return wrapper


# {
#   "name": "Apartment",
#   "buying_price": 120000,
#   "selling_price": 150000,
#   "categories": ["real_estate"]
# }

@director_blueprint.route(
    "/pending_orders",
    methods=["GET"]
)
@director_required
def pending_orders(): # director trazi buy/sell zahteve iz redisa (pending)
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
def decision(): # director pokrece blockchain glasanje za uuid zahtev iz redisa, uz poslate glasace (voters)
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    # Provera da li poslat uuid (zahtev) postoji
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

    # Neispravan uuid
    if (
        not is_valid_uuid(order_uuid)
        or not redis_client.exists(redis_key)
    ):
        return jsonify({
            "message": "Invalid uuid."
        }), 400

    # Nedostaju voters
    if (
        "voters" not in body
        or not isinstance(body["voters"], list)
        or len(body["voters"]) == 0
    ):
        return jsonify({
            "message": "Field voters is missing."
        }), 400

    voters = body["voters"]

    # Voters nevalidno
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

    # Poslat je paran broj glasaca
    if len(normalized_voters) % 2 == 0:
        return jsonify({
            "message": "Even number of voters."
        }), 400

    # BLOCKCHAIN
    deployment = deploy_voting_contract( # za konkretan order director napravi novi contract za glasanje
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

    # Zahtev jos ne brisemo - cuvamo za order adresu i ABI njgeogvog smart ugovora
    redis_client.hset(
        f"voting:{order_uuid}",
        mapping={
            "contract_address": contract_address,
            "abi": json.dumps(abi),
            "finished": "false"
        }
    )

    return jsonify({ # vraca pripremljene transakcije za glasanje za i protiv
        "approve_transaction": approve_transaction,
        "reject_transaction": reject_transaction
    }), 200

# ----------------------------------------------------------------------------
# MODIF

## jos neke:
# "Nađi kategoriju sa najvećim prosečnim profitom"
# "Vrati sve investicije čiji je profit veći od prosečnog"
# "Za svaku kategoriju izračunaj broj prodatih investicija"

@director_blueprint.route(
    "/assets-by-category",
    methods=["GET"]
)
def assets_by_category():
    assets = get_assets_collection()

    pipeline = [
        {
            "$unwind": "$categories"
        },
        {
            "$group": {
                "_id": "$categories",
                "count": {
                    "$sum": 1
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "count": 1
            }
        },
        {
            "$sort": {
                "count": -1,
                "category": 1
            }
        }
    ]

    statistics = list(assets.aggregate(pipeline))

    return jsonify({
        "statistics": statistics
    }), 200


@director_blueprint.route(
    "/highest-profit",
    methods=["GET"]
)
def highest_profit():
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": { # gledace se samo upit koji ima buying i selling price
                "buying_price": {
                    "$exists": True,
                    "$ne": None
                },
                "selling_price": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$addFields": {
                "profit": {
                    "$subtract": [
                        "$selling_price",
                        "$buying_price"
                    ]
                }
            }
        },
        {
            "$sort": {
                "profit": -1 # za najmanji profit 1
            }
        },
        {
            "$limit": 1
        },
        {
            "$project": {
                "_id": 0,
                "highest_profit": "$profit"
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result[0]), 200

@director_blueprint.route(
    "/highest-roi",
    methods=["GET"]
)
def highest_roi():
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": { # gledace se samo upit koji ima buying i selling price i ciji buying price nije 0
                "buying_price": {
                    "$exists": True,
                    "$nin": [None, 0]
                },
                "selling_price": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$addFields": {
                "roi": {
                    "$divide": [
                        {
                            "$subtract": [
                                "$selling_price",
                                "$buying_price"
                            ]
                        },
                        "$buying_price"
                    ]
                }
            }
        },
        {
            "$sort": {
                "roi": -1 # za najmanji roi 1
            }
        },
        {
            "$limit": 1
        },
        {
            "$project": {
                "_id": 0
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result[0]), 200

# Nove modif:

# Prosecan profit:
# za ukupni profit isto samo promeni $avg u $sum

@director_blueprint.route(
    "/average-profit",
    methods=["GET"]
)
def average_profit():
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "buying_price": {
                    "$exists": True, 
                    "$ne": None
                },
                "selling_price": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$group": {
                "_id": None,
                "average_profit": {
                    "$avg": {
                        "$subtract": [
                            "$selling_price",
                            "$buying_price"
                        ]
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "average_profit": "$average_profit" # pisalo je 1
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({
            "average_profit": 0
        }), 200

    return jsonify(result[0]), 200


# Broj prodatih investicija - mora da ima selling_price i selling_date:

@director_blueprint.route(
    "/sold-assets-count",
    methods=["GET"]
)
def sold_assets_count():
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "selling_price": {
                    "$exists": True,
                    "$ne": None
                },
                "selling_date": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$count": "count"
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({
            "count": 0
        }), 200

    return jsonify(result[0]), 200


@director_blueprint.route(
    "/average-roi-by-category",
    methods=["GET"]
)
def average_roi_by_category(): # racuna prosecan roi po kategorijama - samo za prodate assets
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "selling_price": {
                    "$exists": True,
                }
            }
        },
        {
            "$unwind": "$categories"
        },
        {
            "$group": {
                "_id": "$categories",
                "average_roi": {
                    "$avg": {
                        "$multiply": [
                            {
                                "$divide": [
                                    {
                                        "$subtract": [
                                            "$selling_price",
                                            "$buying_price"
                                        ]
                                    },
                                    "$buying_price"
                                ]
                            },
                            100
                        ]

                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "average_roi": 1
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result), 200


@director_blueprint.route(
    "/unsold-assets",
    methods=["GET"]
)
def unsold_assets(): # assets koji nemaju selling_price
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "selling_price": {
                    "$exists": False,
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "buying_price": 1
            }
        },
        {
            "$sort": {
                "buying_price": -1
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result), 200

@director_blueprint.route(
    "/asset-price-status",
    methods=["GET"]
)
def asset_price_status(): # statusi: unsold, zero, profit, loss
    assets = get_assets_collection()

    pipeline = [
        {
            "$project": {
                "_id": 0,
                "name": 1,
                "status": {
                    "$cond": {
                        "if": {
                            "$gt": ["$selling_price", "$buying_price"]
                        },
                        "then": "profit",
                        "else": {
                            "$cond": {
                                "if": {
                                    "$eq": ["$selling_price", "$buying_price"]
                                },
                                "then": "zero",
                                "else": {
                                    "$cond": {
                                        "if": {
                                            "$eq": [
                                                {"$type": "$selling_price"},
                                                "missing"
                                            ]
                                        },
                                        "then": "unsold",
                                        "else": "loss"
                                    }
                                }
                            }
                        }
                    }
                }
            }

        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result), 200


@director_blueprint.route(
    "/profitable-assets-count",
    methods=["GET"]
)
def profitable_assets_count(): # broji assets kod kojih vazi: selling_price > buying_price
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "selling_price": {
                    "$exists": True,
                    "$ne": None
                },
                "buying_price": {
                    "$exists": True,
                    "$ne": None
                },
                "$expr": { # omogucava da u $match koristiš izraze i porediš vrednost jednog polja sa drugim poljem
                    "$gt": ["$selling_price", "$buying_price"]
                }
            }
        },
        {
            "$count": "count"
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result), 200

@director_blueprint.route(
    "/category-price-range",
    methods=["GET"]
)
def category_price_range(): # za svaku kategoriju vraca najnizi i najvisi buying_price
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "buying_price": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$unwind": "$categories"
        },
        {
            "$group": {
                "_id": "$categories",
                "max_price": {
                    "$max": "$buying_price"
                },
                "min_price": {
                    "$min": "$buying_price"
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "max_price": 1,
                "min_price": 1
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({}), 200

    return jsonify(result), 200


@director_blueprint.route(
    "/highest-average-profit-category",
    methods=["GET"]
)
def highest_average_profit_category():
    assets = get_assets_collection()

    pipeline = [
        {
            "$match": {
                "buying_price": {
                    "$exists": True,
                    "$ne": None
                },
                "selling_price": {
                    "$exists": True,
                    "$ne": None
                }
            }
        },
        {
            "$unwind": "$categories"
        },
        {
            "$group": {
                "_id": "$categories",
                "average_profit": {
                    "$avg": {
                        "$subtract": [
                            "$selling_price",
                            "$buying_price"
                        ]
                    }
                }
            }
        },
        {
            "$sort": {
                "average_profit": -1
            }
        },
        {
            "$limit": 1
        },
        {
            "$project": {
                "_id": 0,
                "category": "$_id",
                "average_profit": 1
            }
        }
    ]

    result = list(assets.aggregate(pipeline))

    if len(result) == 0:
        return jsonify({
            "average_profit": 0
        }), 200

    return jsonify(result[0]), 200

@director_blueprint.route(
    "/status-distribution",
    methods=["GET"]
)
def status_distribution():
    assets = get_assets_collection()

    pipeline = [
        {
            "$addFields": {
                "status": {
                    "$cond": {
                        "if": { "$gt": ["$selling_price", "$buying_price"] },
                        "then": "profit",
                        "else": {
                            "$cond": {
                                "if": {"$eq", ["$buying_price", "$selling_price"]},
                                "then": "zero",
                                "else": {
                                    "$cond": {
                                        "if": {"$eq": [{"$type": "$selling_price"}, "missing"]},
                                        "then": "unsold",
                                        "else": "loss"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        {
            "group": {
                "_id": "$status",
                "count": {"$sum": 1 }
            }
        },
        {
            "$project": {
                "status": "$_id",
                "count": 1,
                "_id": 0
            }
        }
    ]

    result = list(assets.aggregate(pipeline))
    return jsonify(result), 200