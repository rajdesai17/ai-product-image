from __future__ import annotations

import base64
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GeminiServiceError(Exception):
  """Raised when Gemini requests fail."""
  
  def __init__(self, message: str, original_error: Exception | None = None, is_quota_error: bool = False, retry_after: float | None = None):
    super().__init__(message)
    self.original_error = original_error
    self.is_quota_error = is_quota_error
    self.retry_after = retry_after


def _is_quota_error(error: Exception) -> tuple[bool, float | None]:
  """Check if error is a quota/rate limit error and extract retry delay."""
  error_str = str(error).lower()
  error_repr = repr(error).lower()
  
  # Check for quota indicators
  is_quota = (
    "429" in error_str or
    "quota" in error_str or
    "resource_exhausted" in error_str or
    "rate limit" in error_str or
    "429" in error_repr or
    "quota" in error_repr or
    "resource_exhausted" in error_repr
  )
  
  if not is_quota:
    return False, None
  
  # Try to extract retry delay from error message
  retry_after = None
  # Look for patterns like "Please retry in 19.907498206s" or "retryDelay": "19s"
  retry_patterns = [
    r"retry in ([\d.]+)s",
    r"retrydelay['\"]?\s*:\s*['\"]?(\d+)s",
    r"wait (\d+)",
  ]
  
  full_error_text = f"{error_str} {error_repr}"
  for pattern in retry_patterns:
    match = re.search(pattern, full_error_text, re.IGNORECASE)
    if match:
      try:
        retry_after = float(match.group(1))
        break
      except (ValueError, IndexError):
        continue
  
  # Default retry delay if not found
  if retry_after is None:
    retry_after = 20.0  # Default 20 seconds
  
  return True, retry_after


def _retry_on_quota_error(max_retries: int = 2, base_delay: float = 1.0):
  """Decorator to retry function calls on quota errors."""
  def decorator(func):
    def wrapper(*args, **kwargs):
      last_error = None
      for attempt in range(max_retries + 1):
        try:
          return func(*args, **kwargs)
        except Exception as error:
          last_error = error
          is_quota, retry_after = _is_quota_error(error)
          
          if is_quota and attempt < max_retries:
            delay = retry_after if retry_after else base_delay * (2 ** attempt)
            logger.warning(f"Quota error on attempt {attempt + 1}/{max_retries + 1}, retrying after {delay:.1f}s: {error}")
            time.sleep(delay)
            continue
          else:
            # Not a quota error or max retries reached
            raise
      
      # If we get here, all retries failed
      raise last_error
    return wrapper
  return decorator


