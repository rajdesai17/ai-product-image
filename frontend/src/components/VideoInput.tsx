"use client";

import { useState } from "react";

type VideoInputProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  disabled?: boolean;
};

export default function VideoInput({
  value,
  onChange,
  onSubmit,
  disabled = false,
}: VideoInputProps) {
  const [localError, setLocalError] = useState<string | null>(null);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextValue = event.target.value;
    if (localError) {
      setLocalError(null);
    }
    onChange(nextValue);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const url = value.trim();

    if (!isYouTubeUrl(url)) {
      setLocalError("Please enter a valid YouTube URL.");
      return;
    }

    setLocalError(null);
    onSubmit(url);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-2">
      <div className="space-y-1">
        <label htmlFor="youtube-url" className="text-sm font-medium text-neutral-700">
          YouTube URL
        </label>
        <input
          id="youtube-url"
          type="url"
          inputMode="url"
          placeholder="https://www.youtube.com/watch?v=..."
          className="border border-neutral-300 p-2 rounded w-full focus:outline-none focus:ring-2 focus:ring-neutral-900 disabled:cursor-not-allowed disabled:opacity-70"
          value={value}
          onChange={handleChange}
          disabled={disabled}
        />
        {localError && (
          <p className="text-sm text-red-600" role="alert">
            {localError}
          </p>
        )}
      </div>
      <button
        type="submit"
        className="px-4 py-2 bg-black text-white rounded w-full disabled:cursor-not-allowed disabled:opacity-70"
        disabled={disabled}
      >
        Generate Product Images
      </button>
    </form>
  );
}

function isYouTubeUrl(value: string): boolean {
  if (value.length === 0) {
    return false;
  }

  try {
    const url = new URL(value);
    const hostname = url.hostname.toLowerCase();
    return hostname.includes("youtube.com") || hostname.includes("youtu.be");
  } catch (error) {
    return false;
  }
}

