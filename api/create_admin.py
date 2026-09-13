from pymongo import MongoClient
from passlib.context import CryptContext

MONGO_URI = "mongodb://mongo:27017"
DB_NAME = "newspulse"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_admin():
    print("Connecting to MongoDB...")
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    print("Deleting all existing users...")
    db.users.delete_many({})
    print("Deleted all users.")
    
    admin_email = "admin@newspulse.com"
    admin_password = "admin"
    hashed_password = pwd_context.hash(admin_password)
    
    admin_user = {
        "email": admin_email,
        "password": hashed_password,
        "full_name": "System Administrator",
        "role": "admin",
        "created_at": "2024-01-01T00:00:00Z"
    }
    
    db.users.insert_one(admin_user)
    print(f"Created admin user successfully: {admin_email} / {admin_password}")

if __name__ == "__main__":
    create_admin()
