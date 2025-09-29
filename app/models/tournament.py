from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class TournamentCreate(BaseModel):
    stage: int = 1
    time_limit: int = 600  # 10 minutes
    tournament_mode: str = "head_to_head"


class TournamentJoin(BaseModel):
    room_code: str
    guest_name: Optional[str] = None  # For guest users


class TournamentParticipant(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str] 
    is_guest: bool = False
    guest_name: Optional[str]
    is_ready: bool = False
    final_score: int = 0
    keys_found: int = 0
    completion_time: Optional[int]
    position: Optional[int]


class Tournament(BaseModel):
    id: str
    room_code: str
    host_user_id: int
    stage: int
    status: str  # waiting, ready, active, completed, cancelled
    max_participants: int = 2
    tournament_mode: str = "head_to_head"
    time_limit: int = 600
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    winner_user_id: Optional[int]
    participants: List[TournamentParticipant] = []


class TournamentGameState(BaseModel):
    tournament_id: str
    participant_id: int
    current_keys: List[str] = []
    score: int = 0
    attempts: int = 0
    is_active: bool = False
    start_time: Optional[str]
    time_remaining: Optional[int]


class TournamentEvent(BaseModel):
    tournament_id: str
    participant_id: int
    event_type: str  # key_found, ready_status, game_complete, etc.
    event_data: Dict[Any, Any] = {}
    created_at: str


class TournamentProgress(BaseModel):
    participant_id: int
    username: Optional[str]
    guest_name: Optional[str]
    keys_found: int = 0
    total_keys: int = 3
    current_score: int = 0
    is_complete: bool = False
    completion_time: Optional[int]


class TournamentStatus(BaseModel):
    tournament: Tournament
    participants_progress: List[TournamentProgress]
    time_remaining: Optional[int]
    current_events: List[TournamentEvent] = []


class TournamentResults(BaseModel):
    tournament_id: str
    winner: Optional[TournamentParticipant]
    final_standings: List[TournamentParticipant]
    total_duration: int
    statistics: Dict[str, Any] = {}
