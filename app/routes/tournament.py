from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
import json
import uuid
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List

from app.models.tournament import (
    TournamentCreate, TournamentJoin, Tournament, TournamentParticipant,
    TournamentStatus, TournamentResults, TournamentEvent, TournamentGameState
)
from app.models.game_state import GameState
from app.database.connection import get_db
from app.auth.auth import get_current_user
from app.game.stages import STAGES
from app.game.workflow import create_game_workflow

router = APIRouter(prefix="/tournament", tags=["tournament"])

# Create game workflow instance for tournament
tournament_game_app = create_game_workflow()

# WebSocket connection manager
class TournamentConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, tournament_id: str):
        await websocket.accept()
        if tournament_id not in self.active_connections:
            self.active_connections[tournament_id] = []
        self.active_connections[tournament_id].append(websocket)

    def disconnect(self, websocket: WebSocket, tournament_id: str):
        if tournament_id in self.active_connections:
            self.active_connections[tournament_id].remove(websocket)
            if not self.active_connections[tournament_id]:
                del self.active_connections[tournament_id]

    async def broadcast_to_tournament(self, tournament_id: str, message: dict):
        if tournament_id in self.active_connections:
            for connection in self.active_connections[tournament_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Connection is broken, remove it
                    self.active_connections[tournament_id].remove(connection)

manager = TournamentConnectionManager()


def generate_room_code() -> str:
    """Generate a 6-character room code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


@router.post("/create")
async def create_tournament(
    tournament_data: TournamentCreate,
    current_user: str = Depends(get_current_user)
):
    """Create a new tournament"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate unique tournament ID and room code
        tournament_id = str(uuid.uuid4())
        room_code = generate_room_code()
        
        # Ensure room code is unique
        while True:
            cursor.execute("SELECT id FROM tournaments WHERE room_code = ?", (room_code,))
            if not cursor.fetchone():
                break
            room_code = generate_room_code()
        
        # Create tournament
        cursor.execute("""
            INSERT INTO tournaments (
                id, room_code, host_user_id, stage, time_limit, tournament_mode, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'waiting')
        """, (tournament_id, room_code, user["id"], tournament_data.stage, 
              tournament_data.time_limit, tournament_data.tournament_mode))
        
        # Add host as first participant
        cursor.execute("""
            INSERT INTO tournament_participants (
                tournament_id, user_id, is_ready
            ) VALUES (?, ?, FALSE)
        """, (tournament_id, user["id"]))
        
        conn.commit()
        
        return {
            "tournament_id": tournament_id,
            "room_code": room_code,
            "status": "waiting",
            "stage": tournament_data.stage,
            "time_limit": tournament_data.time_limit
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/join")
async def join_tournament(
    join_data: TournamentJoin,
    current_user: str = Depends(get_current_user)
):
    """Join an existing tournament"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get tournament by room code
        cursor.execute("""
            SELECT id, host_user_id, status, max_participants
            FROM tournaments WHERE room_code = ?
        """, (join_data.room_code,))
        
        tournament = cursor.fetchone()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        if tournament["status"] != "waiting":
            raise HTTPException(status_code=400, detail="Tournament already started or completed")
        
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if tournament is full
        cursor.execute("""
            SELECT COUNT(DISTINCT CASE WHEN tp.user_id IS NOT NULL THEN tp.user_id ELSE tp.guest_name END) as unique_count
            FROM tournament_participants tp
            WHERE tournament_id = ?
        """, (tournament["id"],))
        
        participant_count = cursor.fetchone()["unique_count"]
        if participant_count >= tournament["max_participants"]:
            raise HTTPException(status_code=400, detail="Tournament is full")
        
        # Check if user already joined (including duplicates)
        cursor.execute("""
            SELECT id FROM tournament_participants 
            WHERE tournament_id = ? AND user_id = ?
        """, (tournament["id"], user["id"]))
        
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Already joined this tournament")
        
        # Add participant
        try:
            cursor.execute("""
                INSERT INTO tournament_participants (
                    tournament_id, user_id, is_ready
                ) VALUES (?, ?, FALSE)
            """, (tournament["id"], user["id"]))
        except Exception as e:
            if "UNIQUE constraint failed" in str(e):
                raise HTTPException(status_code=400, detail="You are already in this tournament")
            else:
                raise HTTPException(status_code=500, detail="Failed to join tournament")
        
        conn.commit()
        
        # Broadcast join event
        await manager.broadcast_to_tournament(tournament["id"], {
            "type": "participant_joined",
            "username": current_user,
            "participant_count": participant_count + 1
        })
        
        return {
            "tournament_id": tournament["id"],
            "room_code": join_data.room_code,
            "status": "joined"
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/join-guest")
async def join_tournament_as_guest(join_data: TournamentJoin):
    """Join tournament as guest user"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get tournament by room code
        cursor.execute("""
            SELECT id, status, max_participants
            FROM tournaments WHERE room_code = ?
        """, (join_data.room_code,))
        
        tournament = cursor.fetchone()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        if tournament["status"] != "waiting":
            raise HTTPException(status_code=400, detail="Tournament already started or completed")
        
        # Check if tournament is full
        cursor.execute("""
            SELECT COUNT(*) as count FROM tournament_participants 
            WHERE tournament_id = ?
        """, (tournament["id"],))
        
        participant_count = cursor.fetchone()["count"]
        if participant_count >= tournament["max_participants"]:
            raise HTTPException(status_code=400, detail="Tournament is full")
        
        if not join_data.guest_name:
            raise HTTPException(status_code=400, detail="Guest name required")
        
        # Add guest participant
        cursor.execute("""
            INSERT INTO tournament_participants (
                tournament_id, is_guest, guest_name, is_ready
            ) VALUES (?, TRUE, ?, FALSE)
        """, (tournament["id"], join_data.guest_name))
        
        participant_id = cursor.lastrowid
        conn.commit()
        
        # Broadcast join event
        await manager.broadcast_to_tournament(tournament["id"], {
            "type": "participant_joined",
            "guest_name": join_data.guest_name,
            "participant_count": participant_count + 1
        })
        
        return {
            "tournament_id": tournament["id"],
            "participant_id": participant_id,
            "room_code": join_data.room_code,
            "status": "joined",
            "is_guest": True
        }
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{tournament_id}/status")
async def get_tournament_status(
    tournament_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get current tournament status"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get tournament info with host username
        cursor.execute("""
            SELECT t.*, u.username as host_username
            FROM tournaments t
            JOIN users u ON t.host_user_id = u.id
            WHERE t.id = ?
        """, (tournament_id,))
        
        tournament = cursor.fetchone()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Get participants
        cursor.execute("""
            SELECT tp.*, u.username 
            FROM tournament_participants tp
            LEFT JOIN users u ON tp.user_id = u.id
            WHERE tp.tournament_id = ?
            ORDER BY tp.joined_at
        """, (tournament_id,))
        
        participants = cursor.fetchall()
        
        # Calculate time remaining if active
        time_remaining = None
        if tournament["status"] == "active" and tournament["started_at"]:
            start_time = datetime.fromisoformat(tournament["started_at"])
            elapsed = (datetime.now() - start_time).total_seconds()
            time_remaining = max(0, tournament["time_limit"] - elapsed)
        
        return {
            "tournament": dict(tournament),
            "participants": [dict(p) for p in participants],
            "time_remaining": time_remaining
        }
    
    finally:
        conn.close()


@router.post("/{tournament_id}/ready")
async def set_ready_status(
    tournament_id: str,
    ready: bool,
    current_user: str = Depends(get_current_user)
):
    """Set player ready status"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update ready status
        cursor.execute("""
            UPDATE tournament_participants 
            SET is_ready = ?
            WHERE tournament_id = ? AND user_id = ?
        """, (ready, tournament_id, user["id"]))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not a participant in this tournament")
        
        # Check if all participants are ready
        cursor.execute("""
            SELECT COUNT(*) as total, SUM(is_ready) as ready_count
            FROM tournament_participants 
            WHERE tournament_id = ?
        """, (tournament_id,))
        
        counts = cursor.fetchone()
        all_ready = counts["ready_count"] == counts["total"] and counts["total"] >= 2
        
        if all_ready:
            # Update tournament status to ready
            cursor.execute("""
                UPDATE tournaments 
                SET status = 'ready'
                WHERE id = ?
            """, (tournament_id,))
        
        conn.commit()
        
        # Broadcast ready status change
        await manager.broadcast_to_tournament(tournament_id, {
            "type": "ready_status_changed",
            "username": current_user,
            "is_ready": ready,
            "all_ready": all_ready
        })
        
        return {"status": "ready" if all_ready else "waiting", "is_ready": ready}
    
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{tournament_id}/start")
async def start_tournament(
    tournament_id: str,
    current_user: str = Depends(get_current_user)
):
    """Start the tournament (host only)"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get tournament and verify host
        cursor.execute("""
            SELECT t.*, u.username as host_username
            FROM tournaments t
            JOIN users u ON t.host_user_id = u.id
            WHERE t.id = ?
        """, (tournament_id,))
        
        tournament = cursor.fetchone()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        if tournament["host_username"] != current_user:
            raise HTTPException(status_code=403, detail="Only host can start tournament")
        
        if tournament["status"] != "ready":
            raise HTTPException(status_code=400, detail="Tournament not ready to start")
        
        # Validate participant count
        cursor.execute("""
            SELECT COUNT(DISTINCT CASE WHEN tp.user_id IS NOT NULL THEN tp.user_id ELSE tp.guest_name END) as unique_count
            FROM tournament_participants tp
            WHERE tp.tournament_id = ?
        """, (tournament_id,))
        
        participant_count = cursor.fetchone()["unique_count"]
        if participant_count != 2:
            raise HTTPException(status_code=400, detail=f"Tournament must have exactly 2 participants, but has {participant_count}")
        
        # Start tournament
        started_at = datetime.now().isoformat()
        cursor.execute("""
            UPDATE tournaments 
            SET status = 'active', started_at = ?
            WHERE id = ?
        """, (started_at, tournament_id))
        
        # Initialize game sessions for all participants
        cursor.execute("""
            SELECT tp.id as participant_id, tp.user_id, tp.guest_name
            FROM tournament_participants tp
            WHERE tp.tournament_id = ?
        """, (tournament_id,))
        
        participants = cursor.fetchall()
        
        for participant in participants:
            # Create game session for each participant
            game_session_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO tournament_game_sessions (
                    id, tournament_id, participant_id, stage, start_time, status
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (game_session_id, tournament_id, participant["participant_id"], 
                  tournament["stage"], started_at, 'active'))
        
        conn.commit()
        
        # Broadcast tournament start
        await manager.broadcast_to_tournament(tournament_id, {
            "type": "tournament_started",
            "started_at": started_at,
            "time_limit": tournament["time_limit"],
            "stage": tournament["stage"]
        })
        
        return {"status": "started", "started_at": started_at}
    
    except Exception as e:
        conn.rollback()
        print(f"Tournament start error: {str(e)}")  # Add logging
        raise HTTPException(status_code=500, detail=f"Failed to start tournament: {str(e)}")
    finally:
        conn.close()


@router.get("/{tournament_id}/leaderboard")
async def get_tournament_leaderboard(tournament_id: str):
    """Get live tournament leaderboard"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                tp.id as participant_id,
                tp.user_id,
                tp.guest_name,
                tp.is_guest,
                u.username,
                tgs.stage,
                tgs.score,
                tgs.time_taken,
                tgs.status,
                tgs.completed_at
            FROM tournament_participants tp
            LEFT JOIN users u ON tp.user_id = u.id
            LEFT JOIN tournament_game_sessions tgs ON tp.id = tgs.participant_id
            WHERE tp.tournament_id = ?
            ORDER BY 
                tgs.status DESC,
                tgs.stage DESC,
                tgs.score DESC,
                tgs.time_taken ASC
        """, (tournament_id,))
        
        participants = cursor.fetchall()
        
        leaderboard = []
        for i, participant in enumerate(participants, 1):
            leaderboard.append({
                "rank": i,
                "username": participant["username"] if not participant["is_guest"] else participant["guest_name"],
                "is_guest": participant["is_guest"],
                "stage": participant["stage"] or 1,
                "score": participant["score"] or 0,
                "time_taken": participant["time_taken"] or 0,
                "status": participant["status"] or "active",
                "completed_at": participant["completed_at"]
            })
        
        return {"leaderboard": leaderboard}
    
    finally:
        conn.close()


@router.post("/{tournament_id}/submit-answer")
async def submit_tournament_answer(
    tournament_id: str,
    answer: dict,
    current_user: str = Depends(get_current_user)
):
    """Submit answer for tournament game"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get user ID
        cursor.execute("SELECT id FROM users WHERE username = ?", (current_user,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get participant game session
        cursor.execute("""
            SELECT tgs.*, tp.id as participant_id
            FROM tournament_game_sessions tgs
            JOIN tournament_participants tp ON tgs.participant_id = tp.id
            WHERE tgs.tournament_id = ? AND tp.user_id = ? AND tgs.status = 'active'
        """, (tournament_id, user["id"]))
        
        game_session = cursor.fetchone()
        if not game_session:
            raise HTTPException(status_code=404, detail="No active game session found")
        
        # Debug: Check what columns exist in game_session
        print(f"Game session keys: {list(game_session.keys()) if game_session else 'None'}")
        print(f"Game session data: {dict(game_session) if game_session else 'None'}")
        
        # Get or initialize session data for the AI workflow
        session_data_raw = game_session["session_data"] if game_session["session_data"] else None
        session_data = json.loads(session_data_raw) if session_data_raw else {
            "conversation_history": [],
            "character_mood": "helpful", 
            "resistance_level": 1,
            "failed_attempts": 0,
            "extracted_keys": []
        }
        
        # Create GameState object for the AI workflow
        game_state = GameState(
            stage=game_session["stage"],
            score=game_session["score"],
            attempts=0,  # We'll track this separately in tournament
            extracted_keys=session_data.get("extracted_keys", []),
            user_input=answer.get("message", ""),
            bot_response="",
            game_over=False,
            success=False,
            conversation_history=session_data.get("conversation_history", []),
            character_mood=session_data.get("character_mood", "helpful"),
            resistance_level=session_data.get("resistance_level", 1),
            failed_attempts=session_data.get("failed_attempts", 0)
        )
        
        # Process through the AI workflow (same as main game)
        print(f"Invoking AI workflow with game_state: {game_state}")
        result = tournament_game_app.invoke(game_state)
        print(f"AI workflow result: {result}")
        
        # Update session data with new state
        new_session_data = {
            "conversation_history": result["conversation_history"],
            "character_mood": result["character_mood"],
            "resistance_level": result["resistance_level"],
            "failed_attempts": result["failed_attempts"],
            "extracted_keys": result["extracted_keys"]
        }
        
        print(f"Processing stage completion for stage {game_session['stage']}")
        print(f"Session extracted keys: {session_data.get('extracted_keys', [])}")
        print(f"AI result extracted keys: {result['extracted_keys']}")
        
        try:
            # Check if stage is completed (all keys found for current stage)
            if game_session["stage"] not in STAGES:
                raise ValueError(f"Invalid stage: {game_session['stage']}")
                
            current_stage_config = STAGES[game_session["stage"]]
            
            # Get previous keys to detect NEW keys found in this turn
            previous_keys = session_data.get("extracted_keys", [])
            current_stage_keys = []
            
            # Find keys that belong to current stage and are in the extracted keys
            for key in current_stage_config["keys"]:
                if key in result["extracted_keys"]:
                    current_stage_keys.append(key)
            
            # Find new keys found in this turn
            new_keys_this_turn = []
            for key in result["extracted_keys"]:
                if key not in previous_keys:
                    new_keys_this_turn.append(key)
            
            stage_completed = len(current_stage_keys) >= len(current_stage_config["keys"])
            
            print(f"Processing stage completion for stage {game_session['stage']}")
            print(f"Session extracted keys: {previous_keys}")
            print(f"AI result extracted keys: {result['extracted_keys']}")
            print(f"Current stage keys found: {current_stage_keys}")
            print(f"New keys this turn: {new_keys_this_turn}")
            print(f"Stage completed: {stage_completed}")
            
        except Exception as e:
            print(f"Error in stage validation: {e}, stage: {game_session['stage']}")
            print(f"Available stages: {list(STAGES.keys())}")
            # Fallback to basic response
            ai_result = {
                "response": result.get("bot_response", "System error occurred."),
                "stage_completed": False,
                "score": 0,
                "total_score": game_session["score"],
                "extracted_keys": result.get("extracted_keys", []),
                "keys_found": 0,
                "total_keys": 3
            }
            
            conn.commit()
            return {
                "status": "continue",
                "result": ai_result,
                "current_stage": game_session["stage"]
            }
        
        # Initialize status variable
        status = "continue"
        current_stage = game_session["stage"]
        
        if stage_completed:
            try:
                # In tournament mode, completing any stage ends the tournament
                # Update this player's status to completed
                cursor.execute("""
                    UPDATE tournament_game_sessions 
                    SET status = 'completed', completed_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), game_session["id"]))
                
                # Update tournament status to completed
                cursor.execute("""
                    UPDATE tournaments 
                    SET status = 'completed'
                    WHERE id = ?
                """, (tournament_id,))
                
                # Calculate final score with stage completion bonus
                difficulty = current_stage_config.get("difficulty", "EASY")
                difficulty_multipliers = {
                    "EASY": 1.0,
                    "MEDIUM": 1.2, 
                    "HARD": 1.5,
                    "VERY HARD": 2.0,
                    "MASTER": 3.0
                }
                score_multiplier = difficulty_multipliers.get(difficulty, 1.0)
                stage_completion_bonus = int(200 * score_multiplier)  # Bigger bonus for winning
                
                final_score = (game_session["score"] or 0) + stage_completion_bonus
                
                # Update final score
                cursor.execute("""
                    UPDATE tournament_game_sessions 
                    SET score = ?
                    WHERE id = ?
                """, (final_score, game_session["id"]))
                
                status = "tournament_won"
                current_stage = game_session["stage"]
                response_message = f"� TOURNAMENT WINNER! You completed Stage {current_stage} first! Final Score: {final_score}"
                    
                ai_result = {
                    "response": response_message,
                    "stage_completed": True,
                    "tournament_won": True,
                    "score": stage_completion_bonus,
                    "total_score": final_score,
                    "extracted_keys": result["extracted_keys"],
                    "keys_found": len(current_stage_keys),
                    "total_keys": len(current_stage_config["keys"])
                }
            except Exception as e:
                print(f"Error in tournament completion logic: {e}")
                # Fallback response
                ai_result = {
                    "response": "You completed the stage and won the tournament!",
                    "stage_completed": True,
                    "tournament_won": True,
                    "score": 200,
                    "total_score": (game_session["score"] or 0) + 200,
                    "extracted_keys": result["extracted_keys"],
                    "keys_found": len(current_stage_keys),
                    "total_keys": len(current_stage_config["keys"])
                }
        else:
            try:
                # Continue with current stage - update session data and score from AI workflow
                updated_score = result.get("score", game_session["score"] or 0)  # Fallback to current score
                cursor.execute("""
                    UPDATE tournament_game_sessions 
                    SET session_data = ?, score = ?
                    WHERE id = ?
                """, (json.dumps(new_session_data), updated_score, game_session["id"]))
                
                status = "continue"
                current_stage = game_session["stage"]
                
                # Calculate score gained in this turn
                score_gained = updated_score - (game_session["score"] or 0)
                
                ai_result = {
                    "response": result.get("bot_response", "No response available."),
                    "stage_completed": False,
                    "score": score_gained,
                    "total_score": updated_score,
                    "extracted_keys": result.get("extracted_keys", []),
                    "keys_found": len(current_stage_keys),
                    "total_keys": len(current_stage_config.get("keys", []))
                }
            except Exception as e:
                print(f"Error in continue logic: {e}")
                # Fallback response
                ai_result = {
                    "response": result.get("bot_response", "Error occurred during processing."),
                    "stage_completed": False,
                    "score": 0,
                    "total_score": game_session["score"] or 0,
                    "extracted_keys": result.get("extracted_keys", []),
                    "keys_found": 0,
                    "total_keys": 3
                }
        
        # Log the event
        cursor.execute("""
            INSERT INTO tournament_events (
                tournament_id, participant_id, event_type, event_data
            ) VALUES (?, ?, 'answer_submitted', ?)
        """, (tournament_id, game_session["participant_id"], 
              json.dumps({"answer": answer, "result": ai_result})))
        
        conn.commit()
        
        # Broadcast detailed progress update for opponent notifications
        try:
            if status == "tournament_won":
                # Tournament ended - broadcast winner announcement to all players
                broadcast_data = {
                    "type": "tournament_ended",
                    "winner": current_user,
                    "stage": current_stage,
                    "final_score": ai_result.get("total_score", 0),
                    "message": f"🏆 Tournament Winner: {current_user}!"
                }
            else:
                # Regular progress update
                broadcast_data = {
                    "type": "progress_update", 
                    "username": current_user,
                    "stage": current_stage,
                    "status": status,
                    "keys_found": len(current_stage_keys),
                    "total_keys": len(current_stage_config.get("keys", [])),
                    "score": ai_result.get("total_score", 0)
                }
                
                # Add specific notifications for key extraction (only for NEW keys found this turn)
                if len(new_keys_this_turn) > 0:
                    total_keys_found = len(current_stage_keys)
                    broadcast_data["notification"] = f"{current_user} unlocked Key {total_keys_found}!"
                    
                    # Check if opponent is close to completing the stage
                    total_stage_keys = len(current_stage_config.get("keys", []))
                    if total_keys_found == total_stage_keys - 1:
                        broadcast_data["warning"] = f"{current_user} is close to winning the tournament!"
            
            await manager.broadcast_to_tournament(tournament_id, broadcast_data)
        except Exception as e:
            print(f"Error in broadcast: {e}")
            # Continue without broadcasting
        
        return {
            "status": status,
            "result": ai_result,
            "current_stage": current_stage
        }
    
    except Exception as e:
        conn.rollback()
        print(f"Tournament submit-answer error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{tournament_id}/results")
