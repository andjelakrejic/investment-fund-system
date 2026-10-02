from flask import Flask
from flask_jwt_extended import JWTManager
from redis import Redis

from director.configuration import Configuration
from director.routes.director import director_blueprint

from threading import Thread

from director.voting_worker import (
    process_finished_votings
)
app = Flask(__name__)
app.config.from_object(Configuration)

jwt = JWTManager(app)

app.register_blueprint(director_blueprint)

redis_client = Redis(
    host=app.config["REDIS_HOST"],
    port=app.config["REDIS_PORT"],
    decode_responses=True
)
@app.route("/")
def index():
    redis_client.ping()

    return "Director service works."

def start_voting_worker():
    worker = Thread(
        target=process_finished_votings,
        kwargs={
            "blockchain_url": app.config[
                "BLOCKCHAIN_URL"
            ],
            "mongo_uri": app.config[
                "MONGO_URI"
            ],
            "mongo_database_name": app.config[
                "MONGO_DATABASE"
            ],
            "redis_host": app.config[
                "REDIS_HOST"
            ],
            "redis_port": app.config[
                "REDIS_PORT"
            ]
        },
        daemon=True
    )

    worker.start()

if __name__ == "__main__":
    start_voting_worker()
    app.run(host="0.0.0.0",debug=False, port=5002)