/** Adds https:// when the user pastes a bare address like "example.com/page". */
export function normalizeUrl(input: string): string {
  const value = input.trim();
  if (value === "" || value.includes("://")) return value;
  return `https://${value}`;
}

// A real hostname: localhost, an IPv4 address, a bracketed IPv6 address, or a
// dotted domain whose last label is at least two characters ("example.com").
const HOSTNAME =
  /^(localhost|\d{1,3}(\.\d{1,3}){3}|\[[0-9a-f:.]+\]|([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z0-9-]{2,})$/i;

/** True when the input would make a usable http(s) link once normalized. */
export function isValidUrl(input: string): boolean {
  let url: URL;
  try {
    url = new URL(normalizeUrl(input));
  } catch {
    return false;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return false;
  // "mailto:a@b.com" would otherwise parse as https://mailto:a@b.com (user:pass@host).
  if (url.username !== "" || url.password !== "") return false;
  return HOSTNAME.test(url.hostname);
}

export function printedAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
