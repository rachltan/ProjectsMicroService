import os
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
    mongo_uri = os.getenv("MONGO_URI")           # e.g. mongodb+srv://...
    mongo_db  = os.getenv("MONGO_DB", "projects_db")

    # Instantiate DB (note: param name is dbname, not db_name)
    project_db = ProjectDB(
        uri=mongo_uri,
        dbname=mongo_db,
        # optional: tweak timeouts if your cluster is slow
        connect_timeout_ms=15000,
        server_select_timeout_ms=15000,
    )

    # ============== UI PAGE ==============
    @app.get("/")
    def root():
        # Renders templates/index.html (your Projects UI)
        return render_template("index.html")

    # ============== HEALTH ==============
    @app.get("/health")
    def health():
        try:
            _ = project_db.ping()
            return jsonify({"status": "ok", "mongo": "reachable"}), 200
        except Exception as e:
            return jsonify({"status": "degraded", "mongo_error": str(e)}), 200

    # ============== PROJECTS JSON API ==============

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

        # Normalize fields
        payload = {
            "project_id": project_id,
            "project_name": project_name,
            "project_desc": (data.get("project_desc") or "").strip(),
        }

        # If your Project model does extra normalization, you can keep it
        proj_obj = Project.from_dict(payload) if hasattr(Project, "from_dict") else payload
        created = project_db.create_project(
            proj_obj.to_dict() if hasattr(proj_obj, "to_dict") else proj_obj
        )
        return jsonify({"success": True, "project": created}), 201

    @app.get("/projects")
    def list_projects_route():
        # Optional ?limit=
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
        updates.pop("project_id", None)  # don't allow id change
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

# Gunicorn
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5003"))
    app.run(host="0.0.0.0", port=port, debug=False)
