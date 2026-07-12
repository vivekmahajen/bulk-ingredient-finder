/**
 * Tiny typed fetch wrapper for the Rasoi Radar API.
 *
 * Every call returns a discriminated result so callers handle RFC-7807
 * `problem+json` errors explicitly rather than throwing. Auth cookies (PR-1) ride
 * along via `credentials: "include"`.
 */

export interface Problem {
  type: string;
  title: string;
  status: number;
  detail?: string;
  instance?: string;
  [key: string]: unknown;
}

export type ApiResult<T> = { ok: true; data: T } | { ok: false; status: number; problem: Problem };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const MUTATING = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/** Read the non-httpOnly CSRF cookie so we can echo it in the header. */
function csrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)rr_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function doFetch(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (MUTATING.has(method)) {
    const csrf = csrfToken();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }
  return fetch(`${API_URL}${path}`, {
    method,
    credentials: "include",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
}

async function request<T>(method: string, path: string, body?: unknown): Promise<ApiResult<T>> {
  try {
    let resp = await doFetch(method, path, body);

    // Transparently refresh an expired access token once, then retry.
    if (resp.status === 401 && !path.startsWith("/api/v1/auth/")) {
      const refreshed = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      });
      if (refreshed.ok) resp = await doFetch(method, path, body);
    }

    if (resp.status === 204) {
      return { ok: true, data: undefined as T };
    }

    const payload = (await resp.json().catch(() => ({}))) as unknown;

    if (!resp.ok) {
      const problem = (payload ?? {}) as Partial<Problem>;
      return {
        ok: false,
        status: resp.status,
        problem: {
          ...problem,
          type: problem.type ?? "about:blank",
          title: problem.title ?? "Request failed",
          status: resp.status,
          detail: problem.detail,
        },
      };
    }

    return { ok: true, data: payload as T };
  } catch (err) {
    return {
      ok: false,
      status: 0,
      problem: {
        type: "about:blank",
        title: "Network error",
        status: 0,
        detail: err instanceof Error ? err.message : "Could not reach the API.",
      },
    };
  }
}

export const apiGet = <T>(path: string) => request<T>("GET", path);
export const apiPost = <T>(path: string, body: unknown) => request<T>("POST", path, body);
export const apiPatch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
export const apiDelete = <T>(path: string) => request<T>("DELETE", path);
