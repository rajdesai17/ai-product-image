export interface ProcessVideoRequest {
  video_url: string;
}

export interface ProcessVideoResponse {
  status: "success" | "error";
  job_id: string;
  product_name?: string;
  key_frame_url?: string;
  segmented_image_url?: string;
  enhanced_shots?: string[];
  processing_time_seconds?: number;
  message?: string;
}

