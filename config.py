import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env in development (safe to keep; on prod you'll rely on real env vars)
load_dotenv()

class Config:
    # Mongo – Heroku/Atlas mode
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB = os.getenv("MONGO_DB", "projects_db")

    # docker-style local Mongo (not used when MONGO_URI is set)
    MONGO_HOST = os.getenv('MONGO_HOST', 'localhost')
    MONGO_PORT = int(os.getenv('MONGO_PORT', 27017))
    MONGO_INITDB_ROOT_USERNAME = os.getenv('MONGO_INITDB_ROOT_USERNAME')
    MONGO_INITDB_ROOT_PASSWORD = os.getenv('MONGO_INITDB_ROOT_PASSWORD')
    MONGO_AUTHSOURCE = os.getenv('MONGO_AUTHSOURCE', 'admin')

    # JWT (not used by this microservice right now but harmless)
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MIN", "30"))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        days=int(os.getenv("JWT_REFRESH_DAYS", "7"))
    )

    # CORS
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
