from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Link
from app.services.codes import generate_code

MAX_ATTEMPTS = 5


class CodeGenerationError(Exception):
    """Raised when no unused code could be found within MAX_ATTEMPTS."""


def create_link(db: Session, original_url: str, code_length: int) -> Link:
    # Codes are random, so a collision is rare but possible. The unique constraint
    # is the source of truth: try to insert and retry on conflict.
    for _ in range(MAX_ATTEMPTS):
        link = Link(code=generate_code(code_length), original_url=original_url)
        try:
            with db.begin_nested():
                db.add(link)
        except IntegrityError:
            continue
        db.commit()
        db.refresh(link)
        return link
    raise CodeGenerationError


def get_link_by_code(db: Session, code: str) -> Link | None:
    return db.scalar(select(Link).where(Link.code == code))
