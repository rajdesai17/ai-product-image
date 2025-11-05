const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";

export function resolveStaticUrl(path: string): string {
  if (!path || typeof path !== "string") {
    return path;
  }

  if (isAbsolutePath(path) || path.startsWith("data:")) {
    return path;
  }

  if (!path.startsWith("/")) {
    return path;
  }

  if (!API_BASE_URL) {
    return path;
  }

  return `${API_BASE_URL}${path}`;
}

function isAbsolutePath(path: string): boolean {
  try {
    const url = new URL(path);
    return Boolean(url.protocol && url.host);
  } catch (error) {
    return false;
  }
}

