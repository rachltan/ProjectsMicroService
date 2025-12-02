# projectdb.py
import os
from typing import Any, Dict, List, Optional

from pymongo import MongoClient
from bson.objectid import ObjectId


class ProjectDB:
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
        uri: Optional[str] = None,
    ) -> None:
        """
        Initialize ProjectDB.

        Either:
          - pass a full Mongo URI via `uri`, or
          - pass host/port/username/password/etc.

        This class DOES NOT touch `current_app`, so it works fine
        during app factory creation and on Heroku.
        """
        if uri:
            # URI mode (Atlas / connection string)
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            dbname = db_name or os.getenv("MONGO_DB", "projects_db")
        else:
            # host/port mode (Docker, local)
            host = host or os.getenv("MONGO_HOST", "localhost")
            port = int(port or os.getenv("MONGO_PORT", 27017))
            dbname = db_name or os.getenv("MONGO_DB", "projects_db")
            username = username or os.getenv("MONGO_INITDB_ROOT_USERNAME")
            password = password or os.getenv("MONGO_INITDB_ROOT_PASSWORD")
            auth_source = auth_source or os.getenv("MONGO_AUTHSOURCE", "admin")

            self.client = MongoClient(
                host=host,
                port=port,
                username=username,
                password=password,
                authSource=auth_source,
                serverSelectionTimeoutMS=5000,
            )

        self.db = self.client[dbname]
        self.projects = self.db["projects"]

    # ------------ helpers ------------

    def _normalize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Mongo _id to string and return a clean dict."""
        if not doc:
            return doc
        doc = dict(doc)
        _id = doc.get("_id")
        if isinstance(_id, ObjectId):
            doc["_id"] = str(_id)
        return doc

    # ------------ CRUD ------------

    def create_project(self, project_doc: Dict[str, Any]) -> Dict[str, Any]:
        res = self.projects.insert_one(project_doc)
        created = self.projects.find_one({"_id": res.inserted_id})
        return self._normalize(created)

    def list_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.projects.find({})
        if limit:
            cursor = cursor.limit(limit)
        return [self._normalize(d) for d in cursor]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        doc = self.projects.find_one({"project_id": project_id})
        if not doc:
            return None
        return self._normalize(doc)

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        res = self.projects.find_one_and_update(
            {"project_id": project_id},
            {"$set": updates},
            return_document=True,
        )
        if not res:
            return None
        return self._normalize(res)

    def delete_project(self, project_id: str) -> bool:
        res = self.projects.delete_one({"project_id": project_id})
        return res.deleted_count > 0
