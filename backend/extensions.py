# backend/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_caching import Cache
from flask_cors import CORS

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
cache = Cache(config={'CACHE_TYPE': 'simple'})  # Add this config
cors = CORS()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'