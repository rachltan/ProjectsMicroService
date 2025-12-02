import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import Config
from projectdb import ProjectDB
from project import Project


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(Config)

    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # ---- Mongo wiring ----
    mongo_uri = app.config.get("MONGO_URI")
    db_name = app.config.get("MONGO_DB", "projects_db")

    if mongo_uri:
        print(f"[info] Using Mongo URI: {mongo_uri}")
        project_db = ProjectDB(uri=mongo_uri, db_name=db_name)
    else:
        print("[info] Using host/port Mongo config")
        project_db = ProjectDB(
            host=app.config.get("MONGO_HOST", "localhost"),
            port=app.config.get("MONGO_PORT", 27017),
            db_name=db_name,
            username=app.config.get("MONGO_INITDB_ROOT_USERNAME"),
            password=app.config.get("MONGO_INITDB_ROOT_PASSWORD"),
            auth_source=app.config.get("MONGO_AUTHSOURCE", "admin"),
        )

    # ========= UI =========
    @app.get("/")
    def root():
        return render_template("index.html")

    # ========= Health =========
    @app.get("/health")
    def health():
        try:
            _ = project_db.list_projects(limit=1)
            return jsonify({"status": "ok", "service": "projects", "mongo": "reachable"}), 200
        except Exception as e:
            return jsonify({"status": "degraded", "service": "projects", "error": str(e)}), 200

    # ========= API: list =========
    @app.get("/projects")
    def list_projects_route():
        try:
            projects = project_db.list_projects()
            return jsonify({"success": True, "projects": projects}), 200
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    # ========= API: create =========
    @app.post("/projects")
    def create_project_route():
        data = request.get_json(force=True) or {}

        project_id = (data.get("project_id") or "").strip()
        project_name = (data.get("project_name") or "").strip()
        project_desc = (data.get("project_desc") or "").strip()

        if not project_id or not project_name:
            return jsonify({
                "success": False,
                "message": "project_id and project_name are required"
            }), 400

        # --- normalize members_list ---
        members_raw = data.get("members_list")
        if isinstance(members_raw, str):
            members_list = [m.strip() for m in members_raw.split(",") if m.strip()]
        elif isinstance(members_raw, list):
            members_list = members_raw
        else:
            members_list = []

        # --- normalize hardware_set_id ---
        hardware_raw = data.get("hardware_set_id")
        if isinstance(hardware_raw, str):
            hardware_set_id = [h.strip() for h in hardware_raw.split(",") if h.strip()]
        elif isinstance(hardware_raw, list):
            hardware_set_id = hardware_raw
        else:
            hardware_set_id = []

        # --- normalize num_of_hardware_sets ---
        num_raw = data.get("num_of_hardware_sets", 0)
        try:
            num_of_hardware_sets = int(num_raw)
        except (TypeError, ValueError):
            num_of_hardware_sets = 0

        project_dict = {
            "project_id": project_id,
            "project_name": project_name,
            "project_desc": project_desc,
            "members_list": members_list,
            "hardware_set_id": hardware_set_id,
            "num_of_hardware_sets": num_of_hardware_sets,
        }

        # if you want to keep using the Project model:
        project_obj = Project.from_dict(project_dict)
        created = project_db.create_project(project_obj.to_dict())

        return jsonify({"success": True, "project": created}), 201

    # ========= API: get one =========
    @app.get("/projects/<project_id>")
    def get_project_route(project_id: str):
        proj = project_db.get_project(project_id)
        if not proj:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "project": proj}), 200

    # ========= API: update =========
    @app.put("/projects/<project_id>")
    def update_project_route(project_id: str):
        updates = request.get_json(force=True) or {}
        updates.pop("project_id", None)  # don't let ID change
        updated = project_db.update_project(project_id, updates)
        if not updated:
            return jsonify({"success": False, "message": "Project not found"}), 404
        return jsonify({"success": True, "project": updated}), 200

    # ========= API: delete =========
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
