type ProcessingStatusProps = {
  message?: string;
};

export default function ProcessingStatus({
  message = "Processing video... please wait",
}: ProcessingStatusProps) {
  return (
    <p className="text-center text-sm text-gray-500" role="status" aria-live="polite">
      {message}
    </p>
  );
}

