# projectdb.py – Mongo wrapper for Projects

from typing import Any, Dict, List, Optional
from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from bson.objectid import ObjectId
from pymongo import ReturnDocument


class ProjectDB:
    def __init__(
        self,
        uri: Optional[str] = None,
        dbname: Optional[str] = None,
        host: str = "localhost",
        port: int = 27017,
        db_name: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
    ):
        """
        You can initialize either with:
          - uri + dbname (Atlas / connection string)
          - or host/port/db_name (+ optional username/password)
        """
        if dbname is None and db_name is not None:
            dbname = db_name
        if dbname is None:
            dbname = "projects_db"

        if uri:
            # Simple URI mode (Atlas etc.)
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        else:
            # Host/port mode (Docker/local)
            conn_kwargs: Dict[str, Any] = {
                "host": host,
                "port": port,
                "serverSelectionTimeoutMS": 5000,
            }
            if username and password:
                conn_kwargs.update(
                    {
                        "username": username,
                        "password": password,
                        "authSource": auth_source,
                    }
                )
            self.client = MongoClient(**conn_kwargs)

        self.db = self.client[dbname]
        self.collection: Collection = self.db["projects"]

        # Index for fast lookups and uniqueness
        try:
            self.collection.create_index(
                [("project_id", ASCENDING)], unique=True, name="idx_project_id_unique"
            )
        except PyMongoError as e:
            print("[ProjectDB] Warning: could not create index:", e)

    # ---------- Helpers ----------

    @staticmethod
    def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert Mongo _id to string and ensure core fields exist.
        """
        if not doc:
            return doc
        out = dict(doc)
        if isinstance(out.get("_id"), ObjectId):
            out["_id"] = str(out["_id"])

        # Ensure these keys exist
        out.setdefault("project_id", "")
        out.setdefault("project_name", "")
        out.setdefault("project_desc", "")
        out.setdefault("members_list", [])
        out.setdefault("num_of_hardware_sets", 0)
        out.setdefault("hardware_set_id", [])

        return out

    # ---------- CRUD ----------

    def create_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert project; if duplicate project_id, raises error.
        """
        try:
            # Up-front ensure lists exist
            project.setdefault("members_list", [])
            project.setdefault("hardware_set_id", [])
            project.setdefault("num_of_hardware_sets", len(project["hardware_set_id"]))

            res = self.collection.insert_one(project)
            inserted = self.collection.find_one({"_id": res.inserted_id})
            return self._normalize(inserted)
        except PyMongoError as e:
            print("[ProjectDB] create_project error:", e)
            raise

    def list_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            cursor = self.collection.find({})
            if limit is not None:
                cursor = cursor.limit(limit)
            return [self._normalize(doc) for doc in cursor]
        except PyMongoError as e:
            print("[ProjectDB] list_projects error:", e)
            raise

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        try:
            doc = self.collection.find_one({"project_id": project_id})
            return self._normalize(doc) if doc else None
        except PyMongoError as e:
            print("[ProjectDB] get_project error:", e)
            raise

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            # If hardware_set_id changed, recalc num_of_hardware_sets when not explicitly provided
            if "hardware_set_id" in updates and "num_of_hardware_sets" not in updates:
                hw = updates["hardware_set_id"]
                if isinstance(hw, list):
                    updates["num_of_hardware_sets"] = len(hw)

            updated = self.collection.find_one_and_update(
                {"project_id": project_id},
                {"$set": updates},
                return_document=ReturnDocument.AFTER,
            )
            return self._normalize(updated) if updated else None
        except PyMongoError as e:
            print("[ProjectDB] update_project error:", e)
            raise

    def delete_project(self, project_id: str) -> bool:
        try:
            res = self.collection.delete_one({"project_id": project_id})
            return res.deleted_count > 0
        except PyMongoError as e:
            print("[ProjectDB] delete_project error:", e)
            raise
