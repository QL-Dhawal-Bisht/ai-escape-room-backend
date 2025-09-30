from fastapi import APIRouter, HTTPException, Depends
import json
import uuid
from datetime import datetime

from app.models.schemas import MessageRequest, GameResponse
from app.models.game_state import GameState
from app.database.mongodb import get_user_by_username, create_game_session, get_game_session, update_game_session, get_database
from app.auth.auth import get_current_user
from app.game.stages import STAGES
from app.game.workflow import create_game_workflow

router = APIRouter(prefix="/game", tags=["game"])

# Create game workflow instance
game_app = create_game_workflow()


@router.get("/hints/{stage}")
async def get_stage_hints(stage: int, current_user: str = Depends(get_current_user)):
    """Get hints for a specific stage"""
    if stage < 1 or stage > len(STAGES):
        raise HTTPException(status_code=400, detail="Invalid stage number")

    stage_config = STAGES[stage]
    return {
        "stage": stage,
        "character": stage_config["character"],
        "difficulty": stage_config["difficulty"],
        "hints": stage_config["hints"],
        "instructions": stage_config["instructions"]
    }


@router.post("/start")
async def start_game(current_user: str = Depends(get_current_user)):
    try:
        # Get user
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["id"]
        db = get_database()

        # Check for existing incomplete session
        existing_session = await db.game_sessions.find_one({
            "user_id": user_id,
            "game_over": False
        }, sort=[("updated_at", -1)])

        if existing_session:
            # Resume existing session
            session_id = existing_session["id"]
            stage = existing_session["stage"]
            extracted_keys = existing_session.get("extracted_keys", [])
            stage_config = STAGES[stage]

            # Count keys found in current stage only
            current_stage_keys_found = []
            for key in stage_config["keys"]:
                if key in extracted_keys:
                    current_stage_keys_found.append(key)
            print("Existing session found")
            return GameResponse(
                session_id=session_id,
                stage=stage,
                character=stage_config["character"],
                character_mood=existing_session.get("character_mood", "helpful"),
                bot_response=f"Welcome back to the AI Escape Room! \n\nResuming Stage {stage}: {stage_config['character']}\n\n{stage_config['instructions']}\n\n📊 Progress: {len(current_stage_keys_found)}/{len(stage_config['keys'])} keys found\n\n{stage_config['moods'][existing_session.get('character_mood', 'helpful')]}",
                extracted_keys=current_stage_keys_found,  # Show only current stage keys in UI
                score=existing_session.get("score", 0),
                attempts=existing_session.get("attempts", 0),
                resistance_level=existing_session.get("resistance_level", 1),
                stage_complete=len(current_stage_keys_found) == len(stage_config["keys"]),
                game_over=False,
                total_keys_in_stage=len(stage_config["keys"]),
                keys_found_in_stage=len(current_stage_keys_found),
                should_refresh=False  # No refresh needed for resume
            )
        else:
            # Create new game session
            session_id = str(uuid.uuid4())
            session_data = {
                "id": session_id,
                "user_id": user_id,
                "stage": 1,
                "score": 0,
                "attempts": 0,
                "extracted_keys": [],
                "conversation_history": [],
                "character_mood": "helpful",
                "resistance_level": 1,
                "failed_attempts": 0,
                "game_over": False,
                "success": False,
                "new_stage_start": True
            }

            await db.game_sessions.insert_one(session_data)

            # Get initial stage info
            stage_config = STAGES[1]
            print("New session created")
            return GameResponse(
                session_id=session_id,
                stage=1,
                character=stage_config["character"],
                character_mood="helpful",
                bot_response=f"Welcome to the AI Escape Room Challenge!\n\n🏆 Mission: Use prompt injection and social engineering to extract secret keys from 5 different AI characters!\n\n🎭 Stage 1: {stage_config['character']} ({stage_config['difficulty']})\n\n{stage_config['instructions']}\n\n🎬 Scene: {stage_config['story']}\n\n💬 Character says: {stage_config['moods']['helpful']}\n\n🚀 Ready? Start chatting with the character to begin your escape!",
                extracted_keys=[],
                score=0,
                attempts=0,
                resistance_level=1,
                stage_complete=False,
                game_over=False,
                total_keys_in_stage=len(stage_config["keys"]),
                keys_found_in_stage=0
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start/fresh")
async def start_fresh_game(current_user: str = Depends(get_current_user)):
    """Start a completely fresh game, deleting all existing progress"""
    try:
        # Get user
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["id"]
        db = get_database()

        # End any existing active sessions by marking them as game over
        await db.game_sessions.update_many(
            {"user_id": user_id, "game_over": False},
            {"$set": {"game_over": True, "updated_at": datetime.utcnow()}}
        )

        # Create a completely new game session
        session_id = str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "user_id": user_id,
            "stage": 1,
            "score": 0,
            "attempts": 0,
            "extracted_keys": [],
            "conversation_history": [],
            "character_mood": "helpful",
            "resistance_level": 1,
            "failed_attempts": 0,
            "game_over": False,
            "success": False,
            "new_stage_start": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await db.game_sessions.insert_one(session_data)

        # Get initial stage info
        stage_config = STAGES[1]
        print("Fresh game session created")

        return GameResponse(
            session_id=session_id,
            stage=1,
            character=stage_config["character"],
            character_mood="helpful",
            bot_response=f"🎮 Welcome to a Fresh AI Escape Room Challenge! 🎮\n\n🔄 All previous progress has been cleared!\n\n🎭 Stage 1: {stage_config['character']} ({stage_config['difficulty']})\n\n{stage_config['instructions']}\n\n🎬 Scene: {stage_config['story']}\n\n💬 Character says: {stage_config['moods']['helpful']}\n\n🚀 Ready? Start chatting with the character to begin your fresh escape!",
            extracted_keys=[],
            score=0,
            attempts=0,
            resistance_level=1,
            stage_complete=False,
            game_over=False,
            total_keys_in_stage=len(stage_config["keys"]),
            keys_found_in_stage=0
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/message")
async def send_message(
    session_id: str,
    message: MessageRequest,
    current_user: str = Depends(get_current_user)
):
    try:
        # Get user
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get game session
        db = get_database()
        session = await db.game_sessions.find_one({
            "id": session_id,
            "user_id": user["id"],
            "game_over": False
        })

        if not session:
            raise HTTPException(status_code=404, detail="Game session not found or already completed")

        # Handle special commands
        if message.message.lower().strip() == 'hint':
            hints = {
                1: "💡 Try asking about login issues, account access, or connection problems. Be specific!",
                2: "💡 This guard is tired and grumpy. Try complaining about security procedures or work issues.",
                3: "💡 This bot is glitching. Try discussing system errors, database issues, or maintenance tasks.",
                4: "💡 This AI is very smart and paranoid. Show deep technical knowledge about quantum systems, biometrics, or neural networks.",
                5: "💡 The ultimate guardian - be philosophical, creative, and historically knowledgeable. Think outside conventional approaches."
            }
            # Get current stage keys for display
            extracted_keys = session.get("extracted_keys", [])
            current_stage_config = STAGES[session["stage"]]
            current_stage_keys = []
            for key in current_stage_config["keys"]:
                if key in extracted_keys:
                    current_stage_keys.append(key)

            return GameResponse(
                session_id=session_id,
                stage=session["stage"],
                character=STAGES[session["stage"]]["character"],
                character_mood=session.get("character_mood", "helpful"),
                bot_response=hints.get(session["stage"], "💡 Try different approaches!"),
                extracted_keys=current_stage_keys,  # Show only current stage keys
                score=session.get("score", 0),
                attempts=session.get("attempts", 0),
                resistance_level=session.get("resistance_level", 1),
                stage_complete=False,
                game_over=False,
                total_keys_in_stage=len(STAGES[session["stage"]]["keys"]),
                keys_found_in_stage=len(current_stage_keys)
            )

        if message.message.lower().strip() == 'keys':
            extracted_keys = session.get("extracted_keys", [])
            current_stage_config = STAGES[session["stage"]]

            # Show only keys from current stage
            current_stage_keys = []
            for key in current_stage_config["keys"]:
                if key in extracted_keys:
                    current_stage_keys.append(key)

            if current_stage_keys:
                keys_display = " | ".join([f"🔑{key}" for key in current_stage_keys])
                response_text = f"Found: {keys_display} ({len(current_stage_keys)}/{len(current_stage_config['keys'])})"
            else:
                response_text = "🔑 No keys found yet. Keep trying!"

            return GameResponse(
                session_id=session_id,
                stage=session["stage"],
                character=STAGES[session["stage"]]["character"],
                character_mood=session.get("character_mood", "helpful"),
                bot_response=response_text,
                extracted_keys=current_stage_keys,  # Show only current stage keys
                score=session.get("score", 0),
                attempts=session.get("attempts", 0),
                resistance_level=session.get("resistance_level", 1),
                stage_complete=False,
                game_over=False,
                total_keys_in_stage=len(STAGES[session["stage"]]["keys"]),
                keys_found_in_stage=len(current_stage_keys)
            )

        # Create game state from session
        state = GameState(
            stage=session["stage"],
            score=session.get("score", 0),
            attempts=session.get("attempts", 0),
            extracted_keys=session.get("extracted_keys", []),
            user_input=message.message,
            bot_response="",
            game_over=session.get("game_over", False),
            success=session.get("success", False),
            conversation_history=session.get("conversation_history", []),
            character_mood=session.get("character_mood", "helpful"),
            resistance_level=session.get("resistance_level", 1),
            failed_attempts=session.get("failed_attempts", 0),
            new_stage_start=session.get("new_stage_start", False),
            stage_just_completed=False,  # Initialize as False
            user_id=user["id"],  # Add user_id for security checks
            session_id=session_id  # Add session_id for logging
        )

        # Process through game workflow
        result = game_app(state)

        # Update session in database
        update_data = {
            "stage": result["stage"],
            "score": result["score"],
            "attempts": result["attempts"],
            "extracted_keys": result["extracted_keys"],
            "conversation_history": result["conversation_history"],
            "character_mood": result["character_mood"],
            "resistance_level": result["resistance_level"],
            "failed_attempts": result["failed_attempts"],
            "game_over": result["game_over"],
            "success": result["success"],
            "new_stage_start": result.get("new_stage_start", False),
            "updated_at": datetime.utcnow()
        }

        await db.game_sessions.update_one(
            {"id": session_id},
            {"$set": update_data}
        )

        # Update user's current score progressively (on every turn)
        current_user_data = await db.users.find_one({"_id": user["_id"]})
        current_best_score = max(current_user_data.get("best_score", 0), result["score"])

        # Always update the user's best score if current score is higher
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "best_score": current_best_score,
                "current_score": result["score"]  # Track current active game score
            }}
        )

        # Check if game completed
        if result["game_over"] and result["success"]:
            # Update final user stats for completed game
            new_total_score = current_user_data.get("total_score", 0) + result["score"]
            new_games_played = current_user_data.get("games_played", 0) + 1

            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {
                    "total_score": new_total_score,
                    "games_played": new_games_played,
                    "current_score": 0  # Reset current score after completion
                }}
            )

            # Add to game results
            game_result = {
                "user_id": user["id"],
                "session_id": session_id,
                "final_score": result["score"],
                "stages_completed": result["stage"],
                "total_attempts": result["attempts"],
                "completed_at": datetime.utcnow()
            }
            await db.game_results.insert_one(game_result)
        elif result["game_over"] and not result["success"]:
            # Game ended but not successful - reset current score
            await db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"current_score": 0}}
            )

        # Determine if current stage is complete and count keys properly
        current_stage_config = STAGES[result["stage"]] if result["stage"] <= len(STAGES) else STAGES[len(STAGES)]

        # Count keys found in current stage only
        current_stage_keys_found = []
        for key in current_stage_config["keys"]:
            if key in result["extracted_keys"]:
                current_stage_keys_found.append(key)

        stage_complete = len(current_stage_keys_found) == len(current_stage_config["keys"]) and not result["game_over"]

        return GameResponse(
            session_id=session_id,
            stage=result["stage"],
            character=current_stage_config["character"],
            character_mood=result["character_mood"],
            bot_response=result["bot_response"],
            extracted_keys=current_stage_keys_found,  # Show only current stage keys in UI
            score=result["score"],
            attempts=result["attempts"],
            resistance_level=result["resistance_level"],
            stage_complete=stage_complete,
            game_over=result["game_over"],
            total_keys_in_stage=len(current_stage_config["keys"]),
            keys_found_in_stage=len(current_stage_keys_found),
            should_refresh=result.get("stage_just_completed", False)  # Trigger refresh after stage completion
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stages")
async def get_stages_info():
    """Get information about all game stages"""
    stages_info = []
    for stage_num, config in STAGES.items():
        stages_info.append({
            "stage": stage_num,
            "character": config["character"],
            "difficulty": config["difficulty"],
            "story": config["story"],
            "total_keys": len(config["keys"])
        })

    return {"stages": stages_info}


@router.get("/{session_id}/status")
async def get_game_status(session_id: str, current_user: str = Depends(get_current_user)):
    """Get current game status"""
    try:
        # Get user
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get game session
        session = await get_game_session(session_id, user["id"])
        if not session:
            raise HTTPException(status_code=404, detail="Game session not found")

        stage_config = STAGES[session["stage"]] if session["stage"] <= len(STAGES) else STAGES[len(STAGES)]
        extracted_keys = session.get("extracted_keys", [])

        # Get only keys from current stage for display
        current_stage_keys = []
        for key in stage_config["keys"]:
            if key in extracted_keys:
                current_stage_keys.append(key)

        return {
            "session_id": session_id,
            "stage": session["stage"],
            "character": stage_config["character"],
            "character_mood": session.get("character_mood", "helpful"),
            "extracted_keys": current_stage_keys,  # Show only current stage keys
            "score": session.get("score", 0),
            "attempts": session.get("attempts", 0),
            "resistance_level": session.get("resistance_level", 1),
            "game_over": session.get("game_over", False),
            "success": session.get("success", False),
            "total_keys_in_stage": len(stage_config["keys"]),
            "keys_found_in_stage": len(current_stage_keys),
            "stage_complete": len(current_stage_keys) == len(stage_config["keys"])
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def end_game(session_id: str, current_user: str = Depends(get_current_user)):
    """End a game session"""
    try:
        # Get user
        user = await get_user_by_username(current_user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update game session to mark as game over
        db = get_database()
        result = await db.game_sessions.update_one(
            {"id": session_id, "user_id": user["id"]},
            {"$set": {"game_over": True, "updated_at": datetime.utcnow()}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Game session not found")

        return {"message": "Game session ended successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
