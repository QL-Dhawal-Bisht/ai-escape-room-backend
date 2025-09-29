from fastapi import APIRouter
import json

from app.models.schemas import LeaderboardEntry
from app.database.connection import get_db
from app.game.stages import STAGES

router = APIRouter(tags=["stats"])


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 15):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Get latest session for each user with their progress
        cursor.execute("""
            SELECT 
                u.username,
                u.id as user_id,
                COALESCE(latest_session.stage, 1) as current_stage,
                COALESCE(latest_session.score, 0) as score,
                COALESCE(latest_session.extracted_keys, '[]') as extracted_keys_json,
                COALESCE(latest_session.game_over, 0) as game_over,
                COALESCE(latest_session.success, 0) as success,
                COALESCE(latest_session.updated_at, u.created_at) as last_active
            FROM users u
            LEFT JOIN (
                SELECT 
                    gs1.user_id,
                    gs1.stage,
                    gs1.score,
                    gs1.extracted_keys,
                    gs1.game_over,
                    gs1.success,
                    gs1.updated_at
                FROM game_sessions gs1
                WHERE gs1.updated_at = (
                    SELECT MAX(gs2.updated_at)
                    FROM game_sessions gs2
                    WHERE gs2.user_id = gs1.user_id
                )
            ) latest_session ON u.id = latest_session.user_id
            ORDER BY 
                -- Prioritize completed players, then by normalized score
                CASE WHEN latest_session.game_over = 1 AND latest_session.success = 1 THEN 1000000 + latest_session.score
                     ELSE latest_session.stage * 100000 + latest_session.score END DESC,
                latest_session.updated_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        
        leaderboard_entries = []
        for row in results:
            try:
                # Parse extracted keys JSON
                extracted_keys = json.loads(row["extracted_keys_json"])
            except (json.JSONDecodeError, TypeError):
                extracted_keys = []
            
            current_stage = max(1, row["current_stage"])
            
            # Calculate accurate progress based on game state
            if row["game_over"] and row["success"]:
                # Game completed successfully
                completion_status = "completed"
                stages_completed = len(STAGES)  # Completed all stages
                
                # For completed players: show total keys from all stages
                keys_found = len(extracted_keys)
                total_keys_possible = sum(len(STAGES[stage]["keys"]) for stage in STAGES)
                
                # Completed players get full score
                display_score = row["score"]
                
            elif row["game_over"] and not row["success"]:
                # Game abandoned or failed
                completion_status = "abandoned"
                
                # Count how many stages were actually completed
                stages_completed = 0
                keys_by_stage = {}
                
                # Group keys by stage to count completed stages
                for key in extracted_keys:
                    for stage_num, stage_data in STAGES.items():
                        if key in stage_data["keys"]:
                            if stage_num not in keys_by_stage:
                                keys_by_stage[stage_num] = []
                            keys_by_stage[stage_num].append(key)
                
                # Count completed stages (all keys found)
                for stage_num, found_keys in keys_by_stage.items():
                    if len(found_keys) == len(STAGES[stage_num]["keys"]):
                        stages_completed += 1
                
                # For abandoned games: show progress in current stage
                current_stage_keys = []
                if current_stage in STAGES:
                    for key in extracted_keys:
                        if key in STAGES[current_stage]["keys"]:
                            current_stage_keys.append(key)
                
                keys_found = len(current_stage_keys)
                total_keys_possible = len(STAGES.get(current_stage, {}).get("keys", []))
                
                # Abandoned players get reduced score based on progress
                stage_multiplier = sum(0.8 ** (i-1) for i in range(1, current_stage))
                display_score = int(row["score"] * stage_multiplier)
                
            else:
                # Active game
                completion_status = "active"
                
                # Count completed stages
                stages_completed = 0
                keys_by_stage = {}
                
                # Group keys by stage
                for key in extracted_keys:
                    for stage_num, stage_data in STAGES.items():
                        if key in stage_data["keys"]:
                            if stage_num not in keys_by_stage:
                                keys_by_stage[stage_num] = []
                            keys_by_stage[stage_num].append(key)
                
                # Count completed stages
                for stage_num, found_keys in keys_by_stage.items():
                    if len(found_keys) == len(STAGES[stage_num]["keys"]):
                        stages_completed += 1
                
                # For active games: show progress in current stage only
                current_stage_keys = []
                if current_stage in STAGES:
                    for key in extracted_keys:
                        if key in STAGES[current_stage]["keys"]:
                            current_stage_keys.append(key)
                
                keys_found = len(current_stage_keys)
                total_keys_possible = len(STAGES.get(current_stage, {}).get("keys", []))
                
                # Active players get current score
                display_score = row["score"]
            
            leaderboard_entries.append(LeaderboardEntry(
                username=row["username"],
                score=display_score,
                current_stage=current_stage,
                stages_completed=stages_completed,
                keys_found=keys_found,
                total_keys_possible=total_keys_possible,
                is_active=(completion_status == "active"),
                last_active=row["last_active"],
                completion_status=completion_status
            ))
        
        return leaderboard_entries
    
    finally:
        conn.close()


@router.get("/stats/global")
async def get_global_stats():
    """Get global game statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Total users
        cursor.execute("SELECT COUNT(*) as total_users FROM users")
        total_users = cursor.fetchone()["total_users"]
        
        # Total games
        cursor.execute("SELECT COUNT(*) as total_games FROM game_sessions WHERE game_over = TRUE")
        total_games = cursor.fetchone()["total_games"]
        
        # Successful completions
        cursor.execute("SELECT COUNT(*) as successful_games FROM game_sessions WHERE game_over = TRUE AND success = TRUE")
        successful_games = cursor.fetchone()["successful_games"]
        
        # Average score
        cursor.execute("SELECT AVG(final_score) as avg_score FROM game_results")
        avg_score_result = cursor.fetchone()
        avg_score = round(avg_score_result["avg_score"] or 0, 2)
        
        # Highest score
        cursor.execute("SELECT MAX(final_score) as max_score FROM game_results")
        max_score = cursor.fetchone()["max_score"] or 0
        
        # Success rate
        success_rate = (successful_games / total_games * 100) if total_games > 0 else 0
        
        return {
            "total_users": total_users,
            "total_games": total_games,
            "successful_games": successful_games,
            "success_rate": round(success_rate, 2),
            "average_score": avg_score,
            "highest_score": max_score
        }
    
    finally:
        conn.close()
