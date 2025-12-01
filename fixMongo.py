from pymongo import MongoClient, ASCENDING

MONGO_URI = "mongodb+srv://haas:haaspassword@haas-app-cluster.p0wa0nu.mongodb.net/"
client = MongoClient(MONGO_URI)
db = client["haasappusersdb"]
users = db["users"]

print("Step 1: Checking existing indexes...")
indexes = users.index_information()
print(f"Current indexes: {list(indexes.keys())}")

print("\nStep 2: Dropping all username indexes...")
for index_name in indexes.keys():
    if index_name != "_id_" and "username" in index_name:
        try:
            users.drop_index(index_name)
            print(f"  ✓ Dropped index: {index_name}")
        except Exception as e:
            print(f"  ✗ Failed to drop {index_name}: {e}")

print("\nStep 3: Finding duplicates...")
pipeline = [
    {"$group": {
        "_id": "$username",
        "count": {"$sum": 1},
        "docs": {"$push": "$_id"}
    }},
    {"$match": {"count": {"$gt": 1}}}
]

duplicates = list(users.aggregate(pipeline))
print(f"Found {len(duplicates)} duplicate usernames")

print("\nStep 4: Removing duplicates...")
for dup in duplicates:
    docs_to_delete = dup['docs'][1:]
    if docs_to_delete:
        users.delete_many({"_id": {"$in": docs_to_delete}})
        print(f"  ✓ Removed {len(docs_to_delete)} duplicate(s) of username: {dup['_id']}")

print("\nStep 5: Creating unique index...")
try:
    users.create_index([("username", ASCENDING)], unique=True)
    print("  ✓ Unique index created successfully!")
except Exception as e:
    print(f"  ✗ Failed: {e}")

print("\n✅ Database cleanup complete!")
print(f"Total users remaining: {users.count_documents({})}")