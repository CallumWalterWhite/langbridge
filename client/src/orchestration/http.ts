export class ApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, options: { status: number; details?: unknown }) {
    super(message);
    this.name = 'ApiError';
    this.status = options.status;
    this.details = options.details;
  }
}

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? '';

function resolveUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  if (!API_BASE) {
    return path;
  }
  return `${API_BASE}${path}`;
}

export type ApiRequestOptions = RequestInit & {
  skipJsonParse?: boolean;
};

export async function apiFetch<T = unknown>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { headers, skipJsonParse, ...init } = options;
  const response = await fetch(resolveUrl(path), {
    credentials: 'include',
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(headers ?? {}),
    },
  });

  if (skipJsonParse) {
    if (!response.ok) {
      throw new ApiError(response.statusText || 'Request failed', {
        status: response.status,
      });
    }
    return undefined as T;
  }

  let payload: unknown = null;
  const contentType = response.headers.get('content-type');

  try {
    if (contentType && contentType.includes('application/json')) {
      payload = await response.json();
    } else {
      const text = await response.text();
      payload = text ? text : null;
    }
  } catch (error) {
    if (response.ok) {
      throw error;
    }
  }

  if (!response.ok) {
    const message =
      typeof payload === 'object' && payload && 'detail' in payload
        ? String((payload as Record<string, unknown>).detail)
        : typeof payload === 'string' && payload
          ? payload
          : response.statusText || 'Request failed';
    throw new ApiError(message, { status: response.status, details: payload });
  }

  return payload as T;
}
