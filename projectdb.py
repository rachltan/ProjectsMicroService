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
                tls=True
            )
        else:
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

        try:
            self.projects.create_index([("project_id", ASCENDING)], unique=True)
        except Exception:
            pass

    def ping(self) -> Dict[str, Any]:
        return self.client.admin.command("ping")

    def create_project(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        # Normalize canonical fields you use in the UI
        doc.setdefault("project_desc", "")
        doc.setdefault("hardware_set_id", [])
        doc.setdefault("num_of_hardware_sets", 0)
        doc.setdefault("target_state", "")
        doc.setdefault("target_category", "")

        try:
            self.projects.insert_one(doc)
        except DuplicateKeyError:
            raise ValueError(f"project_id '{doc.get('project_id')}' already exists")

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
