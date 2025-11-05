from __future__ import annotations

from pathlib import Path
from typing import List, TypedDict

from langgraph.graph import StateGraph, START, END

from .config import Settings
from .services.enhancement_prompts import PromptStyle, build_prompt
from .services.gemini import GeminiService
from .services.segmentation import segment_product
from .services.video import download_and_sample_frames
from .utils.file_paths import JobPaths, ensure_job_paths, to_static_url


class WorkflowState(TypedDict, total=False):
  video_url: str
  job_id: str
  product_name: str
  sampled_frames: List[str]
  best_frame_path: str
  key_frame_url: str
  segmented_image_path: str
  segmented_image_url: str
  enhanced_shots: List[str]
  error: str | None


ENHANCEMENT_STYLES: tuple[PromptStyle, ...] = ("studio", "lifestyle", "creative")


def run_workflow(
  *,
  video_url: str,
  job_id: str,
  settings: Settings,
  gemini: GeminiService,
) -> WorkflowState:
  """Run the workflow using LangGraph StateGraph."""
  job_paths = ensure_job_paths(settings.static_dir, job_id)

  # Create the graph
  builder = StateGraph(WorkflowState)

  # Add nodes
  builder.add_node("extract_frames", _make_extract_frames_node(settings, job_paths))
  builder.add_node("identify_product", _make_identify_product_node(gemini))
  builder.add_node("select_best_frame", _make_best_frame_node(gemini, job_paths))
  builder.add_node("segment_image", _make_segmentation_node(job_paths))
  builder.add_node("enhance_images", _make_enhancement_node(gemini, job_paths))

  # Define edges
  builder.add_edge(START, "extract_frames")
  builder.add_edge("extract_frames", "identify_product")
  builder.add_edge("identify_product", "select_best_frame")
  builder.add_edge("select_best_frame", "segment_image")
  builder.add_edge("segment_image", "enhance_images")
  builder.add_edge("enhance_images", END)

  # Compile the graph
  graph = builder.compile()

  # Initial state
  initial_state: WorkflowState = {
    "video_url": video_url,
    "job_id": job_id,
  }

  # Invoke the graph
  final_state = graph.invoke(initial_state)

  return final_state


def _make_extract_frames_node(settings: Settings, job_paths: JobPaths):
  def node(state: WorkflowState) -> dict:
    frames = download_and_sample_frames(
      video_url=state["video_url"],
      target_dir=job_paths.frames_dir,
      frame_sample_rate=settings.frame_sample_rate,
      max_video_duration=settings.max_video_duration,
    )
    return {"sampled_frames": [str(path) for path in frames]}

  return node


def _make_identify_product_node(gemini: GeminiService):
  def node(state: WorkflowState) -> dict:
    frames = [Path(path) for path in state.get("sampled_frames", [])][:10]
    if not frames:
      raise ValueError("No frames available for product identification")
    product_name = gemini.identify_product(frames)
    return {"product_name": product_name}

  return node


def _make_best_frame_node(gemini: GeminiService, job_paths: JobPaths):
  def node(state: WorkflowState) -> dict:
    frames = [Path(path) for path in state.get("sampled_frames", [])]
    if not frames:
      raise ValueError("No frames available for best frame selection")
    index = gemini.select_best_frame(frames, state["product_name"])

    if index < 0 or index >= len(frames):
      raise ValueError(f"Gemini selected frame index {index} out of range (0-{len(frames)-1})")

    return {"best_frame_path": str(frames[index])}

  return node


def _make_segmentation_node(job_paths: JobPaths):
  def node(state: WorkflowState) -> dict:
    best_frame_path = Path(state["best_frame_path"])
    if not best_frame_path.exists():
      raise ValueError(f"Best frame not found: {best_frame_path}")
    segmented_path = segment_product(best_frame_path, job_paths.segmented_image_path)
    return {"segmented_image_path": str(segmented_path)}

  return node


def _make_enhancement_node(gemini: GeminiService, job_paths: JobPaths):
  """Enhancement node - optional for MVP. Falls back gracefully if quota exceeded."""
  def node(state: WorkflowState) -> dict:
    segmented_path = Path(state["segmented_image_path"])
    if not segmented_path.exists():
      raise ValueError(f"Segmented image not found: {segmented_path}")
    product_name = state.get("product_name", "product")

    enhanced_paths: list[str] = []
    
    # Try to generate enhanced shots, but gracefully handle failures
    for style in ENHANCEMENT_STYLES:
      try:
        prompt = build_prompt(style, product_name)
        image_bytes = gemini.generate_enhanced_shot(prompt, segmented_path)
        output_path = job_paths.enhancement_path(style)
        with output_path.open("wb") as file:
          file.write(image_bytes)
        enhanced_paths.append(str(output_path))
      except Exception as e:
        # If enhancement fails (e.g., quota), skip this style
        # MVP: Continue with other styles or return empty list
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "resource_exhausted" in error_msg:
          # Quota exceeded - skip enhancement for MVP
          continue
        # For other errors, also skip (MVP: fail gracefully)
        continue

    # MVP: If no enhanced shots, return empty list (frontend will handle gracefully)
    return {"enhanced_shots": enhanced_paths}

  return node


def convert_paths_to_urls(state: WorkflowState, static_dir: Path) -> WorkflowState:
  transformed = WorkflowState(**state)

  if state.get("best_frame_path"):
    transformed["key_frame_url"] = to_static_url(static_dir, Path(state["best_frame_path"]))

  if state.get("segmented_image_path"):
    transformed["segmented_image_url"] = to_static_url(static_dir, Path(state["segmented_image_path"]))

  enhanced_shots = state.get("enhanced_shots", [])
  if enhanced_shots:
    transformed["enhanced_shots"] = [
      to_static_url(static_dir, Path(path)) for path in enhanced_shots
    ]

  return transformed

