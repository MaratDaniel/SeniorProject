import type { ApiErrorBody, SessionResult, User } from "./types";

/** An error answered by the API (or a network failure, code "network_error"). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** Field messages from a 422 validation_error, keyed by field name. */
  fieldErrors(): Record<string, string> {
    const fields = this.details.fields;
    if (!fields || typeof fields !== "object") return {};
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(fields as Record<string, unknown>)) {
      if (typeof value === "string") out[key] = value;
    }
    return out;
  }

  detail(key: string): string | null {
    const value = this.details[key];
    return typeof value === "string" ? value : null;
  }
}

export function isApiError(e: unknown, code?: string): e is ApiError {
  return e instanceof ApiError && (code === undefined || e.code === code);
}

// ---------------------------------------------------------------------------
// Session: the access token lives in memory only. The refresh token is an
// httpOnly cookie the browser sends to /api/auth/* by itself.

type Session = { token: string | null; user: User | null };
type SessionListener = (session: Session) => void;

let accessToken: string | null = null;
const listeners = new Set<SessionListener>();

export function setSession(token: string | null, user: User | null): void {
  accessToken = token;
  for (const listener of listeners) listener({ token, user });
}

export function onSessionChange(listener: SessionListener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function hasAccessToken(): boolean {
  return accessToken !== null;
}

let refreshing: Promise<boolean> | null = null;

/**
 * Exchanges the refresh cookie for a new access token. Concurrent callers share one
 * request, because the server rotates the refresh token on every use.
 */
export function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
        });
        if (!res.ok) {
          setSession(null, null);
          return false;
        }
        const body = (await res.json()) as SessionResult;
        setSession(body.access_token, body.user);
        return true;
      } catch {
        return false;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

// ---------------------------------------------------------------------------
// Server clock. Countdowns use server time; the auction page sets a precise
// offset from `server_time`, other pages fall back to the HTTP Date header.

let serverOffsetMs = 0;
let haveExactOffset = false;

export function noteServerTime(iso: string, exact: boolean): void {
  const server = Date.parse(iso);
  if (Number.isNaN(server)) return;
  if (exact) {
    serverOffsetMs = server - Date.now();
    haveExactOffset = true;
  } else if (!haveExactOffset) {
    serverOffsetMs = server - Date.now();
  }
}

export function serverNow(): number {
  return Date.now() + serverOffsetMs;
}

// ---------------------------------------------------------------------------

type RequestOptions = {
  method?: string;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Send the bearer token when we have one. Default true. */
  auth?: boolean;
  /** Internal: whether a 401 may trigger one refresh and retry. */
  retry?: boolean;
};

const fallbackMessages: Record<number, string> = {
  400: "The request was not accepted.",
  401: "Please sign in to continue.",
  403: "You do not have access to this.",
  404: "We could not find that.",
  409: "That is no longer possible.",
  413: "That file is too large.",
  422: "Some fields need attention.",
  423: "This account is locked for now.",
  429: "Too many attempts. Wait a moment and try again.",
};

async function readError(res: Response): Promise<ApiError> {
  let code = `http_${res.status}`;
  let message = fallbackMessages[res.status] ?? "Something went wrong on our side. Try again in a moment.";
  let details: Record<string, unknown> = {};
  try {
    const body = (await res.json()) as Partial<ApiErrorBody>;
    if (body && body.error) {
      code = body.error.code || code;
      message = body.error.message || message;
      details = body.error.details ?? {};
    }
  } catch {
    // not JSON; keep the fallback message
  }
  return new ApiError(res.status, code, message, details);
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  if (accessToken && opts.auth !== false) headers.Authorization = `Bearer ${accessToken}`;

  let res: Response;
  try {
    res = await fetch(path, {
      method: opts.method ?? (body !== undefined ? "POST" : "GET"),
      headers,
      body,
      credentials: "same-origin",
      signal: opts.signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "network_error", "We could not reach the server. Check your connection and try again.");
  }

  const date = res.headers.get("Date");
  if (date) noteServerTime(new Date(date).toISOString(), false);

  if (res.status === 401 && opts.retry !== false && accessToken && opts.auth !== false) {
    const err = await readError(res);
    if (err.code === "token_expired" || err.code === "not_authenticated") {
      if (await refreshSession()) return api<T>(path, { ...opts, retry: false });
    }
    throw err;
  }
  if (!res.ok) throw await readError(res);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** Photo upload with progress (fetch has no upload progress). */
export function uploadImage(
  file: File,
  onProgress: (percent: number) => void,
  retry = true,
): Promise<{ id: number; url: string }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/uploads/images");
    xhr.setRequestHeader("Accept", "application/json");
    if (accessToken) xhr.setRequestHeader("Authorization", `Bearer ${accessToken}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () =>
      reject(new ApiError(0, "network_error", "The upload did not reach the server. Check your connection and try again."));
    xhr.onload = () => {
      let parsed: unknown = null;
      try {
        parsed = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        parsed = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(parsed as { id: number; url: string });
        return;
      }
      const body = parsed as Partial<ApiErrorBody> | null;
      const err = new ApiError(
        xhr.status,
        body?.error?.code ?? `http_${xhr.status}`,
        body?.error?.message ?? fallbackMessages[xhr.status] ?? "The upload failed.",
        body?.error?.details ?? {},
      );
      if (xhr.status === 401 && retry && (err.code === "token_expired" || err.code === "not_authenticated")) {
        refreshSession().then((ok) => {
          if (ok) uploadImage(file, onProgress, false).then(resolve, reject);
          else reject(err);
        });
        return;
      }
      reject(err);
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** Only relative in-app paths are allowed as a post-sign-in destination. */
export function safeNext(raw: string | null | undefined, fallback = "/"): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return fallback;
  return raw;
}
