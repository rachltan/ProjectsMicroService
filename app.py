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
    from bson import ObjectId

@app.route("/projects", methods=["POST"])
def create_project():
    try:
        data = request.get_json()
        result = projects_collection.insert_one(data)
        inserted = projects_collection.find_one({"_id": result.inserted_id})

        # Convert ObjectId → string for JSON
        inserted["_id"] = str(inserted["_id"])

        return jsonify({
            "success": True,
            "project": inserted
        }), 201

    except Exception as e:
        import traceback
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
