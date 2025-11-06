from __future__ import annotations

from pathlib import Path

from rembg import remove


class SegmentationError(Exception):
  """Raised when background removal fails."""


def segment_product(source_image: Path, destination_image: Path) -> Path:
  if not source_image.exists():
    raise SegmentationError("Source image for segmentation not found")

  try:
    with source_image.open("rb") as file:
      data = file.read()
      result = remove(data)
  except Exception as error:
    raise SegmentationError("Failed to remove background from image") from error

  destination_image.parent.mkdir(parents=True, exist_ok=True)
  with destination_image.open("wb") as file:
    file.write(result)

  return destination_image




