import json
from uuid import uuid4
from datetime import datetime
from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
from redis import Redis

from employee.validation import (
    missing_field,
    is_valid_positive_number
)
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient


employee_blueprint = Blueprint(
    "employee",
    __name__
)

def parse_iso_date(value):
    if not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None


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


def employee_required(function):
    @wraps(function)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()

        if claims.get("role") != "employee":
            return jsonify(
                msg="Missing Authorization Header"
            ), 401

        return function(*args, **kwargs)

    return wrapper


@employee_blueprint.route(
    "/create_buy_order",
    methods=["POST"]
)
@employee_required
def create_buy_order():
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    required_fields = [
        "name",
        "categories",
        "buying_price",
        "info"
    ]

    for field in required_fields:
        if missing_field(body, field):
            return jsonify({
                "message": f"Field {field} is missing."
            }), 400

    name = body["name"]
    categories = body["categories"]
    buying_price = body["buying_price"]
    info = body["info"]

    if not isinstance(name, str):
        return jsonify({
            "message": "Field name is missing."
        }), 400

    if not isinstance(categories, list):
        return jsonify({
            "message": "Field categories is missing."
        }), 400

    if len(categories) == 0:
        return jsonify({
            "message": "Categories list is empty."
        }), 400

    if not is_valid_positive_number(buying_price):
        return jsonify({
            "message": "Invalid buying price."
        }), 400

    if not isinstance(info, dict):
        return jsonify({
            "message": "Field info is missing."
        }), 400

    order_uuid = str(uuid4())

    order = {
        "uuid": order_uuid,
        "order_type": "BUY",
        "name": name,
        "categories": categories,
        "buying_price": buying_price,
        "info": info
    }

    redis_client = get_redis_client()

    redis_client.set(
        f"order:{order_uuid}",
        json.dumps(order)
    )

    return "", 200

@employee_blueprint.route(
    "/create_sell_order",
    methods=["POST"]
)
@employee_required
def create_sell_order():
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    required_fields = [
        "id",
        "selling_price"
    ]

    for field in required_fields:
        if missing_field(body, field):
            return jsonify({
                "message": f"Field {field} is missing."
            }), 400

    asset_id = body["id"]
    selling_price = body["selling_price"]

    if not isinstance(asset_id, str):
        return jsonify({
            "message": "Invalid id."
        }), 400

    try:
        object_id = ObjectId(asset_id)
    except (InvalidId, TypeError):
        return jsonify({
            "message": "Invalid id."
        }), 400

    assets = get_assets_collection()

    asset = assets.find_one({
        "_id": object_id
    })

    if asset is None:
        return jsonify({
            "message": "Invalid id."
        }), 400

    if not is_valid_positive_number(selling_price):
        return jsonify({
            "message": "Invalid selling price."
        }), 400

    order_uuid = str(uuid4())

    order = {
        "uuid": order_uuid,
        "order_type": "SELL",
        "id": asset_id,
        "selling_price": selling_price
    }

    redis_client = get_redis_client()

    redis_client.set(
        f"order:{order_uuid}",
        json.dumps(order)
    )

    return "", 200


@employee_blueprint.route("/search", methods=["POST"])
@employee_required
def search():
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    query = {}

    name = body.get("name")

    if isinstance(name, str) and len(name) > 0:
        query["name"] = {
            "$regex": name,
            "$options": "i"
        }

    category = body.get("category")

    if isinstance(category, str) and len(category) > 0:
        query["categories"] = category

    buying_date = body.get("buying_date")

    if buying_date is not None:
        parsed_buying_date = parse_iso_date(buying_date)

        if parsed_buying_date is not None:
            query["buying_date"] = {
                "$gt": parsed_buying_date
            }

    selling_date = body.get("selling_date")

    if selling_date is not None:
        parsed_selling_date = parse_iso_date(selling_date)

        if parsed_selling_date is not None:
            query["selling_date"] = {
                "$lt": parsed_selling_date
            }

    operator_mapping = {
        "eq": "$eq",
        "ne": "$ne",
        "gt": "$gt",
        "gte": "$gte",
        "lt": "$lt",
        "lte": "$lte",
        "in": "$in",
        "nin": "$nin"
    }

    info_filters = body.get("info_filters", [])

    if isinstance(info_filters, list):
        for info_filter in info_filters:
            if not isinstance(info_filter, dict):
                continue

            field = info_filter.get("field")
            operator = info_filter.get("operator")

            if (
                not isinstance(field, str)
                or len(field) == 0
                or operator not in operator_mapping
                or "value" not in info_filter
            ):
                continue

            mongo_field = f"info.{field}"
            mongo_operator = operator_mapping[operator]

            query[mongo_field] = {
                mongo_operator: info_filter["value"]
            }

    assets_collection = get_assets_collection()
    assets_cursor = assets_collection.find(query)

    result = []

    for asset in assets_cursor:
        serialized_asset = {
            "id": str(asset["_id"]),
            "name": asset["name"],
            "categories": asset["categories"],
            "buying_date": asset["buying_date"].isoformat(),
            "buying_price": asset["buying_price"],
            "info": asset.get("info", {})
        }

        if "selling_date" in asset:
            serialized_asset["selling_date"] = (
                asset["selling_date"].isoformat()
            )

        if "selling_price" in asset:
            serialized_asset["selling_price"] = (
                asset["selling_price"]
            )

        result.append(serialized_asset)

    return jsonify({
        "assets": result
    }), 200