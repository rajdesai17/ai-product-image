import type { ProcessVideoResponse } from "@/types";
import { resolveStaticUrl } from "@/lib/url";

type ResultsGalleryProps = {
  data: ProcessVideoResponse;
};

const ENHANCED_SHOT_LABELS = ["Studio", "Lifestyle", "Creative"];

export default function ResultsGallery({ data }: ResultsGalleryProps) {
  const {
    product_name,
    key_frame_url,
    segmented_image_url,
    enhanced_shots,
  } = data;

  const shots = Array.isArray(enhanced_shots) ? enhanced_shots : [];

  return (
    <div className="space-y-6">
      {product_name && (
        <header className="space-y-1">
          <p className="text-sm uppercase tracking-wide text-neutral-500">Product</p>
          <h2 className="text-2xl font-semibold text-neutral-900">{product_name}</h2>
        </header>
      )}

      {key_frame_url && (
        <section className="space-y-2">
          <h3 className="text-lg font-medium">Original Frame</h3>
          <figure className="overflow-hidden rounded-lg border border-neutral-200">
            <img
              src={resolveStaticUrl(key_frame_url)}
              alt="Extracted key frame"
              className="w-full"
              loading="lazy"
            />
          </figure>
        </section>
      )}

      {segmented_image_url && (
        <section className="space-y-2">
          <h3 className="text-lg font-medium">Segmented Product</h3>
          <figure className="flex items-center justify-center rounded-lg border border-neutral-200 bg-white p-6">
            <img
              src={resolveStaticUrl(segmented_image_url)}
              alt="Product with background removed"
              className="max-h-80 object-contain"
              loading="lazy"
            />
          </figure>
        </section>
      )}

      {shots.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-lg font-medium">Enhanced Shots</h3>
          <div className="grid gap-4 sm:grid-cols-2">
            {shots.map((shot, index) => {
              const label = ENHANCED_SHOT_LABELS[index] ?? `Shot ${index + 1}`;
              return (
                <figure
                  key={shot}
                  className="space-y-2 overflow-hidden rounded-lg border border-neutral-200 bg-white"
                >
                  <img
                    src={resolveStaticUrl(shot)}
                    alt={`${label} product shot`}
                    className="w-full"
                    loading="lazy"
                  />
                  <figcaption className="px-4 pb-4 text-sm font-medium text-neutral-700">
                    {label}
                  </figcaption>
                </figure>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}

