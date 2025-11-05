# AI Product Extractor - MVP Requirements

## 🎯 Project Overview
One-click tool that transforms YouTube product videos into professional marketing images. User submits a URL, system identifies product, extracts best frame, removes background, and generates 3 studio-quality product shots.

---

## 📁 Project Structure
```
ai-product-extractor/
├── backend/                 # Python + FastAPI + LangGraph
│   ├── app/
│   │   ├── main.py         # FastAPI entry point
│   │   ├── workflow.py     # LangGraph workflow definition
│   │   ├── nodes/          # Individual processing nodes
│   │   │   ├── extraction.py
│   │   │   ├── segmentation.py
│   │   │   └── enhancement.py
│   │   ├── models.py       # Pydantic models
│   │   └── config.py       # Configuration & env vars
│   ├── static/             # Generated images directory
│   ├── requirements.txt
│   └── .env
│
└── frontend/               # Next.js + TypeScript + Tailwind
    ├── src/
    │   ├── app/
    │   │   ├── page.tsx    # Main page
    │   │   └── layout.tsx  
    │   ├── components/
    │   │   ├── VideoInput.tsx
    │   │   ├── ProcessingStatus.tsx
    │   │   └── ResultsGallery.tsx
    │   ├── lib/
    │   │   └── api.ts      # API client
    │   └── types/
    │       └── index.ts    # TypeScript types
    ├── public/
    ├── package.json
    └── .env.local
```

---

## 🔧 Backend Requirements

### **Tech Stack**
- **Runtime**: Python 3.11+
- **Framework**: FastAPI 0.104+
- **AI Orchestration**: LangGraph 0.2+
- **AI Models**: Google Gemini 2.5 Flash (vision + image generation)
- **Video Processing**: yt-dlp 2023.12+, opencv-python 4.8+
- **Image Processing**: Pillow 10.1+, rembg 2.0+
- **Server**: uvicorn 0.24+

### **Dependencies** (`requirements.txt`)
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
langchain==0.1.0
langgraph==0.2.0
google-generativeai==0.3.0
yt-dlp==2023.12.30
opencv-python==4.8.1.78
Pillow==10.1.0
rembg==2.0.50
python-dotenv==1.0.0
pydantic==2.5.0
aiofiles==23.2.1
```

### **Environment Variables** (`.env`)
```env
GEMINI_API_KEY=your_gemini_api_key_here
BACKEND_PORT=8000
STATIC_DIR=./static
FRAME_SAMPLE_RATE=2  # Sample 1 frame every 2 seconds
MAX_VIDEO_DURATION=300  # 5 minutes max
```

### **API Endpoints**

#### `POST /api/process-video`
**Request Body:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response (Success - 200):**
```json
{
  "status": "success",
  "job_id": "uuid-string",
  "product_name": "Sony WH-1000XM5 Headphones",
  "key_frame_url": "/static/uuid/frame_042.jpg",
  "segmented_image_url": "/static/uuid/segmented.png",
  "enhanced_shots": [
    "/static/uuid/enhanced_studio.jpg",
    "/static/uuid/enhanced_lifestyle.jpg",
    "/static/uuid/enhanced_creative.jpg"
  ],
  "processing_time_seconds": 45.2
}
```

**Response (Error - 400/500):**
```json
{
  "status": "error",
  "message": "Invalid YouTube URL provided",
  "job_id": "uuid-string"
}
```

#### `GET /static/{job_id}/{filename}`
Serves generated images as static files.

---

## 🎨 Frontend Requirements

### **Tech Stack**
- **Framework**: Next.js 14+ (App Router)
- **Language**: TypeScript 5+
- **Styling**: Tailwind CSS 3.4+
- **HTTP Client**: Native fetch API
- **State Management**: React useState (no external library needed)

### **Dependencies** (`package.json`)
```json
{
  "dependencies": {
    "next": "^14.0.4",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "typescript": "^5.3.3",
    "tailwindcss": "^3.4.0"
  },
  "devDependencies": {
    "@types/node": "^20.10.6",
    "@types/react": "^18.2.46",
    "@types/react-dom": "^18.2.18",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32"
  }
}
```

### **Environment Variables** (`.env.local`)
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### **TypeScript Types** (`src/types/index.ts`)
```typescript
export interface ProcessVideoRequest {
  video_url: string;
}

