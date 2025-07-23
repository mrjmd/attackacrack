# extensions.py

from flask_sqlalchemy import SQLAlchemy

# This is now the single source of truth for the db object.
# It's initialized here, but not yet connected to a Flask app.
db = SQLAlchemy()
