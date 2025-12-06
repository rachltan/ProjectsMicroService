# app.py – Projects Microservice

import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from config import Config
from projectdb import ProjectDB
from project import Project


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",  # templates/index.html
        static_folder="static",       # if you add JS/CSS later
    )
    app.config.from_object(Config)

    # CORS (so you can call this service from other frontends if needed)
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

    # ----- Mongo / ProjectDB init -----
    # Prefer full Mongo URI if provided (Atlas, etc.)
    mongo_uri = app.config.get("MONGO_URI")
    dbname = app.config.get("MONGO_DB", "projects_db")

    if mongo_uri:
        print(f"[projects] Using MONGO_URI (db={dbname})")
        project_db = ProjectDB(uri=mongo_uri, dbname=dbname)
    else:
        print("[projects] Using host/port Mongo connection")
        project_db = ProjectDB(
            host=app.config.get("MONGO_HOST", "localhost"),
            port=app.config.get("MONGO_PORT", 27017),
            db_name=dbname,
            username=app.config.get("MONGO_INITDB_ROOT_USERNAME"),
            password=app.config.get("MONGO_INITDB_ROOT_PASSWORD"),
            auth_source=app.config.get("MONGO_AUTHSOURCE", "admin"),
        )

    # ================= UI PAGE =================
    @app.get("/")
    def root():
        """
        Render the Projects dashboard UI.
        The JS inside templates/index.html calls /projects and /projects/<id>.
        """
        return render_template("index.html")

    # ================= HEALTH ==================
    @app.get("/health")
    def health():
        """
        Simple health check + very small DB call.
        """
        try:
            sample = project_db.list_projects(limit=1)
            return jsonify({"status": "ok", "mongo": "reachable", "sample_count": len(sample)}), 200
        except Exception as e:
            return jsonify({"status": "degraded", "mongo_error": str(e)}), 200

    # ============ PROJECTS JSON API ============

    @app.post("/projects")
    def create_project_route():
        """
        Create a new project.

        Expected JSON (min):
        {
          "project_id": "P1",
          "project_name": "My Project",
          "project_desc": "Something..."
        }

        Optional fields (you can pass now or later):
        - members_list: ["user1", "user2"] or "user1,user2"
        - num_of_hardware_sets: 0
        - hardware_set_id: ["HW1","HW2"] or "HW1,HW2"
        """
        try:
            data = request.get_json(force=True) or {}

            project_id = (data.get("project_id") or "").strip()
            project_name = (data.get("project_name") or "").strip()
            project_desc = (data.get("project_desc") or "").strip()

            if not project_id or not project_name:
                return jsonify({
                    "success": False,
                    "message": "project_id and project_name are required"
                }), 400

            # Optional fields – allow both comma-separated string and list
            raw_members = data.get("members_list") or []
            raw_hw = data.get("hardware_set_id") or []
            num_hw = data.get("num_of_hardware_sets")

            # Normalize comma-separated → list
            if isinstance(raw_members, str):
                members_list = [m.strip() for m in raw_members.split(",") if m.strip()]
            else:
                members_list = list(raw_members)

            if isinstance(raw_hw, str):
                hardware_set_id = [h.strip() for h in raw_hw.split(",") if h.strip()]
            else:
                hardware_set_id = list(raw_hw)

            try:
                num_of_hardware_sets = int(num_hw) if num_hw is not None else len(hardware_set_id)
            except (TypeError, ValueError):
                num_of_hardware_sets = len(hardware_set_id)

            project_obj = Project(
                project_id=project_id,
                project_name=project_name,
                project_desc=project_desc,
                members_list=members_list,
                num_of_hardware_sets=num_of_hardware_sets,
                hardware_set_id=hardware_set_id,
            )

            created = project_db.create_project(project_obj.to_dict())
            return jsonify({"success": True, "project": created}), 201

        except Exception as e:
            print("[projects] create_project_route error:", e)
            return jsonify({"success": False, "message": str(e)}), 500

    @app.get("/projects")
    def list_projects_route():
        """
        List projects (optionally ?limit=10).
        """
        try:
            limit_param = request.args.get("limit")
            limit = int(limit_param) if limit_param else None
            projects = project_db.list_projects(limit=limit)
            return jsonify({"success": True, "projects": projects}), 200
        except Exception as e:
            print("[projects] list_projects_route error:", e)
            return jsonify({"success": False, "message": str(e)}), 500

    @app.get("/projects/<project_id>")
    def get_project_route(project_id: str):
        """
        Get a single project by project_id.
        """
        try:
            proj = project_db.get_project(project_id)
            if not proj:
                return jsonify({"success": False, "message": "Project not found"}), 404
            return jsonify({"success": True, "project": proj}), 200
        except Exception as e:
            print("[projects] get_project_route error:", e)
            return jsonify({"success": False, "message": str(e)}), 500

    @app.put("/projects/<project_id>")
    def update_project_route(project_id: str):
        """
        Update an existing project. project_id in the body is ignored.
        Accepts the same fields as create_project_route.
        """
        try:
            updates = request.get_json(force=True) or {}
            updates.pop("project_id", None)  # don't let clients change ID

            # Normalize comma-separated fields if present
            if "members_list" in updates:
                if isinstance(updates["members_list"], str):
                    updates["members_list"] = [
                        m.strip() for m in updates["members_list"].split(",") if m.strip()
                    ]

            if "hardware_set_id" in updates:
                if isinstance(updates["hardware_set_id"], str):
                    updates["hardware_set_id"] = [
                        h.strip() for h in updates["hardware_set_id"].split(",") if h.strip()
                    ]

            updated = project_db.update_project(project_id, updates)
            if not updated:
                return jsonify({"success": False, "message": "Project not found"}), 404
            return jsonify({"success": True, "project": updated}), 200

        except Exception as e:
            print("[projects] update_project_route error:", e)
            return jsonify({"success": False, "message": str(e)}), 500

    @app.delete("/projects/<project_id>")
    def delete_project_route(project_id: str):
        """
        Delete project by project_id.
        """
        try:
            deleted = project_db.delete_project(project_id)
            if not deleted:
                return jsonify({"success": False, "message": "Project not found"}), 404
            return jsonify({"success": True, "message": "Project deleted"}), 200
        except Exception as e:
            print("[projects] delete_project_route error:", e)
            return jsonify({"success": False, "message": str(e)}), 500

    return app


# Local run: python app.py
if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", "5003"))  # Heroku overrides PORT
    app.run(host="0.0.0.0", port=port, debug=False)
else:
    # For gunicorn "web: gunicorn app:app"
    app = create_app()
