# config.py – minimal config for projects microservice

import os

class Config:
    # Prefer a full Mongo connection string
    MONGO_URI = os.getenv("MONGO_URI")

    # Fallback host/port mode
    MONGO_HOST = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT = int(os.getenv("MONGO_PORT", "27017"))
    MONGO_DB = os.getenv("MONGO_DB", "projects_db")
    MONGO_INITDB_ROOT_USERNAME = os.getenv("MONGO_INITDB_ROOT_USERNAME")
    MONGO_INITDB_ROOT_PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    MONGO_AUTHSOURCE = os.getenv("MONGO_AUTHSOURCE", "admin")
