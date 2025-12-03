# projectdb.py
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, ASCENDING
from bson.objectid import ObjectId

class ProjectDB:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 27017,
        db_name: str = "projects_db",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
        uri: Optional[str] = None,
    ):
        if uri:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        else:
            self.client = MongoClient(
                host=host,
                port=int(port),
                username=username,
                password=password,
                authSource=auth_source,
                serverSelectionTimeoutMS=5000,
            )

        self.db = self.client[db_name]
        self.projects = self.db["projects"]
        # Ensure unique project_id
        self.projects.create_index([("project_id", ASCENDING)], unique=True)

    # -- helpers --
    def _normalize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        if not doc:
            return {}
        doc["_id"] = str(doc.get("_id"))
        # Ensure optional fields exist for front-end
        doc.setdefault("project_desc", "")
        doc.setdefault("members_list", [])
        doc.setdefault("hardware_set_id", [])
        doc.setdefault("num_of_hardware_sets", 0)
        doc.setdefault("state", "")     # NEW
        doc.setdefault("category", "")  # NEW
        return doc

    # -- CRUD --
    def create_project(self, project_doc: Dict[str, Any]) -> Dict[str, Any]:
        # only allow known fields; ignore surprises
        allowed = {
            "project_id",
            "project_name",
            "project_desc",
            "members_list",
            "hardware_set_id",
            "num_of_hardware_sets",
            "state",     # NEW
            "category",  # NEW
        }
        body = {k: v for k, v in project_doc.items() if k in allowed}
        res = self.projects.insert_one(body)
        created = self.projects.find_one({"_id": res.inserted_id})
        return self._normalize(created)

    def list_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        cursor = self.projects.find({})
        if limit:
            cursor = cursor.limit(int(limit))
        return [self._normalize(d) for d in cursor]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        doc = self.projects.find_one({"project_id": project_id})
        return self._normalize(doc) if doc else None

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        allowed_updates = {
            "project_name",
            "project_desc",
            "members_list",
            "hardware_set_id",
            "num_of_hardware_sets",
            "state",     # NEW
            "category",  # NEW
        }
        body = {k: v for k, v in updates.items() if k in allowed_updates}
        res = self.projects.find_one_and_update(
            {"project_id": project_id},
            {"$set": body},
            return_document=True
        )
        return self._normalize(res) if res else None

    def delete_project(self, project_id: str) -> bool:
        res = self.projects.delete_one({"project_id": project_id})
        return res.deleted_count == 1
