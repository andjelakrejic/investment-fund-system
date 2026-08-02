import os

class Configuration:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        (
            "mysql+pymysql://authentication_user:"
            "authentication_password@127.0.0.1:3306/authentication"
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "development-secret-key"
    )