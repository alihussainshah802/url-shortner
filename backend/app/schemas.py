from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator
from pydantic_core import PydanticCustomError


class LinkCreate(BaseModel):
    # HttpUrl only accepts http/https and caps the length at 2083 characters.
    url: HttpUrl

    @field_validator("url")
    @classmethod
    def reject_credentials(cls, value: HttpUrl) -> HttpUrl:
        # A link with user:password@ in it would be stored in the database, shown in
        # the UI and sent to every visitor's browser. The web form already blocks it;
        # enforce it here too so direct API calls can't bypass the form.
        if value.username or value.password:
            raise PydanticCustomError(
                "url_credentials", "Links can't contain a username or password"
            )
        return value


class LinkRead(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