async def get_tournament_results(tournament_id: str):
    """Get final tournament results"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get tournament info
        cursor.execute("SELECT * FROM tournaments WHERE id = ?", (tournament_id,))
        tournament = cursor.fetchone()
        if not tournament:
            raise HTTPException(status_code=404, detail="Tournament not found")
        
        # Get final results
        cursor.execute("""
            SELECT 
                tp.id as participant_id,
                tp.user_id,
                tp.guest_name,
                tp.is_guest,
                u.username,
                tgs.stage,
                tgs.score,
                tgs.time_taken,
                tgs.status,
                tgs.completed_at
            FROM tournament_participants tp
            LEFT JOIN users u ON tp.user_id = u.id
            LEFT JOIN tournament_game_sessions tgs ON tp.id = tgs.participant_id
            WHERE tp.tournament_id = ?
            ORDER BY 
                tgs.score DESC,
                tgs.stage DESC,
                tgs.time_taken ASC
        """, (tournament_id,))
        
        results = cursor.fetchall()
        
        final_results = []
        for i, result in enumerate(results, 1):
            final_results.append({
                "rank": i,
                "username": result["username"] if not result["is_guest"] else result["guest_name"],
                "is_guest": result["is_guest"],
                "stage": result["stage"] or 1,
                "score": result["score"] or 0,
                "time_taken": result["time_taken"] or 0,
                "status": result["status"] or "active",
                "completed_at": result["completed_at"]
            })
        
        return {
            "tournament": dict(tournament),
            "results": final_results,
            "winner": final_results[0] if final_results else None
        }
    
    finally:
        conn.close()


@router.websocket("/{tournament_id}/ws")
async def tournament_websocket(websocket: WebSocket, tournament_id: str):
    """WebSocket endpoint for real-time tournament updates"""
    await manager.connect(websocket, tournament_id)
    try:
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, tournament_id)
