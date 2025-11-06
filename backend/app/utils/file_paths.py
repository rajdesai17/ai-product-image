from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class JobPaths:
  job_id: str
  job_dir: Path
  frames_dir: Path
  segmented_image_path: Path
  enhanced_dir: Path

  def enhancement_path(self, suffix: str) -> Path:
    safe_suffix = suffix.replace(" ", "_").lower()
    return self.enhanced_dir / f"enhanced_{safe_suffix}.png"


def ensure_job_paths(static_dir: Path, job_id: str) -> JobPaths:
  job_dir = static_dir / job_id
  frames_dir = job_dir / "frames"
  segmented_image_path = job_dir / "segmented.png"
  enhanced_dir = job_dir / "enhanced"

  frames_dir.mkdir(parents=True, exist_ok=True)
  enhanced_dir.mkdir(parents=True, exist_ok=True)

  return JobPaths(
    job_id=job_id,
    job_dir=job_dir,
    frames_dir=frames_dir,
    segmented_image_path=segmented_image_path,
    enhanced_dir=enhanced_dir,
  )


def to_static_url(static_dir: Path, file_path: Path) -> str:
  relative = file_path.resolve().relative_to(static_dir.resolve())
  return f"/static/{relative.as_posix()}"




