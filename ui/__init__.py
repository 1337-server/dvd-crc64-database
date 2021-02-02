import os
import bcrypt  # noqa: F401

from flask import Flask, logging, current_app  # noqa: F401
from flask_sqlalchemy import SQLAlchemy
from flask.logging import default_handler  # noqa: F401
app = Flask(__name__)

b = os.getcwd()
sqlitefile = 'sqlite:///' + b + '/arm-crc64.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = sqlitefile
db = SQLAlchemy(app)
