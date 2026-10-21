// What the user sees for each validation error type the API can return. The API's own
// wording is for developers, so it is replaced here with plain instructions.
const VALIDATION_MESSAGES: Record<string, string> = {
  missing: "Enter a link to shorten.",
  url_scheme: "Only http:// and https:// links can be shortened.",
  url_too_long: "That link is too long. Links can be up to 2,083 characters.",
  url_credentials: "Links can't contain a username or password.",
};
const DEFAULT_VALIDATION_MESSAGE = "Enter a link that starts with http:// or https://.";
export const GENERIC_ERROR_MESSAGE = "Something went wrong. Try again.";

/** Turns a failed API response into a message that is safe to show the user. */
export async function errorMessage(res: Response): Promise<string> {
  const data: unknown = await res.json().catch(() => null);
  if (typeof data === "object" && data !== null && "detail" in data) {
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    // FastAPI's validation errors arrive as a list; the only field is the URL.
    if (Array.isArray(detail)) {
      const first: unknown = detail[0];
      if (typeof first === "object" && first !== null && "type" in first) {
        const message = VALIDATION_MESSAGES[String(first.type)];
        if (message) return message;
      }
      return DEFAULT_VALIDATION_MESSAGE;
    }
  }
  return GENERIC_ERROR_MESSAGE;
}
