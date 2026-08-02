from flask import Flask
from flask_jwt_extended import JWTManager
from werkzeug.security import generate_password_hash

from authentication.configuration import Configuration
from authentication.models import database, User
from authentication.routes.authentication import authentication_blueprint


app = Flask(__name__)
app.config.from_object(Configuration)

database.init_app(app)
jwt = JWTManager(app)

app.register_blueprint(authentication_blueprint)


@app.route("/")
def index():
    return "Authentication service works."


def initialize_database():
    database.create_all()

    director = User.query.filter_by(
        email="onlymoney@gmail.com"
    ).first()

    if director is None:
        director = User(
            forename="Scrooge",
            surname="McDuck",
            email="onlymoney@gmail.com",
            password=generate_password_hash("evenmoremoney"),
            role="director"
        )

        database.session.add(director)
        database.session.commit()

        print("Initial director created.")
    else:
        print("Initial director already exists.")


if __name__ == "__main__":
    with app.app_context():
        initialize_database()

    app.run(host="0.0.0.0", port=5000, debug=False)