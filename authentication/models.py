from flask_sqlalchemy import SQLAlchemy

database = SQLAlchemy()

class User(database.Model):
    id = database.Column(database.Integer, primary_key=True)
    forename = database.Column(database.String(256), nullable=False)
    surname = database.Column(database.String(256), nullable=False)
    email = database.Column(
        database.String(256),
        unique=True,
        nullable=False
    )
    password = database.Column(database.String(256), nullable=False)
    role = database.Column(
        database.String(20),
        nullable=False,
        default="employee"
    )