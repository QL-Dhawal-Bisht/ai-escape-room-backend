from fastapi import APIRouter, HTTPException
import json

from app.models.schemas import LeaderboardEntry
from app.database.mongodb import get_database
from app.game.stages import STAGES

router = APIRouter(tags=["stats"])


@router.get("/leaderboard")
async def get_leaderboard(limit: int = 15):
    try:
        db = get_database()

        # Get all users
        users = await db.users.find({}).to_list(length=None)

        leaderboard_entries = []

        for user in users:
            user_id = user.get("id", str(user["_id"]))
            username = user["username"]

            # Get latest game session for this user
            latest_session = await db.game_sessions.find_one(
                {"user_id": user_id},
                sort=[("updated_at", -1)]
            )

            if latest_session:
                current_stage = latest_session.get("stage", 1)
                score = latest_session.get("score", 0)
                extracted_keys = latest_session.get("extracted_keys", [])
                game_over = latest_session.get("game_over", False)
                success = latest_session.get("success", False)
                last_active = latest_session.get("updated_at", user.get("created_at"))
            else:
                # User has no game sessions
                current_stage = 1
                score = 0
                extracted_keys = []
                game_over = False
                success = False
                last_active = user.get("created_at")

            # Calculate progress and status
            row = {
                "username": username,
                "current_stage": current_stage,
                "score": score,
                "extracted_keys": extracted_keys,
                "game_over": game_over,
                "success": success,
                "last_active": last_active
            }
            current_stage = max(1, row["current_stage"])
            extracted_keys = row["extracted_keys"]
            
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
            
            # Convert datetime to string for Pydantic
            last_active_str = row["last_active"].isoformat() if row["last_active"] else None

            leaderboard_entries.append(LeaderboardEntry(
                username=row["username"],
                score=display_score,
                current_stage=current_stage,
                stages_completed=stages_completed,
                keys_found=keys_found,
                total_keys_possible=total_keys_possible,
                is_active=(completion_status == "active"),
                last_active=last_active_str,
                completion_status=completion_status
            ))
        
        # Sort entries by score (highest first) and limit results
        leaderboard_entries.sort(key=lambda x: (
            1000000 + x.score if x.completion_status == "completed" else x.current_stage * 100000 + x.score
        ), reverse=True)

        return leaderboard_entries[:limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/global")
async def get_global_stats():
    """Get global game statistics"""
    try:
        db = get_database()

        # Total users
        total_users = await db.users.count_documents({})

        # Total games
        total_games = await db.game_sessions.count_documents({"game_over": True})

        # Successful completions
        successful_games = await db.game_sessions.count_documents({"game_over": True, "success": True})

        # Average score from game results
        avg_score_pipeline = [
            {"$group": {"_id": None, "avg_score": {"$avg": "$final_score"}}}
        ]
        avg_score_result = await db.game_results.aggregate(avg_score_pipeline).to_list(length=1)
        avg_score = round(avg_score_result[0]["avg_score"] if avg_score_result else 0, 2)

        # Highest score
        max_score_pipeline = [
            {"$group": {"_id": None, "max_score": {"$max": "$final_score"}}}
        ]
        max_score_result = await db.game_results.aggregate(max_score_pipeline).to_list(length=1)
        max_score = max_score_result[0]["max_score"] if max_score_result else 0

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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
