from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List

import cv2  # type: ignore
from yt_dlp import YoutubeDL


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


def _download_video(video_url: str, output_dir: Path) -> tuple[Path, int | None]:
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
  }

  try:
    with YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(normalized_url, download=True)
      file_path = Path(ydl.prepare_filename(info))
      duration = info.get("duration")
  except Exception as error:
    error_msg = str(error) if error else "Unknown error"
    raise VideoProcessingError(f"Unable to download video: {error_msg}") from error

  if not file_path.exists():
    raise VideoProcessingError("Downloaded video file not found")

  return file_path, duration


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

