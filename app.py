from dotenv import load_dotenv
load_dotenv()
import os
import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from pymongo import MongoClient

# --------------------------------------------
# Flask App Factory
# --------------------------------------------
def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    CORS(app)

    # ----------------------------------------
    # MongoDB Connection
    # ----------------------------------------
    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb+srv://<USERNAME>:<PASSWORD>@<CLUSTER>.mongodb.net/"
    )
    client = MongoClient(MONGO_URI)
    db = client["haasappprojectsdb"]   # your main MongoDB database name
    projects_collection = db["Projects"]
    hardware_collection = db["HardwareSet"]
    users_collection = db["Users"]

    # ----------------------------------------
    # Helper: Load fallback CSV data (for top brands)
    # ----------------------------------------
    def load_csv_fallback():
        try:
            brand_detail = pd.read_csv("data/stg_brand_detail.csv")
            top10 = pd.read_csv("data/stg_daily_spend_top10.csv")

            merged = (
                top10.merge(
                    brand_detail,
                    on="brand_name",
                    how="left"
                )
                .drop_duplicates(subset=["brand_name"])
                .sort_values("spend_amount", ascending=False)
                .head(10)
            )
            merged["source"] = "csv-fallback"
            return merged.to_dict(orient="records")
        except Exception as e:
            print(f"⚠️ CSV Fallback Error: {e}")
            return []

    # ----------------------------------------
    # ROUTE: Create Project
    # ----------------------------------------
    @app.route("/projects", methods=["POST"])
    def create_project():
        try:
            data = request.get_json()
            project_id = data.get("project_id")
            project_name = data.get("project_name")
            project_desc = data.get("project_desc", "")
            target_state = data.get("target_state", "")
            target_category = data.get("target_category", "")

            if not project_id or not project_name:
                return jsonify({
                    "success": False,
                    "message": "Project ID and Project Name are required."
                }), 400

            project_doc = {
                "project_id": project_id,
                "project_name": project_name,
                "project_desc": project_desc,
                "target_state": target_state,
                "target_category": target_category,
                "hardware_set_id": [],
                "num_of_hardware_sets": 0
            }

            projects_collection.insert_one(project_doc)

            return jsonify({
                "success": True,
                "project": project_doc
            })
        except Exception as e:
            import traceback
            print("⚠️ Error creating project:", e)
            traceback.print_exc()
            return jsonify({
                "success": False,
                "message": f"Error creating project: {str(e)}"
            }), 500


    # ----------------------------------------
    # ROUTE: Get Project by ID
    # ----------------------------------------
    @app.route("/projects/<project_id>", methods=["GET"])
    def get_project(project_id):
        try:
            project = projects_collection.find_one({"project_id": project_id}, {"_id": 0})
            if not project:
                return jsonify({
                    "success": False,
                    "message": "Project not found."
                }), 404
            return jsonify({
                "success": True,
                "project": project
            })
        except Exception as e:
            print(f"⚠️ Error retrieving project: {e}")
            return jsonify({
                "success": False,
                "message": "Error retrieving project."
            }), 500

    # ----------------------------------------
    # ROUTE: Get Top 10 Companies (from CSV)
    # ----------------------------------------
    @app.route("/api/top10companies", methods=["GET"])
    def get_top10companies():
        try:
            data = load_csv_fallback()
            return jsonify({
                "success": True,
                "data": data,
                "source": "csv-fallback"
            })
        except Exception as e:
            print(f"⚠️ Error loading top10: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    # ----------------------------------------
    # ROUTES: Frontend Pages
    # ----------------------------------------
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/top10companies")
    def top10_page():
        return render_template("top10companies.html")

    return app


# --------------------------------------------
# Run Flask Locally
# --------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
