# extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

# This is now the single source of truth for the db object.
# It's initialized here, but not yet connected to a Flask app.
db = SQLAlchemy()

# Authentication extensions
login_manager = LoginManager()
bcrypt = Bcrypt()
