/** Adds https:// when the user pastes a bare address like "example.com/page". */
export function normalizeUrl(input: string): string {
  const value = input.trim();
  if (value === "" || value.includes("://")) return value;
  return `https://${value}`;
}

export function printedAt(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
