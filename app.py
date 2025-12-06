import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# --------------------------------------------
# Load environment variables
# --------------------------------------------
load_dotenv()

def create_app():
    app = Flask(__name__)
    CORS(app)

    # ----------------------------------------
    # MongoDB Connection Setup
    # ----------------------------------------
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGO_DB", "haasappdb")

    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client[mongo_db]
        client.admin.command("ping")  # simple connection test
        print(f"✅ Connected to MongoDB Atlas database: {mongo_db}")
    except Exception as e:
        print(f"⚠️ Atlas connection failed, falling back to Docker Mongo: {e}")
        fallback_uri = (
            f"mongodb://{os.getenv('MONGO_INITDB_ROOT_USERNAME')}:"
            f"{os.getenv('MONGO_INITDB_ROOT_PASSWORD')}@"
            f"{os.getenv('MONGO_HOST')}:{os.getenv('MONGO_PORT')}/"
            f"?authSource={os.getenv('MONGO_AUTHSOURCE', 'admin')}"
        )
        client = MongoClient(fallback_uri)
        db = client[mongo_db]

    projects = db["projects"]

    # ----------------------------------------
    # Helpers
    # ----------------------------------------
    def serialize_project(p):
        p["_id"] = str(p["_id"])
        return p

    # ----------------------------------------
    # Routes
    # ----------------------------------------

    @app.route("/projects", methods=["POST"])
    def create_project():
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "No data provided"}), 400

            project = {
                "project_id": data.get("project_id"),
                "project_name": data.get("project_name"),
                "project_desc": data.get("project_desc"),
                "target_state": data.get("target_state", ""),
                "target_category": data.get("target_category", ""),
            }

            result = projects.insert_one(project)
            project["_id"] = str(result.inserted_id)
            return jsonify({"success": True, "project": project}), 201

        except Exception as e:
            return jsonify({"success": False, "message": f"Error creating project: {e}"}), 500

    @app.route("/projects/<project_id>", methods=["GET"])
    def get_project(project_id):
        try:
            project = projects.find_one({"project_id": project_id})
            if not project:
                return jsonify({"success": False, "message": "Project not found"}), 404
            return jsonify({"success": True, "project": serialize_project(project)})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    # Basic health check
    @app.route("/")
    def home():
        return jsonify({"status": "ok", "message": "MongoDB connection active"})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 2000)))
