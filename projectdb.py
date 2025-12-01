from typing import Optional, Dict, Any, List
from pymongo import MongoClient
from flask import current_app

class ProjectDB:
    def __init__(self,
                 host: str,
                 port: int,
                 db_name: str,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 auth_source: str = "admin"):
        """
        If MONGO_URI is set in config, use that.
        Otherwise, fall back to host/port auth (for local Docker).
        """
        uri = current_app.config.get("MONGO_URI")

        if uri:
            # Atlas / Heroku mode
            self.client = MongoClient(uri)
            self.db = self.client[current_app.config.get("MONGO_DB", db_name)]
        else:
            # Local mode
            if username and password:
                self.client = MongoClient(
                    host=host,
                    port=port,
                    username=username,
                    password=password,
                    authSource=auth_source,
                )
            else:
                self.client = MongoClient(host=host, port=port)
            self.db = self.client[db_name]

        self.projects = self.db["projects"]

    @staticmethod
    def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return doc
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        res = self.projects.insert_one(project_data)
        created = self.projects.find_one({"_id": res.inserted_id})
        return self._normalize(created)

    def list_projects(self) -> List[Dict[str, Any]]:
        return [self._normalize(d) for d in self.projects.find({})]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        doc = self.projects.find_one({"project_id": project_id})
        return self._normalize(doc) if doc else None

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.projects.update_one({"project_id": project_id}, {"$set": updates})
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        res = self.projects.delete_one({"project_id": project_id})
        return res.deleted_count > 0
