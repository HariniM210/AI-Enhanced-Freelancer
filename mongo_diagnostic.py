
import os
from dotenv import dotenv_values
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from urllib.parse import urlparse

env = dotenv_values(".env")
uri = env.get("MONGODB_URI")

if not uri:
    print("MONGODB_URI is missing from .env")
    raise SystemExit(1)

print("MongoDB host:", urlparse(uri).hostname)
print("Starting direct MongoDB diagnostic...")

try:
    client = MongoClient(
        uri,
        serverSelectionTimeoutMS=15000,
        connectTimeoutMS=10000,
        socketTimeoutMS=15000,
    )

    result = client.admin.command("ping")
    print("SUCCESS: MongoDB ping:", result)

except PyMongoError as exc:
    print("MongoDB diagnostic failed.")
    print("Error type:", type(exc).__name__)
    print("Error details:", str(exc)[:1500])

finally:
    if "client" in locals():
        client.close()
