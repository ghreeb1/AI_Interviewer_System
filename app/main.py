"""
This application is configured to use a local Ollama 3.2 model for all AI responses.
Ensure Ollama is installed and the server is running locally before starting the app:
  - Download/install Ollama from `https://ollama.com/`
  - Start the server and pull the model:
      ollama run llama3.2
The backend will call http://localhost:11434/api/generate via HTTP.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from app.routers import api, websocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Interviewer System",
    description="Local AI-powered interview system with voice and vision analysis",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(api.router)
app.include_router(websocket.router)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page - CV upload"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page UI (no auth backend yet)"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/interview/{session_id}", response_class=HTMLResponse)
async def interview_page(request: Request, session_id: str):
    """Interview page with webcam and audio"""
    return templates.TemplateResponse("interview.html", {
        "request": request,
        "session_id": session_id
    })

@app.get("/results/{session_id}", response_class=HTMLResponse)
async def results_page(request: Request, session_id: str):
    """Results page showing interview summary"""
    return templates.TemplateResponse("results.html", {
        "request": request,
        "session_id": session_id
    })

@app.get("/ats", response_class=HTMLResponse)
async def ats_page(request: Request):
    """ATS assessment page"""
    return templates.TemplateResponse("ats.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "AI Interviewer System is running"
    }

@app.get("/system-status")
async def system_status():
    """Get system status including AI services availability"""
    from app.services.speech_service_simple import SpeechService
    from app.services.vision_service_simple import VisionService
    from app.services.ai_interviewer import AIInterviewer
    
    speech_service = SpeechService()
    vision_service = VisionService()
    ai_service = AIInterviewer()
    
    return {
        "speech_services": speech_service.get_speech_status(),
        "vision_services": vision_service.get_vision_status(),
        "llm_provider": "Ollama",
        "ollama_model": ai_service.ollama_model,
        "ollama_url": ai_service.ollama_base_url
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

