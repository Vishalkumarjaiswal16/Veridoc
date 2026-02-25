from fastapi import APIRouter, HTTPException, Depends, status
from backend.models.schemas import UserCreate, UserLogin, UserResponse, Token, SignupResponse, GoogleLogin
from backend.models.database import get_database
from backend.utils.auth import get_password_hash, verify_password, create_access_token
from backend.config import GOOGLE_CLIENT_ID
from datetime import datetime
import uuid
from google.oauth2 import id_token
from google.auth.transport import requests

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/signup", response_model=SignupResponse)
async def signup(user: UserCreate):
    db = get_database()
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user_dict = user.model_dump()
    user_dict["password"] = get_password_hash(user_dict["password"])
    user_dict["_id"] = str(uuid.uuid4())
    user_dict["created_at"] = datetime.utcnow()
    
    await db.users.insert_one(user_dict)
    
    # Generate token for immediate login
    access_token = create_access_token(data={"sub": user.email})
    
    return {
        "user": user_dict,
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    db = get_database()
    
    user = await db.users.find_one({"email": user_data.email})
    if not user or not verify_password(user_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=SignupResponse)
async def google_auth(data: GoogleLogin):
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(data.token, requests.Request(), GOOGLE_CLIENT_ID)
        
        email = idinfo['email']
        full_name = idinfo.get('name')
        
        db = get_database()
        
        # Check if user exists
        user = await db.users.find_one({"email": email})
        
        if not user:
            # Create new user if they don't exist
            user = {
                "_id": str(uuid.uuid4()),
                "email": email,
                "full_name": full_name,
                "is_google_user": True,
                "created_at": datetime.utcnow()
            }
            await db.users.insert_one(user)
        
        access_token = create_access_token(data={"sub": email})
        
        return {
            "user": user,
            "access_token": access_token,
            "token_type": "bearer"
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )
