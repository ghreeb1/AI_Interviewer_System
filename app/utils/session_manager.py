import uuid
import json
import os
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.models.session import InterviewSession, SessionStatus

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, storage_dir: str = "sessions"):
        self.storage_dir = storage_dir
        self.active_sessions: Dict[str, InterviewSession] = {}
        
        # Create storage directory if it doesn't exist
        os.makedirs(storage_dir, exist_ok=True)
    
    def create_session(self) -> str:
        """Create a new interview session"""
        session_id = str(uuid.uuid4())
        session = InterviewSession(session_id=session_id)
        
        self.active_sessions[session_id] = session
        self._save_session(session)
        
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Get session by ID"""
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # Try to load from storage
        session = self._load_session(session_id)
        if session:
            self.active_sessions[session_id] = session
        
        return session
    
    def update_session(self, session: InterviewSession) -> bool:
        """Update session data"""
        try:
            self.active_sessions[session.session_id] = session
            self._save_session(session)
            return True
        except Exception as e:
            logger.error(f"Error updating session {session.session_id}: {e}")
            return False
    
    def start_session(self, session_id: str) -> bool:
        """Start an interview session"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.ACTIVE
        session.start_time = datetime.now()
        
        return self.update_session(session)
    
    def end_session(self, session_id: str) -> bool:
        """End an interview session"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.status = SessionStatus.COMPLETED
        session.end_time = datetime.now()
        
        if session.start_time:
            duration = session.end_time - session.start_time
            session.duration_seconds = int(duration.total_seconds())
        
        return self.update_session(session)
    
    def is_session_expired(self, session_id: str) -> bool:
        """Check if session has exceeded time limit"""
        session = self.get_session(session_id)
        if not session or not session.start_time:
            return False
        
        elapsed = datetime.now() - session.start_time
        return elapsed.total_seconds() > session.max_duration_seconds
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            if session.start_time:
                elapsed = datetime.now() - session.start_time
                if elapsed.total_seconds() > session.max_duration_seconds:
                    session.status = SessionStatus.EXPIRED
                    expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.end_session(session_id)
            logger.info(f"Session {session_id} expired and cleaned up")
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its data"""
        try:
            # Remove from active sessions
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # Remove from storage
            session_file = os.path.join(self.storage_dir, f"{session_id}.json")
            if os.path.exists(session_file):
                os.remove(session_file)
            
            logger.info(f"Deleted session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False
    
    def _save_session(self, session: InterviewSession):
        """Save session to storage"""
        try:
            session_file = os.path.join(self.storage_dir, f"{session.session_id}.json")
            
            # Convert session to dict for JSON serialization
            session_dict = session.dict()

            def convert_datetimes(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, list):
                    return [convert_datetimes(item) for item in obj]
                if isinstance(obj, dict):
                    return {k: convert_datetimes(v) for k, v in obj.items()}
                return obj

            serializable = convert_datetimes(session_dict)

            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Error saving session {session.session_id}: {e}")
            raise
    
    def _load_session(self, session_id: str) -> Optional[InterviewSession]:
        """Load session from storage"""
        try:
            session_file = os.path.join(self.storage_dir, f"{session_id}.json")
            
            if not os.path.exists(session_file):
                return None
            
            with open(session_file, 'r') as f:
                session_dict = json.load(f)
            
            # Handle datetime deserialization
            datetime_fields = ['start_time', 'end_time']
            for field in datetime_fields:
                if session_dict.get(field):
                    session_dict[field] = datetime.fromisoformat(session_dict[field])
            
            # Handle nested datetime fields
            if session_dict.get('cv_data', {}).get('parsed_at'):
                session_dict['cv_data']['parsed_at'] = datetime.fromisoformat(
                    session_dict['cv_data']['parsed_at']
                )
            
            for message in session_dict.get('messages', []):
                if message.get('timestamp'):
                    message['timestamp'] = datetime.fromisoformat(message['timestamp'])
            
            for metric in session_dict.get('behavior_metrics', []):
                if metric.get('timestamp'):
                    metric['timestamp'] = datetime.fromisoformat(metric['timestamp'])
            
            return InterviewSession(**session_dict)
            
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None
    
    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get session summary data"""
        session = self.get_session(session_id)
        if not session:
            return None
        
        return {
            'session_id': session.session_id,
            'status': session.status,
            'duration_seconds': session.duration_seconds,
            'message_count': len(session.messages),
            'cv_uploaded': session.cv_data is not None,
            'behavior_metrics_count': len(session.behavior_metrics)
        }

