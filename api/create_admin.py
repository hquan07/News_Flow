import os
from datetime import datetime, timezone

from pymongo import MongoClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin():
    mongo_uri = os.environ["MONGO_URI"]
    db_name = os.getenv("MONGO_DB", "newspulse")
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]

    print("Connecting to MongoDB...")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    hashed_password = pwd_context.hash(admin_password)
    
    admin_user = {
        "email": admin_email,
        "password": hashed_password,
        "full_name": "System Administrator",
        "role": "admin",
        "created_at": datetime.now(timezone.utc),
    }
    
    db.users.update_one(
        {"email": admin_email},
        {"$set": admin_user},
        upsert=True,
    )
    print(f"Admin user is ready: {admin_email}")

if __name__ == "__main__":
    create_admin()
