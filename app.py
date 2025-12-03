import os
import time
import csv
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from projectdb import ProjectDB
from project import Project

def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    mongo_uri = os.getenv("MONGO_URI")
    mongo_db  = os.getenv("MONGO_DB", "projects_db")

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

    def _load_dewey_csv(year: str | None):
        csv_path = os.getenv("DEWEY_CSV_PATH", "data/stg_daily_spend_top10.csv")
        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if year and str(r.get("year", "")).strip() != str(year):
                    continue
                row = {
                    "brand_name": r.get("brand_name", ""),
                    "sector": r.get("sector", ""),
                    "category": r.get("category", ""),
                    "state": r.get("state", ""),
                }
                try:
                    row["spend_amount"] = float(r.get("spend_amount", 0) or 0)
                except Exception:
                    row["spend_amount"] = 0.0
                rows.append(row)

        rows.sort(key=lambda x: x.get("spend_amount", 0), reverse=True)
        return rows[:10]

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
    # 🔹 PROJECT CREATION with Dewey Auto-Fill Integration
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

        # 🧠 Try to auto-fill category/state from Dewey data
        try:
            dewey_url = os.getenv("DEWEY_API_URL")
            dewey_key = os.getenv("DEWEY_API_KEY")
            params = {"year": "2025"}
            headers = {}
            if dewey_key:
                headers["Authorization"] = f"Bearer {dewey_key}"            

            data_rows = []
            if dewey_url:
                resp = requests.get(f"{dewey_url}?{urlencode(params)}", headers=headers, timeout=10)
                if resp.ok:
                    payload_json = resp.json()
                    data_rows = payload_json.get("data", payload_json)
            else:
                data_rows = _load_dewey_csv("2025")

            for row in data_rows:
                brand = row.get("brand_name", "").lower()
                if brand and project_name.lower() in brand:
                    payload["target_state"] = row.get("state", "")
                    payload["target_category"] = row.get("category", "")
                    break
        except Exception as e:
            print(f"⚠️ Dewey enrichment failed: {e}")

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
    # 🔹 DEWEY PROXY API
    # ======================================================
        # ================= DEWEY PROXY API (with cache + auto fallback) =================
    @app.get("/api/top10companies")
def api_top10companies():
    """
    Returns Top 10 brands (optionally filtered by ?year=) for the Top Brands UI.

    Data source priority:
      1) Dewey API (live)
      2) Local CSV fallback (data/stg_brand_detail.csv + data/stg_daily_spend_top10.csv)
    """

    year = request.args.get("year")  # optional
    dewey_url = os.getenv("DEWEY_API_URL")
    dewey_key = os.getenv("DEWEY_API_KEY")

    cache_key = f"proxy:{year or 'all'}"
    now = time.time()
    if _dewey_cache["key"] == cache_key and (now - _dewey_cache["ts"] < _CACHE_TTL_SEC):
        return jsonify({"success": True, "data": _dewey_cache["payload"]}), 200

    data = None
    error_msg = None

    # -------- Try Dewey API first --------
    if dewey_url:
        try:
            params = {}
            if year:
                params["year"] = year
            headers = {}
            if dewey_key:
                headers["Authorization"] = f"Bearer {dewey_key}"

            r = requests.get(dewey_url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            payload = r.json()
            data = payload.get("data", payload)
            if not isinstance(data, list):
                raise ValueError("Unexpected Dewey API shape")

            # Normalize fields
            for row in data:
                row.setdefault("brand_name", "")
                row.setdefault("sector", "")
                row.setdefault("category", "")
                row.setdefault("state", "")
                try:
                    row["spend_amount"] = float(row.get("spend_amount", 0) or 0)
                except Exception:
                    row["spend_amount"] = 0.0

            _dewey_cache.update({"payload": data, "key": cache_key, "ts": now})

        except Exception as e:
            error_msg = f"Dewey API error: {e}"

    # -------- Fallback: local CSVs --------
    if not data:
        try:
            brand_meta_path = "data/stg_brand_detail.csv"
            spend_path = "data/stg_daily_spend_top10.csv"

            # Load brand metadata
            brand_meta = {}
            with open(brand_meta_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    brand_name = row.get("brand_name") or row.get("Brand") or ""
                    brand_meta[brand_name] = {
                        "sector": row.get("sector", ""),
                        "category": row.get("category", "")
                    }

            # Load spend data
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
                    }
                    try:
                        row["spend_amount"] = float(r.get("spend_amount", 0) or 0)
                    except Exception:
                        row["spend_amount"] = 0.0
                    rows.append(row)

            # Sort + take top 10
            rows.sort(key=lambda x: x.get("spend_amount", 0), reverse=True)
            data = rows[:10]

            _dewey_cache.update({"payload": data, "key": cache_key, "ts": now})

        except Exception as e:
            error_msg = error_msg or f"CSV fallback error: {e}"
            return jsonify({
                "success": False,
                "message": error_msg or "No data available"
            }), 500

    # -------- Always return something if possible --------
    response = {"success": True, "data": data or []}
    if error_msg:
        response["warning"] = error_msg  # Shown in UI bottom message if needed
    return jsonify(response), 200



    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
