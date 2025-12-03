# app.py
import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import Config
from projectdb import ProjectDB
from project import Project  # unchanged if you have it; see note below

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(Config)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # ---- Mongo Projects DB ----
    project_db = ProjectDB(
        host=app.config.get("MONGO_HOST", "localhost"),
        port=app.config.get("MONGO_PORT", 27017),
        db_name=app.config.get("MONGO_DB", "projects_db"),
        username=app.config.get("MONGO_INITDB_ROOT_USERNAME"),
        password=app.config.get("MONGO_INITDB_ROOT_PASSWORD"),
        auth_source=app.config.get("MONGO_AUTHSOURCE", "admin"),
    )

    # ---- UI PAGES ----
    @app.get("/")
    def root():
        return render_template("index.html")

    @app.get("/top10companies")
    def top10_page():
        # Page reads ?state=XX&category=YYY from the query string
        return render_template("top10companies.html")

    # ---- HEALTH ----
    @app.get("/health")
    def health():
        try:
            _ = project_db.list_projects(limit=1)
            return jsonify({"status": "ok", "service": "projects", "mongo": "reachable"}), 200
        except Exception as e:
            return jsonify({"status": "degraded", "service": "projects", "mongo_error": str(e)}), 200

    # ---- PROJECTS API ----
    @app.post("/projects")
    def create_project_route():
        data = request.get_json(force=True) or {}
        project_id   = (data.get("project_id")   or "").strip()
        project_name = (data.get("project_name") or "").strip()
        project_desc = (data.get("project_desc") or "").strip()

        # NEW (optional) filters persisted with the project
        state    = (data.get("state")    or "").strip()   # e.g., 'TX' or ''
        category = (data.get("category") or "").strip()   # e.g., 'Grocery' or ''

        if not project_id or not project_name:
            return jsonify({"success": False, "message": "project_id and project_name are required"}), 400

        data.setdefault("members_list", [])
        data.setdefault("hardware_set_id", [])
        # Normalize optional numeric
        try:
            data["num_of_hardware_sets"] = int(data.get("num_of_hardware_sets") or 0)
        except ValueError:
            data["num_of_hardware_sets"] = 0

        # Attach our new fields (no schema change elsewhere needed)
        data["state"] = state
        data["category"] = category

        # If you use a Project model:
        project_obj = Project.from_dict(data) if hasattr(Project, "from_dict") else data
        created = project_db.create_project(project_obj if isinstance(project_obj, dict) else project_obj.to_dict())
        return jsonify({"success": True, "project": created}), 201

    @app.get("/projects")
    def list_projects_route():
        limit_param = request.args.get("limit")
        limit = int(limit_param) if limit_param else None
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
        # never allow project_id replacement
        updates.pop("project_id", None)
        # keep numeric safe
        if "num_of_hardware_sets" in updates:
            try:
                updates["num_of_hardware_sets"] = int(updates["num_of_hardware_sets"])
            except (TypeError, ValueError):
                updates["num_of_hardware_sets"] = 0
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

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    app = create_app()
