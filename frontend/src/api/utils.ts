/** Turns a failed API response into a message that is safe to show the user. */
export async function errorMessage(res: Response): Promise<string> {
  const data: unknown = await res.json().catch(() => null);
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    // FastAPI's validation errors arrive as a list; the only field is the URL.
    if (Array.isArray(detail)) return "Enter a link that starts with http:// or https://.";
  }
  return "Something went wrong. Try again.";
}
