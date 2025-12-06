import os
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# ----------------------------------------
# Setup
# ----------------------------------------
load_dotenv()

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ----------------------------------------
    # MongoDB Connection
    # ----------------------------------------
    mongo_uri = os.getenv("MONGO_URI")
    mongo_dbname = os.getenv("MONGO_DB", "haasappprojectsdb")
    client = MongoClient(mongo_uri)
    db = client[mongo_dbname]

    print(f"✅ Connected to MongoDB Atlas database: {mongo_dbname}")

    # Helper to serialize MongoDB docs
    def serialize_doc(doc):
        doc["_id"] = str(doc["_id"])
        return doc

    # ----------------------------------------
    # ROUTES
    # ----------------------------------------

    # Root route → render the Projects UI
    @app.route("/")
    def index():
        return render_template("index.html")

    # Health check (JSON)
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "message": "MongoDB connection active"})

    # Get all projects
    @app.route("/projects", methods=["GET"])
    def get_projects():
        projects = [serialize_doc(p) for p in db.projects.find()]
        return jsonify({"success": True, "projects": projects})

    # Create a new project
    @app.route("/projects", methods=["POST"])
    def create_project():
        try:
            data = request.get_json()
            if not data or "project_id" not in data or "project_name" not in data:
                return jsonify({"success": False, "message": "Missing required fields"}), 400

            db.projects.insert_one(data)
            data["_id"] = str(data.get("_id", ""))
            return jsonify({"success": True, "project": data}), 201
        except Exception as e:
            print("❌ Error creating project:", e)
            return jsonify({"success": False, "message": str(e)}), 500

    # Get project by ID
    @app.route("/projects/<project_id>", methods=["GET"])
    def get_project_by_id(project_id):
        proj = db.projects.find_one({"project_id": project_id})
        if proj:
            return jsonify({"success": True, "project": serialize_doc(proj)})
        return jsonify({"success": False, "message": "Project not found"}), 404

    # Render the Top 10 Companies (Frontend)
    @app.route("/top10companies")
    def top10companies_page():
        return render_template("top10companies.html")

    return app


# ----------------------------------------
# Local Run
# ----------------------------------------
if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 2000))
    app.run(debug=True, host="0.0.0.0", port=port)
