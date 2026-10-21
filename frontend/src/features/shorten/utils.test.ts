import { describe, expect, it } from "vitest";

import { checkUrl, isValidUrl, MAX_URL_LENGTH, normalizeUrl, printedAt } from "./utils.ts";

describe("normalizeUrl", () => {
  it("adds https:// to a bare address", () => {
    expect(normalizeUrl("example.com/page")).toBe("https://example.com/page");
  });

  it("leaves links that already have a scheme alone", () => {
    expect(normalizeUrl("http://example.com")).toBe("http://example.com");
    expect(normalizeUrl("https://example.com/a?b=1")).toBe("https://example.com/a?b=1");
  });

  it("adds https:// when the only :// is inside the query or fragment", () => {
    expect(normalizeUrl("google.com/url?q=https://example.com")).toBe(
      "https://google.com/url?q=https://example.com",
    );
    expect(normalizeUrl("example.com/#a://b")).toBe("https://example.com/#a://b");
  });

  it("leaves any scheme:// prefix alone, whatever the case", () => {
    expect(normalizeUrl("HTTPS://Example.com")).toBe("HTTPS://Example.com");
    expect(normalizeUrl("ftp://example.com/file")).toBe("ftp://example.com/file");
  });

  it("trims surrounding whitespace", () => {
    expect(normalizeUrl("  example.com  ")).toBe("https://example.com");
  });

  it("returns an empty string for empty or blank input", () => {
    expect(normalizeUrl("")).toBe("");
    expect(normalizeUrl("   ")).toBe("");
  });
});

describe("isValidUrl", () => {
  it.each([
    "example.com",
    "example.com/page?x=1&y=2",
    "google.com/url?q=https://example.com",
    "example.com/redirect?next=http://other.com/x",
    "example.com/#a://b",
    "  example.com  ",
    "https://example.com/a/b",
    "http://sub.domain.example.co.uk/path#frag",
    "localhost:3000/app",
    "http://localhost:3000/app",
    "http://192.168.0.1/x",
    "http://[::1]:8000/x",
    "https://bücher.de/x",
  ])("accepts %j", (input) => {
    expect(isValidUrl(input)).toBe(true);
  });

  it.each([
    ["empty", ""],
    ["whitespace only", "   "],
    ["a bare word", "hello"],
    ["a word with a space", "hello world"],
    ["a trailing dot", "example."],
    ["a one-letter top-level domain", "example.c"],
    ["an empty label", "a..com"],
    ["a label starting with a hyphen", "-bad.com"],
    ["an ftp link", "ftp://example.com/file"],
    ["a javascript: link", "javascript:alert(1)"],
    ["a mailto: address", "mailto:a@b.com"],
    ["a scheme with no host", "https://"],
    ["a space inside the host", "https://exa mple.com"],
    ["credentials in the link", "https://user:pass@example.com/x"],
  ])("rejects %s", (_name, input) => {
    expect(isValidUrl(input)).toBe(false);
  });
});

describe("printedAt", () => {
  it("formats an ISO timestamp as readable text", () => {
    const text = printedAt("2026-10-21T14:41:00Z");
    expect(text).not.toBe("Invalid Date");
    expect(text).toMatch(/\d/);
  });

  it("reports an invalid timestamp rather than throwing", () => {
    expect(printedAt("not a date")).toBe("Invalid Date");
  });
});

describe("checkUrl", () => {
  it("says why a link is not usable", () => {
    expect(checkUrl("")).toBe("empty");
    expect(checkUrl("   ")).toBe("empty");
    expect(checkUrl("hello")).toBe("invalid");
    expect(checkUrl("ftp://example.com/x")).toBe("invalid");
    expect(checkUrl("https://user:pw@example.com")).toBe("invalid");
    expect(checkUrl("example.com/page")).toBe("valid");
  });

  it("accepts a link of exactly the API limit and rejects one character more", () => {
    const base = "https://example.com/";
    const atLimit = base + "a".repeat(MAX_URL_LENGTH - base.length);
    expect(atLimit).toHaveLength(MAX_URL_LENGTH);
    expect(checkUrl(atLimit)).toBe("valid");
    expect(checkUrl(atLimit + "a")).toBe("too-long");
  });

  it("counts the https:// that normalizing adds", () => {
    // 2083 characters as typed, so 2091 once https:// is added: over the limit.
    const bare = "example.com/" + "a".repeat(MAX_URL_LENGTH - "example.com/".length);
    expect(bare).toHaveLength(MAX_URL_LENGTH);
    expect(checkUrl(bare)).toBe("too-long");
  });

  it("agrees with isValidUrl", () => {
    for (const input of ["example.com", "hello", "", "https://" + "a".repeat(2100) + ".com"]) {
      expect(isValidUrl(input)).toBe(checkUrl(input) === "valid");
    }
  });
});