@dataclass
class GeminiService:
  api_key: str
  text_vision_model: str = "gemini-2.5-flash"
  image_model: str = "gemini-2.5-flash-image-preview"  # Use image generation model
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

  def select_top_frames(self, frames: Sequence[Path], top_n: int = 3) -> list[int]:
    """Select top N best frames from all frames for product identification."""
    if not frames:
      raise GeminiServiceError("No frames provided for frame selection")
    
    if len(frames) <= top_n:
      # If we have fewer frames than requested, return all indices
      return list(range(len(frames)))

    prompt = (
      f"Analyze these {len(frames)} frames from a product video. "
      f"Select the top {top_n} frames where the product is most clearly visible, "
      "well-lit, and prominently shown. Return only the frame index numbers (0-based) "
      f"as a comma-separated list of {top_n} numbers (e.g., '2,5,8')."
    )

    contents = types.Content(parts=list(self._iter_image_parts(frames)) + [types.Part(text=prompt)])

    try:
      response = self.client.models.generate_content(
        model=self.text_vision_model,
        contents=contents,
      )
    except Exception as error:
      raise GeminiServiceError("Gemini top frames selection failed") from error

    text = (response.text or "").strip()
    try:
      # Extract comma-separated integers
      indices = [int(x.strip()) for x in text.split(",") if x.strip().isdigit()]
      if len(indices) != top_n:
        # If we didn't get exactly top_n, take what we got or use first top_n frames
        if len(indices) < top_n:
          # Fill with sequential indices if needed
          for i in range(len(frames)):
            if i not in indices and len(indices) < top_n:
              indices.append(i)
        else:
          indices = indices[:top_n]
      
      # Validate indices are in range
      valid_indices = [idx for idx in indices if 0 <= idx < len(frames)]
      if not valid_indices:
        # Fallback to first top_n frames
        valid_indices = list(range(min(top_n, len(frames))))
      
      return valid_indices[:top_n]
    except (ValueError, IndexError) as error:
      raise GeminiServiceError(f"Unable to parse frame indices from Gemini response: {text}") from error

  def select_best_frame(self, frames: Sequence[Path], product_name: str, max_retries: int = 3) -> int:
    """Select the single best frame from a set of frames given the product name."""
    if not frames:
      raise GeminiServiceError("No frames provided for best frame selection")

    prompt = (
      "From these images, select the frame where the "
      f"'{product_name}' is most clearly visible, well-lit, and prominently shown. "
      "Return only the frame index number (0-based)."
    )

    contents = types.Content(parts=list(self._iter_image_parts(frames)) + [types.Part(text=prompt)])

    response = None
    last_error: Exception | None = None

    for attempt in range(max_retries):
      try:
        logger.info(
          "Calling Gemini for best frame selection with model: %s (attempt %s/%s)",
          self.text_vision_model,
          attempt + 1,
          max_retries,
        )
        response = self.client.models.generate_content(
          model=self.text_vision_model,
          contents=contents,
        )
        logger.info("Gemini best frame response received")
        break
      except Exception as error:
        last_error = error
        is_quota, retry_after = _is_quota_error(error)

        if attempt < max_retries - 1:
          delay = retry_after if is_quota and retry_after else 5.0 * (attempt + 1)
          logger.warning(
            "Gemini best frame selection attempt %s/%s failed: %s. Retrying in %.1fs...",
            attempt + 1,
            max_retries,
            error,
            delay,
          )
          time.sleep(delay)
          continue

        logger.error("Gemini best frame selection failed after %s attempts: %s", max_retries, error)
        is_quota_final, retry_after_final = _is_quota_error(error)
        raise GeminiServiceError(
          "Gemini best frame selection failed",
          original_error=error,
          is_quota_error=is_quota_final,
          retry_after=retry_after_final,
        ) from error

    if response is None and last_error:
      is_quota_final, retry_after_final = _is_quota_error(last_error)
      raise GeminiServiceError(
        f"Gemini best frame selection failed: {last_error}",
        original_error=last_error,
        is_quota_error=is_quota_final,
        retry_after=retry_after_final,
      ) from last_error

    if not response:
      raise GeminiServiceError("Gemini returned empty response for best frame selection")

    text = (response.text or "").strip()
    try:
      return int(_extract_first_integer(text))
    except ValueError as error:
      raise GeminiServiceError(f"Unable to parse frame index from Gemini response: {text}") from error

  def segment_product(self, source_image: Path, product_name: str, max_retries: int = 1) -> bytes:
    """Use Gemini to segment/crop the product from the image (remove background).
    
    Args:
      source_image: Path to the source image
      product_name: Name of the product for the prompt
      max_retries: Maximum number of retry attempts (default: 1 for quick fallback)
    """
    if not source_image.exists():
      raise GeminiServiceError("Source image not found for segmentation")

    # Use image editing: remove background, keep only product
    prompt = (
      f"Using the provided image of a {product_name}, remove all background and surroundings. "
      f"Keep only the product itself on a transparent background. "
      f"Preserve all product details, edges, and maintain high quality. "
      f"The final image should show just the {product_name} with no background."
    )

    # Read image bytes
    image_bytes = source_image.read_bytes()
    
    # Create parts: image first, then text prompt
    parts = [
      types.Part(
        inline_data=types.Blob(
          data=image_bytes,
          mime_type="image/jpeg",
        )
      ),
      types.Part(text=prompt),
    ]

    # Try only once (or max_retries times) - no retries for quick fallback to rembg
    response = None
    last_error = None
    for attempt in range(max_retries):
      try:
        logger.info(f"Calling Gemini for segmentation with model: {self.image_model} (attempt {attempt + 1}/{max_retries})")
        response = self.client.models.generate_content(
          model=self.image_model,
          contents=types.Content(parts=parts),
        )
        logger.info(f"Gemini response received: {type(response)}")
        break  # Success, exit retry loop
      except Exception as error:
        last_error = error
        # For segmentation, we want to fail fast and fallback to rembg
        # So we don't retry even on quota errors
        logger.warning(f"Gemini segmentation failed on attempt {attempt + 1}/{max_retries}: {error}")
        if attempt < max_retries - 1:
          # Only retry if max_retries > 1 and we haven't reached the limit
          continue
        else:
          # Final attempt failed - raise error immediately for rembg fallback
          is_quota_final, retry_after_final = _is_quota_error(error)
          error_msg = f"Gemini segmentation failed: {error}"
          raise GeminiServiceError(
            error_msg,
            original_error=error,
            is_quota_error=is_quota_final,
            retry_after=retry_after_final
          ) from error
    
    if response is None and last_error:
      is_quota_final, retry_after_final = _is_quota_error(last_error)
      raise GeminiServiceError(
        f"Gemini segmentation failed: {last_error}",
        original_error=last_error,
        is_quota_error=is_quota_final,
        retry_after=retry_after_final
      ) from last_error

    if not response:
      raise GeminiServiceError("Gemini returned empty response for segmentation")

    # Debug: Log full response structure
    logger.info(f"Response type: {type(response)}")
    logger.info(f"Response has candidates: {hasattr(response, 'candidates')}")
    if hasattr(response, "candidates") and response.candidates:
      logger.info(f"Number of candidates: {len(response.candidates)}")
      candidate = response.candidates[0]
      logger.info(f"Candidate type: {type(candidate)}")
      logger.info(f"Candidate attributes: {[attr for attr in dir(candidate) if not attr.startswith('_')]}")
      
      if hasattr(candidate, "content"):
        content = candidate.content
        logger.info(f"Content type: {type(content)}")
        logger.info(f"Content attributes: {[attr for attr in dir(content) if not attr.startswith('_')]}")
        
        if hasattr(content, "parts"):
          parts = content.parts
          logger.info(f"Number of parts: {len(parts) if parts else 0}")
          for i, part in enumerate(parts or []):
            logger.info(f"Part {i} type: {type(part)}")
            logger.info(f"Part {i} attributes: {[attr for attr in dir(part) if not attr.startswith('_')]}")
            if hasattr(part, "text") and part.text:
              logger.info(f"Part {i} text (first 200 chars): {part.text[:200]}")
    
    image_data = _extract_image_bytes(response)
    if image_data is None:
      logger.error(f"Failed to extract image bytes from response")
      # Try alternative extraction method
      logger.info("Attempting alternative extraction method...")
      image_data = _extract_image_bytes_alternative(response)
      
      if image_data is None:
        raise GeminiServiceError("Gemini did not return image data for segmentation")

    logger.info(f"Successfully extracted {len(image_data)} bytes of image data")
    return image_data

  def generate_enhanced_shot(self, prompt: str, segmented_image: Path) -> bytes:
    """Generate enhanced product shot using image editing."""
    if not segmented_image.exists():
      raise GeminiServiceError("Segmented image not found for enhancement")

    # Read segmented image
    image_bytes = segmented_image.read_bytes()
    
    # Create parts: image first, then enhancement prompt
    parts = [
      types.Part(
        inline_data=types.Blob(
          data=image_bytes,
          mime_type="image/png",
        )
      ),
      types.Part(text=prompt),
    ]

    # Retry up to 2 times on quota errors
    response = None
    last_error = None
    for attempt in range(3):
      try:
        logger.info(f"Calling Gemini for enhancement with model: {self.image_model} (attempt {attempt + 1})")
        response = self.client.models.generate_content(
          model=self.image_model,
          contents=types.Content(parts=parts),
        )
        logger.info(f"Enhancement response received")
        break  # Success, exit retry loop
      except Exception as error:
        last_error = error
        is_quota, retry_after = _is_quota_error(error)
        
        if is_quota and attempt < 2:
          delay = retry_after if retry_after else 20.0 * (attempt + 1)
          logger.warning(f"Gemini quota error on attempt {attempt + 1}/3, retrying after {delay:.1f}s: {error}")
          time.sleep(delay)
          continue
        else:
          # Not a quota error or max retries reached
          logger.error(f"Gemini image enhancement failed: {error}", exc_info=True)
          is_quota_final, retry_after_final = _is_quota_error(error)
          error_msg = f"Gemini image enhancement failed: {error}"
          raise GeminiServiceError(
            error_msg,
            original_error=error,
            is_quota_error=is_quota_final,
            retry_after=retry_after_final
          ) from error
    
    if response is None and last_error:
      is_quota_final, retry_after_final = _is_quota_error(last_error)
      raise GeminiServiceError(
        f"Gemini image enhancement failed after retries: {last_error}",
        original_error=last_error,
        is_quota_error=is_quota_final,
        retry_after=retry_after_final
      ) from last_error

    if not response:
      raise GeminiServiceError("Gemini returned empty response")

    image_data = _extract_image_bytes(response)
    if image_data is None:
      logger.error("Failed to extract image bytes from enhancement response")
      # Try alternative extraction
      logger.info("Attempting alternative extraction for enhancement...")
      image_data = _extract_image_bytes_alternative(response)
      
      if image_data is None:
        raise GeminiServiceError("Gemini did not return image data in response")

    logger.info(f"Successfully extracted {len(image_data)} bytes of enhanced image")
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
  """Extract image bytes from Gemini API response.
  
  Based on Gemini docs example:
  for part in response.candidates[0].content.parts:
      if part.inline_data is not None:
          image = Image.open(BytesIO(part.inline_data.data))
  """
  import logging
  logger = logging.getLogger(__name__)
  
  try:
    # Check candidates first (standard response format)
    if not hasattr(response, "candidates") or not response.candidates:
      logger.warning("No candidates in response")
      return None
    
    candidates = response.candidates
    logger.info(f"Checking {len(candidates)} candidates for image data")
    
    # Check first candidate's content parts (as per Gemini docs)
    candidate = candidates[0]
    if not hasattr(candidate, "content") or not candidate.content:
      logger.warning("No content in first candidate")
      return None
    
    content = candidate.content
    if not hasattr(content, "parts") or not content.parts:
      logger.warning("No parts in content")
      return None
    
    parts = content.parts
    logger.info(f"First candidate has {len(parts)} parts")
    
    # Iterate through parts as per Gemini docs example
    for part_idx, part in enumerate(parts):
      logger.info(f"Checking part {part_idx}, type: {type(part)}")
      
      # Check if part has inline_data (exactly as per Gemini docs)
      if hasattr(part, "inline_data"):
        inline_data = part.inline_data
        # Check if inline_data is not None (as per docs: "if part.inline_data is not None")
        if inline_data is not None:
          logger.info(f"Found inline_data in part {part_idx} (not None)")
          
          # Access data attribute
          if hasattr(inline_data, "data"):
            data = inline_data.data
            if data is not None:
              logger.info(f"Found data in inline_data, type: {type(data)}")
              
              if isinstance(data, bytes):
                logger.info(f"Returning bytes data, size: {len(data)}")
                return data
              elif isinstance(data, str):
                try:
                  # Try base64 decode if it's a string
                  decoded = base64.b64decode(data)
                  logger.info(f"Decoded base64 string, size: {len(decoded)}")
                  return decoded
                except Exception as e:
                  logger.warning(f"Failed to decode base64: {e}")
          else:
            logger.warning(f"inline_data in part {part_idx} has no 'data' attribute")
            logger.info(f"inline_data attributes: {dir(inline_data)}")
      
      # Check if part has text (for debugging - might return text instead of image)
      if hasattr(part, "text") and part.text is not None:
        logger.info(f"Part {part_idx} has text (not image): {part.text[:200]}...")

    logger.warning("No image data found in response parts")
    logger.warning(f"Response structure: candidates={len(candidates)}, parts={len(parts)}")
    return None
    
  except Exception as e:
    logger.error(f"Error extracting image bytes: {e}", exc_info=True)
    import traceback
    logger.error(traceback.format_exc())
    return None


