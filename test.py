# # test.py
# import os
# import sys
# from datetime import datetime
# from pymongo import MongoClient
# from pymongo.errors import PyMongoError

# MONGO_URI = os.getenv("MONGO_URI") or "YOUR_ATLAS_CONNECTION_STRING"
# DBNAME    = os.getenv("MONGO_DBNAME") or "YOUR_DB_NAME"

# def fail(msg, code=1):
#     print(f"❌ {msg}")
#     sys.exit(code)

# def main():
#     print("🔎 Starting MongoDB connectivity test...")
#     print(f"URI present: {'yes' if MONGO_URI and 'mongodb' in MONGO_URI else 'no'}")
#     print(f"DB Name: {DBNAME}")

#     try:
#         client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
#         # 1) ping cluster
#         client.admin.command("ping")
#         print("✅ Ping successful: connected to cluster.")

#         db = client[DBNAME]
#         col = db["connectivity_tests"]

#         # 2) write
#         payload = {"_type": "healthcheck", "ts": datetime.utcnow()}
#         inserted = col.insert_one(payload)
#         print(f"✅ Inserted test doc with _id={inserted.inserted_id}")

#         # 3) read
#         found = col.find_one({"_id": inserted.inserted_id})
#         if not found:
#             fail("Inserted doc not found back—read failed")

#         print("✅ Read back the test doc.")

#         # 4) (optional) cleanup
#         col.delete_one({"_id": inserted.inserted_id})
#         print("🧹 Deleted the test doc (cleanup complete)")

#         # 5) list collections (sanity)
#         print("📦 Collections:", db.list_collection_names())

#         print("🎉 All checks passed.")
#         sys.exit(0)

#     except PyMongoError as e:
#         fail(f"PyMongoError: {e}")
#     except Exception as e:
#         fail(f"Unexpected error: {e}")

# if __name__ == "__main__":
#     main()



# test.py
import os
import sys
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

# Load .env file into environment variables
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DBNAME = os.getenv("MONGO_DBNAME")

def fail(msg):
    print(f"❌ {msg}")
    sys.exit(1)

def main():
    print("🔎 Testing MongoDB connection...")
    print(f"• MONGO_URI loaded: {'yes' if MONGO_URI else 'no'}")
    print(f"• DB Name: {DBNAME}")

    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        print("✅ Connection Test: Success (Ping OK).")

        db = client[DBNAME]
        col = db["connectivity_test"]
        doc = {"test": True, "timestamp": datetime.utcnow()}

        res = col.insert_one(doc)
        print(f"✅ Write Test: Inserted document with _id={res.inserted_id}")

        fetched = col.find_one({"_id": res.inserted_id})
        print(f"✅ Read Test: Found document back: {fetched}")

        col.delete_one({"_id": res.inserted_id})
        print("🧹 Cleanup: Test document removed.")

        print("\n🎉 All tests passed successfully.\n")
        sys.exit(0)

    except PyMongoError as e:
        fail(f"MongoDB Error: {e}")
    except Exception as e:
        fail(f"Unexpected Error: {e}")

if __name__ == "__main__":
    main()
