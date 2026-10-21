import { errorMessage, GENERIC_ERROR_MESSAGE } from "./utils.ts";

const REQUEST_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  readonly status: number;
  /** The server's X-Request-ID, so a failure can be matched to its log line. */
  readonly requestId: string | undefined;

  constructor(status: number, message: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError(0, "The server took too long to respond. Try again.");
    }
    throw new ApiError(0, "Can't reach the server. Check that the API is running.");
  }
  const requestId = res.headers.get("X-Request-ID") ?? undefined;
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res), requestId);

  try {
    return (await res.json()) as T;
  } catch {
    // A 2xx that is not JSON means something between us and the API answered instead,
    // e.g. a proxy or CDN returning the web app's index.html for /api. Show the
    // generic message, never the parser's "Unexpected token '<'".
    throw new ApiError(res.status, GENERIC_ERROR_MESSAGE, requestId);
  }
}
