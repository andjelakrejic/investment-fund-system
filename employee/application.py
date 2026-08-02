from flask import Flask
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
from redis import Redis

from employee.configuration import Configuration
from employee.routes.employee import employee_blueprint


app = Flask(__name__)
app.config.from_object(Configuration)

jwt = JWTManager(app)

app.register_blueprint(employee_blueprint)

mongo_client = MongoClient(app.config["MONGO_URI"])
mongo_database = mongo_client[
    app.config["MONGO_DATABASE"]
]

redis_client = Redis(
    host=app.config["REDIS_HOST"],
    port=app.config["REDIS_PORT"],
    decode_responses=True
)


@app.route("/")
def index():
    mongo_client.admin.command("ping")
    redis_client.ping()

    return "Employee service works."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)