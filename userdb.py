from typing import Optional, Dict, Any
from pymongo import MongoClient, ASCENDING
from pymongo.errors import OperationFailure

# SHIFT value for encryption (matching old code: encrypt_user(4))
SHIFT = 4
#For both docker and mongo URI
class UserDB:
    def __init__(
        self,
        dbname: str,
        mongo_uri: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: Optional[str] = None,
        users_collection: str = "users",
        unique_field: str = "username", 
        ):  
        self.unique_field = unique_field

        if mongo_uri:
            # URI mode (Atlas, or any SRV/standard URI)
            self.client = MongoClient(mongo_uri)
        else:
            # Host/port mode (Docker Compose local Mongo with auth)
            kwargs = {}
            if username:
                kwargs["username"] = username
            if password:
                kwargs["password"] = password
            if auth_source:
                kwargs["authSource"] = auth_source

            self.client = MongoClient(host=host or "localhost", port=port or 27017, **kwargs)

        self.db = self.client[dbname]
        self.users = self.db[users_collection]

        # Create a unique index on the chosen login identifier.
        # Do not crash the app if duplicates already exist—log and continue.
        try:
            self.users.create_index([(self.unique_field, ASCENDING)], unique=True, name=f"{self.unique_field}_unique")
        except OperationFailure as e:
            print(f"⚠️  Warning: Unique index on '{self.unique_field}' could not be created: {e}")
            print("   App will continue, but duplicates may exist in the collection.")
        except Exception as e:
            print(f"⚠️  Warning: Index creation issue: {e}")
    @staticmethod
    def check_outlier(char_code):
        """Check if character code is outside printable ASCII range"""
        return char_code < 34 or char_code > 126

    @staticmethod
    def encrypt_text(text: str, shift: int) -> str:
        """Encrypt text by shifting ASCII values"""
        new_txt = []
        for ch in text:
            new_ch = ord(ch) + shift
            if not UserDB.check_outlier(new_ch):
                new_txt.append(chr(new_ch))
            else:
                new_txt.append(ch)
        return ''.join(new_txt)

    @staticmethod
    def decrypt_text(text: str, shift: int) -> str:
        """Decrypt text by shifting ASCII values in reverse"""
        return UserDB.encrypt_text(text, -shift)

    @staticmethod
    def _public_user(u):
        """Return user data without encrypted fields"""
        # Decrypt username before returning
        decrypted_username = u["username"]
        return {
            "_id": str(u["_id"]),
            "username": decrypted_username,
        }

    def create_user(self, username: str, password: str):
        """Create a new user with encrypted username and password"""
        # Encrypt both username and password before storing
        encrypted_username = username
        encrypted_password = self.encrypt_text(password, SHIFT)
        
        doc = {
            "username": encrypted_username,
            "password": encrypted_password,
        }
        res = self.users.insert_one(doc)
        created = self.users.find_one({"_id": res.inserted_id})
        return self._public_user(created)

    def find_by_username(self, username: str):
        """Find user by username (searches encrypted username)"""
        # Encrypt username to search in DB
        encrypted_username = username
        return self.users.find_one({"username": encrypted_username})

    def verify_user(self, username: str, password: str):
        """Verify username and password match"""
        u = self.find_by_username(username)
        if not u:
            return None
        
        stored_pw = u.get("password", "")
        # Decrypt stored password and compare
        decrypted_pw = self.decrypt_text(stored_pw, SHIFT)
        
        if decrypted_pw != password:
            return None
        
        return self._public_user(u)