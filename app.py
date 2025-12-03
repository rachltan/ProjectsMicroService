import os
import time
import csv
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from projectdb import ProjectDB
from project import Project

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # --- Mongo config from env (Heroku Config Vars) ---
    mongo_uri = os.getenv("MONGO_URI")            # e.g. mongodb+srv://user:pass@cluster/...
    mongo_db  = os.getenv("MONGO_DB", "projects_db")

    # Instantiate DB (param name is dbname)
    project_db = ProjectDB(
        uri=mongo_uri,
        dbname=mongo_db,
        connect_timeout_ms=15000,
        server_select_timeout_ms=15000,
    )

    # ------------- helpers for /api/top10companies -------------
    _dewey_cache = {"payload": None, "key": None, "ts": 0}
    _CACHE_TTL_SEC = 300  # 5 minutes

    def _load_dewey_csv(year: str | None):
        """
        Lightweight CSV fallback loader.
        Expects a CSV with columns like: brand_name,sector,category,state,spend_amount,year
        Path is configurable via DEWEY_CSV_PATH or defaults to data/stg_daily_spend_top10.csv
        """
        csv_path = os.getenv("DEWEY_CSV_PATH", "data/stg_daily_spend_top10.csv")
        rows = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if year and str(r.get("year", "")).strip() != str(year):
                    continue
                # normalize
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

        # sort desc by spend, take top 10
        rows.sort(key=lambda x: x.get("spend_amount", 0), reverse=True)
        return rows[:10]

    # ================= UI PAGES =================
    @app.get("/")
    def root():
        return render_template("index.html")

    @app.get("/top10companies")
    def top10_page():
        # Renders the Top Brands view; it can read ?state=&category=&year= from the URL
        return render_template("top10companies.html")

    # ================= HEALTH =================
    @app.get("/health")
    def health():
        try:
            _ = project_db.ping()
            return jsonify({"status": "ok", "mongo": "reachable"}), 200
        except Exception as e:
            return jsonify({"status": "degraded", "mongo_error": str(e)}), 200

    # ================= PROJECTS JSON API =================

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

    # ================= DEWEY PROXY API (with cache) =================

    @app.get("/api/top10companies")
    def api_top10companies():
        """
        Returns Top 10 brands (optionally filtered by ?year=) for the Top Brands UI.

        Data source priority:
          1) If DEWEY_API_URL is set → proxy to external Dewey microservice (optional Authorization header via DEWEY_API_KEY)
          2) Else → fallback to local CSV at DEWEY_CSV_PATH (default: data/stg_daily_spend_top10.csv)
        """
        year = request.args.get("year")  # optional

        dewey_url = os.getenv("DEWEY_API_URL")
        dewey_key = os.getenv("DEWEY_API_KEY")

        # simple in-memory cache per dyno
        cache_key = f"proxy:{year or 'all'}"
        now = time.time()
        if _dewey_cache["key"] == cache_key and (now - _dewey_cache["ts"] < _CACHE_TTL_SEC):
            return jsonify({"success": True, "data": _dewey_cache["payload"]}), 200

        # Prefer external Dewey API
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
                    return jsonify({"success": False, "message": "Unexpected Dewey API shape"}), 502

                # normalize
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
                return jsonify({"success": True, "data": data}), 200

            except requests.RequestException as e:
                return jsonify({"success": False, "message": f"Dewey API error: {e}"}), 502

        # CSV fallback
        try:
            data = _load_dewey_csv(year)
            _dewey_cache.update({"payload": data, "key": cache_key, "ts": now})
            return jsonify({"success": True, "data": data}), 200
        except Exception as e:
            return jsonify({"success": False, "message": f"CSV fallback error: {e}"}), 500

    return app

# Gunicorn / Heroku
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
