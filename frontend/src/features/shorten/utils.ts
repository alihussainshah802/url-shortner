// "scheme://" at the very start. Checking only the start matters: a bare address
// can contain "://" later on, e.g. google.com/url?q=https://example.com.
const SCHEME_PREFIX = /^[a-z][a-z0-9+.-]*:\/\//i;

/** Adds https:// when the user pastes a bare address like "example.com/page". */
export function normalizeUrl(input: string): string {
  const value = input.trim();
  if (value === "" || SCHEME_PREFIX.test(value)) return value;
  return `https://${value}`;
}

// A real hostname: localhost, an IPv4 address, a bracketed IPv6 address, or a
// dotted domain whose last label is at least two characters ("example.com").
const HOSTNAME =
  /^(localhost|\d{1,3}(\.\d{1,3}){3}|\[[0-9a-f:.]+\]|([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z0-9-]{2,})$/i;

/** The longest link the API accepts (pydantic's HttpUrl limit), counted after normalizing. */
export const MAX_URL_LENGTH = 2083;

export type UrlCheck = "empty" | "valid" | "invalid" | "too-long";

/** Says whether the input would make a usable http(s) link once normalized, and if not, why. */
export function checkUrl(input: string): UrlCheck {
  const normalized = normalizeUrl(input);
  if (normalized === "") return "empty";
  if (normalized.length > MAX_URL_LENGTH) return "too-long";

  let url: URL;
  try {
    url = new URL(normalized);
  } catch {
    return "invalid";
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return "invalid";
  // "mailto:a@b.com" would otherwise parse as https://mailto:a@b.com (user:pass@host).
  if (url.username !== "" || url.password !== "") return "invalid";
  return HOSTNAME.test(url.hostname) ? "valid" : "invalid";
}

/** True when the input would make a usable http(s) link once normalized. */
export function isValidUrl(input: string): boolean {
  return checkUrl(input) === "valid";
}

export function printedAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
