## AI Product Extractor

Create product-only images and enhanced shots from a YouTube URL.

## TLDR

**What it does:** Extracts product images from YouTube videos, removes backgrounds, and generates 2 enhanced marketing shots.

**How it works:**
- Downloads video → extracts frames → Gemini identifies product → selects best frame
- **Background removal:** Tries Gemini once, **falls back to rembg** to guarantee transparent PNG
- **Enhancement:** Gemini generates 2 shots (studio + lifestyle); uses fallback copies if needed

**Setup:** Clone repo, set `GEMINI_API_KEY` in `backend/.env` (Gemini implemented; test with your own API key). Returns 2 background-removed enhanced shots.

## workflow
<img width="1841" height="770" alt="image" src="https://github.com/user-attachments/assets/f3fda8dc-b112-4ab0-ad3d-1f157c92fa42" />


### 1) Approach (step-by-step)
- ✅ **Input:** User enters a YouTube URL (Shorts are auto-normalized to `watch?v=`).
- ✅ **Frame Extraction:** Download video via yt-dlp, sample frames with OpenCV.
- ✅ **Top Frames:** Gemini (vision) selects the top 3 frames.
- ✅ **Product Name:** Gemini identifies the product from those frames.
- ✅ **Best Frame:** Gemini selects the single best frame index with up to 3 retries; if Gemini fails, the workflow falls back to the first frame.
- ✅ **Segmentation:** Gemini tries background removal once and immediately falls back to `rembg` so a transparent PNG is always produced.
- ✅ **Enhancement:** Gemini attempts studio/lifestyle/creative prompts until two shots are generated; if Gemini can’t finish, the pipeline duplicates successful shots so the frontend always receives two images.
- ✅ **Output:** Backend saves files to `/static/{job_id}/...` and returns URLs in JSON.

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

### 2.1) Image Storage & Delivery
**How segmented images and frames are stored and passed:**
- **Storage**: All images (frames, segmented, enhanced) are stored on the backend filesystem at `backend/static/{job_id}/`:
  ```text
  backend/static/
    └── {job_id}/
        ├── frames/
        │   ├── frame_000.jpg
        │   └── ...
        ├── segmented.png
        └── enhanced/
            ├── enhanced_studio.png
            └── ...
  ```
- **Backend Processing**:
  - Workflow nodes save images directly to disk (e.g., `segmented.png` saved to `backend/static/{job_id}/segmented.png`)
  - File paths are converted to URLs using `to_static_url()` (e.g., `/static/{job_id}/segmented.png`)
  - FastAPI serves static files via `StaticFiles` mounted at `/static` route
- **Frontend Delivery**:
  - Backend returns JSON response with URLs (not binary data)
  - Frontend receives URLs like `/static/{job_id}/segmented.png`
  - Frontend fetches images via HTTP requests to `{API_BASE_URL}/static/{job_id}/...`
  - Images are displayed using `<img src={resolveStaticUrl(segmented_image_url)} />`

**Note**: Images are NOT passed as binary data in the JSON response. They're stored on disk and accessed via HTTP URLs.

### 2.2) Image Enhancement Workflow & API Integration

**Overview:**
The enhancement step uses Gemini's image generation API (Gemini nano banana / `gemini-2.5-flash-image-preview`) to create 2-3 professional product shots with different backgrounds and styles from the segmented product image.

**API Integration Details:**
- **Model**: `gemini-2.5-flash-image-preview` (Gemini nano banana)
- **Pattern**: Image + Text-to-Image editing (as per Gemini API documentation)
- **Input**: Segmented product image (PNG with transparent background) + style-specific text prompt
- **Output**: Enhanced product shot with new background/style matching the prompt

**Implementation:**
- **LangGraph Node**: `enhance_images` node in `backend/app/workflow.py` (lines 161-212)
- **Service Method**: `GeminiService.generate_enhanced_shot()` in `backend/app/services/gemini.py` (lines 321-396)
- **Prompts**: Defined in `backend/app/services/enhancement_prompts.py` with 3 distinct styles:
  - **Studio**: Professional white background, soft even lighting
  - **Lifestyle**: Modern wooden desk scene, natural window lighting, blurred background
  - **Creative**: Vibrant gradient background (blue to purple), dramatic side lighting

**API Call Pattern:**
```python
# Matches Gemini API documentation pattern for Image + Text-to-Image editing
parts = [
  types.Part(
    inline_data=types.Blob(
      data=segmented_image_bytes,
      mime_type="image/png",
    )
  ),
  types.Part(text=style_prompt),
]

response = client.models.generate_content(
  model="gemini-2.5-flash-image-preview",
  contents=types.Content(parts=parts),
)

# Extract image bytes from response
image_data = extract_image_bytes(response)
```

**Error Handling & Retry Logic:**
- **Retry Strategy**: Up to 3 attempts with exponential backoff on quota errors
- **Graceful Degradation**: If one style fails (e.g., quota exceeded), the workflow continues with remaining styles
- **Quota Detection**: Automatically detects 429/quota errors and waits before retrying
- **Logging**: Comprehensive logging for debugging and monitoring

**Workflow Steps:**
1. Read segmented product image (PNG) from disk
2. For each style (studio, lifestyle, creative):
   - Build style-specific prompt using `build_prompt(style, product_name)`
   - Call Gemini API with image + prompt
   - Retry up to 3 times on quota errors
   - Save generated image to `backend/static/{job_id}/enhanced/enhanced_{style}.png`
   - Continue to next style even if current one fails
3. Return list of successfully generated enhanced shot paths
4. Convert paths to URLs for frontend display

**Prompt Engineering:**
Each style uses a descriptive prompt that:
- References the product name for context
- Describes the desired background and lighting
- Specifies the mood/atmosphere
- Preserves product proportions and core design

Example prompt (Studio style):
```text
Generate an enhanced marketing image featuring the {product_name}. 
A professional studio product photograph of the provided product on a clean 
white background with soft, even lighting. High-resolution, sharp focus. 
Preserve the product's proportions and core design.
```

### 3) Technologies used
- **Backend**: FastAPI, LangGraph, Uvicorn
- **Video/Frames**: yt-dlp, OpenCV
- **Images**: Pillow
- **AI**:
  - Google Gemini Vision API (`gemini-2.5-flash`) for product identification and frame selection
  - Google Gemini Image Generation API (`gemini-2.5-flash-image-preview` / Gemini nano banana) for segmentation and enhancement
- **Frontend**: Next.js (TypeScript), Tailwind CSS, fetch API

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

### 5) Time spent
- **Total:** ~7 hours
- **Frontend (Next.js UI + gallery):** ~1 hour
- **Gemini integration (vision + image APIs):** ~2 hours
- **LangGraph workflow orchestration:** ~2 hours
- **Background removal (`rembg` fallback) work:** ~1 hour
- **End-to-end integration & testing:** ~2 hours

### 6) Challenges & improvements
- **Challenges:**
  - Gemini image generation quota was exhausted during segmentation; implemented an automatic `rembg` fallback to keep background removal reliable.
  - Intermittent Gemini network drops during best-frame calls; added retry/backoff and a deterministic fallback frame so the workflow never fails.
- **Possible improvements:**
  - Re-run enhancement against fully credited Gemini image models to unlock more styles per request and increase output count (e.g., 5–6 variants).
  - Refine enhancement prompts based on real results to better control lighting and styling.
  - Add UI controls so users can request additional edited product-showcase shots or provide custom prompt guidance.
