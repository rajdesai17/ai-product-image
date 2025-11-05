"use client";

import { useState } from "react";
import VideoInput from "@/components/VideoInput";
import ProcessingStatus from "@/components/ProcessingStatus";
import ResultsGallery from "@/components/ResultsGallery";
import { processVideo } from "@/lib/api";
import type { ProcessVideoResponse } from "@/types";

const DEFAULT_ERROR_MESSAGE = "Unable to process video. Please try again.";

export default function Page() {
  const [inputUrl, setInputUrl] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done">("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProcessVideoResponse | null>(null);

  const handleSubmit = async (url: string) => {
    setStatus("loading");
    setError(null);
    setResult(null);

    try {
      const response = await processVideo(url);

      if (response.status === "error") {
        throw new Error(response.message ?? DEFAULT_ERROR_MESSAGE);
      }

      setResult(response);
      setStatus("done");
    } catch (error) {
      const message =
        error instanceof Error && error.message.trim().length > 0
          ? error.message
          : DEFAULT_ERROR_MESSAGE;
      setError(message);
      setStatus("idle");
    }
  };

  const handleReset = () => {
    setInputUrl("");
    setResult(null);
    setError(null);
    setStatus("idle");
  };

  return (
    <main className="min-h-screen px-4 py-12">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8">
        <header className="space-y-2 text-center">
          <h1 className="text-3xl font-semibold text-neutral-900">AI Product Extractor</h1>
          <p className="text-sm text-neutral-600">
            Paste a YouTube product video to automatically extract the hero frame, remove the background, and generate studio-quality shots.
          </p>
        </header>

        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
        </div>
        )}

        {(status === "idle" || status === "loading") && (
          <VideoInput
            value={inputUrl}
            onChange={setInputUrl}
            onSubmit={handleSubmit}
            disabled={status === "loading"}
          />
        )}

        {status === "loading" && (
          <ProcessingStatus message="Processing video... This may take 30-60 seconds." />
        )}

        {status === "done" && result?.status === "success" && (
          <section className="space-y-6">
            <ResultsGallery data={result} />
            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleReset}
                className="w-full rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-900"
              >
                Try another URL
              </button>
            </div>
          </section>
        )}

        {status === "done" && result?.status !== "success" && (
          <div className="flex justify-center">
            <button
              type="button"
              onClick={handleReset}
              className="rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-700 transition hover:border-neutral-400 hover:text-neutral-900"
          >
              Try another URL
            </button>
          </div>
        )}
        </div>
      </main>
  );
}
