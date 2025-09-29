from typing import TypedDict, List, Optional


class GameState(TypedDict):
    stage: int
    score: int
    attempts: int
    extracted_keys: list
    user_input: str
    bot_response: str
    game_over: bool
    success: bool
    conversation_history: list
    character_mood: str
    resistance_level: int
    failed_attempts: int
    new_stage_start: bool  # Flag to indicate first message of a new stage
    stage_just_completed: bool  # Flag to indicate stage was just completed
    user_id: Optional[int]  # User ID for security checks
    session_id: Optional[str]  # Session ID for logging
