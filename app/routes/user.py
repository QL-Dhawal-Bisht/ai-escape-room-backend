from fastapi import APIRouter, HTTPException, Depends
import json

from app.models.schemas import UserProfile, LeaderboardEntry
from app.database.connection import get_db
from app.auth.auth import get_current_user
from app.game.stages import STAGES

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile")
async def get_profile(current_user: str = Depends(get_current_user)):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT username, email, total_score, games_played, best_score, created_at
            FROM users WHERE username = ?
        """, (current_user,))
        
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return UserProfile(
            username=user["username"],
            email=user["email"],
            total_score=user["total_score"],
            games_played=user["games_played"],
            best_score=user["best_score"],
            created_at=user["created_at"]
        )
    
    finally:
        conn.close()


@router.get("/games")
async def get_user_games(current_user: str = Depends(get_current_user)):
    """Get user's game history"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        cursor.execute("""
            SELECT id, stage, score, attempts, game_over, success, created_at, updated_at
            FROM game_sessions 
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 20
        """, (user["id"],))
        
        sessions = cursor.fetchall()
        
        return [
            {
                "session_id": session["id"],
                "stage": session["stage"],
                "score": session["score"],
                "attempts": session["attempts"],
                "game_over": session["game_over"],
                "success": session["success"],
                "created_at": session["created_at"],
                "updated_at": session["updated_at"]
            }
            for session in sessions
        ]
    
    finally:
        conn.close()
