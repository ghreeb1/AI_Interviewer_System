
# **AI Interviewer**   
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)  
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)  
[![Ollama](https://img.shields.io/badge/Ollama-local-orange.svg)](https://ollama.com/)  
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)  

> A **FastAPI** web app for **mock interviews** using a local **LLM (Ollama)**, basic speech & vision placeholders, and **CV parsing**.  

---

##  **Preview**
![AI Interviewer Preview](https://github.com/ghreeb1/AI_Interviewer_System/blob/master/static/1.png)

---

##  **Prerequisites**
- **Python** 3.10+ (recommended)  
- **Windows PowerShell**  
- *(Optional)* Ollama with model `llama3.2` running locally at `http://localhost:11434`  

---

##  **Quick Start (Windows)**

###  Create & activate a virtual environment:
```powershell
cd D:\P_2\ai_interviewer
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

###  Install dependencies:
```powershell
pip install -r requirements.txt
```

###  *(Optional)* Start Ollama locally in another terminal:
- Download from [https://ollama.com/](https://ollama.com/)  
- Pull & run the model:
```powershell
ollama run llama3.2
```
- Or set environment variables:
```powershell
$env:OLLAMA_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "llama3.2"
```

###  Run the server:
```powershell
python run.py
```
 Server will start at: `http://localhost:8000`

###  Verify system status:
- **Health check** → [http://localhost:8000/health](http://localhost:8000/health)  
- **System status** → [http://localhost:8000/system-status](http://localhost:8000/system-status)  

---

##  **Notes**
- Uses **simple placeholder services** for speech & vision (no heavy models).  
- Advanced services exist in:
  - `app/services/speech_service.py`  
  - `app/services/vision_service.py`  
  but are **disabled by default**.  
- Uploaded interview sessions are saved in the `sessions/` directory.  
- Static files → `static/`  
- Templates → `app/templates/`  

---

##  **Development Mode**
- Enable auto-reload by setting:
```python
reload=True
```
in `run.py`.  
- API routes are located in `app/routers/`.

---

##  **Features**
 Mock interview simulation with AI  
 CV upload & parsing  
 Simple speech & vision placeholders  
 Health & system status endpoints  

---

##  Contact

**Developer:**  
Mohamed Khaled

**Email:**  
qq11gharipqq11@gmail.com

**Project Link:**  
[https://github.com/ghreeb1/Eye_Disease.Classification](https://github.com/ghreeb1/Eye_Disease.Classification)

**LinkedIn:**  
[https://linkedin.com/in/mohamed-khaled-3a9021263](https://linkedin.com/in/mohamed-khaled-3a9021263)


