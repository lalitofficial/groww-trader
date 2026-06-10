const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

export async function adminFetch<T = any>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${backendUrl}${path}`, { ...init, cache: "no-store" });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || data.error || `${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function safeAdminFetch<T = any>(path: string, fallback: T): Promise<T> {
  try {
    return await adminFetch<T>(path);
  } catch {
    return fallback;
  }
}

export function adminStreamUrl() {
  return `${backendUrl}/api/admin/stream`;
}

export function adminExportUrl(table: string) {
  return `${backendUrl}/api/admin/exports/${encodeURIComponent(table)}.csv`;
}
