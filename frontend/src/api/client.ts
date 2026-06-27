import type { HealthResponse } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, { signal });

  if (!response.ok) {
    throw new Error(`API health check failed with status ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
}
