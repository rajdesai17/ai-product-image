from typing import Literal, Optional

from pydantic import BaseModel, HttpUrl


class ProcessVideoRequest(BaseModel):
  video_url: HttpUrl


class ProcessVideoResponse(BaseModel):
  status: Literal["success", "error"]
  job_id: str
  product_name: Optional[str] = None
  key_frame_url: Optional[str] = None
  segmented_image_url: Optional[str] = None
  enhanced_shots: Optional[list[str]] = None
  processing_time_seconds: Optional[float] = None
  message: Optional[str] = None

