import os
import time
import csv
import pymssql
import pandas as pd
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

    project_db = ProjectDB(uri=mongo_uri, dbname=mongo_db)

    _cache = {"payload": None, "key": None, "ts": 0}
    _CACHE_TTL_SEC = 300

    # ======================================================
    # 🔹 Azure SQL Connection (using pymssql)
    # ======================================================
    def get_azure_connection():
        server = os.getenv("AZURE_SQL_SERVER", "msitmproject.database.windows.net")
        database = os.getenv("AZURE_SQL_DATABASE", "MSITM_Project_Datbase")
        username = os.getenv("AZURE_SQL_USERNAME", "CloudSAffa4d29c")
        password = os.getenv("AZURE_SQL_PASSWORD", "Msitm1234%")

        # pymssql uses host, user, password, database
        return pymssql.connect(server=server, user=username, password=password, database=database, port=1433)

    # ======================================================
    # 🔹 Local CSV Fallback Loader
    # ======================================================
    def load_csv_fallback(year: str | None):
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
        return rows[:10]

    # ======================================================
    # 🔹 UI Routes
    # ======================================================
    @app.get("/")
    def root():
        return render_template("index.html")

    @app.get("/top10companies")
    def top10_page():
        return render_template("top10companies.html")

    # ======================================================
    # 🔹 PROJECT CREATION with Azure Autofill
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

        try:
            conn = get_azure_connection()
            query = """
                SELECT TOP 1 bd.category, bd.sector
                FROM ingest.stg_brand_detail bd
                WHERE LOWER(bd.brand_name) LIKE %s
            """
            df = pd.read_sql(query, conn, params=[f"%{project_name.lower()}%"])
            conn.close()
            if not df.empty:
                payload["target_category"] = df.iloc[0]["category"]
                payload["target_state"] = df.iloc[0]["sector"]
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
    # 🔹 TOP 10 BRANDS — Azure Query with CSV Fallback
    # ======================================================
    @app.get("/api/top10companies")
    def api_top10companies():
        """
        Returns Top 10 brands (from dbo.top10monthly joined with ingest.stg_brand_detail)
        """

        cache_key = "azure_top10"
        now = time.time()

        if _cache["key"] == cache_key and (now - _cache["ts"] < _CACHE_TTL_SEC):
            return jsonify({"success": True, "data": _cache["payload"]}), 200

        data = None
        error_msg = None

        try:
            conn = get_azure_connection()

            # get most recent month dynamically
            month_query = "SELECT MAX(month_start_date) AS latest_month FROM dbo.top10monthly"
            month_df = pd.read_sql(month_query, conn)
            latest_month = month_df.iloc[0]["latest_month"]

            # query top 10 brands joined with brand detail
            query = f"""
                SELECT TOP 10 
                    t.brand_name,
                    b.sector,
                    b.category,
                    t.total_spend AS spend_amount,
                    t.month_start_date
                FROM dbo.top10monthly t
                LEFT JOIN ingest.stg_brand_detail b
                    ON t.brand_name = b.brand_name
                WHERE t.month_start_date = %s
                ORDER BY t.monthly_rank ASC
            """

            df = pd.read_sql(query, conn, params=[latest_month])
            conn.close()
            data = df.to_dict(orient="records")

            _cache.update({"payload": data, "key": cache_key, "ts": now})

        except Exception as e:
            error_msg = f"Azure SQL error: {e}"
            try:
                data = load_csv_fallback(None)
            except Exception as fe:
                return jsonify({"success": False, "message": f"CSV fallback failed: {fe}"}), 500

        response = {"success": True, "data": data or []}
        if error_msg:
            response["warning"] = error_msg
        return jsonify(response), 200

    return app


# ======================================================
# 🔹 Gunicorn / Local Entrypoint
# ======================================================
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
