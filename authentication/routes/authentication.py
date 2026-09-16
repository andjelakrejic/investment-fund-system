from datetime import timedelta

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from authentication.models import database, User
from authentication.validation import is_valid_email
authentication_blueprint = Blueprint(
    "authentication",
    __name__
)

# Korisnik ne moze sam da se registruje kao Director - ne ubacuje podatak o role-u u formi!
@authentication_blueprint.route("/register", methods=["POST"])
def register():
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    required_fields = [
        "forename",
        "surname",
        "email",
        "password"
    ]

    # Provera obaveznih polja
    for field in required_fields:
        if field not in body or not isinstance(body[field], str) or len(body[field]) == 0:
            return jsonify({
                "message": f"Field {field} is missing."
            }), 400

    forename = body["forename"]
    surname = body["surname"]
    email = body["email"]
    password = body["password"]

    if not is_valid_email(email):
        return jsonify({
            "message": "Invalid email."
        }), 400

    if len(password) < 8:
        return jsonify({
            "message": "Invalid password."
        }), 400

    existing_user = User.query.filter_by(email=email).first()

    if existing_user is not None:
        return jsonify({
            "message": "Email already exists."
        }), 400

    user = User(
        forename=forename,
        surname=surname,
        email=email,
        password=generate_password_hash(password),
        role="employee"
    )

    database.session.add(user)
    database.session.commit()

    return "", 200

@authentication_blueprint.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True)

    if body is None:
        body = {}

    required_fields = ["email", "password"]

    for field in required_fields:
        if (
                field not in body
                or not isinstance(body[field], str)
                or len(body[field]) == 0
        ):
            return jsonify({
                "message": f"Field {field} is missing."
            }), 400

    email = body["email"]
    password = body["password"]

    if not is_valid_email(email):
        return jsonify({
            "message": "Invalid email."
        }), 400

    user = User.query.filter_by(email=email).first() # trazi se korisnik u bazi po emailu

    if user is None or not check_password_hash(user.password, password):
        return jsonify({
            "message": "Invalid credentials."
        }), 400

    additional_claims = {
        "forename": user.forename,
        "surname": user.surname,
        "email": user.email,
        "role": user.role
    }

    # kreira se jwt token na osnovu emaila koji traje 1h
    access_token = create_access_token(
        identity=user.email,
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=1)
    )

    return jsonify({
        "accessToken": access_token
    }), 200



@authentication_blueprint.route("/delete", methods=["POST"])
@jwt_required()
def delete():
    email = get_jwt_identity()

    user = User.query.filter_by(email=email).first()

    if user is None:
        return jsonify({
            "message": "Unknown user."
        }), 400

    database.session.delete(user)
    database.session.commit()

    return "", 200