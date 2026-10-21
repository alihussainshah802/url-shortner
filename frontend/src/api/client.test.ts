import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, postJson } from "./client.ts";

function respond(body: unknown, status: number, headers: Record<string, string> = {}): Response {
  const payload = typeof body === "string" ? body : JSON.stringify(body);
  return new Response(payload, { status, headers });
}

function stubFetch(result: Response | Error) {
  const fetchMock = vi.fn(() => (result instanceof Error ? Promise.reject(result) : Promise.resolve(result)));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function failure(): Promise<ApiError> {
  try {
    await postJson("/api/links", { url: "https://example.com" });
  } catch (error) {
    if (error instanceof ApiError) return error;
    throw error;
  }
  throw new Error("expected postJson to fail");
}

afterEach(() => vi.unstubAllGlobals());

describe("postJson", () => {
  it("sends JSON and returns the parsed body", async () => {
    const fetchMock = stubFetch(respond({ code: "abc1234" }, 201));
    await expect(postJson("/api/links", { url: "https://example.com" })).resolves.toEqual({
      code: "abc1234",
    });

    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/api/links");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ url: "https://example.com" }));
    expect(init.signal).toBeInstanceOf(AbortSignal); // every request has a timeout
  });

  it("reports an unreachable server", async () => {
    stubFetch(new TypeError("Failed to fetch"));
    const error = await failure();
    expect(error.status).toBe(0);
    expect(error.message).toBe("Can't reach the server. Check that the API is running.");
  });

  it("reports a timeout differently from an unreachable server", async () => {
    stubFetch(new DOMException("The operation timed out.", "TimeoutError"));
    const error = await failure();
    expect(error.status).toBe(0);
    expect(error.message).toBe("The server took too long to respond. Try again.");
  });

  it("turns a validation error into a plain message", async () => {
    stubFetch(respond({ detail: [{ type: "url_too_long" }] }, 422));
    const error = await failure();
    expect(error.status).toBe(422);
    expect(error.message).toBe("That link is too long. Links can be up to 2,083 characters.");
  });

  it("carries the request id of a server error so it can be matched to a log line", async () => {
    stubFetch(
      respond({ detail: "Something went wrong on our side. Try again." }, 500, {
        "X-Request-ID": "abc123",
      }),
    );
    const error = await failure();
    expect(error.status).toBe(500);
    expect(error.requestId).toBe("abc123");
  });

  it("falls back to a generic message for a proxy error page", async () => {
    stubFetch(respond("<html>502 Bad Gateway</html>", 502));
    const error = await failure();
    expect(error.message).toBe("Something went wrong. Try again.");
    expect(error.requestId).toBeUndefined();
  });

  it("never shows a JSON parser error when a 200 is not JSON (a proxy answering instead of the API)", async () => {
    stubFetch(respond("<!doctype html><html>the web app</html>", 200, { "X-Request-ID": "r1" }));
    const error = await failure();
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Something went wrong. Try again.");
    expect(error.message).not.toMatch(/Unexpected token|JSON/i);
    expect(error.status).toBe(200);
    expect(error.requestId).toBe("r1");
  });

  it("treats an empty 200 body the same way", async () => {
    stubFetch(respond("", 200));
    expect((await failure()).message).toBe("Something went wrong. Try again.");
  });
});