export interface ProcessVideoResponse {
  status: 'success' | 'error';
  job_id: string;
  product_name?: string;
  key_frame_url?: string;
  segmented_image_url?: string;
  enhanced_shots?: string[];
  processing_time_seconds?: number;
  message?: string;
}

export interface ProcessingState {
  isProcessing: boolean;
  error: string | null;
  result: ProcessVideoResponse | null;
}
```

### **UI Components**

#### 1. **VideoInput Component**
- Text input for YouTube URL
- "Generate Product Images" button
- Basic URL validation (YouTube domain check)
- Disabled state during processing

#### 2. **ProcessingStatus Component**
- Loading spinner
- Status text: "Processing video... This may take 30-60 seconds"
- Progress indicator (optional for MVP)

#### 3. **ResultsGallery Component**
- **Section 1**: Product name as heading
- **Section 2**: Original extracted frame (labeled)
- **Section 3**: Segmented product image (labeled)
- **Section 4**: 3 enhanced shots in a grid layout (labeled: Studio, Lifestyle, Creative)
- Download buttons for each image (optional for MVP)

### **UI Flow**
```
Initial State → VideoInput visible
        ↓
User submits URL → ProcessingStatus shows
        ↓
API call completes → ResultsGallery displays
        ↓
User can submit new URL → Reset to Initial State
```

---

## 🔄 LangGraph Workflow (Backend)

### **State Schema**
```python
from typing import TypedDict, List

class WorkflowState(TypedDict):
    video_url: str
    job_id: str
    product_name: str
    sampled_frames: List[str]  # File paths
    best_frame_path: str
    segmented_image_path: str
    enhanced_shots: List[str]  # File paths
    error: str | None
```

### **Workflow Nodes**

#### **Node 1: Frame Extraction**
- **Input**: `video_url`
- **Process**:
  - Use yt-dlp to get video stream
  - Sample 1 frame every 2 seconds using OpenCV
  - Save frames to `/static/{job_id}/frames/`
  - Take first 10-15 frames
- **Output**: `sampled_frames` list

#### **Node 2: Product Identification**
- **Input**: `sampled_frames` (first 10 frames)
- **Process**:
  - Send frames to Gemini 2.5 Flash
  - Prompt: "Analyze these frames from a product video. Identify the main product being showcased. Return only the product name (e.g., 'iPhone 15 Pro')."
- **Output**: `product_name`

#### **Node 3: Best Frame Selection**
- **Input**: `sampled_frames`, `product_name`
- **Process**:
  - Send all frames to Gemini
  - Prompt: "From these images, select the frame where the '{product_name}' is most clearly visible, well-lit, and prominently shown. Return only the frame index number (0-based)."
  - Get best frame index
- **Output**: `best_frame_path`

#### **Node 4: Segmentation**
- **Input**: `best_frame_path`
- **Process**:
  - Use rembg library to remove background
  - Save as PNG with transparency
- **Output**: `segmented_image_path`

#### **Node 5: Enhancement (x3)**
- **Input**: `segmented_image_path`, `product_name`
- **Process**:
  - Generate 3 images using Gemini 2.5 Flash Image (Nano Banana)
  - **Prompt 1 (Studio)**: "A professional studio product photograph of {segmented_image} on a clean white background with soft, even lighting. High-resolution, sharp focus."
  - **Prompt 2 (Lifestyle)**: "A lifestyle product shot of {segmented_image} on a modern wooden desk with a coffee cup nearby, natural window lighting, blurred background."
  - **Prompt 3 (Creative)**: "A creative product shot of {segmented_image} on a vibrant gradient background (blue to purple), dramatic side lighting, studio quality."
- **Output**: `enhanced_shots` list

### **Graph Structure**
```
START → Extract Frames → Identify Product → Select Best Frame 
     → Segment Image → Enhance (x3) → END
