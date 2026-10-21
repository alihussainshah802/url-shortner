import re
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
# Only accept a caller-supplied id that is short and boring, so it is safe to log and
# to echo back in a header.
_SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def pick_request_id(scope: Scope) -> str:
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            if _SAFE_ID.fullmatch(candidate):
                return candidate
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Gives every request an id, stores it on request.state and returns it in X-Request-ID.

    Written as plain ASGI rather than BaseHTTPMiddleware to add almost nothing to the
    redirect hot path.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = pick_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self.app(scope, receive, send_with_id)
