from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from datetime import datetime, timedelta
from api.database import get_mongo_db
from api.config import get_settings
from api.security import create_access_token, get_current_user, permissions_for_role

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def _create_access_token(data: dict):
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return create_access_token(to_encode)

@router.post("/register")
async def register(user: UserCreate):
    db = get_mongo_db()
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user.model_dump()
    user_dict["password"] = get_password_hash(user_dict["password"])
    user_dict["created_at"] = datetime.utcnow()
    user_dict["role"] = "user"
    user_dict["is_active"] = True
    
    result = await db.users.insert_one(user_dict)
    return {"message": "User created successfully", "user_id": str(result.inserted_id)}

@router.post("/login")
async def login(user: UserLogin, response: Response):
    db = get_mongo_db()
    db_user = await db.users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if db_user.get("is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account is disabled")
        
    role = db_user.get("role", "user")
    access_token = _create_access_token(data={"sub": str(db_user["_id"]), "email": db_user["email"], "role": role})
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/api",
    )
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user": {
            "email": db_user["email"], 
            "full_name": db_user.get("full_name", ""), 
            "id": str(db_user["_id"]),
            "role": role,
            "permissions": permissions_for_role(role),
        }
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {
        "id": user["sub"],
        "email": user.get("email", ""),
        "role": user["role"],
        "permissions": user["permissions"],
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/api")
    return {"message": "Logged out"}
