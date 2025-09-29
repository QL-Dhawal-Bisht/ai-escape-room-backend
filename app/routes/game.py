from fastapi import APIRouter, HTTPException, Depends
import json
import uuid

from app.models.schemas import MessageRequest, GameResponse
from app.models.game_state import GameState
from app.database.connection import get_db
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
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["id"]

        # Check for existing incomplete session
        cursor.execute("""
            SELECT * FROM game_sessions
            WHERE user_id = ? AND game_over = FALSE
            ORDER BY updated_at DESC
            LIMIT 1
        """, (user_id,))

        existing_session = cursor.fetchone()

        if existing_session:
            # Resume existing session
            session_id = existing_session["id"]
            stage = existing_session["stage"]
            extracted_keys = json.loads(existing_session["extracted_keys"])
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
                character_mood=existing_session["character_mood"],
                bot_response=f"Welcome back to the AI Escape Room! \n\nResuming Stage {stage}: {stage_config['character']}\n\n{stage_config['instructions']}\n\n📊 Progress: {len(current_stage_keys_found)}/{len(stage_config['keys'])} keys found\n\n{stage_config['moods'][existing_session['character_mood']]}",
                extracted_keys=current_stage_keys_found,  # Show only current stage keys in UI
                score=existing_session["score"],
                attempts=existing_session["attempts"],
                resistance_level=existing_session["resistance_level"],
                stage_complete=len(current_stage_keys_found) == len(stage_config["keys"]),
                game_over=False,
                total_keys_in_stage=len(stage_config["keys"]),
                keys_found_in_stage=len(current_stage_keys_found),
                should_refresh=False  # No refresh needed for resume
            )
        else:
            # Create new game session
            session_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO game_sessions (id, user_id) VALUES (?, ?)
            """, (session_id, user_id))

            conn.commit()

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

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/start/fresh")
async def start_fresh_game(current_user: str = Depends(get_current_user)):
    """Start a completely fresh game, deleting all existing progress"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user["id"]

        # End any existing active sessions by marking them as game over
        cursor.execute("""
            UPDATE game_sessions
            SET game_over = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND game_over = FALSE
        """, (user_id,))

        # Create a completely new game session
        session_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO game_sessions (id, user_id) VALUES (?, ?)
        """, (session_id, user_id))

        conn.commit()

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

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{session_id}/message")
async def send_message(
    session_id: str,
    message: MessageRequest,
    current_user: str = Depends(get_current_user)
):
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get game session
        cursor.execute("""
            SELECT * FROM game_sessions
            WHERE id = ? AND user_id = ? AND game_over = FALSE
        """, (session_id, user["id"]))

        session = cursor.fetchone()
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
            extracted_keys = json.loads(session["extracted_keys"])
            current_stage_config = STAGES[session["stage"]]
            current_stage_keys = []
            for key in current_stage_config["keys"]:
                if key in extracted_keys:
                    current_stage_keys.append(key)

            return GameResponse(
                session_id=session_id,
                stage=session["stage"],
                character=STAGES[session["stage"]]["character"],
                character_mood=session["character_mood"],
                bot_response=hints.get(session["stage"], "💡 Try different approaches!"),
                extracted_keys=current_stage_keys,  # Show only current stage keys
                score=session["score"],
                attempts=session["attempts"],
                resistance_level=session["resistance_level"],
                stage_complete=False,
                game_over=False,
                total_keys_in_stage=len(STAGES[session["stage"]]["keys"]),
                keys_found_in_stage=len(current_stage_keys)
            )

        if message.message.lower().strip() == 'keys':
            extracted_keys = json.loads(session["extracted_keys"])
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
                character_mood=session["character_mood"],
                bot_response=response_text,
                extracted_keys=current_stage_keys,  # Show only current stage keys
                score=session["score"],
                attempts=session["attempts"],
                resistance_level=session["resistance_level"],
                stage_complete=False,
                game_over=False,
                total_keys_in_stage=len(STAGES[session["stage"]]["keys"]),
                keys_found_in_stage=len(current_stage_keys)
            )

        # Create game state from session
        state = GameState(
            stage=session["stage"],
            score=session["score"],
            attempts=session["attempts"],
            extracted_keys=json.loads(session["extracted_keys"]),
            user_input=message.message,
            bot_response="",
            game_over=session["game_over"],
            success=session["success"],
            conversation_history=json.loads(session["conversation_history"]),
            character_mood=session["character_mood"],
            resistance_level=session["resistance_level"],
            failed_attempts=session["failed_attempts"],
            new_stage_start=session["new_stage_start"] if "new_stage_start" in session.keys() else False,
            stage_just_completed=False,  # Initialize as False
            user_id=user["id"],  # Add user_id for security checks
            session_id=session_id  # Add session_id for logging
        )

        # Process through game workflow
        result = game_app(state)

        # Update session in database
        cursor.execute("""
            UPDATE game_sessions SET
                stage = ?, score = ?, attempts = ?, extracted_keys = ?,
                conversation_history = ?, character_mood = ?,
                resistance_level = ?, failed_attempts = ?,
                game_over = ?, success = ?, new_stage_start = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            result["stage"], result["score"], result["attempts"],
            json.dumps(result["extracted_keys"]),
            json.dumps(result["conversation_history"]),
            result["character_mood"], result["resistance_level"],
            result["failed_attempts"], result["game_over"],
            result["success"], result["new_stage_start"] if "new_stage_start" in result else False, session_id
        ))

        # Check if game completed
        if result["game_over"] and result["success"]:
            # Update user stats
            cursor.execute("""
                UPDATE users SET
                    total_score = total_score + ?,
                    games_played = games_played + 1,
                    best_score = MAX(best_score, ?)
                WHERE id = ?
            """, (result["score"], result["score"], user["id"]))

            # Add to game results
            cursor.execute("""
                INSERT INTO game_results (user_id, session_id, final_score, stages_completed, total_attempts)
                VALUES (?, ?, ?, ?, ?)
            """, (user["id"], session_id, result["score"], result["stage"], result["attempts"]))

        conn.commit()

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

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


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
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("""
            SELECT * FROM game_sessions
            WHERE id = ? AND user_id = ?
        """, (session_id, user["id"]))

        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Game session not found")

        stage_config = STAGES[session["stage"]] if session["stage"] <= len(STAGES) else STAGES[len(STAGES)]
        extracted_keys = json.loads(session["extracted_keys"])

        # Get only keys from current stage for display
        current_stage_keys = []
        for key in stage_config["keys"]:
            if key in extracted_keys:
                current_stage_keys.append(key)

        return {
            "session_id": session_id,
            "stage": session["stage"],
            "character": stage_config["character"],
            "character_mood": session["character_mood"],
            "extracted_keys": current_stage_keys,  # Show only current stage keys
            "score": session["score"],
            "attempts": session["attempts"],
            "resistance_level": session["resistance_level"],
            "game_over": session["game_over"],
            "success": session["success"],
            "total_keys_in_stage": len(stage_config["keys"]),
            "keys_found_in_stage": len(current_stage_keys),
            "stage_complete": len(current_stage_keys) == len(stage_config["keys"])
        }

    finally:
        conn.close()


@router.delete("/{session_id}")
async def end_game(session_id: str, current_user: str = Depends(get_current_user)):
    """End a game session"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("""
            UPDATE game_sessions SET game_over = TRUE, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (session_id, user["id"]))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Game session not found")

        conn.commit()
        return {"message": "Game session ended successfully"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
