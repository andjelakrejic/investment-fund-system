import json
import time
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient
from redis import Redis

from director.blockchain import get_voting_result


def process_approved_order(assets, order):
    current_time = datetime.now(timezone.utc)

    if order["order_type"] == "BUY":
        assets.insert_one({
            "name": order["name"],
            "categories": order["categories"],
            "buying_price": order["buying_price"],
            "buying_date": current_time,
            "info": order["info"]
        })

    elif order["order_type"] == "SELL":
        assets.update_one(
            {
                "_id": ObjectId(order["id"])
            },
            {
                "$set": {
                    "selling_price": order["selling_price"],
                    "selling_date": current_time
                }
            }
        )


def process_finished_votings(
    blockchain_url,
    mongo_uri,
    mongo_database_name,
    redis_host,
    redis_port
):
    redis_client = Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )

    mongo_client = MongoClient(mongo_uri)
    mongo_database = mongo_client[mongo_database_name]
    assets = mongo_database["assets"]

    while True:
        try:
            voting_keys = redis_client.keys("voting:*")

            for voting_key in voting_keys:
                order_uuid = voting_key.removeprefix("voting:")

                voting_data = redis_client.hgetall(voting_key)

                if not voting_data:
                    continue

                contract_address = voting_data.get(
                    "contract_address"
                )
                serialized_abi = voting_data.get("abi")

                if (
                    contract_address is None
                    or serialized_abi is None
                ):
                    continue

                abi = json.loads(serialized_abi)

                result = get_voting_result(
                    blockchain_url,
                    contract_address,
                    abi
                )

                if not result["finished"]:
                    continue

                order_key = f"order:{order_uuid}"
                serialized_order = redis_client.get(order_key)

                if serialized_order is not None:
                    order = json.loads(serialized_order)

                    if result["approved"]:
                        process_approved_order(
                            assets,
                            order
                        )

                redis_client.delete(order_key)
                redis_client.delete(voting_key)

                print(
                    f"Voting {order_uuid} processed. "
                    f"Approved: {result['approved']}"
                )

        except Exception as error:
            print(
                "Error while processing votings:",
                error
            )

        time.sleep(2)