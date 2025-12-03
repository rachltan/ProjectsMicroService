# projectdb.py
import os
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError

class ProjectDB:
    """
    Connects via MONGO_URI if provided; otherwise uses host/port (for local dev/docker).
    On Heroku you MUST set MONGO_URI to your Atlas connection string.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        dbname: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: Optional[str] = "admin",
        connect_timeout_ms: int = 5000,
        server_selection_timeout_ms: int = 5000,
    ):
        uri = uri or os.getenv("MONGO_URI")
        dbname = dbname or os.getenv("MONGO_DB", "projects_db")

        if uri:
            # Atlas / SRV path
            self.client = MongoClient(
                uri,
                connectTimeoutMS=connect_timeout_ms,
                serverSelectionTimeoutMS=server_selection_timeout_ms,
                tls=True,  # harmless if already in URI
            )
        else:
            # Local/dev path (NOT for Heroku)
            host = host or os.getenv("MONGO_HOST", "localhost")
            port = port or int(os.getenv("MONGO_PORT", "27017"))
            username = username or os.getenv("MONGO_INITDB_ROOT_USERNAME")
            password = password or os.getenv("MONGO_INITDB_ROOT_PASSWORD")
            auth_source = auth_source or os.getenv("MONGO_AUTHSOURCE", "admin")

            kwargs = dict(
                host=host,
                port=port,
                connectTimeoutMS=connect_timeout_ms,
                serverSelectionTimeoutMS=server_selection_timeout_ms,
            )
            if username and password:
                kwargs.update(username=username, password=password, authSource=auth_source)

            self.client = MongoClient(**kwargs)

        self.db = self.client[dbname]
        self.projects = self.db["projects"]

        # Create indexes lazily; if Mongo isn’t reachable this will raise quickly and clearly.
        try:
            self.projects.create_index([("project_id", ASCENDING)], unique=True, name="ux_project_id")
        except PyMongoError as e:
            # Surface a clean message so Heroku logs make the cause obvious
            raise RuntimeError(f"Mongo connection/indexing failed: {e}") from e

    @staticmethod
    def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return {}
        doc = dict(doc)
        # Convert ObjectId -> str
        _id = doc.get("_id")
        if _id is not None:
            doc["_id"] = str(_id)
        return doc

    def create_project(self, project_doc: Dict[str, Any]) -> Dict[str, Any]:
        self.projects.insert_one(project_doc)
        return self._normalize(self.projects.find_one({"project_id": project_doc["project_id"]}))

    def list_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.projects.find({})
        if limit:
            cursor = cursor.limit(limit)
        return [self._normalize(d) for d in cursor]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        doc = self.projects.find_one({"project_id": project_id})
        return self._normalize(doc) if doc else None

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.projects.update_one({"project_id": project_id}, {"$set": updates})
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        res = self.projects.delete_one({"project_id": project_id})
        return res.deleted_count > 0