def _extract_image_bytes_alternative(response: types.GenerateContentResponse) -> bytes | None:
  """Alternative extraction method - try direct attribute access."""
  import logging
  logger = logging.getLogger(__name__)
  
  try:
    # Try accessing directly as per Python SDK examples
    if hasattr(response, "candidates") and response.candidates:
      candidate = response.candidates[0]
      if hasattr(candidate, "content") and candidate.content:
        content = candidate.content
        if hasattr(content, "parts") and content.parts:
          for part in content.parts:
            # Try accessing inline_data directly
            if hasattr(part, "inline_data"):
              inline_data = part.inline_data
              if inline_data and hasattr(inline_data, "data"):
                data = inline_data.data
                if isinstance(data, bytes):
                  logger.info(f"Alternative method found bytes, size: {len(data)}")
                  return data
                elif isinstance(data, str):
                  try:
                    decoded = base64.b64decode(data)
                    logger.info(f"Alternative method decoded base64, size: {len(decoded)}")
                    return decoded
                  except Exception:
                    pass
            
            # Try accessing as dictionary-like if it supports it
            if isinstance(part, dict):
              if "inline_data" in part:
                inline_data = part["inline_data"]
                if "data" in inline_data:
                  data = inline_data["data"]
                  if isinstance(data, bytes):
                    return data
                  elif isinstance(data, str):
                    try:
                      return base64.b64decode(data)
                    except Exception:
                      pass
  except Exception as e:
    logger.error(f"Alternative extraction failed: {e}")
  
  return None

