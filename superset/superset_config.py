"""
Apache Superset Configuration for Hotel ABC Platform
"""
import os
from datetime import timedelta

# Secret key for signing cookies
SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY", "supersecret-change-in-production-32chars")

# SQLAlchemy URI for Superset metadata database (uses same PostgreSQL)
SQLALCHEMY_DATABASE_URI = (
    f"postgresql+psycopg2://hotel_user:{os.getenv('POSTGRES_PASSWORD', 'hotel_secure_2025')}"
    f"@postgres:5432/hotel_abc_superset"
)

# Redis for caching
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "redis_secure_2025")
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': REDIS_HOST,
    'CACHE_REDIS_PORT': REDIS_PORT,
    'CACHE_REDIS_PASSWORD': REDIS_PASSWORD,
    'CACHE_REDIS_DB': 1,
}

# Feature flags
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "ALERT_REPORTS": True,
}

# OAuth2 authentication (optional - can be enabled)
# from flask_appbuilder.security.manager import AUTH_OAUTH
# AUTH_TYPE = AUTH_OAUTH
# OAUTH_PROVIDERS = [{
#     'name': ' hotel',
#     'icon': 'fa-google',
#     'token_key': 'access_token',
# }]

# Results backend for async queries
RESULT_BACKEND = 'cache'
RESULT_CACHE_SIZE = 256

# SQL tracing
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Timezone
TIME_ZONE = "Europe/Rome"

# Enable CORS for frontend
ENABLE_CORS = True
CORS_OPTIONS = {
    "origins": ["http://localhost:3000", "http://localhost:8088"],
    "supports_credentials": True,
}
