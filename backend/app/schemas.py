from datetime import datetime

from pydantic import BaseModel, HttpUrl


class LinkCreate(BaseModel):
    # HttpUrl only accepts http/https and caps the length at 2083 characters.
    url: HttpUrl


class LinkRead(BaseModel):
    code: str
    short_url: str
    original_url: str
    created_at: datetime
