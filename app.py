import os
import time
import csv
import requests
import pyodbc
import pandas as pd
from urllib.parse import urlencode
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from projectdb import ProjectDB
from project import Project


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # ======================================================
    # 🔹 MongoDB Setup
    # ======================================================
    mongo_uri = os.getenv("MONGO_URI")
    mongo_db = os.getenv("MONGO_DB", "projects_db")

    print("🔍 Using Mongo URI:", mongo_uri)
    print("🔍 Using Mongo DB:", mongo_db)

    project_db = ProjectDB(
        uri=mongo_uri,
        dbname=mongo_db,
        connect_timeout_ms=15000,
        server_select_timeout_ms=15000,
    )

    _dewey_cache = {"payload": None, "key": None, "ts": 0}
    _CACHE_TTL_SEC = 300

    # ======================================================
    # 🔹 Azure SQL Connection Helper
    # ======================================================
    def get_azure_connection():
        server = os.getenv("AZURE_SQL_SERVER")
        database = os.getenv("AZURE_SQL_DATABASE")
        username = os.getenv("AZURE_SQL_USERNAME")
        password = os.getenv("AZURE_SQL_PASSWORD")
        driver = "{ODBC Driver 18 for SQL Server}"

        conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        return pyodbc.connect(conn_str)

    # ======================================================
    # 🔹 UI ROUTES
    # ======================================================
    @app.get("/")
    def root():
        return render_template("index.html")

    @app.get("/top10companies")
    def top10_page():
        return render_template("top10companies.html")

    @app.get("/health")
    def health():
        try:
            _ = project_db.ping()
            return jsonify({"status": "ok", "mongo": "reachable"}), 200
        except Exception as e:
            return jsonify({"status": "degraded", "mongo_error": str(e)}), 200

    # ======================================================
    # 🔹 PROJECT CREATION with optional Azure autofill
    # ======================================================
    @app.post("/projects")
    def create_project_route():
        data = request.get_json(force=True) or {}
        project_id = (data.get("project_id") or "").strip()
        project_name = (data.get("project_name") or "").strip()
        if not project_id or not project_name:
            return jsonify({
                "success": False,
                "message": "project_id and project_name are required"
            }), 400

        payload = {
            "project_id": project_id,
            "project_name": project_name,
            "project_desc": (data.get("project_desc") or "").strip(),
        }

        # Try to enrich with Azure brand info
        try:
            conn = get_azure_connection()
            query = """
                SELECT TOP 1 state, category
                FROM dbo.TopBrands
                WHERE LOWER(brand_name) LIKE ?
            """
            df = pd.read_sql(query, conn, params=[f"%{project_name.lower()}%"])
            if not df.empty:
                payload["target_state"] = df.iloc[0]["state"]
                payload["target_category"] = df.iloc[0]["category"]
            conn.close()
        except Exception as e:
            print(f"⚠️ Azure enrichment failed: {e}")

        try:
            proj_obj = Project.from_dict(payload) if hasattr(Project, "from_dict") else payload
            created = project_db.create_project(
                proj_obj.to_dict() if hasattr(proj_obj, "to_dict") else proj_obj
            )
            return jsonify({"success": True, "project": created}), 201
        except ValueError as ve:
            return jsonify({"success": False, "message": str(ve)}), 409
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    # ======================================================
    # 🔹 PROJECT CRUD ROUTES
    # ======================================================
    @app.get("/projects")
    def list_projects_route():
        limit = request.args.get("limit", type=int)
        projects = project_db.list_projects(limit=limit)
        return jsonify({"success": True, "projects": projects}), 200

    @app.get("/projects/<project_id>")
    def get_project_route(project_id: str):
        proj = project_db.get_project(project_id)
        if not proj:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "project": proj}), 200

    @app.put("/projects/<project_id>")
    def update_project_route(project_id: str):
        updates = request.get_json(force=True) or {}
        updates.pop("project_id", None)
        updated = project_db.update_project(project_id, updates)
        if not updated:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "project": updated}), 200

    @app.delete("/projects/<project_id>")
    def delete_project_route(project_id: str):
        deleted = project_db.delete_project(project_id)
        if not deleted:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "message": "Project deleted"}), 200

    # ======================================================
    # 🔹 TOP BRANDS via Azure SQL (auto fallback to CSV)
    # ======================================================
    @app.get("/api/top10companies")
    def api_top10companies():
        """
        Returns Top 10 brands from Azure SQL.
        Falls back to local CSVs if connection fails.
        """

        year = request.args.get("year")
        cache_key = f"azure:{year or 'all'}"
        now = time.time()

        if _dewey_cache["key"] == cache_key and (now - _dewey_cache["ts"] < _CACHE_TTL_SEC):
            return jsonify({"success": True, "data": _dewey_cache["payload"]}), 200

        data = None
        error_msg = None

        try:
            conn = get_azure_connection()
            query = """
                SELECT TOP 10 brand_name, sector, category, state, spend_amount
                FROM dbo.TopBrands
                ORDER BY spend_amount DESC
            """
            df = pd.read_sql(query, conn)
            data = df.to_dict(orient="records")
            _dewey_cache.update({"payload": data, "key": cache_key, "ts": now})
            conn.close()
        except Exception as e:
            error_msg = f"Azure SQL error: {e}"
            # fallback to CSV
            try:
                brand_meta_path = "data/stg_brand_detail.csv"
                spend_path = "data/stg_daily_spend_top10.csv"

                brand_meta = {}
                with open(brand_meta_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        brand_meta[row["brand_name"]] = {
                            "sector": row.get("sector", ""),
                            "category": row.get("category", "")
                        }

                rows = []
                with open(spend_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        if year and str(r.get("year", "")).strip() != str(year):
                            continue
                        brand_name = r.get("brand_name", "")
                        meta = brand_meta.get(brand_name, {})
                        row = {
                            "brand_name": brand_name,
                            "sector": meta.get("sector", ""),
                            "category": meta.get("category", ""),
                            "state": r.get("state", ""),
                            "spend_amount": float(r.get("spend_amount", 0) or 0)
                        }
                        rows.append(row)

                rows.sort(key=lambda x: x["spend_amount"], reverse=True)
                data = rows[:10]
                _dewey_cache.update({"payload": data, "key": cache_key, "ts": now})
            except Exception as fe:
                return jsonify({"success": False, "message": f"CSV fallback failed: {fe}"}), 500

        response = {"success": True, "data": data or []}
        if error_msg:
            response["warning"] = error_msg
        return jsonify(response), 200

    return app


# ======================================================
# 🔹 Gunicorn / Heroku Entrypoint
# ======================================================
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
