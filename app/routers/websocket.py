from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import logging
import asyncio
import base64
from typing import Dict, List

from app.services.speech_service_simple import SpeechService
from app.services.vision_service_simple import VisionService
from app.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)

# Initialize services
speech_service = SpeechService()
vision_service = VisionService()
session_manager = SessionManager()

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected for session: {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected for session: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to {session_id}: {e}")
                self.disconnect(session_id)

manager = ConnectionManager()

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Main WebSocket endpoint for real-time communication"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get('type')
            
            if message_type == 'audio':
                await handle_audio_message(session_id, message)
            elif message_type == 'video':
                await handle_video_frame(session_id, message)
            elif message_type == 'ping':
                await manager.send_message(session_id, {'type': 'pong'})
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(session_id)

async def handle_audio_message(session_id: str, message: dict):
    """Handle audio data for speech-to-text processing"""
    try:
        # Get audio data
        audio_data_b64 = message.get('data')
        if not audio_data_b64:
            return
        
        # Decode base64 audio data
        audio_data = base64.b64decode(audio_data_b64)
        
        # Convert speech to text
        # Quick return if speech is disabled to avoid blocking UX
        transcribed_text = await speech_service.speech_to_text(audio_data)
        
        if transcribed_text and transcribed_text.strip():
            # Send transcription back to client
            await manager.send_message(session_id, {
                'type': 'transcription',
                'text': transcribed_text
            })
            
            # Get session for AI response
            session = session_manager.get_session(session_id)
            if session and session.cv_data:
                from app.services.ai_interviewer import AIInterviewer
                ai_interviewer = AIInterviewer()

                # Generate AI response off the event loop (blocking HTTP)
                cv_data_dict = session.cv_data.dict()
                conversation_history = [msg.dict() for msg in session.messages]

                loop = asyncio.get_running_loop()
                ai_response = await loop.run_in_executor(
                    None,
                    lambda: ai_interviewer.get_interview_response(
                        cv_data_dict, conversation_history, transcribed_text
                    )
                )
                
                # Convert AI response to speech
                audio_response_b64 = None
                try:
                    # TTS may block; keep event loop free
                    audio_response = await speech_service.text_to_speech(ai_response)
                    audio_response_b64 = base64.b64encode(audio_response).decode('utf-8') if audio_response else None
                except Exception as tts_err:
                    logger.warning(f"TTS unavailable or failed: {tts_err}")
                
                # Send AI response back to client
                await manager.send_message(session_id, {
                    'type': 'ai_response',
                    'text': ai_response,
                    'audio': audio_response_b64
                })
                
                # Update session with messages
                from app.models.session import InterviewMessage
                from datetime import datetime
                
                user_message = InterviewMessage(
                    role="candidate",
                    content=transcribed_text,
                    timestamp=datetime.now()
                )
                ai_message = InterviewMessage(
                    role="interviewer",
                    content=ai_response,
                    timestamp=datetime.now()
                )
                
                session.messages.extend([user_message, ai_message])
                session_manager.update_session(session)
        
    except Exception as e:
        logger.error(f"Error handling audio message: {e}")
        await manager.send_message(session_id, {
            'type': 'error',
            'message': 'Error processing audio'
        })

async def handle_video_frame(session_id: str, message: dict):
    """Handle video frame for computer vision analysis"""
    try:
        # Get video frame data
        frame_data_b64 = message.get('data')
        if not frame_data_b64:
            return
        
        # Decode base64 image data (simplified - no actual processing)
        frame_data = base64.b64decode(frame_data_b64)
        
        # Analyze frame with computer vision (placeholder)
        metrics = vision_service.analyze_frame(None)  # Pass None since we're not processing
        
        # Send metrics back to client
        await manager.send_message(session_id, {
            'type': 'vision_metrics',
            'metrics': metrics
        })
        
        # Update session with behavior metrics
        session = session_manager.get_session(session_id)
        if session:
            from app.models.session import BehaviorMetrics
            from datetime import datetime
            
            behavior_metrics = BehaviorMetrics(
                face_detected=metrics.get('face_detected', False),
                eye_contact_score=metrics.get('eye_contact_score', 0.0),
                posture_score=metrics.get('posture_score', 0.0),
                gesture_count=metrics.get('gesture_count', 0),
                attention_score=metrics.get('attention_score', 0.0),
                timestamp=datetime.now()
            )
            
            session.behavior_metrics.append(behavior_metrics)
            session_manager.update_session(session)
        
    except Exception as e:
        logger.error(f"Error handling video frame: {e}")
        await manager.send_message(session_id, {
            'type': 'error',
            'message': 'Error processing video frame'
        })

@router.websocket("/ws/audio/{session_id}")
async def audio_websocket(websocket: WebSocket, session_id: str):
    """Dedicated WebSocket endpoint for audio streaming"""
    await websocket.accept()
    
    try:
        while True:
            # Receive audio data
            audio_data = await websocket.receive_bytes()
            
            # Process audio
            transcribed_text = await speech_service.speech_to_text(audio_data)
            
            if transcribed_text and transcribed_text.strip():
                # Send transcription
                await websocket.send_json({
                    'type': 'transcription',
                    'text': transcribed_text
                })
                
    except WebSocketDisconnect:
        logger.info(f"Audio WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"Audio WebSocket error for session {session_id}: {e}")

@router.websocket("/ws/video/{session_id}")
async def video_websocket(websocket: WebSocket, session_id: str):
    """Dedicated WebSocket endpoint for video streaming"""
    await websocket.accept()
    
    try:
        while True:
            # Receive video frame
            frame_data = await websocket.receive_bytes()
            
            # Analyze frame (placeholder)
            metrics = vision_service.analyze_frame(None)
            
            # Send metrics
            await websocket.send_json({
                'type': 'metrics',
                'data': metrics
            })
                
    except WebSocketDisconnect:
        logger.info(f"Video WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"Video WebSocket error for session {session_id}: {e}")

