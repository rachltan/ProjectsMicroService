# app.py
import os
from datetime import timedelta
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from config import Config
from userdb import UserDB
from azuredb import AzureDB

# ========= 1) TOKEN BLOCKLIST AT MODULE LEVEL =========
TOKEN_BLOCKLIST = set()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Optional: short expiry for easier testing of logout/expiry behavior
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", timedelta(minutes=60))

    # CORS (allow Authorization header)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # JWT
    jwt = JWTManager(app)

    # ===== DB init (flexible: URI or host/port) =====
    if app.config.get("MONGO_URI"):
        user_db = UserDB(
            dbname=app.config.get("MONGO_DB"),
            mongo_uri=app.config["MONGO_URI"],
        )
    else:
        user_db = UserDB(
            dbname=app.config.get("MONGO_DB"),
            host=app.config.get("MONGO_HOST"),
            port=app.config.get("MONGO_PORT"),
            username=app.config.get("MONGO_INITDB_ROOT_USERNAME"),
            password=app.config.get("MONGO_INITDB_ROOT_PASSWORD"),
            auth_source=app.config.get("MONGO_AUTHSOURCE", "admin"),
        )
    # Azure SQL Database connection
    azure_db = AzureDB(
        server=app.config.get("AZURE_SQL_SERVER"),
        database=app.config.get("AZURE_SQL_DATABASE"),
        username=app.config.get("AZURE_SQL_USERNAME"),
        password=app.config.get("AZURE_SQL_PASSWORD")
    )

    # ===== JWT / Blocklist hooks =====
    @jwt.token_in_blocklist_loader
    def _is_token_revoked(jwt_header, jwt_payload):
        return jwt_payload.get("jti") in TOKEN_BLOCKLIST

    @jwt.revoked_token_loader
    def _revoked_response(jwt_header, jwt_payload):
        return jsonify({"success": False, "message": "Token has been revoked"}), 401

    @jwt.expired_token_loader
    def _expired_response(jwt_header, jwt_payload):
        return jsonify({"success": False, "message": "Token has expired"}), 401

    @jwt.unauthorized_loader
    def _missing_auth_header(err):
        return jsonify({"success": False, "message": "Missing or invalid Authorization header"}), 401

    # ============== UI PAGES ==============
    @app.get("/")
    def home():
        # Login + dashboard
        return render_template("index.html")

    @app.get("/hardware")
    def hardware_page():
        # Simple page routed from dashboard
        return render_template("hardware.html")

    @app.get("/top10companies")
    def top10_page():
        # Simple page routed from dashboard
        return render_template("top10companies.html")

    # ============== AUTH API ==============
    @app.post("/createAccount")
    def create_account():
        data = request.get_json(force=True) or {}
        username = (data.get("Username") or "").strip()
        password = data.get("pswd")
        if not username or not password:
            return jsonify({"success": False, "message": "username or password is missing"}), 400
        if user_db.find_by_username(username):
            return jsonify({"success": False, "message": "username already exists"}), 409
        user_public = user_db.create_user(username=username, password=password)
        access_token = create_access_token(identity=user_public["username"])
        return jsonify({
            "success": True,
            "message": "Account created",
            "user": user_public,
            "access_token": access_token
        }), 201

    @app.post("/logIn")
    def log_in():
        data = request.get_json(force=True) or {}
        username = data.get("Username")
        password = data.get("pswd")
        if not username or not password:
            return jsonify({"success": False, "message": "username or password is missing"}), 400
        user_public = user_db.verify_user(username=username, password=password)
        if not user_public:
            return jsonify({"success": False, "message": "incorrect password"}), 401
        access_token = create_access_token(identity=user_public["username"])
        return jsonify({
            "success": True,
            "message": "login successful",
            "user": user_public,
            "access_token": access_token
        }), 200

    # Validate token / whoami (used at page load)
    @app.get("/me")
    @jwt_required()
    def me():
        return jsonify({"success": True, "username": get_jwt_identity()}), 200

    # Logout → revoke current token (server-side) + frontend clears localStorage
    @app.post("/logOut")
    @jwt_required()
    def log_out():
        jti = get_jwt()["jti"]
        TOKEN_BLOCKLIST.add(jti)
        return jsonify({"success": True, "message": "Logged out"}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "2000"))
    app.run(host="0.0.0.0", port=port, debug=False)
