import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import Config
from projectdb import ProjectDB
from project import Project

def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",  # so /templates/index.html works
        static_folder="static",      # in case you add JS/CSS later
    )
    app.config.from_object(Config)

    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # Mongo Projects DB init (same as your original)
    project_db = ProjectDB(
        host=app.config.get("MONGO_HOST", "localhost"),
        port=app.config.get("MONGO_PORT", 27017),
        db_name=app.config.get("MONGO_DB", "projects_db"),
        username=app.config.get("MONGO_INITDB_ROOT_USERNAME"),
        password=app.config.get("MONGO_INITDB_ROOT_PASSWORD"),
        auth_source=app.config.get("MONGO_AUTHSOURCE", "admin"),
    )

    # ============== UI PAGE ==============
    @app.get("/")
    def root():
        """
        Render the Projects dashboard UI (HTML).
        The JS inside index.html will call /projects.
        """
        return render_template("index.html")

    # ============== HEALTH ==============
    @app.get("/health")
    def health():
        # You can make this smarter later (e.g., ping DB)
        return jsonify({"status": "ok", "service": "projects"}), 200

    # ============== PROJECTS JSON API (your existing CRUD) ==============

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

        # default members_list if missing
        data.setdefault("members_list", [])
        # Let your Project model handle normalization
        project_obj = Project.from_dict(data)
        created = project_db.create_project(project_obj.to_dict())
        return jsonify({"success": True, "project": created}), 201

    @app.get("/projects")
    def list_projects_route():
        projects = project_db.list_projects()
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

    return app

if __name__ == "__main__":
    app = create_app()
    # keep Heroku-compatible PORT env but default to your old 5003
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    # for gunicorn: gunicorn "app:create_app()"
    app = create_app()
