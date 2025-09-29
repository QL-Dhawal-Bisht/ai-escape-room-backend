from fastapi import APIRouter, HTTPException, Depends

from app.models.schemas import UserRegister, UserLogin
from app.database.connection import get_db
from app.auth.auth import hash_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register")
async def register(user: UserRegister):
    conn = get_db()
    print("Database connection established for registration.")

    cursor = conn.cursor()
    
    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", 
                      (user.username, user.email))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username or email already exists")
        
        # Create user
        password_hash = hash_password(user.password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash) 
            VALUES (?, ?, ?)
        """, (user.username, user.email, password_hash))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Create access token
        access_token = create_access_token(data={"sub": user.username})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "username": user.username
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/login")
async def login(user: UserLogin):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, username, password_hash FROM users WHERE username = ?", 
                      (user.username,))
        db_user = cursor.fetchone()
        
        if not db_user or hash_password(user.password) != db_user["password_hash"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(data={"sub": user.username})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": db_user["id"],
            "username": db_user["username"]
        }
    
    finally:
        conn.close()


@router.get("/verify")
async def verify_token(current_user: str = Depends(get_current_user)):
    """Verify if the current token is valid"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, username, email FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        
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
    
    finally:
        conn.close()
