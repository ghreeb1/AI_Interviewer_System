# AI Interviewer

A FastAPI web app that conducts mock interviews using a local LLM (Ollama), simple speech/vision placeholders, and CV parsing.

## Prerequisites
- Python 3.10+ (recommended)
- Windows PowerShell
- Optional: Ollama with model `llama3.2` running locally (`http://localhost:11434`)

## Quick Start (Windows)
1. Create and activate a virtual environment:
   ```powershell
   cd D:\P_2\ai_interviewer
   py -3 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. (Optional) Start Ollama locally in another terminal:
   - Install from `https://ollama.com/`
   - Pull/run model:
     ```powershell
     ollama run llama3.2
     ```
   - Or set environment variables before running the app:
     ```powershell
     $env:OLLAMA_URL = "http://localhost:11434"
     $env:OLLAMA_MODEL = "llama3.2"
     ```

4. Run the server:
   ```powershell
   python run.py
   ```
   The server will start at `http://localhost:8000`.

5. Verify health:
   - Open `http://localhost:8000/health`
   - System status: `http://localhost:8000/system-status`

## Notes
- The app uses simple placeholder services for speech and vision (no heavy models required). Advanced services (`app/services/speech_service.py`, `vision_service.py`) are present but not used by default.
- Uploaded sessions are stored in `sessions/`.
- Static assets are under `static/` and templates under `app/templates/`.

## Development
- Enable auto-reload by setting `reload=True` in `run.py` during development.
- API routes are under `app/routers/`.
