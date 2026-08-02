import os


class Configuration:
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "development-secret-key"
    )

    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://127.0.0.1:27017/"
    )

    MONGO_DATABASE = os.getenv(
        "MONGO_DATABASE",
        "investment"
    )

    REDIS_HOST = os.getenv(
        "REDIS_HOST",
        "127.0.0.1"
    )

    REDIS_PORT = int(
        os.getenv("REDIS_PORT", "6379")
    )