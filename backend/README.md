# AI Product Extractor Backend

## Prerequisites
- Python 3.11+
- Gemini API key (`GEMINI_API_KEY`)

## Setup
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and add your real Gemini key.

## Running
```powershell
cd backend
.\.venv\Scripts\Activate
uvicorn app.main:app --reload --port $env:BACKEND_PORT
```

Static assets are written to the `static/` directory and served at `/static/{job_id}/...`.




