from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from google import genai
from google.genai import types


class GeminiServiceError(Exception):
  """Raised when Gemini requests fail."""


@dataclass
class GeminiService:
  api_key: str
  text_vision_model: str = "gemini-2.5-flash"
  image_model: str = "gemini-2.5-flash"
  client: genai.Client = field(init=False)

  def __post_init__(self) -> None:
    self.client = genai.Client(api_key=self.api_key)

  def identify_product(self, frames: Sequence[Path]) -> str:
    if not frames:
      raise GeminiServiceError("No frames provided for product identification")

    contents = types.Content(parts=list(self._iter_image_parts(frames)) + [
      types.Part(
        text=(
          "Analyze these frames from a product video. Identify the main product "
          "being showcased. Return only the product name (e.g., 'iPhone 15 Pro')."
        )
      )
    ])

    try:
      response = self.client.models.generate_content(
        model=self.text_vision_model,
        contents=contents,
      )
    except Exception as error:
      raise GeminiServiceError("Gemini product identification failed") from error

    text = (response.text or "").strip()
    if not text:
      raise GeminiServiceError("Gemini returned an empty product name")

    return text

  def select_best_frame(self, frames: Sequence[Path], product_name: str) -> int:
    if not frames:
      raise GeminiServiceError("No frames provided for best frame selection")

    prompt = (
      "From these images, select the frame where the "
      f"'{product_name}' is most clearly visible, well-lit, and prominently shown. "
      "Return only the frame index number (0-based)."
    )

    contents = types.Content(parts=list(self._iter_image_parts(frames)) + [types.Part(text=prompt)])

    try:
      response = self.client.models.generate_content(
        model=self.text_vision_model,
        contents=contents,
      )
    except Exception as error:
      raise GeminiServiceError("Gemini best frame selection failed") from error

    text = (response.text or "").strip()
    try:
      return int(_extract_first_integer(text))
    except ValueError as error:
      raise GeminiServiceError(f"Unable to parse frame index from Gemini response: {text}") from error

  def generate_enhanced_shot(self, prompt: str, segmented_image: Path) -> bytes:
    if not segmented_image.exists():
      raise GeminiServiceError("Segmented image not found for enhancement")

    parts = [
      types.Part(
        inline_data=types.Blob(
          data=segmented_image.read_bytes(),
          mime_type="image/png",
        )
      ),
      types.Part(text=prompt),
    ]

    try:
      response = self.client.models.generate_content(
        model=self.image_model,
        contents=types.Content(parts=parts),
      )
    except Exception as error:
      raise GeminiServiceError(f"Gemini image enhancement failed: {error}") from error

    if not response:
      raise GeminiServiceError("Gemini returned empty response")

    image_data = _extract_image_bytes(response)
    if image_data is None:
      raise GeminiServiceError("Gemini did not return image data in response")

    return image_data

  def _iter_image_parts(self, frames: Iterable[Path]) -> Iterable[types.Part]:
    for frame in frames:
      if not frame.exists():
        continue
      yield types.Part(
        inline_data=types.Blob(
          data=frame.read_bytes(),
          mime_type="image/jpeg",
        )
      )


def _extract_first_integer(text: str) -> int:
  digits = ""
  for char in text:
    if char.isdigit():
      digits += char
    elif digits:
      break
  if not digits:
    raise ValueError("No integer found")
  return int(digits)


def _extract_image_bytes(response: types.GenerateContentResponse) -> bytes | None:
  generated_images = getattr(response, "generated_images", None)
  if generated_images:
    for image in generated_images:
      if getattr(image, "data", None):
        return image.data

  candidates = getattr(response, "candidates", [])
  for candidate in candidates:
    for part in getattr(candidate, "content", types.Content()).parts or []:
      inline_data = getattr(part, "inline_data", None)
      if inline_data and getattr(inline_data, "data", None):
        data = inline_data.data
        if isinstance(data, bytes):
          return data
        if isinstance(data, str):
          try:
            return base64.b64decode(data)
          except Exception:
            continue

  return None

