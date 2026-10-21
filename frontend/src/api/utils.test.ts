import { describe, expect, it } from "vitest";

import { errorMessage } from "./utils.ts";

function json(body: unknown, status = 422): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("errorMessage", () => {
  it("shows a string detail from the API as is", () => {
    return expect(errorMessage(json({ detail: "Links to this service can't be shortened." }))).resolves.toBe(
      "Links to this service can't be shortened.",
    );
  });

  it("turns a FastAPI validation list into a plain instruction", () => {
    return expect(errorMessage(json({ detail: [{ loc: ["body", "url"], msg: "bad" }] }))).resolves.toBe(
      "Enter a link that starts with http:// or https://.",
    );
  });

  it("falls back to a generic message when there is no detail", () => {
    return expect(errorMessage(json({ other: 1 }, 500))).resolves.toBe(
      "Something went wrong. Try again.",
    );
  });

  it("falls back when the body is not JSON, e.g. a proxy error page", () => {
    const res = new Response("<html>502 Bad Gateway</html>", { status: 502 });
    return expect(errorMessage(res)).resolves.toBe("Something went wrong. Try again.");
  });
});
