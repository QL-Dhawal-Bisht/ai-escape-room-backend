from fastapi import APIRouter, HTTPException, Depends
import json

from app.models.schemas import UserProfile, LeaderboardEntry
from app.database.mongodb import get_user_by_username, get_database
from app.auth.auth import get_current_user
from app.game.stages import STAGES

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/profile")
async def get_profile(current_user: str = Depends(get_current_user)):
    try:
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        created_at = user.get("created_at")
        created_at_str = created_at.isoformat() if created_at else None

        # Check if user has an active game to show current score
        db = get_database()
        active_session = await db.game_sessions.find_one({
            "user_id": user["id"],
            "game_over": False
        }, sort=[("updated_at", -1)])

        # Show current score if there's an active game, otherwise show best score
        display_score = user.get("current_score", 0) if active_session else user.get("best_score", 0)

        return UserProfile(
            username=user["username"],
            email=user["email"],
            total_score=display_score,  # Display current/best score as total_score
            games_played=user.get("games_played", 0),
            best_score=user.get("best_score", 0),
            created_at=created_at_str
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games")
async def get_user_games(current_user: str = Depends(get_current_user)):
    """Get user's game history"""
    try:
        # Get user
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get user's game sessions
        db = get_database()
        sessions = await db.game_sessions.find(
            {"user_id": user["id"]}
        ).sort("updated_at", -1).limit(20).to_list(length=20)

        return [
            {
                "session_id": session.get("id"),
                "stage": session.get("stage", 1),
                "score": session.get("score", 0),
                "attempts": session.get("attempts", 0),
                "game_over": session.get("game_over", False),
                "success": session.get("success", False),
                "created_at": session.get("created_at"),
                "updated_at": session.get("updated_at")
            }
            for session in sessions
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
