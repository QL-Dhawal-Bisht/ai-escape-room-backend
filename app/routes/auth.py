from fastapi import APIRouter, HTTPException, Depends
from passlib.context import CryptContext

from app.models.schemas import UserRegister, UserLogin
from app.database.mongodb import create_user, get_user_by_username, get_user_by_email
from app.auth.auth import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


@router.post("/register")
async def register(user: UserRegister):
    try:
        # Check if user exists
        if await get_user_by_username(user.username):
            raise HTTPException(status_code=400, detail="Username already exists")
        if await get_user_by_email(user.email):
            raise HTTPException(status_code=400, detail="Email already exists")

        # Hash password
        password_hash = hash_password(user.password)
        user_data = {
            "username": user.username,
            "email": user.email,
            "password_hash": password_hash
        }

        user_id = await create_user(user_data)

        # Create access token
        access_token = create_access_token(data={"sub": user.username})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "username": user.username
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login")
async def login(user: UserLogin):
    try:
        db_user = await get_user_by_username(user.username)
        if not db_user or not verify_password(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        access_token = create_access_token(data={"sub": user.username})

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": db_user["id"],
            "username": db_user["username"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/verify")
async def verify_token(current_user: str = Depends(get_current_user)):
    """Verify if the current token is valid"""
    try:
        user = await get_user_by_username(current_user)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "valid": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
