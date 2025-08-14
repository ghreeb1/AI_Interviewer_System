from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SessionStatus(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"

class CVData(BaseModel):
    filename: str
    content: str
    skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    contact_info: Dict[str, str] = Field(default_factory=dict)
    parsed_at: datetime

class InterviewMessage(BaseModel):
    role: str  # "interviewer" or "candidate"
    content: str
    timestamp: datetime
    audio_duration: Optional[float] = None

class BehaviorMetrics(BaseModel):
    face_detected: bool = False
    eye_contact_score: float = 0.0
    posture_score: float = 0.0
    gesture_count: int = 0
    attention_score: float = 0.0
    timestamp: datetime

class InterviewSession(BaseModel):
    session_id: str
    status: SessionStatus = SessionStatus.CREATED
    cv_data: Optional[CVData] = None
    messages: List[InterviewMessage] = Field(default_factory=list)
    behavior_metrics: List[BehaviorMetrics] = Field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: int = 0
    max_duration_seconds: int = 900  # 15 minutes
    # Interview plan
    questions: List[str] = Field(default_factory=list)
    total_questions: int = 0
    questions_asked: int = 0
    
    class Config:
        use_enum_values = True

class SessionSummary(BaseModel):
    session_id: str
    duration_minutes: float
    total_messages: int
    cv_match_score: float
    behavior_summary: Dict[str, Any]
    transcript: List[InterviewMessage]
    recommendations: List[str]