```

---

## 🚀 MVP Features

### **Included**
✅ Single YouTube URL input  
✅ One product per video  
✅ Automatic frame extraction (sampled)  
✅ AI-powered product identification  
✅ AI-powered best frame selection  
✅ Background removal (segmentation)  
✅ 3 enhanced product shots (different styles)  
✅ Clean, responsive UI  
✅ Error handling  

### **Excluded (Future Enhancements)**
❌ Multiple products per video  
❌ Real-time progress updates (WebSocket)  
❌ User authentication  
❌ Image editing capabilities  
❌ Batch processing  
❌ Database storage  
❌ Download all as ZIP  

---

## 📝 README Requirements

Your final README should include:

1. **Project Description**: What it does, why it's useful
2. **Tech Stack**: List of all technologies used
3. **Prerequisites**: Python 3.11+, Node.js 18+, Gemini API key
4. **Installation**:
   - Backend setup steps
   - Frontend setup steps
   - Environment variable configuration
5. **Usage**: 
   - How to run backend
   - How to run frontend
   - Example YouTube URLs for testing
6. **Architecture**:
   - System diagram (optional)
   - LangGraph workflow explanation
   - API endpoint documentation
7. **Time Spent**:
   - Breakdown by section (Setup, Backend, Frontend, Testing, Docs)
8. **Challenges Faced**:
   - Technical difficulties
   - How you solved them
   - Gemini API usage details
9. **Future Improvements**:
   - Scalability ideas
   - Feature enhancements
   - Performance optimizations

---

## ⏱️ Estimated Time Breakdown

| Task | Time | Details |
|------|------|---------|
| **Setup** | 1.5h | Project structure, dependencies, environment |
| **Backend - LangGraph** | 5h | 5 nodes, state management, error handling |
| **Backend - FastAPI** | 1.5h | API endpoint, static file serving |
| **Frontend - Components** | 3h | VideoInput, ProcessingStatus, ResultsGallery |
| **Frontend - Integration** | 1h | API calls, state management |
| **Testing** | 2h | End-to-end testing with sample videos |
| **Documentation** | 2h | README, code comments, API docs |
| **Total** | **16h** | Clean MVP delivery |

---

## 🧪 Testing Strategy

### **Backend Testing**
1. Test each LangGraph node independently
2. Test with various YouTube URLs (tech reviews, unboxing videos)
3. Test error scenarios (invalid URL, private video, no product visible)
4. Verify all generated images are accessible

### **Frontend Testing**
1. Test URL validation
2. Test loading states
3. Test error display
4. Test results rendering with mock data
5. Test responsive design (mobile, tablet, desktop)

### **Recommended Test Videos**
- iPhone review: Clear product shots
- Headphones unboxing: Good lighting
- Gadget demo: Product in action

---

## 🔒 Security Considerations (MVP)

- ✅ Input validation (YouTube URL format)
- ✅ File size limits for generated images
- ✅ Temporary file cleanup after processing
- ✅ API rate limiting (basic)
- ⚠️ Note: No authentication in MVP (add for production)

---

## 📦 Deliverables

1. **Source Code**:
   - `/backend` - Complete Python backend
   - `/frontend` - Complete Next.js frontend
   
2. **Documentation**:
   - README.md (comprehensive)
   - API documentation
   - Setup instructions
   
3. **Demo Materials**:
   - Sample input (YouTube URL)
   - Sample output images
   - Screenshots/video of working system (optional)

---

## 🎯 Success Criteria

✅ User can paste any product review YouTube URL  
✅ System processes video in < 60 seconds  
✅ Identifies product correctly (80%+ accuracy expected)  
✅ Generates 3 distinct, high-quality product shots  
✅ Clean, professional UI  
✅ No crashes on common error scenarios  
✅ Well-documented codebase  

---

**Ready to build? Next steps:**
1. Set up backend environment
2. Set up frontend environment  
3. Implement LangGraph workflow
4. Connect frontend to backend
5. Test and document