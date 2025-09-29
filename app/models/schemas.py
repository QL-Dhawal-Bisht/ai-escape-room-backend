from pydantic import BaseModel
from typing import List


class UserRegister(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class MessageRequest(BaseModel):
    message: str


class GameResponse(BaseModel):
    session_id: str
    stage: int
    character: str
    character_mood: str
    bot_response: str
    extracted_keys: List[str]
    score: int
    attempts: int
    resistance_level: int
    stage_complete: bool
    game_over: bool
    total_keys_in_stage: int
    keys_found_in_stage: int
    should_refresh: bool = False  # Flag to trigger page refresh after stage completion


class UserProfile(BaseModel):
    username: str
    email: str
    total_score: int
    games_played: int
    best_score: int
    created_at: str


class LeaderboardEntry(BaseModel):
    username: str
    score: int
    current_stage: int
    stages_completed: int
    keys_found: int
    total_keys_possible: int  # Keys in current stage OR total keys if completed
    is_active: bool
    last_active: str
    completion_status: str  # "active", "completed", "abandoned"
