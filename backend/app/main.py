from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import ensure_directories, settings
from .models import ProcessVideoRequest, ProcessVideoResponse
from .services.gemini import GeminiService, GeminiServiceError
from .services.segmentation import SegmentationError
from .services.video import VideoProcessingError
from .workflow import convert_paths_to_urls, run_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(title="AI Product Extractor")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


ensure_directories()
app.mount("/static", StaticFiles(directory=settings.static_dir, check_dir=False), name="static")


gemini_service = GeminiService(api_key=settings.gemini_api_key)


@app.post("/api/process-video", response_model=ProcessVideoResponse)
async def process_video(request: ProcessVideoRequest) -> ProcessVideoResponse:
  job_id = str(uuid.uuid4())
  start_time = time.perf_counter()

  try:
    video_url_str = str(request.video_url)
    logger.info(f"Processing video: {video_url_str}")
    state = run_workflow(
      video_url=video_url_str,
      job_id=job_id,
      settings=settings,
      gemini=gemini_service,
    )

    transformed_state = convert_paths_to_urls(state, settings.static_dir)

    return ProcessVideoResponse(
      status="success",
      job_id=job_id,
      product_name=transformed_state.get("product_name"),
      key_frame_url=transformed_state.get("key_frame_url"),
      segmented_image_url=transformed_state.get("segmented_image_url"),
      enhanced_shots=transformed_state.get("enhanced_shots"),
      processing_time_seconds=time.perf_counter() - start_time,
    )

  except (VideoProcessingError, GeminiServiceError, SegmentationError) as error:
    logger.error(f"Processing error: {error}", exc_info=True)
    raise HTTPException(status_code=400, detail=str(error)) from error
  except Exception as error:  # pragma: no cover
    logger.error(f"Unexpected error: {error}", exc_info=True)
    error_msg = f"Internal server error: {str(error)}"
    raise HTTPException(status_code=500, detail=error_msg) from error


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
  return JSONResponse(
    status_code=exc.status_code,
    content={
      "status": "error",
      "job_id": getattr(request.state, "job_id", ""),
      "message": str(exc.detail),
    },
  )

