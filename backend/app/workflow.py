from __future__ import annotations

from pathlib import Path
from typing import List, TypedDict

from langgraph.graph import StateGraph, START, END

from .config import Settings
from .services.enhancement_prompts import PromptStyle, build_prompt
from .services.gemini import GeminiService, GeminiServiceError
from .services.video import download_and_sample_frames
from .utils.file_paths import JobPaths, ensure_job_paths, to_static_url


class WorkflowState(TypedDict, total=False):
  video_url: str
  job_id: str
  product_name: str
  sampled_frames: List[str]
  top_frames: List[str]  # Top 3 frames selected for product identification
  best_frame_path: str
  key_frame_url: str
  segmented_image_path: str
  segmented_image_url: str
  enhanced_shots: List[str]
  error: str | None


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
  builder.add_node("select_top_frames", _make_select_top_frames_node(gemini))
  builder.add_node("identify_product", _make_identify_product_node(gemini))
  builder.add_node("select_best_frame", _make_best_frame_node(gemini, job_paths))
  builder.add_node("segment_image", _make_segmentation_node(gemini, job_paths))
  builder.add_node("enhance_images", _make_enhancement_node(gemini, job_paths))

  # Define edges
  builder.add_edge(START, "extract_frames")
  builder.add_edge("extract_frames", "select_top_frames")
  builder.add_edge("select_top_frames", "identify_product")
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


def _make_select_top_frames_node(gemini: GeminiService):
  """Select top 3 frames from all extracted frames."""
  def node(state: WorkflowState) -> dict:
    all_frames = [Path(path) for path in state.get("sampled_frames", [])]
    if not all_frames:
      raise ValueError("No frames available for top frame selection")
    
    # Select top 3 frames using Gemini
    top_indices = gemini.select_top_frames(all_frames, top_n=3)
    top_frames = [str(all_frames[idx]) for idx in top_indices]
    
    return {"top_frames": top_frames}

  return node


def _make_identify_product_node(gemini: GeminiService):
  """Identify product from the top 3 frames."""
  def node(state: WorkflowState) -> dict:
    top_frames = [Path(path) for path in state.get("top_frames", [])]
    if not top_frames:
      raise ValueError("No top frames available for product identification")
    product_name = gemini.identify_product(top_frames)
    return {"product_name": product_name}

  return node


def _make_best_frame_node(gemini: GeminiService, job_paths: JobPaths):
  """Select the single best frame from the top 3 frames."""
  def node(state: WorkflowState) -> dict:
    top_frames = [Path(path) for path in state.get("top_frames", [])]
    if not top_frames:
      raise ValueError("No top frames available for best frame selection")
    
    # Select best frame from the top 3 frames
    index = gemini.select_best_frame(top_frames, state["product_name"])

    if index < 0 or index >= len(top_frames):
      raise ValueError(f"Gemini selected frame index {index} out of range (0-{len(top_frames)-1})")

    return {"best_frame_path": str(top_frames[index])}

  return node


def _make_segmentation_node(gemini: GeminiService, job_paths: JobPaths):
  """Use Gemini to segment/crop the product from the best frame."""
  def node(state: WorkflowState) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    
    best_frame_path = Path(state["best_frame_path"])
    if not best_frame_path.exists():
      raise ValueError(f"Best frame not found: {best_frame_path}")
    
    product_name = state.get("product_name", "product")
    logger.info(f"Segmenting product '{product_name}' from frame: {best_frame_path}")
    
    segmented_image_bytes = gemini.segment_product(best_frame_path, product_name)
    logger.info(f"Gemini segmentation successful, received {len(segmented_image_bytes)} bytes")
    
    # Save segmented image
    segmented_path = job_paths.segmented_image_path
    segmented_path.parent.mkdir(parents=True, exist_ok=True)
    with segmented_path.open("wb") as file:
      file.write(segmented_image_bytes)
    
    logger.info(f"Segmented image saved to: {segmented_path}")
    return {"segmented_image_path": str(segmented_path)}

  return node


def _make_enhancement_node(gemini: GeminiService, job_paths: JobPaths):
  """Generate 2-3 enhanced product shots using different styles."""
  def node(state: WorkflowState) -> dict:
    import logging
    logger = logging.getLogger(__name__)
    
    segmented_path = Path(state["segmented_image_path"])
    if not segmented_path.exists():
      raise ValueError(f"Segmented image not found: {segmented_path}")
    product_name = state.get("product_name", "product")
    logger.info(f"Enhancing product '{product_name}' from segmented image: {segmented_path}")

    # Generate 2-3 enhanced images (studio, lifestyle, creative)
    enhanced_paths: list[str] = []
    styles: tuple[PromptStyle, ...] = ("studio", "lifestyle", "creative")
    
    for style in styles:
      try:
        logger.info(f"Generating {style} enhanced shot...")
        prompt = build_prompt(style, product_name)
        image_bytes = gemini.generate_enhanced_shot(prompt, segmented_path)
        logger.info(f"{style} shot generated, received {len(image_bytes)} bytes")
        output_path = job_paths.enhancement_path(style)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as file:
          file.write(image_bytes)
        enhanced_paths.append(str(output_path))
        logger.info(f"{style} shot saved to: {output_path}")
      except GeminiServiceError as e:
        # If enhancement fails for a style, skip it but continue with others
        error_msg = str(e).lower()
        is_quota_error = (
          getattr(e, "is_quota_error", False) or
          "429" in error_msg or
          "quota" in error_msg or
          "resource_exhausted" in error_msg
        )
        if is_quota_error:
          logger.warning(f"Quota exceeded for {style} shot, skipping: {e}")
        else:
          logger.warning(f"Failed to generate {style} shot, skipping: {e}")
        continue
      except Exception as e:
        # If enhancement fails for a style, skip it but continue with others
        logger.warning(f"Failed to generate {style} shot, skipping: {e}")
        continue

    logger.info(f"Enhancement complete. Generated {len(enhanced_paths)} shots: {enhanced_paths}")
    # Return enhanced shots (should have at least 2-3)
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

