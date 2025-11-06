from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from typing import List

import cv2  # type: ignore
from yt_dlp import YoutubeDL

logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
  """Raised when a video cannot be downloaded or processed."""


def download_and_sample_frames(
  video_url: str,
  target_dir: Path,
  frame_sample_rate: int,
  max_video_duration: int,
  max_frames: int = 15,
) -> List[Path]:
  """Download a YouTube video and sample frames every N seconds.

  Args:
    video_url: Public YouTube URL.
    target_dir: Directory under which sampled frames will be written.
    frame_sample_rate: Interval in seconds between sampled frames.
    max_video_duration: Maximum duration (seconds) allowed for processing.
    max_frames: Cap of frames to persist (defaults to 15 per MVP).

  Returns:
    A list of frame image paths in chronological order.
  """

  target_dir.mkdir(parents=True, exist_ok=True)

  with tempfile.TemporaryDirectory() as tmp_dir:
    download_dir = Path(tmp_dir)
    video_path, duration = _download_video(video_url, download_dir)

    if duration and duration > max_video_duration:
      raise VideoProcessingError(
        f"Video duration {duration}s exceeds limit of {max_video_duration}s."
      )

    return _sample_frames(
      video_path=video_path,
      destination_dir=target_dir,
      frame_sample_rate=frame_sample_rate,
      max_frames=max_frames,
    )


def _download_video(video_url: str, output_dir: Path, max_retries: int = 3) -> tuple[Path, int | None]:
  """Download video with retry logic and increased timeouts.
  
  Args:
    video_url: YouTube URL to download
    output_dir: Directory to save the video
    max_retries: Maximum number of retry attempts (default: 3)
    
  Returns:
    Tuple of (video_path, duration)
  """
  # Normalize YouTube Shorts URLs to regular watch format
  normalized_url = video_url
  if "/shorts/" in video_url:
    video_id = video_url.split("/shorts/")[-1].split("?")[0]
    normalized_url = f"https://www.youtube.com/watch?v={video_id}"

  ydl_opts = {
    "format": "worst",  # Use worst quality single file format (no merging needed)
    "outtmpl": str(output_dir / "video.%(ext)s"),
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    # Increase timeouts to handle slow connections
    "socket_timeout": 120,  # 2 minutes for socket operations
    "retries": 10,  # yt-dlp internal retries
    "fragment_retries": 10,  # Retries for video fragments
    "file_access_retries": 3,  # Retries for file access
    # Additional options for better reliability
    "http_chunk_size": 10485760,  # 10MB chunks for better performance
    "noprogress": True,
  }

  last_error = None
  for attempt in range(max_retries):
    try:
      logger.info(f"Attempting to download video (attempt {attempt + 1}/{max_retries}): {normalized_url}")
      with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(normalized_url, download=True)
        file_path = Path(ydl.prepare_filename(info))
        duration = info.get("duration")
      
      if not file_path.exists():
        raise VideoProcessingError("Downloaded video file not found")
      
      logger.info(f"Video downloaded successfully: {file_path}")
      return file_path, duration
      
    except Exception as error:
      last_error = error
      error_msg = str(error) if error else "Unknown error"
      
      if attempt < max_retries - 1:
        # Exponential backoff: wait longer on each retry
        wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
        logger.warning(
          f"Download attempt {attempt + 1} failed: {error_msg}. "
          f"Retrying in {wait_time} seconds..."
        )
        time.sleep(wait_time)
        # Increase timeout on retry for slow connections
        ydl_opts["socket_timeout"] = min(ydl_opts["socket_timeout"] + 30, 300)  # Cap at 5 minutes
      else:
        # Last attempt failed
        logger.error(f"All {max_retries} download attempts failed. Last error: {error_msg}")
        raise VideoProcessingError(f"Unable to download video after {max_retries} attempts: {error_msg}") from error

  # Should never reach here, but just in case
  if last_error:
    raise VideoProcessingError(f"Unable to download video: {last_error}") from last_error
  raise VideoProcessingError("Unable to download video: Unknown error")


def _sample_frames(
  video_path: Path,
  destination_dir: Path,
  frame_sample_rate: int,
  max_frames: int,
) -> List[Path]:
  capture = cv2.VideoCapture(str(video_path))

  if not capture.isOpened():
    capture.release()
    raise VideoProcessingError("Unable to open video for processing")

  fps = capture.get(cv2.CAP_PROP_FPS) or 30
  if fps <= 0:
    fps = 30

  frame_interval = int(fps * frame_sample_rate)
  if frame_interval <= 0:
    frame_interval = int(fps)

  sampled_paths: List[Path] = []
  frame_index = 0
  saved_frames = 0

  try:
    while saved_frames < max_frames:
      success, frame = capture.read()
      if not success or frame is None:
        break

      if frame_index % frame_interval == 0:
        output_path = destination_dir / f"frame_{frame_index:03d}.jpg"
        if not cv2.imwrite(str(output_path), frame):
          raise VideoProcessingError(f"Failed to write frame to {output_path}")
        sampled_paths.append(output_path)
        saved_frames += 1

      frame_index += 1
  finally:
    capture.release()

  if not sampled_paths:
    raise VideoProcessingError("No frames extracted from video")

  return sampled_paths

