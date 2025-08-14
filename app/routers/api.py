from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks, Form
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime
import asyncio
import re
import difflib
from concurrent.futures import ThreadPoolExecutor
import traceback

from app.services.cv_parser_simple import CVParser
from app.services.ai_interviewer import AIInterviewer
from app.utils.session_manager import SessionManager
from app.models.session import InterviewMessage, BehaviorMetrics, CVData # Ensure these are properly imported and defined as Pydantic models

# Configure logging for better visibility of errors
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services with error handling. This ensures the application won't start
# if crucial dependencies fail to load, preventing runtime issues.
try:
    cv_parser = CVParser()
    ai_interviewer = AIInterviewer()
    session_manager = SessionManager()
    logger.info("Services initialized successfully.")
except Exception as e:
    logger.critical(f"Failed to initialize services: {e}", exc_info=True)
    raise # Re-raise to prevent server from starting without essential services

router = APIRouter(prefix="/api", tags=["api"])

# Thread pool for CPU-bound background tasks like AI processing or heavy parsing.
# Adjust max_workers based on available CPU cores and expected load.
executor = ThreadPoolExecutor(max_workers=5)

def safe_dict_get(data: Dict, key: str, default=None):
    """Safely get value from dictionary with proper type checking.
       Handles cases where data might not be a dictionary.
    """
    try:
        return data.get(key, default) if isinstance(data, dict) else default
    except Exception:
        return default

def validate_session_id(session_id: str) -> str:
    """Validate session ID format and presence."""
    if not session_id or not isinstance(session_id, str):
        logger.warning(f"Invalid session ID type or empty: {session_id}")
        raise HTTPException(status_code=400, detail="Invalid session ID: Must be a non-empty string.")
    
    # Basic format validation: alphanumeric characters, hyphen, underscore, 8-64 length
    # This pattern helps prevent simple injection or malformed IDs.
    if not re.match(r'^[a-zA-Z0-9\-_]{8,64}$', session_id):
        logger.warning(f"Invalid session ID format: {session_id}")
        raise HTTPException(status_code=400, detail="Invalid session ID format.")
    
    return session_id.strip()

def _generate_initial_question(session_id: str) -> None:
    """
    Background task to generate the first interviewer message without blocking the request.
    This task updates the session asynchronously.
    """
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            logger.warning(f"Session {session_id_validated} not found during initial question generation.")
            return

        if not session.cv_data:
            logger.warning(f"No CV data found for session {session_id_validated}. Cannot generate tailored initial questions.")
            # Fallback to a generic intro if no CV data
            questions_to_use = ["Tell me about yourself and your background."]
        else:
            # Generate questions if not present or explicitly re-generating
            questions_to_use = getattr(session, 'questions', []) or []
            if not questions_to_use:
                try:
                    # Use model_dump() for Pydantic v2, .dict() for Pydantic v1
                    cv_data_for_ai = session.cv_data.model_dump() if hasattr(session.cv_data, 'model_dump') else session.cv_data.dict() if hasattr(session.cv_data, 'dict') else {}
                    generated_questions = ai_interviewer.generate_interview_questions(cv_data_for_ai)
                    
                    total_qs_configured = getattr(session, 'total_questions', 0)
                    if isinstance(total_qs_configured, int) and total_qs_configured > 0:
                        questions_to_use = generated_questions[:total_qs_configured]
                    else:
                        questions_to_use = generated_questions
                    
                    if not questions_to_use: # Fallback if AI returns no questions
                        logger.warning(f"AI interviewer returned no questions for session {session_id_validated}. Using generic.")
                        questions_to_use = ["Tell me about yourself and your background."]

                    session.questions = questions_to_use # Update session with generated plan
                    logger.info(f"Generated {len(questions_to_use)} interview questions for session {session_id_validated}.")

                except Exception as gen_err:
                    logger.error(f"Failed to generate question plan for session {session_id_validated}: {gen_err}", exc_info=True)
                    questions_to_use = ["Tell me about yourself and your background."] # Fallback
                    session.questions = questions_to_use
        
        # Create initial message with introductory text and the first question.
        # Ensure 'questions' list has at least one item, either AI-generated or fallback.
        first_question = questions_to_use[0] if questions_to_use else "Tell me about yourself and your background."
        intro_text = f"Hello! Welcome to the virtual interview. {first_question}"

        initial_message = InterviewMessage(
            role="interviewer",
            content=intro_text.strip(),
            timestamp=datetime.now()
        )
        
        # Ensure messages list exists before appending
        if not hasattr(session, 'messages') or session.messages is None:
            session.messages = []
        
        session.messages.append(initial_message)
        session_manager.update_session(session)
        logger.info(f"Initial question generated and added to session {session_id_validated}.")
        
    except Exception as e:
        logger.error(f"Background initial question generation failed for session {session_id}: {e}", exc_info=True)

