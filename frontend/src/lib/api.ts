import type { ProcessVideoResponse } from "@/types";

const DEFAULT_ERROR_MESSAGE = "Failed to process video. Please try again.";

export async function processVideo(video_url: string): Promise<ProcessVideoResponse> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/process-video`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_url })
  });

  let payload: unknown;

  try {
    payload = await res.json();
  } catch (error) {
    // Ignore JSON parse errors; will handle below based on status
  }

  if (!res.ok) {
    const message = extractErrorMessage(payload) ?? DEFAULT_ERROR_MESSAGE;
    throw new Error(message);
  }

  if (!isProcessVideoResponse(payload)) {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }

  return payload;
}

function extractErrorMessage(payload: unknown): string | null {
  if (typeof payload === "object" && payload !== null && "message" in payload) {
    const message = (payload as Record<string, unknown>).message;
    if (typeof message === "string" && message.trim().length > 0) {
      return message;
    }
  }

  return null;
}

function isProcessVideoResponse(payload: unknown): payload is ProcessVideoResponse {
  if (!payload || typeof payload !== "object") {
    return false;
  }

  const obj = payload as Record<string, unknown>;
  return typeof obj.status === "string" && typeof obj.job_id === "string";
}

