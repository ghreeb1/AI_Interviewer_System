import os
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
import random
import requests

logger = logging.getLogger(__name__)

class AIInterviewer:
    def __init__(self):
        # Ollama configuration
        self.ollama_base_url = os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.ollama_generate_url = f"{self.ollama_base_url}/api/generate"
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2')
        logger.info("AIInterviewer initialized using Ollama 3.2 (local)")
    
    def generate_interview_questions(self, cv_data: Dict) -> List[str]:
        """Generate interview questions based on CV data"""
        base_questions = [
            "Tell me about yourself and your background.",
            "What interests you most about this role?",
            "Describe a challenging project you've worked on.",
            "How do you handle working under pressure?",
            "What are your greatest strengths?",
            "Where do you see yourself in 5 years?",
            "Why are you looking for a new opportunity?",
            "How do you stay updated with industry trends?",
            "Describe a time when you had to learn something new quickly.",
            "What motivates you in your work?"
        ]
        
        # Add skill-specific questions
        skills = cv_data.get('skills', [])
        skill_questions = []
        
        for skill in skills[:3]:  # Focus on top 3 skills
            skill_questions.extend([
                f"Can you tell me about your experience with {skill}?",
                f"How have you used {skill} in your previous projects?",
                f"What challenges have you faced while working with {skill}?"
            ])
        
        all_questions = base_questions + skill_questions
        return random.sample(all_questions, min(10, len(all_questions)))
    
    def get_interview_response(self, cv_data: Dict, conversation_history: List[Dict], user_message: str) -> str:
        """Generate interviewer response based on conversation context"""
        # Try Ollama first; if it fails, fall back to local response
        ollama_response = self._get_ollama_response(cv_data, conversation_history, user_message)
        if ollama_response is not None:
            return ollama_response
        fallback = self._get_local_response(cv_data, conversation_history, user_message)
        return fallback
    
    def _get_ollama_response(self, cv_data: Dict, conversation_history: List[Dict], user_message: str) -> Optional[str]:
        """Get response from local Ollama server. Returns None on failure."""
        try:
            # Try with provided model name and a sensible fallback (with/without :latest)
            def candidate_models(model_name: str) -> List[str]:
                names = [model_name]
                if ":" in model_name:
                    names.append(model_name.split(":", 1)[0])
                else:
                    names.append(f"{model_name}:latest")
                # Ensure uniqueness while keeping order
                seen = set()
                ordered = []
                for n in names:
                    if n not in seen:
                        seen.add(n)
                        ordered.append(n)
                return ordered

            # Build a single prompt for the generate API
            history_lines: List[str] = []
            for msg in conversation_history[-5:]:  # Use last 5 messages for context
                role = 'Interviewer' if msg.get('role') == 'interviewer' else 'Candidate'
                content = msg.get('content', '')
                history_lines.append(f"{role}: {content}")

            context = (
                "You are an AI interviewer conducting a professional and interactive interview session. "
                "Follow these rules strictly: "
                "1) Always ask one question at a time and wait for the candidate's response. "
                "2) Start with general background, then technical, situational, and project-specific questions based on the CV. "
                "3) If the candidate's answer is brief, ask a clarifying follow-up for more detail. "
                "4) If the answer is detailed, ask a deeper, related question to probe expertise. "
                "5) Keep a natural, conversational tone. "
                "6) Never provide answers yourself; only ask questions and react like an interviewer."
            )

            cv_context = (
                f"Skills: {', '.join(cv_data.get('skills', []))}\n"
                f"Education: {'; '.join(cv_data.get('education', [])[:2])}\n"
                f"Experience: {'; '.join(cv_data.get('experience', [])[:2])}"
            )

            conversation_block = "\n".join(history_lines)
            prompt = (
                f"{context}\n\nCV Context:\n{cv_context}\n\n"
                f"Recent Conversation (last 5 turns):\n{conversation_block}\n\n"
                f"Candidate: {user_message}\nInterviewer (ask just one question, 1-2 sentences, following the rules):"
            )

            for model_name in candidate_models(self.ollama_model):
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 60,
                        "temperature": 0.7,
                        "top_p": 0.9
                    }
                }

                try:
                    response = requests.post(
                        self.ollama_generate_url,
                        json=payload,
                        timeout=8
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Ollama may return either aggregated {response: "..."} or streaming chunks
                    text = (data or {}).get("response", "")
                    if isinstance(text, str) and text.strip():
                        if model_name != self.ollama_model:
                            logger.info(f"Ollama responded using fallback model name '{model_name}'")
                        return text.strip()
                except requests.exceptions.HTTPError as http_err:
                    # If model not found, try the next candidate
                    status = getattr(http_err.response, 'status_code', None)
                    body = None
                    try:
                        body = http_err.response.text if http_err.response is not None else None
                    except Exception:
                        pass
                    if status == 404 or (body and 'not found' in body.lower()):
                        logger.warning(f"Ollama model '{model_name}' not found; trying next candidate if any")
                        continue
                    else:
                        logger.error(f"Ollama HTTP error for model '{model_name}': {http_err}")
                        continue
                except requests.exceptions.RequestException as req_err:
                    logger.error(f"Error connecting to Ollama for model '{model_name}': {req_err}")
                    continue

            logger.warning("Ollama returned no usable response for any candidate model; falling back to local patterns")
            return None

        except requests.exceptions.RequestException as http_error:
            logger.error(f"Error connecting to Ollama at {self.ollama_generate_url}: {http_error}")
            return None
    
    def _get_local_response(self, cv_data: Dict, conversation_history: List[Dict], user_message: str) -> str:
        """Generate local response using predefined patterns"""
        
        # Simple response patterns based on conversation flow
        message_count = len(conversation_history)
        
        if message_count == 0:
            return "Let's begin the interview. First, please introduce yourself."
        
        # Analyze user message for keywords
        user_lower = user_message.lower()
        
        if any(word in user_lower for word in ['experience', 'worked', 'project']):
            follow_ups = [
                "That sounds interesting. Can you tell me more about the challenges you faced in that role?",
                "What was the most rewarding aspect of that experience?",
                "How did that experience prepare you for this role?",
                "What would you do differently if you had to do it again?"
            ]
            return random.choice(follow_ups)
        
        elif any(word in user_lower for word in ['skill', 'technology', 'tool']):
            skills = cv_data.get('skills', [])
            if skills:
                skill = random.choice(skills)
                return f"I see you mentioned {skill} in your CV. How would you rate your proficiency with it?"
            else:
                return "What technologies or tools are you most comfortable working with?"
        
        elif any(word in user_lower for word in ['challenge', 'difficult', 'problem']):
            return "How do you typically approach problem-solving when faced with technical challenges?"
        
        elif any(word in user_lower for word in ['team', 'collaborate', 'work with']):
            return "Can you describe your preferred working style when collaborating with team members?"
        
        else:
            # Decide follow-up depth based on brevity (simple heuristic by word count)
            word_count = len(user_message.strip().split())
            if word_count < 20:
                clarifying = [
                    "Could you expand on that a bit—what were your specific responsibilities?",
                    "What was the context and goal, and what part did you personally own?",
                    "Can you share a concrete example or metric to illustrate that?"
                ]
                return random.choice(clarifying)
            else:
                probing = [
                    "What trade-offs did you consider, and why did you choose that approach?",
                    "How did you validate the results, and what would you improve next time?",
                    "Walk me through a tricky technical decision you made and its impact."
                ]
                return random.choice(probing)
    
    def generate_session_summary(self, session_data: Dict) -> Dict:
        """Generate a summary of the interview session"""
        messages = session_data.get('messages', [])
        cv_data = session_data.get('cv_data', {})
        behavior_metrics = session_data.get('behavior_metrics', [])
        
        # Calculate basic metrics
        total_messages = len(messages)
        candidate_messages = [msg for msg in messages if msg['role'] == 'candidate']
        
        # Simple CV match score based on skills mentioned
        cv_skills = set(skill.lower() for skill in cv_data.get('skills', []))
        mentioned_skills = set()
        
        for msg in candidate_messages:
            content_lower = msg['content'].lower()
            for skill in cv_skills:
                if skill in content_lower:
                    mentioned_skills.add(skill)
        
        cv_match_score = len(mentioned_skills) / max(len(cv_skills), 1) * 100
        
        # Behavior summary
        if behavior_metrics:
            avg_attention = sum(m.get('attention_score', 0) for m in behavior_metrics) / len(behavior_metrics)
            avg_eye_contact = sum(m.get('eye_contact_score', 0) for m in behavior_metrics) / len(behavior_metrics)
            avg_posture = sum(m.get('posture_score', 0) for m in behavior_metrics) / len(behavior_metrics)
            total_gestures = sum(m.get('gesture_count', 0) for m in behavior_metrics)
        else:
            avg_attention = 0
            avg_eye_contact = 0
            avg_posture = 0
            total_gestures = 0
        
        behavior_summary = {
            'average_attention_score': round(avg_attention, 2),
            'average_eye_contact_score': round(avg_eye_contact, 2),
            'average_posture_score': round(avg_posture, 2),
            'total_gestures': total_gestures,
            'engagement_level': 'High' if avg_attention > 0.7 else 'Medium' if avg_attention > 0.4 else 'Low'
        }
        
        # Generate recommendations
        recommendations = []
        if cv_match_score < 50:
            recommendations.append("Consider highlighting more relevant skills during the interview")
        if avg_eye_contact < 0.5:
            recommendations.append("Maintain better eye contact with the camera")
        if total_gestures < 5:
            recommendations.append("Use more hand gestures to appear more engaging")
        if len(candidate_messages) < 5:
            recommendations.append("Provide more detailed responses to interview questions")
        
        if not recommendations:
            recommendations.append("Great interview performance! Keep up the good work.")
        
        return {
            'total_messages': total_messages,
            'cv_match_score': round(cv_match_score, 1),
            'behavior_summary': behavior_summary,
            'recommendations': recommendations
        }

