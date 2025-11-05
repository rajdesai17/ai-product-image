## AI Product Extractor

Create product-only images and enhanced shots from a YouTube URL.

## workflow
<img width="1841" height="770" alt="image" src="https://github.com/user-attachments/assets/f3fda8dc-b112-4ab0-ad3d-1f157c92fa42" />


### 1) Approach (step-by-step)
- ✅ **Input:** User enters a YouTube URL (Shorts are auto-normalized to `watch?v=`).
- ✅ **Frame Extraction:** Download video via yt-dlp, sample frames with OpenCV.
- ✅ **Top Frames:** Gemini (vision) selects the top 3 frames.
- ✅ **Product Name:** Gemini identifies the product from those frames.
- ✅ **Best Frame:** Gemini selects the single best frame index.
- [ ] **Segmentation:** Gemini removes background from the best frame (Gemini-only; retries on quota).
- [ ] **Enhancement:** Gemini generates 2–3 styled shots (studio, lifestyle, creative), skipping styles if quota is hit.
- [ ] **Output:** Backend saves files to `/static/{job_id}/...` and returns URLs in JSON.

### 2) LangGraph ↔ React communication (API & data flow)
- Endpoint: `POST /api/process-video`
  - Request JSON: `{ "video_url": "<YouTube URL>" }`
  - Response JSON (success):
    ```json
    {
      "status": "success",
      "job_id": "uuid",
      "product_name": "...",
      "key_frame_url": "/static/{job_id}/frames/frame_XXX.jpg",
      "segmented_image_url": "/static/{job_id}/segmented.png",
      "enhanced_shots": ["/static/{job_id}/enhanced/enhanced_studio.png", "..."],
      "processing_time_seconds": 42.1
    }
    ```
- Data flow:
  - React sends URL → FastAPI.
  - FastAPI runs LangGraph pipeline (nodes listed above).
  - Files are written under `backend/static/{job_id}` and served at `/static`.
  - React renders returned URLs in the gallery.

### 3) Technologies used
- Backend: FastAPI, LangGraph, Uvicorn
- Video/Frames: yt-dlp, OpenCV
- Images: Pillow
- AI: Google Gemini (vision + image editing); segmentation is Gemini-only
- Frontend: Next.js (TypeScript), Tailwind CSS, fetch API

### 4) How to run / demo (Windows PowerShell)
- Prerequisites: Python 3.11+, Node.js 18+, Gemini API key

Backend
```powershell
cd "backend"
python -m venv .venv
.\.venv\Scripts\Activate
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit backend\.env and set GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```
- API: http://localhost:8000
- Docs: http://localhost:8000/docs

Frontend
```powershell
cd "frontend"
npm install
"NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" | Out-File -FilePath .env.local -Encoding utf8
npm run dev
```
- App: http://localhost:3000

Demo (PowerShell)
```powershell
$body = @{ video_url = "https://youtube.com/shorts/-2DvWn6wUFc" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/process-video" -Method POST -ContentType "application/json" -Body $body | ConvertTo-Json -Depth 5
```
