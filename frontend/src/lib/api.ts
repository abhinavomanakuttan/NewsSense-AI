const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getStoredToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err: any) {
    const isNetworkError =
      err?.name === "TypeError" || err?.message?.includes("fetch");
    const message = isNetworkError
      ? "Unable to connect to server. Please verify the backend is running at " + API_BASE
      : err?.message || "Network request failed";
    throw new ApiError(0, message);
  }

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  }

  if (!res.ok) {
    const error = (await res.json().catch(() => ({
      detail: `Request failed (${res.status})`,
    }))) as { detail?: any; message?: string };

    let detail: string;
    if (typeof error.detail === "string") {
      detail = error.detail;
    } else if (Array.isArray(error.detail)) {
      detail = error.detail
        .map((item: any) => item?.msg || item?.message || JSON.stringify(item))
        .join(", ");
    } else if (error.detail && typeof error.detail === "object") {
      detail = JSON.stringify(error.detail);
    } else if (typeof error.message === "string") {
      detail = error.message;
    } else {
      detail = `Request failed (${res.status})`;
    }

    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(endpoint: string) => fetchApi<T>(endpoint),
  post: <T>(endpoint: string, data?: unknown) =>
    fetchApi<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    }),
  put: <T>(endpoint: string, data?: unknown) =>
    fetchApi<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    }),
  delete: <T>(endpoint: string) => fetchApi<T>(endpoint, { method: "DELETE" }),
};
