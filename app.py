# app.py — Projects Microservice

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from projectdb import ProjectDB
from project import Project


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # ===== MongoDB initialization =====
    project_db = ProjectDB(
        db_name=app.config.get("MONGO_DB", "projects_db"),
        uri=app.config.get("MONGO_URI"),   # Atlas / cloud connection
        host=app.config.get("MONGO_HOST", "localhost"),
        port=app.config.get("MONGO_PORT", 27017),
        username=app.config.get("MONGO_INITDB_ROOT_USERNAME"),
        password=app.config.get("MONGO_INITDB_ROOT_PASSWORD"),
        auth_source=app.config.get("MONGO_AUTHSOURCE", "admin"),
    )

    # ============== HEALTHCHECK ==============
    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "projects"}), 200

    @app.get("/")
    def root():
        return jsonify({
            "message": "Projects microservice is running",
            "endpoints": ["/health", "/projects"]
        }), 200

    # ============== PROJECT CRUD API ==============

    @app.post("/projects")
    def create_project():
        data = request.get_json(force=True) or {}

        project_id = (data.get("project_id") or "").strip()
        project_name = (data.get("project_name") or "").strip()

        if not project_id or not project_name:
            return jsonify({
                "success": False,
                "message": "project_id and project_name are required"
            }), 400

        # Default members_list
        data.setdefault("members_list", [])

        project_obj = Project.from_dict(data)
        created = project_db.create_project(project_obj.to_dict())
        return jsonify({"success": True, "project": created}), 201

    @app.get("/projects")
    def list_projects():
        projects = project_db.list_projects()
        return jsonify({"success": True, "projects": projects}), 200

    @app.get("/projects/<project_id>")
    def get_project(project_id: str):
        proj = project_db.get_project(project_id)
        if not proj:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "project": proj}), 200

    @app.put("/projects/<project_id>")
    def update_project(project_id: str):
        updates = request.get_json(force=True) or {}
        updates.pop("project_id", None)

        updated = project_db.update_project(project_id, updates)
        if not updated:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "project": updated}), 200

    @app.delete("/projects/<project_id>")
    def delete_project(project_id: str):
        deleted = project_db.delete_project(project_id)
        if not deleted:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "message": "Project deleted"}), 200

    return app


# Only used locally (Heroku uses gunicorn)
if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
