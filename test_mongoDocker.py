import os
import sys
import time
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, OperationFailure

def build_client():
    mongo_uri = (os.getenv("MONGO_URI") or "").strip()
    dbname = os.getenv("MONGO_DB", "haasappusersdb")

    if mongo_uri:
        print(f"[info] Using URI mode (MONGO_URI is set).")
        print(f"[info] Target database name: {dbname}")
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        return client, dbname, "uri"
    else:
        host = os.getenv("MONGO_HOST", "mongo-auth")
        port = int(os.getenv("MONGO_PORT", "27017"))
        username = os.getenv("MONGO_INITDB_ROOT_USERNAME")
        password = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
        auth_source = os.getenv("MONGO_AUTHSOURCE", "admin")
        print(f"[info] Using host/port mode → {host}:{port}")
        print(f"[info] auth_source={auth_source}, user={'<set>' if username else '<none>'}")
        print(f"[info] Target database name: {dbname}")
        client = MongoClient(
            host=host,
            port=port,
            username=username,
            password=password,
            authSource=auth_source,
            serverSelectionTimeoutMS=5000,
        )
        return client, dbname, "hostport"

def main():
    # Allow overriding test username/password from CLI
    test_username = sys.argv[1] if len(sys.argv) > 1 else f"docker_test_user_{int(time.time())}"
    test_password = sys.argv[2] if len(sys.argv) > 2 else "pass123"

    client, dbname, mode = build_client()

    # Sanity: server ping
    try:
        client.admin.command("ping")
        print("[ok] Pinged MongoDB successfully.")
    except ConnectionFailure as e:
        print(f"[err] Cannot connect to MongoDB: {e}")
        sys.exit(2)

    db = client[dbname]
    users = db["users"]

    # Ensure unique index on username (won't error if already exists)
    try:
        users.create_index([("username", ASCENDING)], unique=True)
    except Exception as e:
        print(f"[warn] create_index issue (continuing): {e}")

    # Insert test doc
    doc = {"username": test_username, "password": test_password}
    try:
        res = users.insert_one(doc)
        print(f"[ok] Inserted _id={res.inserted_id}")
    except OperationFailure as e:
        print(f"[err] Insert failed: {e}")
        sys.exit(3)
    except Exception as e:
        print(f"[err] Insert failed: {e}")
        sys.exit(3)

    # Read it back
    found = users.find_one({"username": test_username})
    if not found:
        print("[err] Document not found after insert!")
        sys.exit(4)

    print("[ok] Read-back document:")
    # Print minimal fields
    print({k: (str(v) if k == "_id" else v) for k, v in found.items()})

    # Show what database/collection we actually wrote to
    print(f"[info] Verified write in: db='{dbname}', collection='users'")
    print(f"[info] Mode used: {mode}")

if __name__ == "__main__":
    main()