@router.post("/session/create")
async def create_session(duration_minutes: int = Form(15), total_questions: int = Form(8)):
    """Create a new interview session with optional duration and question count."""
    try:
        # Validate and clamp inputs for safety and consistency.
        # Durations mapping to seconds.
        allowed_durations = {10: 600, 15: 900, 30: 1800, 60: 3600}
        selected_duration_minutes = duration_minutes if duration_minutes in allowed_durations else 15
        max_duration_seconds = allowed_durations[selected_duration_minutes]
        
        # Clamp total_questions between reasonable limits (e.g., 3 to 20 questions)
        clamped_total_questions = max(3, min(20, int(total_questions)))

        session_id = session_manager.create_session()
        if not session_id:
            logger.critical("Failed to generate a new session ID.")
            raise HTTPException(status_code=500, detail="Failed to generate session ID")
            
        session = session_manager.get_session(session_id)
        if not session:
            logger.critical(f"Session with ID {session_id} was created but could not be retrieved immediately.")
            raise HTTPException(status_code=500, detail="Failed to retrieve created session")
        
        session.max_duration_seconds = max_duration_seconds
        session.total_questions = clamped_total_questions
        
        # Initialize all necessary session attributes to prevent potential None issues later.
        session.messages = []
        session.behavior_metrics = []
        session.questions_asked = 0
        session.cv_data = None # Explicitly set to None initially
        session.questions = [] # Question plan initialized as empty
            
        session_manager.update_session(session)
        logger.info(f"Session {session_id} created with max_duration: {max_duration_seconds}s, total_questions: {clamped_total_questions}.")
        
        return {
            "session_id": session_id,
            "status": "created",
            "max_duration_seconds": session.max_duration_seconds,
            "total_questions": session.total_questions
        }
        
    except HTTPException:
        raise # Re-raise FastAPI HTTP exceptions directly
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create session")

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session information."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Safely extract initial question
        initial_question = None
        messages = getattr(session, 'messages', []) 
        if messages and len(messages) > 0:
            first_message = messages[0]
            # Safely check for attributes that should exist on an InterviewMessage object
            if hasattr(first_message, 'role') and getattr(first_message, 'role') == 'interviewer' \
               and hasattr(first_message, 'content'):
                initial_question = first_message.content

        # Safely retrieve other session attributes, providing defaults
        questions = getattr(session, 'questions', []) 
        total_questions = getattr(session, 'total_questions', 8)
        questions_asked = getattr(session, 'questions_asked', 0)
        cv_uploaded = session.cv_data is not None
        session_status = getattr(session, 'status', 'created') # Default to 'created'
        session_duration = getattr(session, 'duration_seconds', 0)
        max_duration = getattr(session, 'max_duration_seconds', 900)

        logger.info(f"Retrieved session info for {session_id_validated}. Status: {session_status}")

        return {
            "session_id": session.session_id,
            "status": session_status,
            "cv_uploaded": cv_uploaded,
            "message_count": len(messages),
            "duration_seconds": session_duration,
            "max_duration_seconds": max_duration,
            "initial_question": initial_question,
            "questions": questions,
            "total_questions": total_questions,
            "questions_asked": questions_asked
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

@router.post("/session/{session_id}/upload-cv")
async def upload_cv(session_id: str, file: UploadFile = File(...)):
    """Upload and parse CV for the session."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session.status != 'created':
            # Disallow CV upload after the interview has started
            raise HTTPException(status_code=400, detail="CV can only be uploaded for a new session before starting the interview.")

        # Validate file existence
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided in the request.")
            
        # Validate file type using standard MIME types
        allowed_types = {
            'application/pdf': 'PDF',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
            'text/plain': 'TXT'
        }
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. Only PDF, DOCX, and TXT are supported."
            )
        
        # Read file content safely
        content = b""
        try:
            content = await file.read()
        except Exception as read_error:
            logger.error(f"Failed to read file content for session {session_id}: {read_error}", exc_info=True)
            raise HTTPException(status_code=400, detail="Failed to read file content. File might be corrupted.")
            
        # Validate file size
        if not content: # Check for empty content AFTER reading
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
            
        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")
        
        # Parse CV with robust error handling for the parsing service
        cv_data_parsed_dict = {}
        try:
            cv_data_parsed_dict = cv_parser.parse_cv(file.filename, content)
        except Exception as parse_error:
            logger.error(f"CV parsing failed for session {session_id}: {parse_error}", exc_info=True)
            raise HTTPException(status_code=400, detail="Failed to parse CV content. Ensure it's a valid document.")
        
        if not cv_data_parsed_dict or not isinstance(cv_data_parsed_dict, dict):
            logger.warning(f"CV parser returned invalid or empty data for session {session_id}. Data: {cv_data_parsed_dict}")
            raise HTTPException(status_code=400, detail="Invalid CV data parsed. Could not extract meaningful information.")
        
        # Update session with CV data. Using Pydantic's CVData model for type safety.
        try:
            session.cv_data = CVData(**cv_data_parsed_dict)
            logger.info(f"CV successfully parsed and stored for session {session_id_validated}.")
        except Exception as cv_model_error:
            logger.error(f"Failed to create CVData object from parsed data for session {session_id}: {cv_model_error}. Parsed data: {cv_data_parsed_dict}", exc_info=True)
            # Fallback if Pydantic model creation fails due to missing fields, still try to store available data.
            # This handles cases where CVParser might return incomplete dict.
            session.cv_data = CVData(
                content=safe_dict_get(cv_data_parsed_dict, 'content', ''),
                skills=safe_dict_get(cv_data_parsed_dict, 'skills', []),
                education=safe_dict_get(cv_data_parsed_dict, 'education', []),
                experience=safe_dict_get(cv_data_parsed_dict, 'experience', []),
                contact_info=safe_dict_get(cv_data_parsed_dict, 'contact_info', {})
            )
            logger.warning(f"CVData object creation partial due to schema mismatch for session {session_id}.")
        
        session_manager.update_session(session)
        
        return {
            "message": "CV uploaded and parsed successfully",
            "skills_found": len(getattr(session.cv_data, 'skills', [])), # Access directly from session.cv_data model
            "education_entries": len(getattr(session.cv_data, 'education', [])),
            "experience_entries": len(getattr(session.cv_data, 'experience', []))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading CV for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process CV. Please try again or with a different file.")

@router.post("/session/{session_id}/start")
async def start_interview(session_id: str, background_tasks: BackgroundTasks):
    """Start the interview session. Triggers initial question generation."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if not session.cv_data:
            raise HTTPException(status_code=400, detail="CV must be uploaded before starting the interview.")
        
        # Check if already started or in an active state
        current_status = getattr(session, 'status', 'created')
        if current_status == 'active':
            # If already active, return its current state
            messages = getattr(session, 'messages', []) 
            initial_question_content = "Interview already in progress. Waiting for your response."
            if messages and len(messages) > 0 and hasattr(messages[0], 'content'):
                initial_question_content = messages[0].content # Return the first interviewer message
                
            logger.info(f"Attempted to start already active session {session_id_validated}.")
            return {
                "message": "Interview already started",
                "initial_question": initial_question_content,
                "total_questions": getattr(session, 'total_questions', 8),
                "questions": getattr(session, 'questions', []) # Return the full question plan if available
            }
        
        # Mark session as started (active)
        success = session_manager.start_session(session_id_validated)
        if not success:
            logger.error(f"Failed to update session status to 'active' for {session_id_validated}.")
            raise HTTPException(status_code=500, detail="Failed to start session.")
        
        # Initialize attributes just in case, though they should be by create_session.
        if not hasattr(session, 'messages') or session.messages is None:
            session.messages = []
        if not hasattr(session, 'questions') or session.questions is None:
            session.questions = []
        if not hasattr(session, 'questions_asked') or session.questions_asked is None:
            session.questions_asked = 0
        
        # Initial question generation.
        # It's ideal to try and generate the first question directly or as fast as possible for UX.
        # However, as ai_interviewer might be slow, submit as a background task.
        # The frontend should poll /session/{session_id} for the actual initial_question.
        initial_question_text_placeholder = "The interview is starting... Please wait for the first question."
        
        try:
            # Submitting the task to the ThreadPoolExecutor
            # Note: The result of _generate_initial_question is only persisted in SessionManager,
            # not returned directly here. Frontend must poll get_session endpoint.
            executor.submit(_generate_initial_question, session_id_validated)
            logger.info(f"Submitted initial question generation to background for session {session_id_validated}.")
        except Exception as intro_task_err:
            logger.warning(f"Failed to submit immediate intro generation for session {session_id_validated} to executor: {intro_task_err}", exc_info=True)
            # Fallback to a FastAPI BackgroundTask if executor submission fails
            background_tasks.add_task(_generate_initial_question, session_id_validated)
            logger.info(f"Submitted initial question generation to FastAPI background task for session {session_id_validated}.")
        
        # Return immediate response, indicating the question is being prepared.
        return {
            "message": "Interview started successfully. Initial question is being prepared.",
            "initial_question": initial_question_text_placeholder,
            "total_questions": getattr(session, 'total_questions', 8),
            "questions": getattr(session, 'questions', []) # This might be an empty list until the background task populates it
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting interview for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start interview.")

@router.post("/session/{session_id}/message")
async def add_message(session_id: str, message_data: Dict[str, Any]):
    """Add a message to the interview conversation and optionally get an AI response."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        if session_manager.is_session_expired(session_id_validated):
            session_manager.end_session(session_id_validated) # Explicitly end if expired
            raise HTTPException(status_code=400, detail="Session has expired. Please create a new one.")
        
        # Basic validation for message data structure and content.
        if not isinstance(message_data, dict):
            raise HTTPException(status_code=400, detail="Invalid message data format. Must be a JSON object.")
            
        role = safe_dict_get(message_data, 'role')
        content = safe_dict_get(message_data, 'content', '').strip() # Ensure content is string and trimmed
        
        if not role or not isinstance(role, str):
            raise HTTPException(status_code=400, detail="'role' field is required and must be a string.")
            
        if not content or not isinstance(content, str):
            raise HTTPException(status_code=400, detail="'content' field is required and must be a non-empty string.")
        
        if role not in ['interviewer', 'candidate']:
            raise HTTPException(status_code=400, detail="'role' must be 'interviewer' or 'candidate'.")
        
        # Ensure messages list exists on the session object
        if not hasattr(session, 'messages') or session.messages is None:
            session.messages = []
        
        # Add user's message
        try:
            user_message = InterviewMessage(
                role=role,
                content=content,
                timestamp=datetime.now()
            )
            session.messages.append(user_message)
            logger.info(f"User message added to session {session_id_validated}. Role: {role}")
        except Exception as msg_obj_error:
            logger.error(f"Failed to create InterviewMessage object from input: {msg_obj_error}", exc_info=True)
            raise HTTPException(status_code=400, detail="Failed to process message content.")
        
        # Generate AI response if the user is the candidate.
        ai_response_text = None
        if role == 'candidate':
            try:
                # Prepare CV data for AI interviewer (safely convert Pydantic model to dict)
                cv_data_for_ai = session.cv_data.model_dump() if hasattr(session.cv_data, 'model_dump') else session.cv_data.dict() if hasattr(session.cv_data, 'dict') else {}
                
                # Prepare conversation history for AI (safely convert list of Pydantic models to list of dicts)
                conversation_history_for_ai = []
                for msg_item in session.messages:
                    if hasattr(msg_item, 'model_dump'):
                        conversation_history_for_ai.append(msg_item.model_dump())
                    elif hasattr(msg_item, 'dict'):
                        conversation_history_for_ai.append(msg_item.dict())
                    else: # Fallback for unexpected message object types
                        conversation_history_for_ai.append({
                            'role': getattr(msg_item, 'role', 'unknown'),
                            'content': getattr(msg_item, 'content', ''),
                            'timestamp': getattr(msg_item, 'timestamp', datetime.now()).isoformat()
                        })
                
                ai_response_content = ai_interviewer.get_interview_response(
                    cv_data_for_ai, conversation_history_for_ai, content # Pass current message too
                )
                
                if ai_response_content and isinstance(ai_response_content, str) and ai_response_content.strip():
                    ai_message = InterviewMessage(
                        role="interviewer",
                        content=ai_response_content.strip(),
                        timestamp=datetime.now()
                    )
                    session.messages.append(ai_message)
                    ai_response_text = ai_response_content.strip()
                    logger.info(f"AI response generated for session {session_id_validated}.")
                    
                    # Increment questions asked counter ONLY if the AI generated a meaningful question/response
                    # and if the candidate message was truly an answer to a question, which is implied by 'interviewer' role response.
                    current_asked_count = getattr(session, 'questions_asked', 0)
                    session.questions_asked = current_asked_count + 1
                else:
                    logger.warning(f"AI response was empty or invalid for session {session_id_validated}. No interviewer message added.")
                    
            except Exception as ai_error:
                logger.error(f"Failed to generate AI response for session {session_id_validated}: {ai_error}", exc_info=True)
                # Do not raise HTTP 500 here; instead, return success for user's message
                # but with an indication that AI response failed if needed on frontend.
                # A robust frontend can then show a 'technical difficulties' message.
                ai_response_text = "I'm sorry, I seem to be experiencing technical difficulties. Could you please rephrase or tell me more about that?"
                ai_message_error_fallback = InterviewMessage(
                    role="interviewer",
                    content=ai_response_text,
                    timestamp=datetime.now()
                )
                session.messages.append(ai_message_error_fallback)


        session_manager.update_session(session) # Always update the session regardless of AI response outcome.
        
        response_data = {"message": "Message added successfully"}
        if ai_response_text:
            response_data["ai_response"] = ai_response_text
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding message to session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add message.")

@router.post("/session/{session_id}/behavior")
async def add_behavior_metrics(session_id: str, metrics_data: Dict[str, Any]):
    """Add behavior metrics to the session (e.g., eye contact, posture scores)."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        # Ensure behavior_metrics list exists on session
        if not hasattr(session, 'behavior_metrics') or session.behavior_metrics is None:
            session.behavior_metrics = []
        
        # Create BehaviorMetrics object with robust type conversion and clamping
        try:
            metrics = BehaviorMetrics(
                face_detected=bool(safe_dict_get(metrics_data, 'face_detected', False)),
                eye_contact_score=_safe_float(safe_dict_get(metrics_data, 'eye_contact_score', 0.0)),
                posture_score=_safe_float(safe_dict_get(metrics_data, 'posture_score', 0.0)),
                gesture_count=_safe_int(safe_dict_get(metrics_data, 'gesture_count', 0), min_val=0, max_val=1000), # Assuming a reasonable max
                attention_score=_safe_float(safe_dict_get(metrics_data, 'attention_score', 0.0)),
                timestamp=datetime.now()
            )
        except (ValueError, TypeError) as validation_error:
            logger.warning(f"Invalid behavior metrics data received for session {session_id}: {validation_error}. Data: {metrics_data}")
            raise HTTPException(status_code=400, detail=f"Invalid behavior metrics values: {validation_error}")
        
        session.behavior_metrics.append(metrics)
        session_manager.update_session(session)
        logger.debug(f"Behavior metrics added for session {session_id_validated}.")
        
        return {"message": "Behavior metrics added successfully."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding behavior metrics to session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add behavior metrics.")

@router.post("/session/{session_id}/end")
async def end_interview(session_id: str):
    """End the interview session and generate a summary."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        # End the session (stops timer, sets status)
        session_manager.end_session(session_id_validated)
        logger.info(f"Session {session_id_validated} has been marked as ended.")
        
        # Prepare session data for summary generation, robustly converting Pydantic models to dicts
        messages_to_process = getattr(session, 'messages', []) 
        behavior_metrics_to_process = getattr(session, 'behavior_metrics', [])
        
        session_data_for_summary = {
            'messages': [],
            'cv_data': {},
            'behavior_metrics': []
        }
        
        # Convert messages
        for msg_item in messages_to_process:
            try:
                if hasattr(msg_item, 'model_dump'):
                    session_data_for_summary['messages'].append(msg_item.model_dump())
                elif hasattr(msg_item, 'dict'): # Pydantic V1 compatibility
                    session_data_for_summary['messages'].append(msg_item.dict())
                else:
                    # Fallback for unexpected message types
                    session_data_for_summary['messages'].append({
                        'role': getattr(msg_item, 'role', 'unknown'),
                        'content': getattr(msg_item, 'content', ''),
                        'timestamp': getattr(msg_item, 'timestamp', datetime.now()).isoformat()
                    })
            except Exception as msg_conv_error:
                logger.warning(f"Failed to convert message to dict for summary for session {session_id}: {msg_conv_error}")
        
        # Convert CV data
        if session.cv_data:
            try:
                if hasattr(session.cv_data, 'model_dump'):
                    session_data_for_summary['cv_data'] = session.cv_data.model_dump()
                elif hasattr(session.cv_data, 'dict'): # Pydantic V1 compatibility
                    session_data_for_summary['cv_data'] = session.cv_data.dict()
                else:
                    logger.warning(f"Session CV data not a Pydantic model for session {session_id}.")
                    session_data_for_summary['cv_data'] = {} # Default to empty if cannot convert
            except Exception as cv_conv_error:
                logger.warning(f"Failed to convert CV data to dict for summary for session {session_id}: {cv_conv_error}")
        
        # Convert behavior metrics
        for metric_item in behavior_metrics_to_process:
            try:
                if hasattr(metric_item, 'model_dump'):
                    session_data_for_summary['behavior_metrics'].append(metric_item.model_dump())
                elif hasattr(metric_item, 'dict'): # Pydantic V1 compatibility
                    session_data_for_summary['behavior_metrics'].append(metric_item.dict())
                else:
                    logger.warning(f"Session behavior metric not a Pydantic model for session {session_id}.")
                    session_data_for_summary['behavior_metrics'].append({}) # Default to empty if cannot convert
            except Exception as metric_conv_error:
                logger.warning(f"Failed to convert behavior metric to dict for summary for session {session_id}: {metric_conv_error}")
        
        # Generate summary using the AI service.
        # The service is expected to return a structured dict (with keys like
        # 'total_messages', 'cv_match_score', 'behavior_summary', 'recommendations').
        # If the AI returns a non-dict (e.g. a plain string) handle gracefully and
        # return a structured fallback so the frontend can render the results page.
        summary = {}
        try:
            summary_result = ai_interviewer.generate_session_summary(session_data_for_summary)

            # If AI returns a dict (the preferred/expected shape) use it directly.
            if isinstance(summary_result, dict):
                summary = summary_result
            else:
                # If AI returned a string (or other type), wrap it into a structured
                # summary object so the frontend won't crash when accessing fields.
                text_repr = str(summary_result) if summary_result is not None else ''
                if text_repr.strip():
                    logger.warning(f"AI returned non-dict summary for session {session_id_validated}; wrapping text into structured summary.")
                    summary = {
                        'total_messages': len(messages_to_process),
                        'cv_match_score': 0,
                        'behavior_summary': {
                            'average_attention_score': 0,
                            'average_eye_contact_score': 0,
                            'average_posture_score': 0,
                            'total_gestures': 0,
                            'engagement_level': 'Low'
                        },
                        'recommendations': ["Summary returned as text. See detailed text below."],
                        'text_summary': text_repr
                    }
                else:
                    logger.warning(f"AI interviewer generated an empty summary for session {session_id_validated}.")
                    summary = {
                        'total_messages': len(messages_to_process),
                        'cv_match_score': 0,
                        'behavior_summary': {
                            'average_attention_score': 0,
                            'average_eye_contact_score': 0,
                            'average_posture_score': 0,
                            'total_gestures': 0,
                            'engagement_level': 'Low'
                        },
                        'recommendations': ["Summary generation did not produce any content. Please check logs."]
                    }
        except Exception as summary_ai_error:
            logger.error(f"Failed to generate summary for session {session_id_validated} using AI: {summary_ai_error}", exc_info=True)
            summary = {
                'total_messages': len(messages_to_process),
                'cv_match_score': 0,
                'behavior_summary': {
                    'average_attention_score': 0,
                    'average_eye_contact_score': 0,
                    'average_posture_score': 0,
                    'total_gestures': 0,
                    'engagement_level': 'Low'
                },
                'recommendations': ["An error occurred while generating the detailed interview summary."]
            }
        
        # Calculate final duration based on actual start/end times if available, or recorded duration.
        duration_seconds_actual = getattr(session, 'duration_seconds', 0)
        duration_minutes_rounded = round(duration_seconds_actual / 60, 1) if duration_seconds_actual > 0 else 0
        
        return {
            "message": "Interview ended successfully",
            "summary": summary,
            "transcript": session_data_for_summary['messages'],
            "duration_minutes": duration_minutes_rounded
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending interview for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to end interview and generate summary.")

@router.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get current session status including time remaining and other key indicators."""
    try:
        session_id_validated = validate_session_id(session_id)
        session = session_manager.get_session(session_id_validated)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        time_remaining = 0
        current_status = getattr(session, 'status', 'created')
        start_time = getattr(session, 'start_time', None)
        max_duration = getattr(session, 'max_duration_seconds', 900) # Default 900 seconds (15 minutes)
        
        if start_time and current_status == "active":
            try:
                elapsed_seconds = (datetime.now() - start_time).total_seconds()
                time_remaining = max(0, max_duration - elapsed_seconds)
            except Exception as time_calc_error:
                logger.warning(f"Failed to calculate time remaining for session {session_id}: {time_calc_error}")
                # Fallback to max duration if calculation fails, indicating potential issue.
                time_remaining = max_duration 
        elif current_status == 'ended':
            time_remaining = 0 # No time remaining for an ended session.
        elif current_status == 'created':
            time_remaining = max_duration # Full time available for a new session.

        messages = getattr(session, 'messages', [])
        behavior_metrics = getattr(session, 'behavior_metrics', [])
        
        return {
            "session_id": session.session_id,
            "status": current_status,
            "time_remaining_seconds": int(time_remaining),
            "message_count": len(messages),
            "behavior_metrics_count": len(behavior_metrics)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get session status.")

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and all its data."""
    try:
        session_id_validated = validate_session_id(session_id)
        success = session_manager.delete_session(session_id_validated)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found.")
        
        logger.info(f"Session {session_id_validated} deleted successfully.")
        return {"message": "Session deleted successfully."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete session.")

# ------------------------------------
# Enhanced ATS Analysis Endpoints
# ------------------------------------

def _extract_required_skills(job_description: str) -> List[str]:
    """
    Enhanced skill extraction from job description with improved accuracy and a robust fallback.
    Identifies common technical and soft skills, handles variations, and can extract general terms.
    """
    if not job_description or not isinstance(job_description, str):
        return []
    
    # Comprehensive lists of common technical and soft skills (can be extended)
    technical_skills_phrases = [
        'python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'php', 'ruby', 'swift',
        'html', 'css', 'sass', 'less', 'typescript', 'jsx', 'react', 'angular', 'vue', 'svelte', 'nodejs',
        'expressjs', 'fastapi', 'django', 'flask', 'spring boot', 'laravel', 'rails',
        'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle database',
        'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'google cloud', 'git', 'linux', 'unix', 'bash', 'powershell',
        'machine learning', 'ml', 'ai', 'artificial intelligence', 'deep learning',
        'data science', 'pandas', 'numpy', 'matplotlib', 'scikit-learn', 'pytorch', 'tensorflow', 'katalon', 'selenium',
        'rest api', 'graphql', 'microservices', 'devops', 'ci/cd', 'jenkins', 'terraform', 'ansible', 'chef', 'puppet',
        'containerization', 'cloud computing', 'cyber security', 'blockchain', 'etl', 'data warehousing'
    ]
    
    soft_skills_phrases = [
        'leadership', 'communication', 'teamwork', 'problem solving', 'analytical thinking',
        'time management', 'project management', 'agile', 'scrum', 'kanban',
        'collaboration', 'adaptability', 'creativity', 'attention to detail',
        'critical thinking', 'negotiation', 'mentoring', 'client management', 'stakeholder management'
    ]
    
    # Combine and normalize all predefined skills for matching
    all_known_skills = {skill.lower(): skill for skill in technical_skills_phrases + soft_skills_phrases}
    
    jd_lower = job_description.lower()
    found_skills_temp = set() # Use a set to handle duplicates automatically

    # Pass 1: Direct/Exact match for predefined skills and their common variations
    variations_map = {
        'js': 'javascript', 'ts': 'typescript', 'postgres': 'postgresql',
        'ml': 'machine learning', 'ai': 'artificial intelligence',
        'gcp': 'google cloud', 'spring': 'spring boot', 'node': 'nodejs'
    }

    for known_skill_lower, original_form in all_known_skills.items():
        if known_skill_lower in jd_lower:
            found_skills_temp.add(original_form)
            continue
        
        # Check variations (e.g., "js" for "javascript")
        if known_skill_lower in variations_map:
            for alias in variations_map[known_skill_lower].split(' '): # e.g., 'spring' alias of 'spring boot'
                 if alias.lower() in jd_lower:
                    found_skills_temp.add(original_form)
                    break
        
        # Check if all words in a multi-word skill phrase exist (e.g., 'spring' and 'boot' for 'spring boot')
        if ' ' in known_skill_lower:
            words = known_skill_lower.split()
            if all(word in jd_lower for word in words):
                found_skills_temp.add(original_form)
                
    # Pass 2: Enhanced Fallback - Identify capitalized terms/phrases which often denote specific technologies or proper nouns
    if not found_skills_temp:
        # Look for multi-word capitalized phrases (e.g., "FastAPI", "TensorFlow")
        # and single capitalized words that might be skills.
        potential_capitalized_terms = re.findall(r'\b(?:[A-Z][a-zA-Z0-9_+\-\.]+(?:\s[A-Z][a-zA-Z0-9_+\-\.]+)*)\b', job_description)
        stop_words = set(['the', 'and', 'for', 'with', 'in', 'of', 'to', 'a', 'an', 'is', 'on', 'or', 'at', 'etc', 'are', 'you', 'be', 'by', 'as']) # Extended
        
        for term in potential_capitalized_terms:
            if len(term) > 2 and term.lower() not in stop_words and not any(word.lower() in stop_words for word in term.split()):
                found_skills_temp.add(term.strip())

    unique_skills_list = sorted(list(found_skills_temp)) # Sort for consistent output
    return unique_skills_list[:25]  # Limit to 25 skills max to keep results concise

def _normalize_text(text: str) -> str:
    """Normalize text for better string matching by converting to lowercase and removing non-alphanumeric characters."""
    if not text or not isinstance(text, str):
        return ""
    # Replace non-alphanumeric characters with spaces, then strip, then convert to lowercase.
    # Keep digits as they are common in tech skills (e.g., C# .NET Core)
    return re.sub(r'[^a-z0-9\s]+', ' ', text.lower()).strip()


def _safe_float(value: Any, default: float = 0.0, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Safely convert value to float within specified bounds."""
    try:
        result = float(value)
        return max(min_val, min(max_val, result))
    except (ValueError, TypeError):
        return default


def _safe_int(value: Any, default: int = 0, min_val: int = 0, max_val: int = 1000) -> int:
    """Safely convert value to int within specified bounds."""
    try:
        result = int(value)
        return max(min_val, min(max_val, result))
    except (ValueError, TypeError):
        return default


def _extract_evidence_snippet(text: str, skill: str, max_length: int = 250) -> str:
    """
    Extract a relevant snippet from text demonstrating evidence of a skill.
    Prioritizes full sentences or relevant phrases.
    """
    if not text or not skill:
        return ""
    
    # Try to find a sentence containing the skill first
    sentences = re.split(r'(?<=[.!?])\s+', text) # Splits by .!? followed by space, keeping delimiter
    skill_lower = skill.lower()
    
    for sentence in sentences:
        if skill_lower in sentence.lower():
            # Ensure the snippet is not just the skill but has surrounding context
            if len(sentence) > max_length:
                # Find the skill in the sentence and take context around it
                match_start = sentence.lower().find(skill_lower)
                if match_start != -1:
                    start_idx = max(0, match_start - 50) # Start 50 chars before
                    end_idx = min(len(sentence), match_start + len(skill) + 200) # End 200 chars after
                    snippet = sentence[start_idx:end_idx]
                    return "... " + snippet.strip() + " ..." if start_idx > 0 else snippet.strip()
            return sentence.strip()[:max_length]
    
    # Fallback: if no full sentence, try to extract words around the skill
    # Pattern to capture words 50 characters before and after the skill.
    pattern = rf'\b.{0,50}\b({re.escape(skill_lower)})\b.{0,50}\b'
    match = re.search(pattern, _normalize_text(text), re.IGNORECASE)
    if match:
        snippet_raw = match.group(0)
        # Find original text for better presentation, but with risk if normalization loses info.
        # This part could be improved for finding exact match in original text.
        # For simplicity, returning the normalized text context
        return snippet_raw.strip()[:max_length]

    return "" # No strong evidence found


@router.post("/ats/analyze")
async def ats_analyze(
    file: UploadFile = File(...),
    job_description: str = Form(..., min_length=50), # Enforce a minimum length for JD quality
    candidate_name: Optional[str] = Form(None)
):
    """
    Enhanced ATS analysis: Uploads a CV, parses it, and compares it against a job description
    to calculate a compatibility score, identify matched/missing skills, and provide recommendations.
    """
    try:
        # Validate job description content (minimum length, stripping whitespace)
        job_description_clean = job_description.strip()
        if len(job_description_clean) < 50: # Stronger validation for quality JD
            raise HTTPException(status_code=400, detail="Job description must be at least 50 characters long to provide meaningful analysis.")
        
        candidate_name_clean = (candidate_name or "").strip()
        
        # File Validation (same as upload_cv endpoint)
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No CV file provided.")
            
        allowed_types = {
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain'
        }
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported CV file type: {file.content_type}. Only PDF, DOCX, and TXT are supported."
            )

        content = b""
        try:
            content = await file.read()
        except Exception as read_error:
            logger.error(f"Failed to read uploaded CV file for ATS analysis: {read_error}", exc_info=True)
            raise HTTPException(status_code=400, detail="Failed to read CV file content.")
            
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded CV file is empty.")
            
        if len(content) > 10 * 1024 * 1024: # 10MB limit
            raise HTTPException(status_code=400, detail="CV file too large. Maximum size is 10MB.")

        # Parse CV
        cv_data_parsed = {}
        try:
            cv_data_parsed = cv_parser.parse_cv(file.filename, content)
        except Exception as parse_error:
            logger.error(f"CV parsing failed during ATS analysis: {parse_error}", exc_info=True)
            raise HTTPException(status_code=400, detail="Failed to parse CV. Ensure the file is valid and readable.")
        
        if not cv_data_parsed or not isinstance(cv_data_parsed, dict) or not cv_data_parsed.get('content'):
            raise HTTPException(status_code=400, detail="No readable content found in the CV after parsing.")

        # Extract CV components (safe retrieval with defaults)
        cv_content = safe_dict_get(cv_data_parsed, 'content', '')
        cv_skills = safe_dict_get(cv_data_parsed, 'skills', [])
        cv_education = safe_dict_get(cv_data_parsed, 'education', [])
        cv_experience = safe_dict_get(cv_data_parsed, 'experience', [])
        cv_contact = safe_dict_get(cv_data_parsed, 'contact_info', {})
        
        # Required skills from Job Description
        required_skills = _extract_required_skills(job_description_clean)
        
        if not required_skills:
            logger.warning("No significant skills extracted from job description for ATS analysis.")
            return {
                "candidate_name": candidate_name_clean,
                "compatibility_score": 0,
                "required_skills": [],
                "matched_skills": [],
                "missing_skills": [],
                "cv_summary": {
                    "skills_found": len(cv_skills),
                    "education_entries": len(cv_education),
                    "experience_entries": len(cv_experience)
                },
                "contact_info": cv_contact,
                "recommendations": ["Could not extract key requirements from the provided job description. Please provide a more detailed and structured job description."],
                "_skill_confidences": {},
                "_skill_evidence": {}
            }

        # Normalize texts for matching (only once for efficiency)
        cv_text_norm = _normalize_text(cv_content)
        cv_skill_tokens_norm = {_normalize_text(s) for s in cv_skills if s} # Use a set for quick lookup
        
        matched_skills_output = []
        missing_skills_output = []
        skill_confidences = {}
        skill_evidence = {}
        
        for required_skill in required_skills:
            required_skill_norm = _normalize_text(required_skill)
            current_confidence = 0.0
            current_evidence = ""

            # Strategy for matching (prioritized):
            # 1. Direct match in extracted skills section (highest confidence)
            if required_skill_norm in cv_skill_tokens_norm:
                current_confidence = max(current_confidence, 0.95)
                current_evidence = "Explicitly listed in CV skills section."
            else:
                # Check for direct word match in a larger set of skills/phrases
                # Fuzzy matching in general content or experience.
                
                # Check within job experience descriptions
                for exp_entry in cv_experience:
                    exp_description = ""
                    if isinstance(exp_entry, dict):
                        exp_description = safe_dict_get(exp_entry, 'description', '') or safe_dict_get(exp_entry, 'content', '')
                    else: # Handle cases where exp_entry might be just a string
                        exp_description = str(exp_entry)
                        
                    if exp_description and required_skill_norm in _normalize_text(exp_description):
                        current_confidence = max(current_confidence, 0.85)
                        current_evidence = _extract_evidence_snippet(exp_description, required_skill)
                        break # Found strong evidence, no need to check other experiences for this skill

                # Check general CV content for the exact phrase
                if current_confidence < 0.8: # Only if not already high confidence
                    pattern_whole_word = rf'\b{re.escape(required_skill_norm)}\b'
                    if re.search(pattern_whole_word, cv_text_norm):
                        current_confidence = max(current_confidence, 0.75)
                        current_evidence = _extract_evidence_snippet(cv_content, required_skill)

                # Fuzzy matching with extracted CV skills for close variations
                if current_confidence < 0.7:
                    for cv_skill_norm in cv_skill_tokens_norm:
                        try:
                            ratio = difflib.SequenceMatcher(None, required_skill_norm, cv_skill_norm).ratio()
                            if ratio > 0.8: # A high ratio for fuzzy match
                                new_confidence = 0.6 + (ratio - 0.8) * 0.3 # Scale confidence 0.6 to 0.9
                                current_confidence = max(current_confidence, new_confidence)
                                current_evidence = f"Similar to listed skill: {cv_skill_norm} (Similarity: {int(ratio*100)}%)."
                                break
                        except Exception:
                            continue # Continue if SequenceMatcher encounters issues

                # Partial match in overall CV content (lowest but still valuable)
                if current_confidence < 0.5 and required_skill_norm in cv_text_norm:
                    current_confidence = max(current_confidence, 0.4) # Min threshold for consideration
                    if not current_evidence: # Only add if no stronger evidence found
                        current_evidence = _extract_evidence_snippet(cv_content, required_skill) or "Found contextually in CV."
            
            # Record result if above threshold
            if current_confidence > 0.35: # Min confidence to consider a skill as "matched"
                skill_confidences[required_skill] = current_confidence
                skill_evidence[required_skill] = current_evidence
                matched_skills_output.append(f"{required_skill} ({int(current_confidence * 100)}%)")
            else:
                missing_skills_output.append(required_skill)
        
        # Calculate Compatibility Score
        compatibility_score = 0
        try:
            if required_skills:
                # Sum of confidences / total required skills (accounts for missing skills effectively as 0 confidence)
                total_possible_score_from_skills = sum(skill_confidences.get(s, 0) for s in required_skills)
                avg_skill_match_score = total_possible_score_from_skills / len(required_skills)
                
                # Boost based on comprehensive CV sections
                contact_bonus = 0.05 if (cv_contact.get('email') and cv_contact.get('phone')) else 0 # Stronger condition
                education_bonus = min(0.1, 0.025 * len(cv_education))
                experience_bonus = min(0.15, 0.03 * len(cv_experience))
                
                # Combine weighted scores and scale to 0-100
                raw_score = avg_skill_match_score + contact_bonus + education_bonus + experience_bonus
                # Cap the score at a max theoretical value to prevent it going way above 1.0 before multiplying
                raw_score = min(raw_score, 1.0) 
                
                compatibility_score = min(100, max(0, int(raw_score * 100))) # Ensure it's between 0 and 100
            else:
                compatibility_score = 0
        except Exception as score_calc_error:
            logger.error(f"Error calculating compatibility score: {score_calc_error}", exc_info=True)
            compatibility_score = 0 # Fallback if score calculation itself fails
        
        # Generate Actionable Recommendations
        recommendations = []
        if missing_skills_output:
            for skill in missing_skills_output[:5]: # Focus on top 5 missing skills
                recommendations.append(
                    f"Strongly consider adding '{skill}' to your CV, along with concrete examples of its application in your projects or roles (e.g., project details, specific tasks, technologies integrated, quantifiable results)."
                )
        
        if not cv_education:
            recommendations.append("Include an 'Education' section with degrees, institutions, graduation dates, and relevant academic achievements.")
        elif len(cv_education) == 1:
             recommendations.append("Expand on your educational background, detailing relevant coursework, academic projects, or certifications.")
        
        if not cv_experience:
            recommendations.append("Add an 'Experience' section, listing roles with start/end dates, responsibilities, and key achievements using action verbs and quantifiable results.")
        elif len(cv_experience) < 2:
            recommendations.append("Consider adding more professional experience entries or detailed project descriptions for significant freelance/personal work.")
        
        # Comprehensive contact info check
        contact_suggestions = []
        if not safe_dict_get(cv_contact, 'email'): contact_suggestions.append("a professional email address")
        if not safe_dict_get(cv_contact, 'phone'): contact_suggestions.append("a reliable phone number")
        if not safe_dict_get(cv_contact, 'linkedin'): contact_suggestions.append("your LinkedIn profile URL")
        
        if contact_suggestions:
            recommendations.append(f"Ensure your 'Contact Information' includes {', '.join(contact_suggestions)} for recruiters to reach you.")

        if len(cv_content) < 700: # Heuristic for detail level
            recommendations.append("Elaborate on your past responsibilities and accomplishments with more detail and context, focusing on results.")
        
        if compatibility_score < 40 and not missing_skills_output:
            recommendations.append("The job description appears highly specific. Try to tailor your CV to align more directly with the keywords and required skills mentioned in the job description.")

        if compatibility_score >= 80:
            recommendations.append("Excellent match! To further strengthen your application, highlight unique leadership experiences or contributions to company growth if not already prominent.")
        elif compatibility_score >= 60:
            recommendations.append("Good compatibility! Focus on enhancing the depth and detail of your most relevant skills and experiences by adding quantifiable impacts.")
            
        # Default recommendation if no specific issues identified (e.g., short CV)
        if not recommendations:
            recommendations.append("Ensure your CV uses strong action verbs and quantifies achievements wherever possible.")
            
        # Prepare final response structure
        final_response = {
            "candidate_name": candidate_name_clean if candidate_name_clean else (cv_contact.get('name') if cv_contact.get('name') else "N/A"),
            "compatibility_score": compatibility_score,
            "required_skills": required_skills,
            "matched_skills": matched_skills_output,
            "missing_skills": missing_skills_output,
            "cv_summary": {
                "skills_found": len(cv_skills),
                "education_entries": len(cv_education),
                "experience_entries": len(cv_experience)
            },
            "contact_info": cv_contact,
            "recommendations": recommendations[:8], # Limit to top 8 recommendations
            "_skill_confidences": {k: round(v, 2) for k, v in skill_confidences.items()},
            "_skill_evidence": {k: v[:300] + ('...' if len(v) > 300 else '') for k, v in skill_evidence.items()} # Clip evidence length
        }
        
        logger.info(f"ATS analysis completed for {candidate_name_clean}, score: {compatibility_score}.")
        return final_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ATS analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to analyze CV. A server-side error occurred. Please try again or contact support.")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Provides a basic health check for the API and its integrated services."""
    services_status = {}
    overall_status = "healthy"

    # Test SessionManager availability
    try:
        session_manager.get_session("non_existent_id") # Test a lookup (should not raise fatal error)
        services_status["session_manager"] = "ok"
    except Exception as e:
        services_status["session_manager"] = f"unhealthy: {str(e)[:50]}"
        overall_status = "unhealthy"

    # Test CVParser availability (e.g., attempt a trivial parse or just check instantiation)
    try:
        # A simple check that doesn't involve actual heavy file processing.
        # This assumes CVParser can quickly handle simple inputs or has a internal readiness check.
        test_cv_parser_result = cv_parser.parse_cv("dummy.txt", b"simple test content")
        if not test_cv_parser_result:
            raise ValueError("CVParser returned empty for test content.")
        services_status["cv_parser"] = "ok"
    except Exception as e:
        services_status["cv_parser"] = f"unhealthy: {str(e)[:50]}"
        overall_status = "unhealthy"

    # Test AIInterviewer availability (e.g., generate a trivial response)
    try:
        test_ai_response = ai_interviewer.get_interview_response({}, [], "hello")
        if not test_ai_response or not test_ai_response.strip():
            raise ValueError("AIInterviewer returned empty response for test content.")
        services_status["ai_interviewer"] = "ok"
    except Exception as e:
        services_status["ai_interviewer"] = f"unhealthy: {str(e)[:50]}"
        overall_status = "unhealthy"
        
    logger.debug(f"Health check status: {overall_status}, details: {services_status}")
    
    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "services": services_status
    }