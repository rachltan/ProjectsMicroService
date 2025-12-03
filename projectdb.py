import os
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import DuplicateKeyError

class ProjectDB:
    """
    Works with either:
      - Atlas SRV URI: ProjectDB(uri=..., dbname="projects_db")
      - Host/port:     ProjectDB(host=..., port=..., dbname="projects_db", username=..., password=..., auth_source=...)
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        dbname: str = "projects_db",
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
        connect_timeout_ms: int = 10000,
        server_select_timeout_ms: int = 10000,
    ):
        self.dbname = dbname

        if uri:
            self.client = MongoClient(
                uri,
                connectTimeoutMS=connect_timeout_ms,
                serverSelectionTimeoutMS=server_select_timeout_ms,
                tls=True  # harmless if implied by SRV
            )
        else:
            # fallback to classic host/port (useful for local dev/docker)
            host = host or os.getenv("MONGO_HOST", "localhost")
            port = port or int(os.getenv("MONGO_PORT", "27017"))
            username = username or os.getenv("MONGO_INITDB_ROOT_USERNAME")
            password = password or os.getenv("MONGO_INITDB_ROOT_PASSWORD")
            auth_source = auth_source or os.getenv("MONGO_AUTHSOURCE", "admin")

            self.client = MongoClient(
                host=host,
                port=port,
                username=username,
                password=password,
                authSource=auth_source,
                connectTimeoutMS=connect_timeout_ms,
                serverSelectionTimeoutMS=server_select_timeout_ms,
            )

        self.db = self.client[self.dbname]
        self.projects = self.db["projects"]

        # Ensure a unique index on project_id
        try:
            self.projects.create_index([("project_id", ASCENDING)], unique=True)
        except Exception:
            # If server selection fails here, app.py /health will surface it
            pass

    # Quick connectivity check for /health
    def ping(self) -> Dict[str, Any]:
        return self.client.admin.command("ping")

    # CRUD methods
    def create_project(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        # Normalize canonical fields you use in the UI
        doc.setdefault("project_desc", "")
        doc.setdefault("hardware_set_id", [])         # future-proof for your popup
        doc.setdefault("num_of_hardware_sets", 0)     # shown in details

        try:
            self.projects.insert_one(doc)
        except DuplicateKeyError:
            # Replace with a friendlier message
            raise ValueError(f"project_id '{doc.get('project_id')}' already exists")

        # return created (without _id for simpler frontend)
        out = self.projects.find_one({"project_id": doc["project_id"]}, {"_id": False})
        return out or doc

    def list_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.projects.find({}, {"_id": False}).sort("project_id", ASCENDING)
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.projects.find_one({"project_id": project_id}, {"_id": False})

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.projects.update_one({"project_id": project_id}, {"$set": updates})
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        res = self.projects.delete_one({"project_id": project_id})
        return res.deleted_count == 1
